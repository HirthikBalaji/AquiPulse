"""AquiPulse Jacob Step-Drawdown Well Loss Separation (B and C coefficients).

Separates:
- B: Laminar aquifer formation loss coefficient (s/m^2)
- C: Turbulent casing and screen entrance well loss coefficient (s^2/m^5)
Using multi-rate operating steps (e.g. VFD sweeps or voltage/head step shifts).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class WellLossResult:
    """Estimated well-loss coefficients."""

    pump_id: str
    b_formation_loss: float  # s/m^2
    c_turbulent_loss: float  # s^2/m^5
    well_efficiency_pct: float  # B*Q / (B*Q + C*Q^2) * 100 at rated Q
    r_squared: float


class JacobWellLossEstimator:
    """Estimates Jacob well-loss equation s_w = B*Q + C*Q^2 from multi-rate operating points."""

    def estimate_coefficients(
        self,
        pump_id: str,
        q_steps_lps: np.ndarray,
        drawdown_steps_m: np.ndarray,
        rated_q_lps: float = 6.0,
    ) -> WellLossResult:
        """Fit specific drawdown (s_w / Q) = B + C * Q via linear regression."""
        # Convert Q to m^3/s
        q_m3_s = q_steps_lps / 1000.0

        valid = (q_m3_s > 0.0005) & (drawdown_steps_m > 0.05)
        q_val = q_m3_s[valid]
        s_val = drawdown_steps_m[valid]

        if len(q_val) < 2:
            # Fallback default
            return WellLossResult(
                pump_id=pump_id,
                b_formation_loss=350.0,
                c_turbulent_loss=25000.0,
                well_efficiency_pct=75.0,
                r_squared=0.0,
            )

        # Specific drawdown: y = s / Q
        y = s_val / q_val

        # Linear fit: y = C * Q + B
        slope_c, intercept_b = np.polyfit(q_val, y, 1)

        # Ensure physical non-negativity
        b_est = float(max(10.0, intercept_b))
        c_est = float(max(100.0, slope_c))

        # Well efficiency at rated flow
        q_rated_m3_s = rated_q_lps / 1000.0
        s_lam = b_est * q_rated_m3_s
        s_turb = c_est * (q_rated_m3_s**2)
        well_eff = float(100.0 * s_lam / max(1e-4, s_lam + s_turb))
        well_eff = float(np.clip(well_eff, 20.0, 95.0))

        # R^2
        y_pred = c_est * q_val + b_est
        ss_tot = np.sum((y - np.mean(y)) ** 2)
        ss_res = np.sum((y - y_pred) ** 2)
        r2 = float(1.0 - (ss_res / max(1e-9, ss_tot)))

        return WellLossResult(
            pump_id=pump_id,
            b_formation_loss=round(b_est, 1),
            c_turbulent_loss=round(c_est, 1),
            well_efficiency_pct=round(well_eff, 1),
            r_squared=round(max(0.0, r2), 3),
        )
