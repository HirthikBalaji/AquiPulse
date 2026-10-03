"""AquiPulse Ghost-Well Adjoint Source Inversion.

Locates clandestine unmetered irrigation wells using unexplained aquifer head residuals:
- Unmonitored pumping produces anomalous cone of depression
- Solves inverse problem for hidden source location (x_ghost, y_ghost)
- Evaluates localization accuracy against the <= 1.0 km benchmark
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Optional, Tuple

import numpy as np


@dataclass
class GhostWellDetectionResult:
    """Estimated location and rate of an inverted hidden well."""

    estimated_x_m: float
    estimated_y_m: float
    true_x_m: Optional[float]
    true_y_m: Optional[float]
    localization_error_km: Optional[float]
    estimated_rate_lps: float
    confidence_score: float
    within_1km_target: bool


class GhostWellLocalizer:
    """Inverts spatial head residuals across monitored wells to pinpoint hidden sources."""

    def __init__(self, nx: int, ny: int, dx: float, dy: float) -> None:
        self.nx = nx
        self.ny = ny
        self.dx = dx
        self.dy = dy

    def invert_ghost_source(
        self,
        monitored_head_residuals: List[Tuple[float, float, float]],
        # list of (x_m, y_m, unexplained_drawdown_m)
        prior_t_m2_s: float = 2.0e-4,
        true_location: Optional[Tuple[float, float]] = None,
    ) -> GhostWellDetectionResult:
        """Invert spatial residual field to estimate hidden extraction centroid."""
        # Create candidate grid
        x_coords = (np.arange(self.nx) + 0.5) * self.dx
        y_coords = (np.arange(self.ny) + 0.5) * self.dy
        X, Y = np.meshgrid(x_coords, y_coords)

        # Adjoint back-projection:
        # Pumping well at (X, Y) causes drawdown at sensor (x_k, y_k) proportional to log(R / r)
        likelihood_map = np.zeros((self.ny, self.nx), dtype=np.float64)

        for x_k, y_k, s_res in monitored_head_residuals:
            if s_res > 0.10:  # Sensor experienced unexplained lowering
                dist = np.sqrt((X - x_k) ** 2 + (Y - y_k) ** 2)
                # Influence kernel: 1 / (dist + r_reg)
                influence = s_res / (dist + 150.0)
                likelihood_map += influence

        # Peak of likelihood field
        peak_idx = np.unravel_index(np.argmax(likelihood_map), likelihood_map.shape)
        est_y = float(y_coords[peak_idx[0]])
        est_x = float(x_coords[peak_idx[1]])

        # Estimate hidden pumping rate from peak residual
        max_res = max(0.1, max(s for _, _, s in monitored_head_residuals))
        est_rate_lps = float(
            np.clip(2.0 * math.pi * prior_t_m2_s * max_res * 1000.0 * 2.5, 3.0, 15.0)
        )

        # Localization error if ground truth is supplied
        loc_err_km = None
        within_1km = False
        true_x, true_y = None, None

        if true_location is not None:
            true_x, true_y = true_location
            dist_m = math.sqrt((est_x - true_x) ** 2 + (est_y - true_y) ** 2)
            loc_err_km = round(dist_m / 1000.0, 3)
            within_1km = loc_err_km <= 1.0

        confidence = float(
            np.clip(np.max(likelihood_map) / (np.mean(likelihood_map) + 1e-6) / 4.0, 0.2, 0.98)
        )

        return GhostWellDetectionResult(
            estimated_x_m=round(est_x, 1),
            estimated_y_m=round(est_y, 1),
            true_x_m=true_x,
            true_y_m=true_y,
            localization_error_km=loc_err_km,
            estimated_rate_lps=round(est_rate_lps, 1),
            confidence_score=round(confidence, 3),
            within_1km_target=within_1km,
        )
