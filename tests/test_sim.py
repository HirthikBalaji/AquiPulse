"""Unit tests for AquiPulse simulator (sim/) package."""

import numpy as np

from sim.adversary import AdversaryManager
from sim.aquifer import Aquifer2D, AquiferConfig
from sim.catalog import create_pump_instance, get_catalog
from sim.generate import run_district_simulation
from sim.sensor import EdgeSensorNode


def test_pump_catalog_size_and_diversity():
    """Verify pump catalog has >= 30 distinct families across HP, phase, and type."""
    catalog = get_catalog()
    assert len(catalog) >= 30, f"Expected >= 30 pump families, found {len(catalog)}"

    phases = {f.phase for f in catalog.values()}
    types = {f.pump_type for f in catalog.values()}
    hps = {f.hp for f in catalog.values()}

    assert 1 in phases and 3 in phases, "Catalog must contain both 1-phase and 3-phase pumps"
    assert "submersible" in types and "centrifugal" in types, (
        "Catalog must have submersible and centrifugal"
    )
    assert min(hps) <= 1.0 and max(hps) >= 10.0, "Catalog must span 1 HP to at least 10 HP"


def test_pump_affinity_laws_and_slip():
    """Test motor slip, affinity laws, and operating point solution."""
    inst = create_pump_instance("PUMP-001", "SUB-3P-5HP-H60", z_static_m=40.0)

    # Slip increases with load
    slip_light = inst.compute_slip(p_shaft_kw=1.0, v_actual=415.0, freq_actual=50.0)
    slip_heavy = inst.compute_slip(p_shaft_kw=3.5, v_actual=415.0, freq_actual=50.0)
    assert slip_heavy > slip_light

    # Voltage drop increases slip
    slip_sag = inst.compute_slip(p_shaft_kw=3.0, v_actual=340.0, freq_actual=50.0)
    slip_nom = inst.compute_slip(p_shaft_kw=3.0, v_actual=415.0, freq_actual=50.0)
    assert slip_sag > slip_nom

    # Operating point solution
    q, h_dyn, p_shaft, p_el = inst.solve_operating_point(
        h_static_and_drawdown_m=42.0, v_actual=415.0, freq_actual=50.0
    )
    assert q > 0.0, "Flow rate must be positive for head below shutoff"
    assert h_dyn >= 42.0, "Dynamic head must be at least static head"
    assert p_el > p_shaft, "Electrical power must exceed shaft power (efficiency < 1)"


def test_aquifer_mass_balance_conservation():
    """Verify unconfined aquifer flow solver strictly conserves mass to < 1e-12."""
    config = AquiferConfig(nx=15, ny=15, dx=200.0, dy=200.0)
    aquifer = Aquifer2D(config, rng=np.random.default_rng(42))

    # Run for 24 hours (144 steps of 600s) with active extraction
    pumping = {
        (5, 5): 0.008,  # 8 L/s in m^3/s
        (8, 9): 0.012,  # 12 L/s
    }

    for step in range(72):
        aquifer.step(dt_seconds=600.0, pumping_rates_m3_s=pumping, day_of_year=200.0)

    d_stor, net_inflow, rel_err = aquifer.verify_mass_balance()
    assert rel_err < 1e-12, f"Aquifer mass balance violation! rel_err = {rel_err}"


def test_start_burst_transient_and_column_fill():
    """Verify 4 kHz start burst captures physical column fill duration correlated with depth."""
    sensor = EdgeSensorNode("PUMP-BURST-TEST", secret_key=b"test_key_123456789012345678901234")

    # Shallow well vs deep well
    shallow_burst = sensor.generate_start_burst(
        timestamp_start_s=100.0,
        z_static_depth_m=15.0,
        q_steady_lps=6.0,
        p_steady_kw=4.0,
        v_rms=415.0,
        duration_s=10.0,
        fs_hz=4000,
    )
    deep_burst = sensor.generate_start_burst(
        timestamp_start_s=200.0,
        z_static_depth_m=80.0,
        q_steady_lps=6.0,
        p_steady_kw=4.0,
        v_rms=415.0,
        duration_s=10.0,
        fs_hz=4000,
    )

    assert deep_burst.metadata["t_fill_s"] > shallow_burst.metadata["t_fill_s"]
    assert len(shallow_burst.samples_raw) == 10 * 4000 * 2  # 16-bit integers = 2 bytes per sample


def test_adversary_tamper_injection():
    """Verify adversary module alters telemetry for tamper testing."""
    adv = AdversaryManager()
    sensor = EdgeSensorNode("PUMP-TAMP", secret_key=b"secret_key_12345678901234567890")

    adv.configure_tamper("PUMP-TAMP", "ct_open")
    pkt = sensor.generate_telemetry_1hz(10.0, 415.0, 10.0, 0.85, 5.0, 50.0)
    tampered_pkt = adv.apply_tamper(pkt, "PUMP-TAMP")
    assert tampered_pkt is not None
    assert tampered_pkt.i_rms == 0.0 and tampered_pkt.p_kw == 0.0
    assert tampered_pkt.v_rms > 350.0  # Voltage still present


def test_simulation_reproducibility():
    """Verify simulator is deterministic given identical seed."""
    res1 = run_district_simulation(
        num_wells=5, num_days=0.1, seed=99, grid_dim=10, out_dir="test_out1", verbose=False
    )
    res2 = run_district_simulation(
        num_wells=5, num_days=0.1, seed=99, grid_dim=10, out_dir="test_out2", verbose=False
    )

    assert res1["mass_balance_rel_err"] == res2["mass_balance_rel_err"]
    assert len(res1["telemetry"]) == len(res2["telemetry"])
    assert res1["telemetry"][0]["p_kw"] == res2["telemetry"][0]["p_kw"]
