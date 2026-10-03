"""AquiPulse Restart-Residual Recovery Regression.

When a pump is OFF, there is no electrical signal. Recovery is observed only
at subsequent restarts as a single residual drawdown sample at off-duration t'.
Regresses residual drawdown across many cycles with varying off-durations,
incorporating a regional aquifer background trend drift term.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Tuple

import numpy as np


@dataclass
class PumpingCycleSummary:
    """Historical pumping run and subsequent rest interval."""

    cycle_id: int
    t_pump_seconds: float  # Pumping duration
    t_off_seconds: float  # Shut-in rest duration before next restart
    q_avg_lps: float
    residual_drawdown_m: float  # Head drop remaining at restart vs seasonal static
    calendar_day: float


@dataclass
class RecoveryRegressionResult:
    """Hydrogeological parameters derived from restart residuals."""

    pump_id: str
    t_recovery_m2_s: float
    log10_t: float
    sigma_log10_t: float
    ci_90_log10_t: Tuple[float, float]
    regional_drift_m_per_day: float
    r_squared: float
    num_cycles: int


class RestartRecoveryRegressor:
    """Performs multi-cycle recovery regression using restart residual drawdowns."""

    def estimate_recovery_transmissivity(
        self,
        pump_id: str,
        cycles: List[PumpingCycleSummary],
    ) -> RecoveryRegressionResult:
        """Fit Theis recovery equation with regional drift:

        s_res = c0 + (2.303 * Q_bar / (4 * pi * T)) * log10( (t_pump + t_off) / t_off ) + beta_drift * days
        """
        valid_cycles = [
            c
            for c in cycles
            if c.t_off_seconds > 60.0 and c.t_pump_seconds > 300.0 and c.residual_drawdown_m > 0.0
        ]

        if len(valid_cycles) < 3:
            # Fallback prior
            return RecoveryRegressionResult(
                pump_id=pump_id,
                t_recovery_m2_s=1e-4,
                log10_t=-4.0,
                sigma_log10_t=0.60,
                ci_90_log10_t=(-5.0, -3.0),
                regional_drift_m_per_day=0.0,
                r_squared=0.0,
                num_cycles=len(valid_cycles),
            )

        n = len(valid_cycles)
        # Formulate linear regression design matrix
        # y = s_res
        # X = [1, log10( (t_pump + t_off) / t_off ), calendar_day]
        y = np.array([c.residual_drawdown_m for c in valid_cycles], dtype=np.float64)
        x_theis = np.array(
            [
                math.log10((c.t_pump_seconds + c.t_off_seconds) / c.t_off_seconds)
                for c in valid_cycles
            ],
            dtype=np.float64,
        )
        x_day = np.array([c.calendar_day for c in valid_cycles], dtype=np.float64)
        x_day_centered = x_day - np.mean(x_day)

        X = np.column_stack([np.ones(n), x_theis, x_day_centered])

        # Ordinary Least Squares: beta = (X^T X)^-1 X^T y
        try:
            beta, residuals, rank, s = np.linalg.lstsq(X, y, rcond=None)
            _c0, m_theis, beta_drift = float(beta[0]), float(beta[1]), float(beta[2])
        except Exception:
            _c0, m_theis, beta_drift = float(np.mean(y)), 0.5, 0.0

        # Mean flow rate in m^3/s
        q_avg_m3_s = float(np.mean([c.q_avg_lps for c in valid_cycles])) / 1000.0

        # T = 2.303 * Q_bar / (4 * pi * m_theis)
        m_theis_clamped = max(0.02, m_theis)
        t_est = (2.303 * q_avg_m3_s) / (4.0 * math.pi * m_theis_clamped)
        t_est = float(np.clip(t_est, 1e-6, 1.0))
        log10_t = math.log10(t_est)

        # R^2 and uncertainty
        y_pred = X @ beta
        ss_tot = np.sum((y - np.mean(y)) ** 2)
        ss_res = np.sum((y - y_pred) ** 2)
        r2 = float(1.0 - (ss_res / max(1e-9, ss_tot)))

        sigma_log10 = float(np.clip(math.sqrt(max(0.01, 1.0 - r2)) * 0.45 + 0.08, 0.06, 0.50))

        return RecoveryRegressionResult(
            pump_id=pump_id,
            t_recovery_m2_s=t_est,
            log10_t=round(log10_t, 3),
            sigma_log10_t=round(sigma_log10, 3),
            ci_90_log10_t=(
                round(log10_t - 1.645 * sigma_log10, 3),
                round(log10_t + 1.645 * sigma_log10, 3),
            ),
            regional_drift_m_per_day=round(beta_drift, 4),
            r_squared=round(max(0.0, r2), 3),
            num_cycles=n,
        )
