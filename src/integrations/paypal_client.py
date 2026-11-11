"""
PayPal sandbox integration client.

Reads credentials exclusively from environment variables.
Never logs or prints secrets.
Implements sandbox-only operations by default.

Required environment variables:
    PAYPAL_CLIENT_ID      — PayPal REST API client ID
    PAYPAL_CLIENT_SECRET  — PayPal REST API client secret
    PAYPAL_MODE           — 'sandbox' (default) or 'live' (requires explicit override)
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
from typing import Any, Dict, Optional

from dotenv import load_dotenv
import requests

from src.utils.logging_config import setup_logging

load_dotenv()

logger = setup_logging(name="paypal_client")

SANDBOX_BASE = "https://api-m.sandbox.paypal.com"
LIVE_BASE = "https://api-m.paypal.com"


class PayPalClientError(Exception):
    pass


class PayPalClient:
    """
    PayPal REST API client — sandbox mode by default.

    Never uses hardcoded credentials. Never simulates successful API responses.
    All API results are taken from actual HTTP responses.
    """

    def __init__(
        self,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        mode: Optional[str] = None,
    ):
        self._client_id = os.getenv("PAYPAL_CLIENT_ID", "") if client_id is None else client_id
        self._client_secret = os.getenv("PAYPAL_CLIENT_SECRET", "") if client_secret is None else client_secret
        mode = mode or os.getenv("PAYPAL_MODE", "sandbox")

        if mode == "live":
            confirm = os.getenv("PAYPAL_LIVE_CONFIRM", "").lower()
            if confirm != "yes_i_understand_this_is_live":
                raise PayPalClientError(
                    "Live mode requires PAYPAL_LIVE_CONFIRM='yes_i_understand_this_is_live'. "
                    "Default is sandbox."
                )
            self._base_url = LIVE_BASE
        else:
            self._base_url = SANDBOX_BASE

        self._mode = mode
        self._access_token: Optional[str] = None
        self._token_expires_at: float = 0.0

    @property
    def is_configured(self) -> bool:
        return bool(self._client_id and self._client_secret)

    def _get_access_token(self) -> str:
        """Obtain or refresh OAuth2 access token from PayPal."""
        if not self.is_configured:
            raise PayPalClientError(
                "PAYPAL_CLIENT_ID and PAYPAL_CLIENT_SECRET environment variables are required."
            )
        if self._access_token and time.time() < self._token_expires_at - 60:
            return self._access_token

        resp = requests.post(
            f"{self._base_url}/v1/oauth2/token",
            auth=(self._client_id, self._client_secret),
            data={"grant_type": "client_credentials"},
            timeout=15,
        )
        if resp.status_code != 200:
            raise PayPalClientError(
                f"Token request failed: HTTP {resp.status_code}. "
                "Check credentials and sandbox account setup."
            )
        data = resp.json()
        self._access_token = data["access_token"]
        self._token_expires_at = time.time() + data.get("expires_in", 3600)
        logger.info(f"PayPal access token obtained (mode={self._mode})")
        return self._access_token

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self._get_access_token()}",
            "Content-Type": "application/json",
        }

    def create_order(
        self,
        amount: str,
        currency: str = "USD",
        reference_id: Optional[str] = None,
        description: str = "Digital Goods Order",
    ) -> Dict[str, Any]:
        """Create an order in PayPal Sandbox."""
        payload = {
            "intent": "CAPTURE",
            "purchase_units": [
                {
                    "reference_id": reference_id or f"ref_{int(time.time())}",
                    "description": description,
                    "amount": {
                        "currency_code": currency,
                        "value": amount,
                    },
                }
            ],
        }
        resp = requests.post(
            f"{self._base_url}/v2/checkout/orders",
            headers=self._headers(),
            json=payload,
            timeout=15,
        )
        logger.info(f"create_order: HTTP {resp.status_code}")
        if resp.status_code not in (200, 201):
            raise PayPalClientError(f"create_order failed: HTTP {resp.status_code} - {resp.text}")
        return resp.json()

    def capture_order(self, order_id: str) -> Dict[str, Any]:
        """Capture payment for an order."""
        resp = requests.post(
            f"{self._base_url}/v2/checkout/orders/{order_id}/capture",
            headers=self._headers(),
            json={},
            timeout=15,
        )
        logger.info(f"capture_order {order_id}: HTTP {resp.status_code}")
        if resp.status_code not in (200, 201):
            raise PayPalClientError(f"capture_order failed: HTTP {resp.status_code} - {resp.text}")
        return resp.json()

    def provide_dispute_evidence(
        self,
        dispute_id: str,
        evidence_type: str,
        evidence_info: Dict[str, Any],
        notes: str,
    ) -> Dict[str, Any]:
        """
        Submit evidence for a dispute to PayPal Dispute API.
        Requires CUSTOMER_DISPUTE.MANAGE scope and seller human approval.
        """
        payload = {
            "evidence_type": evidence_type,
            "evidence_info": evidence_info,
            "notes": notes,
        }
        resp = requests.post(
            f"{self._base_url}/v1/customer/disputes/{dispute_id}/provide-evidence",
            headers=self._headers(),
            json=payload,
            timeout=15,
        )
        logger.info(f"provide_dispute_evidence {dispute_id}: HTTP {resp.status_code}")
        if resp.status_code == 403:
            raise PayPalClientError(
                f"Dispute evidence submission denied for {dispute_id}. "
                "Requires CUSTOMER_DISPUTE.MANAGE scope on sandbox app."
            )
        if resp.status_code not in (200, 201, 204):
            raise PayPalClientError(f"provide_dispute_evidence failed: HTTP {resp.status_code} - {resp.text}")
        return resp.json() if resp.text else {"status": "SUBMITTED"}

    def get_order(self, order_id: str) -> Dict[str, Any]:
        """Retrieve order details from PayPal API."""
        resp = requests.get(
            f"{self._base_url}/v2/checkout/orders/{order_id}",
            headers=self._headers(),
            timeout=15,
        )
        logger.info(f"get_order {order_id}: HTTP {resp.status_code}")
        if resp.status_code != 200:
            raise PayPalClientError(f"get_order failed: HTTP {resp.status_code}")
        return resp.json()

    def get_capture(self, capture_id: str) -> Dict[str, Any]:
        """Retrieve capture details."""
        resp = requests.get(
            f"{self._base_url}/v2/payments/captures/{capture_id}",
            headers=self._headers(),
            timeout=15,
        )
        logger.info(f"get_capture {capture_id}: HTTP {resp.status_code}")
        if resp.status_code != 200:
            raise PayPalClientError(f"get_capture failed: HTTP {resp.status_code}")
        return resp.json()

    def list_disputes(
        self,
        page_size: int = 10,
        dispute_state: Optional[str] = None,
    ) -> Dict[str, Any]:
        """List disputes. Requires dispute read permission."""
        params: Dict[str, Any] = {"page_size": page_size}
        if dispute_state:
            params["dispute_state"] = dispute_state
        resp = requests.get(
            f"{self._base_url}/v1/customer/disputes",
            headers=self._headers(),
            params=params,
            timeout=15,
        )
        logger.info(f"list_disputes: HTTP {resp.status_code}")
        if resp.status_code == 403:
            raise PayPalClientError(
                "Dispute listing requires CUSTOMER_DISPUTE.READ scope. "
                "See https://developer.paypal.com/api/disputes/ for setup instructions."
            )
        if resp.status_code != 200:
            raise PayPalClientError(f"list_disputes failed: HTTP {resp.status_code}")
        return resp.json()

    def get_dispute(self, dispute_id: str) -> Dict[str, Any]:
        """Retrieve dispute details."""
        resp = requests.get(
            f"{self._base_url}/v1/customer/disputes/{dispute_id}",
            headers=self._headers(),
            timeout=15,
        )
        logger.info(f"get_dispute {dispute_id}: HTTP {resp.status_code}")
        if resp.status_code == 403:
            raise PayPalClientError(
                f"Dispute access denied for {dispute_id}. "
                "Requires CUSTOMER_DISPUTE.READ scope."
            )
        if resp.status_code != 200:
            raise PayPalClientError(f"get_dispute failed: HTTP {resp.status_code}")
        return resp.json()

    def verify_webhook_signature(
        self,
        transmission_id: str,
        transmission_time: str,
        webhook_id: str,
        event_body: bytes,
        cert_url: str,
        auth_algo: str,
        actual_signature: str,
    ) -> bool:
        """
        Verify PayPal webhook signature using the documented API method.
        https://developer.paypal.com/api/webhooks/v1/#verify-webhook-signature_post
        """
        payload = {
            "transmission_id": transmission_id,
            "transmission_time": transmission_time,
            "cert_url": cert_url,
            "auth_algo": auth_algo,
            "transmission_sig": actual_signature,
            "webhook_id": webhook_id,
            "webhook_event": json.loads(event_body),
        }
        resp = requests.post(
            f"{self._base_url}/v1/notifications/verify-webhook-signature",
            headers=self._headers(),
            json=payload,
            timeout=15,
        )
        if resp.status_code != 200:
            logger.warning(f"Webhook verification API returned HTTP {resp.status_code}")
            return False
        result = resp.json()
        verified = result.get("verification_status") == "SUCCESS"
        logger.info(f"Webhook signature verification: {result.get('verification_status')}")
        return verified

