"""AquiPulse District Simulator CLI and Generation Pipeline.

CLI: python -m sim.generate --wells 500 --seed 1 --days 2 --out-dir sim_data

Generates:
- 2D heterogeneous aquifer ground truth (K, Sy, bedrock, topography)
- Fleet of irrigation pumps from the 35-family catalog
- 1 Hz electrical telemetry + 4 kHz start transients
- Ground-truth pumping volumes, heads, aquifer hydraulic properties
- Adversarial attacks and ghost wells for integrity benchmarking
- Exact mass-balance closure verification
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np

from sim.adversary import AdversaryManager
from sim.aquifer import Aquifer2D, AquiferConfig
from sim.catalog import PUMP_CATALOG, PumpState, create_pump_instance
from sim.farmer import CROP_CATALOG, FarmerAgent
from sim.grid import FeederConfig, RuralFeeder
from sim.sensor import EdgeSensorNode


def run_district_simulation(
    num_wells: int = 50,
    num_days: float = 2.0,
    seed: int = 1,
    grid_dim: int = 20,
    cell_size_m: float = 200.0,
    out_dir: str = "sim_data",
    verbose: bool = True,
) -> Dict[str, Any]:
    """Execute complete district simulation and write synthetic telemetry and ground truth."""
    rng = np.random.default_rng(seed)
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    if verbose:
        print("=== Starting AquiPulse District Simulation ===")
        print(f"Wells: {num_wells}, Days: {num_days}, Seed: {seed}, Grid: {grid_dim}x{grid_dim}")

    # 1. Initialize Aquifer
    aq_config = AquiferConfig(
        nx=grid_dim,
        ny=grid_dim,
        dx=cell_size_m,
        dy=cell_size_m,
        initial_depth=35.0,
    )
    aquifer = Aquifer2D(aq_config, rng=rng)

    # 2. Feeder and Grid setup
    feeder_config = FeederConfig()
    feeder = RuralFeeder(feeder_config, rng=rng)

    # 3. Create Well Fleet
    wells: List[Dict[str, Any]] = []
    sensors: Dict[str, EdgeSensorNode] = {}
    farmers: Dict[str, FarmerAgent] = {}
    pumps: Dict[str, PumpState] = {}

    crops = list(CROP_CATALOG.values())
    catalog_list = PUMP_CATALOG

    adversary = AdversaryManager(rng=rng)

    for i in range(num_wells):
        pump_id = f"PUMP-{i + 1:04d}"
        farmer_id = f"FARMER-{i + 1:04d}"

        # Spatial placement (clustered or distributed)
        x_m = float(rng.uniform(0.05 * grid_dim * cell_size_m, 0.95 * grid_dim * cell_size_m))
        y_m = float(rng.uniform(0.05 * grid_dim * cell_size_m, 0.95 * grid_dim * cell_size_m))
        ix, iy = aquifer.locate_cell(x_m, y_m)

        # 20% solar pumps, 80% grid pumps
        is_solar = bool(rng.uniform(0.0, 1.0) < 0.20)

        # Select pump family compatible with solar or grid
        if is_solar:
            fam_candidates = [f for f in catalog_list if "SOLAR" in f.family_id]
        else:
            fam_candidates = [f for f in catalog_list if "SOLAR" not in f.family_id]
        chosen_fam = fam_candidates[int(rng.integers(0, len(fam_candidates)))]

        # Physical pump instance
        z_static_init = float(aquifer.z_surf[iy, ix] - aquifer.h[iy, ix])
        wear_years = float(rng.uniform(0.0, 8.0))
        pump_inst = create_pump_instance(
            pump_id=pump_id,
            family_id=chosen_fam.family_id,
            z_static_m=z_static_init,
            wear_years=wear_years,
            solar_vfd=is_solar,
            rng=rng,
        )

        # Farmer agent
        crop = crops[int(rng.integers(0, len(crops)))]
        parcel_ha = float(rng.uniform(1.0, 4.0))
        farmer = FarmerAgent(
            farmer_id=farmer_id,
            pump_id=pump_id,
            crop=crop,
            parcel_area_ha=parcel_ha,
            is_solar=is_solar,
            rng=rng,
        )

        # Edge Sensor Node
        secret_key = rng.bytes(32)
        ct_err = float(rng.normal(0.0, 0.012))  # +-1.2% CT error
        sensor = EdgeSensorNode(
            pump_id=pump_id,
            secret_key=secret_key,
            ct_ratio_error=ct_err,
            rng=rng,
        )

        pumps[pump_id] = pump_inst
        sensors[pump_id] = sensor
        farmers[pump_id] = farmer

        wells.append(
            {
                "pump_id": pump_id,
                "farmer_id": farmer_id,
                "x_m": round(x_m, 2),
                "y_m": round(y_m, 2),
                "grid_ix": ix,
                "grid_iy": iy,
                "family_id": chosen_fam.family_id,
                "make": chosen_fam.make,
                "model": chosen_fam.model,
                "hp": chosen_fam.hp,
                "phase": chosen_fam.phase,
                "is_solar": is_solar,
                "wear_years": round(wear_years, 2),
                "crop": crop.crop_name,
                "parcel_area_ha": round(parcel_ha, 2),
                "t_true_m2_s": float(aquifer.get_transmissivity()[iy, ix]),
                "sy_true": float(aquifer.sy[iy, ix]),
            }
        )

    # 4. Inject Adversaries (CT-open, bypass, replay) and Ghost Wells
    num_tampered = max(1, int(num_wells * 0.08))
    tamper_modes = ["ct_open", "bypass_50pct", "replay"]
    tampered_indices = rng.choice(num_wells, size=num_tampered, replace=False)
    for idx_t in tampered_indices:
        p_id = wells[idx_t]["pump_id"]
        t_mode = str(tamper_modes[int(rng.integers(0, len(tamper_modes)))])
        adversary.configure_tamper(p_id, t_mode)
        wells[idx_t]["tamper_mode"] = t_mode

    # Add 2 to 4 ghost wells
    num_ghosts = max(2, int(num_wells * 0.04))
    ghost_wells_info = []
    for g in range(num_ghosts):
        gw_id = f"GHOST-{g + 1:02d}"
        gx = float(rng.uniform(0.1 * grid_dim * cell_size_m, 0.9 * grid_dim * cell_size_m))
        gy = float(rng.uniform(0.1 * grid_dim * cell_size_m, 0.9 * grid_dim * cell_size_m))
        q_gw = float(rng.uniform(4.0, 9.0))
        run_h = float(rng.uniform(4.0, 8.0))
        st_h = float(rng.uniform(10.0, 18.0))
        gw = adversary.add_ghost_well(gw_id, gx, gy, q_gw, run_h, st_h)
        ghost_wells_info.append(
            {
                "well_id": gw_id,
                "x_m": round(gx, 2),
                "y_m": round(gy, 2),
                "q_lps": round(q_gw, 2),
                "run_hours_per_day": round(run_h, 2),
                "start_hour": round(st_h, 2),
            }
        )

    # 5. Simulation Execution Loop
    # Time parameters: 1-minute steps for dynamic simulation, with 1 Hz sub-telemetry
    step_dt_s = 60.0  # 60 second solver step
    total_seconds = num_days * 86400.0
    sim_time = 0.0

    telemetry_records: List[Dict[str, Any]] = []
    ground_truth_records: List[Dict[str, Any]] = []
    start_bursts: List[Dict[str, Any]] = []

    last_pump_running: Dict[str, bool] = {w["pump_id"]: False for w in wells}
    cum_volume_m3: Dict[str, float] = {w["pump_id"]: 0.0 for w in wells}

    step_count = int(total_seconds / step_dt_s)
    if verbose:
        print(f"Simulating {step_count} time steps ({step_dt_s}s resolution)...")

    # Day of year (monsoon period for dynamic recharge: day 200)
    sim_day_of_year = 200.0

    for step_i in range(step_count):
        sim_time = step_i * step_dt_s
        power_avail = feeder.is_power_available(sim_time)

        # Total fleet kW currently running
        active_kw = sum(
            pumps[w["pump_id"]].family.p_rated_kw
            for w in wells
            if last_pump_running[w["pump_id"]] and not w["is_solar"]
        )

        pumping_rates_m3_s: Dict[Tuple[int, int], float] = {}

        # Update ghost wells extraction into the aquifer
        for gw in adversary.ghost_wells:
            if gw.is_active(sim_time):
                g_ix, g_iy = aquifer.locate_cell(gw.x_coord, gw.y_coord)
                cell_key = (g_ix, g_iy)
                pumping_rates_m3_s[cell_key] = pumping_rates_m3_s.get(cell_key, 0.0) + (
                    gw.q_lps / 1000.0
                )

        # Update each monitored well
        for w in wells:
            p_id = w["pump_id"]
            farmer = farmers[p_id]
            pump = pumps[p_id]
            sensor = sensors[p_id]
            ix, iy = w["grid_ix"], w["grid_iy"]

            should_run, freq_hz = farmer.update_irrigation_decision(
                dt_seconds=step_dt_s,
                time_seconds=sim_time,
                power_available=power_avail,
            )

            v_supply, grid_freq = feeder.get_voltage_and_frequency(
                sim_time_seconds=sim_time,
                fleet_active_kw=active_kw,
                phase=pump.family.phase,
            )

            if not w["is_solar"]:
                operating_freq = grid_freq
            else:
                operating_freq = freq_hz
                # Solar inverter synthesizes 3-phase AC voltage proportional to frequency
                if operating_freq > 20.0:
                    v_supply = pump.family.v_rated * (operating_freq / 50.0)
                else:
                    v_supply = 0.0

            if should_run and v_supply > 50.0 and operating_freq >= 25.0:
                is_running = True
                # Query local dynamic drawdown at well
                # Tentative Q guess for well head calculation
                approx_q = pump.family.rated_q_lps
                z_static, s_local, total_lift = aquifer.compute_local_well_head(
                    ix, iy, q_lps=approx_q
                )

                # Solve coupled pump operating point
                q_lps, h_dyn, p_shaft, p_el = pump.solve_operating_point(
                    h_static_and_drawdown_m=total_lift,
                    v_actual=v_supply,
                    freq_actual=operating_freq,
                )

                v_act, i_rms, pf = pump.compute_electrical(p_el, v_supply, operating_freq)

                # Add to aquifer cell extraction
                cell_key = (ix, iy)
                pumping_rates_m3_s[cell_key] = pumping_rates_m3_s.get(cell_key, 0.0) + (
                    q_lps / 1000.0
                )

                pumped_vol_step = (q_lps / 1000.0) * step_dt_s
                cum_volume_m3[p_id] += pumped_vol_step

                # Check if this step is a new start (Start Burst Trigger)
                if not last_pump_running[p_id]:
                    # Pump just started: capture 4 kHz start-burst
                    burst = sensor.generate_start_burst(
                        timestamp_start_s=sim_time,
                        z_static_depth_m=z_static,
                        q_steady_lps=q_lps,
                        p_steady_kw=p_el,
                        v_rms=v_act,
                        duration_s=60.0,
                    )
                    start_bursts.append(
                        {
                            "pump_id": burst.pump_id,
                            "timestamp_start_s": burst.timestamp_start_s,
                            "fs_hz": burst.fs_hz,
                            "duration_s": burst.duration_s,
                            "metadata": burst.metadata,
                            "byte_length": len(burst.samples_raw),
                        }
                    )

                last_pump_running[p_id] = True
            else:
                is_running = False
                last_pump_running[p_id] = False
                q_lps = 0.0
                p_el = 0.0
                i_rms = 0.0
                pf = 1.0
                z_static = float(aquifer.z_surf[iy, ix] - aquifer.h[iy, ix])
                h_dyn = z_static
                v_act = v_supply if (power_avail and not w["is_solar"]) else 0.0

            # Generate sensor telemetry
            raw_pkt = sensor.generate_telemetry_1hz(
                sim_time_s=sim_time,
                v_true=v_act,
                i_true=i_rms,
                pf_true=pf,
                p_kw_true=p_el,
                freq_true=operating_freq if is_running else 50.0,
            )

            # Pass through adversary module for tamper injection
            final_pkt = adversary.apply_tamper(raw_pkt, p_id)

            if final_pkt is not None:
                telemetry_records.append(
                    {
                        "pump_id": final_pkt.pump_id,
                        "ts": final_pkt.timestamp_s,
                        "v_rms": final_pkt.v_rms,
                        "i_rms": final_pkt.i_rms,
                        "pf": final_pkt.pf,
                        "p_kw": final_pkt.p_kw,
                        "freq_hz": final_pkt.freq_hz,
                        "signature": final_pkt.signature,
                    }
                )

            # Ground truth record
            ground_truth_records.append(
                {
                    "pump_id": p_id,
                    "ts": sim_time,
                    "q_true_lps": round(q_lps, 3),
                    "h_dyn_true_m": round(h_dyn, 2),
                    "z_static_true_m": round(z_static, 2),
                    "cum_vol_m3": round(cum_volume_m3[p_id], 3),
                    "p_shaft_kw": round(p_el * 0.85 if is_running else 0.0, 3),
                    "eta_overall": round((9.81 * q_lps * h_dyn / (1000.0 * max(0.01, p_el))), 3)
                    if is_running
                    else 0.0,
                }
            )

        # Step groundwater flow solver
        aquifer.step(
            dt_seconds=step_dt_s,
            pumping_rates_m3_s=pumping_rates_m3_s,
            day_of_year=sim_day_of_year + (sim_time / 86400.0),
        )

    # Verify mass balance
    d_stor, net_inflow, mb_rel_err = aquifer.verify_mass_balance()

    if verbose:
        print(
            f"Simulation completed. Telemetry records: {len(telemetry_records)}, Bursts: {len(start_bursts)}"
        )
        print(
            f"Mass balance check: delta_storage={d_stor:.2f} m3, net_inflow={net_inflow:.2f} m3, rel_err={mb_rel_err:.2e}"
        )

    # Save outputs to out_path
    with open(out_path / "wells.json", "w") as f:
        json.dump(wells, f, indent=2)

    with open(out_path / "ghost_wells.json", "w") as f:
        json.dump(ghost_wells_info, f, indent=2)

    with open(out_path / "telemetry_sample.json", "w") as f:
        # Save sample of telemetry to keep json size reasonable
        json.dump(telemetry_records[:5000], f, indent=2)

    with open(out_path / "start_bursts.json", "w") as f:
        json.dump(start_bursts, f, indent=2)

    with open(out_path / "ground_truth_summary.json", "w") as f:
        summary = {
            "num_wells": num_wells,
            "num_days": num_days,
            "seed": seed,
            "mass_balance": {
                "delta_storage_m3": round(d_stor, 3),
                "net_inflow_m3": round(net_inflow, 3),
                "relative_error": float(f"{mb_rel_err:.2e}"),
            },
            "total_pumped_m3": round(aquifer.total_pumped_vol, 2),
            "total_recharge_m3": round(aquifer.total_recharge_vol, 2),
            "wells_cum_volume_m3": {p: round(v, 2) for p, v in cum_volume_m3.items()},
        }
        json.dump(summary, f, indent=2)

    # Save spatial aquifer fields
    np.savez_compressed(
        out_path / "aquifer_fields.npz",
        log_k=aquifer.log_k,
        k=aquifer.k,
        sy=aquifer.sy,
        bedrock=aquifer.bedrock,
        z_surf=aquifer.z_surf,
        h_final=aquifer.h,
    )

    return {
        "wells": wells,
        "ghost_wells": ghost_wells_info,
        "telemetry_count": len(telemetry_records),
        "telemetry": telemetry_records,
        "ground_truth": ground_truth_records,
        "start_bursts": start_bursts,
        "aquifer": aquifer,
        "mass_balance_rel_err": mb_rel_err,
    }


def main() -> None:
    """CLI entrypoint for python -m sim.generate."""
    parser = argparse.ArgumentParser(description="AquiPulse District Simulator")
    parser.add_argument(
        "--wells", type=int, default=50, help="Number of wells in the fleet (default: 50)"
    )
    parser.add_argument(
        "--days", type=float, default=2.0, help="Simulation duration in days (default: 2.0)"
    )
    parser.add_argument(
        "--seed", type=int, default=1, help="Random seed for reproducibility (default: 1)"
    )
    parser.add_argument(
        "--grid-size", type=int, default=20, help="Aquifer grid dimension NxN (default: 20)"
    )
    parser.add_argument(
        "--out-dir", type=str, default="sim_data", help="Output directory path (default: sim_data)"
    )

    args = parser.parse_args()
    run_district_simulation(
        num_wells=args.wells,
        num_days=args.days,
        seed=args.seed,
        grid_dim=args.grid_size,
        out_dir=args.out_dir,
    )


if __name__ == "__main__":
    main()
