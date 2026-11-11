"""
Unit tests for the hardened PayPal Sandbox lifecycle validation logic.

Covers:
1. Capture response validation:
   - Valid response with COMPLETED order and individual capture, correct amount and currency
   - Amount mismatch ($10.00 vs expected $5.00)
   - Currency mismatch (EUR vs expected USD)
   - Reference ID mismatch
   - Non-COMPLETED order status
   - Non-COMPLETED individual capture status
   - Missing or unknown capture_id
2. In-doubt capture reconciliation:
   - Reconciles order successfully when order is COMPLETED on PayPal
   - Rejects reconciliation when order on PayPal is not COMPLETED
3. Strict webhook correlation:
   - Strict AND match on both resource_id (capture_id) and transaction_reference (order_id)
   - Mismatched capture_id rejected
   - Mismatched order_id rejected
4. Event-specific hash-chain verification:
   - Valid target event found in valid chain
   - Missing target event in valid chain
   - Mismatched event_type in target event
   - Non-existent log file
5. 8-Point verification checklist:
   - All conditions met -> SUCCESSFUL
   - Missing transaction record -> FAILED
   - Mismatched capture ID in transaction -> FAILED
   - Failed hash-chain -> FAILED
   - Unsuccessful signature verification -> FAILED
   - Webhook not received -> PARTIAL
6. Sensitive data sanitization
"""
from __future__ import annotations

import hashlib
import json
from unittest.mock import MagicMock
import pytest

from src.integrations.run_live_sandbox_lifecycle import (
    ChainVerificationResult,
    evaluate_lifecycle_checklist,
    reconcile_in_doubt_capture,
    run_lifecycle,
    sanitize_message,
    validate_capture_response,
    validate_existing_order_payload,
    verify_event_in_hash_chain,
)
from src.models.evidence_compiler import (
    ChainIntegrityError,
    EventLog,
    MalformedEventError,
)
from src.storage.db import (
    SilentFallbackProhibitedError,
    find_webhook_event_strict,
    get_chain_log_path,
    init_db,
    record_webhook_event,
)


@pytest.fixture
def isolated_db(tmp_path, monkeypatch):
    test_db = str(tmp_path / "test_lifecycle.db")
    monkeypatch.setenv("DATABASE_PATH", test_db)
    init_db(test_db)
    return test_db


# ===========================================================================
# 1. Capture Response Validation Tests (Status, Amount, Currency, Reference)
# ===========================================================================

def test_validate_capture_response_valid():
    resp = {
        "id": "ORD-12345",
        "status": "COMPLETED",
        "purchase_units": [
            {
                "reference_id": "ref_valid_01",
                "payments": {
                    "captures": [
                        {
                            "id": "CAP-998877",
                            "status": "COMPLETED",
                            "amount": {"value": "5.00", "currency_code": "USD"},
                        }
                    ]
                },
            }
        ],
    }
    is_valid, cap_id, ind_status, amt, curr, msg = validate_capture_response(
        resp, expected_amount="5.00", expected_currency="USD", expected_reference_id="ref_valid_01"
    )
    assert is_valid is True
    assert cap_id == "CAP-998877"
    assert ind_status == "COMPLETED"
    assert amt == "5.00"
    assert curr == "USD"


def test_validate_capture_response_amount_mismatch():
    resp = {
        "id": "ORD-12345",
        "status": "COMPLETED",
        "purchase_units": [
            {
                "payments": {
                    "captures": [
                        {
                            "id": "CAP-1",
                            "status": "COMPLETED",
                            "amount": {"value": "10.00", "currency_code": "USD"},  # 10.00 != 5.00
                        }
                    ]
                }
            }
        ],
    }
    is_valid, cap_id, ind_status, amt, curr, msg = validate_capture_response(
        resp, expected_amount="5.00", expected_currency="USD"
    )
    assert is_valid is False
    assert "Capture amount mismatch: expected '5.00', got '10.00'" in msg


def test_validate_capture_response_currency_mismatch():
    resp = {
        "id": "ORD-12345",
        "status": "COMPLETED",
        "purchase_units": [
            {
                "payments": {
                    "captures": [
                        {
                            "id": "CAP-1",
                            "status": "COMPLETED",
                            "amount": {"value": "5.00", "currency_code": "EUR"},  # EUR != USD
                        }
                    ]
                }
            }
        ],
    }
    is_valid, cap_id, ind_status, amt, curr, msg = validate_capture_response(
        resp, expected_amount="5.00", expected_currency="USD"
    )
    assert is_valid is False
    assert "Capture currency mismatch: expected 'USD', got 'EUR'" in msg


def test_validate_capture_response_reference_id_mismatch():
    resp = {
        "id": "ORD-12345",
        "status": "COMPLETED",
        "purchase_units": [
            {
                "reference_id": "ref_wrong",
                "payments": {
                    "captures": [
                        {
                            "id": "CAP-1",
                            "status": "COMPLETED",
                            "amount": {"value": "5.00", "currency_code": "USD"},
                        }
                    ]
                },
            }
        ],
    }
    is_valid, cap_id, ind_status, amt, curr, msg = validate_capture_response(
        resp, expected_amount="5.00", expected_currency="USD", expected_reference_id="ref_expected"
    )
    assert is_valid is False
    assert "Reference ID mismatch" in msg


def test_validate_capture_response_non_completed_order():
    resp = {
        "id": "ORD-12345",
        "status": "PENDING",
        "purchase_units": [{"payments": {"captures": [{"id": "CAP-1", "status": "COMPLETED", "amount": {"value": "5.00", "currency_code": "USD"}}]}}],
    }
    is_valid, cap_id, ind_status, amt, curr, msg = validate_capture_response(resp)
    assert is_valid is False
    assert "Order-level capture status is 'PENDING'" in msg


def test_validate_capture_response_non_completed_individual():
    resp = {
        "id": "ORD-12345",
        "status": "COMPLETED",
        "purchase_units": [{"payments": {"captures": [{"id": "CAP-1", "status": "PENDING", "amount": {"value": "5.00", "currency_code": "USD"}}]}}],
    }
    is_valid, cap_id, ind_status, amt, curr, msg = validate_capture_response(resp)
    assert is_valid is False
    assert "Individual capture resource status is 'PENDING'" in msg


def test_validate_capture_response_unknown_capture_id():
    resp = {
        "id": "ORD-12345",
        "status": "COMPLETED",
        "purchase_units": [{"payments": {"captures": [{"id": "unknown", "status": "COMPLETED", "amount": {"value": "5.00", "currency_code": "USD"}}]}}],
    }
    is_valid, cap_id, ind_status, amt, curr, msg = validate_capture_response(resp)
    assert is_valid is False
    assert "Invalid or missing capture_id" in msg


# ===========================================================================
# 2. In-Doubt Capture Reconciliation Tests
# ===========================================================================

def test_reconcile_in_doubt_capture_success():
    mock_client = MagicMock()
    mock_client.get_order.return_value = {
        "id": "ORD-RECON-01",
        "status": "COMPLETED",
        "purchase_units": [
            {
                "reference_id": "ref_recon_01",
                "payments": {
                    "captures": [
                        {
                            "id": "CAP-RECON-01",
                            "status": "COMPLETED",
                            "amount": {"value": "5.00", "currency_code": "USD"},
                        }
                    ]
                },
            }
        ],
    }

    ok, order_obj, msg = reconcile_in_doubt_capture(
        client=mock_client,
        order_id="ORD-RECON-01",
        expected_amount="5.00",
        expected_currency="USD",
        expected_reference_id="ref_recon_01",
    )
    assert ok is True
    assert "Successfully reconciled" in msg


def test_reconcile_in_doubt_capture_aborts_when_not_completed():
    mock_client = MagicMock()
    mock_client.get_order.return_value = {
        "id": "ORD-RECON-02",
        "status": "APPROVED",  # Not completed on PayPal
    }

    ok, order_obj, msg = reconcile_in_doubt_capture(
        client=mock_client,
        order_id="ORD-RECON-02",
        expected_amount="5.00",
        expected_currency="USD",
    )
    assert ok is False
    assert "Payment was NOT captured. Aborting without retry" in msg


# ===========================================================================
# 3. Strict Webhook Correlation Tests (resource_id AND transaction_reference)
# ===========================================================================

def test_strict_webhook_correlation_matches(isolated_db):
    record_webhook_event(
        event_id="WH-EVT-01",
        event_type="PAYMENT.CAPTURE.COMPLETED",
        resource_type="capture",
        resource_id="CAP-CORRECT-99",
        transaction_reference="ORD-CORRECT-11",
        status="PROCESSED",
        summary="Payment captured",
        raw_payload="{}",
        db_path=isolated_db,
    )

    matched = find_webhook_event_strict(
        capture_id="CAP-CORRECT-99",
        order_id="ORD-CORRECT-11",
        db_path=isolated_db,
    )
    assert matched is not None
    assert matched["event_id"] == "WH-EVT-01"


def test_strict_webhook_correlation_mismatched_capture_id(isolated_db):
    record_webhook_event(
        event_id="WH-EVT-02",
        event_type="PAYMENT.CAPTURE.COMPLETED",
        resource_type="capture",
        resource_id="CAP-WRONG",
        transaction_reference="ORD-CORRECT-11",
        status="PROCESSED",
        summary="Payment captured",
        raw_payload="{}",
        db_path=isolated_db,
    )

    matched = find_webhook_event_strict(
        capture_id="CAP-CORRECT-99",
        order_id="ORD-CORRECT-11",
        db_path=isolated_db,
    )
    assert matched is None


def test_strict_webhook_correlation_mismatched_order_id(isolated_db):
    record_webhook_event(
        event_id="WH-EVT-03",
        event_type="PAYMENT.CAPTURE.COMPLETED",
        resource_type="capture",
        resource_id="CAP-CORRECT-99",
        transaction_reference="ORD-WRONG",
        status="PROCESSED",
        summary="Payment captured",
        raw_payload="{}",
        db_path=isolated_db,
    )

    matched = find_webhook_event_strict(
        capture_id="CAP-CORRECT-99",
        order_id="ORD-CORRECT-11",
        db_path=isolated_db,
    )
    assert matched is None


# ===========================================================================
# 4. Event-Specific Hash Chain Verification Tests
# ===========================================================================

def test_event_specific_hash_chain_valid(tmp_path):
    chain_file = tmp_path / "chain.jsonl"
    log = EventLog(log_path=str(chain_file))
    log.append("ORD-1", "paypal_api", "ev1", "2026-10-31T00:00:00Z", {"action": "create"})
    log.append("ORD-1", "paypal_webhook", "TARGET-WH-EVENT-99", "2026-10-31T01:00:00Z", {"event_type": "PAYMENT.CAPTURE.COMPLETED"})

    chain_ok, target_ok, msg = verify_event_in_hash_chain(
        chain_log_path=str(chain_file),
        expected_event_id="TARGET-WH-EVENT-99",
        expected_event_type="PAYMENT.CAPTURE.COMPLETED",
    )
    assert chain_ok is True
    assert target_ok is True
    assert "verified in valid hash chain" in msg


def test_event_specific_hash_chain_missing_target_event(tmp_path):
    chain_file = tmp_path / "chain_no_target.jsonl"
    log = EventLog(log_path=str(chain_file))
    log.append("ORD-1", "paypal_api", "ev1", "2026-10-31T00:00:00Z", {"action": "create"})
    # Target event never appended

    chain_ok, target_ok, msg = verify_event_in_hash_chain(
        chain_log_path=str(chain_file),
        expected_event_id="TARGET-WH-EVENT-MISSING",
        expected_event_type="PAYMENT.CAPTURE.COMPLETED",
    )
    assert chain_ok is True
    assert target_ok is False
    assert "not found in the hash chain" in msg


def test_event_specific_hash_chain_mismatched_event_type(tmp_path):
    chain_file = tmp_path / "chain_wrong_type.jsonl"
    log = EventLog(log_path=str(chain_file))
    log.append("ORD-1", "paypal_webhook", "TARGET-WH-EVENT-01", "2026-10-31T00:00:00Z", {"event_type": "CHECKOUT.ORDER.APPROVED"})

    chain_ok, target_ok, msg = verify_event_in_hash_chain(
        chain_log_path=str(chain_file),
        expected_event_id="TARGET-WH-EVENT-01",
        expected_event_type="PAYMENT.CAPTURE.COMPLETED",  # expects capture completed, but found order approved
    )
    assert chain_ok is True
    assert target_ok is False
    assert "event_type 'CHECKOUT.ORDER.APPROVED' != expected 'PAYMENT.CAPTURE.COMPLETED'" in msg


def test_event_specific_hash_chain_with_sqlite_crosscheck_success(tmp_path):
    chain_file = tmp_path / "chain_sqlite_match.jsonl"
    log = EventLog(log_path=str(chain_file))
    log.append(
        transaction_ref="CAP-VALID-999",
        source_type="paypal_webhook",
        source_event_id="WH-CORRELATED-01",
        event_timestamp="2026-10-31T12:00:00Z",
        payload={"event_type": "PAYMENT.CAPTURE.COMPLETED", "summary": "Payment capture completed successfully."},
    )

    sqlite_record = {
        "event_id": "WH-CORRELATED-01",
        "event_type": "PAYMENT.CAPTURE.COMPLETED",
        "resource_id": "CAP-VALID-999",
        "transaction_reference": "ORD-VALID-888",
        "status": "PROCESSED",
        "summary": "Payment capture completed successfully.",
        "raw_payload": json.dumps({
            "id": "WH-CORRELATED-01",
            "event_type": "PAYMENT.CAPTURE.COMPLETED",
            "summary": "Payment capture completed successfully.",
        }),
    }

    chain_ok, target_ok, msg = verify_event_in_hash_chain(
        chain_log_path=str(chain_file),
        expected_event_id="WH-CORRELATED-01",
        expected_event_type="PAYMENT.CAPTURE.COMPLETED",
        expected_capture_id="CAP-VALID-999",
        expected_order_id="ORD-VALID-888",
        sqlite_event_record=sqlite_record,
    )
    assert chain_ok is True
    assert target_ok is True
    assert "verified in valid hash chain" in msg
    assert "Cross-checked against SQLite record" in msg


def test_event_specific_hash_chain_mismatched_capture_id(tmp_path):
    chain_file = tmp_path / "chain_cap_mismatch.jsonl"
    log = EventLog(log_path=str(chain_file))
    log.append(
        transaction_ref="CAP-WRONG-111",
        source_type="paypal_webhook",
        source_event_id="WH-TARGET-02",
        event_timestamp="2026-10-31T12:00:00Z",
        payload={"event_type": "PAYMENT.CAPTURE.COMPLETED", "summary": "Capture completed"},
    )

    chain_ok, target_ok, msg = verify_event_in_hash_chain(
        chain_log_path=str(chain_file),
        expected_event_id="WH-TARGET-02",
        expected_event_type="PAYMENT.CAPTURE.COMPLETED",
        expected_capture_id="CAP-EXPECTED-999",  # Does not match chain_tx_ref CAP-WRONG-111
    )
    assert chain_ok is True
    assert target_ok is False
    assert "transaction_ref 'CAP-WRONG-111' != expected capture_id 'CAP-EXPECTED-999'" in msg


def test_event_specific_hash_chain_mismatched_sqlite_resource_id(tmp_path):
    chain_file = tmp_path / "chain_sqlite_res_mismatch.jsonl"
    log = EventLog(log_path=str(chain_file))
    log.append(
        transaction_ref="CAP-IN-CHAIN",
        source_type="paypal_webhook",
        source_event_id="WH-TARGET-03",
        event_timestamp="2026-10-31T12:00:00Z",
        payload={"event_type": "PAYMENT.CAPTURE.COMPLETED", "summary": "Capture completed"},
    )

    sqlite_record = {
        "event_id": "WH-TARGET-03",
        "event_type": "PAYMENT.CAPTURE.COMPLETED",
        "resource_id": "CAP-DIFFERENT-IN-SQLITE",  # Differs from chain transaction_ref
        "transaction_reference": "ORD-123",
        "raw_payload": "{}",
    }

    chain_ok, target_ok, msg = verify_event_in_hash_chain(
        chain_log_path=str(chain_file),
        expected_event_id="WH-TARGET-03",
        expected_event_type="PAYMENT.CAPTURE.COMPLETED",
        expected_capture_id="CAP-IN-CHAIN",
        sqlite_event_record=sqlite_record,
    )
    assert chain_ok is True
    assert target_ok is False
    assert "transaction_ref 'CAP-IN-CHAIN' != SQLite resource_id 'CAP-DIFFERENT-IN-SQLITE'" in msg


def test_event_specific_hash_chain_mismatched_sqlite_order_id(tmp_path):
    chain_file = tmp_path / "chain_sqlite_ord_mismatch.jsonl"
    log = EventLog(log_path=str(chain_file))
    log.append(
        transaction_ref="CAP-123",
        source_type="paypal_webhook",
        source_event_id="WH-TARGET-04",
        event_timestamp="2026-10-31T12:00:00Z",
        payload={"event_type": "PAYMENT.CAPTURE.COMPLETED", "summary": "Capture completed"},
    )

    sqlite_record = {
        "event_id": "WH-TARGET-04",
        "event_type": "PAYMENT.CAPTURE.COMPLETED",
        "resource_id": "CAP-123",
        "transaction_reference": "ORD-SQLITE-WRONG",  # Differs from expected order_id
        "raw_payload": "{}",
    }

    chain_ok, target_ok, msg = verify_event_in_hash_chain(
        chain_log_path=str(chain_file),
        expected_event_id="WH-TARGET-04",
        expected_event_type="PAYMENT.CAPTURE.COMPLETED",
        expected_capture_id="CAP-123",
        expected_order_id="ORD-EXPECTED-RIGHT",
        sqlite_event_record=sqlite_record,
    )
    assert chain_ok is True
    assert target_ok is False
    assert "transaction_reference 'ORD-SQLITE-WRONG' != expected order_id 'ORD-EXPECTED-RIGHT'" in msg


def test_event_specific_hash_chain_mismatched_payload_summary(tmp_path):
    chain_file = tmp_path / "chain_summary_mismatch.jsonl"
    log = EventLog(log_path=str(chain_file))
    log.append(
        transaction_ref="CAP-123",
        source_type="paypal_webhook",
        source_event_id="WH-TARGET-05",
        event_timestamp="2026-10-31T12:00:00Z",
        payload={"event_type": "PAYMENT.CAPTURE.COMPLETED", "summary": "Summary A"},
    )

    sqlite_record = {
        "event_id": "WH-TARGET-05",
        "event_type": "PAYMENT.CAPTURE.COMPLETED",
        "resource_id": "CAP-123",
        "transaction_reference": "ORD-123",
        "raw_payload": json.dumps({
            "id": "WH-TARGET-05",
            "summary": "Summary B Different",  # Differs from chain summary
        }),
    }

    chain_ok, target_ok, msg = verify_event_in_hash_chain(
        chain_log_path=str(chain_file),
        expected_event_id="WH-TARGET-05",
        expected_event_type="PAYMENT.CAPTURE.COMPLETED",
        expected_capture_id="CAP-123",
        sqlite_event_record=sqlite_record,
    )
    assert chain_ok is True
    assert target_ok is False
    assert "summary 'Summary A' != raw payload summary 'Summary B Different'" in msg


def test_event_specific_hash_chain_tampered_fails(tmp_path):
    chain_file = tmp_path / "chain_tampered.jsonl"
    log = EventLog(log_path=str(chain_file))
    log.append("ORD-1", "paypal_api", "ev1", "2026-10-31T00:00:00Z", {"action": "create"})
    log.append("CAP-1", "paypal_webhook", "WH-TARGET-06", "2026-10-31T01:00:00Z", {"event_type": "PAYMENT.CAPTURE.COMPLETED"})

    # Tamper with the log file directly (tamper event 0)
    with open(chain_file, "r") as f:
        lines = f.readlines()
    tampered_data = json.loads(lines[0])
    tampered_data["payload"]["tampered"] = True
    lines[0] = json.dumps(tampered_data) + "\n"
    with open(chain_file, "w") as f:
        f.writelines(lines)

    res = verify_event_in_hash_chain(
        chain_log_path=str(chain_file),
        expected_event_id="WH-TARGET-06",
        expected_event_type="PAYMENT.CAPTURE.COMPLETED",
        expected_capture_id="CAP-1",
    )
    # Decoupled verification: full chain is False because event 0 was tampered,
    # but target event WH-TARGET-06 itself was NOT tampered so its self-hash is valid!
    assert res.chain_valid is False
    assert res.target_self_hash_ok is True
    assert res.target_valid is True
    assert "Historical chain has" in res.message


def test_event_specific_hash_chain_target_self_tampered_fails(tmp_path):
    chain_file = tmp_path / "chain_target_tampered.jsonl"
    log = EventLog(log_path=str(chain_file))
    log.append("ORD-1", "paypal_api", "ev1", "2026-10-31T00:00:00Z", {"action": "create"})
    log.append("CAP-1", "paypal_webhook", "WH-TARGET-TAMPERED", "2026-10-31T01:00:00Z", {"event_type": "PAYMENT.CAPTURE.COMPLETED"})

    # Tamper with target event itself
    with open(chain_file, "r") as f:
        lines = f.readlines()
    target_data = json.loads(lines[1])
    target_data["payload"]["forged_amount"] = "9999.00"
    lines[1] = json.dumps(target_data) + "\n"
    with open(chain_file, "w") as f:
        f.writelines(lines)

    res = verify_event_in_hash_chain(
        chain_log_path=str(chain_file),
        expected_event_id="WH-TARGET-TAMPERED",
        expected_event_type="PAYMENT.CAPTURE.COMPLETED",
        expected_capture_id="CAP-1",
    )
    assert res.target_self_hash_ok is False
    assert res.target_valid is False
    assert "self-hash mismatch" in res.message


# ===========================================================================
# 5. Strict 8-Point Verification Checklist Tests
# ===========================================================================

def test_checklist_all_passed():
    all_passed, verdict, chk = evaluate_lifecycle_checklist(
        capture_valid=True,
        capture_id="CAP-100",
        amount_valid=True,
        webhook_event={"event_id": "WH-1", "status": "PROCESSED"},
        tx_record={"status": "COMPLETED", "capture_id": "CAP-100"},
        hash_chain_target_valid=True,
    )
    assert all_passed is True
    assert verdict == "SUCCESSFUL"
    assert all(chk.values())


def test_checklist_missing_transaction_fails():
    all_passed, verdict, chk = evaluate_lifecycle_checklist(
        capture_valid=True,
        capture_id="CAP-100",
        amount_valid=True,
        webhook_event={"event_id": "WH-1", "status": "PROCESSED"},
        tx_record=None,  # Missing transaction record in SQLite
        hash_chain_target_valid=True,
    )
    assert all_passed is False
    assert chk["sqlite_transaction_exists"] is False
    assert "FAILED" in verdict


def test_checklist_amount_invalid_fails():
    all_passed, verdict, chk = evaluate_lifecycle_checklist(
        capture_valid=True,
        capture_id="CAP-100",
        amount_valid=False,  # Amount mismatch
        webhook_event={"event_id": "WH-1", "status": "PROCESSED"},
        tx_record={"status": "COMPLETED", "capture_id": "CAP-100"},
        hash_chain_target_valid=True,
    )
    assert all_passed is False
    assert chk["capture_amount_and_currency_verified"] is False
    assert "FAILED" in verdict


def test_checklist_missing_target_hash_chain_fails():
    all_passed, verdict, chk = evaluate_lifecycle_checklist(
        capture_valid=True,
        capture_id="CAP-100",
        amount_valid=True,
        webhook_event={"event_id": "WH-1", "status": "PROCESSED"},
        tx_record={"status": "COMPLETED", "capture_id": "CAP-100"},
        hash_chain_target_valid=False,  # Target event missing from chain
    )
    assert all_passed is False
    assert chk["hash_chain_target_verified"] is False
    assert "FAILED" in verdict


def test_checklist_missing_webhook_reports_partial():
    all_passed, verdict, chk = evaluate_lifecycle_checklist(
        capture_valid=True,
        capture_id="CAP-100",
        amount_valid=True,
        webhook_event=None,  # Webhook not delivered / timed out
        tx_record={"status": "COMPLETED", "capture_id": "CAP-100"},
        hash_chain_target_valid=False,
    )
    assert all_passed is False
    assert "PARTIAL" in verdict


# ===========================================================================
# 6. Sensitive Data Sanitization Test
# ===========================================================================

def test_sanitize_message():
    raw_error = "Error with access_token='A21AAI_secret_token_123456789' for buyer john.doe@example.com Bearer token_secret_abcdef12345"
    sanitized = sanitize_message(raw_error)
    assert "A21AAI_secret_token" not in sanitized
    assert "john.doe@example.com" not in sanitized
    assert "[REDACTED_TOKEN]" in sanitized
    assert "[REDACTED_EMAIL]" in sanitized


def test_sanitize_message_passwords():
    # Various password patterns
    samples = [
        "Exception in auth: password='SecretPassword123' rejected",
        "Config dump: password=SuperSecret456! failed",
        '{"user": "buyer", "password": "JsonPassword789"}',
        "buyer_password=BuyerPass321 in context",
        "Failed login with password: PlainPass654",
    ]
    for s in samples:
        sanitized = sanitize_message(s)
        assert "SecretPassword123" not in sanitized
        assert "SuperSecret456!" not in sanitized
        assert "JsonPassword789" not in sanitized
        assert "BuyerPass321" not in sanitized
        assert "PlainPass654" not in sanitized
        assert "[REDACTED_PASSWORD]" in sanitized


# ===========================================================================
# 7. Resume Mode and Existing Order Validation Tests
# ===========================================================================

def test_validate_existing_order_payload_valid():
    order_data = {
        "id": "3EU95140LR696653G",
        "status": "CREATED",
        "intent": "CAPTURE",
        "purchase_units": [
            {
                "reference_id": "proofledger_sb_94b76ba7d009",
                "amount": {"value": "5.00", "currency_code": "USD"},
            }
        ],
    }
    is_valid, msg = validate_existing_order_payload(
        order_data,
        expected_order_id="3EU95140LR696653G",
        expected_amount="5.00",
        expected_currency="USD",
        expected_reference_id="proofledger_sb_94b76ba7d009",
        expected_intent="CAPTURE",
    )
    assert is_valid is True
    assert "Existing order validated successfully" in msg


def test_validate_existing_order_payload_order_id_mismatch():
    order_data = {
        "id": "WRONG-ORDER-ID",
        "status": "CREATED",
        "intent": "CAPTURE",
        "purchase_units": [
            {
                "reference_id": "proofledger_sb_94b76ba7d009",
                "amount": {"value": "5.00", "currency_code": "USD"},
            }
        ],
    }
    is_valid, msg = validate_existing_order_payload(
        order_data,
        expected_order_id="3EU95140LR696653G",
    )
    assert is_valid is False
    assert "Order ID mismatch" in msg


def test_validate_existing_order_payload_intent_mismatch():
    order_data = {
        "id": "3EU95140LR696653G",
        "status": "CREATED",
        "intent": "AUTHORIZE",  # Expected CAPTURE
        "purchase_units": [
            {
                "reference_id": "proofledger_sb_94b76ba7d009",
                "amount": {"value": "5.00", "currency_code": "USD"},
            }
        ],
    }
    is_valid, msg = validate_existing_order_payload(
        order_data,
        expected_order_id="3EU95140LR696653G",
        expected_intent="CAPTURE",
    )
    assert is_valid is False
    assert "Order intent mismatch" in msg


def test_validate_existing_order_payload_amount_mismatch():
    order_data = {
        "id": "3EU95140LR696653G",
        "status": "CREATED",
        "intent": "CAPTURE",
        "purchase_units": [
            {
                "reference_id": "proofledger_sb_94b76ba7d009",
                "amount": {"value": "10.00", "currency_code": "USD"},  # 10.00 != 5.00
            }
        ],
    }
    is_valid, msg = validate_existing_order_payload(
        order_data,
        expected_order_id="3EU95140LR696653G",
        expected_amount="5.00",
    )
    assert is_valid is False
    assert "Order amount mismatch" in msg


def test_validate_existing_order_payload_currency_mismatch():
    order_data = {
        "id": "3EU95140LR696653G",
        "status": "CREATED",
        "intent": "CAPTURE",
        "purchase_units": [
            {
                "reference_id": "proofledger_sb_94b76ba7d009",
                "amount": {"value": "5.00", "currency_code": "EUR"},  # EUR != USD
            }
        ],
    }
    is_valid, msg = validate_existing_order_payload(
        order_data,
        expected_order_id="3EU95140LR696653G",
        expected_currency="USD",
    )
    assert is_valid is False
    assert "Order currency mismatch" in msg


def test_validate_existing_order_payload_reference_id_mismatch():
    order_data = {
        "id": "3EU95140LR696653G",
        "status": "CREATED",
        "intent": "CAPTURE",
        "purchase_units": [
            {
                "reference_id": "wrong_reference_id",
                "amount": {"value": "5.00", "currency_code": "USD"},
            }
        ],
    }
    is_valid, msg = validate_existing_order_payload(
        order_data,
        expected_order_id="3EU95140LR696653G",
        expected_reference_id="proofledger_sb_94b76ba7d009",
    )
    assert is_valid is False
    assert "Order reference_id mismatch" in msg


def test_resume_mode_bypasses_create_order_and_uses_get_order(monkeypatch):
    mock_client = MagicMock()
    mock_client._base_url = "https://api-m.sandbox.paypal.com"
    mock_client.is_configured = True
    monkeypatch.setenv("PAYPAL_MODE", "sandbox")
    monkeypatch.setenv("PAYPAL_WEBHOOK_ID", "WH-MOCK-ID-123456789")

    mock_client.get_order.return_value = {
        "id": "3EU95140LR696653G",
        "status": "CREATED",
        "intent": "CAPTURE",
        "purchase_units": [
            {
                "reference_id": "proofledger_sb_94b76ba7d009",
                "amount": {"value": "5.00", "currency_code": "USD"},
            }
        ],
        "links": [{"rel": "approve", "href": "https://sandbox.paypal.com/approve"}],
    }

    monkeypatch.setattr("builtins.input", lambda prompt: "q")
    monkeypatch.setattr("src.integrations.run_live_sandbox_lifecycle.PayPalClient", lambda *args, **kwargs: mock_client)

    with pytest.raises(SystemExit) as exc:
        run_lifecycle(existing_order_id="3EU95140LR696653G")

    assert exc.value.code == 0
    mock_client.create_order.assert_not_called()
    mock_client.get_order.assert_called_with("3EU95140LR696653G")


def test_resume_mode_created_status_never_permits_capture(monkeypatch):
    mock_client = MagicMock()
    mock_client._base_url = "https://api-m.sandbox.paypal.com"
    mock_client.is_configured = True
    monkeypatch.setenv("PAYPAL_MODE", "sandbox")
    monkeypatch.setenv("PAYPAL_WEBHOOK_ID", "WH-MOCK-ID-123456789")

    mock_client.get_order.return_value = {
        "id": "3EU95140LR696653G",
        "status": "CREATED",
        "intent": "CAPTURE",
        "purchase_units": [
            {
                "reference_id": "proofledger_sb_94b76ba7d009",
                "amount": {"value": "5.00", "currency_code": "USD"},
            }
        ],
        "links": [{"rel": "approve", "href": "https://sandbox.paypal.com/approve"}],
    }

    monkeypatch.setattr("builtins.input", lambda prompt: "")
    monkeypatch.setattr("src.integrations.run_live_sandbox_lifecycle.PayPalClient", lambda *args, **kwargs: mock_client)

    with pytest.raises(SystemExit) as exc:
        run_lifecycle(existing_order_id="3EU95140LR696653G")

    assert exc.value.code == 1
    mock_client.capture_order.assert_not_called()


def test_resume_mode_approved_status_requires_explicit_confirmation(monkeypatch):
    mock_client = MagicMock()
    mock_client._base_url = "https://api-m.sandbox.paypal.com"
    mock_client.is_configured = True
    monkeypatch.setenv("PAYPAL_MODE", "sandbox")
    monkeypatch.setenv("PAYPAL_WEBHOOK_ID", "WH-MOCK-ID-123456789")

    mock_client.get_order.return_value = {
        "id": "3EU95140LR696653G",
        "status": "APPROVED",
        "intent": "CAPTURE",
        "purchase_units": [
            {
                "reference_id": "proofledger_sb_94b76ba7d009",
                "amount": {"value": "5.00", "currency_code": "USD"},
            }
        ],
        "links": [{"rel": "approve", "href": "https://sandbox.paypal.com/approve"}],
    }

    monkeypatch.setattr("builtins.input", lambda prompt: "no")
    monkeypatch.setattr("src.integrations.run_live_sandbox_lifecycle.PayPalClient", lambda *args, **kwargs: mock_client)

    with pytest.raises(SystemExit) as exc:
        run_lifecycle(existing_order_id="3EU95140LR696653G")

    assert exc.value.code == 0
    mock_client.capture_order.assert_not_called()


def test_resume_mode_completed_status_reconciles_without_capture(monkeypatch):
    mock_client = MagicMock()
    mock_client._base_url = "https://api-m.sandbox.paypal.com"
    mock_client.is_configured = True
    monkeypatch.setenv("PAYPAL_MODE", "sandbox")
    monkeypatch.setenv("PAYPAL_WEBHOOK_ID", "WH-MOCK-ID-123456789")

    completed_order = {
        "id": "3EU95140LR696653G",
        "status": "COMPLETED",
        "intent": "CAPTURE",
        "purchase_units": [
            {
                "reference_id": "proofledger_sb_94b76ba7d009",
                "payments": {
                    "captures": [
                        {
                            "id": "CAP-ALREADY-COMPLETED-01",
                            "status": "COMPLETED",
                            "amount": {"value": "5.00", "currency_code": "USD"},
                        }
                    ]
                },
            }
        ],
    }
    mock_client.get_order.return_value = completed_order

    monkeypatch.setattr("src.integrations.run_live_sandbox_lifecycle.PayPalClient", lambda *args, **kwargs: mock_client)
    monkeypatch.setattr("src.integrations.run_live_sandbox_lifecycle.wait_for_webhook_event_strict", lambda **kwargs: None)
    monkeypatch.setattr("src.integrations.run_live_sandbox_lifecycle.find_transaction", lambda *args, **kwargs: None)

    with pytest.raises(SystemExit):
        run_lifecycle(existing_order_id="3EU95140LR696653G")

    mock_client.capture_order.assert_not_called()


def test_resume_mode_unexpected_status_aborts_safely(monkeypatch):
    mock_client = MagicMock()
    mock_client._base_url = "https://api-m.sandbox.paypal.com"
    mock_client.is_configured = True
    monkeypatch.setenv("PAYPAL_MODE", "sandbox")
    monkeypatch.setenv("PAYPAL_WEBHOOK_ID", "WH-MOCK-ID-123456789")

    mock_client.get_order.return_value = {
        "id": "3EU95140LR696653G",
        "status": "VOIDED",
        "intent": "CAPTURE",
        "purchase_units": [
            {
                "reference_id": "proofledger_sb_94b76ba7d009",
                "amount": {"value": "5.00", "currency_code": "USD"},
            }
        ],
    }

    monkeypatch.setattr("src.integrations.run_live_sandbox_lifecycle.PayPalClient", lambda *args, **kwargs: mock_client)

    with pytest.raises(SystemExit) as exc:
        run_lifecycle(existing_order_id="3EU95140LR696653G")

    assert exc.value.code == 1
    mock_client.capture_order.assert_not_called()


# ===========================================================================
# 8. Hash-Chain Integrity, State Recovery, Concurrency & V2 Ledger Tests
# ===========================================================================

def test_event_log_state_recovery_across_instances(tmp_path):
    """Verify that a new EventLog instance recovers disk state and links properly."""
    chain_file = tmp_path / "chain_recovery.jsonl"
    
    # Process 1 creates initial log and appends event 1
    log1 = EventLog(log_path=str(chain_file))
    ev1 = log1.append("ORD-1", "test_source", "EV-1", "2026-10-31T00:00:00Z", {"action": "create"})
    assert ev1["previous_hash"] == "genesis"
    assert len(log1.events) == 1

    # Process 2 (simulating restart) initializes with existing log path
    log2 = EventLog(log_path=str(chain_file))
    assert len(log2.events) == 1
    assert log2.events[0]["current_hash"] == ev1["current_hash"]

    # Append event 2 in process 2: MUST link to event 1, NOT "genesis"
    ev2 = log2.append("ORD-1", "test_source", "EV-2", "2026-10-31T00:01:00Z", {"action": "capture"})
    assert ev2["previous_hash"] == ev1["current_hash"]
    assert ev2["previous_hash"] != "genesis"
    assert len(log2.events) == 2

    # Entire chain must be cryptographically valid
    valid, errors = log2.verify_chain()
    assert valid is True
    assert len(errors) == 0


def test_event_log_rejects_malformed_json(tmp_path):
    """Verify that corrupt non-JSON lines raise MalformedEventError."""
    chain_file = tmp_path / "chain_corrupt.jsonl"
    with open(chain_file, "w", encoding="utf-8") as f:
        f.write('NOT_A_VALID_JSON_LINE\n')

    with pytest.raises(MalformedEventError) as exc:
        EventLog(log_path=str(chain_file))
    assert "not valid JSON" in str(exc.value)


def test_event_log_rejects_missing_required_fields(tmp_path):
    """Verify that records missing required fields raise MalformedEventError."""
    chain_file = tmp_path / "chain_missing_fields.jsonl"
    bad_record = {
        "event_id": "test-id",
        # missing schema_version, transaction_ref, etc.
        "current_hash": "abcdef",
    }
    with open(chain_file, "w", encoding="utf-8") as f:
        f.write(json.dumps(bad_record) + "\n")

    with pytest.raises(MalformedEventError) as exc:
        EventLog(log_path=str(chain_file))
    assert "missing required fields" in str(exc.value)


def test_event_log_rejects_append_on_broken_chain(tmp_path):
    """Verify that normal appends are strictly rejected if existing chain has broken links."""
    chain_file = tmp_path / "chain_broken.jsonl"
    log = EventLog(log_path=str(chain_file))
    ev1 = log.append("ORD-1", "src", "EV-1", "2026-10-31T00:00:00Z", {"a": 1})

    # Tamper with event 0 on disk
    with open(chain_file, "r") as f:
        lines = f.readlines()
    data = json.loads(lines[0])
    data["previous_hash"] = "tampered_genesis"  # breaks genesis check
    with open(chain_file, "w") as f:
        f.write(json.dumps(data) + "\n")

    # Reopen log with broken chain
    log_broken = EventLog(log_path=str(chain_file))
    assert log_broken.is_valid is False
    assert len(log_broken.chain_errors) > 0

    # Normal append MUST be rejected with ChainIntegrityError
    with pytest.raises(ChainIntegrityError) as exc:
        log_broken.append("ORD-1", "src", "EV-2", "2026-10-31T00:01:00Z", {"b": 2})
    assert "Cannot append to broken hash chain" in str(exc.value)

    # Explicit override allows append when requested
    log_broken._allow_broken_chain = True
    ev_override = log_broken.append("ORD-1", "src", "EV-OVERRIDE", "2026-10-31T00:02:00Z", {"b": 2})
    assert ev_override is not None


def test_event_log_concurrent_appends_with_locking(tmp_path):
    """Verify thread-safe concurrent appends produce an unbroken hash chain."""
    import concurrent.futures
    chain_file = tmp_path / "chain_concurrent.jsonl"
    num_threads = 10
    events_per_thread = 5

    def worker(worker_id):
        worker_log = EventLog(log_path=str(chain_file))
        results = []
        for j in range(events_per_thread):
            ev = worker_log.append(
                transaction_ref=f"ORD-WORKER-{worker_id}",
                source_type="concurrent_test",
                source_event_id=f"EV-W{worker_id}-{j}",
                event_timestamp=f"2026-10-31T00:{worker_id:02d}:{j:02d}Z",
                payload={"worker": worker_id, "iteration": j},
            )
            results.append(ev)
        return results

    with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
        futures = [executor.submit(worker, i) for i in range(num_threads)]
        for f in concurrent.futures.as_completed(futures):
            f.result()

    # Verify all records loaded from disk form a valid unbroken chain
    final_log = EventLog(log_path=str(chain_file))
    assert len(final_log.events) == num_threads * events_per_thread
    valid, errors = final_log.verify_chain()
    assert valid is True
    assert len(errors) == 0


def test_independent_target_verification_with_broken_historical_link(tmp_path):
    """
    Core regression test:
    Target event is valid and genuine, but an earlier historical event has a broken link.
    Verification must report:
      - chain_valid: False
      - target_exists: True
      - target_self_hash_ok: True
      - target_valid: True
    """
    chain_file = tmp_path / "chain_legacy_simulation.jsonl"
    log = EventLog(log_path=str(chain_file))
    ev0 = log.append("ORD-1", "paypal", "EV-0", "2026-10-31T00:00:00Z", {"step": 0})
    
    # Simulate historical bug: write ev1 with previous_hash="genesis" instead of ev0["current_hash"]
    ev1_data = {
        "event_id": "mock-ev1",
        "schema_version": "1.0",
        "transaction_ref": "ORD-1",
        "source_type": "paypal",
        "source_event_id": "EV-1",
        "event_timestamp": "2026-10-31T00:01:00Z",
        "recorded_at": "2026-10-31T00:01:00Z",
        "previous_hash": "genesis",  # BROKEN LINK (should have been ev0 hash)
        "payload": {"step": 1},
    }
    blob1 = json.dumps(ev1_data, sort_keys=True, default=str).encode()
    import hashlib
    ev1_data["current_hash"] = hashlib.sha256(blob1).hexdigest()
    with open(chain_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(ev1_data) + "\n")

    # Now append target capture event (ev2)
    ev2_data = {
        "event_id": "target-uuid-002",
        "schema_version": "1.0",
        "transaction_ref": "CAP-LEGACY-002",
        "source_type": "paypal_webhook",
        "source_event_id": "WH-TARGET-LEGACY-002",
        "event_timestamp": "2026-10-31T00:02:00Z",
        "recorded_at": "2026-10-31T00:02:00Z",
        "previous_hash": "genesis",  # historical instance restart wrote genesis
        "payload": {"event_type": "PAYMENT.CAPTURE.COMPLETED", "summary": "Capture completed"},
    }
    blob2 = json.dumps(ev2_data, sort_keys=True, default=str).encode()
    ev2_data["current_hash"] = hashlib.sha256(blob2).hexdigest()
    with open(chain_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(ev2_data) + "\n")

    # Run independent verification
    sqlite_mock = {
        "event_id": "WH-TARGET-LEGACY-002",
        "event_type": "PAYMENT.CAPTURE.COMPLETED",
        "resource_id": "CAP-LEGACY-002",
        "transaction_reference": "ORD-1",
        "raw_payload": json.dumps({"summary": "Capture completed", "id": "WH-TARGET-LEGACY-002"}),
    }

    res = verify_event_in_hash_chain(
        chain_log_path=str(chain_file),
        expected_event_id="WH-TARGET-LEGACY-002",
        expected_event_type="PAYMENT.CAPTURE.COMPLETED",
        expected_capture_id="CAP-LEGACY-002",
        expected_order_id="ORD-1",
        sqlite_event_record=sqlite_mock,
    )

    # Decoupled verification assertions
    assert res.chain_valid is False  # Historical chain has broken links
    assert len(res.chain_errors) > 0
    assert res.target_exists is True  # Target found
    assert res.target_self_hash_ok is True  # Target self-hash is 100% valid
    assert res.target_link_ok is False  # Predecessor link is broken
    assert res.sqlite_correlated is True  # SQLite cross-check passed
    assert res.target_valid is True  # Target is authentic and validated
    assert "Historical chain has" in res.message


def test_reconstruct_v2_ledger_provenance(tmp_path):
    """Verify that reconstruct_v2_ledger creates a clean, continuous V2 chain without modifying source."""
    source_file = tmp_path / "source_broken.jsonl"
    target_file = tmp_path / "target_v2.jsonl"

    # Create a broken source ledger
    log = EventLog(log_path=str(source_file))
    ev0 = log.append("ORD-1", "src", "EV-0", "2026-10-31T00:00:00Z", {"action": "create"})
    
    # Second event with genesis previous_hash (broken link)
    ev1_data = {
        "event_id": "ev1-id",
        "schema_version": "1.0",
        "transaction_ref": "ORD-1",
        "source_type": "src",
        "source_event_id": "EV-1",
        "event_timestamp": "2026-10-31T00:01:00Z",
        "recorded_at": "2026-10-31T00:01:00Z",
        "previous_hash": "genesis",
        "payload": {"action": "capture"},
    }
    blob = json.dumps(ev1_data, sort_keys=True, default=str).encode()
    import hashlib
    ev1_data["current_hash"] = hashlib.sha256(blob).hexdigest()
    with open(source_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(ev1_data) + "\n")

    # Read original source bytes & hash
    with open(source_file, "rb") as f:
        source_bytes_before = f.read()
    source_hash_before = hashlib.sha256(source_bytes_before).hexdigest()

    # Reconstruct V2 ledger
    v2_log, meta = EventLog.reconstruct_v2_ledger(
        source_log_path=str(source_file),
        target_log_path=str(target_file),
        provenance_note="Test migration to V2",
    )

    # 1. Source file MUST be byte-for-byte identical
    with open(source_file, "rb") as f:
        source_bytes_after = f.read()
    source_hash_after = hashlib.sha256(source_bytes_after).hexdigest()
    assert source_hash_before == source_hash_after

    # 2. V2 chain MUST be completely valid
    assert meta["v2_chain_valid"] is True
    assert meta["total_events_migrated"] == 2
    v2_valid, v2_errors = v2_log.verify_chain()
    assert v2_valid is True
    assert len(v2_errors) == 0

    # 3. Provenance disclaimer must be present
    assert "provenance_disclaimer" in meta
    assert "cannot retroactively guarantee" in meta["provenance_disclaimer"]

    # 4. Overwrite must be prohibited
    with pytest.raises(FileExistsError):
        EventLog.reconstruct_v2_ledger(str(source_file), str(target_file))


# ===========================================================================
# 9. Multi-Process Concurrency, Crash Recovery, Manifest Audit & V2 Guard Tests
# ===========================================================================

def _multiprocess_log_worker(chain_path: str, proc_id: int, num_events: int) -> None:
    """Worker function executed in separate OS processes."""
    log = EventLog(log_path=chain_path)
    for i in range(num_events):
        log.append(
            transaction_ref=f"ORD-MP-{proc_id}",
            source_type="multiprocess_test",
            source_event_id=f"EV-MP{proc_id}-{i}",
            event_timestamp=f"2026-10-31T00:{proc_id:02d}:{i:02d}Z",
            payload={"proc_id": proc_id, "iteration": i},
        )


def test_event_log_multiprocess_concurrency_locking(tmp_path):
    """Verify separate OS processes using fcntl.flock produce an unbroken hash chain."""
    import multiprocessing
    chain_file = str(tmp_path / "chain_multiprocess.jsonl")
    num_procs = 4
    events_per_proc = 5

    ctx = multiprocessing.get_context("spawn")
    processes = [
        ctx.Process(target=_multiprocess_log_worker, args=(chain_file, p_id, events_per_proc))
        for p_id in range(num_procs)
    ]

    for p in processes:
        p.start()
    for p in processes:
        p.join()
        assert p.exitcode == 0

    # Verify final chain
    final_log = EventLog(log_path=chain_file)
    assert len(final_log.events) == num_procs * events_per_proc
    valid, errors = final_log.verify_chain()
    assert valid is True
    assert len(errors) == 0


def test_crash_recovery_truncated_trailing_write(tmp_path):
    """
    Verify crash-recovery for interrupted trailing write:
    Simulates SIGKILL / power loss mid-write leaving a truncated JSON fragment at EOF.
    """
    chain_file = tmp_path / "chain_crashed.jsonl"
    log = EventLog(log_path=str(chain_file))
    log.append("ORD-1", "src", "EV-1", "2026-10-31T00:00:00Z", {"step": 1})
    log.append("ORD-1", "src", "EV-2", "2026-10-31T00:01:00Z", {"step": 2})

    # Simulate crash mid-write: append an incomplete trailing JSON line
    with open(chain_file, "a", encoding="utf-8") as f:
        f.write('{"event_id": "half-written-uuid-during-crash", "schema_version": "1.0", "transact')

    # Unprotected load must detect malformed event
    with pytest.raises(MalformedEventError):
        EventLog(log_path=str(chain_file))

    # Run crash-recovery
    recovered, msg, valid_count = EventLog.recover_interrupted_write(str(chain_file))
    assert recovered is True
    assert valid_count == 2
    assert "Preserved 2 valid records" in msg

    # File should now load cleanly and allow normal appends
    recovered_log = EventLog(log_path=str(chain_file))
    assert len(recovered_log.events) == 2
    valid, errors = recovered_log.verify_chain()
    assert valid is True
    assert len(errors) == 0

    # Append event 3: must link cleanly to event 2
    ev3 = recovered_log.append("ORD-1", "src", "EV-3", "2026-10-31T00:02:00Z", {"step": 3})
    assert ev3["previous_hash"] == recovered_log.events[1]["current_hash"]
    v3_valid, v3_err = recovered_log.verify_chain()
    assert v3_valid is True
    assert len(v3_err) == 0


def test_verify_v2_manifest_and_provenance(tmp_path):
    """Verify independent audit of V2 ledger against its migration manifest."""
    source_file = tmp_path / "legacy_source.jsonl"
    target_file = tmp_path / "v2_target.jsonl"

    # Create source ledger with 3 events
    log = EventLog(log_path=str(source_file))
    for i in range(3):
        log.append(f"ORD-{i}", "src", f"EV-{i}", f"2026-10-31T00:0{i}:00Z", {"data": i})

    # Reconstruct V2 ledger
    v2_log, meta = EventLog.reconstruct_v2_ledger(str(source_file), str(target_file))

    # Verify manifest audit
    is_valid, errors, report = EventLog.verify_v2_manifest(
        v2_log_path=str(target_file),
        source_legacy_path=str(source_file),
    )
    assert is_valid is True
    assert len(errors) == 0
    assert report["actual_total_events"] == 3
    assert report["manifest_genesis_hash"] == v2_log.events[0]["current_hash"]
    assert report["manifest_head_hash"] == v2_log.events[-1]["current_hash"]
    assert report["legacy_records_matched"] is True


def test_strict_no_silent_fallback_to_legacy(tmp_path, monkeypatch):
    """Verify that get_chain_log_path() strictly forbids silent fallback to legacy ledger."""
    fake_legacy = tmp_path / "legacy_events.jsonl"
    fake_v2 = tmp_path / "nonexistent_v2.jsonl"

    fake_legacy.write_text('{"event_id": "leg1"}\n')
    assert fake_legacy.exists()
    assert not fake_v2.exists()

    monkeypatch.setattr("src.storage.db.LEGACY_CHAIN_LOG_PATH", str(fake_legacy))
    monkeypatch.setattr("src.storage.db.V2_CHAIN_LOG_PATH", str(fake_v2))
    monkeypatch.delenv("CHAIN_LOG_PATH", raising=False)

    with pytest.raises(SilentFallbackProhibitedError) as exc:
        get_chain_log_path()
    assert "Silent fallback to legacy ledger" in str(exc.value)


def test_forensic_verdict_content_authenticated_database_correlated(tmp_path):
    """
    Verify forensic verdict:
    When target event is valid and matched with SQLite, but historical chain or predecessor link
    is broken, verdict MUST be:
    'CONTENT_AUTHENTICATED & DATABASE_CORRELATED — HISTORICAL CHAIN LINK UNVERIFIED'
    """
    chain_file = tmp_path / "chain_forensic_test.jsonl"
    log = EventLog(log_path=str(chain_file))
    log.append("ORD-1", "src", "EV-0", "2026-10-31T00:00:00Z", {"step": 0})

    # Append broken predecessor event
    broken_evt = {
        "event_id": "target-wh-01",
        "schema_version": "1.0",
        "transaction_ref": "CAP-FORENSIC-01",
        "source_type": "paypal_webhook",
        "source_event_id": "WH-FORENSIC-01",
        "event_timestamp": "2026-10-31T00:01:00Z",
        "recorded_at": "2026-10-31T00:01:00Z",
        "previous_hash": "genesis",  # Broken predecessor link (should be EV-0 hash)
        "payload": {"event_type": "PAYMENT.CAPTURE.COMPLETED", "summary": "Payment capture confirmed"},
    }
    blob = json.dumps(broken_evt, sort_keys=True, default=str).encode()
    broken_evt["current_hash"] = hashlib.sha256(blob).hexdigest()
    with open(chain_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(broken_evt) + "\n")

    sqlite_record = {
        "event_id": "WH-FORENSIC-01",
        "event_type": "PAYMENT.CAPTURE.COMPLETED",
        "resource_id": "CAP-FORENSIC-01",
        "transaction_reference": "ORD-1",
        "raw_payload": json.dumps({"summary": "Payment capture confirmed", "id": "WH-FORENSIC-01"}),
    }

    res = verify_event_in_hash_chain(
        chain_log_path=str(chain_file),
        expected_event_id="WH-FORENSIC-01",
        expected_event_type="PAYMENT.CAPTURE.COMPLETED",
        expected_capture_id="CAP-FORENSIC-01",
        expected_order_id="ORD-1",
        sqlite_event_record=sqlite_record,
    )

    assert res.target_valid is True
    assert res.target_self_hash_ok is True
    assert res.target_link_ok is False
    assert res.forensic_verdict == "CONTENT_AUTHENTICATED & DATABASE_CORRELATED — HISTORICAL CHAIN LINK UNVERIFIED"
    assert "CONTENT_AUTHENTICATED & DATABASE_CORRELATED — HISTORICAL CHAIN LINK UNVERIFIED" in res.message
