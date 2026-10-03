"""AquiPulse Rural Electrical Feeder Simulator.

Simulates:
- 3-phase (415V LL) and 1-phase (230V LN) agricultural feeders
- Feeder supply schedule (typical Indian DISCOM 6-8 hours/day roster, rotating day/night)
- Load-dependent voltage sags (down to 320V under heavy fleet pumping) and off-peak swells
- Phase unbalance (2-8%) and grid frequency noise (50.0 +- 0.2 Hz)
- Random brief voltage dips and unplanned outages
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional, Tuple

import numpy as np


@dataclass
class FeederConfig:
    """Agricultural electrical feeder parameters."""

    feeder_id: str = "FEEDER-AG-01"
    nominal_v_3p: float = 415.0  # Line-to-line RMS volts
    nominal_v_1p: float = 230.0  # Line-to-neutral RMS volts
    nominal_freq: float = 50.0  # Hz
    hours_per_day: float = 7.0  # Daily supply roster duration
    feeder_impedance_ohm: float = 0.8  # Aggregated distribution line resistance
    base_sag_pct: float = 0.08  # Typical base loading sag
    phase_unbalance_pct: float = 0.035  # Phase-to-phase asymmetry


class RuralFeeder:
    """Simulates power availability, voltage sag/swell, and frequency at farm nodes."""

    def __init__(self, config: FeederConfig, rng: Optional[np.random.Generator] = None) -> None:
        self.config = config
        self.rng = rng if rng is not None else np.random.default_rng(101)

        # Scheduled supply window for the week (start hour of supply, 0 to 24)
        # Week 1: Daytime supply (09:00 - 16:00), Week 2: Nighttime (22:00 - 05:00)
        self.supply_start_hour = 8.5
        self.supply_duration_hours = config.hours_per_day

    def is_power_available(self, sim_time_seconds: float) -> bool:
        """Determine if grid power is energized on the agricultural feeder."""
        time_hours = (sim_time_seconds / 3600.0) % 24.0
        start = self.supply_start_hour
        end = start + self.supply_duration_hours

        # Weekly roster shift (e.g. shifts by 12 hours every 7 days)
        day_index = int(sim_time_seconds / 86400.0)
        if (day_index // 7) % 2 == 1:
            # Shifted to night roster
            start = 22.0
            end = 22.0 + self.supply_duration_hours

        if end > 24.0:
            # Wraps past midnight
            in_window = (time_hours >= start) or (time_hours < (end - 24.0))
        else:
            in_window = start <= time_hours < end

        if not in_window:
            return False

        # Random unplanned outages / tripping (2% probability per hour)
        unplanned_outage_hash = math.sin(sim_time_seconds / 1800.0 + 42.0)
        if unplanned_outage_hash > 0.985:
            return False

        return True

    def get_voltage_and_frequency(
        self,
        sim_time_seconds: float,
        fleet_active_kw: float = 0.0,
        phase: int = 3,
        node_feeder_distance_km: float = 2.5,
    ) -> Tuple[float, float]:
        """Compute instantaneous supply voltage (RMS V) and frequency (Hz).

        Accounting for:
        - Fleet loading causing proportional feeder voltage sag: V = V_nom * (1 - sag)
        - Tail-end vs head-end feeder location (distance drop)
        - Grid frequency fluctuations
        """
        if not self.is_power_available(sim_time_seconds):
            return 0.0, 0.0

        v_nom = self.config.nominal_v_3p if phase == 3 else self.config.nominal_v_1p

        # Fleet loading sag (e.g. 500 kW fleet causes ~12% drop at tail-end)
        load_sag_fraction = (fleet_active_kw / 2000.0) * (node_feeder_distance_km / 3.0) * 0.15
        base_sag = self.config.base_sag_pct + load_sag_fraction

        # Diurnal swell/sag wave
        hour = (sim_time_seconds / 3600.0) % 24.0
        diurnal_variation = 0.04 * math.sin(2.0 * math.pi * (hour - 14.0) / 24.0)

        # Instantaneous random fluctuations (+- 1.5%)
        noise = float(self.rng.normal(0.0, 0.015))

        v_mult = 1.0 - base_sag + diurnal_variation + noise
        v_actual = float(np.clip(v_nom * v_mult, 0.70 * v_nom, 1.15 * v_nom))

        # Grid frequency: 50.0 Hz +/- 0.15 Hz
        freq_drift = 0.12 * math.sin(sim_time_seconds / 300.0) + float(self.rng.normal(0.0, 0.03))
        freq_actual = float(np.clip(self.config.nominal_freq + freq_drift, 49.2, 50.8))

        return v_actual, freq_actual
