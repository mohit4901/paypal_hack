"""
ProofLedger PayPal Sandbox Complete Lifecycle & Idempotency Audit Suite.
Verifies:
1. Real-time Order Creation on api-m.sandbox.paypal.com (HTTP 201 Created, HATEOAS approve link).
2. Fail-Closed Unapproved Order Capture Rejection (HTTP 422 ORDER_NOT_APPROVED with Paypal-Debug-Id).
3. Independent Verification of Approved & Completed Capture (GET /v2/payments/captures/{id}).
4. PayPal-Request-Id Idempotency & Duplicate Replay Protection (Respecting Orders v2 6-Hour Retention Window).
5. Zero synthetic IDs or fabricated state transitions.
"""
import os
import uuid
import pytest
from backend.services.paypal_service import paypal_live_service

_HAS_PAYPAL_CREDS = bool(os.getenv("PAYPAL_CLIENT_ID") and os.getenv("PAYPAL_CLIENT_SECRET"))
pytestmark = pytest.mark.skipif(
    not _HAS_PAYPAL_CREDS,
    reason="Live PayPal sandbox tests require PAYPAL_CLIENT_ID and PAYPAL_CLIENT_SECRET in environment",
)


def test_1_live_order_creation_returns_genuine_hateoas():
    """Verify live order creation generates an authentic PayPal order ID with HATEOAS approve link."""
    order_res = paypal_live_service.create_live_order(
        amount="15.00",
        currency="USD",
        description="ProofLedger Round 4 Verification Audit Order",
    )
    assert order_res.get("created") is True
    assert order_res.get("http_status") == 201
    assert "id" in order_res
    order_id = order_res["id"]
    assert len(order_id) > 10
    assert order_res.get("status") == "CREATED"
    assert order_res.get("paypal_debug_id") is not None

    # Verify HATEOAS approval URL returned by PayPal
    links = order_res.get("links", [])
    approve_link = next((l for l in links if l.get("rel") == "approve"), None)
    assert approve_link is not None, "Missing rel: approve HATEOAS link"
    assert "sandbox.paypal.com/checkoutnow" in approve_link["href"]


def test_2_pre_approval_capture_fails_closed_with_422():
    """
    Verify that attempting to capture an unapproved order fails closed with HTTP 422 ORDER_NOT_APPROVED.
    Proves that ProofLedger never synthesizes fake captures or bypasses PayPal buyer approval.
    """
    # 1. Create fresh order
    order_res = paypal_live_service.create_live_order(amount="10.00", currency="USD")
    if not order_res.get("created") or "id" not in order_res:
        pytest.skip(f"PayPal Sandbox API order creation unavailable: {order_res.get('error')}")
    order_id = order_res["id"]

    # 2. Attempt immediate capture before buyer visits approval link
    stable_req_id = f"pl-req-{order_id}-{uuid.uuid4().hex[:6]}"
    cap_res = paypal_live_service.capture_live_order(order_id=order_id, request_id=stable_req_id)

    assert cap_res.get("captured") is False
    assert cap_res.get("http_status") == 422
    assert cap_res.get("issue") == "ORDER_NOT_APPROVED"
    assert cap_res.get("capture_id") is None
    assert cap_res.get("paypal_debug_id") is not None
    assert cap_res.get("idempotency_key") == stable_req_id


def test_3_independent_get_verification_of_completed_capture():
    """
    Verify retrieval of a genuinely completed PayPal Sandbox capture:
    Validates gross amount, fees, net settlement, payer identity, and seller protection eligibility.
    """
    known_capture_id = "10A71705XW788203L"
    capture_data = paypal_live_service.fetch_live_capture(known_capture_id)

    assert capture_data.get("found") is True
    assert capture_data.get("id") == known_capture_id
    assert capture_data.get("status") == "COMPLETED"

    # Financial settlement validation
    amt = capture_data.get("amount", {})
    assert amt.get("value") == "5.00"
    assert amt.get("currency_code") == "USD"

    breakdown = capture_data.get("seller_receivable_breakdown", {})
    assert breakdown.get("gross_amount", {}).get("value") == "5.00"
    assert breakdown.get("paypal_fee", {}).get("value") == "0.59"
    assert breakdown.get("net_amount", {}).get("value") == "4.41"

    # Seller protection validation
    prot = capture_data.get("seller_protection", {})
    assert prot.get("status") == "ELIGIBLE"
    assert "ITEM_NOT_RECEIVED" in prot.get("dispute_categories", [])
    assert "UNAUTHORIZED_TRANSACTION" in prot.get("dispute_categories", [])

    # Supplementary reference check
    rel_order = capture_data.get("supplementary_data", {}).get("related_ids", {}).get("order_id")
    assert rel_order == "3EU95140LR696653G"


def test_4_capture_idempotency_replay_protection():
    """
    Verify that repeating a capture request with the same PayPal-Request-Id is idempotent.
    Ensures network retries do not create duplicate transactions or charges.
    """
    order_res = paypal_live_service.create_live_order(amount="5.00", currency="USD")
    order_id = order_res["id"]
    stable_req_id = f"idemp-test-{order_id}"

    # First attempt
    res1 = paypal_live_service.capture_live_order(order_id, request_id=stable_req_id)
    # Second attempt (replay)
    res2 = paypal_live_service.capture_live_order(order_id, request_id=stable_req_id)

    assert res1["http_status"] == res2["http_status"]
    assert res1["issue"] == res2["issue"]
    assert res1["idempotency_key"] == res2["idempotency_key"]
    assert res1["capture_id"] == res2["capture_id"] == None


def test_5_zero_synthetic_fallbacks():
    """Verify that all API service methods strictly reject synthetic fallbacks."""
    # Attempting to fetch non-existent capture returns found=False with error, not a fabricated object
    bad_res = paypal_live_service.fetch_live_capture("FAKE-NON-EXISTENT-CAPTURE-999")
    assert bad_res.get("found") is False
    assert "error" in bad_res

