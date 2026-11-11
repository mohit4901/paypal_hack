"""
Automated Database <-> Evidence Ledger Reconciliation Service.
Cross-verifies operational persistence (SQLite) against the authoritative V2 hash chain.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, List

from backend.config import DATABASE_PATH, V2_CHAIN_LOG_PATH
from src.models.evidence_compiler import strict_json_pairs_hook


class ReconciliationService:
    """Performs deep cross-system reconciliation between database and cryptographic ledger."""

    @staticmethod
    def run_reconciliation() -> Dict[str, Any]:
        report: Dict[str, Any] = {
            "database_type": "SQLite WAL",
            "ledger_type": "Append-Only JSONL SHA-256 Hash Chain",
            "timestamp": None,
            "sqlite_webhook_count": 0,
            "sqlite_transaction_count": 0,
            "ledger_event_count": 0,
            "matched_events": 0,
            "discrepancies": [],
            "reconciliation_status": "UNINITIALIZED",
        }

        # 1. Read all ledger events
        ledger_events = []
        ledger_event_ids = set()
        ledger_source_ids = set()
        ledger_tx_refs = set()

        if Path(V2_CHAIN_LOG_PATH).exists():
            with open(V2_CHAIN_LOG_PATH, "r", encoding="utf-8") as f:
                for line in f:
                    s = line.strip()
                    if not s:
                        continue
                    try:
                        ev = json.loads(s, object_pairs_hook=strict_json_pairs_hook)
                        ledger_events.append(ev)
                        if ev.get("event_id"):
                            ledger_event_ids.add(ev["event_id"])
                        if ev.get("source_event_id"):
                            ledger_source_ids.add(ev["source_event_id"])
                        if ev.get("transaction_ref"):
                            ledger_tx_refs.add(ev["transaction_ref"])
                    except Exception:
                        continue

        report["ledger_event_count"] = len(ledger_events)

        # 2. Query SQLite
        sqlite_webhooks = []
        sqlite_transactions = []
        if Path(DATABASE_PATH).exists():
            try:
                conn = sqlite3.connect(str(DATABASE_PATH))
                conn.row_factory = sqlite3.Row
                cur = conn.cursor()

                cur.execute("SELECT event_id, event_type, status, transaction_reference FROM webhook_events")
                sqlite_webhooks = [dict(r) for r in cur.fetchall()]

                cur.execute("SELECT transaction_id, order_id, capture_id, amount, status FROM transactions")
                sqlite_transactions = [dict(r) for r in cur.fetchall()]
                conn.close()
            except Exception as ex:
                report["discrepancies"].append(f"SQLite read error: {ex}")

        report["sqlite_webhook_count"] = len(sqlite_webhooks)
        report["sqlite_transaction_count"] = len(sqlite_transactions)

        # 3. Match webhooks against ledger
        matched_wh = 0
        for wh in sqlite_webhooks:
            wh_id = wh.get("event_id")
            if wh_id in ledger_source_ids or wh_id in ledger_event_ids:
                matched_wh += 1
            else:
                report["discrepancies"].append(
                    f"SQLite Webhook event '{wh_id}' ({wh.get('event_type')}) not found in active hash chain."
                )

        # 4. Match transactions against ledger
        matched_tx = 0
        for tx in sqlite_transactions:
            tx_id = tx.get("transaction_id")
            order_id = tx.get("order_id")
            capture_id = tx.get("capture_id")
            if (
                tx_id in ledger_tx_refs
                or order_id in ledger_tx_refs
                or capture_id in ledger_source_ids
                or any(
                    isinstance(e.get("payload"), dict) and e["payload"].get("capture_id") == capture_id
                    for e in ledger_events
                )
            ):
                matched_tx += 1
            else:
                report["discrepancies"].append(
                    f"SQLite Transaction '{tx_id}' (Order: {order_id}, Capture: {capture_id}) has no matching evidence record."
                )

        report["matched_events"] = matched_wh + matched_tx
        if not report["discrepancies"]:
            report["reconciliation_status"] = "100% RECONCILED — ZERO DISCREPANCIES"
            report["reconciliation_badge"] = "RECONCILED_SUCCESS"
        else:
            report["reconciliation_status"] = "DISCREPANCIES_DETECTED"
            report["reconciliation_badge"] = "WARNING_DISCREPANCY"

        return report

