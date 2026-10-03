"""Unit and benchmark tests for Layer 3: Fleet Aquifer Twin (fat/)."""

import math

import jax
import jax.numpy as jnp
import numpy as np

from fat.jax_model import compute_head_misfit_loss, simulate_trajectory
from fat.twin import FleetAquiferTwin


def test_jax_adjoint_vs_finite_difference_gradient():
    """Verify JAX reverse-mode autodiff gradient matches finite differences to < 1e-4."""
    nx, ny = 6, 6
    dx, dy = 200.0, 200.0
    dt = 300.0

    bedrock = jnp.zeros((ny, nx), dtype=jnp.float64)
    h_init = 30.0 * jnp.ones((ny, nx), dtype=jnp.float64)
    log_k = -4.5 * jnp.ones((ny, nx), dtype=jnp.float64)
    sy = 0.025 * jnp.ones((ny, nx), dtype=jnp.float64)

    # 3 time steps
    recharge = 1e-8 * jnp.ones((3, ny, nx), dtype=jnp.float64)
    pumping = jnp.zeros((3, ny, nx), dtype=jnp.float64)
    pumping = pumping.at[:, 2, 2].set(0.005 / (dx * dy))  # 5 L/s at cell (2, 2)

    obs_idx = (jnp.array([2, 3]), jnp.array([2, 3]))
    obs_heads = jnp.array([29.2, 29.8], dtype=jnp.float64)

    # Autodiff gradient dLoss / d(log_k)
    grad_fn = jax.grad(compute_head_misfit_loss, argnums=0)
    autodiff_grad = grad_fn(
        log_k, h_init, sy, bedrock, recharge, pumping, obs_idx, obs_heads, dx, dy, dt
    )

    # Central finite differences at cell (2, 2)
    eps = 1e-5
    target_cell = (2, 2)

    log_k_plus = log_k.at[target_cell].add(eps)
    log_k_minus = log_k.at[target_cell].add(-eps)

    loss_plus = compute_head_misfit_loss(
        log_k_plus, h_init, sy, bedrock, recharge, pumping, obs_idx, obs_heads, dx, dy, dt
    )
    loss_minus = compute_head_misfit_loss(
        log_k_minus, h_init, sy, bedrock, recharge, pumping, obs_idx, obs_heads, dx, dy, dt
    )

    fd_grad = float((loss_plus - loss_minus) / (2.0 * eps))
    ad_grad = float(autodiff_grad[target_cell])

    rel_diff = abs(ad_grad - fd_grad) / max(1e-7, abs(ad_grad) + abs(fd_grad))
    print(f"Gradient Check -> Autodiff: {ad_grad:.6e}, FD: {fd_grad:.6e}, Rel Diff: {rel_diff:.2e}")

    assert rel_diff < 1e-4, f"Adjoint gradient check failed! Rel diff {rel_diff} >= 1e-4"


def test_esmda_head_rmse_target():
    """Verify ES-MDA data assimilation achieves cell-scale head RMSE <= 2m."""
    nx, ny = 8, 8
    dx, dy = 200.0, 200.0
    bedrock = np.zeros((ny, nx))
    z_surf = 100.0 * np.ones((ny, nx))

    true_log_k = -4.2 * np.ones((ny, nx))
    true_sy = 0.025 * np.ones((ny, nx))
    true_h = 75.0 * np.ones((ny, nx))

    # True forward run to create observations
    dt = 3600.0
    n_steps = 4
    recharge = 1e-9 * np.ones((n_steps, ny, nx))
    pumping = np.zeros((n_steps, ny, nx))
    pumping[:, 3, 3] = 0.008 / (dx * dy)  # 8 L/s

    h_true_final, _ = simulate_trajectory(
        h_init=jnp.array(true_h),
        log_k=jnp.array(true_log_k),
        sy=jnp.array(true_sy),
        bedrock=jnp.array(bedrock),
        recharge_rates=jnp.array(recharge),
        pumping_grids=jnp.array(pumping),
        dx=dx,
        dy=dy,
        dt=dt,
    )
    h_true_np = np.array(h_true_final)

    # Observations at 6 well locations
    obs_coords = [(2, 2), (3, 3), (4, 4), (1, 5), (5, 2), (2, 5)]
    head_obs = []
    opt_obs = []
    rng = np.random.default_rng(42)

    for iy, ix in obs_coords:
        h_val = float(h_true_np[iy, ix]) + float(rng.normal(0.0, 0.2))
        head_obs.append((iy, ix, h_val, 0.35))
        opt_obs.append((iy, ix, math.log10(10.0 ** true_log_k[iy, ix] * h_val), 0.15))

    twin = FleetAquiferTwin(
        nx=nx,
        ny=ny,
        dx=dx,
        dy=dy,
        bedrock=bedrock,
        z_surf=z_surf,
        prior_log_k=true_log_k + 0.3,  # Perturbed prior
        prior_sy=true_sy,
        initial_h=true_h - 1.5,
        num_ensemble=20,
    )

    posterior = twin.assimilate_observations(
        head_observations=head_obs,
        opt_t_observations=opt_obs,
        recharge_series=recharge,
        pumping_series=pumping,
        dt_seconds=dt,
    )

    cell_rmse = float(np.sqrt(np.mean((posterior.h_mean - h_true_np) ** 2)))
    print(
        f"FAT Benchmark -> Cell-scale Head RMSE: {cell_rmse:.2f} m, Obs RMSE: {posterior.rmse_vs_obs:.2f} m"
    )

    assert cell_rmse <= 2.0, f"Head RMSE {cell_rmse}m exceeds 2.0m target"
    assert posterior.rmse_vs_obs <= 1.0
