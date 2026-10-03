"""Unit and benchmark tests for Layer 5: Integrity and Settlement Engine (ise/)."""

import math

import numpy as np

from ise.closure import ClosureIntegrityEngine, evaluate_auc_score
from ise.ghost_well import GhostWellLocalizer
from ise.ledger import SettlementEntry, SettlementLedger


def test_tamper_detection_auc_benchmark():
    """Verify composite tamper detection achieves ROC AUC >= 0.90 on simulated fleet."""
    engine = ClosureIntegrityEngine()
    rng = np.random.default_rng(808)

    y_true = []
    y_scores = []

    # 1. 100 Honest Wells
    for i in range(100):
        # Honest well: volume closely tracks agronomic ET demand
        v_agro = float(rng.uniform(1500.0, 4500.0))
        v_phi = v_agro * float(rng.normal(1.0, 0.08))  # ~8% natural variation

        res = engine.evaluate_closure(
            pump_id=f"HONEST-{i}",
            v_phi_m3=v_phi,
            parcel_area_ha=2.0,
            crop_etc_mm=250.0,
            effective_rain_mm=40.0,
            physics_flags_count=0,
            has_invalid_signature=False,
        )
        y_true.append(0)
        y_scores.append(res.tamper_probability_score)

    # 2. 30 Tampered Wells (CT-open, Shunt Bypass, Crypto forgery)
    for j in range(30):
        tamper_type = j % 3
        v_agro = float(rng.uniform(1500.0, 4500.0))

        if tamper_type == 0:
            # Bypass: records only 30% of actual water pumped
            v_phi = v_agro * 0.30
            phys_flags = 1
            bad_sig = False
        elif tamper_type == 1:
            # CT-open: current is zero, volume is near zero despite healthy crop
            v_phi = 20.0
            phys_flags = 2
            bad_sig = False
        else:
            # Replay / Crypto spoof
            v_phi = v_agro * 0.50
            phys_flags = 1
            bad_sig = True

        res = engine.evaluate_closure(
            pump_id=f"TAMPERED-{j}",
            v_phi_m3=v_phi,
            parcel_area_ha=2.0,
            crop_etc_mm=250.0,
            effective_rain_mm=40.0,
            physics_flags_count=phys_flags,
            has_invalid_signature=bad_sig,
        )
        y_true.append(1)
        y_scores.append(res.tamper_probability_score)

    auc = evaluate_auc_score(y_true, y_scores)
    print(f"ISE Benchmark -> Tamper Detection ROC AUC: {auc:.4f}")

    assert auc >= 0.90, f"Tamper AUC {auc:.4f} below 0.90 benchmark target"


def test_ghost_well_localization_benchmark():
    """Verify hidden ghost well adjoint localization locates wells within 1 km for >= 60%."""
    nx, ny = 20, 20
    dx, dy = 200.0, 200.0  # 4km x 4km domain
    localizer = GhostWellLocalizer(nx, ny, dx, dy)
    rng = np.random.default_rng(909)

    # Test 10 synthetic ghost well injections
    n_tests = 10
    within_1km_count = 0
    errors_km = []

    # Monitoring grid of 25 sensor borewells across domain
    sensor_x = np.linspace(400.0, 3600.0, 5)
    sensor_y = np.linspace(400.0, 3600.0, 5)
    SX, SY = np.meshgrid(sensor_x, sensor_y)
    sensors = list(zip(SX.flatten(), SY.flatten()))

    for test_i in range(n_tests):
        # Place ghost well
        true_gx = float(rng.uniform(800.0, 3200.0))
        true_gy = float(rng.uniform(800.0, 3200.0))
        ghost_q_lps = 6.5
        t_field = 2.0e-4

        # Calculate residual drawdown observed at each sensor
        residuals = []
        for sx, sy in sensors:
            dist = math.sqrt((sx - true_gx) ** 2 + (sy - true_gy) ** 2)
            # Theis/log cone of depression residual
            if dist < 1800.0:
                s_anom = (ghost_q_lps / 1000.0 / (2.0 * math.pi * t_field)) * math.log(
                    max(1.1, 2000.0 / max(50.0, dist))
                )
                # Add sensor noise
                s_anom += float(rng.normal(0.0, 0.05))
                residuals.append((sx, sy, max(0.0, s_anom)))
            else:
                residuals.append((sx, sy, 0.0))

        result = localizer.invert_ghost_source(
            monitored_head_residuals=residuals,
            prior_t_m2_s=t_field,
            true_location=(true_gx, true_gy),
        )

        assert result.localization_error_km is not None
        errors_km.append(result.localization_error_km)
        if result.within_1km_target:
            within_1km_count += 1

    success_rate = (within_1km_count / n_tests) * 100.0
    mean_err = float(np.mean(errors_km))
    print(
        f"Ghost Well Inversion -> Success Rate: {success_rate:.1f}%, Mean Error: {mean_err:.2f} km"
    )

    assert success_rate >= 60.0, f"Ghost well localization success {success_rate}% below 60% target"


def test_immutable_settlement_ledger():
    """Verify cryptographically signed settlement ledger detects any retroactive modification."""
    ledger = SettlementLedger()

    entry1 = SettlementEntry(
        entry_id="ENT-001",
        pump_id="PUMP-001",
        farmer_id="FARMER-001",
        period="2026-Q3",
        avoided_m3=450.0,
        unit_price_inr=2.20,
        bonus_inr=495.0,
        guardrail_ok=True,
        flags=[],
        timestamp=1700000100.0,
    )
    ledger.add_entry(entry1)
    block1 = ledger.commit_block()
    assert block1 is not None

    entry2 = SettlementEntry(
        entry_id="ENT-002",
        pump_id="PUMP-002",
        farmer_id="FARMER-002",
        period="2026-Q3",
        avoided_m3=320.0,
        unit_price_inr=1.90,
        bonus_inr=304.0,
        guardrail_ok=True,
        flags=[],
        timestamp=1700000200.0,
    )
    ledger.add_entry(entry2)
    block2 = ledger.commit_block()
    assert block2 is not None

    # Integrity verification
    assert ledger.verify_integrity() is True

    # Tampering test: maliciously change payout in block 1
    block1.entries[0].bonus_inr = 999999.0
    assert ledger.verify_integrity() is False, "Ledger must detect retroactive payload modification"
