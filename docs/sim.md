# AquiPulse Simulator (`sim/`) Documentation

The `sim/` package is the physics-first synthetic district generator for benchmarking all AquiPulse algorithmic layers (L1–L5) against unambiguous ground truth.

---

## 1. Mathematical Models

### 1.1 Unconfined Aquifer Flow (2D Finite Volume)
The unconfined groundwater flow equation across a heterogeneous domain is solved in double precision (`float64`):

$$S_y(x, y) \frac{\partial h}{\partial t} = \nabla \cdot \left( T(h) \nabla h \right) + R(x, y, t) - \sum_{i} Q_i(t) \delta(x - x_i, y - y_i)$$

Where:
- $h(x, y, t)$: Hydraulic head above datum [m]
- $b(x, y)$: Bedrock elevation [m]
- $T(h) = K(x, y) \cdot \max(0.1, h - b)$: Transmissivity [$\text{m}^2/\text{s}$]
- $K(x, y) = 10^{\log_{10} K(x, y)}$: Hydraulic conductivity generated via 2D Gaussian Random Field (GRF) with Matérn-like power spectrum plus intersecting discrete fracture channels (5x to 25x permeability boost)
- $S_y(x, y)$: Spatially variable specific yield [fraction, 0.008 to 0.08]
- $R(x, y, t)$: Seasonal monsoon pulse recharge [$\text{m}/\text{s}$]
- $Q_i(t)$: Extraction rate at well $i$ [$\text{m}^3/\text{s}$]

Mass balance is strictly tracked at every sub-step and verified against total storage change down to machine precision ($< 10^{-12}$).

### 1.2 Near-Well Peaceman Singularity Correction
Because grid blocks represent cell-averaged heads $h_{\text{cell}}$, the dynamic water level inside the well casing $h_{\text{well}}$ experiences radial convergence:

$$s_{\text{laminar}} = \frac{Q_i}{2 \pi T_i} \ln\left(\frac{r_{\text{eq}}}{r_w}\right)$$

$$s_{\text{turbulent}} = C_{\text{well}} Q_i^2$$

$$\text{Dynamic Head } H_d(t) = (z_{\text{surf}} - h_{\text{cell}}) + s_{\text{laminar}} + s_{\text{turbulent}} + k_f Q_i^2 + H_{\text{out}}$$

### 1.3 Pump Affinity Laws and Induction Motor Slip
For shaft speed $\omega$ vs nominal rated speed $\omega_0$:

$$Q_{\text{ref}} = Q \cdot \frac{\omega_0}{\omega}, \quad H = \left(\frac{\omega}{\omega_0}\right)^2 f_H(Q_{\text{ref}}), \quad P_{\text{shaft}} = \left(\frac{\omega}{\omega_0}\right)^3 f_P(Q_{\text{ref}})$$

The induction motor slip responds to shaft torque and line voltage:

$$\text{slip} \approx \text{slip}_{\text{rated}} \cdot \left(\frac{P_{\text{shaft}}}{P_{\text{rated}}}\right) \cdot \left(\frac{V_{\text{rated}}}{V}\right)^2$$

$$\omega = \omega_{\text{sync}} \cdot (1 - \text{slip})$$

Operating points $(Q, H_d, P_{\text{shaft}}, P_{\text{el}})$ are solved iteratively by matching the pump $H(Q)$ curve with the dynamic system head curve $H_{\text{sys}}(Q)$.

---

## 2. Sensor & Hardware Emulation

1. **1 Hz Steady-State Telemetry**:
   - $V_{\text{RMS}}, I_{\text{RMS}}, \text{Power Factor } (\cos \phi), P_{\text{kW}}, \text{Frequency } (\text{Hz})$
   - Realistic sensor flaws: $\pm 1-2\%$ CT/ADC gain error, thermal offset, $1.5\%$ random packet drops, and oscillator clock drift (ppm).
   - Cryptographic signing: HMAC-SHA256 signature emulating on-board secure elements (e.g. ATECC608).

2. **4 kHz Start Burst (60 Seconds)**:
   - Captures high-frequency electrical inrush transient ($5-7\times I_{\text{rated}}$ decaying in 0.1-0.3s).
   - Captures hydraulic column fill transient: as water fills the riser pipe from static level $Z_s$, back-pressure rises, producing a diagnostic power ramp over duration $t_{\text{fill}} \approx \frac{V_{\text{pipe}}}{Q}$.

---

## 3. Adversary & Tamper Injections

- **CT-Open**: Simulates unlatched or cut CT clamp ($I_{\text{RMS}} = 0, P = 0$ while feeder voltage is energized).
- **Meter Bypass**: Simulates shunt tapping ($50\%$ current diverted around CT).
- **Replay Attack**: Malicious re-transmission of cached historical telemetry.
- **Ghost Wells**: Clandestine unmetered borewells operating nearby, producing unmonitored cones of depression.

---

## 4. CLI Usage

```bash
python -m sim.generate --wells 500 --seed 1 --days 2 --grid-size 20 --out-dir sim_data
```

Artifacts generated:
- `wells.json`: Registered well locations, pump families, farmer parameters.
- `ghost_wells.json`: Injected clandestine wells and extraction schedules.
- `telemetry_sample.json`: Edge sensor packets with signatures.
- `start_bursts.json`: Metadata and burst wave references.
- `aquifer_fields.npz`: Spatial ground-truth matrices ($K, S_y, b, z_{\text{surf}}, h$).
- `ground_truth_summary.json`: Volume totals and mass-balance relative error.
