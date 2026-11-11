"""
Final Sprint Verification Tests:
- Real-time 10-stage SSE streaming (/analyze-stream)
- Strict evidence taxonomy (LOOKUP_NOT_CONFIGURED, FORMAT_VALID, VERIFIED_ON_MERCHANT_RECORD)
- File upload persistence (/upload-evidence)
- Server-side approval digest binding & stale/modified approval rejection
- Cross-tenant approval isolation
- Local demo live-submission rejection (require_live_paypal=True)
"""
import json
import sys
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.main import app
from backend.services.db_schema import init_saas_schema

init_saas_schema()
client = TestClient(app)

ALPHA_HEADERS = {"Authorization": "Bearer key_alpha_123"}
BETA_HEADERS = {"Authorization": "Bearer key_beta_456"}


def test_sse_10_stage_analyze_stream():
    res = client.post(
        "/api/v2/disputes/DSP-3EU95140-01/analyze-stream",
        json={
            "carrier_name": "USPS",
            "tracking_number": "9400111899223192348571",
            "fulfillment_notes": "Shipped to verified buyer address.",
        },
        headers=ALPHA_HEADERS,
    )
    assert res.status_code == 200
    assert "text/event-stream" in res.headers["content-type"]

    frames = [f for f in res.text.split("\n\n") if f.strip()]
    events = []
    for frame in frames:
        line = next((l for l in frame.split("\n") if l.startswith("data: ")), None)
        if line:
            events.append(json.loads(line[6:]))

    stage_events = [e["stage"] for e in events if e.get("event") == "stage"]
    complete_events = [e["result"] for e in events if e.get("event") == "complete"]

    assert len(stage_events) == 10
    assert [s["step"] for s in stage_events] == list(range(1, 11))
    assert len(complete_events) == 1

    result = complete_events[0]
    assert "evidence_digest" in result and len(result["evidence_digest"]) == 64
    statuses = {ev["item"]: ev["status"] for ev in result["evidence_items"]}
    assert statuses["Payment & Capture Record"] == "VERIFIED_ON_MERCHANT_RECORD"
    assert statuses["Tracking Number"] == "FORMAT_VALID"
    assert statuses["Carrier Delivery Scan"] == "LOOKUP_NOT_CONFIGURED"
    assert "Not found" not in json.dumps(result["evidence_items"])


def test_evidence_file_upload_persists_sha256():
    res = client.post(
        "/api/v2/disputes/DSP-3EU95140-01/upload-evidence",
        files={"file": ("carrier_receipt.pdf", b"%PDF-1.4 fake delivery receipt bytes", "application/pdf")},
        headers=ALPHA_HEADERS,
    )
    assert res.status_code == 200
    data = res.json()
    assert data["filename"] == "carrier_receipt.pdf"
    assert data["size_bytes"] == len(b"%PDF-1.4 fake delivery receipt bytes")
    assert len(data["file_sha256"]) == 64
    assert "carrier_receipt.pdf" in data["proof_document_url"]


def test_server_side_approval_digest_and_invalidation():
    dispute_id = "DSP-TEST-APPR-SPRINT-01"

    # 1. Obtain server-side approval receipt
    appr_res = client.post(
        f"/api/v2/disputes/{dispute_id}/approve-evidence",
        json={
            "carrier_name": "USPS",
            "tracking_number": "9400111899223192348571",
            "evidence_notes": "Original approved draft text.",
            "signature_confirmed": True,
        },
        headers=ALPHA_HEADERS,
    )
    assert appr_res.status_code == 200
    appr = appr_res.json()
    assert appr["human_approved"] is True
    assert len(appr["evidence_digest"]) == 64

    # 2. Tamper with draft after approval -> MUST reject with 409 STALE_OR_MODIFIED_APPROVAL
    stale_res = client.post(
        f"/api/v2/disputes/{dispute_id}/provide-evidence",
        json={
            "carrier_name": "USPS",
            "tracking_number": "9400111899223192348571",
            "evidence_notes": "Modified draft AFTER approval!",
            "merchant_approved": True,
            "approval_id": appr["approval_id"],
            "approved_digest": appr["evidence_digest"],
        },
        headers=ALPHA_HEADERS,
    )
    assert stale_res.status_code == 409
    assert "STALE_OR_MODIFIED_APPROVAL" in stale_res.json()["detail"]

    # 3. Cross-tenant seller_beta tries to use seller_alpha's approval -> MUST reject 403
    cross_res = client.post(
        f"/api/v2/disputes/{dispute_id}/provide-evidence",
        json={
            "carrier_name": "USPS",
            "tracking_number": "9400111899223192348571",
            "evidence_notes": "Original approved draft text.",
            "merchant_approved": True,
            "approval_id": appr["approval_id"],
            "approved_digest": appr["evidence_digest"],
        },
        headers=BETA_HEADERS,
    )
    assert cross_res.status_code == 403
    assert "INVALID_APPROVAL" in cross_res.json()["detail"]

    # 4. require_live_paypal=True on local demo scenario -> MUST reject 400
    live_guard_res = client.post(
        f"/api/v2/disputes/{dispute_id}/provide-evidence",
        json={
            "carrier_name": "USPS",
            "tracking_number": "9400111899223192348571",
            "evidence_notes": "Original approved draft text.",
            "merchant_approved": True,
            "approval_id": appr["approval_id"],
            "approved_digest": appr["evidence_digest"],
            "require_live_paypal": True,
        },
        headers=ALPHA_HEADERS,
    )
    assert live_guard_res.status_code == 400
    assert "LOCAL_DEMO_NOT_LIVE_PAYPAL" in live_guard_res.json()["detail"]
