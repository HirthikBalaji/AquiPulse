"""Tests for AquiPulse AWS Cloud & Open Source Integration.

Verifies AWS IoT Core bridge, serverless Lambda handlers, Amazon Bedrock
vernacular agent, AWS Cedar authorization, S3 immutable ledger, and REST API.
"""

from __future__ import annotations

import json
from fastapi.testclient import TestClient
import pytest

from api.service import app
from aws.bedrock_agent import BedrockGroundwaterAgent
from aws.cedar_auth import CedarPolicyEngine
from aws.config import get_aws_status, is_localstack_mode
from aws.iot_core import AwsIotBridge
from aws.lambda_handlers import (
    handler_bedrock_advisory,
    handler_heartbeat_ingest,
    handler_settlement_cycle,
    handler_transient_burst,
)
from aws.s3_ledger import S3LedgerArchive


@pytest.fixture
def client():
    return TestClient(app)


def test_aws_config_status():
    status = get_aws_status()
    assert "region" in status
    assert "s3_bucket" in status
    assert "dynamodb_table" in status
    assert "bedrock_model" in status
    assert "status" in status
    assert isinstance(is_localstack_mode(), bool)


def test_aws_iot_topic_formatting():
    bridge = AwsIotBridge()
    topic = bridge.format_telemetry_topic("FEEDER-AG01", "PUMP-0001")
    assert topic == "aquipulse/feeder/FEEDER-AG01/well/PUMP-0001/telemetry"

    burst_topic = bridge.format_burst_topic("FEEDER-AG01", "PUMP-0001")
    assert burst_topic == "aquipulse/feeder/FEEDER-AG01/well/PUMP-0001/burst"

    shadow_topic = bridge.format_shadow_topic("PUMP-0001")
    assert shadow_topic == "$aws/things/PUMP-0001/shadow/update"


def test_aws_iot_publish_and_shadow():
    bridge = AwsIotBridge()
    res = bridge.publish_telemetry(
        feeder_id="FEEDER-AG01",
        pump_id="PUMP-0001",
        v_rms=415.0,
        i_rms=14.2,
        pf=0.86,
        p_kw=8.75,
        freq_hz=50.0,
    )
    assert res["valid"] is True
    assert res["payload"]["pump_id"] == "PUMP-0001"

    shadow = bridge.update_device_shadow(
        pump_id="PUMP-0001",
        flow_lps=5.8,
        dynamic_head_m=48.2,
        static_depth_m=34.6,
        is_running=True,
    )
    assert shadow["shadow"]["state"]["reported"]["flow_lps"] == 5.8


def test_bedrock_agent_multilingual():
    agent = BedrockGroundwaterAgent()

    # Test Hindi
    res_hi = agent.generate_farmer_advisory(
        pump_id="PUMP-0001",
        farmer_name="Rajesh Kumar",
        depth_m=34.8,
        flow_lps=5.8,
        externality_price_inr=2.14,
        language="hi",
    )
    assert res_hi["language"] == "hi"
    assert "Rajesh Kumar" in res_hi["sms_text"]
    assert "जलस्तर" in res_hi["sms_text"]
    assert res_hi["estimated_daily_bonus_inr"] > 0

    # Test Punjabi
    res_pa = agent.generate_farmer_advisory(
        pump_id="PUMP-0002",
        farmer_name="Gurpreet Singh",
        depth_m=38.2,
        flow_lps=6.2,
        externality_price_inr=2.45,
        language="pa",
    )
    assert res_pa["language"] == "pa"
    assert "Gurpreet Singh" in res_pa["sms_text"] or "ਕਿਸਾਨ" in res_pa["sms_text"]

    # Test Gujarati
    res_gu = agent.generate_farmer_advisory(
        pump_id="PUMP-0003",
        farmer_name="Pravin Patel",
        depth_m=32.1,
        flow_lps=5.2,
        externality_price_inr=1.95,
        language="gu",
    )
    assert res_gu["language"] == "gu"
    assert "Pravin Patel" in res_gu["sms_text"] or "ખેડૂત" in res_gu["sms_text"]

    # Test DISCOM natural language copilot
    copilot_res = agent.answer_discom_query("How can we mitigate acute cone stress in Feeder AG-01?")
    assert "cone" in copilot_res["response"].lower() or "feeder" in copilot_res["response"].lower()


def test_cedar_policy_evaluation():
    engine = CedarPolicyEngine()

    # 1. DISCOM Operator on Feeder -> ALLOW
    dec1 = engine.is_authorized(
        principal_type="AquiPulse::Role",
        principal_id="DISCOM_Operator",
        action="ViewTelemetry",
        resource_type="AquiPulse::Feeder",
        resource_id="FEEDER-AG01",
    )
    assert dec1.decision == "ALLOW"

    # 2. DISCOM Operator modifying Aquifer -> DENY (Forbid rule #2)
    dec2 = engine.is_authorized(
        principal_type="AquiPulse::Role",
        principal_id="DISCOM_Operator",
        action="ModifyAquiferBoundary",
        resource_type="AquiPulse::Aquifer",
        resource_id="AQUIFER-DISTRICT",
    )
    assert dec2.decision == "DENY"
    assert "forbidden" in dec2.diagnostic_reason.lower()

    # 3. Hydrogeologist running adjoint solve -> ALLOW
    dec3 = engine.is_authorized(
        principal_type="AquiPulse::Role",
        principal_id="Hydrogeologist",
        action="RunAdjointSolve",
        resource_type="AquiPulse::Aquifer",
        resource_id="AQUIFER-DISTRICT",
    )
    assert dec3.decision == "ALLOW"

    # 4. Farmer claiming bonus on own well -> ALLOW
    dec4 = engine.is_authorized(
        principal_type="AquiPulse::Farmer",
        principal_id="FARMER-0001",
        action="ClaimEarnedBonus",
        resource_type="AquiPulse::Pump",
        resource_id="PUMP-0001",
        resource_owner="FARMER-0001",
    )
    assert dec4.decision == "ALLOW"

    # 5. Farmer claiming bonus on someone else's well -> DENY
    dec5 = engine.is_authorized(
        principal_type="AquiPulse::Farmer",
        principal_id="FARMER-0001",
        action="ClaimEarnedBonus",
        resource_type="AquiPulse::Pump",
        resource_id="PUMP-0002",
        resource_owner="FARMER-0002",
    )
    assert dec5.decision == "DENY"

    # 6. Farmer trying to shut down the grid feeder -> DENY (Forbid rule #6)
    dec6 = engine.is_authorized(
        principal_type="AquiPulse::Farmer",
        principal_id="FARMER-0001",
        action="TriggerEmergencyShutdown",
        resource_type="AquiPulse::Feeder",
        resource_id="FEEDER-AG01",
    )
    assert dec6.decision == "DENY"


def test_lambda_handlers():
    # Ingest handler
    evt_ingest = {
        "pump_id": "PUMP-0001",
        "feeder_id": "FEEDER-AG01",
        "ts": 1728500000.0,
        "v_rms": 415.0,
        "i_rms": 14.5,
        "pf": 0.85,
        "p_kw": 8.8,
        "freq_hz": 50.0,
        "signature": "",
    }
    res_ingest = handler_heartbeat_ingest(evt_ingest)
    assert res_ingest["statusCode"] == 200
    assert res_ingest["body"]["flow_lps"] > 0

    # Transient burst handler
    evt_burst = {"pump_id": "PUMP-0001", "ramp_duration_s": 12.0}
    res_burst = handler_transient_burst(evt_burst)
    assert res_burst["statusCode"] == 200
    assert res_burst["body"]["inferred_static_depth_m"] > 30.0

    # Settlement cycle handler
    res_settle = handler_settlement_cycle({"feeder_id": "FEEDER-AG01"})
    assert res_settle["statusCode"] == 200
    assert res_settle["body"]["total_avoided_volume_m3"] > 0
    assert res_settle["body"]["total_farmer_payout_inr"] > 0

    # Bedrock advisory handler
    res_adv = handler_bedrock_advisory({"pump_id": "PUMP-0001", "lang": "hi"})
    assert res_adv["statusCode"] == 200
    body = json.loads(res_adv["body"])
    assert body["language"] == "hi"


def test_s3_ledger_archive():
    archive = S3LedgerArchive()
    block = archive.archive_settlement_block(
        block_index=1,
        block_hash="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        prev_hash="0000000000000000000000000000000000000000000000000000000000000000",
        settlement_data={"total_avoided_m3": 3850.0},
    )
    assert "ledger/blocks/" in block["key"]
    assert block["block_index"] == 1


def test_api_aws_endpoints(client):
    # GET /v1/aws/status
    res_status = client.get("/v1/aws/status")
    assert res_status.status_code == 200
    data_status = res_status.json()
    assert data_status["region"] == "ap-south-1"

    # POST /v1/aws/advisory
    res_adv = client.post(
        "/v1/aws/advisory",
        json={"pump_id": "PUMP-0001", "language": "gu", "farmer_name": "Ramesh Patel"},
    )
    assert res_adv.status_code == 200
    data_adv = res_adv.json()
    assert data_adv["language"] == "gu"
    assert "Ramesh Patel" in data_adv["sms_text"] or "ખેડૂત" in data_adv["sms_text"]

    # POST /v1/aws/auth-check
    res_auth = client.post(
        "/v1/aws/auth-check",
        json={
            "principal_type": "AquiPulse::Role",
            "principal_id": "DISCOM_Operator",
            "action": "ViewTelemetry",
            "resource_type": "AquiPulse::Feeder",
            "resource_id": "FEEDER-AG01",
        },
    )
    assert res_auth.status_code == 200
    assert res_auth.json()["decision"] == "ALLOW"

    # POST /v1/aws/simulate-iot
    res_iot = client.post(
        "/v1/aws/simulate-iot",
        json={
            "feeder_id": "FEEDER-AG01",
            "pump_id": "PUMP-0001",
            "v_rms": 415.0,
            "i_rms": 14.5,
            "pf": 0.85,
            "p_kw": 8.8,
        },
    )
    assert res_iot.status_code == 200
    assert res_iot.json()["valid"] is True
    assert res_iot.json()["inferred_q_lps"] is not None
