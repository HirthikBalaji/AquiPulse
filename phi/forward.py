"""AquiPulse Layer 1: Pump Plant Forward Model and Inversion.

Implements the physical forward model from §6.1:
- P_el(t) from shaft power and motor efficiency curve
- Total dynamic head H_d(t) = Z_s + s(t) + k_f * Q^2 + H_out
- Monotone polynomial pump curves with affinity laws
- Sensitivity analysis and Fisher information to propagate uncertainty:
  Wide uncertainty intervals near Best Efficiency Point (BEP) where dP/dQ is flat.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Tuple

import numpy as np


@dataclass
class PumpParameters:
    """Estimated or catalog parameters for a pump unit."""

    family_id: str
    hp: float
    p_rated_kw: float
    rated_head_m: float
    rated_q_lps: float
    # Head curve coeffs: H(Q) = a0 - a1*Q - a2*Q^2
    a0: float
    a1: float
    a2: float
    # Shaft power curve coeffs: P_shaft(Q) = b0 + b1*Q - b2*Q^2
    b0: float
    b1: float
    b2: float
    eta_m_max: float = 0.85
    pipe_friction_kf: float = 0.05
    wear_factor: float = 1.0


class PumpPlantModel:
    """Evaluates forward pump performance and inverts electrical telemetry into (Q, H_d, Z_s)."""

    def __init__(self, params: PumpParameters) -> None:
        self.params = params

    def motor_efficiency(self, p_shaft_kw: float) -> float:
        """Motor efficiency as a function of shaft power."""
        load = max(0.05, p_shaft_kw / max(0.1, self.params.p_rated_kw))
        eta = self.params.eta_m_max * (load / (load + 0.15 * (1.0 - 0.7 * load)))
        return float(np.clip(eta * self.params.wear_factor, 0.35, 0.94))

    def shaft_power(self, q_lps: float, speed_ratio: float = 1.0) -> float:
        """Shaft power required by the pump at given flow rate and speed ratio (omega/omega_0)."""
        w = max(0.1, speed_ratio)
        q_ref = q_lps / w
        p_ref = self.params.b0 + self.params.b1 * q_ref - self.params.b2 * (q_ref**2)
        p_ref = max(0.1, p_ref)
        p_shaft = (w**3) * p_ref / (0.85 + 0.15 * self.params.wear_factor)
        return float(p_shaft)

    def head_curve(self, q_lps: float, speed_ratio: float = 1.0) -> float:
        """Total dynamic head delivered by the pump at given flow rate and speed ratio."""
        w = max(0.1, speed_ratio)
        q_ref = q_lps / w
        h_ref = self.params.a0 - self.params.a1 * q_ref - self.params.a2 * (q_ref**2)
        h_ref = max(0.0, h_ref)
        return float((w**2) * h_ref * self.params.wear_factor)

    def forward_pel(self, q_lps: float, speed_ratio: float = 1.0) -> float:
        """Calculate electrical input power P_el from flow rate Q."""
        p_shaft = self.shaft_power(q_lps, speed_ratio)
        eta_m = self.motor_efficiency(p_shaft)
        return p_shaft / eta_m

    def invert_q_from_pel(
        self,
        p_el_kw: float,
        speed_ratio: float = 1.0,
        sigma_pel_kw: float = 0.05,
    ) -> Tuple[float, float]:
        """Invert electrical power P_el to estimate flow rate Q and its uncertainty sigma_Q.

        Near BEP, dP/dQ is small or flat -> sigma_Q automatically expands.
        Returns (q_estimated_lps, sigma_q_lps).
        """
        if p_el_kw <= 0.10:
            return 0.0, 0.0

        # Fine grid search to locate flow rate matching P_el
        q_grid = np.linspace(0.0, self.params.rated_q_lps * 2.2, 500)
        pel_grid = np.array([self.forward_pel(q, speed_ratio) for q in q_grid])

        # Find closest match
        diff = np.abs(pel_grid - p_el_kw)
        best_idx = int(np.argmin(diff))
        q_est = float(q_grid[best_idx])

        # Compute numerical gradient dP_el / dQ
        dq = 0.02
        p_plus = self.forward_pel(q_est + dq, speed_ratio)
        p_minus = self.forward_pel(max(0.0, q_est - dq), speed_ratio)
        dp_dq = (p_plus - p_minus) / (2.0 * dq)

        # Sensitivity: sigma_Q = sigma_P / |dP/dQ|
        # Clip gradient to prevent division by zero near flat BEP
        grad_magnitude = max(0.015, abs(dp_dq))
        sigma_q = float(
            np.clip(sigma_pel_kw / grad_magnitude, 0.15, self.params.rated_q_lps * 0.40)
        )

        # Extra uncertainty if pump operates far from rated envelope
        if q_est > self.params.rated_q_lps * 1.5:
            sigma_q *= 1.3

        return q_est, sigma_q

    def estimate_dynamic_and_static_head(
        self,
        q_lps: float,
        speed_ratio: float = 1.0,
        residual_drawdown_m: float = 0.0,
        sigma_q_lps: float = 0.5,
    ) -> Tuple[float, float, float, float]:
        """Estimate dynamic head H_d, static depth Z_s, and their uncertainties.

        Returns (h_dyn_m, sigma_hd_m, z_static_m, sigma_zs_m).
        """
        if q_lps <= 0.01:
            # Standby/idle head
            return 0.0, 0.0, 0.0, 0.0

        h_dyn = self.head_curve(q_lps, speed_ratio)

        # Gradient dH/dQ
        dq = 0.05
        h_plus = self.head_curve(q_lps + dq, speed_ratio)
        h_minus = self.head_curve(max(0.0, q_lps - dq), speed_ratio)
        dh_dq = abs(h_plus - h_minus) / (2.0 * dq)

        sigma_hd = float(np.clip(dh_dq * sigma_q_lps + 0.5, 0.3, 8.0))

        # Static depth Z_s = H_d - friction - discharge_head - residual_drawdown
        h_friction = self.params.pipe_friction_kf * (q_lps**2)
        h_out = 1.5
        z_static = max(1.0, h_dyn - h_friction - h_out - residual_drawdown_m)

        sigma_zs = float(math.sqrt(sigma_hd**2 + 0.8**2))

        return h_dyn, sigma_hd, z_static, sigma_zs
