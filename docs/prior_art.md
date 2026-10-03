# AquiPulse Prior Art & Freedom to Operate (FTO) Audit (`docs/prior_art.md`)

*Date of Scan: 3 October 2026*  
*Status: Initial Technical & Prior Art Review (Pre-FTO Legal Opinion)*

---

## 1. Primary Patent Landscape Analysis

| Patent / Publication | Assignee / Inventors | Key Claims | Differentiation in AquiPulse | FTO Risk Level |
|---|---|---|---|---|
| **US 12066313**  *(Issued ~2024)* | Monitored Water Solutions / Indiv. | Non-invasive groundwater well level monitoring from single-phase/three-phase AC motor current signatures during start-up and running transients. Focuses on residential/light-commercial single wells. | **AquiPulse L1/L2 Differentiation:** <br>1. AquiPulse solves the *degenerate identifiability problem* across unmetered farm wells with *unknown* pump curves using natural experiments (solar VFD frequency sweeps, grid voltage sags) combined with hierarchical Bayesian partial pooling across a 35-family catalog.<br>2. US 12066313 does not perform regional multi-well crowd hydraulic tomography or adjoint aquifer twin assimilation. | **Medium** (Requires formal claims mapping by patent attorney on L1 transient feature extraction) |
| **US 12152473**  *(Issued ~2024)* | Dynamic Aquifer Extraction Systems | Recharge-aware groundwater extraction scheduling; fits Theis analytical equation to recover transmissivity $T$ and storativity $S$ to prevent overdraft in single wells. | **AquiPulse L2/L4 Differentiation:** <br>1. US 12152473 relies on physical water level loggers / flow meter sensors installed inside the well.<br>2. AquiPulse invents *opportunistic pumping tests (OPT)* where recovery curves are observed strictly via *restart residuals* ($t'$) because unmetered pumps have zero telemetry when de-energized.<br>3. AquiPulse computes marginal hydraulic externality prices $\lambda_i = \partial L / \partial Q_i$ across thousands of wells via reverse-mode autodiff adjoints of a 2D nonlinear unconfined PDE twin. | **Low–Medium** (Independent claims depend on physical sensor hardware) |
| **US 10317894 Family** | Grundfos / Danfoss / Commercial Drives | Sensorless flow estimation in variable-frequency pump drives using internal motor voltage/frequency and factory-calibrated pump curves. | Closed industrial hydronic loops with known, un-degraded manufacturer curves and fixed piping; does not invert unknown deep borewells, dynamic aquifer drawdowns, or geological parameters. | **Low** |
| **USGS WRI 89-4107 & ASCE ELM Studies** | Hurr & Litke (1989); ASCE EWRI | Efficiency–Lift Method (ELM) estimating volume from utility power bills: $V \approx 367 \cdot \eta \cdot E / H$. | Relies on assumed static lift and assumed constant efficiency; fails in unmetered settings with unknown degrading pumps and dynamic drawdown cones (Korean Haean basin study demonstrated $-88\%$ to $+399\%$ empirical error). | **None** (Prior art / Public Domain) |

---

## 2. Academic Literature & Programmes

1. **IWMI SPaRC (Solar Power as a Remunerative Crop, Dhundi, Gujarat):**
   - Established that paying farmers to feed solar power into the grid curbs over-pumping.
   - *Gap filled by AquiPulse:* SPaRC used flat ₹/kWh feed-in bonuses and required expensive solar metering. AquiPulse replaces flat incentives with *aquifer-indexed marginal externality pricing ($\lambda_i$)*, paying for avoided hydraulic damage where it matters most, verified directly from pump telemetry.

2. **Barker (1988) Generalized Radial Flow & Theis (1935):**
   - Classical hydrogeological foundations.
   - AquiPulse applies Barker's flow dimension parameter $n$ to identify fracture channel flow versus 2D radial flow in hard-rock aquifers.

3. **Emerick & Reynolds (2013) ES-MDA:**
   - Ensemble Smoother with Multiple Data Assimilation.
   - Adapted in AquiPulse Layer 3 (FAT) to assimilate heterogeneous crowd-sourced telemetry, start-burst static heads, and satellite ET constraints into a calibrated 2D aquifer twin.

---

## 3. Commercial & Startup Landscape in India

- **Waterlab Solutions (Bhujal):** IoT acoustic water level monitoring device for borewells. Provides per-well depth measurements; does not perform electrical telemetry inversion, fleet-scale PDE digital twin inversion, or marginal externality pricing.
- **IIIT-Hyderabad String-Tension Sensor:** Mechanical string-tension logger for borewells. Focused on low-cost physical sensor hardware.
- **Borewell Controller OEMs (Kirloskar, Crompton, Shakti, Texmo):** Offer mobile starter controllers with dry-run protection; do not provide virtual metering, hydrogeology estimation, or settlement ledgers.

---

## 4. Conclusion & Action Items

- **Hypothesis:** No commercial or academic system provides the unified end-to-end stack (L1 Virtual Metering $\to$ L2 Opportunistic Pumping Tests $\to$ L3 Fleet Aquifer Twin $\to$ L4 Adjoint Externality Pricing $\to$ L5 Verifiable Settlement Ledger).
- **FTO Action Item:** Retain patent counsel to analyze the independent claims of US 12066313 (counsel review scheduled prior to Phase 1 field loop testing).
