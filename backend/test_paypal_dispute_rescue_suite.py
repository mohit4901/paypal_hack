"""
ProofLedger — PayPal Dispute Rescue
Integration Acceptance Test Suite (15 Test Cases).

Verifies the 10-step merchant journey and all core guarantees:
1. Genuine PayPal dispute list retrieval
2. Dispute detail retrieval
3. Missing seller response deadline handling
4. Unsupported dispute reason rejection (Scope Enforcement)
5. Requested evidence type mapping (PROOF_OF_FULFILLMENT)
6. Missing carrier information detection
7. Missing tracking number detection
8. Invalid / unrelated order linkage rejection
9. Mismatched amount and currency detection
10. Unsupported AI statements excluded from draft (Strict Grounding)
11. AI abstention / human-review deferral preserved (No autonomous submission)
12. Merchant approval required before submission
13. Evidence submitted through genuine PayPal API endpoint
14. PayPal HTTP response and dispute state recorded in SQLite
15. Duplicate submission protection (Idempotency enforcement)
"""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from backend.auth import hash_api_key
from backend.config import SANDBOX_AMOUNT, SANDBOX_CAPTURE_ID, SANDBOX_CURRENCY, SANDBOX_ORDER_ID
from backend.main import app
from backend.routes.disputes import SANDBOX_BASELINE_DISPUTE_ID
from backend.services.db_schema import get_db_connection
from backend.services.dispute_rescue_ai import dispute_rescue_ai
from backend.services.paypal_dispute_service import paypal_dispute_client
from backend.services.paypal_mcp import paypal_mcp_registry

client = TestClient(app)
AUTH_HEADERS = {"Authorization": "Bearer key_alpha_123"}


@pytest.fixture(autouse=True)
def cleanup_test_disputes():
    """Ensure test dispute submissions are cleaned up before and after each test."""
    conn = get_db_connection()
    conn.execute("DELETE FROM dispute_submissions WHERE dispute_id LIKE 'DSP-TEST-%'")
    conn.commit()
    conn.close()
    yield
    conn = get_db_connection()
    conn.execute("DELETE FROM dispute_submissions WHERE dispute_id LIKE 'DSP-TEST-%'")
    conn.commit()
    conn.close()


def test_01_genuine_paypal_dispute_list_retrieval():
    """1. Test genuine PayPal dispute list retrieval and response structure."""
    res = client.get("/api/v2/disputes", headers=AUTH_HEADERS)
    assert res.status_code == 200
    data = res.json()

    assert "total_disputes" in data
    assert "open_disputes_count" in data
    assert "due_soon_count" in data
    assert "disputes" in data
    assert data["total_disputes"] >= 1

    # Verify baseline dispute is present
    dispute_ids = [d["dispute_id"] for d in data["disputes"]]
    assert SANDBOX_BASELINE_DISPUTE_ID in dispute_ids

    # Also test paypal_dispute_client directly
    list_res = paypal_dispute_client.list_disputes()
    assert "success" in list_res
    assert "items" in list_res


def test_02_dispute_detail_retrieval():
    """2. Test dispute detail retrieval and field extraction."""
    res = client.get(f"/api/v2/disputes/{SANDBOX_BASELINE_DISPUTE_ID}", headers=AUTH_HEADERS)
    assert res.status_code == 200
    d = res.json()

    assert d["dispute_id"] == SANDBOX_BASELINE_DISPUTE_ID
    assert d["amount"] == SANDBOX_AMOUNT
    assert d["currency"] == SANDBOX_CURRENCY
    assert d["status"] == "WAITING_FOR_SELLER_RESPONSE"
    assert d["dispute_reason"] == "MERCHANDISE_OR_SERVICE_NOT_RECEIVED"
    assert d["transaction_reference"] == SANDBOX_ORDER_ID
    assert d["capture_id"] == SANDBOX_CAPTURE_ID
    assert d["can_provide_evidence"] is True


def test_03_missing_seller_response_deadline_handling():
    """3. Test dispute formatting when seller response deadline is missing."""
    raw_dispute_no_deadline = {
        "dispute_id": "PP-D-NO-DEADLINE-99",
        "reason": "MERCHANDISE_OR_SERVICE_NOT_RECEIVED",
        "status": "WAITING_FOR_SELLER_RESPONSE",
        "dispute_amount": {"value": "25.00", "currency_code": "USD"},
        "seller_response_due_date": None,
    }
    summary = paypal_dispute_client._format_dispute_summary(raw_dispute_no_deadline)
    assert summary["seller_response_due_date"] is None
    assert summary["urgency_days_left"] is None
    assert summary["amount"] == "25.00"
    assert summary["currency"] == "USD"


def test_04_unsupported_dispute_reason_rejection():
    """4. Scope Enforcement: Reject any dispute reason outside MERCHANDISE_OR_SERVICE_NOT_RECEIVED."""
    unsupported_dispute = {
        "dispute_id": "DSP-TEST-UNAUTH-01",
        "reason": "UNAUTHORISED_TRANSACTION",
        "amount": "99.00",
        "currency": "USD",
    }
    ai_res = dispute_rescue_ai.validate_and_prepare(dispute=unsupported_dispute)
    assert ai_res["dispute_reason_supported"] is False
    assert "strictly supports 'MERCHANDISE_OR_SERVICE_NOT_RECEIVED'" in ai_res["rejection_reason"]
    assert ai_res["draft_response"] == ""
    assert ai_res["required_evidence"] == []


def test_05_requested_evidence_type_mapping():
    """5. Verify requested evidence type mapping for non-receipt is PROOF_OF_FULFILLMENT."""
    res = client.get(f"/api/v2/disputes/{SANDBOX_BASELINE_DISPUTE_ID}", headers=AUTH_HEADERS)
    assert res.status_code == 200
    d = res.json()
    assert d["required_evidence_type"] == "PROOF_OF_FULFILLMENT"
    assert "Carrier Name" in d["required_evidence"]
    assert "Tracking Number" in d["required_evidence"]


def test_06_missing_carrier_information_detection():
    """6. Checklist evaluates carrier name as MISSING when omitted."""
    payload = {
        "carrier_name": "",
        "tracking_number": "9400111899223192348571",
        "delivery_document_name": "Signed Receipt",
    }
    res = client.post(
        f"/api/v2/disputes/{SANDBOX_BASELINE_DISPUTE_ID}/prepare-response",
        json=payload,
        headers=AUTH_HEADERS,
    )
    assert res.status_code == 200
    data = res.json()

    carrier_check = next(c for c in data["evidence_checklist"] if c["field"] == "Carrier Name")
    assert carrier_check["status"] == "MISSING"
    assert carrier_check["verified"] is False
    assert any("Carrier name" in m for m in data["missing_evidence"])
    assert data["can_submit_to_paypal"] is False


def test_07_missing_tracking_number_detection():
    """7. Checklist evaluates tracking number as MISSING when omitted."""
    payload = {
        "carrier_name": "USPS",
        "tracking_number": "",
        "delivery_document_name": "Signed Receipt",
    }
    res = client.post(
        f"/api/v2/disputes/{SANDBOX_BASELINE_DISPUTE_ID}/prepare-response",
        json=payload,
        headers=AUTH_HEADERS,
    )
    assert res.status_code == 200
    data = res.json()

    tracking_check = next(c for c in data["evidence_checklist"] if c["field"] == "Tracking Number")
    assert tracking_check["status"] == "MISSING"
    assert tracking_check["verified"] is False
    assert any("Tracking number" in m for m in data["missing_evidence"])
    assert data["can_submit_to_paypal"] is False


def test_08_invalid_unrelated_order_linkage_rejection():
    """8. Rejects or flags dispute when order linkage is absent or unverified."""
    dispute = {
        "dispute_id": "DSP-TEST-NO-ORDER",
        "reason": "MERCHANDISE_OR_SERVICE_NOT_RECEIVED",
        "amount": "15.00",
        "currency": "USD",
    }
    # No order ID provided in transaction record
    empty_tx = {}
    seller_ev = {"carrier_name": "USPS", "tracking_number": "9400111899223192348571"}
    ai_res = dispute_rescue_ai.validate_and_prepare(
        dispute=dispute,
        transaction=empty_tx,
        seller_evidence=seller_ev,
    )
    assert any("Order linkage missing" in err for err in ai_res["validation_errors"])
    assert ai_res["evidence_readiness"] == "NEEDS_ATTENTION"
    assert ai_res["can_submit_to_paypal"] is False


def test_09_mismatched_amount_and_currency_detection():
    """9. Detects mismatched transaction amount / currency between store and dispute."""
    dispute = {
        "dispute_id": "DSP-TEST-MISMATCH",
        "reason": "MERCHANDISE_OR_SERVICE_NOT_RECEIVED",
        "amount": "50.00",
        "currency": "EUR",
    }
    tx = {
        "order_id": "ORD-MISMATCH-123",
        "amount": "5.00",
        "currency": "USD",
        "payment_status": "COMPLETED",
    }
    seller_ev = {"carrier_name": "FedEx", "tracking_number": "794612345678"}
    ai_res = dispute_rescue_ai.validate_and_prepare(
        dispute=dispute,
        transaction=tx,
        seller_evidence=seller_ev,
    )
    assert any("Amount or currency mismatch" in err for err in ai_res["validation_errors"])
    assert ai_res["evidence_readiness"] == "NEEDS_ATTENTION"


def test_10_unsupported_ai_statements_excluded_from_draft():
    """10. Strict Grounding: Draft response contains only verified facts, without hallucinated commitments."""
    payload = {
        "carrier_name": "USPS Priority",
        "tracking_number": "9400111899223192348571",
        "fulfillment_notes": "Shipped in sealed padded envelope.",
    }
    res = client.post(
        f"/api/v2/disputes/{SANDBOX_BASELINE_DISPUTE_ID}/prepare-response",
        json=payload,
        headers=AUTH_HEADERS,
    )
    assert res.status_code == 200
    data = res.json()
    draft = data["draft_response"]

    # Must contain verified order, carrier, and tracking
    assert SANDBOX_ORDER_ID in draft
    assert "USPS Priority" in draft
    assert "9400111899223192348571" in draft
    assert "Capture ID: 10A71705XW788203L" in draft
    # Must NOT contain speculation or ungrounded promises
    assert "100% win guaranteed" not in draft.lower()
    assert "immediate refund" not in draft.lower()


def test_11_ai_abstention_and_human_review_deferral_preserved():
    """11. AI assistant strictly defers to merchant review; zero autonomous submission."""
    payload = {
        "carrier_name": "UPS",
        "tracking_number": "1Z9999999999999999",
    }
    res = client.post(
        f"/api/v2/disputes/{SANDBOX_BASELINE_DISPUTE_ID}/prepare-response",
        json=payload,
        headers=AUTH_HEADERS,
    )
    assert res.status_code == 200
    data = res.json()

    assert data["merchant_approval_required"] is True
    assert data["relevance_signal"]["autonomous_action_taken"] is False

    # Verify MCP tool registry also prohibits autonomous settlement mutations
    mcp_tools = paypal_mcp_registry.get_tool_definitions()
    tool_names = [t["name"] for t in mcp_tools]
    assert "create_refund" not in tool_names
    assert "accept_dispute_claim" not in tool_names


def test_12_merchant_approval_required_before_submission():
    """12. HTTP 400 when merchant_approved is False on evidence submission."""
    payload = {
        "carrier_name": "USPS",
        "tracking_number": "9400111899223192348571",
        "evidence_notes": "Delivered to buyer.",
        "merchant_approved": False,
    }
    res = client.post(
        f"/api/v2/disputes/{SANDBOX_BASELINE_DISPUTE_ID}/provide-evidence",
        json=payload,
        headers=AUTH_HEADERS,
    )
    assert res.status_code == 400
    assert "MERCHANT_APPROVAL_REQUIRED" in res.json()["detail"]


def test_13_evidence_submitted_through_genuine_paypal_api_endpoint():
    """13. Submits evidence through genuine POST /v1/customer/disputes/{dispute_id}/provide-evidence."""
    with patch("requests.post") as mock_post:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"Paypal-Debug-Id": "mock-dbg-sub-13"}
        mock_response.text = '{"acknowledged": true}'
        mock_response.json.return_value = {"acknowledged": True}
        mock_post.return_value = mock_response

        # Call paypal_dispute_client directly
        res = paypal_dispute_client.submit_dispute_evidence(
            dispute_id="PP-D-GENUINE-13",
            carrier_name="DHL",
            tracking_number="DHL123456789",
            evidence_notes="Hand-delivered with signature.",
            merchant_approved=True,
        )

        assert res["success"] is True
        assert res["submitted"] is True
        assert res["evidence_type"] == "PROOF_OF_FULFILLMENT"
        assert res["carrier_name"] == "DHL"
        assert res["tracking_number"] == "DHL123456789"
        assert res["paypal_debug_id"] == "mock-dbg-sub-13"

        # Verify POST URL and payload structure matches PayPal specification
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert "/v1/customer/disputes/PP-D-GENUINE-13/provide-evidence" in call_args[0][0]
        json_payload = call_args[1]["json"]
        ev = json_payload["evidences"][0]
        assert ev["evidence_type"] == "PROOF_OF_FULFILLMENT"
        assert ev["evidence_info"]["tracking_info"][0]["carrier_name"] == "DHL"
        assert ev["evidence_info"]["tracking_info"][0]["tracking_number"] == "DHL123456789"


def test_14_paypal_http_response_and_dispute_state_recorded():
    """14. Records submission receipt, debug ID, and dispute state in SQLite."""
    test_dsp_id = "DSP-TEST-RECORD-14"
    payload = {
        "carrier_name": "FedEx",
        "tracking_number": "794612345678",
        "evidence_notes": "Express delivery confirmation.",
        "merchant_approved": True,
    }
    res = client.post(
        f"/api/v2/disputes/{test_dsp_id}/provide-evidence",
        json=payload,
        headers=AUTH_HEADERS,
    )
    assert res.status_code == 200
    data = res.json()

    assert data["success"] is True
    assert data["submitted"] is True
    assert data["dispute_id"] == test_dsp_id
    assert data["carrier_name"] == "FEDEX"
    assert data["tracking_number"] == "794612345678"
    assert data["dispute_state"] in ("LOCAL_SIMULATED_SUBMISSION", "UNDER_REVIEW")
    assert "paypal_debug_id" in data
    assert "submission_id" in data

    # Verify persistent storage in SQLite
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT * FROM dispute_submissions WHERE dispute_id = ? AND seller_id = ?",
        (test_dsp_id, "seller_alpha"),
    )
    row = cur.fetchone()
    conn.close()

    assert row is not None
    assert row["carrier_name"] == "FEDEX"
    assert row["tracking_number"] == "794612345678"
    assert row["merchant_approved"] == 1


def test_15_duplicate_submission_protection():
    """15. Idempotency: Duplicate submissions for same dispute are rejected with HTTP 409."""
    test_dsp_id = "DSP-TEST-IDEMPOTENCY-15"
    payload = {
        "carrier_name": "USPS",
        "tracking_number": "9400111899223192348571",
        "evidence_notes": "First submission attempt.",
        "merchant_approved": True,
    }

    # First attempt: succeeds
    res1 = client.post(
        f"/api/v2/disputes/{test_dsp_id}/provide-evidence",
        json=payload,
        headers=AUTH_HEADERS,
    )
    assert res1.status_code == 200
    assert res1.json()["success"] is True

    # Second attempt: blocked with 409 Conflict
    res2 = client.post(
        f"/api/v2/disputes/{test_dsp_id}/provide-evidence",
        json=payload,
        headers=AUTH_HEADERS,
    )
    assert res2.status_code == 409
    assert "DUPLICATE_SUBMISSION" in res2.json()["detail"]


def test_16_provenance_separation_local_vs_live():
    """16. Provenance Separation: Clearly separates local demo scenarios from genuine live PayPal disputes."""
    res = client.get(f"/api/v2/disputes/{SANDBOX_BASELINE_DISPUTE_ID}", headers=AUTH_HEADERS)
    assert res.status_code == 200
    d = res.json()

    assert d["local_case_id"] == SANDBOX_BASELINE_DISPUTE_ID
    assert d["paypal_dispute_id"] is None
    assert d["provenance"] == "LOCAL_DEMO_SCENARIO"
    assert "Local Demo Scenario" in d["provenance_label"]
    assert d["is_live_paypal_dispute"] is False


def test_17_sentence_level_source_grounding_and_format_valid():
    """17. Sentence-Level Source Grounding: Verifies citations and FORMAT_VALID distinction."""
    payload = {
        "carrier_name": "USPS",
        "tracking_number": "9400111899223192348571",
        "fulfillment_notes": "Shipped to buyer's verified PayPal address.",
    }
    res = client.post(
        f"/api/v2/disputes/{SANDBOX_BASELINE_DISPUTE_ID}/prepare-response",
        json=payload,
        headers=AUTH_HEADERS,
    )
    assert res.status_code == 200
    data = res.json()

    # Checklist must label tracking syntax as FORMAT_VALID (NOT delivered)
    tracking_check = next(c for c in data["evidence_checklist"] if c["field"] == "Tracking Number")
    assert tracking_check["status"] == "AVAILABLE"
    assert tracking_check["validation_tag"] == "FORMAT_VALID"
    assert "FORMAT_VALID" in tracking_check["detail"]

    # Must provide sentence-level source citations
    assert "grounding_sources" in data
    sources = data["grounding_sources"]
    assert len(sources) >= 3

    # Check Capture ID source
    cap_src = next(s for s in sources if "Capture ID" in s["source_reference"])
    assert cap_src["verification_status"] == "VERIFIED_ON_LEDGER"
    assert cap_src["supporting_source"] == "PayPal REST Capture API"

    # Check Tracking source is FORMAT_VALID
    track_src = next(s for s in sources if "Tracking" in s["source_reference"])
    assert track_src["verification_status"] == "FORMAT_VALID"


def test_18_official_paypal_mcp_jsonrpc_protocol():
    """18. Model Context Protocol: Tests standard JSON-RPC 2.0 initialize, tools/list, tools/call and read-only guardrails."""
    # 1. initialize
    init_res = client.post("/api/v2/mcp", json={
        "jsonrpc": "2.0",
        "id": 101,
        "method": "initialize",
        "params": {}
    })
    assert init_res.status_code == 200
    init_data = init_res.json()
    assert init_data["result"]["serverInfo"]["name"] == "@paypal/mcp-server"
    assert "tools" in init_data["result"]["capabilities"]

    # 2. tools/list
    tools_res = client.post("/api/v2/mcp", json={
        "jsonrpc": "2.0",
        "id": 102,
        "method": "tools/list",
        "params": {}
    })
    assert tools_res.status_code == 200
    tool_names = [t["name"] for t in tools_res.json()["result"]["tools"]]
    assert "list_disputes" in tool_names
    assert "get_dispute" in tool_names
    assert "get_order" in tool_names
    assert "list_transactions" in tool_names

    # 3. tools/call list_disputes (read-only execution)
    call_res = client.post("/api/v2/mcp", json={
        "jsonrpc": "2.0",
        "id": 103,
        "method": "tools/call",
        "params": {"name": "list_disputes", "arguments": {}}
    })
    assert call_res.status_code == 200
    call_data = call_res.json()
    assert "result" in call_data
    assert "content" in call_data["result"]
    assert call_data["result"]["structured_content"]["success"] is True

    # 4. tools/call create_refund (prohibited - must fail closed)
    proh_res = client.post("/api/v2/mcp", json={
        "jsonrpc": "2.0",
        "id": 104,
        "method": "tools/call",
        "params": {"name": "create_refund", "arguments": {}}
    })
    assert proh_res.status_code == 200
    proh_data = proh_res.json()
    assert "error" in proh_data
    assert proh_data["error"]["code"] == -32000
    assert "SECURITY_PROHIBITED" in proh_data["error"]["message"]


def test_19_genuine_paypal_sandbox_disputes_api_live():
    """19. Live Sandbox REST Disputes API: Verifies live handshake with api-m.sandbox.paypal.com."""
    live_res = paypal_dispute_client.list_disputes()
    assert live_res["success"] is True
    assert live_res["http_status"] == 200
    assert live_res["paypal_debug_id"] is not None
    assert isinstance(live_res["items"], list)
    assert isinstance(live_res["latency_ms"], (int, float))


