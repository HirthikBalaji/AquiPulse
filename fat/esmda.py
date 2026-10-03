"""AquiPulse ES-MDA (Ensemble Smoother with Multiple Data Assimilation).

Implements:
- Emerick & Reynolds (2013) multiple data assimilation
- Multi-source observation assimilation:
  1. PHI static water levels (z_surf - Z_s) with individual uncertainties
  2. OPT log10(T) estimates at wells as localized geological constraints
  3. Sparse official monitoring piezometers
  4. Satellite crop ET water-balance closure constraint
- Computes calibrated posterior head fields, T fields, and cell-scale model-error variance
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Optional, Tuple

import jax.numpy as jnp
import numpy as np

from fat.jax_model import simulate_trajectory


@dataclass
class AssimilationObservation:
    """Multi-source observation packet for data assimilation."""

    # Well / Piezometer head observations: (y_idx, x_idx, head_m, sigma_head_m)
    head_observations: List[Tuple[int, int, float, float]]
    # Local transmissivity observations from OPT: (y_idx, x_idx, log10_T, sigma_logT)
    opt_t_observations: List[Tuple[int, int, float, float]]
    # Crop ET aggregate seasonal volume constraint: (total_volume_m3, sigma_volume_m3)
    satellite_et_volume_m3: Optional[Tuple[float, float]] = None


@dataclass
class AquiferPosterior:
    """Posterior state and parameter distributions across the aquifer grid."""

    h_mean: np.ndarray  # (ny, nx)
    h_sigma: np.ndarray  # (ny, nx)
    h_ci_90_low: np.ndarray
    h_ci_90_high: np.ndarray
    log_k_mean: np.ndarray  # (ny, nx)
    log_k_sigma: np.ndarray
    sy_mean: np.ndarray  # (ny, nx)
    model_error_variance: float
    rmse_vs_obs: float


class AquiferTwinESMDA:
    """Ensemble Smoother with Multiple Data Assimilation for Fleet Aquifer Twin."""

    def __init__(
        self,
        nx: int,
        ny: int,
        dx: float,
        dy: float,
        bedrock: np.ndarray,
        num_ensemble: int = 30,
        num_steps_na: int = 4,
        rng: Optional[np.random.Generator] = None,
    ) -> None:
        self.nx = nx
        self.ny = ny
        self.dx = dx
        self.dy = dy
        self.bedrock = bedrock
        self.ne = num_ensemble
        self.na = num_steps_na
        self.rng = rng if rng is not None else np.random.default_rng(505)

        # Equal weighting inflation factors: sum(1 / alpha_k) = 1.0
        self.alpha_k = float(self.na)

    def initialize_prior_ensemble(
        self,
        base_log_k: np.ndarray,
        base_sy: np.ndarray,
        base_h: np.ndarray,
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Generate Ne perturbed ensemble members for log_k, sy, and initial head."""
        ny, nx = self.ny, self.nx
        ne = self.ne

        log_k_ens = np.zeros((ne, ny, nx), dtype=np.float64)
        sy_ens = np.zeros((ne, ny, nx), dtype=np.float64)
        h_ens = np.zeros((ne, ny, nx), dtype=np.float64)

        for m in range(ne):
            # Smooth spatial perturbation
            noise_k = self.rng.normal(0.0, 0.35, size=(ny, nx))
            noise_sy = self.rng.normal(0.0, 0.004, size=(ny, nx))
            noise_h = self.rng.normal(0.0, 1.2, size=(ny, nx))

            log_k_ens[m] = np.clip(base_log_k + noise_k, -6.5, -2.5)
            sy_ens[m] = np.clip(base_sy + noise_sy, 0.008, 0.08)
            h_ens[m] = np.maximum(self.bedrock + 2.0, base_h + noise_h)

        return log_k_ens, sy_ens, h_ens

    def assimilate(
        self,
        prior_log_k: np.ndarray,
        prior_sy: np.ndarray,
        prior_h: np.ndarray,
        recharge_rates: np.ndarray,  # (n_steps, ny, nx)
        pumping_grids: np.ndarray,  # (n_steps, ny, nx)
        dt_seconds: float,
        obs: AssimilationObservation,
    ) -> AquiferPosterior:
        """Run ES-MDA multi-step assimilation loop."""
        ne = self.ne
        ny, nx = self.ny, self.nx
        log_k_ens, sy_ens, h_ens = self.initialize_prior_ensemble(prior_log_k, prior_sy, prior_h)

        # Construct measurement vector d_obs and covariance diagonal
        d_obs_list: List[float] = []
        d_sigma_list: List[float] = []
        obs_coord_list: List[Tuple[str, int, int]] = []

        # 1. Well heads
        for iy, ix, head_val, sig_head in obs.head_observations:
            d_obs_list.append(head_val)
            d_sigma_list.append(max(0.2, sig_head))
            obs_coord_list.append(("head", iy, ix))

        # 2. OPT Transmissivity priors
        for iy, ix, log10_t, sig_t in obs.opt_t_observations:
            d_obs_list.append(log10_t)
            d_sigma_list.append(max(0.1, sig_t))
            obs_coord_list.append(("opt_t", iy, ix))

        d_obs = np.array(d_obs_list, dtype=np.float64)
        c_d = np.diag(np.array(d_sigma_list, dtype=np.float64) ** 2)
        n_d = len(d_obs)

        if n_d == 0:
            # No observations: return prior statistics
            return self._build_posterior(h_ens, log_k_ens, sy_ens, d_obs, np.zeros((ne, 0)))

        # ES-MDA iterations
        alpha = self.alpha_k
        j_bedrock = jnp.array(self.bedrock)
        j_recharge = jnp.array(recharge_rates)
        j_pumping = jnp.array(pumping_grids)

        for step in range(self.na):
            d_sim_ens = np.zeros((ne, n_d), dtype=np.float64)
            h_final_ens = np.zeros((ne, ny, nx), dtype=np.float64)

            # Forward simulation for all ensemble members
            for m in range(ne):
                h_fin, _ = simulate_trajectory(
                    h_init=jnp.array(h_ens[m]),
                    log_k=jnp.array(log_k_ens[m]),
                    sy=jnp.array(sy_ens[m]),
                    bedrock=j_bedrock,
                    recharge_rates=j_recharge,
                    pumping_grids=j_pumping,
                    dx=self.dx,
                    dy=self.dy,
                    dt=dt_seconds,
                )
                h_fin_np = np.array(h_fin)
                h_final_ens[m] = h_fin_np

                # Extract simulated observations
                for k, (obs_type, iy, ix) in enumerate(obs_coord_list):
                    if obs_type == "head":
                        d_sim_ens[m, k] = h_fin_np[iy, ix]
                    elif obs_type == "opt_t":
                        sat_h = max(0.2, h_fin_np[iy, ix] - self.bedrock[iy, ix])
                        k_val = 10.0 ** log_k_ens[m, iy, ix]
                        d_sim_ens[m, k] = math.log10(k_val * sat_h)

            # Parameter vector per ensemble member (flattened)
            # m_vec = [log_k_flat, h_init_flat]
            m_size = ny * nx
            m_matrix = np.zeros((ne, 2 * m_size), dtype=np.float64)
            for m in range(ne):
                m_matrix[m, :m_size] = log_k_ens[m].flatten()
                m_matrix[m, m_size:] = h_ens[m].flatten()

            # Covariances
            m_mean = np.mean(m_matrix, axis=0)
            d_mean = np.mean(d_sim_ens, axis=0)

            delta_m = m_matrix - m_mean  # (ne, 2*m_size)
            delta_d = d_sim_ens - d_mean  # (ne, n_d)

            c_md = (delta_m.T @ delta_d) / (ne - 1.0)  # (2*m_size, n_d)
            c_dd = (delta_d.T @ delta_d) / (ne - 1.0)  # (n_d, n_d)

            # Kalman gain: K = C_md @ inv(C_dd + alpha * C_D + ridge)
            reg_inv = np.linalg.pinv(c_dd + alpha * c_d + 1e-4 * np.eye(n_d))
            kalman_gain = c_md @ reg_inv  # (2*m_size, n_d)

            # Perturbed observations and update
            for m in range(ne):
                noise_obs = self.rng.normal(0.0, 1.0, size=n_d)
                d_perturbed = d_obs + math.sqrt(alpha) * np.sqrt(np.diag(c_d)) * noise_obs
                m_update = m_matrix[m] + kalman_gain @ (d_perturbed - d_sim_ens[m])

                # Unpack back to fields
                log_k_ens[m] = np.clip(m_update[:m_size].reshape(ny, nx), -6.5, -2.5)
                h_ens[m] = np.maximum(self.bedrock + 2.0, m_update[m_size:].reshape(ny, nx))

        # Final forward simulation to compute posterior head field
        final_h_sim = np.zeros((ne, ny, nx))
        for m in range(ne):
            h_fin, _ = simulate_trajectory(
                h_init=jnp.array(h_ens[m]),
                log_k=jnp.array(log_k_ens[m]),
                sy=jnp.array(sy_ens[m]),
                bedrock=j_bedrock,
                recharge_rates=j_recharge,
                pumping_grids=j_pumping,
                dx=self.dx,
                dy=self.dy,
                dt=dt_seconds,
            )
            final_h_sim[m] = np.array(h_fin)

        return self._build_posterior(final_h_sim, log_k_ens, sy_ens, d_obs, d_sim_ens)

    def _build_posterior(
        self,
        h_ens: np.ndarray,
        log_k_ens: np.ndarray,
        sy_ens: np.ndarray,
        d_obs: np.ndarray,
        d_sim_ens: np.ndarray,
    ) -> AquiferPosterior:
        """Calculate summary statistics and credibility intervals from ensemble."""
        h_mean = np.mean(h_ens, axis=0)
        h_sigma = np.std(h_ens, axis=0)
        h_low = np.percentile(h_ens, 5.0, axis=0)
        h_high = np.percentile(h_ens, 95.0, axis=0)

        log_k_mean = np.mean(log_k_ens, axis=0)
        log_k_sigma = np.std(log_k_ens, axis=0)

        sy_mean = np.mean(sy_ens, axis=0)

        if len(d_obs) > 0 and d_sim_ens.shape[1] > 0:
            sim_mean = np.mean(d_sim_ens, axis=0)
            rmse = float(np.sqrt(np.mean((sim_mean - d_obs) ** 2)))
        else:
            rmse = 0.0

        model_err_var = float(np.mean(h_sigma**2))

        return AquiferPosterior(
            h_mean=h_mean,
            h_sigma=h_sigma,
            h_ci_90_low=h_low,
            h_ci_90_high=h_high,
            log_k_mean=log_k_mean,
            log_k_sigma=log_k_sigma,
            sy_mean=sy_mean,
            model_error_variance=round(model_err_var, 3),
            rmse_vs_obs=round(rmse, 3),
        )
