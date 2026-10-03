# AquiPulse System Assumptions, Failure Modes, and Real-World Limitations (`LIMITATIONS.md`)

*Version 1.0 — October 2026*  
*Authors: AquiPulse Engineering and Hydrogeology Core*

This document provides a comprehensive audit of every physical, electrical, mathematical, and behavioural assumption embedded within AquiPulse (Layers L1 through L5) that could be violated in real-world agricultural borewell deployments.

---

## 1. Layer 1: Pump Heartbeat Inference (PHI)

| Assumption in Model | Real-World Failure Mode | Consequence | Mitigation & Fallback |
|---|---|---|---|
| **P-Q Monotonicity** | Pumps operated very close to Best Efficiency Point (BEP) have flat $\frac{\partial P}{\partial Q} \approx 0$. | Inversion Jacobian becomes ill-conditioned; multiple flow rates can produce identical electrical power. | Wide uncertainty intervals reported automatically; trigger active-learning bucket audit; exploit voltage sags / solar frequency sweeps to move operating point off-peak. |
| **Clean Water Density & Viscosity** | Silt, sand, or saline water entrainment ($\rho > 1000 \text{ kg/m}^3, \mu > 1.0 \text{ cP}$). | Implied hydraulic power equation underestimates mass lift; flow overestimated by 5–15%. | Seasonal water-quality calibration; conductivity sensor integration on Node G voltage taps where available. |
| **Uniform Motor Characteristics** | Unrewound / repeatedly rewound induction motors (common in rural India, rewound with non-spec copper gauge or altered pole turns). | Motor efficiency curve $\eta_m(\text{load})$ and rated slip deviate severely from catalog ($\eta_m$ drops from 85% to 65–70%). | Hierarchical partial pooling absorbs motor-level parameter offsets $\theta_i$; single bucket audit pins the individual motor's true efficiency curve. |
| **Rigid Vertical Riser Pipe** | Leaking delivery pipe couplings, column drainage check-valve failure, or HDPE flexible hose expansion under pressure. | 4 kHz start-burst column fill duration $t_{\text{fill}}$ reflects draining/filling leaks rather than static water table. | Cross-check $Z_s$ against steady-state dynamic head $H_d$; report wide confidence intervals if $t_{\text{fill}}$ disagrees with head curve. |
| **Stable Line Voltage & Frequency** | Extreme phase unbalance (>10%), harmonic pollution (THD > 12%), or sub-harmonic oscillations from rural distribution transformers. | Distorts RMS power factor calculation and creates artificial slip fluctuations. | Front-end digital filtering on ATM90E32 IC; discard telemetry during severe phase unbalance (>8%). |

---

## 2. Layer 2: Opportunistic Pumping Tests (OPT)

| Assumption in Model | Real-World Failure Mode | Consequence | Mitigation & Fallback |
|---|---|---|---|
| **Constant Rate Extraction** | As dynamic water level drops, pump head rises, causing flow rate $Q(t)$ to decline by 5–20% during a multi-hour irrigation run. | Violates constant-discharge assumption of Cooper-Jacob and Theis formulas. | Apply Birsoy-Summers variable-rate superposition or Agarwal equivalent drawdown time $t_{\text{equiv}} = \sum \Delta Q_i \log(t - t_i)$. |
| **Isotropic Equivalent Porous Medium** | Hard-rock basalt flows and crystalline granite basement with discrete, orthogonal fracture networks. | Drawdown exhibits linear flow ($s \propto \sqrt{t}$) or bilinear flow rather than logarithmic radial flow ($s \propto \ln t$). Single-well effective $T$ does not represent regional volume. | Barker (1988) Generalized Radial Flow dimension parameter $n \in [1.0, 3.0]$ is fitted; cell-scale claims only; use $T$ as a regional prior, not an exact point property. |
| **Identifiability of Storativity ($S$)** | Single-well pumping tests cannot separate storativity $S$ from wellbore skin factor $\xi$ and effective casing radius $r_w$. | Storativity $S$ estimated from single-well intercept $t_0$ is unreliable by an order of magnitude. | **Honest hydrogeology:** Do not report single-well $S$ as true formation storage. Use multi-well crowd interference tomography across neighbor pairs ($r \le 100$ m) to isolate true formation $S_y$. |
| **Static Level Recovery Completeness** | Rest intervals between irrigation cycles ($t'$) may be shorter than full aquifer recovery time ($t' < 5 \cdot t_{\text{pump}}$). | Residual drawdown from previous cycle contaminates subsequent cycle's initial head. | State-space tracking of residual drawdown memory; include explicit Theis recovery residual correction $s_{\text{res}}(t')$. |

---

## 3. Layer 3: Fleet Aquifer Twin (FAT)

| Assumption in Model | Real-World Failure Mode | Consequence | Mitigation & Fallback |
|---|---|---|---|
| **No-Flow / Static Boundary Conditions** | Regional basin boundary inflows, river-aquifer recharge, or canal seepage. | Groundwater balance overestimates depletion or misattributes lateral boundary inflow to local recharge. | Assimilate sparse official CGWB/State piezometers along basin boundaries; calibrate dynamic Robin boundary fluxes. |
| **Grid Discretization (200 m cells)** | Sub-grid hydraulic variations (e.g. productive fracture lineaments narrower than 20 m). | Effective continuum cell transmissivity under-predicts rapid localized drawdown cones. | Explicitly report model-error variance $\sigma_{\text{model}}^2$; enforce that externality pricing operates on cell-averaged hydraulic damage rather than micro-fracture singularities. |
| **Monsoon Recharge Linear Factor** | Nonlinear soil moisture threshold: intense storms produce rapid surface runoff without recharge, while gentle rain infiltrates efficiently. | Linear rainfall-recharge factor $\alpha$ misestimates post-monsoon water table rise. | Incorporate antecedent soil moisture index (SMI) and satellite soil moisture (e.g. SMAP / Sentinel-1 SAR). |

---

## 4. Layer 4: Marginal Externality Pricing (MEP)

| Assumption in Model | Real-World Failure Mode | Consequence | Mitigation & Fallback |
|---|---|---|---|
| **Perfect Adjoint Convexity** | Severe water table decline crossing dry-well threshold introduces discontinuous cost jumps. | Adjoint gradient $\nabla_Q L$ can be sensitive to step perturbations near bifurcation boundaries. | Smooth quadratic sigmoid approximations for failure risk $P_{\text{fail}}(h)$; regularize adjoint prices with spatial kernel smoothing. |
| **Counterfactual Baseline Honesty** | Historic farmer pumping baseline $Q_{\text{base}}$ could be inflated prior to programme enrollment ("strategic baselining"). | Farmers intentionally pump excessively during baseline years to earn larger reduction bonuses later. | Base counterfactuals primarily on satellite-mapped crop area $\times$ crop evapotranspiration ($ET_c$) and matched peer controls, rather than self-reported historical metering alone. |
| **Crop Water Stress Non-Linearity** | Farmer reduces pumping by 25% but shifts to high-value deficit-irrigated crops without yield reduction, or conversely causes hidden root-zone yield collapse. | Payout could penalize agronomic innovation or fail to catch hidden yield losses. | Calibrated NDVI / NDRE / EVI remote sensing guardrail benchmarks against village peer cohort; positive incentives only; farmer remains in full control. |

---

## 5. Layer 5: Integrity, Governance, & Hardware (ISE)

| Assumption in Model | Real-World Failure Mode | Consequence | Mitigation & Fallback |
|---|---|---|---|
| **Hardware Physical Tamper Resistance** | Split-core CT unlatched or shunt resistor placed across CT terminals; clamp placed on single phase while drawing three-phase load. | Measured power drops by 50–100% while pump extracts water undetected. | Water-balance closure residual $r_i = \frac{V_i^{\text{PHI}} - V_i^{\text{agro}}}{\sigma_i}$ detects persistent mismatch; CT-open electrical detector flags line energized with zero current; randomized active-learning physical audits. |
| **Ghost Well Exclusion** | Farmer shifts pumping from monitored subsidized well to an unregistered borewell 400 m away on adjacent unregistered parcel. | Local aquifer cone deepens while monitored pump shows reduced extraction ("water leakage"). | Adjoint source inversion identifies anomalous drawdown centroid; cluster-level community payment sharing ties village bonuses to collective cell-scale water table preservation. |
| **Rural Grid Connectivity & Power Outages** | Cellular connectivity drops for 2–3 weeks during heavy monsoon or rural tower outages. | Telemetry packets cannot reach central cloud backend in real time. | ESP32-S3 on-board flash circular ring buffer retains 30+ days of signed 1 Hz and burst records; automatically bulk-uploads with back-pressure throttling upon reconnection. |
| **Farmer Data Sovereignty & Trust** | Suspicion that telemetry will be used by state agencies to tax or restrict groundwater extraction. | Widespread farmer resistance or device disconnection. | **Core ethical commitment:** Data is farmer-owned; positive-only financial incentives (bonuses for avoided depletion); zero punitive tariffs; public outputs strictly aggregated to privacy-preserving cell scales ($\ge 1 \text{ km}^2$). |
