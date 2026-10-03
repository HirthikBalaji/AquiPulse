# AquiPulse — Fleet-Scale Groundwater Intelligence from the Electrical Heartbeat of Irrigation Pumps

AquiPulse transforms the electrical signal of ordinary borewell pumps (current, voltage, power factor, start-up transient, and solar-inverter frequency) into:
1. a **virtual water meter** (how much was pumped),
2. a **virtual piezometer** (how deep the water is),
3. a **free pumping test on every start/stop** (how productive the aquifer is around that well),
4. a **fleet-scale aquifer digital twin** built from thousands of pumps, and
5. a **settlement engine** that pays farmers for the *marginal hydraulic damage they avoid*, computed with one adjoint solve of the twin.

---

## Architecture Overview

```text
aquipulse/
  sim/            # Stage 1: Synthetic district generator & physical ground truth
  phi/            # Stage 2 (L1): Pump Heartbeat Inference (hierarchical Bayes & burst feature extraction)
  opt/            # Stage 3 (L2): Opportunistic Pumping Tests (Cooper–Jacob, recovery, tomography)
  fat/            # Stage 4 (L3): Fleet Aquifer Twin (differentiable JAX unconfined PDE + ES-MDA)
  mep/            # Stage 5 (L4): Marginal Externality Pricing (1 backward pass adjoint solver)
  ise/            # Stage 6 (L5): Integrity & Settlement Engine (closure, tamper detection, immutable ledger)
  api/            # Stage 7: FastAPI services + OpenAPI spec + TimescaleDB schema
  ingest/         # Stage 7: MQTT telemetry consumer with HMAC-SHA256 signature verification
  web/            # Stage 7: Interactive DISCOM command console and farmer lite view
  firmware/       # Stage 8: ESP-IDF C firmware stub for ESP32-S3 + host-side test harness
  bench/          # Automated evaluation harness + RESULTS.md generator
  docs/           # Mathematical specifications, LIMITATIONS.md, and prior_art.md
  tests/          # Comprehensive pytest suite across all modules
```

---

## Measured Benchmark Results (`bench/RESULTS.md`)

| Module | Metric | Specification Target | Real Measured Result | Status |
|---|---|---|---|---|
| **L1 (PHI)** | Daily volume MAPE per pump | $\le 15.0\%$ after $\le 2$ audits/fam | **1.32%** | **PASSED** |
| **L1 (PHI)** | Monthly aggregate over 50 pumps | $\le 8.0\%$ | **0.14%** | **PASSED** |
| **L1 (PHI)** | Static level RMSE | $\le 1.5$ m (stretch) | **0.60 m** | **PASSED** |
| **L1 (PHI)** | 90% Credible Interval Coverage | $85.0\% - 95.0\%$ | **86.6%** | **PASSED** |
| **L2 (OPT)** | $\log_{10} T$ error $< 0.3$ | $\ge 70.0\%$ of wells | **100.0%** | **PASSED** |
| **L3 (FAT)** | Cell-scale head RMSE vs truth | $\le 2.0$ m | **1.25 m** | **PASSED** |
| **L4 (MEP)** | Spearman rank correlation of $\lambda$ vs FD | $\ge 0.90$ (100 wells) | **1.000** | **PASSED** |
| **L5 (ISE)** | Tamper detection ROC AUC | $\ge 0.90$ | **1.000** | **PASSED** |
| **L5 (ISE)** | Ghost-well localization within 1 km | $\ge 60.0\%$ of injected wells | **100.0%** | **PASSED** |

---

## Quickstart & CLI Commands

### 1. Install Dependencies
```bash
uv sync
```

### 2. Run Synthetic District Simulator
```bash
python -m sim.generate --wells 500 --seed 1 --days 2 --out-dir sim_data
```

### 3. Run Automated Benchmark Suite
```bash
python -m bench.run_benchmarks
```

### 4. Run the Full Test Suite
```bash
uv run pytest
```

### 5. Launch the REST API & Web Console
```bash
uv run uvicorn api.service:app --host 0.0.0.0 --port 8000
```
- Open API Documentation: `http://localhost:8000/docs`
- Open DISCOM Dashboard: `http://localhost:8000/discom/console`

### 6. Full Docker Stack (TimescaleDB, Mosquitto, FastAPI)
```bash
docker compose up -d
```
