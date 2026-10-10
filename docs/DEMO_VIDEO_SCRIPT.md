# 3-Minute Hackathon Demo Video Script: AquiPulse

**Event:** Environmental Hacks — Bharat Builds Tour (WeMakeDevs & AWS)  
**Track:** Track 02: Heat and Water (Groundwater)  
**Total Target Duration:** Exactly 3 minutes (180 seconds)  
**Video Goal:** Demonstrate what it does, who it is for, where AWS fits, and the measured environmental impact.

---

## Visual & Audio Production Breakdown

```text
TIMELINE BREAKDOWN:
0:00 - 0:35 (35s) : Act 1 — The Environmental Crisis & Why Hardware Meters Fail
0:35 - 1:15 (40s) : Act 2 — The Innovation: Electrical Inversion & Differentiable Twin
1:15 - 2:05 (50s) : Act 3 — Built on AWS: IoT Core, Lambda, Bedrock & Cedar
2:05 - 2:40 (35s) : Act 4 — Live System Walkthrough & Vernacular Farmer Cards
2:40 - 3:00 (20s) : Act 5 — Real-World Impact & Bharat Builds Tour Closing
```

---

### Act 1: The Environmental Crisis (0:00 – 0:35 | 35 Seconds)

**Visuals On Screen:**
- Montage of rural Indian agricultural fields in Punjab / Gujarat, roaring borewell tubewells flooding furrows under hot sun.
- Infographic overlay: *"30 Million Unmetered Borewells | 250 Billion m³ Pumping/Year | Water Tables Falling 1–3 m/yr"*.
- Close-up photo/diagram of jammed physical flow meters clogged with abrasive quartz sand and calcium carbonate crust.

**Speaker (Clear, energetic, authoritative):**
> *"India is the largest consumer of groundwater on Earth, pumping 250 billion cubic meters every single year across 30 million agricultural borewells. Because agricultural power is heavily subsidized, farmers have zero financial incentive to turn off pumps once crops are irrigated.*
> 
> *Why not install water meters? Because mechanical meters cost ₹30,000 each, seize within weeks due to abrasive sand and scaling, and are trivially bypassed. Meanwhile, government piezometers are spaced 30 kilometers apart—completely blind to localized cones of depression that dry out village drinking wells.*
> 
> *Our thesis: If you touch the water, you lose. So we listen to the electrical heartbeat of the pump instead."*

---

### Act 2: The Core Innovation (0:35 – 1:15 | 40 Seconds)

**Visuals On Screen:**
- Technical animation showing an $18 DIN-rail clamp-on module (Node G) inside the pump starter panel.
- Dual-pane waveform view: 
  - Left: 1 Hz active power curve showing motor slip tracking dynamic water level ($H_{\text{dyn}}$).
  - Right: 4 kHz startup power burst showing the riser pipe filling duration ($Z_s$).
- 2D heatmap rendering of the JAX unconfined aquifer PDE showing cone-of-depression interference.

**Speaker:**
> *"Meet AquiPulse. An $18 non-invasive clamp-on node installed inside the pump starter control box. It touches no water, cuts no pipes, and requires zero downhole cables.*
> 
> *By measuring 3-phase electrical slip at 1 Hertz, AquiPulse acts as a virtual flow meter with 1.32% volume MAPE. When the motor starts up, it captures a 4-kilohertz transient burst as water accelerates up the empty riser pipe, extracting static water depth to within 0.60 meters.*
> 
> *Every farmer start and stop becomes an autonomous pumping test. We assimilate this fleet telemetry into a 2D differentiable groundwater PDE written in JAX. With one single backward adjoint pass, we calculate the exact marginal hydraulic damage of every well in the watershed in milliseconds."*

---

### Act 3: Built on AWS (1:15 – 2:05 | 50 Seconds)

**Visuals On Screen:**
- High-definition animated AWS Architecture Diagram highlighting:
  - AWS IoT Core (ap-south-1 Mumbai)
  - AWS Lambda (Serverless Ingest, Burst Piezometer & Nightly Adjoint)
  - Amazon Bedrock (Claude 3.5 Sonnet / Titan)
  - Amazon S3 Object Lock & DynamoDB
  - AWS Cedar Zero-Trust Authorization
- Quick terminal view running `uv run pytest` showing `42 passed in 12.08s`.

**Speaker:**
> *"Here is how AWS powers AquiPulse from edge to cloud, completely within the AWS Free Tier.*
> 
> *At the edge, Node G streams 1-Hertz telemetry to AWS IoT Core over mutual TLS. IoT Topic Rules route packets into event-driven AWS Lambda functions that invert motor slip in under 40 milliseconds, updating IoT Device Shadows and caching states in Amazon DynamoDB.*
> 
> *Startup burst waveforms stream into Amazon S3, triggering our transient piezometer Lambda.*
> 
> *Every night, Amazon EventBridge triggers the adjoint PDE solver. Verified water savings are committed to Amazon S3 with Object Lock for immutable regulatory audit trails.*
> 
> *To govern grid controls, we use AWS Cedar—providing declarative zero-trust policies that let utility engineers roster power while preventing unauthorized modifications to hydrological parameters.*
> 
> *And for developers without cloud credits, our LocalStack integration emulates the entire AWS stack locally for zero cost."*

---

### Act 4: Live System Walkthrough (2:05 – 2:40 | 35 Seconds)

**Visuals On Screen:**
- Screen capture of the live interactive AquiPulse Console (`http://localhost:8000/discom/console`):
  - Dashboard showing 500 active pump heartbeats, ₹26,950 utility savings, and cone stress tags.
  - Dropdown selector for languages: Hindi, Punjabi, Gujarati, Telugu, Tamil, English.
  - Live click on "Generate via Bedrock" showing instant vernacular card generation.
  - Live click on "Evaluate Policy" in the AWS Cedar tester showing `ALLOW` / `DENY` decisions.

**Speaker:**
> *"Let's see it live.*
> 
> *On the DISCOM console, grid dispatchers see real-time pumping flow, dynamic lift, and cone-of-depression stress across all agricultural feeders.*
> 
> *Farmers don't need a smartphone app. Using Amazon Bedrock, AquiPulse automatically generates personalized, culturally authentic SMS and WhatsApp advisory cards in Hindi, Punjabi, Gujarati, Telugu, Tamil, and English.*
> 
> *Here, Bedrock advises Farmer Rajesh in Hindi: 'Your water table is 34.8m. Shift 2 hours of afternoon pumping to the solar window to earn ₹80 in direct cash bonuses today, with NDVI crop health verified safe.'*
> 
> *And with our Cedar policy evaluator, access controls between DISCOM operators, hydrologists, and farmers are verified with mathematical zero-trust certainty."*

---

### Act 5: Impact & Amazon Alignment (2:40 – 3:00 | 20 Seconds)

**Visuals On Screen:**
- Summary impact infographic:
  - *"21.4 Crore Litres Preserved per Feeder / Year"*
  - *"150–250 Hectares Protected against Well Failure"*
  - *"₹2,69,500 Utility Subsidy Saved per Feeder"*
  - *"1.11-Year Capex Payback"*
- Closing screen: *"AquiPulse | Built for Bharat Builds Tour: Environmental Hacks | AWS ap-south-1"*.

**Speaker:**
> *"Across a standard 100-well rural feeder, AquiPulse preserves 21.4 Crore litres of groundwater every year, protects 200 hectares of cropland, safeguards village drinking water, and saves power utilities ₹2.7 Lakhs in subsidies—recouping all hardware capex in just 1.1 years.*
> 
> *AquiPulse transforms an unmanaged open-access commons into a transparent, fair, and sustainable aquifer digital twin. Ready to scale across Bharat with AWS.*
> 
> *Thank you!"*
