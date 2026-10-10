"""AquiPulse Pydantic Models for REST API endpoints."""

from __future__ import annotations

from typing import List, Optional, Tuple

from pydantic import BaseModel


class TelemetryBatchItem(BaseModel):
    pump_id: str
    ts: float
    v_rms: float
    i_rms: float
    pf: float
    p_kw: float
    freq_hz: float = 50.0
    signature: str


class TelemetryBatchRequest(BaseModel):
    batch: List[TelemetryBatchItem]


class TelemetryBatchResponse(BaseModel):
    received_count: int
    accepted_count: int
    flagged_count: int
    flags: List[str]


class PumpStateResponse(BaseModel):
    pump_id: str
    timestamp_s: float
    q_lps: float
    sigma_q: float
    q_ci_90: Tuple[float, float]
    h_dyn_m: float
    sigma_hd: float
    z_static_m: float
    sigma_zs: float
    zs_ci_90: Tuple[float, float]
    eta_overall: float
    is_running: bool
    is_dry_run: bool


class PumpAquiferResponse(BaseModel):
    pump_id: str
    log10_t: float
    sigma_log10_t: float
    flow_dim_n: float
    storativity_s: Optional[float]
    interference_neighbours: List[str]
    identifiability_status: str


class CellStateItem(BaseModel):
    cell_id: str
    x_m: float
    y_m: float
    head_m: float
    static_depth_m: float
    sigma_head_m: float
    transmissivity_m2_s: float
    stress_level: str


class CellsResponse(BaseModel):
    cells: List[CellStateItem]
    count: int


class PumpPriceResponse(BaseModel):
    pump_id: str
    timestamp_s: float
    lambda_inr_per_m3: float
    ci_90_low: float
    ci_90_high: float
    local_cone_stress: str


class AuditSubmissionRequest(BaseModel):
    pump_id: str
    ts: float
    bucket_q_lps: float
    dip_level_m: float
    auditor_id: str


class AuditSubmissionResponse(BaseModel):
    status: str
    audit_id: int
    calibrated_q_lps: float
    calibrated_z_static_m: float


class SettlementItem(BaseModel):
    pump_id: str
    farmer_id: str
    period: str
    avoided_volume_m3: float
    unit_externality_price_inr: float
    farmer_payout_inr: float
    guardrail_passed: bool
    flags: List[str]


class SettlementResponse(BaseModel):
    period: str
    total_avoided_volume_m3: float
    total_farmer_payout_inr: float
    settlements: List[SettlementItem]


class FarmerLiteViewResponse(BaseModel):
    farmer_id: str
    pump_id: str
    language: str
    summary_text_sms: str
    whatsapp_card_markdown: str
    recommended_action: str


class AwsStatusResponse(BaseModel):
    region: str
    localstack_mode: bool
    localstack_endpoint: Optional[str]
    s3_bucket: str
    dynamodb_table: str
    timestream_db: str
    bedrock_model: str
    status: str


class BedrockAdvisoryRequest(BaseModel):
    pump_id: str = "PUMP-0001"
    language: str = "hi"
    farmer_name: Optional[str] = None
    query: Optional[str] = None


class BedrockAdvisoryResponse(BaseModel):
    pump_id: str
    farmer_name: str
    language: str
    source: str
    model_id: str
    sms_text: str
    whatsapp_message: str
    recommended_action: str
    estimated_daily_bonus_inr: float = 0.0


class CedarAuthRequest(BaseModel):
    principal_type: str = "AquiPulse::Role"
    principal_id: str = "DISCOM_Operator"
    action: str = "ViewTelemetry"
    resource_type: str = "AquiPulse::Feeder"
    resource_id: str = "FEEDER-AG01"
    resource_owner: Optional[str] = None
    context: Optional[dict] = None


class CedarAuthResponse(BaseModel):
    decision: str
    diagnostic_reason: str
    matching_policy: Optional[str]


class AwsIoTSimulateRequest(BaseModel):
    feeder_id: str = "FEEDER-AG01"
    pump_id: str = "PUMP-0001"
    v_rms: float = 415.0
    i_rms: float = 14.5
    pf: float = 0.85
    p_kw: float = 8.8
    freq_hz: float = 50.0
    signature: str = ""


class AwsIoTSimulateResponse(BaseModel):
    topic: str
    published: bool
    valid: bool
    flags: List[str]
    inferred_q_lps: Optional[float] = None
    inferred_h_dyn_m: Optional[float] = None
