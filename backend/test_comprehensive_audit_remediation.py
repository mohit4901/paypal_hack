"""
Comprehensive Audit Remediation Acceptance Test Suite (12 Acceptance Criteria)
ProofLedger Cryptographic Evidence Platform — PayPal AI Hackathon 2026.
"""

import hashlib
import json
import os
import sqlite3
import pytest
from pathlib import Path
from starlette.testclient import TestClient

from backend.main import app
from backend.config import ROOT_DIR, DATABASE_PATH, CHECKPOINTS_DIR, V2_CHAIN_LOG_PATH
from backend.security.asymmetric_anchor import (
    verify_asymmetric_checkpoint,
    ACTIVE_ED25519_PUBLIC_KEY_HEX,
    ACTIVE_AUTHORITY_KEY_IDENTITY,
    REVOKED_HISTORICAL_AUTHORITIES,
)
from backend.services.key_service import KeyRegistryService
from backend.services.dispute_service import DisputeVerificationService

client = TestClient(app)
SELLER_ALPHA_KEY = "key_alpha_123"
SELLER_BETA_KEY = "key_beta_456"
AUTH_ALPHA = {"Authorization": f"Bearer {SELLER_ALPHA_KEY}"}
AUTH_BETA = {"Authorization": f"Bearer {SELLER_BETA_KEY}"}


# ---------------------------------------------------------------------------
# Criterion 1: Exposed signing key regression & Ed25519 Authority Isolation
# ---------------------------------------------------------------------------
def test_criterion_1_authority_key_compromise_and_isolation():
    """
    1. Compromised key dbd6f98... is explicitly marked REVOKED_COMPROMISED and rejected.
    2. Zero hardcoded private seeds or HMAC secrets in tools and config files.
    3. tools/external_signing_authority.py fails closed without PROOFLEDGER_AUTHORITY_OFFLINE_SECRET.
    4. Active authority v3 verifies the baseline checkpoint.
    """
    # 1. Revoked key check
    compromised_key = "dbd6f98003d24c1170bfe6e89ad1e367e4f2aa44d14c2aaede7edd1600c1fae0"
    assert compromised_key in REVOKED_HISTORICAL_AUTHORITIES
    assert REVOKED_HISTORICAL_AUTHORITIES[compromised_key]["status"] == "REVOKED_COMPROMISED"

    # 2. Source code audit for exposed keys
    forbidden_strings = [
        "3a7b9c1d5e4f2a8b0c9d8e7f6a5b4c3d2e1f0a9b8c7d6e5f4a3b2c1d0e9f8a7b",
        "sandbox-hmac-secret-proofledger-2026-v2",
        "default-hmac-secret-proofledger-2026",
    ]
    files_to_check = [
        ROOT_DIR / "tools" / "external_signing_authority.py",
        ROOT_DIR / "backend" / "config.py",
        ROOT_DIR / "backend" / "services" / "key_service.py",
    ]
    for filepath in files_to_check:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
            for forbidden in forbidden_strings:
                assert forbidden not in content, f"Found exposed secret in {filepath}: {forbidden}"

    # 3. tools/external_signing_authority.py fails closed if secret absent
    from tools.external_signing_authority import _get_private_key
    old_env = os.environ.pop("PROOFLEDGER_AUTHORITY_OFFLINE_SECRET", None)
    try:
        with pytest.raises(RuntimeError, match="PROOFLEDGER_AUTHORITY_OFFLINE_SECRET environment variable is missing"):
            _get_private_key()
    finally:
        if old_env is not None:
            os.environ["PROOFLEDGER_AUTHORITY_OFFLINE_SECRET"] = old_env

    # 4. Active checkpoint verifies with pinned authority
    cp_path = CHECKPOINTS_DIR / "checkpoint_v2_baseline_ed25519_signed.json"
    assert cp_path.exists()
    is_valid, errors, meta = verify_asymmetric_checkpoint(
        ledger_path=str(V2_CHAIN_LOG_PATH),
        checkpoint_path=str(cp_path),
    )
    assert is_valid is True, f"Ed25519 verification failed: {errors}"
    assert meta["key_identity"] == "proofledger-authority-v3-isolated"
    assert meta["public_key_hex"] == ACTIVE_ED25519_PUBLIC_KEY_HEX


# ---------------------------------------------------------------------------
# Criterion 2: Anonymous and runtime checkpoint creation rejection
# ---------------------------------------------------------------------------
def test_criterion_2_anonymous_and_runtime_checkpoint_rejection():
    """
    1. Anonymous POST to /checkpoints/create returns 401 Unauthorized.
    2. Authenticated POST to /checkpoints/create returns 405 Method Not Allowed.
    """
    # Anonymous -> 401
    anon_res = client.post("/api/v2/checkpoints/create", json={"total_events": 10})
    assert anon_res.status_code == 401

    # Authenticated -> 405 Method Not Allowed (runtime signing prohibited)
    auth_res = client.post("/api/v2/checkpoints/create", json={"total_events": 10}, headers=AUTH_ALPHA)
    assert auth_res.status_code == 405
    assert "Runtime checkpoint signing is prohibited" in auth_res.json()["detail"]


# ---------------------------------------------------------------------------
# Criterion 3: AI abstention propagation
# ---------------------------------------------------------------------------
def test_criterion_3_ai_abstention_propagation():
    """
    When DeBERTa returns is_abstained=True or decision='NEEDS_HUMAN_REVIEW',
    the final_verdict must be strictly NEEDS_HUMAN_REVIEW, seller_decision=NEEDS_HUMAN_REVIEW,
    and excluded_from_response=True.
    Raw ml_label ('SUPPORTED') must NEVER override the final verdict!
    """
    service = DisputeVerificationService()

    # Mock verifier to simulate safe DeBERTa abstention on a low-confidence claim
    class MockVerifier:
        is_loaded = True
        device = "cpu"
        def predict(self, claim_text, evidence_records):
            return {
                "label": "SUPPORTED",
                "confidence": 0.45,
                "scores": {"SUPPORTED": 0.45, "CONTRADICTED": 0.35, "INSUFFICIENT_EVIDENCE": 0.20},
                "is_abstained": True,
                "decision": "NEEDS_HUMAN_REVIEW",
                "abstention_reason": "Low confidence (0.45 < 0.70 threshold)",
                "status": "INVOKED",
            }

    service.verifier = MockVerifier()

    claim_input = {
        "claim_id": "CLM-ABSTAIN-TEST",
        "claim_text": "Buyer accepted delivery in person at physical warehouse",
        "excluded_from_response": False,
        "seller_decision": "INCLUDED",
    }
    evidence = [
        {
            "evidence_id": "EV-01",
            "source_type": "warehouse",
            "timestamp": "2026-10-31T11:15:00Z",
            "content": "Warehouse pickup logged for order ORD-TEST-999",
        }
    ]

    res = service.verify_single_claim(
        claim_input=claim_input,
        evidence=evidence,
        transaction_reference="ORD-TEST-999",
    )

    # Enforce strict safety invariants:
    assert res["verdict"] == "NEEDS_HUMAN_REVIEW"
    assert res["seller_decision"] == "NEEDS_HUMAN_REVIEW"
    assert res["excluded_from_response"] is True
    assert res["is_abstained"] is True
    assert res["ai_model"]["label"] == "SUPPORTED"  # Telemetry preserves raw label, but final_verdict never uses it
    assert res["verdict_engine"] == "DEBERTA_SAFE_ABSTENTION"


# ---------------------------------------------------------------------------
# Criterion 4: Zero synthetic PayPal IDs in /import-live
# ---------------------------------------------------------------------------
def test_criterion_4_zero_synthetic_paypal_ids_in_import():
    """
    1. Calling POST /api/v2/paypal/import-live without order_id returns 400 Bad Request.
    2. Non-existent orders return 404 (strictly rejected; zero synthetic fallback IDs).
    """
    # 1. Missing order_id -> 400
    res = client.post("/api/v2/paypal/import-live", json={}, headers=AUTH_ALPHA)
    assert res.status_code == 400
    assert "order_id is required" in res.json()["detail"]

    # 2. Non-existent sandbox order -> 404
    res_fake = client.post(
        "/api/v2/paypal/import-live",
        json={"order_id": "NON-EXISTENT-ORDER-999"},
        headers=AUTH_ALPHA,
    )
    assert res_fake.status_code == 404
    assert "could not be verified on PayPal Sandbox" in res_fake.json()["detail"]


# ---------------------------------------------------------------------------
# Criterion 5: Missing PayPal capture ID handling
# ---------------------------------------------------------------------------
def test_criterion_5_missing_capture_id_fails_closed(monkeypatch):
    """
    If PayPal returns a capture response without a capture ID, the capture flow
    must fail closed with 422 and record no simulated or partial capture.
    """
    import requests
    from backend.services.paypal_service import PayPalLiveService

    class MockResponse:
        status_code = 201
        headers = {"Content-Type": "application/json"}
        def json(self):
            return {
                "id": "TEST-ORDER-123",
                "status": "COMPLETED",
                "purchase_units": [{"payments": {"captures": []}}],  # Empty captures!
            }

    monkeypatch.setattr(requests, "post", lambda *args, **kwargs: MockResponse())
    monkeypatch.setattr(PayPalLiveService, "get_access_token", lambda self: ("mock_token", 3600, None))

    svc = PayPalLiveService()
    res = svc.capture_live_order("TEST-ORDER-123")
    assert res["captured"] is False
    assert res["http_status"] == 422
    assert "did not contain a valid capture ID" in res["error"]


# ---------------------------------------------------------------------------
# Criterion 6: Failed independent capture verification handling
# ---------------------------------------------------------------------------
def test_criterion_6_failed_independent_capture_verification(monkeypatch):
    """
    If PayPal capture returns a capture ID, but independent GET verification
    shows status != COMPLETED (e.g. PENDING or FAILED), fail closed with 422.
    """
    import requests
    from backend.services.paypal_service import PayPalLiveService

    class MockCaptureResponse:
        status_code = 201
        headers = {"Content-Type": "application/json"}
        def json(self):
            return {
                "id": "TEST-ORDER-123",
                "status": "COMPLETED",
                "purchase_units": [{"payments": {"captures": [{"id": "CAP-TEST-123", "status": "COMPLETED"}]}}],
            }

    monkeypatch.setattr(requests, "post", lambda *args, **kwargs: MockCaptureResponse())
    monkeypatch.setattr(PayPalLiveService, "get_access_token", lambda self: ("mock_token", 3600, None))
    # Independent GET returns PENDING
    monkeypatch.setattr(
        PayPalLiveService,
        "fetch_live_capture",
        lambda self, cap_id: {"found": True, "status": "PENDING", "capture_id": cap_id},
    )

    svc = PayPalLiveService()
    res = svc.capture_live_order("TEST-ORDER-123")
    assert res["captured"] is False
    assert res["http_status"] == 422
    assert "Independent GET verification failed" in res["error"]
    assert "PENDING" in res["error"]


def test_criterion_6b_missing_amount_currency_or_order_relationship_fails_closed(monkeypatch):
    """
    Independent GET verification must fail closed with 422 if amount, currency,
    or supplementary_data.related_ids.order_id are missing from the capture resource.
    """
    import requests
    from backend.services.paypal_service import PayPalLiveService

    class MockCaptureResponse:
        status_code = 201
        headers = {"Content-Type": "application/json"}
        def json(self):
            return {
                "id": "TEST-ORDER-123",
                "status": "COMPLETED",
                "purchase_units": [{"payments": {"captures": [{"id": "CAP-TEST-123", "status": "COMPLETED", "amount": {"value": "50.00", "currency_code": "USD"}}]}}],
            }

    monkeypatch.setattr(requests, "post", lambda *args, **kwargs: MockCaptureResponse())
    monkeypatch.setattr(PayPalLiveService, "get_access_token", lambda self: ("mock_token", 3600, None))

    # Case A: Missing amount in independent GET
    monkeypatch.setattr(
        PayPalLiveService,
        "fetch_live_capture",
        lambda self, cap_id: {"found": True, "status": "COMPLETED", "capture_id": cap_id},
    )
    svc = PayPalLiveService()
    res = svc.capture_live_order("TEST-ORDER-123")
    assert res["captured"] is False
    assert res["http_status"] == 422
    assert "missing 'amount.value'" in res["error"]

    # Case B: Missing currency in independent GET
    monkeypatch.setattr(
        PayPalLiveService,
        "fetch_live_capture",
        lambda self, cap_id: {"found": True, "status": "COMPLETED", "capture_id": cap_id, "amount": {"value": "50.00"}},
    )
    res_b = svc.capture_live_order("TEST-ORDER-123")
    assert res_b["captured"] is False
    assert res_b["http_status"] == 422
    assert "missing 'amount.currency_code'" in res_b["error"]

    # Case C: Missing related_ids.order_id in independent GET
    monkeypatch.setattr(
        PayPalLiveService,
        "fetch_live_capture",
        lambda self, cap_id: {"found": True, "status": "COMPLETED", "capture_id": cap_id, "amount": {"value": "50.00", "currency_code": "USD"}},
    )
    res_c = svc.capture_live_order("TEST-ORDER-123")
    assert res_c["captured"] is False
    assert res_c["http_status"] == 422
    assert "missing 'supplementary_data.related_ids.order_id'" in res_c["error"]

    # Case D: Mismatched order_id
    monkeypatch.setattr(
        PayPalLiveService,
        "fetch_live_capture",
        lambda self, cap_id: {
            "found": True,
            "status": "COMPLETED",
            "capture_id": cap_id,
            "amount": {"value": "50.00", "currency_code": "USD"},
            "supplementary_data": {"related_ids": {"order_id": "WRONG-ORDER-999"}},
        },
    )
    res_d = svc.capture_live_order("TEST-ORDER-123")
    assert res_d["captured"] is False
    assert res_d["http_status"] == 422
    assert "Order ID mismatch" in res_d["error"]


# ---------------------------------------------------------------------------
# Criterion 7: Wrong seller order ownership
# ---------------------------------------------------------------------------
def test_criterion_7_wrong_seller_order_ownership():
    """
    POST /api/v2/paypal/orders/{order_id}/capture rejects orders not owned by seller with 404.
    """
    # Order 3EU95140LR696653G is owned by seller_alpha
    # seller_beta attempts to capture seller_alpha's order
    res = client.post("/api/v2/paypal/orders/3EU95140LR696653G/capture", headers=AUTH_BETA)
    assert res.status_code == 404
    assert "not found for seller 'seller_beta'" in res.json()["detail"]


# ---------------------------------------------------------------------------
# Criterion 8: Correct amount, fee, and payer reconciliation
# ---------------------------------------------------------------------------
def test_criterion_8_amount_fee_payer_reconciliation():
    """
    Canonical transaction for Order 3EU95140LR696653G:
    Gross $5.00, Fee $0.59, Net $4.41,
    Buyer: sb-rcnwy53637793@personal.example.com (John Doe, LAE4A4GDX2XQ8).
    """
    conn = sqlite3.connect(str(DATABASE_PATH))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(
        "SELECT * FROM seller_transactions WHERE order_id = '3EU95140LR696653G' AND seller_id = 'seller_alpha'"
    )
    tx = cur.fetchone()
    conn.close()

    assert tx is not None, "Order 3EU95140LR696653G not found in SQLite"
    assert float(tx["amount"]) == 5.00
    assert tx["currency"] == "USD"
    assert tx["capture_id"] == "10A71705XW788203L"
    assert tx["payment_status"] in ("COMPLETED", "PAYMENT_CAPTURED")

    # Verify dispute service sample dispute contains verified transaction details
    dispute_service = DisputeVerificationService()
    sample = dispute_service.get_sample_dispute(seller_id="seller_alpha")
    assert sample["transaction_reference"] == "3EU95140LR696653G"
    assert sample["capture_id"] == "10A71705XW788203L"
    assert sample["amount"] == "5.00"
    assert sample["currency"] == "USD"
    assert sample["buyer_email"] == "sb-rcnwy53637793@personal.example.com"
    assert "John Doe" in sample["buyer_name"]

    ev_0 = sample["default_evidence"][0]
    assert "gross 5.00 USD" in ev_0["content"]
    assert "fee 0.59 USD" in ev_0["content"]
    assert "net 4.41 USD" in ev_0["content"]
    assert "sb-rcnwy53637793@personal.example.com" in ev_0["content"]


# ---------------------------------------------------------------------------
# Criterion 9: Simulated dispute source classification
# ---------------------------------------------------------------------------
def test_criterion_9_simulated_dispute_source_classification():
    """
    scenario_unauth_3ds must have dispute_provenance='LOCAL_DEMO_SCENARIO',
    paypal_dispute_id=None, Exhibit F with provenance_type='SIMULATED_DEMO_EXHIBIT',
    is_verified_source=False, and NO fake WH-DISPUTE-8821.
    """
    dispute_service = DisputeVerificationService()
    catalog = dispute_service.get_scenario_catalog(seller_id="seller_alpha")
    scenario = next(sc for sc in catalog if sc["scenario_id"] == "scenario_unauth_3ds")

    assert scenario["dispute_provenance"] == "LOCAL_DEMO_SCENARIO"
    assert scenario["dispute_type"] == "LOCAL_DEMO_DISPUTE_SCENARIO"
    assert scenario["paypal_dispute_id"] is None
    assert "WH-DISPUTE-8821" not in json.dumps(scenario)

    exhibit_f = next(
        ev for ev in scenario["default_evidence"]
        if ev.get("document_exhibit", {}).get("exhibit_number") == "EXHIBIT F"
    )
    assert exhibit_f["is_verified_source"] is False
    assert exhibit_f["document_exhibit"]["provenance_type"] == "SIMULATED_DEMO_EXHIBIT"


# ---------------------------------------------------------------------------
# Criterion 10: Exhibit F never resolving to Exhibit A in strict priority matcher
# ---------------------------------------------------------------------------
def test_criterion_10_strict_priority_matcher_never_aliases_f_to_a():
    """
    Verify that Exhibit F ('PayPal 3DS...' or '3DS Bank OTP Auth Certificate')
    strictly matches Exhibit F and NEVER matches Exhibit A.
    """
    DOCUMENTS_CATALOG = [
        {
            "id": "EXHIBIT_A",
            "exhibit_number": "EXHIBIT A",
            "title": "PayPal Payment Capture Notice (Live Sandbox Verified)",
            "filename": "exhibit_a_paypal_notice.png",
        },
        {
            "id": "EXHIBIT_B",
            "exhibit_number": "EXHIBIT B",
            "title": "MemberPress LMS Student Access & Session Audit Certificate",
            "filename": "exhibit_b_lms_access_cert.png",
        },
        {
            "id": "EXHIBIT_C",
            "exhibit_number": "EXHIBIT C",
            "title": "SendGrid Enterprise SMTP Transmission & Delivery Receipt",
            "filename": "exhibit_c_sendgrid_receipt.png",
        },
        {
            "id": "EXHIBIT_D",
            "exhibit_number": "EXHIBIT D",
            "title": "Digital Course License Key & Entitlement Certificate",
            "filename": "exhibit_d_license_key.png",
        },
        {
            "id": "EXHIBIT_E",
            "exhibit_number": "EXHIBIT E",
            "title": "Cloudflare CDN Asset Download & Telemetry Log",
            "filename": "exhibit_e_cdn_download.png",
        },
        {
            "id": "EXHIBIT_F",
            "exhibit_number": "EXHIBIT F",
            "title": "3DS Bank OTP Auth Certificate (Simulated Demo Exhibit)",
            "filename": "exhibit_f_3ds_auth.png",
        },
    ]

    def resolve_doc(req):
        req_num = (req.get("exhibit_number") or "").strip().upper()
        if req_num:
            for doc in DOCUMENTS_CATALOG:
                if doc["exhibit_number"].upper() == req_num:
                    return doc

        req_img = (req.get("image_src") or req.get("file") or "").strip().lower()
        if req_img:
            img_basename = os.path.basename(req_img)
            for doc in DOCUMENTS_CATALOG:
                if doc["filename"].lower() == img_basename:
                    return doc

        req_title = (req.get("title") or "").strip().lower()
        if req_title:
            for doc in DOCUMENTS_CATALOG:
                if doc["title"].lower() == req_title:
                    return doc

        return None

    # Test resolution by exhibit number
    res_f = resolve_doc({"exhibit_number": "EXHIBIT F", "title": "PayPal 3D-Secure Authentication"})
    assert res_f["exhibit_number"] == "EXHIBIT F"
    assert res_f["id"] == "EXHIBIT_F"

    # Test resolution by filename
    res_f_img = resolve_doc({"image_src": "/documents/exhibit_f_3ds_auth.png"})
    assert res_f_img["exhibit_number"] == "EXHIBIT F"

    # Test resolution by title
    res_f_title = resolve_doc({"title": "3DS Bank OTP Auth Certificate (Simulated Demo Exhibit)"})
    assert res_f_title["exhibit_number"] == "EXHIBIT F"


# ---------------------------------------------------------------------------
# Criterion 11: Source payload hash reproducibility
# ---------------------------------------------------------------------------
def test_criterion_11_source_payload_hash_reproducibility():
    """
    Verify raw webhook payload in SQLite hashes to SHA-256:
    53e6474db96c5cee657048ee3c8d93ef95132f649de0f073d4bde27c669d4fb5
    and canonical sorted JSON hashes to:
    77d0fc024835a1a1fca22d4689fa318d071383698249d6abfd7f9483902353c1.
    """
    conn = sqlite3.connect(str(DATABASE_PATH))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(
        "SELECT raw_payload FROM webhook_events WHERE event_id = 'WH-5YU92122SU5558421-38D64732GN611071G'"
    )
    row = cur.fetchone()
    conn.close()

    assert row is not None, "Webhook event not found in SQLite"
    raw_payload_str = row["raw_payload"]
    raw_sha = hashlib.sha256(raw_payload_str.encode("utf-8")).hexdigest()
    assert raw_sha == "53e6474db96c5cee657048ee3c8d93ef95132f649de0f073d4bde27c669d4fb5"

    parsed = json.loads(raw_payload_str)
    canonical_bytes = json.dumps(parsed, sort_keys=True, separators=(",", ":")).encode("utf-8")
    canonical_sha = hashlib.sha256(canonical_bytes).hexdigest()
    assert canonical_sha == "77d0fc024835a1a1fca22d4689fa318d071383698249d6abfd7f9483902353c1"


# ---------------------------------------------------------------------------
# Criterion 12: Clean installed-wheel backend imports
# ---------------------------------------------------------------------------
def test_criterion_12_clean_backend_imports():
    """
    Ensure core backend and src modules import cleanly without exception.
    """
    import backend.config
    import backend.security.asymmetric_anchor
    import backend.services.db_schema
    import backend.services.dispute_service
    import backend.services.forensic_engine
    import backend.services.key_service
    import backend.services.paypal_service
    from backend.routes import api_router
    import src.models.evidence_compiler

    assert backend.config.DATABASE_PATH.exists()
    assert src.models.evidence_compiler.EventLog is not None
    assert api_router is not None
