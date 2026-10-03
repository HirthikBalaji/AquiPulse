"""AquiPulse Farmer Bonus and Guardrail Settlement Calculator.

Implements §6.5:
bonus_i = kappa * lambda_i * max(0, V_base - V_actual) * 1[guardrail_i]

Guardrail prevents 'reward starvation':
Verifies that crop health (satellite NDVI) on the parcel is within healthy peer bounds.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple

import numpy as np


@dataclass
class ParcelCropObservation:
    """Satellite remote sensing observation of farmer's parcel."""

    pump_id: str
    farmer_id: str
    crop_type: str
    cluster_id: int
    parcel_area_ha: float
    satellite_ndvi: float  # Normalized Difference Vegetation Index (0.0 to 1.0)
    baseline_volume_m3: float
    actual_pumped_m3: float


@dataclass
class VerifiedBonusStatement:
    """Settlement statement for a farmer pump."""

    pump_id: str
    farmer_id: str
    avoided_volume_m3: float
    unit_externality_price_inr: float
    gross_avoided_value_inr: float
    farmer_payout_inr: float
    guardrail_passed: bool
    guardrail_flags: List[str]


class BonusSettlementCalculator:
    """Calculates verifiable payments to farmers for avoiding marginal hydraulic damage."""

    def __init__(
        self,
        kappa_farmer_share: float = 0.50,  # 50% of avoided externality goes to farmer
        min_ndvi_peer_fraction: float = 0.88,  # Must be at least 88% of peer mean NDVI
    ) -> None:
        self.kappa = kappa_farmer_share
        self.min_ndvi_ratio = min_ndvi_peer_fraction

    def evaluate_settlement(
        self,
        parcels: List[ParcelCropObservation],
        externality_prices: Dict[str, float],
    ) -> List[VerifiedBonusStatement]:
        """Compute verified payouts for all participating farmers."""
        # Group peers by (cluster_id, crop_type) to establish local cohort NDVI baseline
        cohort_ndvis: Dict[Tuple[int, str], List[float]] = {}
        for p in parcels:
            key = (p.cluster_id, p.crop_type)
            if key not in cohort_ndvis:
                cohort_ndvis[key] = []
            cohort_ndvis[key].append(p.satellite_ndvi)

        cohort_means = {k: float(np.mean(vals)) for k, vals in cohort_ndvis.items()}

        statements: List[VerifiedBonusStatement] = []

        for p in parcels:
            p_id = p.pump_id
            unit_price = externality_prices.get(p_id, 1.20)  # Default ₹1.20 / m^3

            avoided_m3 = max(0.0, p.baseline_volume_m3 - p.actual_pumped_m3)
            gross_value = avoided_m3 * unit_price

            # Check guardrail: NDVI comparison
            cohort_mean_ndvi = cohort_means.get((p.cluster_id, p.crop_type), 0.65)
            flags: List[str] = []
            guardrail_ok = True

            if p.satellite_ndvi < self.min_ndvi_ratio * cohort_mean_ndvi:
                guardrail_ok = False
                flags.append("GUARDRAIL_FAILED_CROP_STARVATION_SUSPECT")

            if p.actual_pumped_m3 == 0.0 and p.baseline_volume_m3 > 500.0:
                # Total abandonment without notice
                flags.append("FLAG_ZERO_EXTRACTION_UNVERIFIED_FALLOW")

            if guardrail_ok:
                farmer_payout = gross_value * self.kappa
            else:
                farmer_payout = 0.0

            statements.append(
                VerifiedBonusStatement(
                    pump_id=p_id,
                    farmer_id=p.farmer_id,
                    avoided_volume_m3=round(avoided_m3, 2),
                    unit_externality_price_inr=round(unit_price, 3),
                    gross_avoided_value_inr=round(gross_value, 2),
                    farmer_payout_inr=round(farmer_payout, 2),
                    guardrail_passed=guardrail_ok,
                    guardrail_flags=flags,
                )
            )

        return statements
