"""AquiPulse Pump Catalog and Induction Motor Affinity Law Models.

Defines >=30 pump families (submersible and centrifugal, 1 to 15 HP, 1-phase and 3-phase)
with empirical H-Q and P-Q curves, motor efficiency, slip models, and degradation.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, List, Literal, Optional, Tuple

import numpy as np


@dataclass(frozen=True)
class PumpFamily:
    """Pump catalog specification for a family of commercial irrigation pumps."""

    family_id: str
    make: str
    model: str
    pump_type: Literal["submersible", "centrifugal"]
    hp: float
    phase: Literal[1, 3]
    v_rated: float
    rated_freq: float = 50.0
    poles: int = 2
    rated_slip: float = 0.045
    rated_head_m: float = 45.0
    rated_q_lps: float = 6.0
    # Head curve: H(Q) = a0 - a1*Q - a2*Q^2 (H in meters, Q in L/s at rated speed)
    h_curve_coeffs: Tuple[float, float, float] = (55.0, 1.2, 0.08)
    # Shaft power curve: P_shaft(Q) = b0 + b1*Q - b2*Q^2 (kW at rated speed)
    p_curve_coeffs: Tuple[float, float, float] = (1.5, 0.45, 0.02)
    # Motor efficiency parameters (load = P_shaft / P_rated)
    eta_m_max: float = 0.85
    eta_m_shape: float = 0.15  # drop-off rate at low load
    # Well friction factor: k_f in H_friction = k_f * Q^2
    pipe_friction_kf: float = 0.05
    description: str = ""

    @property
    def p_rated_kw(self) -> float:
        """Rated mechanical power in kW (1 HP = 0.7457 kW)."""
        return self.hp * 0.7457

    @property
    def sync_speed_rpm(self) -> float:
        """Synchronous speed in RPM at rated frequency."""
        return 120.0 * self.rated_freq / self.poles

    @property
    def rated_speed_rpm(self) -> float:
        """Nominal shaft speed at rated load in RPM."""
        return self.sync_speed_rpm * (1.0 - self.rated_slip)


@dataclass
class PumpState:
    """State and parameters of an individual installed pump instance."""

    pump_id: str
    family: PumpFamily
    wear_factor: float = 1.0  # 1.0 = brand new, 0.8 = 20% degraded
    pipe_friction_kf: float = 0.05
    z_static_m: float = 35.0  # Static groundwater depth from surface
    discharge_head_m: float = 1.5  # Surface discharge elevation / pressure head
    solar_vfd: bool = False  # True if driven by solar inverter
    noise_seed: int = 42

    def compute_slip(self, p_shaft_kw: float, v_actual: float, freq_actual: float) -> float:
        """Induction motor slip dependent on load and supply voltage.

        slip ≈ slip_rated * (P_shaft / P_rated) * (V_rated / V)^2
        """
        if self.solar_vfd:
            # Solar VFD controls frequency directly; slip is small and regulated
            return 0.02 * (p_shaft_kw / max(0.1, self.family.p_rated_kw))

        v_ratio = self.family.v_rated / max(50.0, v_actual)
        load_ratio = p_shaft_kw / max(0.1, self.family.p_rated_kw)
        slip = self.family.rated_slip * load_ratio * (v_ratio**2)
        return float(np.clip(slip, 0.005, 0.18))

    def shaft_speed_rpm(
        self, p_shaft_kw: float, v_actual: float, freq_actual: float = 50.0
    ) -> float:
        """Actual shaft speed in RPM considering grid frequency or VFD frequency and slip."""
        sync_rpm = 120.0 * freq_actual / self.family.poles
        slip = self.compute_slip(p_shaft_kw, v_actual, freq_actual)
        return sync_rpm * (1.0 - slip)

    def motor_efficiency(self, p_shaft_kw: float) -> float:
        """Motor efficiency as a function of shaft load fraction."""
        load = max(0.05, p_shaft_kw / max(0.1, self.family.p_rated_kw))
        # Monotone increasing up to ~0.8 load then flat
        eta = self.family.eta_m_max * (load / (load + self.family.eta_m_shape * (1.0 - 0.7 * load)))
        # Degradation decreases efficiency slightly
        eta *= 0.95 + 0.05 * self.wear_factor
        return float(np.clip(eta, 0.30, 0.94))

    def pump_head_curve(self, q_lps: float, speed_rpm: float) -> float:
        """Pump generated total dynamic head H (meters) using affinity laws.

        H = (omega / omega_0)^2 * f_H(Q * omega_0 / omega) * wear_factor
        """
        omega_ratio = max(0.1, speed_rpm / self.family.rated_speed_rpm)
        q_ref = q_lps / omega_ratio

        a0, a1, a2 = self.family.h_curve_coeffs
        # Monotone quadratic head-flow polynomial
        h_ref = a0 - a1 * q_ref - a2 * (q_ref**2)
        h_ref = max(0.0, h_ref)

        h_actual = (omega_ratio**2) * h_ref * self.wear_factor
        return float(h_actual)

    def pump_shaft_power_curve(self, q_lps: float, speed_rpm: float) -> float:
        """Shaft power required by the pump P_shaft (kW) using affinity laws.

        P_shaft = (omega / omega_0)^3 * f_P(Q * omega_0 / omega) / wear_factor
        """
        omega_ratio = max(0.1, speed_rpm / self.family.rated_speed_rpm)
        q_ref = q_lps / omega_ratio

        b0, b1, b2 = self.family.p_curve_coeffs
        p_ref = b0 + b1 * q_ref - b2 * (q_ref**2)
        p_ref = max(0.2, p_ref)

        # Worn pump needs slightly more shaft power for same output due to recirculation
        wear_penalty = 1.0 / (0.85 + 0.15 * self.wear_factor)
        p_shaft = (omega_ratio**3) * p_ref * wear_penalty
        return float(p_shaft)

    def solve_operating_point(
        self,
        h_static_and_drawdown_m: float,
        v_actual: float,
        freq_actual: float = 50.0,
        max_iter: int = 20,
    ) -> Tuple[float, float, float, float]:
        """Solve for operating point (Q_lps, H_dyn_m, P_shaft_kw, P_el_kw) given current water depth.

        The system curve is:
            H_sys(Q) = h_static_and_drawdown_m + self.pipe_friction_kf * Q^2 + self.discharge_head_m
        The pump curve is:
            H_pump(Q, omega(P_shaft, V, freq))
        Solves coupled nonlinear system iteratively.
        """
        # Initial guess
        q = max(0.1, self.family.rated_q_lps * 0.8)
        p_shaft = self.family.p_rated_kw * 0.75
        speed_rpm = self.family.rated_speed_rpm

        for _ in range(max_iter):
            speed_rpm = self.shaft_speed_rpm(p_shaft, v_actual, freq_actual)
            h_pump = self.pump_head_curve(q, speed_rpm)
            h_sys = h_static_and_drawdown_m + self.pipe_friction_kf * (q**2) + self.discharge_head_m

            diff = h_pump - h_sys
            if abs(diff) < 1e-4:
                break

            # Approximate derivative d(H_pump - H_sys)/dQ
            omega_ratio = max(0.1, speed_rpm / self.family.rated_speed_rpm)
            a0, a1, a2 = self.family.h_curve_coeffs
            dh_dq = -(a1 + 2 * a2 * (q / omega_ratio)) * omega_ratio - 2 * self.pipe_friction_kf * q
            step = diff / min(-0.1, dh_dq)
            q = float(np.clip(q - step, 0.0, self.family.rated_q_lps * 2.5))
            p_shaft = self.pump_shaft_power_curve(q, speed_rpm)

        # Check if head is above shutoff head (no flow condition)
        shutoff_head = self.pump_head_curve(0.0, speed_rpm)
        if h_static_and_drawdown_m + self.discharge_head_m >= shutoff_head:
            q = 0.0
            h_dyn = shutoff_head
            p_shaft = self.pump_shaft_power_curve(0.0, speed_rpm)
        else:
            h_dyn = h_static_and_drawdown_m + self.pipe_friction_kf * (q**2) + self.discharge_head_m

        eta_m = self.motor_efficiency(p_shaft)
        p_el = p_shaft / eta_m

        return q, h_dyn, p_shaft, p_el

    def compute_electrical(
        self, p_el_kw: float, v_actual: float, freq_actual: float = 50.0
    ) -> Tuple[float, float, float]:
        """Compute (V_rms, I_rms, Power_Factor) for the electrical telemetry."""
        load = float(np.clip(p_el_kw / max(0.1, self.family.p_rated_kw / 0.85), 0.1, 1.5))
        # Power factor varies with load (0.35 at idle to 0.88 at full load)
        pf = 0.35 + 0.53 * (load / (load + 0.22))
        pf = float(np.clip(pf, 0.30, 0.92))

        if self.family.phase == 3:
            # 3-phase: P = sqrt(3) * V_LL * I * PF
            i_rms = (p_el_kw * 1000.0) / max(1.0, math.sqrt(3.0) * v_actual * pf)
        else:
            # 1-phase: P = V_LN * I * PF
            i_rms = (p_el_kw * 1000.0) / max(1.0, v_actual * pf)

        return v_actual, i_rms, pf


# Comprehensive catalog of >= 35 pump families representing standard Indian/global irrigation pumps
PUMP_CATALOG: List[PumpFamily] = [
    # Submersible Deep Well Pumps (3-phase 415V, 2-pole, high head)
    PumpFamily(
        "SUB-3P-3HP-H50",
        "Kirloskar",
        "KS4-0315",
        "submersible",
        3.0,
        3,
        415.0,
        50.0,
        2,
        0.045,
        52.0,
        4.5,
        (65.0, 1.8, 0.12),
        (1.1, 0.32, 0.015),
        0.84,
        0.14,
        0.06,
        "3HP 15-stage 4in borewell pump",
    ),
    PumpFamily(
        "SUB-3P-5HP-H60",
        "Kirloskar",
        "KS4-0520",
        "submersible",
        5.0,
        3,
        415.0,
        50.0,
        2,
        0.042,
        65.0,
        6.0,
        (82.0, 2.1, 0.11),
        (1.6, 0.42, 0.016),
        0.86,
        0.13,
        0.05,
        "5HP 20-stage borewell submersible",
    ),
    PumpFamily(
        "SUB-3P-5HP-H90",
        "CRI",
        "Silver-50-25",
        "submersible",
        5.0,
        3,
        415.0,
        50.0,
        2,
        0.043,
        90.0,
        4.0,
        (110.0, 3.5, 0.22),
        (1.7, 0.46, 0.018),
        0.85,
        0.15,
        0.07,
        "5HP deep multi-stage borewell",
    ),
    PumpFamily(
        "SUB-3P-7.5HP-H70",
        "Texmo",
        "TARS-75-18",
        "submersible",
        7.5,
        3,
        415.0,
        50.0,
        2,
        0.040,
        72.0,
        8.5,
        (92.0, 1.6, 0.08),
        (2.3, 0.44, 0.012),
        0.87,
        0.12,
        0.04,
        "7.5HP high-flow deepwell submersible",
    ),
    PumpFamily(
        "SUB-3P-7.5HP-H110",
        "Falcon",
        "FAL-75-28",
        "submersible",
        7.5,
        3,
        415.0,
        50.0,
        2,
        0.038,
        115.0,
        5.5,
        (142.0, 3.2, 0.16),
        (2.4, 0.49, 0.014),
        0.87,
        0.12,
        0.06,
        "7.5HP ultra-deep well submersible",
    ),
    PumpFamily(
        "SUB-3P-10HP-H80",
        "Lubi",
        "LHL-10-16",
        "submersible",
        10.0,
        3,
        415.0,
        50.0,
        2,
        0.036,
        85.0,
        11.0,
        (112.0, 1.8, 0.06),
        (3.0, 0.48, 0.010),
        0.88,
        0.11,
        0.03,
        "10HP heavy-duty agricultural submersible",
    ),
    PumpFamily(
        "SUB-3P-10HP-H130",
        "Shakti",
        "SH-100-30",
        "submersible",
        10.0,
        3,
        415.0,
        50.0,
        2,
        0.035,
        135.0,
        7.0,
        (168.0, 3.4, 0.13),
        (3.2, 0.54, 0.012),
        0.88,
        0.11,
        0.05,
        "10HP deep basalt aquifer borewell",
    ),
    PumpFamily(
        "SUB-3P-12.5HP-H100",
        "Crompton",
        "CG-125-20",
        "submersible",
        12.5,
        3,
        415.0,
        50.0,
        2,
        0.034,
        105.0,
        12.5,
        (138.0, 1.9, 0.055),
        (3.6, 0.52, 0.009),
        0.89,
        0.10,
        0.03,
        "12.5HP farm irrigation fleet pump",
    ),
    PumpFamily(
        "SUB-3P-15HP-H120",
        "Texmo",
        "TARS-150-22",
        "submersible",
        15.0,
        3,
        415.0,
        50.0,
        2,
        0.032,
        122.0,
        14.0,
        (160.0, 1.9, 0.05),
        (4.2, 0.56, 0.008),
        0.90,
        0.10,
        0.025,
        "15HP high-capacity collective well",
    ),
    PumpFamily(
        "SUB-3P-15HP-H160",
        "Falcon",
        "FAL-150-32",
        "submersible",
        15.0,
        3,
        415.0,
        50.0,
        2,
        0.032,
        165.0,
        9.5,
        (210.0, 3.2, 0.11),
        (4.4, 0.62, 0.010),
        0.89,
        0.10,
        0.04,
        "15HP deep aquifer heavy lift",
    ),
    # Submersible Medium/Low Head 3-Phase
    PumpFamily(
        "SUB-3P-3HP-H35",
        "Taro",
        "TR-03-08",
        "submersible",
        3.0,
        3,
        415.0,
        50.0,
        2,
        0.046,
        36.0,
        7.0,
        (48.0, 1.2, 0.07),
        (1.1, 0.28, 0.012),
        0.83,
        0.16,
        0.035,
        "3HP alluvial aquifer submersible",
    ),
    PumpFamily(
        "SUB-3P-5HP-H45",
        "CRI",
        "Silver-50-12",
        "submersible",
        5.0,
        3,
        415.0,
        50.0,
        2,
        0.044,
        46.0,
        9.5,
        (60.0, 1.0, 0.05),
        (1.5, 0.36, 0.011),
        0.85,
        0.14,
        0.03,
        "5HP shallow water table borewell",
    ),
    PumpFamily(
        "SUB-3P-7.5HP-H55",
        "Lubi",
        "LHL-75-12",
        "submersible",
        7.5,
        3,
        415.0,
        50.0,
        2,
        0.041,
        56.0,
        12.0,
        (74.0, 1.1, 0.038),
        (2.1, 0.40, 0.009),
        0.86,
        0.13,
        0.025,
        "7.5HP delta region submersible",
    ),
    # Single-Phase Submersible Borewell Pumps (230V, common in smallholder farms)
    PumpFamily(
        "SUB-1P-1HP-H30",
        "Kirloskar",
        "KU4-0108",
        "submersible",
        1.0,
        1,
        230.0,
        50.0,
        2,
        0.065,
        30.0,
        2.2,
        (40.0, 2.8, 0.55),
        (0.45, 0.22, 0.035),
        0.76,
        0.22,
        0.12,
        "1HP 1-phase smallholder borewell",
    ),
    PumpFamily(
        "SUB-1P-1.5HP-H40",
        "CRI",
        "Single-15-12",
        "submersible",
        1.5,
        1,
        230.0,
        50.0,
        2,
        0.060,
        42.0,
        2.8,
        (54.0, 2.6, 0.42),
        (0.65, 0.26, 0.030),
        0.78,
        0.20,
        0.10,
        "1.5HP 1-phase borewell pump",
    ),
    PumpFamily(
        "SUB-1P-2HP-H45",
        "Texmo",
        "AQU-20-14",
        "submersible",
        2.0,
        1,
        230.0,
        50.0,
        2,
        0.055,
        48.0,
        3.5,
        (62.0, 2.4, 0.32),
        (0.85, 0.30, 0.025),
        0.80,
        0.18,
        0.08,
        "2HP 1-phase deep borewell",
    ),
    PumpFamily(
        "SUB-1P-3HP-H50",
        "Falcon",
        "FAL-1P-30",
        "submersible",
        3.0,
        1,
        230.0,
        50.0,
        2,
        0.050,
        52.0,
        4.2,
        (68.0, 2.2, 0.22),
        (1.2, 0.35, 0.020),
        0.81,
        0.17,
        0.07,
        "3HP 1-phase heavy smallholder pump",
    ),
    # Centrifugal Open-Well Submersible / Monoblock Pumps (3-phase 415V)
    PumpFamily(
        "CENT-3P-2HP-H20",
        "Kirloskar",
        "KDS-214",
        "centrifugal",
        2.0,
        3,
        415.0,
        50.0,
        2,
        0.050,
        20.0,
        6.0,
        (28.0, 0.9, 0.06),
        (0.75, 0.18, 0.008),
        0.81,
        0.18,
        0.04,
        "2HP open well centrifugal",
    ),
    PumpFamily(
        "CENT-3P-3HP-H25",
        "Texmo",
        "OWS-30",
        "centrifugal",
        3.0,
        3,
        415.0,
        50.0,
        2,
        0.048,
        25.0,
        8.5,
        (34.0, 0.7, 0.04),
        (1.0, 0.22, 0.007),
        0.83,
        0.16,
        0.03,
        "3HP open well monoblock",
    ),
    PumpFamily(
        "CENT-3P-5HP-H28",
        "CRI",
        "OW-50",
        "centrifugal",
        5.0,
        3,
        415.0,
        50.0,
        2,
        0.044,
        28.0,
        14.0,
        (38.0, 0.5, 0.02),
        (1.5, 0.26, 0.005),
        0.85,
        0.14,
        0.02,
        "5HP canal/open well high volume",
    ),
    PumpFamily(
        "CENT-3P-7.5HP-H32",
        "Lubi",
        "LOM-75",
        "centrifugal",
        7.5,
        3,
        415.0,
        50.0,
        2,
        0.040,
        34.0,
        18.0,
        (45.0, 0.45, 0.015),
        (2.1, 0.32, 0.004),
        0.86,
        0.13,
        0.015,
        "7.5HP open well heavy centrifugal",
    ),
    PumpFamily(
        "CENT-3P-10HP-H35",
        "Texmo",
        "OWS-100",
        "centrifugal",
        10.0,
        3,
        415.0,
        50.0,
        2,
        0.038,
        38.0,
        24.0,
        (50.0, 0.38, 0.010),
        (2.8, 0.35, 0.003),
        0.88,
        0.12,
        0.012,
        "10HP open well fleet pump",
    ),
    # Centrifugal Monoblock Surface / Shallow Well Pumps (1-phase 230V)
    PumpFamily(
        "CENT-1P-1HP-H15",
        "Kirloskar",
        "CHAMP-10",
        "centrifugal",
        1.0,
        1,
        230.0,
        50.0,
        2,
        0.065,
        16.0,
        3.5,
        (22.0, 1.2, 0.12),
        (0.42, 0.14, 0.010),
        0.74,
        0.24,
        0.08,
        "1HP 1-phase surface monoblock",
    ),
    PumpFamily(
        "CENT-1P-1.5HP-H20",
        "Crompton",
        "MINI-15",
        "centrifugal",
        1.5,
        1,
        230.0,
        50.0,
        2,
        0.060,
        20.0,
        4.5,
        (28.0, 1.1, 0.09),
        (0.60, 0.18, 0.009),
        0.77,
        0.21,
        0.06,
        "1.5HP surface suction pump",
    ),
    PumpFamily(
        "CENT-1P-2HP-H22",
        "Taro",
        "SURF-20",
        "centrifugal",
        2.0,
        1,
        230.0,
        50.0,
        2,
        0.055,
        23.0,
        5.8,
        (32.0, 1.0, 0.07),
        (0.80, 0.22, 0.008),
        0.79,
        0.19,
        0.05,
        "2HP 1-phase open well pump",
    ),
    # Solar VFD Optimized Submersible Pumps (compatible with DC/AC drives)
    PumpFamily(
        "SOLAR-SUB-3HP",
        "Shakti",
        "SOL-30-DCAC",
        "submersible",
        3.0,
        3,
        200.0,
        50.0,
        2,
        0.030,
        48.0,
        5.0,
        (60.0, 1.5, 0.12),
        (0.9, 0.30, 0.014),
        0.88,
        0.10,
        0.05,
        "3HP solar VFD borewell pump",
    ),
    PumpFamily(
        "SOLAR-SUB-5HP",
        "Shakti",
        "SOL-50-DCAC",
        "submersible",
        5.0,
        3,
        300.0,
        50.0,
        2,
        0.028,
        70.0,
        6.5,
        (86.0, 1.7, 0.09),
        (1.4, 0.38, 0.012),
        0.89,
        0.09,
        0.04,
        "5HP PM-KUSUM solar submersible",
    ),
    PumpFamily(
        "SOLAR-SUB-7.5HP",
        "Falcon",
        "SOL-75-INV",
        "submersible",
        7.5,
        3,
        380.0,
        50.0,
        2,
        0.025,
        95.0,
        8.0,
        (118.0, 1.8, 0.07),
        (2.0, 0.42, 0.010),
        0.90,
        0.08,
        0.035,
        "7.5HP solar VFD deep borewell",
    ),
    PumpFamily(
        "SOLAR-CENT-3HP",
        "CRI",
        "SOL-OW-30",
        "centrifugal",
        3.0,
        3,
        200.0,
        50.0,
        2,
        0.032,
        22.0,
        9.0,
        (30.0, 0.6, 0.03),
        (0.85, 0.20, 0.006),
        0.87,
        0.11,
        0.025,
        "3HP solar surface monoblock",
    ),
    PumpFamily(
        "SOLAR-CENT-5HP",
        "Lubi",
        "SOL-OW-50",
        "centrifugal",
        5.0,
        3,
        300.0,
        50.0,
        2,
        0.030,
        26.0,
        15.0,
        (35.0, 0.45, 0.016),
        (1.3, 0.24, 0.004),
        0.88,
        0.10,
        0.018,
        "5HP solar open-well pump",
    ),
    # High-Lift 4-Pole Medium Speed Pumps (1500 RPM, low wear, high torque)
    PumpFamily(
        "SUB-3P-4P-5HP",
        "Texmo",
        "T4P-05",
        "submersible",
        5.0,
        3,
        415.0,
        50.0,
        4,
        0.040,
        40.0,
        8.0,
        (52.0, 1.0, 0.05),
        (1.5, 0.38, 0.010),
        0.86,
        0.12,
        0.03,
        "5HP 4-pole durable borewell pump",
    ),
    PumpFamily(
        "SUB-3P-4P-7.5HP",
        "Kirloskar",
        "K4P-07",
        "submersible",
        7.5,
        3,
        415.0,
        50.0,
        4,
        0.036,
        55.0,
        11.0,
        (70.0, 0.9, 0.035),
        (2.2, 0.42, 0.008),
        0.87,
        0.11,
        0.025,
        "7.5HP 4-pole high reliability",
    ),
    PumpFamily(
        "SUB-3P-4P-10HP",
        "CRI",
        "C4P-10",
        "submersible",
        10.0,
        3,
        415.0,
        50.0,
        4,
        0.034,
        68.0,
        14.0,
        (88.0, 0.85, 0.025),
        (2.9, 0.46, 0.007),
        0.88,
        0.10,
        0.02,
        "10HP 4-pole collective irrigation",
    ),
    PumpFamily(
        "CENT-3P-4P-5HP",
        "Lubi",
        "L4P-OW5",
        "centrifugal",
        5.0,
        3,
        415.0,
        50.0,
        4,
        0.042,
        22.0,
        16.0,
        (30.0, 0.4, 0.012),
        (1.4, 0.24, 0.004),
        0.86,
        0.12,
        0.015,
        "5HP 4-pole high volume centrifugal",
    ),
    PumpFamily(
        "CENT-3P-4P-7.5HP",
        "Falcon",
        "F4P-OW7",
        "centrifugal",
        7.5,
        3,
        415.0,
        50.0,
        4,
        0.038,
        28.0,
        22.0,
        (38.0, 0.35, 0.008),
        (2.1, 0.28, 0.003),
        0.88,
        0.11,
        0.012,
        "7.5HP 4-pole heavy canal lift",
    ),
]


def get_catalog() -> Dict[str, PumpFamily]:
    """Return dictionary of all available pump families keyed by family_id."""
    return {f.family_id: f for f in PUMP_CATALOG}


def create_pump_instance(
    pump_id: str,
    family_id: str,
    z_static_m: float = 35.0,
    wear_years: float = 0.0,
    solar_vfd: bool = False,
    rng: Optional[np.random.Generator] = None,
) -> PumpState:
    """Instantiate a physical pump instance with realistic manufacturing variability and wear."""
    catalog = get_catalog()
    if family_id not in catalog:
        raise ValueError(f"Unknown pump family: {family_id}")

    family = catalog[family_id]
    if rng is None:
        rng = np.random.default_rng(42)

    # Slight individual manufacturing variation (+- 3%)
    h_var = 1.0 + float(rng.normal(0.0, 0.025))
    # Wear degradation: ~2% loss of head per year of heavy use, bounded [0.75, 1.0]
    wear = (
        float(np.clip(1.0 - 0.02 * wear_years + float(rng.normal(0.0, 0.015)), 0.75, 1.0)) * h_var
    )

    friction = float(
        np.clip(family.pipe_friction_kf * (1.0 + float(rng.normal(0.0, 0.05))), 0.01, 0.20)
    )
    discharge_h = 1.0 + float(rng.uniform(0.0, 1.5))

    return PumpState(
        pump_id=pump_id,
        family=family,
        wear_factor=wear,
        pipe_friction_kf=friction,
        z_static_m=z_static_m,
        discharge_head_m=discharge_h,
        solar_vfd=solar_vfd,
        noise_seed=int(rng.integers(0, 1_000_000)),
    )
