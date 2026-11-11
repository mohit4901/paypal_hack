"""
Phase 2.6 Security Hardening & Trustworthiness Audit Test Suite.
Validates 15 core security, isolation, provenance, and fail-closed cryptographic invariants:

1. Fail-closed authentication (401 on missing auth across protected endpoints).
2. Rejection of invalid/forged API keys (401).
3. Cross-seller transaction isolation (404).
4. Cross-seller evidence isolation (404/empty).
5. Cross-seller verification run isolation (404).
6. Cross-seller approval attempt rejection (403 forbidden).
7. Provenance safety: newly created/uploaded evidence defaults to SOURCE_UNVERIFIED and is_verified_source = 0.
8. Approval schema defaults: human_approved=0, signature_confirmed=0.
9. Approval tampering/drift rejection (400 on modified packet digest).
10. Stale / nonexistent verification run rejection (400).
11. Duplicate approval replay rejection (409).
12. Model offline fail-closed for semantic claims (INSUFFICIENT_EVIDENCE + FALLBACK_MODEL_OFFLINE).
13. Deterministic rule offline disclosure (SUPPORTED + DETERMINISTIC_RULES_ONLY).
14. API key rotation and account revocation (old/revoked keys return 401).
15. SQLite relational foreign key enforcement (PRAGMA foreign_keys = ON).
"""
import copy
import json
import sqlite3
import uuid
import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.services.db_schema import (
    get_db_connection,
    PROVENANCE_SOURCE_UNVERIFIED,
    hash_api_key,
)
from backend.services.dispute_service import DisputeVerificationService

client = TestClient(app)

SELLER_ALPHA_KEY = "key_alpha_123"
SELLER_BETA_KEY = "key_beta_456"

ALPHA_HEADERS = {"Authorization": f"Bearer {SELLER_ALPHA_KEY}"}
BETA_HEADERS = {"Authorization": f"Bearer {SELLER_BETA_KEY}"}


# 1. Unauthenticated request rejected (401)
def test_unauthenticated_request_rejected_401():
    protected_endpoints = [
        ("GET", "/api/v2/transactions"),
        ("POST", "/api/v2/transactions"),
        ("GET", "/api/v2/transactions/3EU95140LR696653G"),
        ("GET", "/api/v2/transactions/3EU95140LR696653G/evidence"),
        ("GET", "/api/v2/disputes"),
        ("GET", "/api/v2/disputes/runs"),
        ("POST", "/api/v2/disputes/verify-claims"),
        ("POST", "/api/v2/disputes/DSP-TEST/approve"),
        ("GET", "/api/v2/sellers/me"),
        ("POST", "/api/v2/sellers/rotate-key"),
    ]
    for method, path in protected_endpoints:
        if method == "GET":
            res = client.get(path)
        else:
            res = client.post(path, json={})
        assert res.status_code == 401, f"Endpoint {method} {path} failed to fail-closed! Status: {res.status_code}"


# 2. Invalid API key rejected (401)
def test_invalid_api_key_rejected_401():
    bad_headers = [
        {"Authorization": "Bearer invalid_token_xyz_999"},
        {"Authorization": "Bearer key_alpha_WRONG"},
        {"X-Seller-Key": "completely_bogus_key"},
        {"Authorization": "Basic dXNlcjpwYXNz"},
    ]
    for h in bad_headers:
        res = client.get("/api/v2/sellers/me", headers=h)
        assert res.status_code == 401


# 3. Cross-seller transaction isolation (404)
def test_cross_seller_transaction_isolation_404():
    # Alpha creates a transaction
    ord_id = f"ORD-ISOL-{uuid.uuid4().hex[:6].upper()}"
    res_create = client.post("/api/v2/transactions", json={
        "order_id": ord_id,
        "amount": "120.00",
        "currency": "USD",
        "product_name": "Alpha Confidential Source Code",
        "buyer_email": "buyer.alpha@example.com",
    }, headers=ALPHA_HEADERS)
    assert res_create.status_code == 200

    # Alpha can read it
    res_alpha = client.get(f"/api/v2/transactions/{ord_id}", headers=ALPHA_HEADERS)
    assert res_alpha.status_code == 200
    assert res_alpha.json()["order_id"] == ord_id

    # Beta querying Alpha's transaction MUST get 404
    res_beta = client.get(f"/api/v2/transactions/{ord_id}", headers=BETA_HEADERS)
    assert res_beta.status_code == 404


# 4. Cross-seller evidence isolation (404 / isolated)
def test_cross_seller_evidence_isolation():
    ord_id = f"ORD-EV-ISOL-{uuid.uuid4().hex[:6].upper()}"
    client.post("/api/v2/transactions", json={
        "order_id": ord_id,
        "amount": "80.00",
        "buyer_email": "alpha.private@example.com",
    }, headers=ALPHA_HEADERS)

    # Beta querying evidence for Alpha's order gets zero records
    res_beta = client.get(f"/api/v2/transactions/{ord_id}/evidence", headers=BETA_HEADERS)
    assert res_beta.status_code == 200
    assert res_beta.json()["total_records"] == 0
    assert len(res_beta.json()["evidence"]) == 0


# 5. Cross-seller verification run isolation (404)
def test_cross_seller_verification_run_isolation_404():
    # Alpha executes a verification run
    res_ver = client.post("/api/v2/disputes/verify-claims", json={
        "transaction_reference": "ORD-ISOL-RUN",
        "claims": ["Payment was captured"],
        "evidence": [{
            "evidence_id": "EV-01",
            "source_type": "paypal_api",
            "content": "Order ORD-ISOL-RUN Capture CAP-01 COMPLETED gross 50.00 USD",
        }],
    }, headers=ALPHA_HEADERS)
    assert res_ver.status_code == 200
    alpha_run_id = res_ver.json()["run_id"]

    # Beta querying Alpha's run_id MUST get 404
    res_beta_run = client.get(f"/api/v2/disputes/runs/{alpha_run_id}", headers=BETA_HEADERS)
    assert res_beta_run.status_code == 404


# 6. Cross-seller approval attempt rejection (403 forbidden)
def test_cross_seller_approval_rejection_403():
    # Alpha generates a valid packet
    res_ver = client.post("/api/v2/disputes/verify-claims", json={
        "transaction_reference": "ORD-CROSS-APPR",
        "claims": ["Payment of 50.00 USD completed"],
        "evidence": [{
            "evidence_id": "EV-01",
            "source_type": "paypal_api",
            "content": "Order ORD-CROSS-APPR Capture CAP-01 COMPLETED gross 50.00 USD",
        }],
    }, headers=ALPHA_HEADERS)
    pkt = res_ver.json()

    # Beta tries to approve it on behalf of Alpha
    res_beta_appr = client.post("/api/v2/disputes/DSP-ORD-CROSS-APPR/approve", json={
        "seller_id": "seller_alpha",
        "packet_data": pkt,
        "signature_confirmed": True,
    }, headers=BETA_HEADERS)
    assert res_beta_appr.status_code == 403
    assert "Forbidden" in res_beta_appr.json()["detail"]


# 7. Provenance safety: newly created/uploaded evidence defaults to SOURCE_UNVERIFIED and is_verified_source = 0
def test_provenance_defaults_to_unverified():
    ord_id = f"ORD-PROV-{uuid.uuid4().hex[:6].upper()}"
    res_tx = client.post("/api/v2/transactions", json={
        "order_id": ord_id,
        "amount": "99.00",
        "buyer_email": "customer@example.com",
    }, headers=ALPHA_HEADERS)
    assert res_tx.status_code == 200

    # Add custom uploaded evidence
    res_ev = client.post(f"/api/v2/transactions/{ord_id}/evidence", json={
        "source_type": "custom_upload",
        "source_name": "Manual Excel Ingest",
        "event_type": "CLAIM_PROOF",
        "content": "Customer confirmed receipt via WhatsApp screenshot",
    }, headers=ALPHA_HEADERS)
    assert res_ev.status_code == 200

    # Check database directly to ensure unverified defaults were stored
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT evidence_id, provenance_status, is_verified_source FROM seller_evidence WHERE transaction_ref = ?",
        (ord_id,),
    )
    rows = cur.fetchall()
    conn.close()

    assert len(rows) >= 4  # 3 auto-generated + 1 custom uploaded
    for r in rows:
        assert r["provenance_status"] == PROVENANCE_SOURCE_UNVERIFIED
        assert r["is_verified_source"] == 0, f"Record {r['evidence_id']} was falsely marked as verified!"


# 8. Approval schema defaults: human_approved=0, signature_confirmed=0
def test_approval_schema_defaults_are_false():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(dispute_approvals)")
    cols = {r["name"]: r["dflt_value"] for r in cur.fetchall()}
    conn.close()

    assert cols.get("human_approved") == "0"
    assert cols.get("signature_confirmed") == "0"


# 9. Approval tampering/drift rejection (400 on modified packet digest)
def test_approval_rejects_tampered_packet_digest():
    res_ver = client.post("/api/v2/disputes/verify-claims", json={
        "transaction_reference": "ORD-DRIFT-TEST",
        "claims": ["Payment confirmed"],
        "evidence": [{
            "evidence_id": "EV-01",
            "source_type": "paypal_api",
            "content": "Order ORD-DRIFT-TEST Capture CAP-01 COMPLETED gross 40.00 USD",
        }],
    }, headers=ALPHA_HEADERS)
    pkt = res_ver.json()

    # Tamper with the packet by forging a different digest
    tampered_pkt = copy.deepcopy(pkt)
    tampered_pkt["packet_sha256_digest"] = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"

    res_appr = client.post("/api/v2/disputes/DSP-DRIFT/approve", json={
        "packet_data": tampered_pkt,
        "signature_confirmed": True,
    }, headers=ALPHA_HEADERS)
    assert res_appr.status_code == 400
    assert "Packet digest mismatch" in res_appr.json()["detail"]


# 10. Stale / nonexistent verification run rejection (400)
def test_approval_rejects_nonexistent_run():
    fake_pkt = {
        "run_id": "VRUN-FAKE-DOES-NOT-EXIST",
        "packet_sha256_digest": "a" * 64,
        "response_draft": "Draft",
    }
    res_appr = client.post("/api/v2/disputes/DSP-FAKE/approve", json={
        "packet_data": fake_pkt,
        "signature_confirmed": True,
    }, headers=ALPHA_HEADERS)
    assert res_appr.status_code == 400
    assert "not found" in res_appr.json()["detail"].lower()


# 11. Duplicate approval replay rejection (409)
def test_duplicate_approval_replay_rejected_409():
    disp_id = f"DSP-REPLAY-{uuid.uuid4().hex[:6].upper()}"
    res_ver = client.post("/api/v2/disputes/verify-claims", json={
        "transaction_reference": disp_id,
        "claims": ["Payment of 35.00 USD completed"],
        "evidence": [{
            "evidence_id": "EV-01",
            "source_type": "paypal_api",
            "content": f"Order {disp_id} Capture CAP-01 COMPLETED gross 35.00 USD",
        }],
    }, headers=ALPHA_HEADERS)
    pkt = res_ver.json()

    # First approval succeeds
    res_appr_1 = client.post(f"/api/v2/disputes/{disp_id}/approve", json={
        "packet_data": pkt,
        "signature_confirmed": True,
    }, headers=ALPHA_HEADERS)
    assert res_appr_1.status_code == 200

    # Second approval of exact same digest for same dispute MUST return 409
    res_appr_2 = client.post(f"/api/v2/disputes/{disp_id}/approve", json={
        "packet_data": pkt,
        "signature_confirmed": True,
    }, headers=ALPHA_HEADERS)
    assert res_appr_2.status_code == 409
    assert "Duplicate approval rejected" in res_appr_2.json()["detail"]


# 12. Model offline fail-closed for semantic claims (INSUFFICIENT_EVIDENCE + FALLBACK_MODEL_OFFLINE)
def test_model_offline_fail_closed_for_semantic_claim():
    offline_service = DisputeVerificationService()
    offline_service.verifier = None  # Simulate offline model

    res = offline_service.verify_single_claim(
        claim_input="The student completed module 4 and gave a 5 star course review",
        evidence=[{
            "evidence_id": "EV-01",
            "source_type": "course_platform",
            "content": "Student enrolled in Python course. Module 4 completed.",
        }],
        transaction_reference="ORD-OFFLINE-01",
    )
    # Must fail-closed because model is unavailable to perform semantic inference
    assert res["verdict"] == "INSUFFICIENT_EVIDENCE"
    assert res["verdict_engine"] == "FALLBACK_MODEL_OFFLINE"
    assert res["semantic_inference_performed"] is False
    assert res["ai_model"]["calibration_status"] == "NOT_APPLICABLE_OFFLINE"


# 13. Deterministic rule offline disclosure (SUPPORTED + DETERMINISTIC_RULES_ONLY)
def test_deterministic_rule_offline_disclosure():
    offline_service = DisputeVerificationService()
    offline_service.verifier = None  # Simulate offline model

    # Payment capture claim has an exact deterministic validator rule
    res = offline_service.verify_single_claim(
        claim_input="Payment of 50.00 USD was successfully captured for Order ORD-OFFLINE-02",
        evidence=[{
            "evidence_id": "EV-01",
            "source_type": "paypal_api",
            "content": "Order ORD-OFFLINE-02 Capture CAP-01 status COMPLETED gross 50.00 USD",
        }],
        transaction_reference="ORD-OFFLINE-02",
    )
    assert res["verdict"] == "SUPPORTED"
    assert res["verdict_engine"] == "DETERMINISTIC_RULES_ONLY"
    assert res["semantic_inference_performed"] is False


# 14. API key rotation and account revocation
def test_api_key_rotation_and_revocation():
    # Register a new dynamic seller
    seller_tag = f"test_seller_{uuid.uuid4().hex[:6]}"
    res_reg = client.post("/api/v2/sellers/register", json={
        "seller_id": seller_tag,
        "business_name": "Temporary Test Store",
        "product_category": "Software",
        "support_email": f"{seller_tag}@example.com",
    })
    assert res_reg.status_code == 200
    raw_key_1 = res_reg.json()["raw_api_key"]

    auth_1 = {"Authorization": f"Bearer {raw_key_1}"}
    res_me = client.get("/api/v2/sellers/me", headers=auth_1)
    assert res_me.status_code == 200
    assert res_me.json()["seller_id"] == seller_tag

    # Rotate API key
    res_rot = client.post("/api/v2/sellers/rotate-key", headers=auth_1)
    assert res_rot.status_code == 200
    raw_key_2 = res_rot.json()["raw_api_key"]
    assert raw_key_2 != raw_key_1

    # Old key immediately rejected (401)
    res_old = client.get("/api/v2/sellers/me", headers=auth_1)
    assert res_old.status_code == 401

    # New key succeeds (200)
    auth_2 = {"Authorization": f"Bearer {raw_key_2}"}
    res_new = client.get("/api/v2/sellers/me", headers=auth_2)
    assert res_new.status_code == 200

    # Revoke account
    res_rev = client.post("/api/v2/sellers/revoke", headers=auth_2)
    assert res_rev.status_code == 200

    # Revoked key immediately returns 401
    res_revoked = client.get("/api/v2/sellers/me", headers=auth_2)
    assert res_revoked.status_code == 401


# 15. SQLite relational foreign key enforcement (PRAGMA foreign_keys = ON)
def test_sqlite_foreign_key_enforcement():
    conn = get_db_connection()
    cur = conn.cursor()

    # Attempt to insert a transaction pointing to a nonexistent seller_id
    with pytest.raises(sqlite3.IntegrityError):
        cur.execute("""
            INSERT INTO seller_transactions (
                transaction_id, seller_id, order_id, capture_id, amount, buyer_email, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            "TX-FK-TEST",
            "nonexistent_seller_99999",
            "ORD-FK-01",
            "CAP-FK-01",
            "10.00",
            "buyer@example.com",
            "2026-11-01T00:00:00Z",
            "2026-11-01T00:00:00Z",
        ))
    conn.close()

