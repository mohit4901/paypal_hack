"""
Seller Authentication and Multi-Tenant Account Isolation for ProofLedger.
Enforces strict fail-closed authorization, salted PBKDF2 API key verification,
constant-time cryptographic comparison, and key rotation/revocation.
"""
from __future__ import annotations

import secrets
from datetime import datetime, timezone
from typing import Optional, Tuple
from fastapi import Header, HTTPException, Request
from pydantic import BaseModel

from backend.config import is_production_mode, should_seed_demo_credentials
from backend.services.db_schema import (
    get_db_connection,
    hash_api_key,
    verify_api_key,
)

PROHIBITED_DEMO_KEYS = {"key_alpha_123", "key_beta_456"}
PROHIBITED_DEMO_SELLERS = {"seller_alpha", "seller_beta"}


class Seller(BaseModel):
    seller_id: str
    business_name: str
    product_category: Optional[str] = None
    support_email: Optional[str] = None
    api_key_prefix: Optional[str] = None
    is_active: bool = True


def get_seller_by_id(seller_id: str) -> Optional[Seller]:
    """Retrieve seller profile by unique seller_id (without exposing key hashes)."""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT seller_id, business_name, product_category, support_email, api_key_prefix, is_active FROM sellers WHERE seller_id = ?",
        (seller_id,),
    )
    row = cur.fetchone()
    conn.close()
    if row:
        return Seller(
            seller_id=row["seller_id"],
            business_name=row["business_name"],
            product_category=row["product_category"],
            support_email=row["support_email"],
            api_key_prefix=row["api_key_prefix"],
            is_active=bool(row["is_active"]),
        )
    return None


def get_seller_by_key(api_key: str) -> Optional[Seller]:
    """
    Authenticate seller by verifying raw API key against stored salted PBKDF2 hash.
    Safe against timing attacks using constant-time verification.
    """
    if not api_key or not api_key.strip():
        return None

    clean_key = api_key.strip()

    # P0 Security Enforcement: Demo keys are strictly blocked in production mode or when demo seeding is disabled
    if (is_production_mode() or not should_seed_demo_credentials()) and clean_key in PROHIBITED_DEMO_KEYS:
        return None

    conn = get_db_connection()
    cur = conn.cursor()

    # Query active candidate sellers matching the key prefix or candidate pool
    prefix = clean_key[:10]
    cur.execute(
        "SELECT seller_id, api_key_hash, api_key_prefix, business_name, product_category, support_email, is_active FROM sellers WHERE (api_key_prefix = ? OR api_key_prefix = ?) AND is_active = 1",
        (prefix, clean_key[:8]),
    )
    candidates = cur.fetchall()

    if not candidates:
        # Fallback to check all active sellers if key format differs
        cur.execute(
            "SELECT seller_id, api_key_hash, api_key_prefix, business_name, product_category, support_email, is_active FROM sellers WHERE is_active = 1"
        )
        candidates = cur.fetchall()

    conn.close()

    for cand in candidates:
        stored_hash = cand["api_key_hash"]
        if verify_api_key(clean_key, stored_hash):
            if (is_production_mode() or not should_seed_demo_credentials()) and cand["seller_id"] in PROHIBITED_DEMO_SELLERS:
                return None
            return Seller(
                seller_id=cand["seller_id"],
                business_name=cand["business_name"],
                product_category=cand["product_category"],
                support_email=cand["support_email"],
                api_key_prefix=cand["api_key_prefix"],
                is_active=bool(cand["is_active"]),
            )

    return None


def register_new_seller(
    seller_id: str,
    business_name: str,
    product_category: str = "Digital Products",
    support_email: str = "contact@example.com",
) -> Tuple[Seller, str]:
    """
    Register and persist a new independent seller.
    Stores only salted PBKDF2 hash. Returns the raw API key ONCE.
    """
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("SELECT seller_id FROM sellers WHERE seller_id = ?", (seller_id.strip(),))
    if cur.fetchone():
        conn.close()
        raise ValueError(f"Seller with ID '{seller_id}' already exists.")

    raw_api_key = f"pl_{seller_id.strip()}_{secrets.token_urlsafe(32)}"
    api_key_hash, _ = hash_api_key(raw_api_key)
    api_key_prefix = raw_api_key[:10]
    now_iso = datetime.now(timezone.utc).isoformat()

    cur.execute("""
        INSERT INTO sellers (seller_id, api_key_hash, api_key_prefix, business_name, product_category, support_email, is_active, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?)
    """, (seller_id.strip(), api_key_hash, api_key_prefix, business_name.strip(), product_category.strip(), support_email.strip(), now_iso, now_iso))

    conn.commit()
    conn.close()

    seller = Seller(
        seller_id=seller_id.strip(),
        business_name=business_name.strip(),
        product_category=product_category.strip(),
        support_email=support_email.strip(),
        api_key_prefix=api_key_prefix,
        is_active=True,
    )
    return seller, raw_api_key


def rotate_seller_key(seller_id: str) -> str:
    """Rotate API key for a seller. Invalidates previous key and returns new key ONCE."""
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("SELECT seller_id FROM sellers WHERE seller_id = ?", (seller_id,))
    if not cur.fetchone():
        conn.close()
        raise ValueError(f"Seller '{seller_id}' not found.")

    new_raw_key = f"pl_{seller_id}_{secrets.token_urlsafe(32)}"
    new_hash, _ = hash_api_key(new_raw_key)
    new_prefix = new_raw_key[:10]
    now_iso = datetime.now(timezone.utc).isoformat()

    cur.execute("""
        UPDATE sellers
        SET api_key_hash = ?, api_key_prefix = ?, updated_at = ?
        WHERE seller_id = ?
    """, (new_hash, new_prefix, now_iso, seller_id))

    conn.commit()
    conn.close()
    return new_raw_key


def revoke_seller_access(seller_id: str) -> None:
    """Revoke/deactivate seller credentials immediately."""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("UPDATE sellers SET is_active = 0, updated_at = ? WHERE seller_id = ?", (
        datetime.now(timezone.utc).isoformat(),
        seller_id,
    ))
    conn.commit()
    conn.close()


def get_current_seller(request: Request) -> Seller:
    """
    STRICT FAIL-CLOSED FastAPI Dependency for authenticating sellers.
    Rejects missing or invalid credentials with HTTP 401.
    Zero fail-open defaults. No unauthenticated data access permitted.
    """
    auth_header = request.headers.get("Authorization")
    key_header = request.headers.get("X-Seller-Key")

    token = None
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ", 1)[1].strip()
    elif key_header:
        token = key_header.strip()

    # P0 Security Enforcement: Missing credentials strictly fail-closed
    if not token:
        raise HTTPException(
            status_code=401,
            detail="Authentication required. Please provide a valid Bearer token or X-Seller-Key header.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # P0 Security Enforcement: Demo keys are strictly prohibited in production mode or when demo seeding is disabled
    if (is_production_mode() or not should_seed_demo_credentials()) and token in PROHIBITED_DEMO_KEYS:
        raise HTTPException(
            status_code=401,
            detail="Demo credentials (key_alpha_123 / key_beta_456) are strictly prohibited in production mode or when demo credentials are disabled.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    seller = get_seller_by_key(token)
    if not seller:
        raise HTTPException(
            status_code=401,
            detail="Invalid API key. Authentication failed.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not seller.is_active:
        raise HTTPException(
            status_code=401,
            detail="Seller account credentials have been revoked or deactivated.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return seller
