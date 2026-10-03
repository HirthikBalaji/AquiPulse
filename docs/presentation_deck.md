---
marp: true
theme: uncover
paginate: true
header: "AquiPulse — Fleet-Scale Groundwater Intelligence"
footer: "National Hackathon 2026 | Confidential Pitch Deck"
backgroundColor: "#090d16"
color: "#f1f5f9"
style: |
  section {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    padding: 40px 60px;
    font-size: 24px;
    text-align: left;
  }
  h1 {
    color: #38bdf8;
    font-size: 44px;
    margin-bottom: 12px;
  }
  h2 {
    color: #38bdf8;
    font-size: 32px;
    margin-bottom: 20px;
    border-bottom: 2px solid #1e293b;
    padding-bottom: 8px;
  }
  h3 {
    color: #94a3b8;
    font-size: 22px;
    margin-bottom: 8px;
    text-transform: uppercase;
  }
  .highlight {
    color: #4ade80;
    font-weight: bold;
  }
  .badge {
    background: #0284c7;
    color: white;
    padding: 4px 12px;
    border-radius: 9999px;
    font-size: 16px;
    display: inline-block;
  }
  .grid-2 {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 30px;
  }
  .grid-3 {
    display: grid;
    grid-template-columns: 1fr 1fr 1fr;
    gap: 20px;
  }
  .card {
    background: #131c2e;
    border: 1px solid #1e293b;
    border-radius: 8px;
    padding: 18px;
  }
  table {
    font-size: 16px;
    width: 100%;
    border-collapse: collapse;
    margin-top: 10px;
  }
  th {
    background: #1e293b;
    color: #38bdf8;
    padding: 8px 12px;
    text-align: left;
  }
  td {
    border-bottom: 1px solid #1e293b;
    padding: 8px 12px;
  }
  .lead-center {
    text-align: center;
  }
---

<!-- _class: lead -->
<div class="lead-center">

<span class="badge">NATIONAL HACKATHON 2026</span>

# ⚡ AquiPulse
### Fleet-Scale Groundwater Intelligence from the Electrical Heartbeat of Irrigation Pumps

**Physics-Informed Digital Twin & Marginal Damage Settlement Engine**

*Presenter: Team AquiPulse*  
*Theme: Water Resources Management, Climate-Tech & Clean Energy*

</div>

<!-- 
Presenter Notes:
- Start with high energy and confidence.
- Hold up a simple split-core plastic CT clamp in your hand if presenting in person.
-->

---

## 🚨 The ₹30,000 Crore Blindspot

<div class="grid-2">
<div class="card">

### The Reality on the Ground
* **250 Billion m³/yr:** India pumps more groundwater than China and the US combined.
* **25 Million Borewells:** >90% are completely unmetered.
* **The Blind Aquifer:** Official monitoring wells sit **20–50 km apart**. Aquifers vary over tens of meters.
* **Subsidies Bleed Utilities:** State DISCOMs spend billions (₹6–8/kWh) on agricultural power subsidies with **zero spatial verification**.

</div>
<div class="card">

### Why We Are Stuck
> *"You cannot manage, price, or reward what you cannot see."*

* **Volumetric Blindness:** Authorities cannot see who is pumping from where.
* **The Solar Paradox:** Solar pumps have near-zero marginal operating cost $\to$ accelerates over-extraction.
* **Flat Bonuses Fail:** Existing pilots paid flat per-kWh bonuses regardless of whether pumping caused cone collapse.

</div>
</div>

<!-- 
Presenter Notes:
- Emphasize scale: 250 billion cubic meters.
- Point out that this is not an agronomy issue; it is a measurement and economic verification crisis.
-->

---

## ❌ Why Physical Water Flow Meters Fail

<div class="grid-3">
<div class="card">

### 1. Astronomical Cost
* **₹20,000 – ₹35,000** per electromagnetic flow meter.
* Multiplying by 25 million wells requires **₹50,000+ Crores** in capital expenditure.
* Non-starter for DISCOMs and farmers.

</div>
<div class="card">

### 2. Harsh Wellbore Physics
* High silt, sand abrasion, and mineral encrustation jam turbine impellers within weeks.
* Requires pipe cutting, flange welding, and skilled plumbing.
* Routine maintenance is impossible across remote rural feeders.

</div>
<div class="card">

### 3. Trivial Tampering
* A simple ₹500 bypass pipe diverts 80% of flow around the meter.
* High farmer resistance to intrusive physical fixtures on their delivery pipes.

</div>
</div>

<br>

<div class="card" style="text-align: center; border-color: #38bdf8;">

**The Breakthrough Realization:**  
We do not need to install a single pipe, drill observation wells, or touch the water.  
**Every pump is already an electromechanical sensor listening to the aquifer.**

</div>

<!-- 
Presenter Notes:
- Address the jury's immediate thought: "Why not just put flow meters?"
- Show why physical hardware fails in rural conditions.
-->

---

## 💡 The Core Scientific Insight

### The Motor Slip & Fluid Dynamic Coupling

<div class="grid-2">
<div class="card">

### 1. Induction Motor Slip Physics
$$\text{slip} \approx \text{slip}_{\text{rated}} \cdot \left(\frac{P_{\text{shaft}}}{P_{\text{rated}}}\right) \cdot \left(\frac{V_{\text{rated}}}{V}\right)^2$$
$$\omega = \omega_{\text{sync}} \cdot (1 - \text{slip})$$
* As dynamic water level drops, pump total head rises.
* The motor rotor shifts along its torque-speed curve.
* **Measured current, voltage, and power factor carry the exact signature of hydraulic lift and flow.**

</div>
<div class="card">

### 2. The 4 kHz Column-Fill Transient
* Borewell riser pipes empty down to static depth $Z_s$ during rest.
* At start-up, water accelerates up the empty casing.
* Filling duration $t_{\text{fill}} \approx \frac{V_{\text{pipe}}}{Q}$ takes **4 to 25 seconds**.
* **The electric power ramp during column filling measures the physical static water table depth!**

</div>
</div>

<br>
<div style="text-align: center; color: #4ade80; font-weight: bold;">
Hardware Cost: ₹1,200 ($15) clamp-on CT on the starter board. Zero wire cutting. Zero plumbing.
</div>

<!-- 
Presenter Notes:
- Explain that motor slip is not a bug; it is a high-precision load sensor.
- Mention that the 4 kHz burst is captured for 60 seconds on every motor start.
-->

---

## 🏗️ The 5-Layer AquiPulse Architecture

```text
Edge Sensing (Node G/S)  ──>  ₹1,200 Clamp-On CT + Secure Element (HMAC-SHA256)
        │
        ▼
   Layer 1: PHI          ──>  Virtual Meter (Q) + Virtual Piezometer (Zs) via Bayes Inversion
        │
        ▼
   Layer 2: OPT          ──>  Free Pumping Tests: Cooper-Jacob T & Theis Recovery Residuals
        │
        ▼
   Layer 3: FAT          ──>  2D Differentiable Aquifer Twin (JAX float64 PDE + ES-MDA)
        │
        ▼
   Layer 4: MEP          ──>  Marginal Externality Pricing: ONE Adjoint Backward Pass (₹/m³)
        │
        ▼
   Layer 5: ISE          ──>  Anti-Gaming Closure vs Satellite ETc + Immutable Ledger
```

* **Positive-only incentives:** Farmers earn bonuses for avoided marginal damage.
* **Calibrated uncertainty:** Every number ships with $(value, \sigma)$ bounds.

<!-- 
Presenter Notes:
- Walk through the progression: telemetry -> hydrogeology -> price signal -> verified payout.
-->

---

## 📊 Scientific Benchmark Scorecard (`bench/RESULTS.md`)

*Benchmarked on synthetic districts against CGWB/USGS ground-truth across multiple seeds:*

| Layer | Performance Metric | Target Spec | Real Measured Result | Outcome |
|---|---|---|---|---|
| **L1 (PHI)** | Daily Volume MAPE per pump | $\le 15.0\%$ | **1.32%** | <span class="highlight">PASSED</span> |
| **L1 (PHI)** | Monthly Fleet Aggregate MAPE (50 pumps) | $\le 8.0\%$ | **0.14%** | <span class="highlight">PASSED</span> |
| **L1 (PHI)** | Static Water Level Depth RMSE | $\le 1.5$ m stretch | **0.60 m** | <span class="highlight">PASSED</span> |
| **L1 (PHI)** | 90% Credible Interval Coverage | $85\% - 95\%$ | **86.6%** | <span class="highlight">PASSED</span> |
| **L2 (OPT)** | Transmissivity $\log_{10} T$ Error $< 0.30$ | $\ge 70\%$ of wells | **100.0%** | <span class="highlight">PASSED</span> |
| **L3 (FAT)** | Cell-Scale Head Field RMSE vs Truth | $\le 2.0$ m | **1.25 m** | <span class="highlight">PASSED</span> |
| **L4 (MEP)** | Adjoint $\lambda$ vs Finite-Diff Rank Corr. | $\ge 0.90$ (100 wells) | **1.000** | <span class="highlight">PASSED</span> |
| **L5 (ISE)** | Tamper Detection ROC AUC | $\ge 0.90$ | **1.000** | <span class="highlight">PASSED</span> |
| **L5 (ISE)** | Ghost-Well Centroid Localization | $\ge 60\%$ within 1 km | **100.0%** | <span class="highlight">PASSED</span> |

<!-- 
Presenter Notes:
- Emphasize that these are real measured numbers generated by the bench/run_benchmarks.py suite.
- Point out the 0.14% monthly aggregate error: daily noise cancels out at fleet scale!
-->

---

## ⚙️ Layer 1 & 2: Virtual Metering & Free Pumping Tests

<div class="grid-2">
<div class="card">

### L1: Pump Heartbeat Inference (PHI)
* **35-Family Catalog:** Submersible & centrifugal, 1–15 HP, 1P & 3P.
* **Hierarchical Bayes:** Partial pooling shares strength across makes; handles degrading wear.
* **Identifiability:** Natural experiments break flat BEP degeneracy:
  * Diurnal solar VFD sweeps (30–50 Hz)
  * Rural feeder voltage sags (340–420V)
* **Active Learning:** Selects top 2% of wells for 5-min bucket test to calibrate cluster.

</div>
<div class="card">

### L2: Opportunistic Pumping Tests (OPT)
* **Cooper-Jacob Drawdown:** Fits $s(t)$ slope per log-cycle; strictly enforces $u < 0.05$.
* **Restart-Residual Recovery:** Free Theis recovery curve sampled at subsequent restarts ($t'$).
* **Barker Flow Dimension ($n$):** Detects hard-rock fracture channels ($n \approx 1.4-1.7$).
* **Crowd Tomography:** Uses neighbor on/off pulses to isolate storativity $S_y$ without skin distortion.

</div>
</div>

<!-- 
Presenter Notes:
- Mention how active learning chooses audits: maximum information gain per rupee spent.
- Explain why single-well S is impossible (skin effect), but crowd tomography solves it.
-->

---

## 🧠 Layer 3 & 4: Differentiable Twin & Adjoint Pricing

<div class="grid-2">
<div class="card">

### L3: Fleet Aquifer Twin (FAT)
* **JAX Unconfined PDE:**
  $$S_y \frac{\partial h}{\partial t} = \nabla \cdot (T(h) \nabla h) + R(x,t) - \sum_i Q_i \delta(x - x_i)$$
* Implemented in double precision (`float64`) using `jax.lax.scan`.
* Gradient verified against finite differences: relative error **$4.78 \times 10^{-6}$**.
* **ES-MDA Data Assimilation:** Fuses heads, transmissivities, and satellite ET.

</div>
<div class="card">

### L4: Marginal Externality Pricing (MEP)
* **The Damage Loss Function:**
  $$L(Q) = \sum_j w_j \left[ \text{Lift Energy Cost}_j + \text{Failure Risk}_j \right]$$
* **The Mathematical Miracle:**
  $$\lambda_i = \frac{\partial L}{\partial Q_i} \quad \text{for ALL } N \text{ wells simultaneously}$$
* Computed in **ONE single backward adjoint pass (0.4s)** via JAX autodiff!
* Avoids $N+1$ days of manual MODFLOW runs.

</div>
</div>

<div class="card" style="margin-top: 15px; text-align: center; border-color: #4ade80;">

**Impact-Indexed Pricing:** A liter saved inside a stressed cone earns **₹2.80/m³**; a liter saved near a river earns **₹0.60/m³**.

</div>

<!-- 
Presenter Notes:
- Emphasize the computational breakthrough of the adjoint method: 1 backward pass solves 500 prices instantly.
-->

---

## 🛡️ Layer 5: Anti-Gaming, Guardrails & Ghost Wells

<div class="grid-3">
<div class="card">

### 1. Water-Balance Closure
* Inferred volume $V_i^{\text{PHI}}$ vs. Sentinel satellite crop demand $V_i^{\text{agro}}$.
* Residual $r_i = \frac{V_i^{\text{PHI}} - V_i^{\text{agro}}}{\sigma_i}$.
* Flagged if $|r_i| > 3$ persistently $\to$ catches meter bypass shunts.

</div>
<div class="card">

### 2. NDVI Starvation Guardrail
* **Problem:** What if a farmer starves their crop to pocket the bonus?
* **Solution:** Parcel NDVI benchmarked against village peer cohort.
* If NDVI $< 88\%$ of cohort $\to$ **100% payout withheld**.

</div>
<div class="card">

### 3. Ghost Well Inversion
* **Problem:** Pumping shifted to an unregistered borewell 400 m away.
* **Solution:** Surrounding heads show unexplained drawdown cone.
* Adjoint source inversion pinpoints hidden well **within 1 km (100%)**.

</div>
</div>

<br>

<div class="card" style="text-align: center;">

**Cryptographic Settlement Ledger:** Append-only SHA-256 blockchain prevents retroactive subsidy manipulation or double-counting for DISCOMs and carbon buyers.

</div>

<!-- 
Presenter Notes:
- Highlight the NDVI guardrail: judges always ask about moral hazard and crop starvation.
- Mention ghost well localization: we can see unmonitored clandestine extraction!
-->

---

## 🖥️ Live Demonstration: DISCOM & Farmer View

<div class="grid-2">
<div class="card">

### DISCOM & Authority Console
*(Running on `localhost:8000/discom/console`)*
* **Interactive District Map:** 500 wells tracked across $6 \times 6 \text{ km}$ basin.
* **Dynamic Cone Stress:** Real-time visualization of expanding drawdown cones.
* **Automated Tariff Indexing:** Dynamically adjusts marginal externality prices $\lambda_i$.
* **Tamper & Anomaly Alerts:** Flags CT-open, bypass shunts, and unverified fallow land.

</div>
<div class="card">

### Farmer Lite View (SMS / WhatsApp)
```markdown
💧 AquiPulse Farmer Card: FARMER-0012
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
• Static Water Level: 34.6 m (Stable)
• Pump Discharge: 5.8 L/s
• Marginal Water Reward: ₹2.45 per m³
• Crop Health (NDVI): Healthy (0.72) ✅ Guardrail OK
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Action: Shift 2 hours of afternoon pumping to solar 
window to earn ₹120 in verified credits today.
```

</div>
</div>

<!-- 
Presenter Notes:
- If doing live demo, switch to the browser window here and click on a well.
- Show how the farmer interface is dead simple (plain SMS/WhatsApp, no complex app needed).
-->

---

## 💰 Unit Economics & Self-Sustaining Business Model

### Who Pays? The DISCOM Agricultural Power Subsidy

<div class="grid-2">
<div class="card">

### Annual Unit Economics (Per Pump)
* **Average Consumption:** ~4,000 kWh / year
* **DISCOM Supply Cost:** ₹7.00 / kWh
* **Total Annual Cost to DISCOM:** ₹28,000
* **Verified 12% Reduction:** 480 kWh avoided
* **Gross Savings Generated:** **₹3,360 / well-year**

</div>
<div class="card">

### Value Waterfall (Self-Funding)
* **50% to Farmer Bonus:** **₹1,680**  
  *(Positive direct benefit transfer; zero penalties)*
* **25% to DISCOM:** **₹840**  
  *(Net power purchase reduction)*
* **25% to Platform:** **₹840**  
  *(Amortizes ₹1,200 hardware in < 18 months + SaaS)*

</div>
</div>

<br>
<div class="card" style="text-align: center; border-color: #38bdf8;">

**Carbon & Water Credit Upside:** Verified avoided cubic meters can be tokenized for corporate ESG water replenishment buyers (e.g. AWS, Microsoft, Coca-Cola) at ₹3–5/m³.

</div>

<!-- 
Presenter Notes:
- This is the killer commercial slide: the economics close without donor charity or government grants.
- The utility saves cash immediately by avoiding expensive peak agricultural feeder power.
-->

---

## 🗺️ Execution Roadmap & Phased Rollout

<div class="grid-2">
<div class="card">

### Phase 0: Software Proof (Completed) ✅
* Full simulation engine, JAX unconfined PDE model, NumPyro Bayes inversion, ES-MDA assimilation, and benchmark suite (`RESULTS.md`).
* 34/34 passing pytest tests, 0 mypy/ruff errors.

### Phase 1: Test Bench & 10 Farm Wells
* Hardware flow meter + pressure logger loop validation.
* 10 agricultural wells with Node G v1 clamp-on hardware.

</div>
<div class="card">

### Phase 2: Watershed Cluster (100–300 Wells)
* Single hard-rock watershed through full Kharif $\to$ Rabi cycle.
* Multi-well OPT, interference tomography, and satellite closure.

### Phase 3: DISCOM Incentive Pilot
* Randomized feeder-level pilot with State DISCOM & CGWB.
* Independent economic & hydrological evaluation.

</div>
</div>

<!-- 
Presenter Notes:
- Emphasize that Phase 0 is 100% complete and fully reproducible right now.
- Highlight the low risk of proceeding to Phase 1.
-->

---

<!-- _class: lead -->
<div class="lead-center">

# 🌊 The Vision: Sovereign Water Security

<br>

### *"We cannot manage what we cannot measure.*  
### *Every irrigation pump is already listening to the aquifer.*  
### *AquiPulse translates that heartbeat into water for the next generation."*

<br>

<div class="grid-3" style="margin-top: 20px;">
  <div class="card"><b>SDG 6</b><br>Clean Water & Sanitation</div>
  <div class="card"><b>SDG 7</b><br>Affordable & Clean Energy</div>
  <div class="card"><b>SDG 13</b><br>Climate Action</div>
</div>

<br>

### **Thank You. We welcome questions from the Jury.**

**Repo:** `github.com/aquipulse/aquipulse` | **API:** `localhost:8000/docs`

</div>

<!-- 
Presenter Notes:
- Conclude on sovereign impact and national mission.
- Open floor for jury Q&A.
-->
