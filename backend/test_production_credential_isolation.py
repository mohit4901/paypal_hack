"""
Tests for Production Credential Isolation and Demo Account Rejection.
Ensures ProofLedger strictly isolates production environments from development/demo credentials.
"""
import os
import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.config import is_production_mode
from backend.auth import get_seller_by_key, register_new_seller, PROHIBITED_DEMO_KEYS, PROHIBITED_DEMO_SELLERS
from backend.services.db_schema import get_db_connection, init_saas_schema


@pytest.fixture(autouse=True)
def ensure_clean_production_env():
    """Fixture to safely toggle production mode and restore env after test."""
    original_app_env = os.environ.get("APP_ENV")
    original_seed_demo = os.environ.get("SEED_DEMO_CREDENTIALS")
    
    yield
    
    if original_app_env is not None:
        os.environ["APP_ENV"] = original_app_env
    else:
        os.environ.pop("APP_ENV", None)
        
    if original_seed_demo is not None:
        os.environ["SEED_DEMO_CREDENTIALS"] = original_seed_demo
    else:
        os.environ.pop("SEED_DEMO_CREDENTIALS", None)

    init_saas_schema()


def test_production_mode_detection():
    os.environ["APP_ENV"] = "production"
    assert is_production_mode() is True

    os.environ["APP_ENV"] = "development"
    assert is_production_mode() is False

    os.environ.pop("APP_ENV", None)
    assert is_production_mode() is False


def test_production_mode_blocks_demo_keys_in_auth_helper():
    os.environ["APP_ENV"] = "production"
    assert is_production_mode() is True

    for demo_key in PROHIBITED_DEMO_KEYS:
        seller = get_seller_by_key(demo_key)
        assert seller is None, f"Demo key {demo_key} should have returned None in production mode"


def test_production_mode_rejects_demo_bearer_tokens_with_401():
    os.environ["APP_ENV"] = "production"
    client = TestClient(app)

    # 1. Bearer key_alpha_123
    resp1 = client.get("/api/v2/transactions", headers={"Authorization": "Bearer key_alpha_123"})
    assert resp1.status_code == 401
    assert "strictly prohibited in production mode" in resp1.json().get("detail", "")

    # 2. Bearer key_beta_456
    resp2 = client.get("/api/v2/transactions", headers={"Authorization": "Bearer key_beta_456"})
    assert resp2.status_code == 401
    assert "strictly prohibited in production mode" in resp2.json().get("detail", "")

    # 3. Header X-Seller-Key: key_alpha_123
    resp3 = client.get("/api/v2/transactions", headers={"X-Seller-Key": "key_alpha_123"})
    assert resp3.status_code == 401
    assert "strictly prohibited in production mode" in resp3.json().get("detail", "")


def test_production_mode_allows_genuine_registered_seller():
    os.environ["APP_ENV"] = "production"
    client = TestClient(app)

    unique_seller_id = "prod_audit_seller_test"
    # Ensure test seller does not exist before
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM sellers WHERE seller_id = ?", (unique_seller_id,))
    conn.commit()
    conn.close()

    seller, api_key = register_new_seller(
        seller_id=unique_seller_id,
        business_name="Production Audit Seller Corp",
        product_category="Enterprise Security",
        support_email="audit@prodaudit.example.com",
    )
    assert api_key.startswith(f"pl_{unique_seller_id}_")

    try:
        # Genuine seller must authenticate successfully
        resp = client.get("/api/v2/transactions", headers={"Authorization": f"Bearer {api_key}"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["seller_id"] == unique_seller_id
        assert data["total_transactions"] == 0
    finally:
        # Cleanup
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("DELETE FROM sellers WHERE seller_id = ?", (unique_seller_id,))
        conn.commit()
        conn.close()


def test_seed_demo_credentials_false_blocks_demo_keys():
    """Verify that SEED_DEMO_CREDENTIALS=false blocks demo keys with 401."""
    os.environ.pop("APP_ENV", None)
    os.environ["SEED_DEMO_CREDENTIALS"] = "false"
    init_saas_schema()
    client = TestClient(app)
    resp = client.get("/api/v2/transactions", headers={"Authorization": "Bearer key_alpha_123"})
    assert resp.status_code == 401
    assert "strictly prohibited" in resp.json().get("detail", "")


def test_bundled_sqlite_demo_sellers_are_deactivated():
    """Verify demo accounts seller_alpha and seller_beta have is_active = 0 in production."""
    os.environ["APP_ENV"] = "production"
    init_saas_schema()
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT seller_id, is_active FROM sellers WHERE seller_id IN ('seller_alpha', 'seller_beta')"
    )
    rows = cur.fetchall()
    conn.close()

    assert len(rows) > 0, "Demo accounts should exist in db schema but be inactive"
    for r in rows:
        assert r["is_active"] == 0, f"Seller {r['seller_id']} must have is_active == 0"


def test_schema_init_in_production_deactivates_demo_sellers():
    """Verify that calling init_saas_schema() under APP_ENV=production enforces deactivation."""
    os.environ["APP_ENV"] = "production"
    init_saas_schema()

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT seller_id, is_active FROM sellers WHERE seller_id IN ('seller_alpha', 'seller_beta')"
    )
    rows = cur.fetchall()
    conn.close()

    for r in rows:
        assert r["is_active"] == 0
