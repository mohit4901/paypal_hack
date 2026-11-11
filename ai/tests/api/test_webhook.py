"""
Tests for PayPal Sandbox Webhook Receiver.

Covers:
1. Valid webhook signature
2. Invalid webhook signature
3. Missing transmission headers
4. Malformed payload
5. PAYMENT.CAPTURE.COMPLETED
6. PAYMENT.CAPTURE.PENDING
7. CUSTOMER.DISPUTE.CREATED (with verified transaction linkage)
8. CUSTOMER.DISPUTE.UPDATED
9. CUSTOMER.DISPUTE.RESOLVED
10. Duplicate event delivery (persistent idempotency)
11. Unknown transaction reference (flagged for manual reconciliation)
12. Database persistence failure (500 retryable server error)
13. No automatic evidence submission (human approval strictly mandatory)
14. CHECKOUT.ORDER.APPROVED (does not treat approval as payment capture)
"""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from src.api.main import app
from src.storage.db import (
    DatabaseError,
    find_transaction,
    get_dispute,
    get_webhook_event,
    init_db,
    upsert_transaction,
)


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    """Run each test against an isolated temporary SQLite database and hash chain."""
    test_db = str(tmp_path / "test_proofledger.db")
    test_chain = str(tmp_path / "test_events_hash_chain.jsonl")
    monkeypatch.setenv("DATABASE_PATH", test_db)
    monkeypatch.setenv("CHAIN_LOG_PATH", test_chain)
    monkeypatch.setenv("PAYPAL_WEBHOOK_ID", "mock_webhook_id_12345")
    init_db(test_db)
    return test_db


@pytest.fixture
def client():
    return TestClient(app)


def make_headers():
    return {
        "paypal-transmission-id": "mock-transmission-id-001",
        "paypal-transmission-time": "2026-10-31T12:00:00Z",
        "paypal-transmission-sig": "mock-signature-base64",
        "paypal-cert-url": "https://api.sandbox.paypal.com/v1/notifications/certs/CERT-123",
        "paypal-auth-algo": "SHA256withRSA",
        "Content-Type": "application/json",
    }


# ===========================================================================
# 1. Signature & Header Verification Tests
# ===========================================================================

@patch("src.integrations.paypal_client.PayPalClient.verify_webhook_signature", return_value=True)
def test_webhook_valid_signature(mock_verify, client):
    """Test that valid signature allows webhook processing."""
    payload = {
        "id": "WH-TEST-VALID-01",
        "event_type": "CHECKOUT.ORDER.APPROVED",
        "resource_type": "checkout-order",
        "resource": {"id": "ORD-VALID-01"},
    }
    resp = client.post("/paypal/webhook", json=payload, headers=make_headers())
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "PROCESSED"
    assert data["event_id"] == "WH-TEST-VALID-01"
    mock_verify.assert_called_once()


@patch("src.integrations.paypal_client.PayPalClient.verify_webhook_signature", return_value=False)
def test_webhook_invalid_signature(mock_verify, client):
    """Test that invalid signature is rejected with HTTP 400."""
    payload = {
        "id": "WH-TEST-INVALID-01",
        "event_type": "CHECKOUT.ORDER.APPROVED",
        "resource": {"id": "ORD-01"},
    }
    resp = client.post("/paypal/webhook", json=payload, headers=make_headers())
    assert resp.status_code == 400
    assert "Invalid webhook signature" in resp.json()["detail"]


def test_webhook_missing_transmission_headers(client):
    """Test that missing required transmission headers results in HTTP 400."""
    headers = make_headers()
    del headers["paypal-transmission-sig"]

    resp = client.post("/paypal/webhook", json={"id": "WH-01"}, headers=headers)
    assert resp.status_code == 400
    assert "Missing required PayPal transmission headers" in resp.json()["detail"]


@patch("src.integrations.paypal_client.PayPalClient.verify_webhook_signature", return_value=True)
def test_webhook_malformed_payload(mock_verify, client):
    """Test that malformed JSON body returns HTTP 400."""
    headers = make_headers()
    resp = client.post("/paypal/webhook", content=b"invalid { json body", headers=headers)
    assert resp.status_code == 400
    assert "Malformed JSON payload" in resp.json()["detail"]


# ===========================================================================
# 2. Payment Capture Event Tests
# ===========================================================================

@patch("src.integrations.paypal_client.PayPalClient.verify_webhook_signature", return_value=True)
def test_webhook_payment_capture_completed(mock_verify, client, isolated_db):
    """Test PAYMENT.CAPTURE.COMPLETED records transaction in COMPLETED state."""
    payload = {
        "id": "WH-CAP-COMPLETED-01",
        "event_type": "PAYMENT.CAPTURE.COMPLETED",
        "resource_type": "capture",
        "resource": {
            "id": "CAP-887766",
            "status": "COMPLETED",
            "amount": {"value": "99.00", "currency_code": "USD"},
            "supplementary_data": {
                "related_ids": {"order_id": "ORD-554433"}
            },
        },
    }
    resp = client.post("/paypal/webhook", json=payload, headers=make_headers())
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "PROCESSED"
    assert data["transaction_reference"] == "ORD-554433"

    tx = find_transaction("ORD-554433", db_path=isolated_db)
    assert tx is not None
    assert tx["status"] == "COMPLETED"
    assert tx["capture_id"] == "CAP-887766"
    assert tx["amount"] == "99.00"


@patch("src.integrations.paypal_client.PayPalClient.verify_webhook_signature", return_value=True)
def test_webhook_payment_capture_pending(mock_verify, client, isolated_db):
    """Test PAYMENT.CAPTURE.PENDING sets status to PENDING."""
    payload = {
        "id": "WH-CAP-PENDING-01",
        "event_type": "PAYMENT.CAPTURE.PENDING",
        "resource_type": "capture",
        "resource": {
            "id": "CAP-PEND-11",
            "status": "PENDING",
            "amount": {"value": "50.00", "currency_code": "USD"},
            "custom_id": "ORD-PEND-01",
        },
    }
    resp = client.post("/paypal/webhook", json=payload, headers=make_headers())
    assert resp.status_code == 200
    assert resp.json()["status"] == "PROCESSED"

    tx = find_transaction("ORD-PEND-01", db_path=isolated_db)
    assert tx is not None
    assert tx["status"] == "PENDING"


@patch("src.integrations.paypal_client.PayPalClient.verify_webhook_signature", return_value=True)
def test_webhook_order_approved_does_not_capture(mock_verify, client, isolated_db):
    """Test CHECKOUT.ORDER.APPROVED records APPROVED, never treating it as payment capture."""
    payload = {
        "id": "WH-ORDER-APP-01",
        "event_type": "CHECKOUT.ORDER.APPROVED",
        "resource_type": "checkout-order",
        "resource": {
            "id": "ORD-APP-99",
            "purchase_units": [{"amount": {"value": "150.00", "currency_code": "USD"}}],
        },
    }
    resp = client.post("/paypal/webhook", json=payload, headers=make_headers())
    assert resp.status_code == 200
    tx = find_transaction("ORD-APP-99", db_path=isolated_db)
    assert tx is not None
    assert tx["status"] == "APPROVED"
    assert tx["status"] != "COMPLETED"
    assert tx["capture_id"] is None


# ===========================================================================
# 3. Dispute Lifecycle Tests
# ===========================================================================

@patch("src.integrations.paypal_client.PayPalClient.verify_webhook_signature", return_value=True)
@patch("src.integrations.paypal_client.PayPalClient.provide_dispute_evidence")
def test_webhook_customer_dispute_created_linked(mock_submit, mock_verify, client, isolated_db):
    """
    Test CUSTOMER.DISPUTE.CREATED with verified transaction linkage:
    - Dispute recorded
    - Linked to order
    - Evidence compilation queued in background
    - No automatic submission to PayPal
    """
    # 1. Seed verified transaction
    upsert_transaction(
        transaction_id="ORD-DISPUTE-01",
        order_id="ORD-DISPUTE-01",
        capture_id="CAP-DISPUTE-01",
        amount="75.00",
        currency="USD",
        status="COMPLETED",
        event_id="EVT-SEED",
        metadata={"delivery_status": "DELIVERED", "file_name": "software_license.pdf"},
        db_path=isolated_db,
    )

    payload = {
        "id": "WH-DISPUTE-CREATED-01",
        "event_type": "CUSTOMER.DISPUTE.CREATED",
        "resource_type": "dispute",
        "resource": {
            "dispute_id": "PP-D-998877",
            "reason": "MERCHANDISE_OR_SERVICE_NOT_RECEIVED",
            "status": "OPEN",
            "dispute_amount": {"value": "75.00", "currency_code": "USD"},
            "disputed_transactions": [
                {
                    "seller_transaction_id": "CAP-DISPUTE-01",
                    "custom": "ORD-DISPUTE-01",
                }
            ],
        },
    }

    resp = client.post("/paypal/webhook", json=payload, headers=make_headers())
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "PROCESSED"
    assert data["resource_id"] == "PP-D-998877"
    assert data["transaction_reference"] == "ORD-DISPUTE-01"

    # Verify dispute persisted in DB
    dispute = get_dispute("PP-D-998877", db_path=isolated_db)
    assert dispute is not None
    assert dispute["transaction_reference"] == "ORD-DISPUTE-01"
    assert dispute["reason"] == "MERCHANDISE_OR_SERVICE_NOT_RECEIVED"
    assert dispute["status"] == "OPEN"

    # Strictly assert NO automated submission was sent to PayPal
    mock_submit.assert_not_called()


@patch("src.integrations.paypal_client.PayPalClient.verify_webhook_signature", return_value=True)
def test_webhook_customer_dispute_updated(mock_verify, client, isolated_db):
    """Test CUSTOMER.DISPUTE.UPDATED records status transition and updates history."""
    # Seed dispute
    payload_created = {
        "id": "WH-DISP-CREATE-FOR-UPDATE",
        "event_type": "CUSTOMER.DISPUTE.CREATED",
        "resource_type": "dispute",
        "resource": {
            "dispute_id": "PP-D-UPDATE-01",
            "reason": "UNAUTHORISED",
            "status": "OPEN",
        },
    }
    client.post("/paypal/webhook", json=payload_created, headers=make_headers())

    # Send update
    payload_updated = {
        "id": "WH-DISP-UPDATE-EVENT",
        "event_type": "CUSTOMER.DISPUTE.UPDATED",
        "resource_type": "dispute",
        "resource": {
            "dispute_id": "PP-D-UPDATE-01",
            "status": "UNDER_REVIEW",
        },
    }
    resp = client.post("/paypal/webhook", json=payload_updated, headers=make_headers())
    assert resp.status_code == 200
    assert resp.json()["status"] == "PROCESSED"

    dispute = get_dispute("PP-D-UPDATE-01", db_path=isolated_db)
    assert dispute is not None
    assert dispute["status"] == "UNDER_REVIEW"
    assert len(dispute["history"]) >= 2


@patch("src.integrations.paypal_client.PayPalClient.verify_webhook_signature", return_value=True)
def test_webhook_customer_dispute_resolved(mock_verify, client, isolated_db):
    """Test CUSTOMER.DISPUTE.RESOLVED records final outcome."""
    payload_created = {
        "id": "WH-DISP-CREATE-FOR-RESOLVE",
        "event_type": "CUSTOMER.DISPUTE.CREATED",
        "resource": {"dispute_id": "PP-D-RESOLVE-01", "status": "OPEN"},
    }
    client.post("/paypal/webhook", json=payload_created, headers=make_headers())

    payload_resolved = {
        "id": "WH-DISP-RESOLVED-EVENT",
        "event_type": "CUSTOMER.DISPUTE.RESOLVED",
        "resource_type": "dispute",
        "resource": {
            "dispute_id": "PP-D-RESOLVE-01",
            "status": "RESOLVED",
            "dispute_outcome": {"outcome_code": "RESOLVED_SELLER_FAVOUR"},
        },
    }
    resp = client.post("/paypal/webhook", json=payload_resolved, headers=make_headers())
    assert resp.status_code == 200
    assert resp.json()["status"] == "PROCESSED"

    dispute = get_dispute("PP-D-RESOLVE-01", db_path=isolated_db)
    assert dispute is not None
    assert dispute["status"] == "RESOLVED"
    assert dispute["resolution_outcome"] == "RESOLVED_SELLER_FAVOUR"


# ===========================================================================
# 4. Idempotency & Edge Cases Tests
# ===========================================================================

@patch("src.integrations.paypal_client.PayPalClient.verify_webhook_signature", return_value=True)
def test_webhook_duplicate_event_delivery(mock_verify, client, isolated_db):
    """Test repeated deliveries of the exact same event ID are safely deduplicated."""
    payload = {
        "id": "WH-DUP-EVENT-001",
        "event_type": "CHECKOUT.ORDER.APPROVED",
        "resource": {"id": "ORD-DUP-01"},
    }
    # First delivery
    resp1 = client.post("/paypal/webhook", json=payload, headers=make_headers())
    assert resp1.status_code == 200
    assert resp1.json()["status"] == "PROCESSED"

    # Second delivery with identical event ID
    resp2 = client.post("/paypal/webhook", json=payload, headers=make_headers())
    assert resp2.status_code == 200
    assert resp2.json()["status"] == "DUPLICATE"
    assert "already processed" in resp2.json()["detail"].lower()

    # Verify event exists in DB once
    event = get_webhook_event("WH-DUP-EVENT-001", db_path=isolated_db)
    assert event is not None


@patch("src.integrations.paypal_client.PayPalClient.verify_webhook_signature", return_value=True)
def test_webhook_unknown_transaction_reference(mock_verify, client, isolated_db):
    """
    Test dispute referencing an unknown transaction:
    - Never associates with a random order
    - Flags for manual reconciliation
    """
    payload = {
        "id": "WH-UNKNOWN-TX-01",
        "event_type": "CUSTOMER.DISPUTE.CREATED",
        "resource": {
            "dispute_id": "PP-D-UNKNOWN-99",
            "reason": "MERCHANDISE_OR_SERVICE_NOT_RECEIVED",
            "status": "OPEN",
            "disputed_transactions": [{"seller_transaction_id": "UNSEEN-TX-777"}],
        },
    }
    resp = client.post("/paypal/webhook", json=payload, headers=make_headers())
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "FLAGGED_MANUAL_RECONCILIATION"
    assert data["transaction_reference"] is None

    dispute = get_dispute("PP-D-UNKNOWN-99", db_path=isolated_db)
    assert dispute is not None
    assert dispute["transaction_reference"] is None
    assert dispute["evidence_prepared"] == 0


@patch("src.integrations.paypal_client.PayPalClient.verify_webhook_signature", return_value=True)
@patch("src.integrations.paypal_webhook_processor.record_webhook_event", side_effect=DatabaseError("Disk full or lock timeout"))
def test_webhook_database_persistence_failure(mock_db, mock_verify, client):
    """Test that durable persistence failure raises HTTP 500 retryable error for PayPal."""
    payload = {
        "id": "WH-FAIL-01",
        "event_type": "CHECKOUT.ORDER.APPROVED",
        "resource": {"id": "ORD-01"},
    }
    resp = client.post("/paypal/webhook", json=payload, headers=make_headers())
    assert resp.status_code == 500
    assert "Database persistence failure" in resp.json()["detail"]


@patch("src.integrations.paypal_client.PayPalClient.verify_webhook_signature", return_value=True)
@patch("src.integrations.paypal_client.PayPalClient.provide_dispute_evidence")
def test_webhook_no_automatic_evidence_submission(mock_submit, mock_verify, client):
    """
    Strictly verify that incoming dispute webhook NEVER invokes the PayPal dispute evidence submission API.
    Human seller review remains strictly mandatory.
    """
    payload = {
        "id": "WH-NO-AUTO-SUBMIT",
        "event_type": "CUSTOMER.DISPUTE.CREATED",
        "resource": {
            "dispute_id": "PP-D-NO-AUTO",
            "reason": "NOT_AS_DESCRIBED",
            "status": "OPEN",
        },
    }
    resp = client.post("/paypal/webhook", json=payload, headers=make_headers())
    assert resp.status_code == 200
    mock_submit.assert_not_called()
