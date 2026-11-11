"""
Test suite for ProofLedger backend API service.
Verifies all 9 forensic routes, error handling, and payload responses.
"""
import sys
from pathlib import Path
_ROOT_DIR = Path(__file__).resolve().parent.parent
if str(_ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(_ROOT_DIR))

import pytest
from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)

def test_health():
    res = client.get("/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "HEALTHY"
    assert data["ledger_valid"] is True
    assert data["total_events"] == 164

def test_system_status():
    res = client.get("/api/v2/system/status")
    assert res.status_code == 200
    data = res.json()
    assert data["overall_status"] in ["OPERATIONAL", "DEGRADED"]
    assert data["application_server"]["status"] == "ONLINE"
    assert data["database"]["status"] == "CONNECTED"
    assert data["paypal"]["configured"] in [True, False]
    assert data["ai_model"]["status"] in ["MODEL_LOADED", "MODEL_UNAVAILABLE"]
    assert data["ledger"]["status"] == "VALID"

def test_overview():
    res = client.get("/api/v2/overview")
    assert res.status_code == 200
    data = res.json()
    assert "ledger" in data
    assert "paypal_sandbox" in data
    assert data["paypal_sandbox"]["capture_id"] == "10A71705XW788203L"
    assert data["paypal_sandbox"]["order_id"] == "3EU95140LR696653G"

def test_events_list_and_filter():
    res = client.get("/api/v2/events?page=1&page_size=10")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 164
    assert len(data["events"]) == 10
    assert data["page"] == 1

def test_event_detail_and_404():
    # Valid capture lookup
    res = client.get("/api/v2/events/10A71705XW788203L")
    assert res.status_code == 200
    data = res.json()
    assert (
        data.get("transaction_ref") == "10A71705XW788203L"
        or data.get("source_event_id") == "10A71705XW788203L"
        or data.get("payload", {}).get("capture_id") == "10A71705XW788203L"
    )

    # Non-existent
    res_404 = client.get("/api/v2/events/non_existent_uuid_12345")
    assert res_404.status_code == 404

def test_forensic_verification():
    res = client.get("/api/v2/verification/10A71705XW788203L")
    assert res.status_code == 200
    data = res.json()
    assert data["found"] is True
    assert data["verdict"] == "CONTENT_AUTHENTICATED & DATABASE_CORRELATED — HISTORICAL CHAIN LINK UNVERIFIED"
    assert data["checks"]["self_hash_valid"] is True
    assert data["checks"]["database_correlation"] is True

def test_ledger_chain_and_validation():
    res = client.get("/api/v2/ledger")
    assert res.status_code == 200
    data = res.json()
    assert data["is_valid"] is True
    assert data["total_events"] == 164

    res_val = client.get("/api/v2/ledger/validate")
    assert res_val.status_code == 200
    assert res_val.json()["is_valid"] is True
    assert res_val.json()["error_count"] == 0

def test_migration_audit():
    res = client.get("/api/v2/migration")
    assert res.status_code == 200
    data = res.json()
    assert data["manifest_valid"] is True
    assert data["errors"] == []

def test_keys_registry():
    res = client.get("/api/v2/keys")
    assert res.status_code == 200
    data = res.json()
    assert data["total_keys"] >= 3
    # Ensure raw secrets are redacted
    for k in data["keys"]:
        assert "secret" not in k

def test_security_posture():
    res = client.get("/api/v2/security")
    assert res.status_code == 200
    data = res.json()
    assert data["security_posture"] == "FORTIFIED"
    assert "F-01_unicode_normalization" in data["findings_remediation"]

def test_reconciliation():
    res = client.get("/api/v2/reconciliation")
    assert res.status_code == 200
    data = res.json()
    assert data["reconciliation_status"] == "100% RECONCILED — ZERO DISCREPANCIES"
    assert len(data["discrepancies"]) == 0

def test_transactions_endpoint():
    # Unauthenticated must fail closed with 401
    res_unauth = client.get("/api/v2/transactions")
    assert res_unauth.status_code == 401

    # Authenticated seller
    headers = {"Authorization": "Bearer key_alpha_123"}
    res = client.get("/api/v2/transactions", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["total_transactions"] >= 1
    assert any(t["capture_id"] == "10A71705XW788203L" for t in data["transactions"])

def test_disputes_and_claim_verification():
    # Unauthenticated must fail closed with 401
    res_unauth = client.get("/api/v2/disputes")
    assert res_unauth.status_code == 401

    headers = {"Authorization": "Bearer key_alpha_123"}
    res = client.get("/api/v2/disputes", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["total_disputes"] >= 1
    sample = data["disputes"][0]

    # Verify claim verification
    payload = {
        "transaction_reference": sample["transaction_reference"],
        "claimed_recipient": sample["buyer_email"],
        "evidence": sample["default_evidence"],
        "claims": [c["claim_text"] for c in sample["default_claims"]],
    }
    res_ver = client.post("/api/v2/disputes/verify-claims", json=payload, headers=headers)
    assert res_ver.status_code == 200
    packet = res_ver.json()
    assert packet["total_claims"] == 4
    if packet.get("ai_engine", {}).get("status") == "OFFLINE" or packet.get("model_offline_fail_closed"):
        assert packet["supported_claims"] == 1
        assert packet["insufficient_claims"] == 3
    else:
        assert packet["supported_claims"] == 3
        assert packet["insufficient_claims"] == 1
    assert "packet_sha256_digest" in packet

    # Verify server-side human approval
    # 1. Unauthenticated approval must fail closed with 401
    res_unauth_appr = client.post(f"/api/v2/disputes/{sample['dispute_id']}/approve", json={
        "seller_id": "seller_alpha",
        "packet_data": packet,
        "signature_confirmed": True,
    })
    assert res_unauth_appr.status_code == 401

    # 2. Authenticated approval succeeds
    appr_payload = {
        "seller_id": "seller_alpha",
        "packet_data": packet,
        "signature_confirmed": True,
    }
    res_appr = client.post(f"/api/v2/disputes/{sample['dispute_id']}/approve", json=appr_payload, headers=headers)
    assert res_appr.status_code == 200
    appr_receipt = res_appr.json()
    assert appr_receipt["audit_status"] == "SEALED_FOR_PAYPAL_SUBMISSION"
    assert appr_receipt["human_approved"] is True
