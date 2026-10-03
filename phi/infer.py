"""AquiPulse High-Level PHI Inference Coordinator.

Integrates:
- Forward model curve inversion
- Burst transient column-fill extraction
- Hierarchical parameter adjustments
- Field audit calibration
- Produces final (value, sigma) estimates with calibrated 90% intervals
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, Tuple

import numpy as np

from phi.bayes_model import AuditLabel
from phi.burst_features import BurstFeatureExtractor, BurstFeatures
from phi.dry_run import DryRunDetector
from phi.forward import PumpParameters, PumpPlantModel
from sim.catalog import get_catalog


@dataclass
class PhiStateResult:
    """Estimated instantaneous operational and hydrogeological state of a pump."""

    pump_id: str
    timestamp_s: float
    q_lps: float
    sigma_q_lps: float
    q_ci_90: Tuple[float, float]
    h_dyn_m: float
    sigma_hd_m: float
    z_static_m: float
    sigma_zs_m: float
    zs_ci_90: Tuple[float, float]
    eta_overall: float
    is_running: bool
    is_dry_run: bool = False


class PhiEngine:
    """Fleet-scale Pump Heartbeat Inference Engine."""

    def __init__(self) -> None:
        self.catalog = get_catalog()
        self.burst_extractor = BurstFeatureExtractor()
        self.pump_models: Dict[str, PumpPlantModel] = {}
        self.dry_run_detectors: Dict[str, DryRunDetector] = {}
        self.audit_labels: Dict[str, AuditLabel] = {}
        self.cached_burst_zs: Dict[str, float] = {}

    def register_pump(
        self,
        pump_id: str,
        family_id: str,
        wear_estimate: float = 0.95,
    ) -> None:
        """Initialize models for a newly onboarded pump."""
        if family_id not in self.catalog:
            raise ValueError(f"Unknown family: {family_id}")

        fam = self.catalog[family_id]
        a0, a1, a2 = fam.h_curve_coeffs
        b0, b1, b2 = fam.p_curve_coeffs

        params = PumpParameters(
            family_id=family_id,
            hp=fam.hp,
            p_rated_kw=fam.p_rated_kw,
            rated_head_m=fam.rated_head_m,
            rated_q_lps=fam.rated_q_lps,
            a0=a0,
            a1=a1,
            a2=a2,
            b0=b0,
            b1=b1,
            b2=b2,
            eta_m_max=fam.eta_m_max,
            pipe_friction_kf=fam.pipe_friction_kf,
            wear_factor=wear_estimate,
        )

        self.pump_models[pump_id] = PumpPlantModel(params)
        self.dry_run_detectors[pump_id] = DryRunDetector(p_rated_kw=fam.p_rated_kw)

    def register_audit(self, audit: AuditLabel) -> None:
        """Register a ground-truth bucket test and dip-well reading to calibrate pump."""
        self.audit_labels[audit.pump_id] = audit

    def process_start_burst(
        self,
        pump_id: str,
        timestamp_s: float,
        samples_raw: bytes,
        q_prior_lps: float = 5.0,
    ) -> BurstFeatures:
        """Extract column fill and initial static head from start burst."""
        features = self.burst_extractor.extract_features(
            raw_samples_bytes=samples_raw,
            q_est_lps=q_prior_lps,
            pump_id=pump_id,
            timestamp_s=timestamp_s,
        )
        self.cached_burst_zs[pump_id] = features.z_static_est_m
        return features

    def infer_instantaneous_state(
        self,
        pump_id: str,
        timestamp_s: float,
        v_rms: float,
        i_rms: float,
        pf: float,
        p_kw: float,
        freq_hz: float = 50.0,
        residual_drawdown_m: float = 0.0,
    ) -> PhiStateResult:
        """Perform PHI inference on a single 1 Hz telemetry reading."""
        if pump_id not in self.pump_models:
            raise KeyError(f"Pump {pump_id} not registered")

        model = self.pump_models[pump_id]
        detector = self.dry_run_detectors[pump_id]

        dry_event = detector.process_reading(pump_id, timestamp_s, v_rms, i_rms, pf, p_kw)
        is_dry = dry_event is not None

        if p_kw <= 0.05 or v_rms <= 50.0:
            # Pump is OFF
            # Retrieve last known static level or burst static level
            z_s = self.cached_burst_zs.get(pump_id, 35.0)
            sigma_zs = 2.0
            return PhiStateResult(
                pump_id=pump_id,
                timestamp_s=timestamp_s,
                q_lps=0.0,
                sigma_q_lps=0.0,
                q_ci_90=(0.0, 0.0),
                h_dyn_m=0.0,
                sigma_hd_m=0.0,
                z_static_m=round(z_s, 2),
                sigma_zs_m=round(sigma_zs, 2),
                zs_ci_90=(round(z_s - 1.645 * sigma_zs, 2), round(z_s + 1.645 * sigma_zs, 2)),
                eta_overall=0.0,
                is_running=False,
                is_dry_run=False,
            )

        # Compute speed ratio (VFD or slip-adjusted)
        speed_ratio = float(freq_hz / 50.0)

        # Invert flow rate
        q_est, sigma_q = model.invert_q_from_pel(p_kw, speed_ratio=speed_ratio)

        # Incorporate audit calibration if available using Bayesian precision weighting
        if pump_id in self.audit_labels:
            audit = self.audit_labels[pump_id]
            # Precision weights
            w_prior = 1.0 / (sigma_q**2)
            w_audit = 1.0 / (audit.sigma_q**2)
            q_est = (w_prior * q_est + w_audit * audit.bucket_q_lps) / (w_prior + w_audit)
            sigma_q = math.sqrt(1.0 / (w_prior + w_audit))

        # 90% credible interval (calibrated Student-t margin)
        sigma_cal = math.sqrt(sigma_q**2 + 0.05**2)
        q_low = float(max(0.0, q_est - 2.15 * sigma_cal))
        q_high = float(q_est + 2.15 * sigma_cal)

        # Invert dynamic and static heads
        h_dyn, sigma_hd, z_static, sigma_zs = model.estimate_dynamic_and_static_head(
            q_lps=q_est,
            speed_ratio=speed_ratio,
            residual_drawdown_m=residual_drawdown_m,
            sigma_q_lps=sigma_q,
        )

        # Blend with burst static level if available
        if pump_id in self.cached_burst_zs:
            burst_z = self.cached_burst_zs[pump_id]
            # Weighted average: burst sigma ~ 2.5m, curve sigma ~ 3.5m
            w_b = 1.0 / (2.5**2)
            w_c = 1.0 / (sigma_zs**2)
            z_static = (w_b * burst_z + w_c * z_static) / (w_b + w_c)
            sigma_zs = 1.0 / math.sqrt(w_b + w_c)

        if pump_id in self.audit_labels:
            audit = self.audit_labels[pump_id]
            w_prior_zs = 1.0 / (sigma_zs**2)
            w_audit_zs = 1.0 / (audit.sigma_dip**2)
            z_static = (w_prior_zs * z_static + w_audit_zs * audit.dip_level_m) / (w_prior_zs + w_audit_zs)
            sigma_zs = math.sqrt(1.0 / (w_prior_zs + w_audit_zs))

        zs_low = float(max(1.0, z_static - 1.645 * sigma_zs))
        zs_high = float(z_static + 1.645 * sigma_zs)

        # Overall efficiency: P_hyd / P_el
        p_hyd_kw = (9.81 * q_est * h_dyn) / 1000.0
        eta_overall = float(np.clip(p_hyd_kw / max(0.1, p_kw), 0.10, 0.85))

        return PhiStateResult(
            pump_id=pump_id,
            timestamp_s=timestamp_s,
            q_lps=round(q_est, 3),
            sigma_q_lps=round(sigma_q, 3),
            q_ci_90=(round(q_low, 3), round(q_high, 3)),
            h_dyn_m=round(h_dyn, 2),
            sigma_hd_m=round(sigma_hd, 2),
            z_static_m=round(z_static, 2),
            sigma_zs_m=round(sigma_zs, 2),
            zs_ci_90=(round(zs_low, 2), round(zs_high, 2)),
            eta_overall=round(eta_overall, 3),
            is_running=True,
            is_dry_run=is_dry,
        )
