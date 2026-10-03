"""AquiPulse Active-Learning Field Audit Selector.

Selects the optimal 2-5% of pumps for physical ground-truth calibration
(bucket test flow measurement + dip-well water level reading) to maximize
expected information gain (EIG) across the entire fleet per audit rupee spent.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, List


@dataclass
class AuditCandidate:
    """A pump evaluated for audit selection."""

    pump_id: str
    family_id: str
    sigma_q_current: float
    sigma_zs_current: float
    operating_hours_per_week: float
    family_fleet_count: int
    cluster_id: int
    audit_cost_inr: float = 800.0  # Cost of field technician visit (₹800)


class ActiveLearningAuditSelector:
    """Ranks and selects candidate pumps to maximize fleet-wide Bayesian information gain."""

    def __init__(self, cost_weight: float = 1.0) -> None:
        self.cost_weight = cost_weight

    def compute_expected_information_gain(self, candidate: AuditCandidate) -> float:
        """Compute EIG for a single candidate pump.

        Information Gain comprises:
        1. Local well gain: reduction in entropy of (Q, Z_s) proportional to log(sigma_current / sigma_audit)
        2. Family-level hierarchical spillover gain: auditing one pump improves priors for all other pumps
           in the same family by factor sqrt(N_family)
        3. Operating duty cycle weight: pumps that pump more volume produce higher societal value from accuracy
        """
        # Audit observation precision: bucket test achieves sigma_q ~ 0.2 L/s, dip tape ~ 0.15 m
        sigma_audit_q = 0.20
        sigma_audit_zs = 0.15

        # Local entropy reduction Delta H = 0.5 * log(sigma_curr^2 / sigma_audit^2)
        local_gain_q = max(0.0, math.log(max(1.0, candidate.sigma_q_current / sigma_audit_q)))
        local_gain_zs = max(0.0, math.log(max(1.0, candidate.sigma_zs_current / sigma_audit_zs)))
        local_eig = local_gain_q + 1.2 * local_gain_zs

        # Hierarchical spillover across family members
        family_spillover_multiplier = 1.0 + 0.40 * math.log(max(1, candidate.family_fleet_count))

        # Duty cycle / volume significance
        duty_weight = 0.8 + 0.2 * min(3.0, candidate.operating_hours_per_week / 20.0)

        total_eig = local_eig * family_spillover_multiplier * duty_weight
        cost = max(100.0, candidate.audit_cost_inr)
        return total_eig / (cost**self.cost_weight)

    def select_audits(
        self,
        candidates: List[AuditCandidate],
        target_fraction: float = 0.04,  # Default: 4% of fleet
        max_per_family: int = 2,
    ) -> List[AuditCandidate]:
        """Greedy submodular selection with family diversity constraints."""
        n_select = max(1, int(round(len(candidates) * target_fraction)))

        # Score all candidates
        scored = []
        for c in candidates:
            score = self.compute_expected_information_gain(c)
            scored.append((score, c))

        scored.sort(key=lambda x: x[0], reverse=True)

        selected: List[AuditCandidate] = []
        family_counts: Dict[str, int] = {}

        for score, cand in scored:
            fam = cand.family_id
            current_fam_count = family_counts.get(fam, 0)
            if current_fam_count >= max_per_family and len(selected) < n_select * 0.8:
                # Enforce diversity across families unless running out of candidates
                continue

            selected.append(cand)
            family_counts[fam] = current_fam_count + 1

            if len(selected) >= n_select:
                break

        return selected
