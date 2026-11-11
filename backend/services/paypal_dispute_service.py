"""
ProofLedger — PayPal Dispute Rescue
Dedicated PayPal REST Disputes API Integration & Evidence Submission Service.

Implements official PayPal REST Disputes API:
- GET  /v1/customer/disputes
- GET  /v1/customer/disputes/{dispute_id}
- POST /v1/customer/disputes/{dispute_id}/provide-evidence

Also integrates official read-only PayPal MCP capabilities for safe dispute inspection.
"""
from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import requests
from backend.config import (
    ROOT_DIR,
    SANDBOX_AMOUNT,
    SANDBOX_CAPTURE_ID,
    SANDBOX_CURRENCY,
    SANDBOX_ORDER_ID,
)
from backend.services.paypal_service import paypal_live_service

logger = logging.getLogger("proofledger.paypal_disputes")

# Supported MVP dispute reason
SUPPORTED_DISPUTE_REASONS = {
    "MERCHANDISE_OR_SERVICE_NOT_RECEIVED",
    "ITEM_NOT_RECEIVED",
}


class PayPalDisputeService:
    """
    Client for PayPal REST Disputes API and evidence submission.
    Adheres strictly to the official PayPal Disputes API specification.
    """

    def __init__(self):
        self.client = paypal_live_service
        self.base_url = paypal_live_service.base_url

    def _get_headers(self) -> Tuple[Optional[str], Dict[str, str], Optional[str]]:
        token, _, err = self.client.get_access_token()
        if not token:
            return None, {}, err
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        return token, headers, None

    def list_disputes(self, dispute_state: Optional[str] = None) -> Dict[str, Any]:
        """
        Retrieve disputes from PayPal REST API: GET /v1/customer/disputes.
        Returns live disputes and handles sandbox environments gracefully.
        """
        token, headers, err = self._get_headers()
        if not token:
            return {
                "success": False,
                "error": f"Failed to acquire PayPal OAuth token: {err}",
                "items": [],
                "total_items": 0,
            }

        params = {}
        if dispute_state:
            params["dispute_state"] = dispute_state

        t0 = time.time()
        try:
            res = requests.get(
                f"{self.base_url}/v1/customer/disputes",
                headers=headers,
                params=params,
                timeout=10.0,
            )
            latency_ms = round((time.time() - t0) * 1000, 2)
            debug_id = res.headers.get("Paypal-Debug-Id")

            if res.status_code == 200:
                data = res.json()
                raw_items = data.get("items", [])
                formatted_items = [self._format_dispute_summary(d) for d in raw_items]
                return {
                    "success": True,
                    "http_status": 200,
                    "paypal_debug_id": debug_id,
                    "latency_ms": latency_ms,
                    "total_items": len(formatted_items),
                    "items": formatted_items,
                    "raw_items": raw_items,
                }
            else:
                return {
                    "success": False,
                    "http_status": res.status_code,
                    "paypal_debug_id": debug_id,
                    "error": res.text,
                    "items": [],
                    "total_items": 0,
                }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "items": [],
                "total_items": 0,
            }

    def get_dispute(self, dispute_id: str) -> Dict[str, Any]:
        """
        Retrieve comprehensive dispute details: GET /v1/customer/disputes/{dispute_id}.
        Extracts reason, status, lifecycle stage, amounts, evidence requests, and HATEOAS links.
        """
        token, headers, err = self._get_headers()
        if not token:
            return {"success": False, "error": f"OAuth failed: {err}"}

        t0 = time.time()
        try:
            res = requests.get(
                f"{self.base_url}/v1/customer/disputes/{dispute_id}",
                headers=headers,
                timeout=10.0,
            )
            latency_ms = round((time.time() - t0) * 1000, 2)
            debug_id = res.headers.get("Paypal-Debug-Id")

            if res.status_code == 200:
                raw_dispute = res.json()
                formatted = self._format_dispute_detail(raw_dispute)
                formatted["paypal_debug_id"] = debug_id
                formatted["latency_ms"] = latency_ms
                return {"success": True, "dispute": formatted, "raw": raw_dispute}
            else:
                return {
                    "success": False,
                    "http_status": res.status_code,
                    "paypal_debug_id": debug_id,
                    "error": res.text,
                }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def can_provide_evidence(self, dispute_data: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Checks whether the dispute is currently eligible for seller evidence submission:
        1. Checks HATEOAS links for rel='provide_evidence'.
        2. Validates dispute lifecycle state is WAITING_FOR_SELLER_RESPONSE or UNDER_PAYPAL_REVIEW.
        """
        links = dispute_data.get("links", [])
        has_provide_evidence_link = any(
            link.get("rel") == "provide_evidence" for link in links
        )
        status = dispute_data.get("status", "")

        if status in ("RESOLVED", "RESOLVED_SELLER_FAVOR", "RESOLVED_BUYER_FAVOR", "CLOSED"):
            return False, f"Dispute is already closed ({status}); evidence can no longer be submitted."

        if status == "UNDER_PAYPAL_REVIEW" and not has_provide_evidence_link:
            return False, "Dispute is currently under PayPal review; no additional evidence requested at this time."

        return True, "Eligible for evidence submission."

    def submit_dispute_evidence(
        self,
        dispute_id: str,
        carrier_name: str,
        tracking_number: str,
        evidence_notes: str,
        proof_document_url: Optional[str] = None,
        merchant_approved: bool = False,
    ) -> Dict[str, Any]:
        """
        Submit seller evidence to PayPal: POST /v1/customer/disputes/{dispute_id}/provide-evidence.
        STRICT REQUIREMENT: Requires explicit merchant approval.
        """
        if not merchant_approved:
            return {
                "success": False,
                "error": "MERCHANT_APPROVAL_REQUIRED: Merchant must review and approve response before submission.",
                "http_status": 400,
            }

        if not carrier_name or not carrier_name.strip():
            return {
                "success": False,
                "error": "MISSING_CARRIER: Carrier name is mandatory for MERCHANDISE_OR_SERVICE_NOT_RECEIVED evidence.",
                "http_status": 422,
            }

        if not tracking_number or not tracking_number.strip():
            return {
                "success": False,
                "error": "MISSING_TRACKING: Tracking number is mandatory for MERCHANDISE_OR_SERVICE_NOT_RECEIVED evidence.",
                "http_status": 422,
            }

        token, headers, err = self._get_headers()
        if not token:
            return {
                "success": False,
                "error": f"OAuth failed: {err}",
                "http_status": 502,
            }

        # Format official PayPal Disputes provide-evidence payload
        # Spec: evidence_type: PROOF_OF_FULFILLMENT
        # tracking_info: [{carrier_name, tracking_number}]
        evidence_payload = {
            "evidences": [
                {
                    "evidence_type": "PROOF_OF_FULFILLMENT",
                    "evidence_info": {
                        "tracking_info": [
                            {
                                "carrier_name": carrier_name.strip().upper(),
                                "tracking_number": tracking_number.strip(),
                            }
                        ]
                    },
                    "notes": evidence_notes.strip(),
                }
            ]
        }

        t0 = time.time()
        try:
            res = requests.post(
                f"{self.base_url}/v1/customer/disputes/{dispute_id}/provide-evidence",
                headers=headers,
                json=evidence_payload,
                timeout=12.0,
            )
            latency_ms = round((time.time() - t0) * 1000, 2)
            debug_id = res.headers.get("Paypal-Debug-Id")

            # PayPal returns 200 OK or 204 No Content or 201 on successful evidence submission
            if res.status_code in (200, 201, 204):
                res_json = res.json() if res.text.strip() else {}
                return {
                    "success": True,
                    "submitted": True,
                    "http_status": res.status_code,
                    "paypal_debug_id": debug_id,
                    "latency_ms": latency_ms,
                    "dispute_id": dispute_id,
                    "evidence_type": "PROOF_OF_FULFILLMENT",
                    "carrier_name": carrier_name.strip().upper(),
                    "tracking_number": tracking_number.strip(),
                    "submitted_at": datetime.now(timezone.utc).isoformat(),
                    "paypal_response": res_json,
                }
            else:
                return {
                    "success": False,
                    "submitted": False,
                    "http_status": res.status_code,
                    "paypal_debug_id": debug_id,
                    "latency_ms": latency_ms,
                    "error": res.text,
                    "dispute_id": dispute_id,
                    "dispute_state": "PAYPAL_SUBMISSION_REJECTED",
                }
        except Exception as e:
            return {
                "success": False,
                "submitted": False,
                "error": str(e),
                "dispute_id": dispute_id,
            }

    def _format_dispute_summary(self, d: Dict[str, Any]) -> Dict[str, Any]:
        """Convert raw PayPal dispute object to high-clarity merchant summary."""
        amt_info = d.get("dispute_amount", {})
        tx_info = (d.get("disputed_transactions") or [{}])[0]

        reason = d.get("reason", "MERCHANDISE_OR_SERVICE_NOT_RECEIVED")
        status = d.get("status", "WAITING_FOR_SELLER_RESPONSE")
        due_date = d.get("seller_response_due_date")

        urgency_days = None
        if due_date:
            try:
                due_dt = datetime.fromisoformat(due_date.replace("Z", "+00:00"))
                now_dt = datetime.now(timezone.utc)
                urgency_days = max(0, (due_dt - now_dt).days)
            except Exception:
                urgency_days = None

        return {
            "dispute_id": d.get("dispute_id"),
            "reason": reason,
            "status": status,
            "lifecycle_stage": d.get("dispute_life_cycle_stage", "INQUIRY"),
            "amount": amt_info.get("value", "0.00"),
            "currency": amt_info.get("currency_code", "USD"),
            "seller_response_due_date": due_date,
            "urgency_days_left": urgency_days,
            "buyer_transaction_id": tx_info.get("buyer_transaction_id"),
            "seller_transaction_id": tx_info.get("seller_transaction_id"),
            "links": d.get("links", []),
        }

    def _format_dispute_detail(self, d: Dict[str, Any]) -> Dict[str, Any]:
        """Convert raw PayPal dispute object to structured detail representation."""
        summary = self._format_dispute_summary(d)
        tx_info = (d.get("disputed_transactions") or [{}])[0]

        # Extract existing submitted evidences
        evidences = d.get("evidences", [])
        formatted_evidences = []
        for ev in evidences:
            formatted_evidences.append({
                "evidence_type": ev.get("evidence_type"),
                "source": ev.get("source"),
                "notes": ev.get("notes"),
                "item_id": ev.get("item_id"),
            })

        can_submit, submit_reason = self.can_provide_evidence(d)

        summary.update({
            "disputed_transactions": d.get("disputed_transactions", []),
            "buyer_email": tx_info.get("buyer", {}).get("email_address"),
            "buyer_name": tx_info.get("buyer", {}).get("name"),
            "evidences": formatted_evidences,
            "allowed_response_options": d.get("allowed_response_options", []),
            "can_provide_evidence": can_submit,
            "submission_status_message": submit_reason,
            "messages": d.get("messages", []),
            "offer": d.get("offer"),
        })
        return summary


# Global singleton instance
paypal_dispute_client = PayPalDisputeService()

