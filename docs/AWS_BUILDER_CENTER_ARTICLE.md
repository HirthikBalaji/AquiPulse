# AquiPulse: Listening to the Electrical Heartbeat of 30 Million Pumps to Save India's Aquifers on AWS

*Published for the AWS Bharat Builds Tour: Environmental Hacks (Track 02: Heat and Water)*  
*By Team AquiPulse*

---

## 1. The Invisible Crisis Under Our Feet

If you walk through the agricultural heartlands of Punjab, Haryana, or North Gujarat in May, the heat radiates off the baked soil like an oven. The paddy nurseries and cotton fields are lush green, fed by thousands of roaring submersible pumps. But beneath the surface, a slow-motion catastrophe is unfolding.

India pumps over **250 billion cubic meters of groundwater every year**—more than the United States and China combined. Over **30 million agricultural borewells** draw from unconfined and crystalline aquifers. Because agricultural power is provided at flat, heavily subsidized tariffs (₹0 to ₹1 per kWh), electricity has zero marginal cost at the point of use. A farmer has no financial incentive to flip the switch off once their field has had enough.

The obvious engineering reaction is: *"Why not just put flow meters on the pipes?"*

We learned the hard way why that fails:
1. **Physical meters cost ₹25,000 to ₹35,000 per well.** Metering 25 million tubewells would cost over ₹50,000 Crores ($6B USD).
2. **Rural groundwater is full of abrasive quartz sand, silt, and carbonate minerals.** Mechanical turbine impellers seize within weeks. Ultrasonic transducers de-laminate.
3. **Pipes are easily bypassed.** A ₹500 gate valve installed upstream diverts 80% of flow into irrigation furrows unmetered.
4. **State monitoring piezometers are spaced 20 to 50 km apart.** They are completely blind to steep, localized cones of depression (50 to 300 meters wide) that suck neighbor drinking wells dry in six hours.

We realized: **If you touch the water, you lose.** The only place we could reliably sit was inside the electrical pump starter panel.

---

## 2. The Core Idea: The Electrical Heartbeat of a Pump

Every pump is an electro-mechanical transducer. When an induction motor spins a submersible impeller 80 meters underground, the mechanical load on the shaft is directly dictated by fluid dynamics:

$$\text{Load} \propto \rho \cdot g \cdot Q \cdot H_{\text{dyn}}$$

As the dynamic water table drops, the pump has to push water higher against gravity. That extra lift causes the motor rotor to slow down relative to the 50 Hz stator magnetic field. This difference is **rotor slip**.

By measuring three-phase electrical telemetry (Voltage, Current, Power Factor, Frequency) at 1 Hz from non-invasive clamp-on current transformers (an **$18 edge node** called **Node G**), we can invert motor slip back into volumetric discharge $Q$ and dynamic lift $H_{\text{dyn}}$ without touching a single drop of water.

Even better: when an idle pump starts up, the riser pipe between the water table and the surface is initially empty. Over the first 4 to 25 seconds, the pump fills that vertical pipe before discharging at the surface. By capturing a **4 kHz burst of electrical active power during startup**, we measure the exact duration of the water column ascent. That duration gives us the **physical static water table depth ($Z_s$) to within 0.60 meters**—turning every ordinary farm pump into an autonomous piezometer with zero downhole wiring.

---

## 3. The Architecture on AWS

To scale this from one borewell to hundreds of thousands across a state power distribution utility (DISCOM), we built AquiPulse cloud-native on AWS, utilizing the **AWS Free Tier**:

```
[ Farm Borewell Starter Box ]
       │ (1 Hz Telemetry & 4 kHz Burst)
       ▼
 [ AWS IoT Core ] (MQTT over TLS with Topic Rules & Device Shadows)
       │
       ├──► [ AWS Lambda: Heartbeat Ingest ] ──► [ Amazon DynamoDB / Timestream ]
       │                                       └──► [ Amazon SNS: Cone Stress Alerts ]
       ├──► [ Amazon S3: Burst Waveforms ] ──► [ AWS Lambda: Transient Piezometer ]
       │
 [ Amazon EventBridge (Nightly Cron) ]
       │
       ▼
 [ AWS Lambda / Fargate: Differentiable JAX Aquifer Adjoint PDE ]
       │
       ├──► [ Amazon S3 Object Lock: Immutable SHA-256 Settlement Blocks ]
       └──► [ Amazon Bedrock: Claude 3.5 Sonnet / Titan ]
                   │
                   ▼
       [ Amazon API Gateway HTTP API ]
             ├──► Vernacular Farmer Advisory (SMS/WhatsApp in Hindi, Punjabi, Gujarati)
             └──► DISCOM Grid Command Console (Feeder Rostering & Subsidy Savings)
```

### Key AWS Building Blocks:
- **AWS IoT Core:** Handles bidirectional communication with tens of thousands of Node G devices across rural cellular and NB-IoT networks. IoT Topic Rules route 1 Hz electrical readings into Lambda and update Device Shadows with dynamic pumping lift and cone stress levels.
- **AWS Lambda:** Serverless computing means zero idle server cost during daytime agricultural load shedding. Lambda functions process electrical slip inversion in <40 ms per packet.
- **Amazon Bedrock (Claude 3.5 Sonnet & Titan):** Serves as our **Aquifer Generative Copilot**. It translates complex hydraulic derivatives ($\frac{\partial J}{\partial Q_i}$) into empathetic, actionable vernacular advisory cards for farmers in **Hindi, Punjabi, Gujarati, Telugu, Tamil, and English**.
- **Amazon S3 with Object Lock:** Financial groundwater conservation incentives require ironclad auditability. Settlement blocks are chained via SHA-256 and committed to S3 with WORM (Write Once Read Many) compliance to prevent regulatory tampering.
- **AWS Cedar Policy Language:** Provides fine-grained zero-trust authorization (`aws/policies.cedar`), ensuring DISCOM operators can roster power but cannot alter hydrological PDE boundaries, while farmers can claim bonuses for their own wells but cannot trigger feeder shutdowns.

---

## 4. What Fought Back: The Engineering Battles

Every hackathon project looks clean in an architectural diagram. Here is what fought back in reality—and how we solved it:

### Battle 1: Rural Feeder Voltage Collapses (The 320V Problem)
In laboratory pump curves, manufacturers assume clean 415V three-phase sinusoidal power. In rural India, when 40 farmers turn on 10 HP motors simultaneously at 6:00 AM, distribution lines sag down to **320V**, with up to **15% phase unbalance**.

Because induction motor slip is inversely proportional to $V^2$, a voltage drop looks mathematically identical to a massive increase in water lift! Our initial flow estimates were off by 40%.

**The Fix:** We decoupled electromagnetic stator loss from shaft mechanical power using a symmetrical component transformer model and Bayesian partial pooling across pump manufacturer families. Even under 320V sags, our measured volumetric error fell to **1.32% MAPE**.

### Battle 2: Noisy Harmonics in 4 kHz Startup Bursts
When a pump starts up on an agricultural line, contactor bounce and motor inrush current create severe high-frequency electrical hash. Isolating the exact millisecond when water crested the surface pipe head was drowning in electrical noise.

**The Fix:** We implemented a dual-derivative wavelet energy detector. Instead of looking at raw current, we track the rate of change of mechanical reactive torque ($d^2Q/dt^2$) as the impeller transitions from accelerating air in the pipe to accelerating dense water. This isolated static water table depth with **0.60 m RMSE**.

### Battle 3: Vanishing Gradients in the 2D PDE Adjoint Solver
To compute fair conservation bonuses, we needed the marginal social damage of each well ($\lambda_i = \partial J / \partial Q_i$). Finite difference methods ($N+1$ forward runs for $N$ wells) took 45 minutes on our cluster.

We wrote the 2D unconfined groundwater PDE in differentiable JAX. But when running reverse-mode automatic differentiation through 48 hourly time-steps, numerical diffusion in low-permeability granite cells caused gradients to either vanish or explode.

**The Fix:** We implemented an analytical continuous adjoint PDE solver integrated backward in time:
$$-S \frac{\partial \lambda}{\partial t} - \nabla \cdot (T \nabla \lambda) = \frac{\partial L}{\partial h}$$
A single backward pass evaluates marginal damage for all 500 wells simultaneously in **180 milliseconds**, matching finite differences with a relative error of $4.78 \times 10^{-6}$ (Spearman rank correlation $\rho = 1.000$).

### Battle 4: Preventing LLM Hallucinations in Farmer Advisory
When asking an LLM to generate vernacular farming advice, models love to offer generic poetry about water conservation. If an advisory hallucinated a bonus rate of ₹10/m³ instead of ₹2.14/m³, farmers would be misled.

**The Fix:** We grounded Amazon Bedrock with strict JSON structured output schemas containing explicit hydrogeological invariants: exact static depth, inferred flow, earned bonus calculation, and an NDVI crop-health guardrail check. If the farmer reduces pumping, we verify via Sentinel-2 NDVI that crop health is not compromised before disbursing the payout.

---

## 5. Quantitative Impact: What Actually Changes?

For a single standard 100-well agricultural feeder:
- **214,700 m³ of groundwater preserved per year (21.4 Crore litres preserved in the subsurface)** through a verified 14.2% reduction in pumping duration.
- **150 to 250 hectares of cropped land protected** from catastrophic cone-of-depression dewatering.
- **600 to 1,000 village families (3,000–5,000 residents)** secured against domestic handpump failure.
- **₹2,69,500 saved annually by the DISCOM** in avoided electricity subsidies (38,500 kWh saved).
- **₹1,34,750 distributed directly to farmers** as cash bonuses (DBT).
- **Payback period for the entire hardware and commissioning capex: 1.11 years (~13.3 months).**

---

## 6. Try It Yourself (Build It or Ship It)

We built AquiPulse so anyone—whether you have an AWS account with free credits or a student laptop with no credit card—can run and verify everything in 60 seconds:

```bash
# Clone the repository
git clone https://github.com/HirthikBalaji/AquiPulse.git
cd AquiPulse

# Install dependencies
uv sync

# Run the 42-test pytest suite
uv run pytest

# Launch the live interactive dashboard
uv run uvicorn api.service:app --host 0.0.0.0 --port 8000
```

Open `http://localhost:8000/discom/console` to see the live aquifer digital twin, trigger Bedrock vernacular cards in Hindi, Punjabi, and Gujarati, and test AWS Cedar policies in real-time.

*Built with ❤️ for the Bharat Builds Tour by WeMakeDevs and AWS.*
