"""Integration and endpoint tests for FastAPI services (api/)."""

from fastapi.testclient import TestClient

from api.service import app

client = TestClient(app)


def test_get_pump_state():
    """Verify GET /v1/pumps/{id}/state returns valid state and 90% CI."""
    response = client.get("/v1/pumps/PUMP-0001/state")
    assert response.status_code == 200
    data = response.json()
    assert data["pump_id"] == "PUMP-0001"
    assert data["q_lps"] > 0.0
    assert len(data["q_ci_90"]) == 2
    assert data["z_static_m"] > 0.0


def test_get_pump_aquifer():
    """Verify GET /v1/pumps/{id}/aquifer returns T and S estimates."""
    response = client.get("/v1/pumps/PUMP-0001/aquifer")
    assert response.status_code == 200
    data = response.json()
    assert "log10_t" in data
    assert "storativity_s" in data
    assert data["identifiability_status"] == "Identified"


def test_get_cells():
    """Verify GET /v1/cells returns privacy-preserving aggregated grid."""
    response = client.get("/v1/cells")
    assert response.status_code == 200
    data = response.json()
    assert data["count"] > 0
    assert "head_m" in data["cells"][0]


def test_get_pump_price():
    """Verify GET /v1/pumps/{id}/price returns externality price in INR/m3."""
    response = client.get("/v1/pumps/PUMP-0001/price")
    assert response.status_code == 200
    data = response.json()
    assert data["lambda_inr_per_m3"] > 0.0
    assert data["ci_90_low"] <= data["lambda_inr_per_m3"] <= data["ci_90_high"]


def test_post_audit_calibration():
    """Verify POST /v1/audits records ground truth bucket/dip measurement."""
    payload = {
        "pump_id": "PUMP-0001",
        "ts": 1700001000.0,
        "bucket_q_lps": 5.92,
        "dip_level_m": 34.2,
        "auditor_id": "TECH-AG-04",
    }
    response = client.post("/v1/audits", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "CALIBRATED"
    assert data["calibrated_q_lps"] == 5.92


def test_get_settlements():
    """Verify GET /v1/settlements returns verified avoided volumes and bonuses."""
    response = client.get("/v1/settlements?period=2026-Q3")
    assert response.status_code == 200
    data = response.json()
    assert data["total_avoided_volume_m3"] > 0.0
    assert data["total_farmer_payout_inr"] > 0.0
    assert len(data["settlements"]) > 0


def test_get_farmer_lite_view():
    """Verify GET /v1/pumps/{id}/farmer-lite generates SMS and WhatsApp card."""
    response = client.get("/v1/pumps/PUMP-0001/farmer-lite")
    assert response.status_code == 200
    data = response.json()
    assert "summary_text_sms" in data
    assert "whatsapp_card_markdown" in data
    assert "depth" in data["summary_text_sms"]


def test_discom_console_dashboard():
    """Verify GET /discom/console renders interactive HTML dashboard."""
    response = client.get("/discom/console")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "AquiPulse Aquifer & Feeder Console" in response.text
