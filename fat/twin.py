"""AquiPulse Fleet Aquifer Twin (FAT) Coordinator.

High-level interface to:
- Assimilate L1 (PHI) heads, L2 (OPT) transmissivities, and satellite ET volumes
- Maintain the regional aquifer digital twin state
- Provide JAX autodiff adjoint gradients for Layer 4 (MEP externality pricing)
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from fat.esmda import AquiferPosterior, AquiferTwinESMDA, AssimilationObservation


class FleetAquiferTwin:
    """Aquifer digital twin integrating crowd-sourced pump telemetry and physics."""

    def __init__(
        self,
        nx: int,
        ny: int,
        dx: float,
        dy: float,
        bedrock: np.ndarray,
        z_surf: np.ndarray,
        prior_log_k: np.ndarray,
        prior_sy: np.ndarray,
        initial_h: np.ndarray,
        num_ensemble: int = 25,
    ) -> None:
        self.nx = nx
        self.ny = ny
        self.dx = dx
        self.dy = dy
        self.bedrock = bedrock
        self.z_surf = z_surf
        self.log_k = prior_log_k.copy()
        self.sy = prior_sy.copy()
        self.h = initial_h.copy()

        self.esmda = AquiferTwinESMDA(
            nx=nx,
            ny=ny,
            dx=dx,
            dy=dy,
            bedrock=bedrock,
            num_ensemble=num_ensemble,
        )
        self.last_posterior: Optional[AquiferPosterior] = None

    def assimilate_observations(
        self,
        head_observations: List[Tuple[int, int, float, float]],
        opt_t_observations: List[Tuple[int, int, float, float]],
        recharge_series: np.ndarray,  # (n_steps, ny, nx)
        pumping_series: np.ndarray,  # (n_steps, ny, nx)
        dt_seconds: float,
    ) -> AquiferPosterior:
        """Run ES-MDA assimilation on newly received fleet observations."""
        obs = AssimilationObservation(
            head_observations=head_observations,
            opt_t_observations=opt_t_observations,
        )

        posterior = self.esmda.assimilate(
            prior_log_k=self.log_k,
            prior_sy=self.sy,
            prior_h=self.h,
            recharge_rates=recharge_series,
            pumping_grids=pumping_series,
            dt_seconds=dt_seconds,
            obs=obs,
        )

        self.last_posterior = posterior
        # Update current best estimate fields
        self.h = posterior.h_mean.copy()
        self.log_k = posterior.log_k_mean.copy()
        self.sy = posterior.sy_mean.copy()

        return posterior

    def get_cell_state(self, ix: int, iy: int) -> Dict[str, Any]:
        """Query estimated head, static depth, and transmissivity for a grid cell."""
        h_val = float(self.h[iy, ix])
        z_surf_val = float(self.z_surf[iy, ix])
        static_depth = max(0.0, z_surf_val - h_val)
        sat_thick = max(0.2, h_val - float(self.bedrock[iy, ix]))
        k_val = 10.0 ** float(self.log_k[iy, ix])
        transmissivity = k_val * sat_thick

        sigma_h = float(self.last_posterior.h_sigma[iy, ix]) if self.last_posterior else 1.5

        return {
            "cell_x": ix,
            "cell_y": iy,
            "head_m": round(h_val, 2),
            "static_depth_m": round(static_depth, 2),
            "sigma_head_m": round(sigma_h, 2),
            "transmissivity_m2_s": float(f"{transmissivity:.2e}"),
            "log10_k": round(float(self.log_k[iy, ix]), 3),
        }
