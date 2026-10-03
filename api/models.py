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
