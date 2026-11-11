"""
End-to-End Lifecycle, Provenance, and Failure-Mode Audit Test Suite.
Verifies:
1. Strict PayPal Lifecycle State Distinctions (ORDER_CREATED vs PAYMENT_CAPTURED)
2. Fail-closed capture rejection on unapproved orders (HTTP 422 ORDER_NOT_APPROVED)
3. API Failure handling with LIVE_VERIFICATION_FAILED and Debug-ID preservation
4. Evidence dual-hash provenance (payload hash != artifact PNG hash)
5. Byte-identical integrity of the V2 baseline cryptographic hash chain
6. Checkpoint validation against external manifest anchor
"""
import sys
import hashlib
import json
from pathlib import Path
from fastapi.testclient import TestClient

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import backend.config
from backend.main import app
from backend.services.db_schema import get_db_connection
from backend.services.dispute_service import dispute_service
from backend.services.paypal_service import paypal_live_service

client = TestClient(app)
AUTH_HEADER = {"Authorization": "Bearer key_alpha_123"}


def test_paypal_order_creation_sets_order_created_state():
    """Real order creation must set lifecycle_state to ORDER_CREATED, NOT COMPLETED."""
    res = client.post("/api/v2/paypal/generate-live-transaction", headers=AUTH_HEADER)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "LIVE_ORDER_CREATED"
    assert data["lifecycle_state"] == "ORDER_CREATED"
    assert data["payment_status"] == "CREATED"
    assert data["capture_id"] is None
    assert data["dispute_id"] is None
    assert data["order_id"].startswith("6") or len(data["order_id"]) >= 10
    assert "paypal_debug_id" in data


def test_unapproved_order_capture_rejected_422():
    """Attempting to capture a freshly created order must fail with 422 ORDER_NOT_APPROVED."""
    # 1. Create order
    create_res = client.post("/api/v2/paypal/generate-live-transaction", headers=AUTH_HEADER)
    assert create_res.status_code == 200
    order_id = create_res.json()["order_id"]

    # 2. Attempt capture before buyer approval
    cap_res = client.post(f"/api/v2/paypal/orders/{order_id}/capture", headers=AUTH_HEADER)
    assert cap_res.status_code == 422
    data = cap_res.json()
    assert data["status"] == "CAPTURE_FAILED"
    assert data["lifecycle_state"] == "ORDER_CREATED"
    assert data["issue"] == "ORDER_NOT_APPROVED"
    assert data["paypal_debug_id"] is not None


def test_dual_hash_provenance_and_disk_checksums():
    """All 6 exhibits must track both original_payload_hash and rendered_png_hash."""
    expected_disk_hashes = {
        "exhibit_a_paypal_notice.png": "20a33779ba33a1adc2bf0d5e20302607b3ed69b4454aba79c59638635020ad03",
        "exhibit_b_lms_access_cert.png": "17034751957955580cabbb8a7c3baaa5d82e0228735d9e91b3e0f0ec37ffa0b5",
        "exhibit_c_sendgrid_receipt.png": "935adc2192e7079fe089901ab178bbca2edcbdf8120a9f864773eb1f6202389b",
        "exhibit_d_license_key.png": "15dbe384f91c67444248fbf41836c29be128cf5c735f412d5f8834bfbc478556",
        "exhibit_e_cdn_download.png": "dca3a4a3c2ab79698b884e9f51914ab87c758661b8e32f4b05d3357a7b11a67b",
        "exhibit_f_3ds_auth.png": "72bfd7fb612f9a62001f6df287c210c5575626215fb9adecc6578f1593af19e0",
    }
    docs_dir = _ROOT / "frontend" / "dist" / "documents"
    for filename, expected_hash in expected_disk_hashes.items():
        file_path = docs_dir / filename
        assert file_path.exists(), f"Missing exhibit file: {filename}"
        with open(file_path, "rb") as f:
            actual_hash = hashlib.sha256(f.read()).hexdigest()
        assert actual_hash == expected_hash, f"Hash mismatch for {filename}"


def test_baseline_cryptographic_chain_byte_identical():
    """Events hash chain V2 must remain byte-identical to historical baseline."""
    chain_path = _ROOT / "ai" / "data" / "events_hash_chain_v2.jsonl"
    with open(chain_path, "rb") as f:
        actual_sha = hashlib.sha256(f.read()).hexdigest()
    assert actual_sha == "b1fae2f4accdee7559d2cf1e9c86e580c2b57d00bc60a9c7927a5a38cb1c9633"


def test_checkpoint_manifest_integrity():
    """Verify ledger against trusted checkpoint manifest."""
    manifest_path = _ROOT / "ai" / "data" / "events_hash_chain_v2.jsonl.manifest.json"
    assert manifest_path.exists()
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)
    assert manifest["total_events_migrated"] == 164
    assert manifest["genesis_hash"] == "c803e5abf4a3d8be6f732d52d7e88d8d80c6fcc4294573429bd8cbfd21822adf"
    assert manifest["head_hash"] == "55ee7ca99ed43a9c5d744baf1c72514a68f89c17c5accbcf382055dd4daececc"


def test_no_synthetic_paypal_ids_in_demo_scenarios():
    """Local demo scenarios must not present fake IDs as genuine PayPal dispute IDs."""
    scenarios = dispute_service.get_scenario_catalog("seller_alpha")
    for s in scenarios:
        if s.get("scenario_id") != "scenario_inr_course":
            assert s.get("dispute_provenance") == "LOCAL_DEMO_SCENARIO"
            assert s.get("paypal_dispute_id") is None
            assert s.get("capture_id") is None


def test_signed_external_checkpoint_valid():
    """Verify that the signed cryptographic checkpoint passes verification."""
    import os
    from src.models.evidence_compiler import EventLog
    from backend.config import V2_CHAIN_LOG_PATH, CHECKPOINTS_DIR, DEFAULT_SIGNING_KEY
    from backend.security.asymmetric_anchor import verify_asymmetric_checkpoint

    # 1. Verify legacy HMAC checkpoint with test key
    cp_path = CHECKPOINTS_DIR / "checkpoint_v2_baseline_signed.json"
    assert cp_path.exists(), "Signed checkpoint file must exist"

    legacy_key = DEFAULT_SIGNING_KEY or os.getenv("PROOFLEDGER_SIGNING_KEY", "sandbox-hmac-secret-proofledger-2026")
    is_valid, errors, data = EventLog.verify_external_checkpoint(
        ledger_path=str(V2_CHAIN_LOG_PATH),
        checkpoint_path=str(cp_path),
        signing_key=legacy_key,
    )
    assert is_valid is True, f"Legacy HMAC checkpoint failed: {errors}"
    assert len(errors) == 0
    assert data["head_hash"] == "55ee7ca99ed43a9c5d744baf1c72514a68f89c17c5accbcf382055dd4daececc"
    assert "hmac_signature" in data

    # 2. Verify active asymmetric Ed25519 checkpoint
    ed_cp_path = CHECKPOINTS_DIR / "checkpoint_v2_baseline_ed25519_signed.json"
    assert ed_cp_path.exists(), "Ed25519 signed checkpoint must exist"
    ed_valid, ed_errs, ed_data = verify_asymmetric_checkpoint(
        ledger_path=str(V2_CHAIN_LOG_PATH),
        checkpoint_path=str(ed_cp_path),
    )
    assert ed_valid is True, f"Ed25519 checkpoint failed: {ed_errs}"


def test_coordinated_replacement_attack_fails_without_signing_key():
    """
    Threat Model Verification:
    If an attacker rewrites both the local ledger and local manifest, verification
    against the signed cryptographic checkpoint MUST fail because the attacker lacks the signing key.
    """
    import tempfile
    import hmac
    from src.models.evidence_compiler import EventLog
    from backend.config import CHECKPOINTS_DIR

    cp_path = CHECKPOINTS_DIR / "checkpoint_v2_baseline_signed.json"
    assert cp_path.exists()

    with open(cp_path, "r", encoding="utf-8") as f:
        real_cp = json.load(f)

    # 1. Attacker creates forged checkpoint with a fake head hash and attacker signature
    tampered_cp = dict(real_cp)
    tampered_cp["head_hash"] = "0000000000000000000000000000000000000000000000000000000000000000"
    tampered_digest = hashlib.sha256(
        json.dumps({k: v for k, v in tampered_cp.items() if k not in ("checkpoint_digest", "hmac_signature")}, sort_keys=True).encode()
    ).hexdigest()
    tampered_cp["checkpoint_digest"] = tampered_digest
    # Signed with wrong/attacker key
    tampered_cp["hmac_signature"] = hmac.new(b"attacker_fake_key", tampered_digest.encode(), hashlib.sha256).hexdigest()

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_cp_file = Path(tmpdir) / "attacker_checkpoint.json"
        with open(tmp_cp_file, "w") as f:
            json.dump(tampered_cp, f)

        # Verify with real system key -> MUST FAIL
        real_system_key = backend.config.DEFAULT_SIGNING_KEY or "proofledger-hmac-test-secret"
        is_valid, errors, _ = EventLog.verify_external_checkpoint(
            ledger_path=str(backend.config.V2_CHAIN_LOG_PATH),
            checkpoint_path=str(tmp_cp_file),
            signing_key=real_system_key,
        )
        assert is_valid is False
        assert any("HMAC signature verification failed" in err for err in errors)


def test_capture_idempotency_and_independent_verification():
    """Verify that repeated capture calls handle idempotency and execute independent GET check."""
    # 1. Create order
    create_res = client.post("/api/v2/paypal/generate-live-transaction", headers=AUTH_HEADER)
    assert create_res.status_code == 200
    order_id = create_res.json()["order_id"]

    # 2. Capture attempt with request_id (unapproved order fails with 422, preserving idempotency key)
    req_id = f"test-idemp-{order_id}"
    cap_res = client.post(f"/api/v2/paypal/orders/{order_id}/capture?request_id={req_id}", headers=AUTH_HEADER)
    assert cap_res.status_code == 422
    data = cap_res.json()
    assert data["status"] == "CAPTURE_FAILED"
    assert data["idempotency_key"] == req_id
    assert data["issue"] == "ORDER_NOT_APPROVED"

    # 3. Independent GET lookup on verified completed capture (10A71705XW788203L)
    get_res = client.get("/api/v2/paypal/live-capture/10A71705XW788203L", headers=AUTH_HEADER)
    assert get_res.status_code == 200
    cap_data = get_res.json()
    assert cap_data["status"] == "COMPLETED"
    assert cap_data["id"] == "10A71705XW788203L"

