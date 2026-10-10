# How We Used AWS in AquiPulse

**Event:** [Environmental Hacks \| Bharat Builds Tour](https://www.wemakedevs.org/aws/env) (WeMakeDevs & AWS)  
**Track:** Track 02: Heat and Water  
**Project:** **AquiPulse — Fleet-Scale Groundwater Intelligence from the Electrical Heartbeat of Irrigation Pumps**  
**Repository:** [https://github.com/HirthikBalaji/AquiPulse](https://github.com/HirthikBalaji/AquiPulse)  

---

## 1. Project Overview

**AquiPulse transforms the electrical heartbeat of ordinary agricultural borewell pumps into fleet-scale groundwater intelligence without touching a single drop of water.**

By installing an **$18 non-invasive clamp-on IoT node (Node G)** inside the pump starter panel, AquiPulse monitors 3-phase electrical slip at 1 Hz to provide **virtual water metering (1.32% volume error / MAPE)** and captures 4 kHz startup power transients as water fills the riser pipe to measure **physical static water table depth ($Z_s$) to within 0.60 meters** with zero downhole sensors. 

Telemetry feeds a 2D differentiable groundwater PDE digital twin in JAX. Using a single backward adjoint pass, AquiPulse calculates marginal hydraulic drawdown damage ($\lambda_i$) in milliseconds and settles verified cash bonuses (DBT) with farmers for avoiding pumping during peak aquifer stress, verified against satellite crop-health (NDVI) guardrails.

---

## 2. AWS Open Source Stack

AquiPulse leverages the AWS open-source ecosystem to enable zero-trust security and a 100% free, offline development and judging pathway:

### 1. AWS Cedar Policy Language & Engine
* **Files:** [`aws/policies.cedar`](../aws/policies.cedar) & [`aws/cedar_auth.py`](../aws/cedar_auth.py)
* **How It Is Used:** We use AWS Cedar for zero-trust declarative role-based and attribute-based access control (ABAC). We define strict policies governing our multi-stakeholder ecosystem:
  * **DISCOM Grid Operators** are permitted to view feeder telemetry, roster power, and trigger emergency shutdowns during acute cone-of-depression dewatering, but are *strictly forbidden* from modifying physical aquifer PDE boundaries.
  * **State Hydrologists** are permitted to calibrate transmissivity and run adjoint/ES-MDA PDE assimilation.
  * **Farmers** are permitted to view their own well state and claim earned conservation bonuses (`when { resource.owner == principal.id }`), but are *strictly forbidden* from manipulating grid power or pricing.
  * Evaluated in real-time with Cedar default-deny and forbid-overrides semantics.

### 2. LocalStack
* **Files:** [`docker-compose.aws.yml`](../docker-compose.aws.yml) & [`aws/localstack_setup.sh`](../aws/localstack_setup.sh)
* **How It Is Used:** Enables the **"Build It"** pathway of the hackathon. LocalStack provides complete local emulation of AWS IoT Core, AWS Lambda, Amazon S3, Amazon DynamoDB, and Amazon SNS. This allows students, hackathon judges, and evaluators to run, test, and verify the entire AWS architecture locally for **$0.00** without needing an AWS account or credit card.

### 3. AWS SAM CLI (Serverless Application Model)
* **File:** [`aws/template.yaml`](../aws/template.yaml)
* **How It Is Used:** Used for defining, linting, and validating our serverless architecture (`sam validate`, `sam build`). It packages IoT rules, Lambda functions, API Gateway HTTP APIs, DynamoDB tables, and S3 lifecycle configurations into standard AWS CloudFormation templates.

---

## 3. AWS Cloud Services

For the **"Ship It"** cloud deployment pathway, AquiPulse runs serverless in the **`ap-south-1` (Mumbai, India)** region within the **AWS Free Tier**:

### 1. AWS IoT Core
* **Implementation:** [`aws/iot_core.py`](../aws/iot_core.py)
* **How It Is Used:** Ingests streaming electrical telemetry from tens of thousands of agricultural Node G edge units over mutual TLS:
  * **1 Hz RMS Electrical Telemetry:** Published to `aquipulse/feeder/{feeder_id}/well/{pump_id}/telemetry`.
  * **4 kHz Startup Burst Transients:** Published to `aquipulse/feeder/{feeder_id}/well/{pump_id}/burst`.
  * **AWS IoT Topic Rules:** Decouple incoming edge streams and route payloads directly into Lambda and S3 without intermediary polling servers.
  * **AWS IoT Device Shadows:** Maintained at `$aws/things/{pump_id}/shadow/update` to track reported vs desired pump states, dynamic lift, and cone-of-depression stress status.

### 2. AWS Lambda
* **Implementation:** [`aws/lambda_handlers.py`](../aws/lambda_handlers.py)
* **How It Is Used:** Provides event-driven, zero-idle-cost compute during daytime rural load shedding:
  * `handler_heartbeat_ingest`: Triggered by IoT Topic Rules; verifies HMAC-SHA256 signatures, performs physics-informed motor slip state inversion to infer flow $Q$ in under 40 ms, and caches state in DynamoDB.
  * `handler_transient_burst`: S3-triggered serverless function parsing 4 kHz startup power curves to isolate static water table depth ($Z_s$).
  * `handler_settlement_cycle`: EventBridge-triggered batch solver executing the daily hydro-economic adjoint PDE and compiling farmer conservation bonuses.
  * `handler_bedrock_advisory`: API Gateway proxy invoking Bedrock foundation models for vernacular advisory generation.

### 3. Amazon Bedrock
* **Implementation:** [`aws/bedrock_agent.py`](../aws/bedrock_agent.py)
* **How It Is Used:** Acts as the **AquiPulse Autonomous Groundwater Steward & Multilingual Advisor**, leveraging `anthropic.claude-3-5-sonnet` and `amazon.titan-text-express-v1`:
  * **Vernacular Farmer Advisory:** Automatically translates complex hydraulic derivatives ($\partial J / \partial Q_i$) into culturally localized SMS and WhatsApp advisory cards in **Hindi (हिन्दी)**, **Punjabi (ਪੰਜਾਬੀ)**, **Gujarati (ગુજરાતી)**, **Telugu (తెలుగు)**, **Tamil (தமிழ்)**, and **English**. Advises farmers when to shift pumping to earn direct cash bonuses (DBT).
  * **DISCOM Hydrogeology Copilot:** Enables natural language querying for utility dispatchers (e.g., *"Which wells in Feeder AG-01 are creating acute cone-of-depression interference?"*).

### 4. Amazon S3
* **Implementation:** [`aws/s3_ledger.py`](../aws/s3_ledger.py)
* **How It Is Used:**
  * **S3 Object Lock & Versioning:** Enforces Write Once Read Many (WORM) compliance on SHA-256 chained settlement blocks (`ledger/blocks/`), creating an unalterable audit trail for government water conservation payouts.
  * **Transient Burst Storage:** Archives raw 4 kHz startup waveforms (`transients/`), with automated **S3 Lifecycle Rules** transitioning data to **Amazon S3 Glacier** after 30 days.

### 5. Amazon DynamoDB
* **Implementation:** [`aws/template.yaml`](../aws/template.yaml)
* **How It Is Used:** Pay-Per-Request (on-demand) NoSQL database (`AquiPulsePumpRegistry`) serving as the fast state cache for pump metadata, active learning bucket calibrations, and 1 Hz telemetry states with sub-6 ms latency and TTL expirations.

### 6. Amazon EventBridge
* **Implementation:** [`aws/template.yaml`](../aws/template.yaml)
* **How It Is Used:** Scheduled nightly cron (`cron(0 18 * * ? *)`, midnight IST) that triggers the distributed adjoint groundwater PDE solver across monitored agricultural feeders.

### 7. Amazon SNS (Simple Notification Service)
* **Implementation:** [`aws/template.yaml`](../aws/template.yaml)
* **How It Is Used:** Topic `AquiPulseAquiferAlerts` delivers instant push alerts to DISCOM engineers and affected farmers when rapid localized drawdown exceeds critical hydraulic cone-of-depression thresholds.

### 8. Amazon API Gateway (HTTP API v2)
* **Implementation:** [`aws/template.yaml`](../aws/template.yaml)
* **How It Is Used:** Low-latency HTTP endpoints exposing `/v1/advisory`, `/v1/status`, and telemetry endpoints to the web console and external utility systems.

---

## 4. Architectural Summary Table

| Category | Tool / Service Name | Role in AquiPulse |
|---|---|---|
| **AWS Open Source** | **AWS Cedar** | Zero-trust declarative authorization (ABAC) across DISCOM, Hydrologist, Panchayat, and Farmer roles |
| **AWS Open Source** | **LocalStack** | Offline local emulation of IoT, Lambda, S3, DynamoDB, SNS for $0.00 local testing |
| **AWS Open Source** | **AWS SAM CLI** | Serverless template definition, local invocation, and validation |
| **AWS Services** | **AWS IoT Core** | 1 Hz telemetry & 4 kHz burst MQTT streaming, Topic Rules, Device Shadows |
| **AWS Services** | **AWS Lambda** | Event-driven serverless state inversion, burst analysis, and adjoint settlements |
| **AWS Services** | **Amazon Bedrock** | Generative AI Multilingual Farmer Advisor (Hindi, Punjabi, Gujarati, etc.) & DISCOM Copilot |
| **AWS Services** | **Amazon S3** | S3 Object Lock immutable ledger & burst waveform archival with Glacier lifecycle |
| **AWS Services** | **Amazon DynamoDB** | Low-latency pump registry & instantaneous hydraulic state cache |
| **AWS Services** | **Amazon EventBridge** | Nightly scheduled cron orchestrating the watershed settlement cycle |
| **AWS Services** | **Amazon SNS** | Urgent alerts for acute cone-of-depression dewatering |
| **AWS Services** | **Amazon API Gateway** | HTTP API routing requests to serverless microservices |
