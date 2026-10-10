# Team Contributions & Deliverables: AquiPulse

**Event:** [Environmental Hacks \| Bharat Builds Tour](https://www.wemakedevs.org/aws/env) (WeMakeDevs & AWS)  
**Track:** Track 02: Heat and Water  
**Project:** **AquiPulse — Fleet-Scale Groundwater Intelligence from the Electrical Heartbeat of Irrigation Pumps**  
**Repository:** [https://github.com/HirthikBalaji/AquiPulse](https://github.com/HirthikBalaji/AquiPulse)  

---

## 1. Team Leader's Contributions *(required)*

**Team Leader:** Hirthik Balaji  
**Role:** Lead System Architect, Differentiable Physics & AWS Cloud Engineer  

### Key Contributions & Technical Deliverables:
1. **Core Thesis & Physical Sensing Formulation:**
   * Conceptualized and formulated the core electro-mechanical state inversion thesis: turning 3-phase motor stator slip into volumetric water discharge $Q$ and isolating the 4 kHz startup power transient as water fills the empty riser pipe to measure physical static water table depth ($Z_s$) without downhole cables.
   * Solved the real-world 320V rural feeder voltage collapse and phase unbalance problem using hierarchical Bayesian partial pooling across pump manufacturer families (`phi/bayes_model.py` and `phi/infer.py`), achieving **1.32% volume MAPE** and **0.60 m static level RMSE**.

2. **AWS Cloud & Serverless Infrastructure:**
   * Architected and implemented the entire AWS serverless stack (`aws/iot_core.py`, `aws/lambda_handlers.py`, `aws/template.yaml`) deployed in `ap-south-1` (Mumbai).
   * Designed the AWS IoT Core ingestion pipeline streaming 1 Hz telemetry and 4 kHz bursts over mutual TLS MQTT, integrating IoT Topic Rules and Device Shadows for pump states.
   * Built 4 event-driven AWS Lambda microservices for real-time slip inference, burst transient extraction, nightly adjoint settlements, and Bedrock multilingual generation, operating 100% within the AWS Free Tier.

3. **Differentiable Hydro-Economic Twin & Adjoint Solver:**
   * Developed the 2D unconfined groundwater PDE in differentiable JAX float64 (`fat/jax_model.py`) and integrated Ensemble Smoother (ES-MDA) data assimilation.
   * Formulated and coded the analytical continuous adjoint PDE solver (`mep/adjoint.py`), replacing 45-minute finite difference runs with a single backward pass that computes marginal drawdown damage ($\lambda_i$) for 500 wells simultaneously in **180 milliseconds** (Spearman rank correlation $\rho = 1.000$).

4. **Amazon Bedrock Multilingual AI Agent:**
   * Integrated Amazon Bedrock (`aws/bedrock_agent.py`) using Claude 3.5 Sonnet and Titan to build the **AquiPulse Autonomous Groundwater Steward**.
   * Grounded the LLM in physical hydrogeological parameters and satellite NDVI crop-health guardrails to generate culturally authentic vernacular SMS and WhatsApp advisory cards in **Hindi, Punjabi, Gujarati, Telugu, Tamil, and English**.

5. **AWS Cedar Zero-Trust Governance & Immutable Ledger:**
   * Formulated declarative fine-grained access policies in AWS Cedar (`aws/policies.cedar`) and developed the evaluator (`aws/cedar_auth.py`) enforcing zero-trust boundaries across DISCOM operators, hydrologists, and farmers.
   * Designed the immutable WORM settlement ledger on **Amazon S3 with Object Lock** (`aws/s3_ledger.py`) for regulatory auditability.

6. **Testing, Benchmarking & LocalStack Portability:**
   * Built the master evaluation harness (`bench/run_benchmarks.py`) and authored the full 42-test pytest suite (`tests/test_aws.py` and unit tests).
   * Developed the offline **LocalStack** containerized environment (`docker-compose.aws.yml` and `aws/localstack_setup.sh`) allowing judges and developers to run the full AWS stack locally for **$0.00** without cloud credentials.

---

## 2. Individual Roles and Key Deliverables Completed by Team Member

### Option A: If Submitting as Solo Builder (Team of 1)
> *Note: Environmental Hacks permits teams of 1 to 4.*

* **Hirthik Balaji (Solo Builder / Team Leader):**
  * **Role:** Full-Stack & System Architect (Firmware, Applied Physics, Cloud Infrastructure & Machine Learning)
  * **Deliverables Completed:**
    * **Edge & Firmware:** ESP32-S3 C99 firmware specifications, split-core CT signal sampling, 4 kHz burst acquisition (`firmware/`).
    * **Hydrogeology & Physics Inversion:** 2D unconfined PDE in JAX, Cooper-Jacob opportunistic pumping tests, ES-MDA assimilation, and Adjoint marginal damage solver (`sim/`, `phi/`, `opt/`, `fat/`, `mep/`).
    * **AWS Cloud Engineering:** AWS IoT Core, AWS Lambda, Amazon Bedrock, Amazon S3 Object Lock, Amazon DynamoDB, AWS SAM IaC template (`aws/`).
    * **Security & Auditing:** AWS Cedar zero-trust engine, physics checks, satellite NDVI crop guardrail, and SHA-256 ledger (`ise/`).
    * **Web Console & API:** FastAPI REST backend, DISCOM grid command dashboard, interactive Bedrock multilingual advisory generator, and Cedar policy evaluator (`api/`, `web/`).
    * **Testing & Documentation:** 42/42 pytest tests, automated benchmark harness, AWS Builder Center article, 3-minute video recording script, and submission dossiers (`bench/`, `docs/`, `tests/`).

---

### Option B: If Submitting as a Multi-Member Team (2 to 4 Members)
*(Use this breakdown if participating with teammates by assigning the functional components below)*:

1. **Member 1: Team Leader / Lead Architect & Cloud Engineer (Hirthik Balaji)**
   * **Focus:** Overall system architecture, AWS Serverless stack (IoT Core, Lambda, SAM template), JAX differentiable adjoint solver, and benchmark evaluation harness.
   * **Key Deliverables:** `aws/template.yaml`, `aws/lambda_handlers.py`, `aws/iot_core.py`, `fat/`, `mep/adjoint.py`, `bench/run_benchmarks.py`.

2. **Member 2: Edge Firmware & Physical Sensing Engineer**
   * **Focus:** Embedded C99 firmware for Node G (ESP32-S3), split-core CT sensor acquisition, 4 kHz startup burst feature extraction, and HMAC-SHA256 hardware cryptographic signing.
   * **Key Deliverables:** `firmware/include/aquipulse_node.h`, `firmware/src/aquipulse_node.c`, `phi/burst_features.py`, `ise/physics_checks.py`.

3. **Member 3: AI & Security Engineer**
   * **Focus:** Amazon Bedrock multilingual vernacular advisory prompt engineering, Claude 3.5 Sonnet grounding, AWS Cedar zero-trust declarative policies (`aws/policies.cedar`), and S3 Object Lock ledger archiving.
   * **Key Deliverables:** `aws/bedrock_agent.py`, `aws/cedar_auth.py`, `aws/policies.cedar`, `aws/s3_ledger.py`, `ise/closure.py`.

4. **Member 4: Full-Stack Developer & Usability Specialist**
   * **Focus:** FastAPI REST service, interactive DISCOM Feeder Command Console, Farmer Lite View, LocalStack containerization, and developer documentation.
   * **Key Deliverables:** `api/service.py`, `web/index.html`, `docker-compose.aws.yml`, `aws/localstack_setup.sh`, `docs/`.
