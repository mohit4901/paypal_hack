"""
SQLite-backed persistent storage for ProofLedger.

Provides:
- Durable idempotency tracking for PayPal webhook events (database-level uniqueness constraint)
- Transaction ledger (orders and captures)
- Dispute lifecycle tracking with audit history
"""
from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional, Tuple

from src.utils.logging_config import setup_logging

logger = setup_logging(name="storage.db")

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB_PATH = str((PROJECT_ROOT / "data" / "proofledger.db").resolve())
LEGACY_CHAIN_LOG_PATH = str((PROJECT_ROOT / "data" / "events_hash_chain.jsonl").resolve())
V2_CHAIN_LOG_PATH = str((PROJECT_ROOT / "data" / "events_hash_chain_v2.jsonl").resolve())
DEFAULT_CHAIN_LOG_PATH = V2_CHAIN_LOG_PATH
DEFAULT_LOCK_PATH = f"{V2_CHAIN_LOG_PATH}.lock"


class SilentFallbackProhibitedError(RuntimeError):
    """Raised when an operation attempts to silently fall back to legacy ledger."""
    pass


class DatabaseError(Exception):
    """Raised when a durable persistence operation fails."""
    pass


def get_db_path(db_path: Optional[str] = None) -> str:
    raw = db_path or os.getenv("DATABASE_PATH") or DEFAULT_DB_PATH
    p = Path(raw)
    if not p.is_absolute():
        p = PROJECT_ROOT / p
    p.parent.mkdir(parents=True, exist_ok=True)
    return str(p.resolve())


def get_chain_log_path(chain_log_path: Optional[str] = None) -> str:
    raw = chain_log_path or os.getenv("CHAIN_LOG_PATH") or V2_CHAIN_LOG_PATH
    p = Path(raw)
    if not p.is_absolute():
        p = PROJECT_ROOT / p

    # STRICT GUARD: If active V2 ledger is designated, never silently fall back to legacy
    if not chain_log_path and not os.getenv("CHAIN_LOG_PATH"):
        if not p.exists() and Path(LEGACY_CHAIN_LOG_PATH).exists():
            logger.critical(
                "Active V2 ledger '%s' is missing. Silent fallback to legacy ledger '%s' is strictly prohibited.",
                p, LEGACY_CHAIN_LOG_PATH
            )
            raise SilentFallbackProhibitedError(
                f"Active V2 ledger '{p}' does not exist. Silent fallback to legacy ledger '{LEGACY_CHAIN_LOG_PATH}' is prohibited."
            )

    p.parent.mkdir(parents=True, exist_ok=True)
    return str(p.resolve())


def get_lock_path(chain_log_path: Optional[str] = None) -> str:
    """Return the dedicated, persistent .lock file path associated with the ledger."""
    p = get_chain_log_path(chain_log_path)
    return f"{p}.lock"


@contextmanager
def get_connection(db_path: Optional[str] = None) -> Generator[sqlite3.Connection, None, None]:
    path = get_db_path(db_path)
    conn = sqlite3.connect(path, timeout=10.0)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("PRAGMA journal_mode = WAL;")
        yield conn
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise DatabaseError(f"Database transaction error: {e}") from e
    finally:
        conn.close()


def init_db(db_path: Optional[str] = None) -> None:
    """Initialize database tables and indexes."""
    with get_connection(db_path) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS webhook_events (
                event_id TEXT PRIMARY KEY,
                event_type TEXT NOT NULL,
                resource_type TEXT,
                resource_id TEXT,
                transaction_reference TEXT,
                status TEXT NOT NULL,
                summary TEXT,
                raw_payload TEXT NOT NULL,
                received_at TEXT NOT NULL,
                processed_at TEXT NOT NULL
            );
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS transactions (
                transaction_id TEXT PRIMARY KEY,
                order_id TEXT,
                capture_id TEXT,
                amount TEXT,
                currency TEXT,
                status TEXT NOT NULL,
                last_event_id TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                metadata_json TEXT
            );
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_transactions_order_id ON transactions (order_id);
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_transactions_capture_id ON transactions (capture_id);
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS disputes (
                dispute_id TEXT PRIMARY KEY,
                transaction_reference TEXT,
                reason TEXT,
                status TEXT NOT NULL,
                dispute_amount TEXT,
                currency TEXT,
                resolution_outcome TEXT,
                evidence_prepared INTEGER DEFAULT 0,
                evidence_compilation_id TEXT,
                received_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                history_json TEXT NOT NULL,
                raw_payload TEXT
            );
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_disputes_tx_ref ON disputes (transaction_reference);
        """)


def get_webhook_event(event_id: str, db_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Retrieve an event by ID. Returns None if not found."""
    init_db(db_path)
    with get_connection(db_path) as conn:
        cursor = conn.execute(
            "SELECT * FROM webhook_events WHERE event_id = ?",
            (event_id,),
        )
        row = cursor.fetchone()
        if row:
            return dict(row)
    return None


def record_webhook_event(
    event_id: str,
    event_type: str,
    resource_type: Optional[str],
    resource_id: Optional[str],
    transaction_reference: Optional[str],
    status: str,
    summary: str,
    raw_payload: str,
    db_path: Optional[str] = None,
) -> Tuple[bool, str]:
    """
    Persist incoming webhook event enforcing database-level primary key uniqueness.
    Returns (True, "RECORDED") on success.
    Returns (False, "DUPLICATE") if event_id already exists.
    Raises DatabaseError on write failure.
    """
    init_db(db_path)
    now = datetime.now(timezone.utc).isoformat()
    try:
        with get_connection(db_path) as conn:
            conn.execute(
                """
                INSERT INTO webhook_events (
                    event_id, event_type, resource_type, resource_id,
                    transaction_reference, status, summary, raw_payload,
                    received_at, processed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event_id, event_type, resource_type, resource_id,
                    transaction_reference, status, summary, raw_payload,
                    now, now,
                ),
            )
            return True, "RECORDED"
    except DatabaseError as e:
        if isinstance(e.__cause__, sqlite3.IntegrityError):
            logger.info(f"Database uniqueness constraint caught duplicate event {event_id}")
            return False, "DUPLICATE"
        raise


def find_webhook_event_strict(
    capture_id: str,
    order_id: str,
    event_type: str = "PAYMENT.CAPTURE.COMPLETED",
    db_path: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """
    Strictly correlate a webhook event by requiring BOTH:
    1. resource_id == expected_capture_id
    2. transaction_reference == expected_order_id
    Never matches with loose OR conditions.
    """
    init_db(db_path)
    with get_connection(db_path) as conn:
        cursor = conn.execute(
            """
            SELECT * FROM webhook_events
            WHERE event_type = ?
              AND resource_id = ?
              AND transaction_reference = ?
            LIMIT 1
            """,
            (event_type, capture_id, order_id),
        )
        row = cursor.fetchone()
        if row:
            return dict(row)
    return None


def find_transaction(
    identifier: str,
    db_path: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """
    Search for a transaction strictly by exact primary identifier:
    transaction_id, order_id, or capture_id.
    Never matches by customer name or amount.
    """
    init_db(db_path)
    with get_connection(db_path) as conn:
        cursor = conn.execute(
            """
            SELECT * FROM transactions
            WHERE transaction_id = ? OR order_id = ? OR capture_id = ?
            LIMIT 1
            """,
            (identifier, identifier, identifier),
        )
        row = cursor.fetchone()
        if row:
            res = dict(row)
            if res.get("metadata_json"):
                try:
                    res["metadata"] = json.loads(res["metadata_json"])
                except Exception:
                    res["metadata"] = {}
            return res
    return None


def upsert_transaction(
    transaction_id: str,
    order_id: Optional[str],
    capture_id: Optional[str],
    amount: Optional[str],
    currency: Optional[str],
    status: str,
    event_id: str,
    metadata: Optional[Dict[str, Any]] = None,
    db_path: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Insert or update a transaction record in durable ledger.
    """
    init_db(db_path)
    now = datetime.now(timezone.utc).isoformat()
    existing = find_transaction(transaction_id, db_path=db_path)
    meta_json = json.dumps(metadata or {})

    with get_connection(db_path) as conn:
        if existing:
            # Update existing transaction
            conn.execute(
                """
                UPDATE transactions
                SET order_id = COALESCE(?, order_id),
                    capture_id = COALESCE(?, capture_id),
                    amount = COALESCE(?, amount),
                    currency = COALESCE(?, currency),
                    status = ?,
                    last_event_id = ?,
                    updated_at = ?,
                    metadata_json = ?
                WHERE transaction_id = ?
                """,
                (
                    order_id, capture_id, amount, currency,
                    status, event_id, now, meta_json, existing["transaction_id"],
                ),
            )
        else:
            conn.execute(
                """
                INSERT INTO transactions (
                    transaction_id, order_id, capture_id, amount,
                    currency, status, last_event_id, created_at,
                    updated_at, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    transaction_id, order_id, capture_id, amount,
                    currency, status, event_id, now, now, meta_json,
                ),
            )

    return find_transaction(transaction_id, db_path=db_path) or {}


def record_dispute(
    dispute_id: str,
    transaction_reference: Optional[str],
    reason: str,
    status: str,
    dispute_amount: Optional[str],
    currency: Optional[str],
    raw_payload: str,
    event_id: str,
    db_path: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Record an incoming dispute with audit history.
    """
    init_db(db_path)
    now = datetime.now(timezone.utc).isoformat()
    existing = get_dispute(dispute_id, db_path=db_path)

    initial_history = [{
        "status": status,
        "event_id": event_id,
        "timestamp": now,
        "action": "DISPUTE_RECORDED",
    }]

    with get_connection(db_path) as conn:
        if existing:
            history = json.loads(existing.get("history_json") or "[]")
            history.append({
                "status": status,
                "event_id": event_id,
                "timestamp": now,
                "action": "DISPUTE_UPDATED",
            })
            conn.execute(
                """
                UPDATE disputes
                SET transaction_reference = COALESCE(?, transaction_reference),
                    reason = COALESCE(?, reason),
                    status = ?,
                    dispute_amount = COALESCE(?, dispute_amount),
                    currency = COALESCE(?, currency),
                    updated_at = ?,
                    history_json = ?,
                    raw_payload = ?
                WHERE dispute_id = ?
                """,
                (
                    transaction_reference, reason, status,
                    dispute_amount, currency, now,
                    json.dumps(history), raw_payload, dispute_id,
                ),
            )
        else:
            conn.execute(
                """
                INSERT INTO disputes (
                    dispute_id, transaction_reference, reason, status,
                    dispute_amount, currency, resolution_outcome,
                    evidence_prepared, evidence_compilation_id,
                    received_at, updated_at, history_json, raw_payload
                ) VALUES (?, ?, ?, ?, ?, ?, NULL, 0, NULL, ?, ?, ?, ?)
                """,
                (
                    dispute_id, transaction_reference, reason, status,
                    dispute_amount, currency, now, now,
                    json.dumps(initial_history), raw_payload,
                ),
            )

    return get_dispute(dispute_id, db_path=db_path) or {}


def update_dispute_status(
    dispute_id: str,
    status: str,
    resolution_outcome: Optional[str],
    event_id: str,
    raw_payload: Optional[str] = None,
    db_path: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """
    Update dispute status and append to audit history.
    """
    init_db(db_path)
    now = datetime.now(timezone.utc).isoformat()
    existing = get_dispute(dispute_id, db_path=db_path)
    if not existing:
        return None

    history = json.loads(existing.get("history_json") or "[]")
    history.append({
        "status": status,
        "resolution_outcome": resolution_outcome,
        "event_id": event_id,
        "timestamp": now,
        "action": "STATUS_CHANGED",
    })

    with get_connection(db_path) as conn:
        conn.execute(
            """
            UPDATE disputes
            SET status = ?,
                resolution_outcome = COALESCE(?, resolution_outcome),
                updated_at = ?,
                history_json = ?,
                raw_payload = COALESCE(?, raw_payload)
            WHERE dispute_id = ?
            """,
            (
                status, resolution_outcome, now,
                json.dumps(history), raw_payload, dispute_id,
            ),
        )

    return get_dispute(dispute_id, db_path=db_path)


def set_dispute_evidence_prepared(
    dispute_id: str,
    compilation_id: str,
    db_path: Optional[str] = None,
) -> None:
    """Mark that an evidence dossier has been compiled (requires seller human approval before submission)."""
    init_db(db_path)
    with get_connection(db_path) as conn:
        conn.execute(
            """
            UPDATE disputes
            SET evidence_prepared = 1,
                evidence_compilation_id = ?
            WHERE dispute_id = ?
            """,
            (compilation_id, dispute_id),
        )


def get_dispute(dispute_id: str, db_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Retrieve dispute details including history."""
    init_db(db_path)
    with get_connection(db_path) as conn:
        cursor = conn.execute(
            "SELECT * FROM disputes WHERE dispute_id = ?",
            (dispute_id,),
        )
        row = cursor.fetchone()
        if row:
            res = dict(row)
            if res.get("history_json"):
                try:
                    res["history"] = json.loads(res["history_json"])
                except Exception:
                    res["history"] = []
            return res
    return None

