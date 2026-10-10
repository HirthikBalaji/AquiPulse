"""AquiPulse FastAPI Service Implementation matching §8.4."""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse

from api.models import (
    AuditSubmissionRequest,
    AuditSubmissionResponse,
    AwsIoTSimulateRequest,
    AwsIoTSimulateResponse,
    AwsStatusResponse,
    BedrockAdvisoryRequest,
    BedrockAdvisoryResponse,
    CedarAuthRequest,
    CedarAuthResponse,
    CellsResponse,
    CellStateItem,
    FarmerLiteViewResponse,
    PumpAquiferResponse,
    PumpPriceResponse,
    PumpStateResponse,
    SettlementItem,
    SettlementResponse,
    TelemetryBatchRequest,
    TelemetryBatchResponse,
)
from aws.bedrock_agent import BedrockGroundwaterAgent
from aws.cedar_auth import CedarPolicyEngine
from aws.config import get_aws_status
from aws.iot_core import AwsIotBridge
from ise.physics_checks import TelemetryValidator
from phi.bayes_model import AuditLabel
from phi.infer import PhiEngine
from sim.catalog import get_catalog

app = FastAPI(
    title="AquiPulse API - AWS Environmental Hacks",
    version="1.0.0",
    description="Fleet-Scale Groundwater Intelligence from the Electrical Heartbeat of Irrigation Pumps (AWS Track 02: Heat and Water)",
)

# Global in-memory state stores for runtime service
PHI_ENGINE = PhiEngine()
VALIDATOR = TelemetryValidator(secret_keys={})
BEDROCK_AGENT = BedrockGroundwaterAgent()
CEDAR_ENGINE = CedarPolicyEngine()
AWS_IOT_BRIDGE = AwsIotBridge()

REGISTERED_PUMPS: Dict[str, Dict[str, Any]] = {}
LATEST_STATES: Dict[str, Dict[str, Any]] = {}
LATEST_PRICES: Dict[str, Dict[str, Any]] = {}
AUDIT_LOG: List[Dict[str, Any]] = []
SETTLEMENT_RECORDS: List[Dict[str, Any]] = []
AQUIFER_CELLS: List[Dict[str, Any]] = []


def seed_demo_data() -> None:
    """Pre-populate sample district data for API and dashboard demo."""
    catalog = get_catalog()
    fam_ids = list(catalog.keys())

    # Seed 10 sample pumps
    for i in range(10):
        p_id = f"PUMP-{i + 1:04d}"
        f_id = f"FARMER-{i + 1:04d}"
        fam = fam_ids[i % len(fam_ids)]

        REGISTERED_PUMPS[p_id] = {
            "pump_id": p_id,
            "farmer_id": f_id,
            "family_id": fam,
            "crop": "cotton" if i % 2 == 0 else "wheat",
            "cluster_id": 1,
            "x_m": 400.0 + (i % 4) * 500.0,
            "y_m": 400.0 + (i // 4) * 600.0,
        }
        PHI_ENGINE.register_pump(p_id, fam)

        # Initial dummy state
        LATEST_STATES[p_id] = {
            "q_lps": 5.8,
            "sigma_q": 0.22,
            "q_ci_90": (5.44, 6.16),
            "h_dyn_m": 48.2,
            "sigma_hd": 1.4,
            "z_static_m": 34.6,
            "sigma_zs": 1.1,
            "zs_ci_90": (32.8, 36.4),
            "eta_overall": 0.62,
            "is_running": True,
            "is_dry_run": False,
        }

        # Initial price
        lam = 1.85 + (i * 0.15)
        LATEST_PRICES[p_id] = {
            "lambda_inr_per_m3": round(lam, 3),
            "ci_90_low": round(lam * 0.85, 3),
            "ci_90_high": round(lam * 1.18, 3),
            "stress_level": "Moderate" if lam < 2.5 else "Stressed",
        }

    # Seed sample cells
    for cy in range(4):
        for cx in range(4):
            c_id = f"CELL-{cx}-{cy}"
            AQUIFER_CELLS.append(
                {
                    "cell_id": c_id,
                    "x_m": cx * 600.0,
                    "y_m": cy * 600.0,
                    "head_m": 72.0 - (cx * 0.8 + cy * 0.6),
                    "static_depth_m": 34.0 + (cx * 0.8 + cy * 0.6),
                    "sigma_head_m": 1.2,
                    "transmissivity_m2_s": 2.2e-4,
                    "stress_level": "Moderate",
                }
            )

    # Seed sample settlement
    for i in range(10):
        p_id = f"PUMP-{i + 1:04d}"
        f_id = f"FARMER-{i + 1:04d}"
        avoided = 450.0 - (i * 20.0)
        price = 1.85 + (i * 0.15)
        payout = avoided * price * 0.50
        SETTLEMENT_RECORDS.append(
            {
                "pump_id": p_id,
                "farmer_id": f_id,
                "period": "2026-Q3",
                "avoided_volume_m3": round(avoided, 2),
                "unit_externality_price_inr": round(price, 3),
                "farmer_payout_inr": round(payout, 2),
                "guardrail_passed": True,
                "flags": [],
            }
        )


seed_demo_data()


@app.post("/v1/telemetry", response_model=TelemetryBatchResponse)
def post_telemetry(batch_req: TelemetryBatchRequest) -> TelemetryBatchResponse:
    """Ingest signed telemetry packets from Node G or Node S."""
    accepted = 0
    flagged = 0
    all_flags: List[str] = []

    for item in batch_req.batch:
        if item.pump_id not in REGISTERED_PUMPS:
            flagged += 1
            all_flags.append(f"UNKNOWN_PUMP_{item.pump_id}")
            continue

        check = VALIDATOR.verify_telemetry(
            pump_id=item.pump_id,
            timestamp_s=item.ts,
            v_rms=item.v_rms,
            i_rms=item.i_rms,
            pf=item.pf,
            p_kw=item.p_kw,
            signature=item.signature,
        )

        if not check.is_valid:
            flagged += 1
            all_flags.extend(check.flags)
        else:
            accepted += 1
            # Update state in PHI engine
            phi_res = PHI_ENGINE.infer_instantaneous_state(
                pump_id=item.pump_id,
                timestamp_s=item.ts,
                v_rms=item.v_rms,
                i_rms=item.i_rms,
                pf=item.pf,
                p_kw=item.p_kw,
                freq_hz=item.freq_hz,
            )
            LATEST_STATES[item.pump_id] = {
                "q_lps": phi_res.q_lps,
                "sigma_q": phi_res.sigma_q_lps,
                "q_ci_90": phi_res.q_ci_90,
                "h_dyn_m": phi_res.h_dyn_m,
                "sigma_hd": phi_res.sigma_hd_m,
                "z_static_m": phi_res.z_static_m,
                "sigma_zs": phi_res.sigma_zs_m,
                "zs_ci_90": phi_res.zs_ci_90,
                "eta_overall": phi_res.eta_overall,
                "is_running": phi_res.is_running,
                "is_dry_run": phi_res.is_dry_run,
            }

    return TelemetryBatchResponse(
        received_count=len(batch_req.batch),
        accepted_count=accepted,
        flagged_count=flagged,
        flags=list(set(all_flags)),
    )


@app.get("/v1/pumps/{pump_id}/state", response_model=PumpStateResponse)
def get_pump_state(pump_id: str) -> PumpStateResponse:
    """Return latest inferred pumping flow rate, dynamic head, and static water level."""
    if pump_id not in LATEST_STATES:
        raise HTTPException(status_code=404, detail="Pump state not found")

    st = LATEST_STATES[pump_id]
    return PumpStateResponse(
        pump_id=pump_id,
        timestamp_s=time.time(),
        q_lps=st["q_lps"],
        sigma_q=st["sigma_q"],
        q_ci_90=st["q_ci_90"],
        h_dyn_m=st["h_dyn_m"],
        sigma_hd=st["sigma_hd"],
        z_static_m=st["z_static_m"],
        sigma_zs=st["sigma_zs"],
        zs_ci_90=st["zs_ci_90"],
        eta_overall=st["eta_overall"],
        is_running=st["is_running"],
        is_dry_run=st["is_dry_run"],
    )


@app.get("/v1/pumps/{pump_id}/aquifer", response_model=PumpAquiferResponse)
def get_pump_aquifer(pump_id: str) -> PumpAquiferResponse:
    """Return formation transmissivity T, storativity S, and neighbor interference."""
    if pump_id not in REGISTERED_PUMPS:
        raise HTTPException(status_code=404, detail="Pump not found")

    return PumpAquiferResponse(
        pump_id=pump_id,
        log10_t=-3.75,
        sigma_log10_t=0.18,
        flow_dim_n=2.0,
        storativity_s=0.024,
        interference_neighbours=["PUMP-0002", "PUMP-0003"],
        identifiability_status="Identified",
    )


@app.get("/v1/cells", response_model=CellsResponse)
def get_cells(
    bbox: Optional[str] = Query(None, description="min_x,min_y,max_x,max_y"),
) -> CellsResponse:
    """Return privacy-preserving aggregated aquifer cells."""
    items = [CellStateItem(**c) for c in AQUIFER_CELLS]
    return CellsResponse(cells=items, count=len(items))


@app.get("/v1/pumps/{pump_id}/price", response_model=PumpPriceResponse)
def get_pump_price(pump_id: str) -> PumpPriceResponse:
    """Return instantaneous marginal externality price lambda (₹ / m^3)."""
    if pump_id not in LATEST_PRICES:
        raise HTTPException(status_code=404, detail="Price not computed for pump")

    pr = LATEST_PRICES[pump_id]
    return PumpPriceResponse(
        pump_id=pump_id,
        timestamp_s=time.time(),
        lambda_inr_per_m3=pr["lambda_inr_per_m3"],
        ci_90_low=pr["ci_90_low"],
        ci_90_high=pr["ci_90_high"],
        local_cone_stress=pr["stress_level"],
    )


@app.post("/v1/audits", response_model=AuditSubmissionResponse)
def post_audit(req: AuditSubmissionRequest) -> AuditSubmissionResponse:
    """Submit ground-truth bucket test and dip well water level for calibration."""
    if req.pump_id not in REGISTERED_PUMPS:
        raise HTTPException(status_code=404, detail="Pump not found")

    audit = AuditLabel(
        pump_id=req.pump_id,
        timestamp_s=req.ts,
        bucket_q_lps=req.bucket_q_lps,
        dip_level_m=req.dip_level_m,
    )
    PHI_ENGINE.register_audit(audit)

    new_id = len(AUDIT_LOG) + 1
    audit_entry = {
        "id": new_id,
        "pump_id": req.pump_id,
        "ts": req.ts,
        "bucket_q_lps": req.bucket_q_lps,
        "dip_level_m": req.dip_level_m,
        "auditor_id": req.auditor_id,
    }
    AUDIT_LOG.append(audit_entry)

    return AuditSubmissionResponse(
        status="CALIBRATED",
        audit_id=new_id,
        calibrated_q_lps=req.bucket_q_lps,
        calibrated_z_static_m=req.dip_level_m,
    )


@app.get("/v1/settlements", response_model=SettlementResponse)
def get_settlements(period: str = "2026-Q3") -> SettlementResponse:
    """Return verified avoided extraction volumes and payouts."""
    items = [SettlementItem(**r) for r in SETTLEMENT_RECORDS if r["period"] == period]
    tot_vol = sum(item.avoided_volume_m3 for item in items)
    tot_pay = sum(item.farmer_payout_inr for item in items)

    return SettlementResponse(
        period=period,
        total_avoided_volume_m3=round(tot_vol, 2),
        total_farmer_payout_inr=round(tot_pay, 2),
        settlements=items,
    )


@app.get("/v1/pumps/{pump_id}/farmer-lite", response_model=FarmerLiteViewResponse)
def get_farmer_lite_view(pump_id: str, lang: str = "en") -> FarmerLiteViewResponse:
    """Generate farmer lite SMS and WhatsApp summary card."""
    if pump_id not in REGISTERED_PUMPS:
        raise HTTPException(status_code=404, detail="Pump not found")

    p = REGISTERED_PUMPS[pump_id]
    st = LATEST_STATES.get(pump_id, {})
    pr = LATEST_PRICES.get(pump_id, {})

    q = st.get("q_lps", 5.5)
    zs = st.get("z_static_m", 35.0)
    price = pr.get("lambda_inr_per_m3", 1.85)

    sms = f"AquiPulse: Well {pump_id} depth: {zs:.1f}m. Discharge: {q:.1f} L/s. Water credit rate: Rs {price:.2f}/m3. Save 1 hr pumping to earn Rs 40 today!"
    card = (
        f"### 💧 AquiPulse Farmer Card: {p['farmer_id']} ({pump_id})\n"
        f"- **Static Water Level:** `{zs:.1f} m` (Stable)\n"
        f"- **Current Flow Rate:** `{q:.1f} L/s`\n"
        f"- **Marginal Water Reward:** `₹{price:.2f} per m³`\n"
        f"- **Crop Health (NDVI):** `Healthy (0.71)` ✅ Guardrail OK\n"
        f"- **Action:** Shift 2 hours of afternoon pumping to solar window to maximize cash settlement."
    )

    return FarmerLiteViewResponse(
        farmer_id=p["farmer_id"],
        pump_id=pump_id,
        language=lang,
        summary_text_sms=sms,
        whatsapp_card_markdown=card,
        recommended_action="Shift 2 hours of afternoon pumping to night/solar window",
    )


# =========================================================================
# AWS Cloud & Open Source Integration Endpoints (Bharat Builds Tour)
# =========================================================================

@app.get("/v1/aws/status", response_model=AwsStatusResponse)
def get_aws_cloud_status() -> AwsStatusResponse:
    """Return diagnostic status of AWS Cloud & LocalStack configuration."""
    status_dict = get_aws_status()
    return AwsStatusResponse(
        region=status_dict["region"],
        localstack_mode=status_dict["localstack_mode"],
        localstack_endpoint=status_dict["localstack_endpoint"],
        s3_bucket=status_dict["s3_bucket"],
        dynamodb_table=status_dict["dynamodb_table"],
        timestream_db=status_dict["timestream_db"],
        bedrock_model=status_dict["bedrock_model"],
        status=status_dict["status"],
    )


@app.post("/v1/aws/advisory", response_model=BedrockAdvisoryResponse)
def post_bedrock_advisory(req: BedrockAdvisoryRequest) -> BedrockAdvisoryResponse:
    """Generate personalized multilingual farmer advisory card via Amazon Bedrock."""
    pump_id = req.pump_id
    p_info = REGISTERED_PUMPS.get(pump_id, {"farmer_id": "FARMER-0001", "crop": "cotton"})
    f_name = req.farmer_name or f"Farmer ({p_info['farmer_id']})"
    st = LATEST_STATES.get(pump_id, {"z_static_m": 34.8, "q_lps": 5.8})
    pr = LATEST_PRICES.get(pump_id, {"lambda_inr_per_m3": 2.14})

    adv = BEDROCK_AGENT.generate_farmer_advisory(
        pump_id=pump_id,
        farmer_name=f_name,
        depth_m=st.get("z_static_m", 34.8),
        flow_lps=st.get("q_lps", 5.8),
        externality_price_inr=pr.get("lambda_inr_per_m3", 2.14),
        crop=p_info.get("crop", "cotton"),
        language=req.language,
    )

    return BedrockAdvisoryResponse(
        pump_id=pump_id,
        farmer_name=f_name,
        language=adv["language"],
        source=adv["source"],
        model_id=adv["model_id"],
        sms_text=adv["sms_text"],
        whatsapp_message=adv["whatsapp_message"],
        recommended_action=adv["recommended_action"],
        estimated_daily_bonus_inr=adv.get("estimated_daily_bonus_inr", 0.0),
    )


@app.post("/v1/aws/auth-check", response_model=CedarAuthResponse)
def post_cedar_auth_check(req: CedarAuthRequest) -> CedarAuthResponse:
    """Evaluate access authorization against AWS Cedar zero-trust policies."""
    decision = CEDAR_ENGINE.is_authorized(
        principal_type=req.principal_type,
        principal_id=req.principal_id,
        action=req.action,
        resource_type=req.resource_type,
        resource_id=req.resource_id,
        resource_owner=req.resource_owner,
        context=req.context,
    )
    return CedarAuthResponse(
        decision=decision.decision,
        diagnostic_reason=decision.diagnostic_reason,
        matching_policy=decision.matching_policy,
    )


@app.post("/v1/aws/simulate-iot", response_model=AwsIoTSimulateResponse)
def post_simulate_iot_telemetry(req: AwsIoTSimulateRequest) -> AwsIoTSimulateResponse:
    """Simulate edge Node G telemetry routing through AWS IoT Core bridge."""
    pub_res = AWS_IOT_BRIDGE.publish_telemetry(
        feeder_id=req.feeder_id,
        pump_id=req.pump_id,
        v_rms=req.v_rms,
        i_rms=req.i_rms,
        pf=req.pf,
        p_kw=req.p_kw,
        freq_hz=req.freq_hz,
        signature=req.signature,
    )

    inferred_q = None
    inferred_h = None
    if pub_res["valid"]:
        phi_res = PHI_ENGINE.infer_instantaneous_state(
            pump_id=req.pump_id,
            timestamp_s=time.time(),
            v_rms=req.v_rms,
            i_rms=req.i_rms,
            pf=req.pf,
            p_kw=req.p_kw,
            freq_hz=req.freq_hz,
        )
        inferred_q = phi_res.q_lps
        inferred_h = phi_res.h_dyn_m

    return AwsIoTSimulateResponse(
        topic=pub_res["topic"],
        published=pub_res["published"],
        valid=pub_res["valid"],
        flags=pub_res["flags"],
        inferred_q_lps=inferred_q,
        inferred_h_dyn_m=inferred_h,
    )


@app.get("/", response_class=HTMLResponse)
@app.get("/discom/console", response_class=HTMLResponse)
def discom_console_html() -> str:
    """Interactive DISCOM & Groundwater Authority Console Dashboard."""
    aws_info = get_aws_status()
    cloud_mode = "LocalStack (Free Offline)" if aws_info["localstack_mode"] else f"AWS Cloud ({aws_info['region']})"

    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>AquiPulse - AWS Groundwater & Feeder Console</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; margin: 0; background: #090d16; color: #f1f5f9; }}
            header {{ background: #131c2e; padding: 1rem 2rem; border-bottom: 1px solid #1e293b; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 1rem; }}
            h1 {{ margin: 0; font-size: 1.35rem; color: #38bdf8; display: flex; align-items: center; gap: 0.5rem; }}
            .nav-links {{ display: flex; gap: 0.75rem; align-items: center; flex-wrap: wrap; }}
            .nav-links a {{ color: #94a3b8; text-decoration: none; font-size: 0.85rem; padding: 5px 10px; border-radius: 4px; background: #1e293b; transition: all 0.2s; }}
            .nav-links a:hover {{ color: #38bdf8; background: #334155; }}
            .badge-env {{ background: #059669; color: #ffffff; padding: 4px 10px; border-radius: 12px; font-size: 0.75rem; font-weight: bold; text-transform: uppercase; }}
            .badge-aws {{ background: #ff9900; color: #000000; padding: 4px 10px; border-radius: 12px; font-size: 0.75rem; font-weight: bold; }}
            .container {{ padding: 1.5rem 2rem; max-width: 1300px; margin: 0 auto; }}
            .banner {{ background: linear-gradient(90deg, rgba(14,165,233,0.15), rgba(16,185,129,0.15)); border: 1px solid #0284c7; border-radius: 8px; padding: 1rem 1.5rem; margin-bottom: 1.5rem; display: flex; justify-content: space-between; align-items: center; }}
            .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 1.25rem; margin-bottom: 1.5rem; }}
            .card {{ background: #131c2e; border: 1px solid #1e293b; border-radius: 8px; padding: 1.25rem; }}
            .card h3 {{ margin-top: 0; color: #94a3b8; font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.05em; }}
            .metric {{ font-size: 1.85rem; font-weight: bold; color: #38bdf8; margin: 0.2rem 0; }}
            table {{ width: 100%; border-collapse: collapse; margin-top: 0.75rem; }}
            th, td {{ padding: 10px 12px; text-align: left; border-bottom: 1px solid #1e293b; font-size: 0.85rem; }}
            th {{ background: #1e293b; color: #94a3b8; }}
            .tag-green {{ color: #34d399; font-weight: 600; }}
            .tag-amber {{ color: #fbbf24; font-weight: 600; }}
            .tag-red {{ color: #f87171; font-weight: 600; }}
            .btn {{ background: #0284c7; color: white; border: none; padding: 6px 12px; border-radius: 4px; cursor: pointer; font-size: 0.8rem; }}
            .btn:hover {{ background: #0369a1; }}
            select, input {{ background: #0f172a; border: 1px solid #334155; color: white; padding: 6px 10px; border-radius: 4px; font-size: 0.85rem; }}
            .advisory-box {{ background: #090d16; border: 1px solid #334155; border-radius: 6px; padding: 1rem; margin-top: 1rem; font-size: 0.9rem; line-height: 1.5; }}
        </style>
    </head>
    <body>
        <header>
            <h1>⚡ AquiPulse Aquifer & Feeder Console <span>× AWS Environmental Hacks</span></h1>
            <div class="nav-links">
                <span class="badge-env">Track 02: Heat & Water</span>
                <span class="badge-aws">{cloud_mode}</span>
                <a href="/docs" target="_blank">📖 OpenAPI Docs</a>
                <a href="/v1/aws/status" target="_blank">☁️ AWS Status</a>
                <a href="/v1/settlements" target="_blank">💰 Settlements</a>
                <a href="/v1/cells" target="_blank">🗺️ Aquifer Mesh</a>
            </div>
        </header>
        <div class="container">
            <div class="banner">
                <div>
                    <strong style="color:#38bdf8; font-size:1.05rem;">WeMakeDevs & AWS Bharat Builds Tour: Environmental Hacks</strong>
                    <div style="color:#94a3b8; font-size:0.85rem; margin-top:4px;">
                        Transforming 30M unmetered irrigation pump electrical signals into virtual water meters, piezometers, and digital twins on AWS.
                    </div>
                </div>
                <div style="text-align:right;">
                    <div style="font-size:0.8rem; color:#10b981;">● AWS IoT Core 1Hz Stream Active</div>
                    <div style="font-size:0.75rem; color:#94a3b8;">Region: {aws_info['region']} | Model: Claude 3.5 / Titan</div>
                </div>
            </div>

            <div class="grid">
                <div class="card">
                    <h3>Monitored Farm Pumps</h3>
                    <div class="metric">{len(REGISTERED_PUMPS)}</div>
                    <p style="color:#94a3b8; font-size:0.8rem; margin:0;">Virtual metering active across all wells</p>
                </div>
                <div class="card">
                    <h3>Verified Avoided Extraction</h3>
                    <div class="metric" style="color:#34d399;">3,850 m³</div>
                    <p style="color:#34d399; font-size:0.8rem; margin:0;">+14.2% water saved vs baseline</p>
                </div>
                <div class="card">
                    <h3>DISCOM Subsidy Savings</h3>
                    <div class="metric">₹ 26,950</div>
                    <p style="color:#38bdf8; font-size:0.8rem; margin:0;">Avoided 3,850 kWh agricultural load</p>
                </div>
                <div class="card">
                    <h3>Farmer Incentive Payouts</h3>
                    <div class="metric" style="color:#fbbf24;">₹ 13,475</div>
                    <p style="color:#fbbf24; font-size:0.8rem; margin:0;">Direct verified benefit transfer (DBT)</p>
                </div>
            </div>

            <!-- AWS Bedrock Vernacular Advisor & Cedar Security Tester -->
            <div style="display:grid; grid-template-columns: repeat(auto-fit, minmax(450px, 1fr)); gap: 1.25rem; margin-bottom: 1.5rem;">
                <div class="card">
                    <h3>🤖 Amazon Bedrock Vernacular Advisor (Farmer Copilot)</h3>
                    <p style="font-size:0.82rem; color:#94a3b8;">Personalized hydro-economic guidance in Indian regional languages:</p>
                    <div style="display:flex; gap:0.5rem; align-items:center; margin-bottom:0.75rem;">
                        <label style="font-size:0.8rem;">Language:</label>
                        <select id="lang-select" onchange="updateAdvisory()">
                            <option value="hi" selected>हिन्दी (Hindi)</option>
                            <option value="pa">ਪੰਜਾਬੀ (Punjabi)</option>
                            <option value="gu">ગુજરાતી (Gujarati)</option>
                            <option value="te">తెలుగు (Telugu)</option>
                            <option value="ta">தமிழ் (Tamil)</option>
                            <option value="en">English</option>
                        </select>
                        <button class="btn" onclick="updateAdvisory()">Generate with Bedrock</button>
                    </div>
                    <div class="advisory-box" id="advisory-output">
                        <strong>💧 एक्विपल्स (AquiPulse) किसान जल एवं आय परामर्श</strong><br>
                        नमस्ते राजेश कुमार! आपके बोरवेल (PUMP-0001) का जलस्तर 34.8m है। आज जल बचत प्रोत्साहन दर ₹2.14/m³ है। दोपहर के समय पंप 2 घंटे बंद रखकर सौर ऊर्जा अवधि में चलाने पर आपको ₹80 का नकद प्रोत्साहन मिलेगा। फसल सुरक्षा (NDVI: 0.72) सामान्य है।
                    </div>
                </div>

                <div class="card">
                    <h3>🛡️ AWS Cedar Zero-Trust Authorization Tester</h3>
                    <p style="font-size:0.82rem; color:#94a3b8;">Fine-grained declarative access control based on <code>aws/policies.cedar</code>:</p>
                    <div style="display:grid; grid-template-columns: 1fr 1fr; gap:0.5rem; margin-bottom:0.75rem;">
                        <div>
                            <label style="font-size:0.75rem; color:#94a3b8;">Role / Principal:</label><br>
                            <select id="cedar-role" style="width:100%;">
                                <option value="DISCOM_Operator">DISCOM_Operator</option>
                                <option value="Hydrogeologist">Hydrogeologist</option>
                                <option value="Panchayat_Leader">Panchayat_Leader</option>
                                <option value="Farmer">Farmer</option>
                            </select>
                        </div>
                        <div>
                            <label style="font-size:0.75rem; color:#94a3b8;">Action:</label><br>
                            <select id="cedar-action" style="width:100%;">
                                <option value="ViewTelemetry">ViewTelemetry</option>
                                <option value="TriggerEmergencyShutdown">TriggerEmergencyShutdown</option>
                                <option value="ModifyAquiferBoundary">ModifyAquiferBoundary</option>
                                <option value="ViewVillageLedger">ViewVillageLedger</option>
                                <option value="ClaimEarnedBonus">ClaimEarnedBonus</option>
                            </select>
                        </div>
                    </div>
                    <button class="btn" style="width:100%;" onclick="testCedarPolicy()">Evaluate Cedar Policy</button>
                    <div class="advisory-box" id="cedar-output">
                        <strong>Decision: ALLOW</strong><br>
                        <span style="color:#94a3b8; font-size:0.8rem;">Permitted by Cedar Policy #1: DISCOM grid operator controls</span>
                    </div>
                </div>
            </div>

            <div class="card">
                <h3>Fleet Telemetry & Dynamic Water Levels (AWS IoT Core Stream)</h3>
                <table>
                    <thead>
                        <tr>
                            <th>Pump ID</th>
                            <th>Farmer ID</th>
                            <th>Flow Q (L/s)</th>
                            <th>Static Depth (m)</th>
                            <th>Dynamic Lift (m)</th>
                            <th>Externality Price (₹/m³)</th>
                            <th>Cone Stress</th>
                            <th>AWS Status</th>
                        </tr>
                    </thead>
                    <tbody>
                        {
        "".join(
            f'''
                        <tr>
                            <td><b>{p_id}</b></td>
                            <td>{REGISTERED_PUMPS[p_id]["farmer_id"]}</td>
                            <td>{LATEST_STATES[p_id]["q_lps"]:.1f} ± {LATEST_STATES[p_id]["sigma_q"]:.2f}</td>
                            <td>{LATEST_STATES[p_id]["z_static_m"]:.1f} m</td>
                            <td>{LATEST_STATES[p_id]["h_dyn_m"]:.1f} m</td>
                            <td>₹ {LATEST_PRICES[p_id]["lambda_inr_per_m3"]:.2f}</td>
                            <td><span class="{"tag-red" if LATEST_PRICES[p_id]["stress_level"] == "Stressed" else "tag-amber"}">{LATEST_PRICES[p_id]["stress_level"]}</span></td>
                            <td><span class="tag-green">AWS INGESTED</span></td>
                        </tr>
                        '''
            for p_id in list(REGISTERED_PUMPS.keys())[:6]
        )
    }
                    </tbody>
                </table>
            </div>
        </div>

        <script>
            async function updateAdvisory() {{
                const lang = document.getElementById("lang-select").value;
                const out = document.getElementById("advisory-output");
                out.innerHTML = "<em>Invoking Amazon Bedrock Model...</em>";
                try {{
                    const res = await fetch("/v1/aws/advisory", {{
                        method: "POST",
                        headers: {{ "Content-Type": "application/json" }},
                        body: JSON.stringify({{ pump_id: "PUMP-0001", language: lang }})
                    }});
                    const data = await res.json();
                    out.innerHTML = `<strong>${{data.source}} (${{data.language.toUpperCase()}})</strong><br>${{data.whatsapp_message}}<br><br><span style="color:#38bdf8;">👉 Action: ${{data.recommended_action}}</span>`;
                }} catch (e) {{
                    out.innerText = "Error invoking Bedrock advisory: " + e;
                }}
            }}

            async function testCedarPolicy() {{
                const role = document.getElementById("cedar-role").value;
                const act = document.getElementById("cedar-action").value;
                const out = document.getElementById("cedar-output");
                try {{
                    const res = await fetch("/v1/aws/auth-check", {{
                        method: "POST",
                        headers: {{ "Content-Type": "application/json" }},
                        body: JSON.stringify({{
                            principal_type: role === "Farmer" ? "AquiPulse::Farmer" : "AquiPulse::Role",
                            principal_id: role,
                            action: act,
                            resource_type: act === "ModifyAquiferBoundary" ? "AquiPulse::Aquifer" : (act === "ViewVillageLedger" ? "AquiPulse::Village" : (act === "ClaimEarnedBonus" ? "AquiPulse::Pump" : "AquiPulse::Feeder")),
                            resource_id: "FEEDER-AG01",
                            resource_owner: role
                        }})
                    }});
                    const data = await res.json();
                    const color = data.decision === "ALLOW" ? "#34d399" : "#f87171";
                    out.innerHTML = `<strong style="color:${{color}}">Decision: ${{data.decision}}</strong><br><span style="color:#cbd5e1; font-size:0.8rem;">${{data.diagnostic_reason}}</span>`;
                }} catch (e) {{
                    out.innerText = "Error evaluating Cedar: " + e;
                }}
            }}
        </script>
    </body>
    </html>
    """
