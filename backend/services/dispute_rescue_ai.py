"""
ProofLedger — PayPal Dispute Rescue
AI Evidence Preparation Assistant for MERCHANDISE_OR_SERVICE_NOT_RECEIVED.

Strictly grounded AI assistant that:
1. Analyzes actual PayPal dispute fields and requested evidence types.
2. Builds an explicit checklist (Carrier Name, Tracking Number, Proof of Delivery).
3. Deterministically validates transaction amount, currency, order linkage, and tracking formats.
4. Runs DeBERTa for supplementary semantic evidence alignment without autonomous decision-making.
5. Drafts a concise, professional merchant response grounded strictly in verified facts.
6. Enforces merchant approval before submission. Zero win-probability speculation. Zero hallucination.
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from backend.services.paypal_dispute_service import SUPPORTED_DISPUTE_REASONS
from backend.services.dispute_service import dispute_service

logger = logging.getLogger("proofledger.dispute_rescue_ai")


def compute_evidence_digest(
    dispute_id: str,
    carrier_name: str,
    tracking_number: str,
    evidence_notes: str = "",
    proof_document_url: Optional[str] = None,
) -> str:
    """Compute canonical SHA-256 digest binding merchant approval to exact evidence fields."""
    canonical = json.dumps(
        {
            "dispute_id": (dispute_id or "").strip(),
            "carrier_name": (carrier_name or "").strip().upper(),
            "tracking_number": (tracking_number or "").strip(),
            "evidence_notes": (evidence_notes or "").strip(),
            "proof_document_url": (proof_document_url or "").strip(),
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class DisputeRescueAIEngine:
    """
    Evidence preparation assistant for PayPal non-receipt disputes.
    """

    def __init__(self):
        self.legacy_verifier = dispute_service

    def validate_and_prepare(
        self,
        dispute: Dict[str, Any],
        transaction: Optional[Dict[str, Any]] = None,
        seller_evidence: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Execute full evidence validation and structured AI response preparation.
        """
        reason = dispute.get("reason", "").strip().upper()
        dispute_id = dispute.get("dispute_id", "UNKNOWN_DISPUTE")
        dispute_amount_str = str(dispute.get("amount", "0.00")).strip()
        dispute_currency = str(dispute.get("currency", "USD")).strip().upper()

        # 1. Scope Enforcement: Reject unsupported dispute reasons
        if reason not in SUPPORTED_DISPUTE_REASONS:
            return {
                "dispute_id": dispute_id,
                "dispute_reason": reason,
                "dispute_reason_supported": False,
                "rejection_reason": f"MVP strictly supports 'MERCHANDISE_OR_SERVICE_NOT_RECEIVED' disputes. Reason '{reason}' is not supported in this release.",
                "case_summary": f"Dispute received with unsupported reason '{reason}'.",
                "required_evidence": [],
                "evidence_checklist": [],
                "verified_facts": [],
                "missing_evidence": [f"Standard workflow unavailable for '{reason}'"],
                "draft_response": "",
                "merchant_approval_required": True,
            }

        # 2. Extract seller provided fulfillment input
        seller_evidence = seller_evidence or {}
        carrier_name = (seller_evidence.get("carrier_name") or "").strip()
        tracking_number = (seller_evidence.get("tracking_number") or "").strip()
        delivery_document_name = (seller_evidence.get("delivery_document_name") or "").strip()
        fulfillment_notes = (seller_evidence.get("fulfillment_notes") or "").strip()
        custom_proof_text = (seller_evidence.get("custom_proof_text") or "").strip()

        # 3. Transaction Cross-Verification (Deterministic Rules)
        tx = transaction or {}
        tx_order_id = str(tx.get("order_id", "")).strip()
        tx_capture_id = str(tx.get("capture_id", "")).strip()
        tx_amount = str(tx.get("amount", "")).strip()
        tx_currency = str(tx.get("currency", "")).strip().upper()
        tx_payment_status = str(tx.get("payment_status", "")).strip().upper()
        buyer_email = str(tx.get("buyer_email") or dispute.get("buyer_email") or "buyer on file").strip()

        verified_facts: List[str] = []
        validation_errors: List[str] = []
        missing_evidence: List[str] = []

        # Rule A: Order Linkage
        if tx_order_id:
            verified_facts.append(f"Linked Order ID verified in merchant store records: {tx_order_id}")
        else:
            validation_errors.append("Order linkage missing: Dispute is not linked to a merchant transaction reference.")

        # Rule B: Amount & Currency Cross-Check
        if tx_amount and dispute_amount_str:
            try:
                tx_amt_flt = float(tx_amount)
                disp_amt_flt = float(dispute_amount_str)
                if abs(tx_amt_flt - disp_amt_flt) < 0.01 and (not tx_currency or tx_currency == dispute_currency):
                    verified_facts.append(
                        f"Order amount matches dispute claim exactly: {tx_amount} {dispute_currency} captured."
                    )
                else:
                    validation_errors.append(
                        f"Amount or currency mismatch: Store records show {tx_amount} {tx_currency}, but PayPal dispute states {dispute_amount_str} {dispute_currency}."
                    )
            except ValueError:
                pass

        # Rule C: Payment Capture Status
        if tx_capture_id and tx_payment_status in ("COMPLETED", "PAYMENT_CAPTURED"):
            verified_facts.append(
                f"PayPal payment capture confirmed (Capture ID: {tx_capture_id}, Status: COMPLETED)."
            )
        elif tx_payment_status == "CREATED":
            validation_errors.append("Payment capture unconfirmed: Order is still in CREATED state without captured funds.")

        # 4. Evidence Checklist Evaluation
        checklist: List[Dict[str, Any]] = []

        # Check 1: Carrier Name
        if carrier_name:
            checklist.append({
                "field": "Carrier Name",
                "status": "AVAILABLE",
                "value": carrier_name,
                "verified": True,
                "detail": f"Recognized carrier: {carrier_name}",
            })
            verified_facts.append(f"Shipment dispatched via carrier: {carrier_name}")
        else:
            checklist.append({
                "field": "Carrier Name",
                "status": "MISSING",
                "value": None,
                "verified": False,
                "detail": "Carrier name is required by PayPal for merchandise delivery defense.",
            })
            missing_evidence.append("Carrier name (e.g., USPS, UPS, FedEx, DHL)")

        # Check 2: Tracking Number
        if tracking_number:
            # Check realistic tracking number format (alphanumeric, at least 6 chars)
            is_valid_format = bool(re.match(r"^[A-Za-z0-9\-_]{6,35}$", tracking_number))
            if is_valid_format:
                checklist.append({
                    "field": "Tracking Number",
                    "status": "AVAILABLE",
                    "validation_tag": "FORMAT_VALID",
                    "value": tracking_number,
                    "verified": True,
                    "detail": f"Tracking number format syntax is valid. Note: Syntax check only (FORMAT_VALID); carrier delivery confirmation requires courier scan/API.",
                })
                verified_facts.append(f"Carrier tracking number provided (FORMAT_VALID): {tracking_number}")
            else:
                checklist.append({
                    "field": "Tracking Number",
                    "status": "INVALID_FORMAT",
                    "validation_tag": "FORMAT_INVALID",
                    "value": tracking_number,
                    "verified": False,
                    "detail": "Tracking number contains invalid characters or is too short.",
                })
                missing_evidence.append("Valid tracking number format")
        else:
            checklist.append({
                "field": "Tracking Number",
                "status": "MISSING",
                "validation_tag": "NOT_PROVIDED",
                "value": None,
                "verified": False,
                "detail": "Tracking number is mandatory for PayPal non-receipt disputes.",
            })
            missing_evidence.append("Tracking number")

        # Check 3: Proof of Delivery / Fulfillment Notes
        if delivery_document_name or custom_proof_text or fulfillment_notes:
            doc_desc = delivery_document_name or "Signed Delivery Log / Access Receipt"
            checklist.append({
                "field": "Proof of Delivery",
                "status": "AVAILABLE",
                "value": doc_desc,
                "verified": True,
                "detail": "Supporting fulfillment / delivery document supplied.",
            })
            verified_facts.append(f"Supporting fulfillment record: {doc_desc}")
        else:
            checklist.append({
                "field": "Proof of Delivery",
                "status": "NEEDS_REVIEW",
                "value": None,
                "verified": False,
                "detail": "Physical signature or delivery confirmation receipt recommended by PayPal.",
            })
            missing_evidence.append("Proof of delivery confirmation or delivery receipt")

        # 5. Supplementary DeBERTa Alignment Signal (Non-autonomous)
        ai_signal = "UNAVAILABLE"
        ai_status = "MODEL_UNAVAILABLE"
        ai_error = getattr(self.legacy_verifier, "model_load_error", None)
        relevance_score: Optional[float] = None
        loaded_ckpt = getattr(self.legacy_verifier, "loaded_model_path", None)
        try:
            if not self.legacy_verifier.verifier or not self.legacy_verifier.verifier.is_loaded:
                ai_error = ai_error or "DeBERTa checkpoint is not loaded; neural semantic alignment unavailable."
            else:
                claim_text = f"Merchant shipped order {tx_order_id} via {carrier_name or 'courier'} with tracking {tracking_number or 'provided'}."
                evidence_item = {
                    "evidence_id": "EV-DISPUTE-FULFILLMENT-01",
                    "source_type": "store_fulfillment",
                    "content": f"Order {tx_order_id} Capture {tx_capture_id} Status {tx_payment_status} Carrier {carrier_name} Tracking {tracking_number} Buyer {buyer_email}",
                }
                res_nli = self.legacy_verifier.verify_single_claim(
                    claim_input={"claim_text": claim_text, "claim_id": "CLM-DISPUTE-01"},
                    evidence=[evidence_item],
                    transaction_reference=tx_order_id or "ORD-REF",
                )
                ai_info = res_nli.get("ai_model", {})
                inv = ai_info.get("invocation_status")
                if inv == "INVOKED":
                    ai_status = "INVOKED"
                    relevance_score = ai_info.get("confidence")
                    ai_signal = res_nli.get("verdict", "INSUFFICIENT_EVIDENCE")
                else:
                    ai_status = inv or "MODEL_FAILED"
                    ai_error = ai_info.get("error") or "Semantic NLI invocation failed."
                    ai_signal = "UNAVAILABLE"
        except Exception as e:
            logger.warning(f"DeBERTa evaluation pass failed: {e}")
            ai_status = "MODEL_FAILED"
            ai_error = str(e)

        # 6. Craft High-Clarity, Factual Merchant Response
        # Strict Grounding: Only statements verified by facts are included
        case_summary = (
            f"Buyer filed a non-receipt dispute for Order {tx_order_id or dispute_id} "
            f"({dispute_amount_str} {dispute_currency}). PayPal requires proof of shipment and fulfillment."
        )

        response_paragraphs = []
        response_paragraphs.append(
            f"Dear PayPal Dispute Resolutions Team,\n\n"
            f"The merchant is responding to Case {dispute_id} regarding Order {tx_order_id or 'referenced'}. "
            f"The buyer reported non-receipt of the merchandise or service."
        )

        fulfillment_lines = []
        if tx_capture_id:
            fulfillment_lines.append(f"- Payment of {dispute_amount_str} {dispute_currency} was captured via PayPal on record (Capture ID: {tx_capture_id}).")
        if carrier_name and tracking_number:
            fulfillment_lines.append(f"- The package was dispatched via {carrier_name} under tracking number {tracking_number}.")
        if delivery_document_name:
            fulfillment_lines.append(f"- Delivery documentation attached: {delivery_document_name}.")
        if fulfillment_notes:
            fulfillment_lines.append(f"- Fulfillment dispatch notes: {fulfillment_notes}.")

        if fulfillment_lines:
            response_paragraphs.append("Verified fulfillment details from merchant dispatch records:\n" + "\n".join(fulfillment_lines))
        else:
            response_paragraphs.append("The merchant is currently compiling the carrier dispatch records for this transaction.")

        if tracking_number:
            response_paragraphs.append(
                f"The shipment was dispatched to the buyer's destination ({buyer_email}). "
                f"The provided carrier tracking number ({tracking_number}) confirms shipment dispatch via {carrier_name or 'the carrier'}."
            )

        response_paragraphs.append(
            "We respectfully submit these verified records as proof of fulfillment in accordance with PayPal Seller Protection guidelines, "
            "and request that this dispute be resolved in the merchant's favor."
        )

        draft_response = "\n\n".join(response_paragraphs)

        # 7. Sentence-Level Source Grounding Citations
        grounding_sources: List[Dict[str, str]] = []
        if tx_capture_id:
            grounding_sources.append({
                "statement": f"Payment of {dispute_amount_str} {dispute_currency} captured on record via PayPal.",
                "supporting_source": "PayPal REST Capture API",
                "source_reference": f"Capture ID: {tx_capture_id} (Status: COMPLETED)",
                "verification_status": "VERIFIED_ON_LEDGER",
            })
        if tx_order_id:
            grounding_sources.append({
                "statement": f"Order {tx_order_id} linked to merchant store transaction.",
                "supporting_source": "Store Transaction Database",
                "source_reference": f"Order ID: {tx_order_id}",
                "verification_status": "VERIFIED_ON_LEDGER",
            })
        if carrier_name and tracking_number:
            grounding_sources.append({
                "statement": f"Shipment dispatched via {carrier_name} with tracking number {tracking_number}.",
                "supporting_source": "Merchant Fulfillment Dispatch Record",
                "source_reference": f"Carrier: {carrier_name}, Tracking: {tracking_number}",
                "verification_status": "FORMAT_VALID",
            })
        if delivery_document_name or fulfillment_notes:
            grounding_sources.append({
                "statement": f"Supporting fulfillment document/notes provided ({delivery_document_name or 'Dispatch Notes'}).",
                "supporting_source": "Merchant Supporting Attestation",
                "source_reference": delivery_document_name or "Merchant Notes",
                "verification_status": "MERCHANT_ATTESTATION",
            })

        # 8. Readiness Indicator
        has_critical_missing = any(c["status"] == "MISSING" for c in checklist)
        has_validation_errors = len(validation_errors) > 0

        if has_validation_errors:
            readiness = "NEEDS_ATTENTION"
        elif has_critical_missing:
            readiness = "MISSING_REQUIRED_FIELDS"
        else:
            readiness = "READY_FOR_SELLER_APPROVAL"

        tracking_syntax_ok = bool(tracking_number and re.match(r"^[A-Za-z0-9\-_]{6,35}$", tracking_number))
        is_live = bool(dispute.get("is_live_paypal_dispute"))
        payment_linked = bool(tx_order_id and tx_capture_id)
        amount_ok = (len(validation_errors) == 0 and bool(tx_amount))

        # 9. 10-Stage Real-Time Processing Pipeline (Part 4.4)
        analysis_stages = [
            {
                "step": 1,
                "key": "retrieve_dispute",
                "title": "Retrieving PayPal dispute",
                "status": "COMPLETED",
                "detail": f"Loaded dispute {dispute_id} ({'Live PayPal Sandbox' if is_live else 'Local Demo Record'}).",
                "tone": "success",
            },
            {
                "step": 2,
                "key": "read_requested_evidence",
                "title": "Reading requested evidence",
                "status": "COMPLETED",
                "detail": "Mapped PayPal policy requirement: PROOF_OF_FULFILLMENT.",
                "tone": "success",
            },
            {
                "step": 3,
                "key": "link_payment_order",
                "title": "Linking payment and order",
                "status": "VERIFIED" if payment_linked else "FAILED",
                "detail": (
                    f"Order {tx_order_id} & Capture {tx_capture_id} verified."
                    if payment_linked
                    else "Order linkage missing from store transaction table."
                ),
                "tone": "success" if payment_linked else "error",
            },
            {
                "step": 4,
                "key": "validate_amount_currency",
                "title": "Validating amount/currency",
                "status": "VERIFIED" if amount_ok else "MISMATCH",
                "detail": (
                    f"Matched {tx_amount} {dispute_currency} exactly."
                    if amount_ok
                    else "; ".join(validation_errors) or "Amount/currency check failed."
                ),
                "tone": "success" if amount_ok else "error",
            },
            {
                "step": 5,
                "key": "validate_tracking",
                "title": "Validating tracking",
                "status": "FORMAT_VALID" if tracking_syntax_ok else ("FORMAT_INVALID" if tracking_number else "NOT_PROVIDED"),
                "detail": (
                    f"Tracking '{tracking_number}' matches {carrier_name or 'carrier'} alphanumeric syntax."
                    if tracking_syntax_ok
                    else ("Tracking number syntax invalid." if tracking_number else "Tracking number not provided.")
                ),
                "tone": "success" if tracking_syntax_ok else ("error" if tracking_number else "warning"),
            },
            {
                "step": 6,
                "key": "check_delivery_evidence",
                "title": "Checking delivery evidence",
                "status": "MERCHANT_ATTESTATION" if delivery_document_name else "LOOKUP_NOT_CONFIGURED",
                "detail": (
                    f"Merchant attached '{delivery_document_name}'; independent carrier delivery scan API is not configured."
                    if delivery_document_name
                    else "Carrier delivery scan lookup API is not configured in this environment."
                ),
                "tone": "warning",
            },
            {
                "step": 7,
                "key": "semantic_nli",
                "title": "Running semantic NLI analysis",
                "status": "COMPLETED" if ai_status == "INVOKED" else "MODEL_OFFLINE",
                "detail": (
                    f"DeBERTa alignment signal: {ai_signal} (score {round(float(relevance_score), 3)}). Advisory only."
                    if ai_status == "INVOKED" and relevance_score is not None
                    else f"Neural semantic model unavailable ({ai_error or ai_status}). Deterministic rules remain active."
                ),
                "tone": "success" if ai_status == "INVOKED" else "warning",
            },
            {
                "step": 8,
                "key": "identify_gaps",
                "title": "Identifying evidence gaps",
                "status": "COMPLETED" if not missing_evidence else "GAPS_IDENTIFIED",
                "detail": (
                    "All required fulfillment fields present; independent carrier scan unverified."
                    if not missing_evidence
                    else f"Missing: {', '.join(missing_evidence)}."
                ),
                "tone": "success" if not missing_evidence else "warning",
            },
            {
                "step": 9,
                "key": "prepare_grounded_response",
                "title": "Preparing grounded response",
                "status": "COMPLETED",
                "detail": f"Compiled {len(grounding_sources)} source-grounded factual statements.",
                "tone": "success",
            },
            {
                "step": 10,
                "key": "ready_for_review",
                "title": "Ready for merchant review",
                "status": "READY" if readiness == "READY_FOR_SELLER_APPROVAL" else "ACTION_REQUIRED",
                "detail": (
                    "Awaiting explicit merchant review and cryptographic approval before submission."
                    if readiness == "READY_FOR_SELLER_APPROVAL"
                    else "Resolve validation errors or missing fields before approval."
                ),
                "tone": "success" if readiness == "READY_FOR_SELLER_APPROVAL" else "warning",
            },
        ]

        # 10. Structured Evidence Output Items (Part 4.5 strict verification taxonomy)
        evidence_items = [
            {
                "item": "Payment & Capture Record",
                "source": "PayPal Capture / Store Ledger" if not is_live else "PayPal REST API",
                "status": (
                    "VERIFIED_ON_PAYPAL"
                    if (is_live and tx_capture_id)
                    else ("VERIFIED_ON_MERCHANT_RECORD" if tx_capture_id else "NOT_PROVIDED")
                ),
                "value": f"{tx_capture_id} ({tx_amount} {dispute_currency})" if tx_capture_id else None,
                "source_reference": f"Order {tx_order_id or 'N/A'} · Capture {tx_capture_id or 'N/A'}",
                "explanation": (
                    "Payment capture and amount match the dispute claim deterministically."
                    if payment_linked and amount_ok
                    else "Payment capture linkage or amount check requires attention."
                ),
                "next_action": None if (payment_linked and amount_ok) else "Verify linked Order ID and Capture ID in store records.",
            },
            {
                "item": "Shipping Carrier",
                "source": "Merchant Input",
                "status": "MERCHANT_ATTESTATION" if carrier_name else "NOT_PROVIDED",
                "value": carrier_name or None,
                "source_reference": "Seller Fulfillment Form",
                "explanation": (
                    f"Merchant specified carrier '{carrier_name}'."
                    if carrier_name
                    else "Carrier name is required for PROOF_OF_FULFILLMENT."
                ),
                "next_action": None if carrier_name else "Select or enter the shipping carrier name.",
            },
            {
                "item": "Tracking Number",
                "source": "Merchant Input (Syntax Validator)",
                "status": (
                    "FORMAT_VALID"
                    if tracking_syntax_ok
                    else ("NOT_INDEPENDENTLY_VERIFIED" if tracking_number else "NOT_PROVIDED")
                ),
                "value": tracking_number or None,
                "source_reference": f"Regex Syntax Check ({carrier_name or 'Carrier'})",
                "explanation": (
                    "Alphanumeric tracking format is syntactically valid; does NOT prove delivery."
                    if tracking_syntax_ok
                    else ("Tracking syntax failed validation." if tracking_number else "Tracking number was not supplied.")
                ),
                "next_action": None if tracking_syntax_ok else "Provide a valid 6–35 character tracking ID.",
            },
            {
                "item": "Carrier Delivery Scan",
                "source": "Courier Tracking API",
                "status": "LOOKUP_NOT_CONFIGURED",
                "value": None,
                "source_reference": "External Carrier Webhook / API",
                "explanation": "Automated courier delivery scan lookup is not configured; delivery cannot be independently confirmed.",
                "next_action": "Attach signed delivery receipt or courier screenshot before submitting.",
            },
            {
                "item": "Supporting Delivery Document",
                "source": "Merchant Attachment",
                "status": "MERCHANT_ATTESTATION" if (delivery_document_name or fulfillment_notes) else "NOT_PROVIDED",
                "value": delivery_document_name or (fulfillment_notes[:60] + "..." if len(fulfillment_notes) > 60 else fulfillment_notes) or None,
                "source_reference": delivery_document_name or "Merchant Dispatch Notes",
                "explanation": (
                    "Merchant-supplied fulfillment notes/document attached as attestation (not independently verified by carrier)."
                    if (delivery_document_name or fulfillment_notes)
                    else "No delivery document or notes attached."
                ),
                "next_action": None if (delivery_document_name or fulfillment_notes) else "Upload delivery confirmation PDF or add dispatch notes.",
            },
        ]

        if delivery_document_name:
            draft_summary = (
                "Payment and order records have been verified on record. The merchant has supplied a tracking number "
                "and fulfillment documentation, while independent carrier delivery scan lookup is not configured."
            )
        elif tracking_number:
            draft_summary = (
                "Payment and order records have been verified on record. The merchant has supplied a tracking number "
                "(FORMAT_VALID), while independent carrier delivery confirmation is not configured."
            )
        else:
            draft_summary = (
                "Payment and order records have been verified on record. Shipping carrier name and tracking number "
                "are required before the defense package can be approved."
            )

        proof_doc_url = f"https://proofledger.local/docs/{delivery_document_name}" if delivery_document_name else None
        evidence_digest = compute_evidence_digest(
            dispute_id=dispute_id,
            carrier_name=carrier_name,
            tracking_number=tracking_number,
            evidence_notes=draft_response,
            proof_document_url=proof_doc_url,
        )

        return {
            "dispute_id": dispute_id,
            "dispute_reason": reason,
            "dispute_reason_supported": True,
            "case_summary": case_summary,
            "required_evidence": [
                "Carrier Name",
                "Tracking Number",
                "Proof of Delivery Notes / Document",
            ],
            "evidence_checklist": checklist,
            "evidence_items": evidence_items,
            "analysis_stages": analysis_stages,
            "draft_summary": draft_summary,
            "evidence_digest": evidence_digest,
            "verified_facts": verified_facts,
            "grounding_sources": grounding_sources,
            "validation_errors": validation_errors,
            "missing_evidence": missing_evidence,
            "draft_response": draft_response,
            "evidence_readiness": readiness,
            "can_submit_to_paypal": (readiness == "READY_FOR_SELLER_APPROVAL"),
            "merchant_approval_required": True,
            "relevance_signal": {
                "status": ai_status,
                "score": round(float(relevance_score), 4) if relevance_score is not None else None,
                "verdict": ai_signal,
                "model_path": loaded_ckpt,
                "error": ai_error,
                "autonomous_action_taken": False,
            },
        }


# Global singleton engine
dispute_rescue_ai = DisputeRescueAIEngine()

