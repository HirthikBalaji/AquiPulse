"""AquiPulse Cooper-Jacob Drawdown Estimator and Generalized Flow Dimension.

Implements:
- Classical Cooper-Jacob (1946) straight-line method with u < 0.05 validity criterion
- Transmissivity T and uncertainty estimates
- Barker (1988) Generalized Radial Flow (GRF) dimension n parameterization for fractured rock
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional, Tuple

import numpy as np


@dataclass
class CooperJacobResult:
    """Result of Cooper-Jacob pumping test estimation."""

    pump_id: str
    t_transmissivity_m2_s: float
    log10_t: float
    sigma_log10_t: float
    ci_90_log10_t: Tuple[float, float]
    flow_dimension_n: float  # n = 2.0 for classical 2D radial; n < 2.0 for fracture linear flow
    s_storativity_est: Optional[float]  # Weakly identified from single well
    r_squared: float
    num_points_used: int
    validity_u_max: float


class CooperJacobEstimator:
    """Fits drawdown time series s(t) to identify formation transmissivity T and flow dimension n."""

    def __init__(self, well_radius_m: float = 0.10) -> None:
        self.rw = well_radius_m

    def estimate_transmissivity(
        self,
        pump_id: str,
        t_seconds: np.ndarray,
        drawdown_m: np.ndarray,
        q_avg_lps: float,
        s_prior: float = 0.025,
        fit_flow_dimension: bool = False,
    ) -> CooperJacobResult:
        """Estimate transmissivity T and flow dimension n from drawdown s(t) during pumping.

        Cooper-Jacob approximation:
            s(t) = (2.303 * Q / (4 * pi * T)) * log10(2.25 * T * t / (rw^2 * S))
        Validity requirement:
            u = (rw^2 * S) / (4 * T * t) < 0.05
        """
        # Filter positive times and drawdowns
        valid_mask = (t_seconds > 5.0) & (drawdown_m > 0.05) & np.isfinite(drawdown_m)
        t_clean = t_seconds[valid_mask]
        s_clean = drawdown_m[valid_mask]

        if len(t_clean) < 5:
            # Insufficient points: return uninformative prior
            return CooperJacobResult(
                pump_id=pump_id,
                t_transmissivity_m2_s=1e-4,
                log10_t=-4.0,
                sigma_log10_t=0.80,
                ci_90_log10_t=(-5.3, -2.7),
                flow_dimension_n=2.0,
                s_storativity_est=s_prior,
                r_squared=0.0,
                num_points_used=len(t_clean),
                validity_u_max=1.0,
            )

        q_m3_s = q_avg_lps / 1000.0

        # Initial T estimate to check u < 0.05
        log_t = np.log10(t_clean)
        # Linear regression: s = m * log10(t) + c
        m, c = np.polyfit(log_t, s_clean, 1)

        # Delta s per log10 cycle is the slope m
        delta_s = max(0.01, float(m))
        t_est = (2.303 * q_m3_s) / (4.0 * math.pi * delta_s)
        t_est = float(np.clip(t_est, 1e-6, 1.0))

        # Check Cooper-Jacob validity condition u < 0.05
        u_vals = (self.rw**2 * s_prior) / (4.0 * t_est * t_clean)
        cj_valid = u_vals < 0.05

        if np.sum(cj_valid) >= 5:
            # Refit on strictly valid portion
            t_fit = t_clean[cj_valid]
            s_fit = s_clean[cj_valid]
            log_t_fit = np.log10(t_fit)
            m, c = np.polyfit(log_t_fit, s_fit, 1)
            delta_s = max(0.01, float(m))
            t_est = (2.303 * q_m3_s) / (4.0 * math.pi * delta_s)
            t_est = float(np.clip(t_est, 1e-6, 1.0))
            u_max = float(np.max(u_vals[cj_valid]))
            n_used = len(t_fit)
            pred = m * log_t_fit + c
            ss_tot = np.sum((s_fit - np.mean(s_fit)) ** 2)
            ss_res = np.sum((s_fit - pred) ** 2)
            r2 = float(1.0 - (ss_res / max(1e-9, ss_tot)))
        else:
            u_max = float(np.max(u_vals))
            n_used = len(t_clean)
            pred = m * log_t + c
            ss_tot = np.sum((s_clean - np.mean(s_clean)) ** 2)
            ss_res = np.sum((s_clean - pred) ** 2)
            r2 = float(1.0 - (ss_res / max(1e-9, ss_tot)))

        log10_t = math.log10(t_est)

        # Residual variance and standard error on log10_T
        sigma_m = float(math.sqrt(max(1e-6, 1.0 - r2) / max(1, n_used - 2)))
        sigma_log10_t = float(np.clip(sigma_m * 1.5 + 0.08, 0.05, 0.45))

        ci_low = log10_t - 1.645 * sigma_log10_t
        ci_high = log10_t + 1.645 * sigma_log10_t

        # Single-well S estimation (intercept t0 where s=0)
        # s = m * log10(t / t0) -> t0 = 10^(-c / m)
        # S = 2.25 * T * t0 / rw^2
        t0 = 10.0 ** (-c / max(1e-4, m))
        s_est = (2.25 * t_est * t0) / (self.rw**2)
        s_est = float(np.clip(s_est, 1e-4, 0.30)) if 1e-4 <= s_est <= 0.30 else None

        # Barker Generalized Radial Flow dimension n:
        # Classical 2D radial is n=2. If curve exhibits sub-logarithmic or power-law slope:
        flow_dim = 2.0
        if fit_flow_dimension and n_used >= 8:
            # Log(s) vs Log(t) slope beta: s ~ t^beta -> beta = (2 - n) / 2 -> n = 2 - 2*beta
            log_s = np.log(np.maximum(0.01, s_clean))
            ln_t = np.log(t_clean)
            slope_power, _ = np.polyfit(ln_t, log_s, 1)
            candidate_n = 2.0 - 2.0 * float(slope_power)
            flow_dim = float(np.clip(candidate_n, 1.1, 2.9))

        return CooperJacobResult(
            pump_id=pump_id,
            t_transmissivity_m2_s=t_est,
            log10_t=round(log10_t, 3),
            sigma_log10_t=round(sigma_log10_t, 3),
            ci_90_log10_t=(round(ci_low, 3), round(ci_high, 3)),
            flow_dimension_n=round(flow_dim, 2),
            s_storativity_est=round(s_est, 4) if s_est is not None else None,
            r_squared=round(max(0.0, r2), 3),
            num_points_used=n_used,
            validity_u_max=round(u_max, 4),
        )
