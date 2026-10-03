"""AquiPulse Crowd Hydraulic Interference Tomography.

Solves the multi-well cross-interference problem:
- Single-well pumping tests cannot reliably identify storativity S (due to unknown casing skin and rw).
- When well A pumps, its cone of depression diffuses outward to neighbor B at distance r_AB.
- At well B's next start, the initial water level records the diffused interference drawdown of A.
- Jointly inverts cross-well interference events to estimate storativity S and inter-well T.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Tuple

import numpy as np
from scipy.special import exp1  # Theis well function W(u) = E_1(u)


@dataclass
class WellEvent:
    """Historical pumping event at a well."""

    pump_id: str
    x_m: float
    y_m: float
    t_start_s: float
    t_stop_s: float
    q_lps: float


@dataclass
class InterferenceObservation:
    """Observed head shift at well B caused by pumping at neighboring well A."""

    source_pump_id: str
    target_pump_id: str
    distance_r_m: float
    dt_since_source_start_s: float
    dt_since_source_stop_s: float
    q_source_lps: float
    observed_drawdown_m: float


@dataclass
class TomographyResult:
    """Inverted aquifer properties from crowd interference."""

    estimated_s_storativity: float
    sigma_log10_s: float
    ci_90_s: Tuple[float, float]
    inter_well_t_m2_s: float
    num_interference_pairs: int
    identifiability_status: str  # "Identified", "Weak", or "Unidentified"


class HydraulicInterferenceTomography:
    """Inverts multi-well start/stop schedules and restart heads for storativity S."""

    def __init__(self, max_distance_m: float = 1200.0) -> None:
        self.max_distance_m = max_distance_m

    def theis_drawdown(
        self,
        r_m: float,
        t_elapsed_s: float,
        q_lps: float,
        transmissivity: float,
        storativity: float,
    ) -> float:
        """Theis line-source drawdown s = (Q / 4*pi*T) * W(u)."""
        if t_elapsed_s <= 10.0 or r_m <= 1.0 or q_lps <= 0.0:
            return 0.0

        u = (r_m**2 * storativity) / (4.0 * transmissivity * t_elapsed_s)
        if u > 10.0:
            return 0.0  # Cone has not reached distance r yet

        q_m3_s = q_lps / 1000.0
        w_u = float(exp1(u))
        return float((q_m3_s / (4.0 * math.pi * transmissivity)) * w_u)

    def theis_pulse_drawdown(
        self,
        r_m: float,
        t_since_start_s: float,
        t_since_stop_s: float,
        q_lps: float,
        t_m2_s: float,
        s_val: float,
    ) -> float:
        """Theis drawdown from a bounded pulse pumping event."""
        s1 = self.theis_drawdown(r_m, t_since_start_s, q_lps, t_m2_s, s_val)
        if t_since_stop_s > 0.0:
            s2 = self.theis_drawdown(r_m, t_since_stop_s, q_lps, t_m2_s, s_val)
            return max(0.0, s1 - s2)
        return max(0.0, s1)

    def invert_storativity(
        self,
        observations: List[InterferenceObservation],
        prior_t_m2_s: float = 1.5e-4,
    ) -> TomographyResult:
        """Invert multi-pair interference observations for formation storativity S."""
        valid_obs = [
            o
            for o in observations
            if 30.0 <= o.distance_r_m <= self.max_distance_m and o.observed_drawdown_m > 0.02
        ]

        if len(valid_obs) < 3:
            # Insufficient cross-well interference signal
            return TomographyResult(
                estimated_s_storativity=0.025,
                sigma_log10_s=0.70,
                ci_90_s=(0.005, 0.125),
                inter_well_t_m2_s=prior_t_m2_s,
                num_interference_pairs=len(valid_obs),
                identifiability_status="Unidentified (insufficient close-neighbor events)",
            )

        # 1D grid search over log10(S) in [0.005, 0.10]
        s_grid = np.logspace(math.log10(0.003), math.log10(0.08), 80)
        t_candidates = [prior_t_m2_s * 0.7, prior_t_m2_s, prior_t_m2_s * 1.4]

        best_loss = float("inf")
        best_s = 0.025
        best_t = prior_t_m2_s

        for t_test in t_candidates:
            for s_test in s_grid:
                loss = 0.0
                for obs in valid_obs:
                    pred_s = self.theis_pulse_drawdown(
                        r_m=obs.distance_r_m,
                        t_since_start_s=obs.dt_since_source_start_s,
                        t_since_stop_s=obs.dt_since_source_stop_s,
                        q_lps=obs.q_source_lps,
                        t_m2_s=t_test,
                        s_val=s_test,
                    )
                    loss += (obs.observed_drawdown_m - pred_s) ** 2

                if loss < best_loss:
                    best_loss = loss
                    best_s = float(s_test)
                    best_t = float(t_test)

        log10_s = math.log10(best_s)
        sigma_log_s = float(np.clip(0.35 / math.sqrt(len(valid_obs)), 0.12, 0.45))
        ci_low = float(10.0 ** (log10_s - 1.645 * sigma_log_s))
        ci_high = float(10.0 ** (log10_s + 1.645 * sigma_log_s))

        status = "Identified" if len(valid_obs) >= 8 else "Weak"

        return TomographyResult(
            estimated_s_storativity=round(best_s, 4),
            sigma_log10_s=round(sigma_log_s, 3),
            ci_90_s=(round(ci_low, 4), round(ci_high, 4)),
            inter_well_t_m2_s=round(best_t, 6),
            num_interference_pairs=len(valid_obs),
            identifiability_status=status,
        )
