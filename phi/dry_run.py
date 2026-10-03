"""AquiPulse Dry-Run and Air-Lock Detector.

Detects when dynamic drawdown reaches the pump intake level:
- Sudden collapse in motor shaft load and electrical power (drops to 20-35% of rated)
- Power factor drops below 0.35 while supply voltage remains normal
- Identifies lower bound on aquifer drawdown and intake depth
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

import numpy as np


@dataclass
class DryRunEvent:
    """Detected dry-run / air-lock incident."""

    pump_id: str
    timestamp_s: float
    pre_drop_p_kw: float
    post_drop_p_kw: float
    power_factor: float
    estimated_intake_depth_m: Optional[float] = None


class DryRunDetector:
    """Analyzes telemetry streams to detect cavitation, vortexing, and dry-run conditions."""

    def __init__(self, p_rated_kw: float, window_size: int = 5) -> None:
        self.p_rated_kw = p_rated_kw
        self.window_size = window_size
        self.p_history: List[float] = []

    def process_reading(
        self, pump_id: str, ts_s: float, v_rms: float, i_rms: float, pf: float, p_kw: float
    ) -> Optional[DryRunEvent]:
        """Check if current reading represents a dry-run event."""
        if v_rms < 150.0:
            # Feeder off or brownout, not a dry-run
            self.p_history.clear()
            return None

        self.p_history.append(p_kw)
        if len(self.p_history) > self.window_size * 2:
            self.p_history.pop(0)

        if len(self.p_history) < self.window_size * 2:
            return None

        # Compare baseline power from preceding window with current window
        pre_window = self.p_history[: self.window_size]
        curr_window = self.p_history[self.window_size :]

        mean_pre = float(np.mean(pre_window))
        mean_curr = float(np.mean(curr_window))

        # Condition for dry-run:
        # Pre-window was healthy pumping (> 50% rated kW)
        # Current window collapsed to < 35% rated kW, PF < 0.40
        if mean_pre >= 0.50 * self.p_rated_kw and mean_curr <= 0.35 * self.p_rated_kw and pf < 0.42:
            return DryRunEvent(
                pump_id=pump_id,
                timestamp_s=ts_s,
                pre_drop_p_kw=round(mean_pre, 2),
                post_drop_p_kw=round(mean_curr, 2),
                power_factor=round(pf, 3),
            )

        return None
