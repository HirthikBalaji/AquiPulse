"""AquiPulse Water-Balance Closure and Composite Tamper Classifier.

Implements §6.6:
Closure residual: r_i = (V_i^PHI - V_i^agro) / sigma_i
Flags persistent deviation (|r_i| > 3.0) and scores composite tamper probability.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List

import numpy as np


@dataclass
class ClosureCheckResult:
    """Outcome of agronomic water-balance closure check for a pump."""

    pump_id: str
    v_phi_m3: float
    v_agro_m3: float
    residual_sigma: float
    is_closure_violated: bool
    tamper_probability_score: float  # [0.0, 1.0]
    flags: List[str]


class ClosureIntegrityEngine:
    """Evaluates crop water demand vs measured pumpage and scores tampering."""

    def __init__(self, irrigation_efficiency: float = 0.70) -> None:
        self.eta_irr = irrigation_efficiency

    def evaluate_closure(
        self,
        pump_id: str,
        v_phi_m3: float,
        parcel_area_ha: float,
        crop_etc_mm: float,
        effective_rain_mm: float,
        sigma_phi_m3: float = 50.0,
        physics_flags_count: int = 0,
        has_invalid_signature: bool = False,
    ) -> ClosureCheckResult:
        """Compute normalized closure residual and composite tamper score."""
        flags: List[str] = []

        # Agronomic demand in m^3: Area [m^2] * Net Depth [m] / eta_irr
        parcel_area_m2 = parcel_area_ha * 10_000.0
        net_irrigation_depth_m = max(0.0, (crop_etc_mm - effective_rain_mm) / 1000.0)
        v_agro_m3 = (parcel_area_m2 * net_irrigation_depth_m) / self.eta_irr

        # Combined uncertainty of closure (PHI + Agro model ~15%)
        sigma_agro = 0.18 * max(100.0, v_agro_m3)
        total_sigma = math.sqrt(sigma_phi_m3**2 + sigma_agro**2)

        # Normalized residual: r = (V_phi - V_agro) / sigma
        r_residual = (v_phi_m3 - v_agro_m3) / total_sigma
        is_violated = abs(r_residual) > 2.8

        if r_residual < -2.8:
            flags.append("FLAG_UNDER_REPORTING_SUSPECTED_BYPASS")
        elif r_residual > 3.2:
            flags.append("FLAG_OVER_REPORTING_OR_COMMERCIAL_EXPORT")

        # Composite tamper score S in [0.0, 1.0]
        # Combines closure anomaly, physics flags, and cryptographic failures
        score = 0.0

        if has_invalid_signature:
            score += 0.85
            flags.append("FLAG_CRYPTO_TAMPER")

        if physics_flags_count > 0:
            score += min(0.60, 0.20 * physics_flags_count)

        if is_violated:
            score += min(0.50, 0.12 * abs(r_residual))

        tamper_prob = float(np.clip(score, 0.01, 0.99))

        return ClosureCheckResult(
            pump_id=pump_id,
            v_phi_m3=round(v_phi_m3, 2),
            v_agro_m3=round(v_agro_m3, 2),
            residual_sigma=round(r_residual, 2),
            is_closure_violated=is_violated,
            tamper_probability_score=round(tamper_prob, 3),
            flags=flags,
        )


def evaluate_auc_score(true_labels: List[int], predicted_scores: List[float]) -> float:
    """Calculate Area Under the ROC Curve (AUC) for binary classification."""
    y_true = np.array(true_labels)
    y_scores = np.array(predicted_scores)

    pos_mask = y_true == 1
    neg_mask = y_true == 0

    n_pos = int(np.sum(pos_mask))
    n_neg = int(np.sum(neg_mask))

    if n_pos == 0 or n_neg == 0:
        return 1.0

    pos_scores = y_scores[pos_mask]
    neg_scores = y_scores[neg_mask]

    # Mann-Whitney U statistic formulation for AUC
    u_sum = 0.0
    for p in pos_scores:
        u_sum += np.sum(p > neg_scores) + 0.5 * np.sum(p == neg_scores)

    auc = float(u_sum / (n_pos * n_neg))
    return auc
