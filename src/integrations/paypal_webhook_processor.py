"""
PayPal Webhook Event Processor for ProofLedger.

Handles:
- CHECKOUT.ORDER.APPROVED (does not treat approval as payment capture)
- PAYMENT.CAPTURE.COMPLETED / PENDING / DENIED / REFUNDED / REVERSED
- CUSTOMER.DISPUTE.CREATED / UPDATED / RESOLVED
- Transaction linking with strict verification (no heuristics on name/amount)
- Evidence preparation triggers (without automatic PayPal submission)
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

from src.models.evidence_compiler import EvidenceCompiler, EventLog
from src.storage.db import (
    DEFAULT_CHAIN_LOG_PATH,
    DEFAULT_DB_PATH,
    DatabaseError,
    find_transaction,
    get_chain_log_path,
    get_dispute,
    get_webhook_event,
    record_dispute,
    record_webhook_event,
    set_dispute_evidence_prepared,
    update_dispute_status,
    upsert_transaction,
)
from src.utils.logging_config import setup_logging

logger = setup_logging(name="paypal_webhook_processor")

SUPPORTED_EVENT_TYPES = {
    "CHECKOUT.ORDER.APPROVED",
    "PAYMENT.CAPTURE.COMPLETED",
    "PAYMENT.CAPTURE.PENDING",
    "PAYMENT.CAPTURE.DENIED",
    "PAYMENT.CAPTURE.REFUNDED",
    "PAYMENT.CAPTURE.REVERSED",
    "CUSTOMER.DISPUTE.CREATED",
    "CUSTOMER.DISPUTE.UPDATED",
    "CUSTOMER.DISPUTE.RESOLVED",
}


def compile_dispute_evidence_background(
    dispute_id: str,
    transaction_reference: str,
    reason: str,
    verifier_instance: Any = None,
    db_path: Optional[str] = None,
) -> Optional[str]:
    """
    Background evidence compilation task.
    Does NOT automatically submit evidence to PayPal.
    Human seller review remains mandatory before submission.
    """
    logger.info(f"Background evidence compilation started for dispute {dispute_id} (tx: {transaction_reference})")
    try:
        tx = find_transaction(transaction_reference, db_path=db_path)
        if not tx:
            logger.warning(f"Transaction {transaction_reference} not found during background compilation.")
            return None

        # Build evidence items from verified transaction record
        evidence_items = []
        capture_id = tx.get("capture_id") or tx.get("transaction_id")
        status = tx.get("status")
        amount = tx.get("amount", "0.00")
        currency = tx.get("currency", "USD")

        evidence_items.append({
            "evidence_id": f"paypal_capture_{capture_id}",
            "source_type": "paypal_api",
            "timestamp": tx.get("updated_at") or datetime.now(timezone.utc).isoformat(),
            "content": f"PayPal capture {capture_id} status={status} order={transaction_reference} amount={amount} {currency}.",
        })

        # Add delivery confirmation if metadata contains it
        meta = tx.get("metadata", {})
        if meta and meta.get("delivery_status"):
            evidence_items.append({
                "evidence_id": f"delivery_{transaction_reference}",
                "source_type": "delivery_service",
                "timestamp": meta.get("delivered_at") or tx.get("updated_at"),
                "content": f"Delivery status={meta.get('delivery_status')} order={transaction_reference} file={meta.get('file_name', 'digital_goods')}.",
            })

        compiler = EvidenceCompiler(verifier=verifier_instance, log_path=get_chain_log_path())
        claim = f"Payment for order {transaction_reference} was captured (status={status}) and digital goods were fulfilled."

        report = compiler.compile(
            claim=claim,
            evidence=evidence_items,
            transaction_reference=transaction_reference,
            require_human_review=True,
        )

        compilation_id = report.get("compilation_id")
        set_dispute_evidence_prepared(dispute_id, compilation_id, db_path=db_path)
        logger.info(
            f"Evidence compilation prepared for dispute {dispute_id} "
            f"(compilation_id={compilation_id}, readiness={report.get('evidence_readiness')}). "
            "Evidence is ready for merchant review; automatic submission is strictly suppressed."
        )
        return compilation_id
    except Exception as e:
        logger.error(f"Error in background evidence compilation for dispute {dispute_id}: {e}")
        return None


def process_webhook_event(
    event_data: Dict[str, Any],
    raw_payload: str,
    verifier_instance: Any = None,
    db_path: Optional[str] = None,
) -> Tuple[str, Dict[str, Any]]:
    """
    Process verified PayPal webhook event.

    Returns (status, result_dict):
    - status: "PROCESSED" | "DUPLICATE" | "FLAGGED_MANUAL_RECONCILIATION" | "SKIPPED"
    """
    event_id = event_data.get("id")
    event_type = event_data.get("event_type")
    resource_type = event_data.get("resource_type")
    resource = event_data.get("resource", {})

    if not event_id or not event_type:
        raise ValueError("Missing 'id' or 'event_type' in webhook event.")

    # 1. Persistent Idempotency Check at database level
    existing_event = get_webhook_event(event_id, db_path=db_path)
    if existing_event:
        logger.info(f"Duplicate webhook event delivery: {event_id} ({event_type}) already processed.")
        return "DUPLICATE", {
            "event_id": event_id,
            "event_type": event_type,
            "resource_id": existing_event.get("resource_id"),
            "transaction_reference": existing_event.get("transaction_reference"),
            "detail": "Event already processed. Safely deduplicated.",
        }

    # Record into append-only hash chain
    event_log = EventLog(log_path=get_chain_log_path())
    event_log.append(
        transaction_ref=resource.get("id") or event_id,
        source_type="paypal_webhook",
        source_event_id=event_id,
        event_timestamp=event_data.get("create_time") or datetime.now(timezone.utc).isoformat(),
        payload={"event_type": event_type, "summary": event_data.get("summary")},
    )

    # 2. Event-specific handling
    if event_type == "CHECKOUT.ORDER.APPROVED":
        # CRITICAL: Order approval is NOT payment capture!
        order_id = resource.get("id")
        amount = None
        currency = None
        purchase_units = resource.get("purchase_units", [])
        if purchase_units and isinstance(purchase_units, list):
            amt_obj = purchase_units[0].get("amount", {})
            amount = amt_obj.get("value")
            currency = amt_obj.get("currency_code")

        upsert_transaction(
            transaction_id=order_id,
            order_id=order_id,
            capture_id=None,
            amount=amount,
            currency=currency,
            status="APPROVED",
            event_id=event_id,
            metadata={"approved_at": resource.get("create_time")},
            db_path=db_path,
        )
        summary = f"Order {order_id} approved by buyer. Pending payment capture."
        record_webhook_event(
            event_id=event_id,
            event_type=event_type,
            resource_type=resource_type,
            resource_id=order_id,
            transaction_reference=order_id,
            status="PROCESSED",
            summary=summary,
            raw_payload=raw_payload,
            db_path=db_path,
        )
        return "PROCESSED", {
            "event_id": event_id,
            "event_type": event_type,
            "resource_id": order_id,
            "transaction_reference": order_id,
            "detail": summary,
        }

    elif event_type in (
        "PAYMENT.CAPTURE.COMPLETED",
        "PAYMENT.CAPTURE.PENDING",
        "PAYMENT.CAPTURE.DENIED",
        "PAYMENT.CAPTURE.REFUNDED",
        "PAYMENT.CAPTURE.REVERSED",
    ):
        capture_id = resource.get("id")
        amt_obj = resource.get("amount", {})
        amount = amt_obj.get("value")
        currency = amt_obj.get("currency_code")
        status_suffix = event_type.replace("PAYMENT.CAPTURE.", "")

        # Extract related order ID strictly from supplementary_data or custom_id
        supp = resource.get("supplementary_data", {})
        rel_ids = supp.get("related_ids", {}) if isinstance(supp, dict) else {}
        order_id = rel_ids.get("order_id") or resource.get("custom_id")

        target_tx_id = order_id or capture_id
        upsert_transaction(
            transaction_id=target_tx_id,
            order_id=order_id,
            capture_id=capture_id,
            amount=amount,
            currency=currency,
            status=status_suffix,
            event_id=event_id,
            metadata={"final_capture": resource.get("final_capture")},
            db_path=db_path,
        )
        summary = f"Payment capture {capture_id} status={status_suffix} (linked to order {order_id})."
        record_webhook_event(
            event_id=event_id,
            event_type=event_type,
            resource_type=resource_type,
            resource_id=capture_id,
            transaction_reference=target_tx_id,
            status="PROCESSED",
            summary=summary,
            raw_payload=raw_payload,
            db_path=db_path,
        )
        return "PROCESSED", {
            "event_id": event_id,
            "event_type": event_type,
            "resource_id": capture_id,
            "transaction_reference": target_tx_id,
            "detail": summary,
        }

    elif event_type == "CUSTOMER.DISPUTE.CREATED":
        dispute_id = resource.get("dispute_id") or resource.get("id")
        reason = resource.get("reason", "UNKNOWN")
        status = resource.get("status", "OPEN")
        dispute_amount_obj = resource.get("dispute_amount", {})
        dispute_amount = dispute_amount_obj.get("value")
        currency = dispute_amount_obj.get("currency_code")

        # Transaction Linkage Verification:
        # Search candidate IDs only in disputed_transactions seller_transaction_id / custom
        disputed_txs = resource.get("disputed_transactions", [])
        verified_tx = None
        for dtx in disputed_txs:
            seller_tx_id = dtx.get("seller_transaction_id")
            custom_id = dtx.get("custom")
            buyer_tx_id = dtx.get("buyer_transaction_id")

            for candidate in filter(None, [seller_tx_id, custom_id, buyer_tx_id]):
                matched = find_transaction(candidate, db_path=db_path)
                if matched:
                    verified_tx = matched
                    break
            if verified_tx:
                break

        if verified_tx:
            tx_ref = verified_tx["transaction_id"]
            record_dispute(
                dispute_id=dispute_id,
                transaction_reference=tx_ref,
                reason=reason,
                status=status,
                dispute_amount=dispute_amount,
                currency=currency,
                raw_payload=raw_payload,
                event_id=event_id,
                db_path=db_path,
            )
            summary = f"Dispute {dispute_id} created and linked to verified transaction {tx_ref}."
            record_webhook_event(
                event_id=event_id,
                event_type=event_type,
                resource_type=resource_type,
                resource_id=dispute_id,
                transaction_reference=tx_ref,
                status="PROCESSED",
                summary=summary,
                raw_payload=raw_payload,
                db_path=db_path,
            )
            return "PROCESSED", {
                "event_id": event_id,
                "event_type": event_type,
                "resource_id": dispute_id,
                "transaction_reference": tx_ref,
                "verified_linkage": True,
                "reason": reason,
                "detail": summary,
            }
        else:
            # Unverified transaction linkage — NEVER associate based on amounts/names!
            record_dispute(
                dispute_id=dispute_id,
                transaction_reference=None,
                reason=reason,
                status=status,
                dispute_amount=dispute_amount,
                currency=currency,
                raw_payload=raw_payload,
                event_id=event_id,
                db_path=db_path,
            )
            summary = f"Dispute {dispute_id} transaction linkage could not be reliably verified. Flagged for manual reconciliation."
            record_webhook_event(
                event_id=event_id,
                event_type=event_type,
                resource_type=resource_type,
                resource_id=dispute_id,
                transaction_reference=None,
                status="FLAGGED_MANUAL_RECONCILIATION",
                summary=summary,
                raw_payload=raw_payload,
                db_path=db_path,
            )
            return "FLAGGED_MANUAL_RECONCILIATION", {
                "event_id": event_id,
                "event_type": event_type,
                "resource_id": dispute_id,
                "transaction_reference": None,
                "verified_linkage": False,
                "reason": reason,
                "detail": summary,
            }

    elif event_type == "CUSTOMER.DISPUTE.UPDATED":
        dispute_id = resource.get("dispute_id") or resource.get("id")
        status = resource.get("status", "UPDATED")
        updated_dispute = update_dispute_status(
            dispute_id=dispute_id,
            status=status,
            resolution_outcome=None,
            event_id=event_id,
            raw_payload=raw_payload,
            db_path=db_path,
        )
        tx_ref = updated_dispute.get("transaction_reference") if updated_dispute else None
        summary = f"Dispute {dispute_id} status updated to {status}."
        record_webhook_event(
            event_id=event_id,
            event_type=event_type,
            resource_type=resource_type,
            resource_id=dispute_id,
            transaction_reference=tx_ref,
            status="PROCESSED",
            summary=summary,
            raw_payload=raw_payload,
            db_path=db_path,
        )
        return "PROCESSED", {
            "event_id": event_id,
            "event_type": event_type,
            "resource_id": dispute_id,
            "transaction_reference": tx_ref,
            "detail": summary,
        }

    elif event_type == "CUSTOMER.DISPUTE.RESOLVED":
        dispute_id = resource.get("dispute_id") or resource.get("id")
        outcome_obj = resource.get("dispute_outcome", {})
        outcome = outcome_obj.get("outcome_code") or resource.get("status", "RESOLVED")
        updated_dispute = update_dispute_status(
            dispute_id=dispute_id,
            status="RESOLVED",
            resolution_outcome=outcome,
            event_id=event_id,
            raw_payload=raw_payload,
            db_path=db_path,
        )
        tx_ref = updated_dispute.get("transaction_reference") if updated_dispute else None
        summary = f"Dispute {dispute_id} resolved with outcome {outcome}."
        record_webhook_event(
            event_id=event_id,
            event_type=event_type,
            resource_type=resource_type,
            resource_id=dispute_id,
            transaction_reference=tx_ref,
            status="PROCESSED",
            summary=summary,
            raw_payload=raw_payload,
            db_path=db_path,
        )
        return "PROCESSED", {
            "event_id": event_id,
            "event_type": event_type,
            "resource_id": dispute_id,
            "transaction_reference": tx_ref,
            "detail": summary,
        }

    else:
        # Event type outside core handled set: record as SKIPPED
        resource_id = resource.get("id")
        summary = f"Event type {event_type} acknowledged but not actively tracked."
        record_webhook_event(
            event_id=event_id,
            event_type=event_type,
            resource_type=resource_type,
            resource_id=resource_id,
            transaction_reference=None,
            status="SKIPPED",
            summary=summary,
            raw_payload=raw_payload,
            db_path=db_path,
        )
        return "SKIPPED", {
            "event_id": event_id,
            "event_type": event_type,
            "resource_id": resource_id,
            "transaction_reference": None,
            "detail": summary,
        }

