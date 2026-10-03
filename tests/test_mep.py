"""Unit and benchmark tests for Layer 4: Marginal Externality Pricing (mep/)."""

import numpy as np
from scipy.stats import spearmanr

from mep.adjoint import AdjointExternalitySolver
from mep.bonus import BonusSettlementCalculator, ParcelCropObservation
from mep.loss import compute_aquifer_damage_loss


def test_mep_adjoint_vs_finite_difference_rank_correlation():
    """Verify rank correlation >= 0.90 between adjoint prices and finite differences on 100 wells."""
    nx, ny = 12, 12
    dx, dy = 200.0, 200.0
    dt = 3600.0
    n_steps = 2

    # Set up 100 wells on grid
    n_wells = 100
    rng = np.random.default_rng(707)

    # Random well coordinates across the 12x12 grid
    grid_ix = rng.integers(1, nx - 1, size=n_wells).astype(np.int64)
    grid_iy = rng.integers(1, ny - 1, size=n_wells).astype(np.int64)
    pump_ids = [f"WELL-{i + 1:03d}" for i in range(n_wells)]

    # Heterogeneous aquifer properties
    bedrock = np.zeros((ny, nx))
    h_init = 60.0 * np.ones((ny, nx))
    log_k = -4.5 + rng.normal(0.0, 0.3, size=(ny, nx))
    sy = 0.025 * np.ones((ny, nx))
    recharge = 1e-9 * np.ones((n_steps, ny, nx))

    # Pumping rates (L/s)
    q_rates_lps = rng.uniform(3.0, 10.0, size=n_wells)
    baseline_v = q_rates_lps * 3600.0 * 100.0  # m^3
    equity_weights = rng.uniform(0.9, 1.6, size=n_wells)
    ref_heads = 60.0 * np.ones(n_wells)
    crit_heads = 40.0 * np.ones(n_wells)

    solver = AdjointExternalitySolver()

    # 1. Single backward pass computes all 100 adjoint prices
    price_results = solver.compute_fleet_prices(
        pump_ids=pump_ids,
        q_rates_lps=q_rates_lps,
        h_init=h_init,
        log_k=log_k,
        sy=sy,
        bedrock=bedrock,
        recharge_rates=recharge,
        grid_ix=grid_ix,
        grid_iy=grid_iy,
        baseline_v_m3=baseline_v,
        equity_weights=equity_weights,
        ref_heads=ref_heads,
        crit_heads=crit_heads,
        dx=dx,
        dy=dy,
        dt=dt,
    )
    adjoint_lambdas = np.array([p.lambda_inr_per_m3 for p in price_results])

    # 2. Compute finite-difference sensitivities on a subset of 20 wells across the spectrum
    test_subset = np.linspace(0, n_wells - 1, 20, dtype=int)
    fd_sensitivities = []

    import jax.numpy as jnp

    q_base_m3_s = jnp.array(q_rates_lps / 1000.0, dtype=jnp.float64)
    eps = 0.0005  # 0.5 L/s perturbation in m^3/s

    loss_base = float(
        compute_aquifer_damage_loss(
            q_base_m3_s,
            jnp.array(h_init),
            jnp.array(log_k),
            jnp.array(sy),
            jnp.array(bedrock),
            jnp.array(recharge),
            jnp.array(grid_ix),
            jnp.array(grid_iy),
            jnp.array(baseline_v),
            jnp.array(equity_weights),
            jnp.array(ref_heads),
            jnp.array(crit_heads),
            dx=dx,
            dy=dy,
            dt=dt,
        )
    )

    for idx in test_subset:
        q_perturbed = q_base_m3_s.at[idx].add(eps)
        loss_p = float(
            compute_aquifer_damage_loss(
                q_perturbed,
                jnp.array(h_init),
                jnp.array(log_k),
                jnp.array(sy),
                jnp.array(bedrock),
                jnp.array(recharge),
                jnp.array(grid_ix),
                jnp.array(grid_iy),
                jnp.array(baseline_v),
                jnp.array(equity_weights),
                jnp.array(ref_heads),
                jnp.array(crit_heads),
                dx=dx,
                dy=dy,
                dt=dt,
            )
        )
        fd_sensitivities.append((loss_p - loss_base) / eps)

    sub_adjoint = adjoint_lambdas[test_subset]
    sub_fd = np.array(fd_sensitivities)

    rho, pval = spearmanr(sub_adjoint, sub_fd)
    print(
        f"MEP Benchmark -> 100-well Adjoint vs FD Spearman Rank Correlation: {rho:.4f} (p-value: {pval:.2e})"
    )

    assert rho >= 0.90, f"Rank correlation {rho:.4f} below 0.90 acceptance target"


def test_bonus_calculator_guardrails():
    """Verify that NDVI starvation guardrail correctly withholds bonuses on degraded crops."""
    calculator = BonusSettlementCalculator(kappa_farmer_share=0.50, min_ndvi_peer_fraction=0.88)

    parcels = [
        # Farmer A: Conserved water, healthy crop (NDVI 0.72 vs cohort 0.70) -> Should be paid!
        ParcelCropObservation(
            pump_id="PUMP-A",
            farmer_id="FARMER-A",
            crop_type="cotton",
            cluster_id=1,
            parcel_area_ha=2.5,
            satellite_ndvi=0.72,
            baseline_volume_m3=4000.0,
            actual_pumped_m3=3200.0,  # 800 m3 avoided
        ),
        # Farmer B: Pumped less but crop died/starved (NDVI 0.42 vs cohort 0.70) -> Must be blocked!
        ParcelCropObservation(
            pump_id="PUMP-B",
            farmer_id="FARMER-B",
            crop_type="cotton",
            cluster_id=1,
            parcel_area_ha=2.0,
            satellite_ndvi=0.42,
            baseline_volume_m3=3500.0,
            actual_pumped_m3=1000.0,  # 2500 m3 avoided through severe starvation
        ),
    ]

    prices = {"PUMP-A": 2.50, "PUMP-B": 3.00}
    statements = calculator.evaluate_settlement(parcels, prices)

    stmt_a = statements[0]
    stmt_b = statements[1]

    # Farmer A: avoided 800 m3 * ₹2.50 * 50% = ₹1000
    assert stmt_a.guardrail_passed is True
    assert stmt_a.avoided_volume_m3 == 800.0
    assert stmt_a.farmer_payout_inr == 1000.0

    # Farmer B: starved crop -> blocked!
    assert stmt_b.guardrail_passed is False
    assert stmt_b.farmer_payout_inr == 0.0
    assert "GUARDRAIL_FAILED_CROP_STARVATION_SUSPECT" in stmt_b.guardrail_flags
