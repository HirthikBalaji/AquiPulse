"""AquiPulse Adversarial Attack and Anomaly Generators.

Simulates physical and cyber tamper modes for evaluating Layer 5 (Integrity & Settlement):
- CT-Open tamper: current sensor disconnected or unlatched while voltage indicates feeder energized
- Meter Bypass: fraction of motor current diverted around split-core CT
- Replay Attack: re-transmitting genuine previously recorded telemetry stream
- Ghost Wells: clandestine unmetered borewells extracting groundwater without telemetry
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Dict, List, Optional

import numpy as np

from sim.sensor import TelemetryPacket1Hz


@dataclass
class GhostWell:
    """An unmonitored clandestine borewell extracting groundwater in secret."""

    well_id: str
    x_coord: float
    y_coord: float
    q_lps: float
    run_hours_per_day: float
    start_hour: float

    def is_active(self, sim_time_s: float) -> bool:
        """Check if ghost well is pumping at sim_time_s."""
        hour = (sim_time_s / 3600.0) % 24.0
        end = self.start_hour + self.run_hours_per_day
        if end > 24.0:
            return (hour >= self.start_hour) or (hour < (end - 24.0))
        return self.start_hour <= hour < end

    def get_rate_m3_s(self, sim_time_s: float) -> float:
        """Current extraction rate in m^3/s."""
        return (self.q_lps / 1000.0) if self.is_active(sim_time_s) else 0.0


class AdversaryManager:
    """Manages injection of physical tamper and clandestine ghost wells."""

    def __init__(self, rng: Optional[np.random.Generator] = None) -> None:
        self.rng = rng if rng is not None else np.random.default_rng(404)
        self.tampered_pumps: Dict[str, str] = {}  # pump_id -> tamper_type
        self.ghost_wells: List[GhostWell] = []
        self.replay_buffers: Dict[str, List[TelemetryPacket1Hz]] = {}

    def configure_tamper(self, pump_id: str, tamper_mode: str) -> None:
        """Set tamper mode for a pump: 'ct_open', 'bypass_50pct', 'replay'."""
        self.tampered_pumps[pump_id] = tamper_mode

    def add_ghost_well(
        self,
        well_id: str,
        x_m: float,
        y_m: float,
        q_lps: float = 5.0,
        run_hours: float = 6.0,
        start_hour: float = 14.0,
    ) -> GhostWell:
        """Add a hidden clandestine well."""
        gw = GhostWell(
            well_id=well_id,
            x_coord=x_m,
            y_coord=y_m,
            q_lps=q_lps,
            run_hours_per_day=run_hours,
            start_hour=start_hour,
        )
        self.ghost_wells.append(gw)
        return gw

    def apply_tamper(
        self, packet: Optional[TelemetryPacket1Hz], pump_id: str
    ) -> Optional[TelemetryPacket1Hz]:
        """Mutate a telemetry packet according to active adversary mode."""
        if packet is None:
            return None

        mode = self.tampered_pumps.get(pump_id)
        if mode is None:
            # Store legitimate packets for potential replay attack
            if pump_id not in self.replay_buffers:
                self.replay_buffers[pump_id] = []
            if len(self.replay_buffers[pump_id]) < 3600:
                self.replay_buffers[pump_id].append(copy.deepcopy(packet))
            return packet

        if mode == "ct_open":
            # CT unlatched: current is 0 even when voltage is nominal
            return TelemetryPacket1Hz(
                pump_id=packet.pump_id,
                timestamp_s=packet.timestamp_s,
                v_rms=packet.v_rms,
                i_rms=0.0,
                pf=0.15,
                p_kw=0.0,
                freq_hz=packet.freq_hz,
                signature="invalid_or_tampered_sig",
            )

        elif mode == "bypass_50pct":
            # Divert 50% of current around the CT clamp
            i_bypassed = round(packet.i_rms * 0.50, 2)
            p_bypassed = round(packet.p_kw * 0.50, 3)
            return TelemetryPacket1Hz(
                pump_id=packet.pump_id,
                timestamp_s=packet.timestamp_s,
                v_rms=packet.v_rms,
                i_rms=i_bypassed,
                pf=packet.pf,
                p_kw=p_bypassed,
                freq_hz=packet.freq_hz,
                signature=packet.signature,
            )

        elif mode == "replay":
            # Replay stale packet from buffer if available
            buf = self.replay_buffers.get(pump_id, [])
            if buf:
                stale_idx = int(packet.timestamp_s) % len(buf)
                stale_packet = copy.deepcopy(buf[stale_idx])
                # Maliciously keep old timestamp or update timestamp with old data
                stale_packet.timestamp_s = packet.timestamp_s
                return stale_packet

        return packet
