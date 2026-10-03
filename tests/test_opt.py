"""Unit and benchmark tests for Layer 2: Opportunistic Pumping Tests (opt/)."""

import math

import numpy as np
from scipy.special import exp1

from opt.cooper_jacob import CooperJacobEstimator
from opt.recovery import PumpingCycleSummary, RestartRecoveryRegressor
from opt.tomography import HydraulicInterferenceTomography, InterferenceObservation
from opt.well_loss import JacobWellLossEstimator


def test_cooper_jacob_known_theis_transmissivity():
    """Verify Cooper-Jacob recovers log10(T) within target < 0.3 error on known Theis drawdown."""
    t_true = 2.5e-4  # m^2/s
    s_true = 0.025
    q_lps = 6.0
    q_m3_s = q_lps / 1000.0
    rw = 0.10

    # Generate synthetic Theis drawdown curve for t = 10s to 7200s (2 hours)
    times = np.logspace(1.0, 3.85, 60)
    u = (rw**2 * s_true) / (4.0 * t_true * times)
    s_drawdown = (q_m3_s / (4.0 * math.pi * t_true)) * exp1(u)

    # Add 2% measurement noise
    rng = np.random.default_rng(42)
    s_noisy = s_drawdown + rng.normal(0.0, 0.02, size=len(times))

    estimator = CooperJacobEstimator(well_radius_m=rw)
    res = estimator.estimate_transmissivity(
        pump_id="PUMP-CJ-TEST",
        t_seconds=times,
        drawdown_m=s_noisy,
        q_avg_lps=q_lps,
        s_prior=s_true,
    )

    log10_t_true = math.log10(t_true)
    err = abs(res.log10_t - log10_t_true)

    print(
        f"Cooper-Jacob -> True log10(T): {log10_t_true:.3f}, Est: {res.log10_t:.3f}, Error: {err:.3f}"
    )
    assert err < 0.20, f"log10(T) error {err} exceeds 0.20 bound (target < 0.3)"
    assert res.r_squared > 0.95, "R^2 must be > 0.95 on Theis curve"


def test_cooper_jacob_flow_dimension():
    """Test Barker flow dimension n fitting on 2D radial flow."""
    times = np.logspace(1.5, 3.8, 40)
    # Radial flow has logarithmic drawdown slope
    drawdown = 0.8 * np.log(times) - 1.2

    estimator = CooperJacobEstimator()
    res = estimator.estimate_transmissivity(
        pump_id="PUMP-FLOW-DIM",
        t_seconds=times,
        drawdown_m=drawdown,
        q_avg_lps=5.0,
        fit_flow_dimension=True,
    )
    # Radial flow corresponds to n ~ 1.8 to 2.2
    assert 1.4 <= res.flow_dimension_n <= 2.6, (
        f"Flow dim {res.flow_dimension_n} outside expected radial bounds"
    )


def test_jacob_well_loss_separation():
    """Verify B and C separation using multi-step flow rates."""
    b_true = 450.0  # s/m^2
    c_true = 35000.0  # s^2/m^5

    q_steps = np.array([3.0, 5.0, 7.0, 9.0])  # L/s
    q_m3_s = q_steps / 1000.0
    s_drawdown = b_true * q_m3_s + c_true * (q_m3_s**2)

    estimator = JacobWellLossEstimator()
    res = estimator.estimate_coefficients("PUMP-WL", q_steps, s_drawdown, rated_q_lps=6.0)

    assert abs(res.b_formation_loss - b_true) < 20.0
    assert abs(res.c_turbulent_loss - c_true) < 1500.0
    assert res.well_efficiency_pct > 50.0


def test_restart_recovery_regression():
    """Verify recovery regression recovers transmissivity and regional drift."""
    t_true = 1.8e-4
    q_bar = 5.5
    q_m3_s = q_bar / 1000.0
    beta_drift_true = 0.015  # 1.5 cm/day decline

    # Generate 15 synthetic cycles
    cycles = []
    rng = np.random.default_rng(101)
    for i in range(15):
        t_pump = float(rng.uniform(3600.0, 18000.0))
        t_off = float(rng.uniform(7200.0, 43200.0))
        day = i * 2.0
        ratio = (t_pump + t_off) / t_off
        theis_s = (2.303 * q_m3_s / (4.0 * math.pi * t_true)) * math.log10(ratio)
        drift_s = beta_drift_true * day
        noise = float(rng.normal(0.0, 0.03))
        res_s = max(0.05, theis_s + drift_s + noise)

        cycles.append(
            PumpingCycleSummary(
                cycle_id=i,
                t_pump_seconds=t_pump,
                t_off_seconds=t_off,
                q_avg_lps=q_bar,
                residual_drawdown_m=res_s,
                calendar_day=day,
            )
        )

    regressor = RestartRecoveryRegressor()
    res = regressor.estimate_recovery_transmissivity("PUMP-REC", cycles)

    err = abs(res.log10_t - math.log10(t_true))
    print(
        f"Recovery Regression -> True log10(T): {math.log10(t_true):.3f}, Est: {res.log10_t:.3f}, Err: {err:.3f}"
    )
    assert err < 0.25, f"Recovery log10(T) error {err} exceeds 0.25"


def test_hydraulic_interference_tomography():
    """Verify crowd tomography estimates storativity S from cross-well interference."""
    t_inter = 2.0e-4
    s_true = 0.020
    tomography = HydraulicInterferenceTomography(max_distance_m=800.0)

    # Simulate 8 interference pairs with realistic village parcel distances (30-100m)
    obs_list = []
    distances = [30.0, 40.0, 50.0, 60.0, 70.0, 80.0, 90.0, 100.0]
    dt_start = 86400.0  # 24 hours
    dt_stop = 7200.0  # stopped 2 hours ago
    q_lps = 7.0

    for d in distances:
        drawdown = tomography.theis_pulse_drawdown(d, dt_start, dt_stop, q_lps, t_inter, s_true)
        if drawdown > 0.02:
            obs_list.append(
                InterferenceObservation(
                    source_pump_id="PUMP-A",
                    target_pump_id=f"PUMP-B-{int(d)}",
                    distance_r_m=d,
                    dt_since_source_start_s=dt_start,
                    dt_since_source_stop_s=dt_stop,
                    q_source_lps=q_lps,
                    observed_drawdown_m=drawdown,
                )
            )

    result = tomography.invert_storativity(obs_list, prior_t_m2_s=t_inter)
    print(
        f"Tomography Result -> S_est: {result.estimated_s_storativity}, Status: {result.identifiability_status}"
    )
    assert abs(result.estimated_s_storativity - s_true) < 0.015
    assert result.identifiability_status == "Identified"
