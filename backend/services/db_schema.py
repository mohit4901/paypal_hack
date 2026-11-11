"""
Database schema definition, migration, and connection manager for ProofLedger SaaS.
Enforces SQLite foreign key constraints, salted PBKDF2 hashed credentials,
explicit evidence provenance tracking, and secure approval defaults.
"""
from __future__ import annotations

import sys
from pathlib import Path
_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import hashlib
import secrets
import sqlite3
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from backend.config import DATABASE_PATH, SEED_DEMO_CREDENTIALS, is_production_mode, should_seed_demo_credentials

# Standard Provenance States
PROVENANCE_SOURCE_UNVERIFIED = "SOURCE_UNVERIFIED"
PROVENANCE_SELLER_UPLOADED = "SELLER_UPLOADED"
PROVENANCE_MANUAL_ENTRY = "MANUAL_ENTRY"
PROVENANCE_PAYPAL_SANDBOX_VERIFIED = "PAYPAL_SANDBOX_VERIFIED"
PROVENANCE_PAYPAL_LIVE_VERIFIED = "PAYPAL_LIVE_VERIFIED"
PROVENANCE_EXTERNAL_WEBHOOK_VERIFIED = "EXTERNAL_WEBHOOK_VERIFIED"
PROVENANCE_DEMO_SYNTHETIC = "DEMO_SYNTHETIC"

VALID_PROVENANCE_STATUSES = {
    PROVENANCE_SOURCE_UNVERIFIED,
    PROVENANCE_SELLER_UPLOADED,
    PROVENANCE_MANUAL_ENTRY,
    PROVENANCE_PAYPAL_SANDBOX_VERIFIED,
    PROVENANCE_PAYPAL_LIVE_VERIFIED,
    PROVENANCE_EXTERNAL_WEBHOOK_VERIFIED,
    PROVENANCE_DEMO_SYNTHETIC,
}


def hash_api_key(raw_key: str, salt: Optional[str] = None) -> Tuple[str, str]:
    """Compute salted PBKDF2-HMAC-SHA256 hash of API key."""
    if not salt:
        salt = secrets.token_hex(16)
    hashed = hashlib.pbkdf2_hmac("sha256", raw_key.encode("utf-8"), salt.encode("utf-8"), 100_000).hex()
    return f"{salt}${hashed}", salt


def verify_api_key(raw_key: str, stored_hash: str) -> bool:
    """Safely verify raw API key against stored salted PBKDF2 hash using constant-time comparison."""
    try:
        salt, expected = stored_hash.split("$", 1)
        actual = hashlib.pbkdf2_hmac("sha256", raw_key.encode("utf-8"), salt.encode("utf-8"), 100_000).hex()
        return secrets.compare_digest(actual, expected)
    except Exception:
        return False


def get_db_connection() -> sqlite3.Connection:
    """Get an SQLite connection with WAL mode, row factory, and enforced foreign keys."""
    conn = sqlite3.connect(str(DATABASE_PATH), timeout=60.0)
    conn.row_factory = sqlite3.Row
    # Enforce SQLite foreign key integrity on every connection
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA busy_timeout = 60000;")
    return conn


def init_saas_schema(seed_demo_accounts: Optional[bool] = None) -> None:
    """
    Initialize and non-destructively migrate SaaS tables for multi-seller accounts,
    persistent transactions, evidence provenance, and verification runs.
    Demo seller credentials are only seeded when explicitly enabled (dev/test environments).
    In production mode, default demo seller creation is strictly skipped.
    """
    if seed_demo_accounts is None:
        seed_demo_accounts = should_seed_demo_credentials()

    conn = get_db_connection()
    cur = conn.cursor()

    # Temporarily disable foreign keys during schema table restructuring
    conn.execute("PRAGMA foreign_keys = OFF;")

    # 1. Sellers Table (Salted PBKDF2 Hashed Keys & Revocation Support)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS sellers (
            seller_id TEXT PRIMARY KEY,
            api_key_hash TEXT NOT NULL,
            api_key_prefix TEXT NOT NULL,
            business_name TEXT NOT NULL,
            product_category TEXT,
            support_email TEXT,
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)

    # Non-destructive migration if legacy raw api_key column exists in sellers
    cur.execute("PRAGMA table_info(sellers)")
    seller_cols = [c["name"] for c in cur.fetchall()]
    if "api_key" in seller_cols:
        cur.execute("DROP TABLE IF EXISTS sellers_v2")
        cur.execute("""
            CREATE TABLE sellers_v2 (
                seller_id TEXT PRIMARY KEY,
                api_key_hash TEXT NOT NULL,
                api_key_prefix TEXT NOT NULL,
                business_name TEXT NOT NULL,
                product_category TEXT,
                support_email TEXT,
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        cur.execute("SELECT * FROM sellers")
        for row in cur.fetchall():
            d = dict(row)
            raw = d.get("api_key")
            h = d.get("api_key_hash")
            prefix = d.get("api_key_prefix")
            seller_is_active = d.get("is_active", 1)
            if not h and raw:
                h, _ = hash_api_key(raw)
                prefix = raw[:10]
            elif not h:
                # Security Enforcement: Never fallback to known demo keys!
                # If credentials are missing, generate an unguessable random hash
                # and deactivate the seller to require secure key rotation.
                h, _ = hash_api_key(secrets.token_urlsafe(32))
                prefix = "revoked_"
                seller_is_active = 0
            cur.execute("""
                INSERT OR REPLACE INTO sellers_v2 (
                    seller_id, api_key_hash, api_key_prefix, business_name, product_category, support_email, is_active, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                d["seller_id"],
                h,
                prefix or "pl_key_",
                d["business_name"],
                d.get("product_category"),
                d.get("support_email"),
                seller_is_active,
                d.get("created_at"),
                d.get("updated_at"),
            ))
        cur.execute("DROP TABLE sellers")
        cur.execute("ALTER TABLE sellers_v2 RENAME TO sellers")

    # 2. Seller Transactions Table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS seller_transactions (
            transaction_id TEXT PRIMARY KEY,
            seller_id TEXT NOT NULL REFERENCES sellers(seller_id),
            order_id TEXT NOT NULL,
            capture_id TEXT,
            amount TEXT NOT NULL,
            currency TEXT NOT NULL DEFAULT 'USD',
            product_name TEXT,
            product_type TEXT,
            buyer_email TEXT,
            payment_status TEXT NOT NULL DEFAULT 'COMPLETED',
            dispute_status TEXT NOT NULL DEFAULT 'NEEDS_EVIDENCE_RESPONSE',
            dispute_id TEXT,
            provenance_source TEXT NOT NULL DEFAULT 'SELLER_MANUAL_IMPORT',
            metadata_json TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            UNIQUE(seller_id, order_id)
        )
    """)

    # Non-destructive migration if capture_id or buyer_email has NOT NULL constraint
    cur.execute("PRAGMA table_info(seller_transactions)")
    col_nulls = {col["name"]: col["notnull"] for col in cur.fetchall()}
    if col_nulls.get("capture_id") == 1 or col_nulls.get("buyer_email") == 1:
        cur.execute("DROP TABLE IF EXISTS seller_transactions_v2")
        cur.execute("""
            CREATE TABLE seller_transactions_v2 (
                transaction_id TEXT PRIMARY KEY,
                seller_id TEXT NOT NULL REFERENCES sellers(seller_id),
                order_id TEXT NOT NULL,
                capture_id TEXT,
                amount TEXT NOT NULL,
                currency TEXT NOT NULL DEFAULT 'USD',
                product_name TEXT,
                product_type TEXT,
                buyer_email TEXT,
                payment_status TEXT NOT NULL DEFAULT 'COMPLETED',
                dispute_status TEXT NOT NULL DEFAULT 'NEEDS_EVIDENCE_RESPONSE',
                dispute_id TEXT,
                provenance_source TEXT NOT NULL DEFAULT 'SELLER_MANUAL_IMPORT',
                metadata_json TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(seller_id, order_id)
            )
        """)
        cur.execute("""
            INSERT INTO seller_transactions_v2
            SELECT transaction_id, seller_id, order_id, capture_id, amount, currency,
                   product_name, product_type, buyer_email, payment_status, dispute_status,
                   dispute_id, provenance_source, metadata_json, created_at, updated_at
            FROM seller_transactions
        """)
        cur.execute("DROP TABLE seller_transactions")
        cur.execute("ALTER TABLE seller_transactions_v2 RENAME TO seller_transactions")

    # 3. Seller Evidence Table (Default is SOURCE_UNVERIFIED and is_verified_source = 0)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS seller_evidence (
            evidence_id TEXT PRIMARY KEY,
            seller_id TEXT NOT NULL REFERENCES sellers(seller_id),
            transaction_ref TEXT NOT NULL,
            source_type TEXT NOT NULL,
            provenance_label TEXT NOT NULL,
            provenance_status TEXT NOT NULL DEFAULT 'SOURCE_UNVERIFIED',
            source_name TEXT NOT NULL,
            event_type TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            content TEXT NOT NULL,
            is_verified_source INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL
        )
    """)

    # Check seller_evidence columns for provenance_status migration
    cur.execute("PRAGMA table_info(seller_evidence)")
    ev_cols = [c["name"] for c in cur.fetchall()]
    if "provenance_status" not in ev_cols:
        cur.execute("ALTER TABLE seller_evidence ADD COLUMN provenance_status TEXT NOT NULL DEFAULT 'SOURCE_UNVERIFIED'")
        # Ensure only PayPal API Sandbox webhooks hold verified status
        cur.execute("""
            UPDATE seller_evidence
            SET provenance_status = CASE
                WHEN source_type = 'paypal_api' AND provenance_label LIKE '%SANDBOX%' THEN 'PAYPAL_SANDBOX_VERIFIED'
                WHEN source_type = 'paypal_api' THEN 'PAYPAL_LIVE_VERIFIED'
                ELSE 'SOURCE_UNVERIFIED'
            END,
            is_verified_source = CASE
                WHEN source_type = 'paypal_api' THEN 1
                ELSE 0
            END
        """)

    # 4. Verification Runs Table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS verification_runs (
            run_id TEXT PRIMARY KEY,
            seller_id TEXT NOT NULL REFERENCES sellers(seller_id),
            transaction_reference TEXT NOT NULL,
            customer_dispute_reason TEXT,
            model_name TEXT NOT NULL,
            model_checkpoint TEXT NOT NULL,
            model_device TEXT NOT NULL,
            model_invocation_status TEXT NOT NULL,
            raw_model_outputs_json TEXT NOT NULL,
            deterministic_findings_json TEXT NOT NULL,
            combined_verdict TEXT NOT NULL,
            claims_json TEXT NOT NULL,
            evidence_snapshot_json TEXT NOT NULL,
            packet_sha256_digest TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)

    # 5. Dispute Approvals Table (Defaults are strictly FALSE: human_approved=0, signature_confirmed=0)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS dispute_approvals (
            approval_id TEXT PRIMARY KEY,
            run_id TEXT NOT NULL REFERENCES verification_runs(run_id),
            seller_id TEXT NOT NULL REFERENCES sellers(seller_id),
            dispute_id TEXT NOT NULL,
            packet_sha256_digest TEXT NOT NULL,
            human_approved INTEGER NOT NULL DEFAULT 0,
            signature_confirmed INTEGER NOT NULL DEFAULT 0,
            approval_type TEXT NOT NULL DEFAULT 'EVIDENCE_PACKET_INTEGRITY_RECEIPT',
            approved_at TEXT NOT NULL,
            approved_letter_text TEXT NOT NULL
        )
    """)

    # Non-destructive migration for dispute_approvals columns and strict 0 defaults
    cur.execute("PRAGMA table_info(dispute_approvals)")
    appr_info = {c["name"]: str(c["dflt_value"]) for c in cur.fetchall()}
    if appr_info.get("human_approved") != "0" or "approval_type" not in appr_info:
        cur.execute("DROP TABLE IF EXISTS dispute_approvals_v2")
        cur.execute("""
            CREATE TABLE dispute_approvals_v2 (
                approval_id TEXT PRIMARY KEY,
                run_id TEXT NOT NULL REFERENCES verification_runs(run_id),
                seller_id TEXT NOT NULL REFERENCES sellers(seller_id),
                dispute_id TEXT NOT NULL,
                packet_sha256_digest TEXT NOT NULL,
                human_approved INTEGER NOT NULL DEFAULT 0,
                signature_confirmed INTEGER NOT NULL DEFAULT 0,
                approval_type TEXT NOT NULL DEFAULT 'EVIDENCE_PACKET_INTEGRITY_RECEIPT',
                approved_at TEXT NOT NULL,
                approved_letter_text TEXT NOT NULL
            )
        """)
        cur.execute("SELECT * FROM dispute_approvals")
        for row in cur.fetchall():
            d = dict(row)
            cur.execute("""
                INSERT OR REPLACE INTO dispute_approvals_v2 (
                    approval_id, run_id, seller_id, dispute_id, packet_sha256_digest,
                    human_approved, signature_confirmed, approval_type, approved_at, approved_letter_text
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                d["approval_id"],
                d["run_id"],
                d["seller_id"],
                d["dispute_id"],
                d["packet_sha256_digest"],
                d.get("human_approved", 0),
                d.get("signature_confirmed", 0),
                d.get("approval_type", "EVIDENCE_PACKET_INTEGRITY_RECEIPT"),
                d["approved_at"],
                d.get("approved_letter_text", ""),
            ))
        cur.execute("DROP TABLE dispute_approvals")
        cur.execute("ALTER TABLE dispute_approvals_v2 RENAME TO dispute_approvals")

    # 6. Dispute Submissions Table (PayPal Evidence Submissions with Tenant Isolation & Idempotency)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS dispute_submissions (
            submission_id TEXT PRIMARY KEY,
            dispute_id TEXT NOT NULL,
            seller_id TEXT NOT NULL REFERENCES sellers(seller_id),
            carrier_name TEXT NOT NULL,
            tracking_number TEXT NOT NULL,
            evidence_notes TEXT,
            proof_document_url TEXT,
            merchant_approved INTEGER NOT NULL DEFAULT 1,
            approval_id TEXT,
            evidence_digest TEXT,
            paypal_status_code INTEGER DEFAULT 200,
            paypal_debug_id TEXT,
            paypal_response_json TEXT,
            submitted_at TEXT NOT NULL,
            UNIQUE(dispute_id, seller_id)
        )
    """)

    # Non-destructive column additions on dispute_submissions if migrating existing DB
    cur.execute("PRAGMA table_info(dispute_submissions)")
    sub_cols = {c["name"] for c in cur.fetchall()}
    if "approval_id" not in sub_cols:
        cur.execute("ALTER TABLE dispute_submissions ADD COLUMN approval_id TEXT")
    if "evidence_digest" not in sub_cols:
        cur.execute("ALTER TABLE dispute_submissions ADD COLUMN evidence_digest TEXT")

    # 7. Server-Side Fulfillment Evidence Approvals Table (binds approval_id to SHA-256 evidence digest)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS evidence_approvals (
            approval_id TEXT PRIMARY KEY,
            dispute_id TEXT NOT NULL,
            seller_id TEXT NOT NULL REFERENCES sellers(seller_id),
            evidence_digest TEXT NOT NULL,
            carrier_name TEXT NOT NULL,
            tracking_number TEXT NOT NULL,
            evidence_notes TEXT,
            proof_document_url TEXT,
            human_approved INTEGER NOT NULL DEFAULT 0,
            approved_at TEXT NOT NULL
        )
    """)

    # 8. Uploaded Supporting Evidence Files Metadata Table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS uploaded_evidence_files (
            file_id TEXT PRIMARY KEY,
            dispute_id TEXT NOT NULL,
            seller_id TEXT NOT NULL REFERENCES sellers(seller_id),
            filename TEXT NOT NULL,
            content_type TEXT,
            size_bytes INTEGER NOT NULL,
            file_sha256 TEXT NOT NULL,
            uploaded_at TEXT NOT NULL
        )
    """)

    # Pre-seed standard testing sellers with salted PBKDF2 hashes (isolated dev/test mode only)
    # In production mode, demo sellers are strictly forbidden and immediately deactivated if present
    now_iso = datetime.now(timezone.utc).isoformat()
    if is_production_mode() or not seed_demo_accounts:
        cur.execute("""
            UPDATE sellers
            SET is_active = 0, updated_at = ?
            WHERE seller_id IN ('seller_alpha', 'seller_beta')
        """, (now_iso,))
    elif seed_demo_accounts:
        alpha_hash, _ = hash_api_key("key_alpha_123")
        beta_hash, _ = hash_api_key("key_beta_456")

        # Update or insert seller_alpha
        cur.execute("SELECT seller_id FROM sellers WHERE seller_id = 'seller_alpha'")
        if not cur.fetchone():
            cur.execute("""
                INSERT INTO sellers (seller_id, api_key_hash, api_key_prefix, business_name, product_category, support_email, is_active, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?)
            """, ("seller_alpha", alpha_hash, "key_alpha_", "Python Mastery Academy", "Online Courses & Digital Assets", "support@pythonmastery.academy", now_iso, now_iso))
        else:
            # Update existing seller_alpha to hashed credentials
            cur.execute("""
                UPDATE sellers
                SET api_key_hash = ?, api_key_prefix = ?, is_active = 1
                WHERE seller_id = 'seller_alpha'
            """, (alpha_hash, "key_alpha_"))

        # Update or insert seller_beta
        cur.execute("SELECT seller_id FROM sellers WHERE seller_id = 'seller_beta'")
        if not cur.fetchone():
            cur.execute("""
                INSERT INTO sellers (seller_id, api_key_hash, api_key_prefix, business_name, product_category, support_email, is_active, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?)
            """, ("seller_beta", beta_hash, "key_beta_4", "Cloud SaaS Kit", "Developer Tools & SaaS Starters", "contact@cloudsaaskit.io", now_iso, now_iso))
        else:
            cur.execute("""
                UPDATE sellers
                SET api_key_hash = ?, api_key_prefix = ?, is_active = 1
                WHERE seller_id = 'seller_beta'
            """, (beta_hash, "key_beta_4"))

    # Restore foreign keys enforcement and commit
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.commit()
    conn.close()


if __name__ == "__main__":
    init_saas_schema()
    print("SaaS schema initialized and migrated successfully with foreign keys & PBKDF2 key hashes.")
