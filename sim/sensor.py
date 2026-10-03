"""AquiPulse Node G and Node S Edge Sensor Simulator.

Implements:
- 1 Hz RMS electrical telemetry (V_rms, I_rms, PF, P_kw, freq_hz) with CT/ADC noise,
  scaling error (+-1-2%), clock drift, and packet dropouts
- 4 kHz 60-second start-burst transient capturing motor inrush current and the physical
  borewell riser pipe column-filling power ramp
- Cryptographic payload signing simulating on-board secure element (ECDSA/HMAC)
"""

from __future__ import annotations

import hashlib
import hmac
import math
from dataclasses import dataclass
from typing import Dict, Optional

import numpy as np


@dataclass
class TelemetryPacket1Hz:
    """1 Hz steady-state electrical telemetry reading."""

    pump_id: str
    timestamp_s: float
    v_rms: float
    i_rms: float
    pf: float
    p_kw: float
    freq_hz: float
    signature: str


@dataclass
class StartBurstRecord:
    """High-frequency 4 kHz start transient record (60 seconds)."""

    pump_id: str
    timestamp_start_s: float
    fs_hz: int
    duration_s: float
    samples_raw: bytes  # Packed binary float16/int16 waveforms
    metadata: Dict[str, float]


class EdgeSensorNode:
    """Emulates a physical Node G (grid clamp-on) or Node S (solar Modbus/AC) sensor."""

    def __init__(
        self,
        pump_id: str,
        secret_key: bytes,
        ct_ratio_error: float = 0.0,
        adc_offset_volts: float = 0.0,
        packet_loss_rate: float = 0.015,
        clock_drift_ppm: float = 5.0,
        rng: Optional[np.random.Generator] = None,
    ) -> None:
        self.pump_id = pump_id
        self.secret_key = secret_key
        self.ct_ratio_error = ct_ratio_error  # e.g. +0.01 for +1% CT ratio error
        self.adc_offset_volts = adc_offset_volts
        self.packet_loss_rate = packet_loss_rate
        self.clock_drift_ppm = clock_drift_ppm
        self.rng = rng if rng is not None else np.random.default_rng(303)

        self.last_state_was_running = False
        self.accumulated_clock_drift_s = 0.0

    def generate_telemetry_1hz(
        self,
        sim_time_s: float,
        v_true: float,
        i_true: float,
        pf_true: float,
        p_kw_true: float,
        freq_true: float,
    ) -> Optional[TelemetryPacket1Hz]:
        """Generate a single 1 Hz telemetry packet with sensor noise and imperfections."""
        # Check packet loss
        if float(self.rng.uniform(0.0, 1.0)) < self.packet_loss_rate:
            return None

        # Clock drift accumulation: drift_ppm * dt
        self.accumulated_clock_drift_s += (self.clock_drift_ppm * 1e-6) * 1.0
        sensed_ts = sim_time_s + self.accumulated_clock_drift_s

        if p_kw_true <= 0.001 or v_true <= 10.0:
            # Pump is OFF (standby / idle / line de-energized)
            v_meas = float(
                np.clip(v_true + self.adc_offset_volts + self.rng.normal(0.0, 0.4), 0.0, 600.0)
            )
            return TelemetryPacket1Hz(
                pump_id=self.pump_id,
                timestamp_s=round(sensed_ts, 3),
                v_rms=round(v_meas, 2),
                i_rms=0.0,
                pf=1.0,
                p_kw=0.0,
                freq_hz=round(freq_true, 2),
                signature=self._sign_packet(self.pump_id, sensed_ts, v_meas, 0.0, 0.0),
            )

        # Apply CT scaling error and Gaussian measurement noise
        v_noise = float(self.rng.normal(0.0, 0.6))
        v_meas = float(
            np.clip(
                v_true * (1.0 + self.ct_ratio_error * 0.5) + self.adc_offset_volts + v_noise,
                0.0,
                600.0,
            )
        )

        i_noise = float(self.rng.normal(0.0, 0.04))
        i_meas = float(np.clip(i_true * (1.0 + self.ct_ratio_error) + i_noise, 0.0, 200.0))

        pf_noise = float(self.rng.normal(0.0, 0.008))
        pf_meas = float(np.clip(pf_true + pf_noise, 0.10, 0.99))

        p_kw_meas = float(
            np.clip(
                p_kw_true * (1.0 + self.ct_ratio_error) + float(self.rng.normal(0.0, 0.02)),
                0.0,
                100.0,
            )
        )

        freq_noise = float(self.rng.normal(0.0, 0.02))
        freq_meas = float(np.clip(freq_true + freq_noise, 20.0, 65.0))

        sig = self._sign_packet(self.pump_id, sensed_ts, v_meas, i_meas, p_kw_meas)

        return TelemetryPacket1Hz(
            pump_id=self.pump_id,
            timestamp_s=round(sensed_ts, 3),
            v_rms=round(v_meas, 2),
            i_rms=round(i_meas, 2),
            pf=round(pf_meas, 3),
            p_kw=round(p_kw_meas, 3),
            freq_hz=round(freq_meas, 2),
            signature=sig,
        )

    def generate_start_burst(
        self,
        timestamp_start_s: float,
        z_static_depth_m: float,
        q_steady_lps: float,
        p_steady_kw: float,
        v_rms: float,
        duration_s: float = 60.0,
        fs_hz: int = 4000,
    ) -> StartBurstRecord:
        """Synthesize high-resolution (4 kHz, 60-second) start transient.

        Physical transient phases:
        Phase 1 (0.0 to 0.35s): Motor electrical locked-rotor inrush current (5-7x rated).
        Phase 2 (0.35s to t_fill): Water column acceleration and riser pipe filling.
                Head against the pump starts low (water accelerating through empty pipe)
                and ramps up as water column climbs to surface discharge, taking
                t_fill ≈ (pipe_volume / Q) seconds (typically 4 - 25 seconds).
                During this phase, power ramps from partial load to full load!
        Phase 3 (t_fill to 60s): Steady-state flow with dynamic drawdown cone formation.
        """
        num_samples = int(duration_s * fs_hz)
        t = np.linspace(0.0, duration_s, num_samples, endpoint=False)

        # Estimate column fill duration based on physical static depth Z_s
        # 2.5-inch or 3-inch riser pipe: ~3.5 to 5.0 Liters per meter
        pipe_liters_per_m = 4.2
        total_pipe_volume_l = max(10.0, z_static_depth_m * pipe_liters_per_m)
        t_fill = float(np.clip(total_pipe_volume_l / max(0.5, q_steady_lps), 3.0, 35.0))

        # Instantaneous RMS envelope of current: I_env(t)
        i_rated = (p_steady_kw * 1000.0) / (math.sqrt(3.0) * max(100.0, v_rms) * 0.85)

        # Inrush transient: 6.0x decaying with tau ~ 0.08 s
        inrush_envelope = 5.5 * i_rated * np.exp(-t / 0.08)

        # Column fill power/current ramp:
        # Before fill completes, back-pressure is lower, flow is higher, power ramps from ~0.65 to 1.0
        fill_progress = np.clip(t / t_fill, 0.0, 1.0)
        ramp_envelope = i_rated * (0.68 + 0.32 * (fill_progress**0.8))

        i_envelope = inrush_envelope + ramp_envelope
        # Slight line noise and pump vibration ripple (10-30 Hz)
        vibration_ripple = (
            1.0 + 0.03 * np.sin(2.0 * np.pi * 24.5 * t) + 0.015 * np.sin(2.0 * np.pi * 49.0 * t)
        )
        i_envelope *= vibration_ripple

        # AC waveform: 50 Hz fundamental + 3rd and 5th harmonics
        phi_rad = math.acos(0.85)
        phase_angle = 2.0 * np.pi * 50.0 * t - phi_rad
        waveform = (
            math.sqrt(2.0)
            * i_envelope
            * (
                np.sin(phase_angle)
                + 0.04 * np.sin(3.0 * phase_angle)
                + 0.02 * np.sin(5.0 * phase_angle)
            )
        )

        # Quantize to 16-bit signed integer (scale factor: 100 counts per Ampere)
        waveform_int16 = np.clip(waveform * 100.0, -32767, 32767).astype(np.int16)
        raw_bytes = waveform_int16.tobytes()

        metadata = {
            "t_fill_s": round(t_fill, 2),
            "z_static_truth_m": round(z_static_depth_m, 2),
            "q_steady_truth_lps": round(q_steady_lps, 2),
            "p_steady_truth_kw": round(p_steady_kw, 2),
        }

        return StartBurstRecord(
            pump_id=self.pump_id,
            timestamp_start_s=timestamp_start_s,
            fs_hz=fs_hz,
            duration_s=duration_s,
            samples_raw=raw_bytes,
            metadata=metadata,
        )

    def _sign_packet(self, pump_id: str, ts: float, v: float, i: float, p: float) -> str:
        """Create HMAC-SHA256 signature for telemetry validation."""
        payload = f"{pump_id}:{ts:.3f}:{v:.2f}:{i:.2f}:{p:.2f}".encode("utf-8")
        return hmac.new(self.secret_key, payload, hashlib.sha256).hexdigest()
