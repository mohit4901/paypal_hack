"""
ProofLedger — Real PayPal Sandbox End-to-End Lifecycle Verification Runner.

Hardened Implementation:
1. Strict Sandbox-only isolation (enforces PAYPAL_MODE=sandbox and https://api-m.sandbox.paypal.com)
2. UUID-based collision-free order reference IDs
3. Full capture response validation:
   - Order-level status must be COMPLETED
   - Individual capture resource status must be COMPLETED
   - Capture ID must be valid, non-empty, and not 'unknown'
   - Exact amount ($5.00) and currency (USD) verification
   - Purchase unit reference ID match
4. In-doubt / ambiguous capture reconciliation:
   - Handles network timeouts / connection drops without blind retry
   - Reconciles order state from get_order() before any action
5. Strict webhook correlation (requires BOTH resource_id==capture_id AND transaction_reference==order_id)
6. Durable signature verification check (requires status='PROCESSED' in SQLite)
7. Event-specific SHA-256 hash-chain verification:
   - Entire chain integrity validation
   - Confirms exact webhook event_id exists in chain
   - Confirms event digest/payload matches
8. Absolute project-root path resolution for database and logs
9. Sanitized error reporting (never dumps raw responses or PII/credentials)
10. Strict 8-point verification checklist (NO unconditional success reporting)
11. Explicit terminal confirmation before capture (never auto-captures)
12. Zero automatic dispute evidence submission & zero digital-delivery presumption

NEVER exposes secrets, access tokens, or buyer credentials.
NEVER uses live endpoints or real money.
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from dotenv import load_dotenv

# Absolute path resolution relative to AI project root
PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env", override=True)

from src.integrations.paypal_client import (
    PayPalClient,
    PayPalClientError,
    SANDBOX_BASE,
)
from src.models.evidence_compiler import EventLog
from src.storage.db import (
    DEFAULT_CHAIN_LOG_PATH,
    DEFAULT_DB_PATH,
    find_transaction,
    find_webhook_event_strict,
    get_chain_log_path,
    get_connection,
    init_db,
)


def sanitize_message(data: Any) -> str:
    """Sanitize error messages or objects to prevent accidental token/secret/PII exposure."""
    text = str(data)
    # Mask client secrets, tokens, bearer headers
    text = re.sub(r"(access_token['\":\s=]+['\"]?)[A-Za-z0-9_\-\.]{10,}['\"]?", r"\1[REDACTED_TOKEN]", text, flags=re.I)
    text = re.sub(r"(client_secret['\":\s=]+['\"]?)[A-Za-z0-9_\-\.]{10,}['\"]?", r"\1[REDACTED_SECRET]", text, flags=re.I)
    text = re.sub(r"(Bearer\s+)[A-Za-z0-9_\-\.]{10,}", r"\1[REDACTED_BEARER]", text, flags=re.I)
    # Mask passwords (e.g. password=..., "password": "...", password: ...)
    text = re.sub(r"((?:buyer_)?password['\":\s=]+['\"]?)[^\s'\",}]+(['\"]?)", r"\1[REDACTED_PASSWORD]\2", text, flags=re.I)
    # Mask buyer email addresses
    text = re.sub(r"[\w\.\+\-]+@[\w\.\-]+\.\w{2,}", "[REDACTED_EMAIL]", text)
    return text


def verify_sandbox_isolation(client: PayPalClient) -> None:
    """Strictly assert that execution is locked exclusively to PayPal Sandbox."""
    mode = os.getenv("PAYPAL_MODE", "").lower().strip()
    if mode != "sandbox":
        print(f"\n[CRITICAL ERROR] PAYPAL_MODE is '{mode}', expected 'sandbox'. Aborting for safety.")
        sys.exit(1)

    if client._base_url != SANDBOX_BASE or client._base_url != "https://api-m.sandbox.paypal.com":
        print(f"\n[CRITICAL ERROR] Client base URL is '{client._base_url}', expected '{SANDBOX_BASE}'. Aborting.")
        sys.exit(1)

    if not client.is_configured:
        print("\n[CRITICAL ERROR] PayPal credentials not found in .env. Configure PAYPAL_CLIENT_ID and PAYPAL_CLIENT_SECRET.")
        sys.exit(1)

    webhook_id = os.getenv("PAYPAL_WEBHOOK_ID", "").strip()
    if not webhook_id:
        print("\n[CRITICAL ERROR] PAYPAL_WEBHOOK_ID is not configured in .env. Webhook signature verification will fail.")
        sys.exit(1)

    print("✓ Sandbox isolation verified: https://api-m.sandbox.paypal.com (Mode: sandbox)")
    print(f"✓ Webhook ID configured: {webhook_id[:4]}...{webhook_id[-4:]} (length {len(webhook_id)})")
    print(f"✓ SQLite Database Path:  {DEFAULT_DB_PATH}")
    print(f"✓ Hash Chain Log Path:   {get_chain_log_path()}")


def validate_capture_response(
    capture_resp: Dict[str, Any],
    expected_amount: str = "5.00",
    expected_currency: str = "USD",
    expected_reference_id: Optional[str] = None,
) -> Tuple[bool, Optional[str], Optional[str], Optional[str], Optional[str], str]:
    """
    Comprehensive validation of the PayPal capture response:
    1. Order-level status must be 'COMPLETED'
    2. purchase_units must exist and reference_id must match expected_reference_id
    3. Individual capture resource status must be 'COMPLETED'
    4. capture_id must be a valid, non-empty string and not 'unknown'
    5. capture amount must equal expected_amount (e.g. '5.00')
    6. capture currency must equal expected_currency (e.g. 'USD')

    Returns: (is_valid, capture_id, individual_status, actual_amount, actual_currency, error_message)
    """
    order_status = capture_resp.get("status")
    if order_status != "COMPLETED":
        return False, None, None, None, None, f"Order-level capture status is '{order_status}', expected 'COMPLETED'."

    purchase_units = capture_resp.get("purchase_units", [])
    if not purchase_units or not isinstance(purchase_units, list):
        return False, None, None, None, None, "Capture response missing valid 'purchase_units' list."

    pu = purchase_units[0]
    if expected_reference_id:
        actual_ref = pu.get("reference_id")
        if actual_ref != expected_reference_id:
            return False, None, None, None, None, f"Reference ID mismatch: expected '{expected_reference_id}', got '{actual_ref}'."

    payments = pu.get("payments", {})
    captures = payments.get("captures", [])
    if not captures or not isinstance(captures, list):
        return False, None, None, None, None, "Capture response missing 'payments.captures' list."

    capture_obj = captures[0]
    capture_id = capture_obj.get("id")
    ind_status = capture_obj.get("status")

    if not capture_id or str(capture_id).strip() == "" or str(capture_id).lower() == "unknown":
        return False, None, ind_status, None, None, f"Invalid or missing capture_id: '{capture_id}'."

    if ind_status != "COMPLETED":
        return False, capture_id, ind_status, None, None, f"Individual capture resource status is '{ind_status}', expected 'COMPLETED'."

    amt_obj = capture_obj.get("amount", {})
    actual_amount = amt_obj.get("value")
    actual_currency = amt_obj.get("currency_code")

    if actual_amount != expected_amount:
        return False, capture_id, ind_status, actual_amount, actual_currency, f"Capture amount mismatch: expected '{expected_amount}', got '{actual_amount}'."

    if actual_currency != expected_currency:
        return False, capture_id, ind_status, actual_amount, actual_currency, f"Capture currency mismatch: expected '{expected_currency}', got '{actual_currency}'."

    return True, capture_id, ind_status, actual_amount, actual_currency, "Capture response validated successfully."


def validate_existing_order_payload(
    order_data: Dict[str, Any],
    expected_order_id: str,
    expected_amount: str = "5.00",
    expected_currency: str = "USD",
    expected_reference_id: Optional[str] = None,
    expected_intent: str = "CAPTURE",
) -> Tuple[bool, str]:
    """
    Validate that an existing PayPal order fetched via GET /v2/checkout/orders/{id}
    matches expected transaction parameters:
    1. Order ID matches expected_order_id
    2. Intent is CAPTURE
    3. Purchase units list is non-empty
    4. Order amount matches expected_amount (e.g. '5.00')
    5. Order currency matches expected_currency (e.g. 'USD')
    6. Purchase unit reference_id matches expected_reference_id (if provided)
    """
    actual_id = order_data.get("id")
    if actual_id != expected_order_id:
        return False, f"Order ID mismatch: expected '{expected_order_id}', got '{actual_id}'."

    actual_intent = order_data.get("intent")
    if actual_intent != expected_intent:
        return False, f"Order intent mismatch: expected '{expected_intent}', got '{actual_intent}'."

    purchase_units = order_data.get("purchase_units", [])
    if not purchase_units or not isinstance(purchase_units, list):
        return False, "Order missing valid 'purchase_units' list."

    pu = purchase_units[0]
    amt_obj = pu.get("amount", {})
    actual_amount = amt_obj.get("value")
    actual_currency = amt_obj.get("currency_code")

    if actual_amount != expected_amount:
        return False, f"Order amount mismatch: expected '{expected_amount}', got '{actual_amount}'."

    if actual_currency != expected_currency:
        return False, f"Order currency mismatch: expected '{expected_currency}', got '{actual_currency}'."

    if expected_reference_id:
        actual_ref = pu.get("reference_id")
        if actual_ref != expected_reference_id:
            return False, f"Order reference_id mismatch: expected '{expected_reference_id}', got '{actual_ref}'."

    return True, "Existing order validated successfully."


def reconcile_in_doubt_capture(
    client: PayPalClient,
    order_id: str,
    expected_amount: str = "5.00",
    expected_currency: str = "USD",
    expected_reference_id: Optional[str] = None,
) -> Tuple[bool, Optional[Dict[str, Any]], str]:
    """
    Handle ambiguous capture outcomes (network drops, timeouts) safely.
    Reconciles order state from PayPal via get_order() before attempting any action.
    Never blindly retries capture.
    """
    print(f"\n[RECONCILING] Capture response was ambiguous. Querying order {order_id} status from PayPal...")
    try:
        reconciled_order = client.get_order(order_id)
    except Exception as e:
        return False, None, f"Reconciliation query failed: {sanitize_message(e)}. Status is UNKNOWN. Do not retry capture."

    reconciled_status = reconciled_order.get("status")
    if reconciled_status == "COMPLETED":
        # Capture actually succeeded on PayPal
        val_ok, cap_id, ind_st, amt, curr, val_msg = validate_capture_response(
            reconciled_order,
            expected_amount=expected_amount,
            expected_currency=expected_currency,
            expected_reference_id=expected_reference_id,
        )
        if val_ok:
            return True, reconciled_order, "Successfully reconciled completed capture from PayPal order record."
        return False, reconciled_order, f"Reconciled order found but validation failed: {val_msg}"

    return False, reconciled_order, f"Order status on PayPal is '{reconciled_status}'. Payment was NOT captured. Aborting without retry."


class ChainVerificationResult(tuple):
    """
    Rich result tuple for hash-chain verification:
    Maintains 3-tuple compatibility: (chain_valid, target_valid, message)
    while exposing independent verification attributes:
      .chain_valid: bool
      .target_valid: bool
      .message: str
      .chain_errors: List[str]
      .target_exists: bool
      .target_self_hash_ok: bool
      .target_link_ok: bool
      .sqlite_correlated: bool
      .content_authenticated: bool
      .database_correlated: bool
      .source_authenticated: bool
      .ledger_integrity_verified: bool
      .legacy_provenance_status: Optional[str]
      .v2_migration_integrity_status: Optional[str]
      .is_migrated_historical: bool
      .forensic_verdict: str
      .details: Dict[str, Any]
    """
    def __new__(
        cls,
        chain_valid: bool,
        target_valid: bool,
        message: str,
        chain_errors: Optional[List[str]] = None,
        target_exists: bool = False,
        target_self_hash_ok: bool = False,
        target_link_ok: bool = False,
        sqlite_correlated: bool = False,
        content_authenticated: bool = False,
        database_correlated: bool = False,
        source_authenticated: bool = False,
        ledger_integrity_verified: bool = False,
        legacy_provenance_status: Optional[str] = None,
        v2_migration_integrity_status: Optional[str] = None,
        is_migrated_historical: bool = False,
        forensic_verdict: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        instance = super().__new__(cls, (chain_valid, target_valid, message))
        instance.chain_valid = chain_valid
        instance.target_valid = target_valid
        instance.message = message
        instance.chain_errors = chain_errors or []
        instance.target_exists = target_exists
        instance.target_self_hash_ok = target_self_hash_ok
        instance.target_link_ok = target_link_ok
        instance.sqlite_correlated = sqlite_correlated
        instance.content_authenticated = content_authenticated
        instance.database_correlated = database_correlated
        instance.source_authenticated = source_authenticated
        instance.ledger_integrity_verified = ledger_integrity_verified
        instance.legacy_provenance_status = legacy_provenance_status
        instance.v2_migration_integrity_status = v2_migration_integrity_status
        instance.is_migrated_historical = is_migrated_historical
        instance.forensic_verdict = forensic_verdict or "FAILED_VERIFICATION"
        instance.details = details or {}
        instance.details["forensic_verdict"] = instance.forensic_verdict
        return instance


def verify_event_in_hash_chain(
    chain_log_path: str,
    expected_event_id: str,
    expected_event_type: str = "PAYMENT.CAPTURE.COMPLETED",
    expected_capture_id: Optional[str] = None,
    expected_order_id: Optional[str] = None,
    sqlite_event_record: Optional[Dict[str, Any]] = None,
    source_authenticated: Optional[bool] = None,
) -> ChainVerificationResult:
    """
    Event-specific multi-dimensional verification of the append-only SHA-256 hash chain:
    1. Entire chain integrity is independently validated via verify_chain().
    2. Target event presence is verified.
    3. Content Authentication: Target event cryptographic self-hash matches canonical serialization.
    4. Database Correlation: Cross-checks against durable SQLite webhook and transaction records.
    5. Source Authentication: Independent validation of trusted source (PayPal webhook signature & API).
    6. Ledger Integrity: Target event predecessor linkage in active ledger.
    7. Legacy Provenance: Preserves historical unverified link & order limitations for migrated records.
    8. V2 Migration Integrity: Verifies strict migration provenance without upgrading historical status.

    Returns: ChainVerificationResult (unpacks as (chain_valid, target_valid, message))
    """
    p = Path(chain_log_path)
    if not p.exists():
        return ChainVerificationResult(
            chain_valid=False,
            target_valid=False,
            message=f"Hash chain log file '{chain_log_path}' does not exist.",
            chain_errors=[f"File '{chain_log_path}' not found."],
        )

    try:
        event_log = EventLog(log_path=chain_log_path)
    except Exception as e:
        return ChainVerificationResult(
            chain_valid=False,
            target_valid=False,
            message=f"Hash chain log parsing failed: {e}",
            chain_errors=[str(e)],
        )

    # 1. Full chain integrity check (DO NOT early-return on error)
    chain_valid, chain_errors = event_log.verify_chain()

    if not event_log.events:
        return ChainVerificationResult(
            chain_valid=chain_valid,
            target_valid=False,
            message="Hash chain is empty. Target event not found.",
            chain_errors=chain_errors,
            target_exists=False,
            details={"chain_valid": chain_valid, "total_events": 0},
        )

    # 2. Target event existence lookup
    target_entry = None
    target_idx = None
    for idx, entry in enumerate(event_log.events):
        if entry.get("source_event_id") == expected_event_id or entry.get("event_id") == expected_event_id:
            target_entry = entry
            target_idx = idx
            break

    target_exists = (target_entry is not None)
    if not target_exists:
        chain_desc = "valid" if chain_valid else f"BROKEN ({len(chain_errors)} errors)"
        return ChainVerificationResult(
            chain_valid=chain_valid,
            target_valid=False,
            message=f"Target event_id '{expected_event_id}' not found in the hash chain ({len(event_log.events)} entries). Chain integrity: {chain_desc}.",
            chain_errors=chain_errors,
            target_exists=False,
            details={"chain_valid": chain_valid, "total_events": len(event_log.events)},
        )

    # 3. Target event independent self-hash check
    target_current_hash = target_entry.get("current_hash")
    target_without_hash = {k: v for k, v in target_entry.items() if k != "current_hash"}
    computed_hash = event_log._hash_event(target_without_hash)
    target_self_hash_ok = (computed_hash == target_current_hash)

    # 4. Target event predecessor linkage check
    if target_idx == 0:
        target_link_ok = (target_entry.get("previous_hash") == "genesis")
    else:
        expected_prev = event_log.events[target_idx - 1].get("current_hash")
        target_link_ok = (target_entry.get("previous_hash") == expected_prev)

    # 5. Payload and capture ID validation
    payload = target_entry.get("payload", {})
    type_ok = (payload.get("event_type") == expected_event_type)
    chain_tx_ref = target_entry.get("transaction_ref")
    tx_ref_ok = True if not expected_capture_id else (chain_tx_ref == expected_capture_id)

    # 6. SQLite cross-correlation
    sqlite_correlated = True
    sqlite_mismatches = []
    if sqlite_event_record:
        rec_event_id = sqlite_event_record.get("event_id")
        if rec_event_id != expected_event_id:
            sqlite_correlated = False
            sqlite_mismatches.append(f"event_id '{rec_event_id}' != expected '{expected_event_id}'")

        rec_event_type = sqlite_event_record.get("event_type")
        if rec_event_type != expected_event_type:
            sqlite_correlated = False
            sqlite_mismatches.append(f"event_type '{rec_event_type}' != expected '{expected_event_type}'")

        rec_resource_id = sqlite_event_record.get("resource_id")
        if rec_resource_id and chain_tx_ref != rec_resource_id:
            sqlite_correlated = False
            sqlite_mismatches.append(f"chain transaction_ref '{chain_tx_ref}' != SQLite resource_id '{rec_resource_id}'")

        if expected_order_id:
            rec_tx_ref = sqlite_event_record.get("transaction_reference")
            if rec_tx_ref != expected_order_id:
                sqlite_correlated = False
                sqlite_mismatches.append(f"SQLite transaction_reference '{rec_tx_ref}' != expected order_id '{expected_order_id}'")

        raw_payload = sqlite_event_record.get("raw_payload")
        if raw_payload:
            try:
                raw_data = json.loads(raw_payload) if isinstance(raw_payload, str) else raw_payload
                if isinstance(raw_data, dict):
                    expected_summary = raw_data.get("summary")
                    chain_summary = payload.get("summary")
                    if expected_summary is not None and chain_summary != expected_summary:
                        sqlite_correlated = False
                        sqlite_mismatches.append(f"summary '{chain_summary}' != raw payload summary '{expected_summary}'")
                    if raw_data.get("id") and raw_data.get("id") != expected_event_id:
                        sqlite_correlated = False
                        sqlite_mismatches.append(f"raw payload id '{raw_data.get('id')}' != expected '{expected_event_id}'")
            except Exception as ex:
                sqlite_correlated = False
                sqlite_mismatches.append(f"Failed to parse SQLite raw_payload: {ex}")

    # 7. Multi-dimensional status evaluations
    content_authenticated = bool(target_self_hash_ok and type_ok and tx_ref_ok)
    database_correlated = bool(sqlite_correlated)
    ledger_integrity_verified = bool(chain_valid and target_link_ok)
    is_migrated_historical = bool(target_entry.get("v2_migration"))

    # Source authentication: from PayPal webhook signature / API verification
    if source_authenticated is None:
        if sqlite_event_record and sqlite_event_record.get("status") == "PROCESSED":
            is_source_authenticated = True
        else:
            is_source_authenticated = False
    else:
        is_source_authenticated = bool(source_authenticated)

    target_valid = (
        target_exists
        and content_authenticated
        and database_correlated
    )

    # 8. Provenance and migration determinations
    if is_migrated_historical:
        legacy_provenance = "HISTORICAL_CHAIN_LINK_UNVERIFIED & HISTORICAL_ORDER_UNVERIFIED"
        migration_status = "V2_MIGRATION_INTEGRITY_VERIFIED"
    elif target_link_ok and chain_valid:
        legacy_provenance = "NATIVE_CHAIN_PROVENANCE_ESTABLISHED"
        migration_status = "NATIVE_RECORD"
    else:
        legacy_provenance = "HISTORICAL_CHAIN_LINK_UNVERIFIED"
        migration_status = "NATIVE_RECORD"

    # 9. Build detailed diagnostic summary & forensic verdict
    target_issues = []
    if not target_self_hash_ok:
        target_issues.append("self-hash mismatch (payload altered)")
    if not type_ok:
        target_issues.append(f"event_type '{payload.get('event_type')}' != expected '{expected_event_type}'")
    if not tx_ref_ok:
        target_issues.append(f"transaction_ref '{chain_tx_ref}' != expected capture_id '{expected_capture_id}'")
    if sqlite_mismatches:
        target_issues.extend(sqlite_mismatches)

    chain_status_str = "Full chain is cryptographically VALID." if chain_valid else f"Historical chain has {len(chain_errors)} broken link(s)."
    link_status_str = "Predecessor link: VALID." if target_link_ok else f"Predecessor link: BROKEN (previous_hash='{target_entry.get('previous_hash')}')."
    details_suffix = " (Cross-checked against SQLite record)" if sqlite_event_record else ""

    if target_valid:
        if is_migrated_historical:
            # Forensic rule: V2 migration must NOT upgrade historical provenance
            verdict_badge = "CONTENT_AUTHENTICATED & DATABASE_CORRELATED & V2_MIGRATION_INTEGRITY_VERIFIED — HISTORICAL PROVENANCE UNVERIFIED"
            status_summary = (
                f"Target event '{expected_event_id}' verified at migrated index {target_idx}: "
                f"CONTENT_AUTHENTICATED & DATABASE_CORRELATED & V2_MIGRATION_INTEGRITY_VERIFIED — HISTORICAL PROVENANCE UNVERIFIED.{details_suffix}"
            )
        elif not target_link_ok or not chain_valid:
            verdict_badge = "CONTENT_AUTHENTICATED & DATABASE_CORRELATED — HISTORICAL CHAIN LINK UNVERIFIED"
            status_summary = (
                f"Target event '{expected_event_id}' authenticated at index {target_idx}: "
                f"CONTENT_AUTHENTICATED & DATABASE_CORRELATED — HISTORICAL CHAIN LINK UNVERIFIED.{details_suffix}"
            )
        else:
            # Native unbroken chain
            if is_source_authenticated:
                verdict_badge = "VERIFIED_VALID & AUTHENTIC"
                status_summary = f"Target event '{expected_event_id}' verified in valid hash chain ({len(event_log.events)} entries).{details_suffix}"
            else:
                verdict_badge = "LEDGER_INTEGRITY_VERIFIED — SOURCE_AUTHENTICATION_PENDING_OR_UNVERIFIED"
                status_summary = (
                    f"Target event '{expected_event_id}' verified in valid hash chain ({len(event_log.events)} entries), "
                    f"source authentication pending or unverified.{details_suffix}"
                )

        msg = (
            f"{status_summary} [{chain_status_str}] [{link_status_str}] "
            f"[Legacy Provenance: {legacy_provenance}] [V2 Migration: {migration_status}] "
            f"[Source Auth: {'VERIFIED' if is_source_authenticated else 'UNVERIFIED'}] "
            f"[Verdict: {verdict_badge}]"
        )
    else:
        verdict_badge = "FAILED_VERIFICATION"
        msg = (
            f"Target event '{expected_event_id}' failed verification: "
            f"{'; '.join(target_issues)}. "
            f"[{chain_status_str}] [{link_status_str}] "
            f"[Legacy Provenance: {legacy_provenance}] [V2 Migration: {migration_status}] "
            f"[Source Auth: {'VERIFIED' if is_source_authenticated else 'UNVERIFIED'}] "
            f"[Verdict: {verdict_badge}]"
        )

    details = {
        "chain_valid": chain_valid,
        "chain_errors_count": len(chain_errors),
        "target_exists": target_exists,
        "target_index": target_idx,
        "target_self_hash_ok": target_self_hash_ok,
        "target_link_ok": target_link_ok,
        "target_type_ok": type_ok,
        "target_tx_ref_ok": tx_ref_ok,
        "sqlite_correlated": sqlite_correlated,
        "content_authenticated": content_authenticated,
        "database_correlated": database_correlated,
        "source_authenticated": is_source_authenticated,
        "ledger_integrity_verified": ledger_integrity_verified,
        "legacy_provenance_status": legacy_provenance,
        "v2_migration_integrity_status": migration_status,
        "is_migrated_historical": is_migrated_historical,
        "target_valid": target_valid,
        "forensic_verdict": verdict_badge,
    }

    return ChainVerificationResult(
        chain_valid=chain_valid,
        target_valid=target_valid,
        message=msg,
        chain_errors=chain_errors,
        target_exists=target_exists,
        target_self_hash_ok=target_self_hash_ok,
        target_link_ok=target_link_ok,
        sqlite_correlated=sqlite_correlated,
        content_authenticated=content_authenticated,
        database_correlated=database_correlated,
        source_authenticated=is_source_authenticated,
        ledger_integrity_verified=ledger_integrity_verified,
        legacy_provenance_status=legacy_provenance,
        v2_migration_integrity_status=migration_status,
        is_migrated_historical=is_migrated_historical,
        forensic_verdict=verdict_badge,
        details=details,
    )


def wait_for_webhook_event_strict(
    order_id: str,
    capture_id: str,
    db_path: str = DEFAULT_DB_PATH,
    timeout_s: int = 90,
    poll_interval_s: float = 2.0,
) -> Optional[Dict[str, Any]]:
    """
    Poll durable SQLite database strictly matching BOTH expected capture_id AND order_id.
    Never accepts loose OR matching.
    """
    print(f"\nWaiting for PayPal to deliver signed webhook (timeout {timeout_s}s)...")
    start_time = time.time()

    while time.time() - start_time < timeout_s:
        event = find_webhook_event_strict(
            capture_id=capture_id,
            order_id=order_id,
            event_type="PAYMENT.CAPTURE.COMPLETED",
            db_path=db_path,
        )
        if event:
            return event

        elapsed = int(time.time() - start_time)
        print(f"  ... listening on SQLite (elapsed: {elapsed}s / {timeout_s}s)", end="\r", flush=True)
        time.sleep(poll_interval_s)

    return None


def evaluate_lifecycle_checklist(
    capture_valid: bool,
    capture_id: Optional[str],
    amount_valid: bool,
    webhook_event: Optional[Dict[str, Any]],
    tx_record: Optional[Dict[str, Any]],
    hash_chain_target_valid: bool,
) -> Tuple[bool, str, Dict[str, bool]]:
    """
    Evaluate the strict 8-point verification checklist.
    Unconditional success is prohibited.
    """
    chk: Dict[str, bool] = {
        "capture_response_completed": capture_valid,
        "valid_capture_id": bool(capture_id and capture_id != "unknown"),
        "capture_amount_and_currency_verified": amount_valid,
        "exact_webhook_received": bool(webhook_event is not None),
        "signature_verified": bool(webhook_event and webhook_event.get("status") == "PROCESSED"),
        "sqlite_transaction_exists": bool(tx_record is not None),
        "transaction_status_completed": bool(tx_record and tx_record.get("status") == "COMPLETED"),
        "transaction_capture_id_matches": bool(tx_record and tx_record.get("capture_id") == capture_id),
        "hash_chain_target_verified": hash_chain_target_valid,
    }

    all_passed = all(chk.values())
    if all_passed:
        verdict = "SUCCESSFUL"
    elif chk["capture_response_completed"] and not chk["exact_webhook_received"]:
        verdict = "PARTIAL (Payment captured, but webhook delivery/verification incomplete)"
    else:
        verdict = "FAILED"

    return all_passed, verdict, chk


def run_lifecycle(
    existing_order_id: Optional[str] = None,
    expected_reference_id: Optional[str] = None,
) -> None:
    print("=" * 70)
    print("ProofLedger — Real PayPal Sandbox End-to-End Lifecycle Verification")
    print("=" * 70)

    # 1. Initialize & verify isolation
    client = PayPalClient(mode="sandbox")
    verify_sandbox_isolation(client)
    init_db(DEFAULT_DB_PATH)

    if existing_order_id:
        order_id = existing_order_id.strip()
        print(f"\nStep 1: Resuming verification for existing order {order_id}...")
        try:
            order_data = client.get_order(order_id)
        except PayPalClientError as e:
            print(f"\n[ERROR] Failed to fetch order {order_id}: {sanitize_message(e)}")
            sys.exit(1)

        val_order_ok, val_order_msg = validate_existing_order_payload(
            order_data=order_data,
            expected_order_id=order_id,
            expected_amount="5.00",
            expected_currency="USD",
            expected_reference_id=expected_reference_id,
            expected_intent="CAPTURE",
        )
        if not val_order_ok:
            print(f"\n[ERROR] Existing order validation failed: {val_order_msg}")
            sys.exit(1)

        pu = order_data["purchase_units"][0]
        ref_id = pu.get("reference_id")
        order_status = order_data.get("status")
        amt_obj = pu.get("amount", {})
        links = order_data.get("links", [])
        approval_url = None
        for link in links:
            if link.get("rel") == "approve":
                approval_url = link.get("href")
                break
        if not approval_url:
            approval_url = f"https://www.sandbox.paypal.com/checkoutnow?token={order_id}"

        print(f"  ✓ Order retrieved and validated from PayPal Sandbox:")
        print(f"    • Order ID:     {order_id}")
        print(f"    • Current State: {order_status}")
        print(f"    • Amount:        ${amt_obj.get('value')} {amt_obj.get('currency_code')}")
        print(f"    • Intent:        {order_data.get('intent')} (CAPTURE)")
        print(f"    • Reference ID:  {ref_id}")
    else:
        # 2. Create $5.00 Sandbox Order with UUID-based reference ID
        ref_id = f"proofledger_sb_{uuid.uuid4().hex[:12]}"
        print(f"\nStep 1: Creating $5.00 Sandbox Order (Ref: {ref_id})...")

        try:
            order_data = client.create_order(
                amount="5.00",
                currency="USD",
                reference_id=ref_id,
                description="ProofLedger Verification - Digital Goods License #001",
            )
        except PayPalClientError as e:
            print(f"\n[ERROR] Failed to create Sandbox order: {sanitize_message(e)}")
            sys.exit(1)

        order_id = order_data.get("id")
        order_status = order_data.get("status")
        links = order_data.get("links", [])
        approval_url = None
        for link in links:
            if link.get("rel") == "approve":
                approval_url = link.get("href")
                break

        if not order_id or not approval_url:
            print("\n[ERROR] Order creation response missing order_id or approval_url.")
            sys.exit(1)

        print(f"  ✓ Order created successfully!")
        print(f"    • Order ID:     {order_id}")
        print(f"    • Initial State: {order_status}")
        print(f"    • Amount:        $5.00 USD")
        print(f"    • Reference ID:  {ref_id}")

    # Variables for capture validation
    capture_resp = None
    capture_id = None
    ind_status = None
    act_amt = None
    act_curr = None
    val_ok = False

    # State dispatch
    if order_status == "COMPLETED":
        # Order is ALREADY completed on PayPal (e.g. captured previously)
        print("\n" + "-" * 70)
        print(f"Step 2-4: Order {order_id} is ALREADY 'COMPLETED' on PayPal")
        print("-" * 70)
        print("Reconciling existing capture details without duplicate capture call...")
        val_ok, capture_id, ind_status, act_amt, act_curr, val_msg = validate_capture_response(
            order_data,
            expected_amount="5.00",
            expected_currency="USD",
            expected_reference_id=ref_id,
        )
        if not val_ok:
            print(f"\n[ERROR] Completed order validation failed: {val_msg}")
            sys.exit(1)
        capture_resp = order_data
        print(f"  ✓ Existing completed capture reconciled successfully:")
        print(f"    • Order Status:     COMPLETED")
        print(f"    • Capture ID:       {capture_id}")
        print(f"    • Individual State: {ind_status}")
        print(f"    • Amount Verified:  ${act_amt} {act_curr}")
        print(f"    • Reference ID:     {ref_id}")

    elif order_status in ("CREATED", "SAVED", "PAYER_ACTION_REQUIRED"):
        # Manual Buyer Approval in Browser
        print("\n" + "-" * 70)
        print("Step 2: Manual Buyer Approval Required in Browser")
        print("-" * 70)
        print("Please open this link in your browser and log in with your")
        print("PayPal Sandbox Personal (Buyer) account to approve the payment:\n")
        print(f"  🔗  {approval_url}\n")
        print("Notes:")
        print("  - Use your Sandbox Buyer test account credentials from developer.paypal.com")
        print("  - Never share or type buyer credentials into this terminal")
        print("  - Click 'Complete Purchase' / 'Agree & Pay' on the PayPal sandbox page")
        print("-" * 70)

        # Pause for user approval
        user_ack = input("\nHave you approved the payment in your browser? (Press Enter to verify, or 'q' to cancel): ")
        if user_ack.strip().lower() == "q":
            print("\nVerification cancelled by user. No payment was captured.")
            sys.exit(0)

        # Verify Order Approval via get_order() with retry loop
        print(f"\nStep 3: Checking order {order_id} approval status with PayPal API...")
        max_retries = 8
        approved = False

        for attempt in range(1, max_retries + 1):
            try:
                current_order = client.get_order(order_id)
                current_status = current_order.get("status")
                print(f"  [Attempt {attempt}/{max_retries}] Order Status on PayPal: {current_status}")
                if current_status == "APPROVED":
                    approved = True
                    order_status = "APPROVED"
                    break
                elif current_status == "COMPLETED":
                    approved = True
                    order_status = "COMPLETED"
                    order_data = current_order
                    break
            except PayPalClientError as e:
                print(f"  [Attempt {attempt}] Error retrieving order: {sanitize_message(e)}")

            if attempt < max_retries:
                time.sleep(3)

        if not approved:
            print(f"\n[WARNING] Order {order_id} has not reached 'APPROVED' status yet (Current: '{current_status}').")
            print("Payment CANNOT be captured before buyer approval.")
            sys.exit(1)

        if order_status == "COMPLETED":
            val_ok, capture_id, ind_status, act_amt, act_curr, val_msg = validate_capture_response(
                order_data,
                expected_amount="5.00",
                expected_currency="USD",
                expected_reference_id=ref_id,
            )
            if not val_ok:
                print(f"\n[ERROR] Completed order validation failed: {val_msg}")
                sys.exit(1)
            capture_resp = order_data
        else:
            # Explicit Capture Confirmation & Safe Execution
            print("\n" + "-" * 70)
            print("Step 4: Explicit Capture Confirmation")
            print("-" * 70)
            print(f"Order {order_id} is confirmed APPROVED by buyer.")
            confirm = input(f"Capture payment of $5.00 for order {order_id} now? (type 'yes' to proceed): ")
            if confirm.strip().lower() != "yes":
                print("\nCapture cancelled by user. No funds captured.")
                sys.exit(0)

            print(f"\nCapturing payment for order {order_id}...")
            try:
                capture_resp = client.capture_order(order_id)
            except Exception as e:
                print(f"\n[WARNING] Capture request encountered an error: {sanitize_message(e)}")
                reconciled_ok, reconciled_resp, rec_msg = reconcile_in_doubt_capture(
                    client=client,
                    order_id=order_id,
                    expected_amount="5.00",
                    expected_currency="USD",
                    expected_reference_id=ref_id,
                )
                if reconciled_ok and reconciled_resp:
                    capture_resp = reconciled_resp
                    print(f"  ✓ {rec_msg}")
                else:
                    print(f"[ABORT] {rec_msg}")
                    sys.exit(1)

            val_ok, capture_id, ind_status, act_amt, act_curr, val_msg = validate_capture_response(
                capture_resp,
                expected_amount="5.00",
                expected_currency="USD",
                expected_reference_id=ref_id,
            )
            if not val_ok:
                print(f"\n[ERROR] Capture response validation failed: {val_msg}")
                sys.exit(1)

            print(f"  ✓ Capture API call successful & validated!")
            print(f"    • Order Status:     {capture_resp.get('status')} (COMPLETED)")
            print(f"    • Capture ID:       {capture_id}")
            print(f"    • Individual State: {ind_status} (COMPLETED)")
            print(f"    • Amount Verified:  ${act_amt} {act_curr}")
            print(f"    • Reference ID:     {ref_id}")

    elif order_status == "APPROVED":
        # Order was already APPROVED when resumed!
        print("\n" + "-" * 70)
        print("Step 2-3: Buyer Approval Already Confirmed")
        print("-" * 70)
        print(f"Order {order_id} is already in 'APPROVED' status by buyer on PayPal.")

        print("\n" + "-" * 70)
        print("Step 4: Explicit Capture Confirmation")
        print("-" * 70)
        confirm = input(f"Capture payment of $5.00 for order {order_id} now? (type 'yes' to proceed): ")
        if confirm.strip().lower() != "yes":
            print("\nCapture cancelled by user. No funds captured.")
            sys.exit(0)

        print(f"\nCapturing payment for order {order_id}...")
        try:
            capture_resp = client.capture_order(order_id)
        except Exception as e:
            print(f"\n[WARNING] Capture request encountered an error: {sanitize_message(e)}")
            reconciled_ok, reconciled_resp, rec_msg = reconcile_in_doubt_capture(
                client=client,
                order_id=order_id,
                expected_amount="5.00",
                expected_currency="USD",
                expected_reference_id=ref_id,
            )
            if reconciled_ok and reconciled_resp:
                capture_resp = reconciled_resp
                print(f"  ✓ {rec_msg}")
            else:
                print(f"[ABORT] {rec_msg}")
                sys.exit(1)

        val_ok, capture_id, ind_status, act_amt, act_curr, val_msg = validate_capture_response(
            capture_resp,
            expected_amount="5.00",
            expected_currency="USD",
            expected_reference_id=ref_id,
        )
        if not val_ok:
            print(f"\n[ERROR] Capture response validation failed: {val_msg}")
            sys.exit(1)

        print(f"  ✓ Capture API call successful & validated!")
        print(f"    • Order Status:     {capture_resp.get('status')} (COMPLETED)")
        print(f"    • Capture ID:       {capture_id}")
        print(f"    • Individual State: {ind_status} (COMPLETED)")
        print(f"    • Amount Verified:  ${act_amt} {act_curr}")
        print(f"    • Reference ID:     {ref_id}")

    else:
        # Invalid / unexpected status (e.g. VOIDED, EXPIRED)
        print(f"\n[ABORTED] Order {order_id} status '{order_status}' does not permit capture.")
        sys.exit(1)

    # 6. Await and Strictly Correlate Webhook Delivery
    print("\n" + "-" * 70)
    print("Step 5: Verifying Inbound PayPal Signed Webhook")
    print("-" * 70)
    timeout_cfg = int(os.getenv("WEBHOOK_TIMEOUT_S", "90"))
    webhook_event = wait_for_webhook_event_strict(
        order_id=order_id,
        capture_id=capture_id,
        db_path=DEFAULT_DB_PATH,
        timeout_s=timeout_cfg,
    )

    webhook_event_id = None
    if webhook_event:
        webhook_event_id = webhook_event.get("event_id")
        print(f"\n✓ Exact correlated signed webhook received and persisted in SQLite!")
        print(f"  • Event ID:         {webhook_event_id}")
        print(f"  • Event Type:       {webhook_event.get('event_type')}")
        print(f"  • Resource ID:      {webhook_event.get('resource_id')} (matches expected capture_id)")
        print(f"  • TX Reference:     {webhook_event.get('transaction_reference')} (matches expected order_id)")
        print(f"  • Signature Status: {webhook_event.get('status')} (VERIFIED_SUCCESS)")
        print(f"  • Processed At:     {webhook_event.get('processed_at')}")
    else:
        print(f"\n[TIMEOUT] Webhook event not observed in SQLite within {timeout_cfg}s.")
        print("Correlated search required BOTH:")
        print(f"  • resource_id == {capture_id}")
        print(f"  • transaction_reference == {order_id}")

    # 7. Check SQLite Transaction Ledger
    print("\n" + "-" * 70)
    print("Step 6: Verifying Durable Ledger & Hash Chain")
    print("-" * 70)

    tx = find_transaction(order_id, db_path=DEFAULT_DB_PATH)
    if tx:
        print(f"✓ SQLite transactions table record confirmed:")
        print(f"  • Transaction ID:   {tx.get('transaction_id')}")
        print(f"  • Order ID:         {tx.get('order_id')}")
        print(f"  • Capture ID:       {tx.get('capture_id')} (matches expected)")
        print(f"  • Status:           {tx.get('status')} (COMPLETED)")
        print(f"  • Amount:           ${tx.get('amount')} {tx.get('currency')}")
    else:
        print(f"[WARNING] Transaction {order_id} not found in transactions table.")

    # 8. Event-Specific Hash Chain Verification
    hash_chain_target_ok = False
    if webhook_event_id:
        source_auth_confirmed = bool(webhook_event and webhook_event.get("status") == "PROCESSED" and val_ok)
        chain_res = verify_event_in_hash_chain(
            chain_log_path=get_chain_log_path(),
            expected_event_id=webhook_event_id,
            expected_event_type="PAYMENT.CAPTURE.COMPLETED",
            expected_capture_id=capture_id,
            expected_order_id=order_id,
            sqlite_event_record=webhook_event,
            source_authenticated=source_auth_confirmed,
        )
        hash_chain_target_ok = chain_res.target_valid
        print(f"✓ Multi-Dimensional SHA-256 Hash Chain verification:")
        print(f"  • Entire Chain Valid:          {chain_res.chain_valid} ({len(chain_res.chain_errors)} errors)")
        print(f"  • Content Authenticated:       {chain_res.content_authenticated}")
        print(f"  • Database Correlated:         {chain_res.database_correlated}")
        print(f"  • Source Authenticated:        {chain_res.source_authenticated}")
        print(f"  • Ledger Integrity Verified:   {chain_res.ledger_integrity_verified}")
        print(f"  • Legacy Provenance Status:    {chain_res.legacy_provenance_status}")
        print(f"  • V2 Migration Status:         {chain_res.v2_migration_integrity_status}")
        print(f"  • Forensic Verdict:            {chain_res.forensic_verdict}")
        print(f"  • Detail:                      {chain_res.message}")
    else:
        print("• Hash chain target check skipped (webhook event was not received).")

    # 9. Strict 8-Point Checklist Evaluation
    all_passed, verdict, checklist = evaluate_lifecycle_checklist(
        capture_valid=val_ok,
        capture_id=capture_id,
        amount_valid=bool(act_amt == "5.00" and act_curr == "USD"),
        webhook_event=webhook_event,
        tx_record=tx,
        hash_chain_target_valid=hash_chain_target_ok,
    )

    print("\n" + "=" * 70)
    print(f"FINAL AUDIT VERDICT: {verdict}")
    print("=" * 70)
    print("Verification Checklist Breakdown:")
    for check_name, check_result in checklist.items():
        symbol = "✓" if check_result else "✗"
        print(f"  [{symbol}] {check_name}: {'PASSED' if check_result else 'FAILED'}")

    print("\nImportant Scope Clarification:")
    print("  • This test strictly validates: PayPal Sandbox Payment Capture & Signed Webhook Ingestion.")
    print("  • Digital product delivery/download fulfillment is NOT verified by this test.")
    print("=" * 70)

    if not all_passed:
        sys.exit(1)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="ProofLedger PayPal Sandbox Lifecycle Verification")
    parser.add_argument("--order-id", dest="order_id", help="Resume verification with an existing order ID", default=None)
    parser.add_argument("--reference-id", dest="reference_id", help="Expected reference ID for existing order verification", default=None)
    args = parser.parse_args()
    run_lifecycle(existing_order_id=args.order_id, expected_reference_id=args.reference_id)
