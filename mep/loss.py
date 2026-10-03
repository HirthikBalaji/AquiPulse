"""AquiPulse Marginal Externality Pricing (MEP) Loss Function.

Defines the societal hydraulic damage loss L(Q) from §6.5:
1. Extra lifting energy borne by all neighbor wells j:
   c_e * rho * g * V_j * (h_ref_j - h_j(Q))
2. Well-failure and borewell-deepening risk:
   c_f * P_fail(h_j(Q))  [convex in dynamic cone depression]
3. Smallholder equity weights w_j
"""

from __future__ import annotations

from typing import Tuple

import jax
import jax.numpy as jnp

jax.config.update("jax_enable_x64", True)

# Physical constants
RHO_WATER = 1000.0  # kg/m^3
GRAVITY = 9.81  # m/s^2
JOULES_PER_KWH = 3.6e6


def compute_aquifer_damage_loss(
    q_fleet_rates: jnp.ndarray,  # shape: (n_wells,) in m^3/s
    h_init: jnp.ndarray,  # (ny, nx)
    log_k: jnp.ndarray,
    sy: jnp.ndarray,
    bedrock: jnp.ndarray,
    recharge_rates: jnp.ndarray,  # (n_steps, ny, nx)
    well_grid_ix: jnp.ndarray,  # (n_wells,)
    well_grid_iy: jnp.ndarray,  # (n_wells,)
    well_baseline_v_m3: jnp.ndarray,  # (n_wells,) typical seasonal volume
    equity_weights: jnp.ndarray,  # (n_wells,)
    ref_heads: jnp.ndarray,  # (n_wells,) unpumped reference head
    crit_heads: jnp.ndarray,  # (n_wells,) pump intake failure depth
    dx: float,
    dy: float,
    dt: float,
    c_energy_inr_per_kwh: float = 7.0,  # ₹7 / kWh agricultural DISCOM subsidy cost
    c_failure_inr: float = 85_000.0,  # ₹85,000 to re-drill a failed borewell
) -> jnp.ndarray:
    """Evaluate differentiable social loss L(Q) across the entire well fleet.

    Returns scalar damage in Indian Rupees (₹).
    """
    n_steps = recharge_rates.shape[0]
    ny, nx = h_init.shape
    cell_area = dx * dy

    # Project fleet pumping rates onto 2D spatial finite volume grid
    # pumping_grid has shape (ny, nx)
    pumping_grid = jnp.zeros((ny, nx), dtype=jnp.float64)
    # Flux Q / cell_area [m/s]
    fluxes = q_fleet_rates / cell_area
    pumping_grid = pumping_grid.at[(well_grid_iy, well_grid_ix)].add(fluxes)

    # Repeat across time steps
    pumping_grids = jnp.broadcast_to(pumping_grid, (n_steps, ny, nx))

    # Integrate forward PDE trajectory
    def scan_step(
        h_prev: jnp.ndarray, inputs: Tuple[jnp.ndarray, jnp.ndarray]
    ) -> Tuple[jnp.ndarray, jnp.ndarray]:
        r_step, p_step = inputs
        k_field = 10.0**log_k
        sat_thick = jnp.maximum(0.2, h_prev - bedrock)
        t_curr = k_field * sat_thick

        t_east = (
            2.0
            * t_curr[:, :-1]
            * t_curr[:, 1:]
            / jnp.maximum(1e-12, t_curr[:, :-1] + t_curr[:, 1:])
        )
        flux_x = -t_east * (h_prev[:, 1:] - h_prev[:, :-1]) / dx

        t_north = (
            2.0
            * t_curr[:-1, :]
            * t_curr[1:, :]
            / jnp.maximum(1e-12, t_curr[:-1, :] + t_curr[1:, :])
        )
        flux_y = -t_north * (h_prev[1:, :] - h_prev[:-1, :]) / dy

        div_flux = jnp.zeros_like(h_prev)
        div_flux = div_flux.at[:, 1:-1].add((flux_x[:, :-1] - flux_x[:, 1:]) / dx)
        div_flux = div_flux.at[:, 0].add(-flux_x[:, 0] / dx)
        div_flux = div_flux.at[:, -1].add(flux_x[:, -1] / dx)
        div_flux = div_flux.at[1:-1, :].add((flux_y[:-1, :] - flux_y[1:, :]) / dy)
        div_flux = div_flux.at[0, :].add(-flux_y[0, :] / dy)
        div_flux = div_flux.at[-1, :].add(flux_y[-1, :] / dy)

        dh = (div_flux + r_step - p_step) * (dt / jnp.maximum(0.005, sy))
        h_next = h_prev + dh
        return h_next, h_next

    h_final, _ = jax.lax.scan(scan_step, h_init, (recharge_rates, pumping_grids))

    # Extract heads at each well location: h_j
    well_heads = h_final[(well_grid_iy, well_grid_ix)]

    # 1. Extra lifting energy cost for well j:
    # Lift increase = ref_head - well_head
    drawdown_j = jnp.maximum(0.0, ref_heads - well_heads)
    # Energy = rho * g * V_j * drawdown [Joules]
    lift_joules = RHO_WATER * GRAVITY * well_baseline_v_m3 * drawdown_j
    lift_kwh = lift_joules / JOULES_PER_KWH
    cost_lift_j = lift_kwh * c_energy_inr_per_kwh  # ₹

    # 2. Well-failure risk: P_fail increases quadratically as water table drops near intake
    # Head margin to failure
    margin = 5.0  # 5-meter danger zone before dry-run intake collapse
    depth_to_intake = jnp.maximum(0.0, (crit_heads + margin) - well_heads)
    p_fail_j = (depth_to_intake / margin) ** 2
    cost_fail_j = p_fail_j * c_failure_inr * 0.05  # Annualized failure expectation

    # Total weighted fleet externality loss
    loss = jnp.sum(equity_weights * (cost_lift_j + cost_fail_j))
    return loss
