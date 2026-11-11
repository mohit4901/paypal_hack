"""
Automated Test Suite for PayPal Live Sandbox Integration.
Verifies real API communication with api-m.sandbox.paypal.com,
fail-closed authentication, and live SQLite persistence.
"""
import os
import pytest
from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)
AUTH_HEADER = {"Authorization": "Bearer key_alpha_123"}
_HAS_PAYPAL_CREDS = bool(os.getenv("PAYPAL_CLIENT_ID") and os.getenv("PAYPAL_CLIENT_SECRET"))


def test_paypal_sync_unauthenticated_rejected():
    """Fail-closed: unauthenticated requests must be rejected with 401."""
    res = client.post("/api/v2/paypal/sync")
    assert res.status_code == 401


def test_paypal_live_feed_unauthenticated_rejected():
    res = client.get("/api/v2/paypal/live-feed")
    assert res.status_code == 401


@pytest.mark.skipif(not _HAS_PAYPAL_CREDS, reason="Requires live PayPal credentials in environment")
def test_paypal_live_sync_success():
    """Authenticated sync interacts with live PayPal Sandbox and persists records."""
    res = client.post("/api/v2/paypal/sync", headers=AUTH_HEADER)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "LIVE_SYNC_COMPLETED"
    assert data["environment"] == "SANDBOX"
    assert data["captures_synced"] >= 1
    assert data["webhook_events_synced"] >= 1
    assert "oauth_latency_ms" in data
    assert "total_latency_ms" in data
    assert data["capture_details"]["capture_id"] == "10A71705XW788203L"
    assert data["capture_details"]["currency"] == "USD"


@pytest.mark.skipif(not _HAS_PAYPAL_CREDS, reason="Requires live PayPal credentials in environment")
def test_paypal_live_feed():
    """Inspects live payload directly from api-m.sandbox.paypal.com."""
    res = client.get("/api/v2/paypal/live-feed", headers=AUTH_HEADER)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "LIVE_FEED_SUCCESS"
    assert data["api_host"] == "api-m.sandbox.paypal.com"
    assert data["oauth"]["token_masked"].startswith("A21AA")
    assert "live_capture_10A71705XW788203L" in data
    assert data["live_capture_10A71705XW788203L"]["status"] == "COMPLETED"
    assert "live_order_3EU95140LR696653G" in data
    assert data["live_order_3EU95140LR696653G"]["status"] == "COMPLETED"


@pytest.mark.skipif(not _HAS_PAYPAL_CREDS, reason="Requires live PayPal credentials in environment")
def test_paypal_live_capture_endpoint():
    """Direct lookup for capture 10A71705XW788203L."""
    res = client.get("/api/v2/paypal/live-capture/10A71705XW788203L", headers=AUTH_HEADER)
    assert res.status_code == 200
    data = res.json()
    assert data["id"] == "10A71705XW788203L"
    assert data["status"] == "COMPLETED"
    assert data["amount"]["value"] == "5.00"
    assert data["amount"]["currency_code"] == "USD"


@pytest.mark.skipif(not _HAS_PAYPAL_CREDS, reason="Requires live PayPal credentials in environment")
def test_paypal_live_order_endpoint():
    """Direct lookup for order 3EU95140LR696653G."""
    res = client.get("/api/v2/paypal/live-order/3EU95140LR696653G", headers=AUTH_HEADER)
    assert res.status_code == 200
    data = res.json()
    assert data["id"] == "3EU95140LR696653G"
    assert data["status"] == "COMPLETED"
    assert "payer" in data
    assert data["payer"]["email_address"] == "sb-rcnwy53637793@personal.example.com"

