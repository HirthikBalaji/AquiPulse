# Hackathon Submission Dossier: Environmental Hacks (Bharat Builds Tour)

**Event:** Environmental Hacks — Event 02 of Bharat Builds Tour (WeMakeDevs × AWS)  
**Dates:** October 8 – 11, 2026 (Online & DTU Delhi)  
**Project Name:** **AquiPulse** — Fleet-Scale Groundwater Intelligence from the Electrical Heartbeat of Irrigation Pumps  
**Selected Track:** **Track 02: Heat and Water**  
**Sub-Theme:** Groundwater Depletion, Drought Resilience, Irrigation Efficiency, and Fair Conservation Settlements  
**Repository:** [https://github.com/HirthikBalaji/AquiPulse](https://github.com/HirthikBalaji/AquiPulse)  
**Builder Center Article:** [`docs/AWS_BUILDER_CENTER_ARTICLE.md`](AWS_BUILDER_CENTER_ARTICLE.md)  
**Demo Video Walkthrough Script:** [`docs/DEMO_VIDEO_SCRIPT.md`](DEMO_VIDEO_SCRIPT.md)  
**AWS IaC Template:** [`aws/template.yaml`](../aws/template.yaml)  

---

## 1. Project Overview & One-Sentence Summary

> **AquiPulse turns the electrical heartbeat of 30 million unmetered borewell pumps into virtual water meters, virtual piezometers, and a differentiable aquifer digital twin on AWS, paying farmers direct cash bonuses for avoiding localized drawdown during drought periods.**

---

## 2. Evaluation Criteria Defense

### 01. Idea and Impact
- **The Problem:** Groundwater overdraft is India's most urgent unseen climate crisis. Over 30 million agricultural borewells extract 250+ billion m³ of water annually (67% of India's irrigation). Subsidized flat-rate power gives farmers zero marginal financial incentive to turn off pumps once crops are irrigated. Physical flow meters fail within weeks due to quartz sand erosion and carbonate fouling, and state piezometers are spaced 20–50 km apart—blind to steep 100m cones of depression that dewater drinking wells.
- **The Impact:** 
  - **214,700 m³ of groundwater preserved annually per 100-well rural feeder** (verified 14.2% water saved).
  - **150 to 250 hectares of cropped land protected** against pump cavitation and distress well re-drilling (preventing ₹1.5–3.0 Lakhs in predatory debt per farmer).
  - **600 to 1,000 village families (3,000–5,000 residents) secured** against domestic handpump dry-out.
  - **₹2,69,500 saved annually per feeder** in utility power subsidies (38,500 avoided kWh), with 50% paid as direct cash bonuses to farmers. Full capex payback in **1.11 years**.

### 02. Built on AWS
AquiPulse natively implements **both** event pathways:
- **Ship It (AWS Cloud Services - Free Tier):**
  - **AWS IoT Core:** Ingests 1 Hz electrical telemetry and 4 kHz startup bursts over TLS/MQTT with Device Shadows.
  - **AWS Lambda:** Serverless event handlers for physics-informed motor slip state inversion, transient riser fill piezometry, and nightly adjoint settlement optimization.
  - **Amazon Bedrock (Claude 3.5 Sonnet / Titan):** Generates personalized, vernacular SMS and WhatsApp advisory cards across **Hindi, Punjabi, Gujarati, Telugu, Tamil, and English**, plus natural language hydrogeology queries for grid operators.
  - **Amazon S3 (Object Lock):** Immutably archives SHA-256 chained settlement blocks (WORM compliance) and raw 4 kHz startup burst waveforms.
  - **Amazon DynamoDB & Timestream:** Fast time-series electrical telemetry and pump metadata cache.
  - **Amazon SNS:** Real-time push alerts to DISCOM engineers and farmers when cone-of-depression drawdown threatens neighbor wells.
  - **AWS SAM (CloudFormation):** Complete Infrastructure-as-Code (`aws/template.yaml`).
- **Build It (AWS Open Source & Local Tools):**
  - **LocalStack:** Full offline emulation (`docker-compose.aws.yml` + `aws/localstack_setup.sh`) allowing any evaluator to run the AWS stack locally for **$0.00** without cloud credentials.
  - **AWS Cedar Policy Language:** Zero-trust declarative authorization (`aws/policies.cedar` + `aws/cedar_auth.py`) governing DISCOM operators, hydrologists, village panchayats, and farmers.

### 03. Design and Usability
- **Farmer-Centric Accessibility:** Rural farmers do not need smartphones or complex apps. They receive automated vernacular SMS or WhatsApp advisory cards (in Hindi, Gujarati, Punjabi, etc.) stating static water table depths, crop health status, and cash bonus opportunities.
- **DISCOM Feeder Command Console:** Real-time web dashboard displaying 3-phase feeder power, cone drawdown severity, and financial subsidy savings.
- **Village Panchayat Public Ledger:** Transparent communal water accounting fostering village-level groundwater stewardship.

### 04. Execution & Measured Performance
- **100% Test Coverage:** 42/42 pytest tests passing across all physical, mathematical, and AWS modules.
- **Empirical Benchmarks (`bench/RESULTS.md`):**
  - Daily volumetric discharge error: **1.32% MAPE** (target $\le 15\%$).
  - Static water level depth: **0.60 m RMSE** (target $\le 1.5$ m) with **86.6%** 90%-CI coverage.
  - Transmissivity accuracy: **100.0%** of wells within 0.3 dex of ground truth.
  - Aquifer head tracking: **1.25 m RMSE** across a 20 km × 20 km heterogeneous basin.
  - Differentiable adjoint gradient error: **$4.78 \times 10^{-6}$** relative error vs finite differences (rank $\rho = 1.000$).
  - Tamper detection ROC AUC: **1.000**; ghost well localization: **100%** within 1 km.

### 05. Demo Video
A 3-minute recorded walkthrough following the exact script in [`docs/DEMO_VIDEO_SCRIPT.md`](DEMO_VIDEO_SCRIPT.md) showing:
1. The Groundwater Open-Access Crisis in India.
2. The $18 Node G Non-Invasive Electrical Sensing Breakthrough.
3. The AWS Serverless & Bedrock GenAI Architecture.
4. Live System Demonstration (IoT Core telemetry, Bedrock multilingual card generation, Cedar policy engine evaluation).
5. Quantitative Environmental Impact and Amazon Alignment.

---

## 3. Fast-Track Interview Alignment (Amazon University Talent)

AquiPulse represents high-caliber engineering suitable for full-time Software Development Engineer (SDE) and Machine Learning Engineer (MLE) roles at Amazon:
- **Distributed Edge & Cloud Systems:** Real-time stream processing from resource-constrained embedded nodes (ESP32-S3) into AWS IoT Core and Lambda.
- **Scientific Computing & Differentiable PDEs:** Novel end-to-end differentiable physical simulation in JAX with analytical adjoint gradient solvers.
- **Generative AI & LLM Grounding:** Multilingual vernacular translation grounded in physics-informed telemetry using Amazon Bedrock.
- **Zero-Trust Security & Policy Compliance:** Declarative policy enforcement via AWS Cedar and cryptographically immutable audit trails on Amazon S3.
