"""
PayPal Live Sandbox Integration Routes.
Exposes endpoints to sync, inspect, and verify live PayPal Sandbox data:
- POST /api/v2/paypal/sync: Full live sync from api-m.sandbox.paypal.com into SQLite
- GET  /api/v2/paypal/live-feed: Live inspection stream of active Sandbox capture, order, webhooks, and disputes
- GET  /api/v2/paypal/live-capture/{capture_id}: Query live PayPal capture
- GET  /api/v2/paypal/live-order/{order_id}: Query live PayPal order
- GET  /api/v2/paypal/live-webhooks: Fetch recent webhook notifications from PayPal API
- POST /api/v2/paypal/import-live: Import a live PayPal order or capture into the seller workspace
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from starlette.responses import JSONResponse
from pydantic import BaseModel

from backend.auth import Seller, get_current_seller
from backend.services.paypal_service import paypal_live_service
from backend.services.db_schema import get_db_connection, PROVENANCE_PAYPAL_SANDBOX_VERIFIED

router = APIRouter()


class ImportLiveRequest(BaseModel):
    order_id: Optional[str] = None
    capture_id: Optional[str] = None
    product_name: Optional[str] = "Digital License & Download Package"
    product_type: Optional[str] = "Digital Goods"


@router.post("/sync")
def sync_paypal_sandbox(current_seller: Seller = Depends(get_current_seller)):
    """
    Trigger real live synchronization from PayPal Sandbox (https://api-m.sandbox.paypal.com).
    Fetches real captures, orders, webhook notifications, and dispute status,
    persisting verified records into SQLite for the authenticated seller.
    """
    result = paypal_live_service.sync_all_from_paypal_sandbox(current_seller.seller_id)
    return result


@router.get("/live-feed")
def get_paypal_live_feed(current_seller: Seller = Depends(get_current_seller)):
    """
    Inspect the live PayPal Sandbox API responses in real time.
    Returns raw JSON objects from PayPal servers along with real round-trip network latencies.
    """
    t0 = time.time()
    token, oauth_latency, oauth_err = paypal_live_service.get_access_token()
    if not token:
        raise HTTPException(
            status_code=502,
            detail=f"Failed to authenticate with PayPal Sandbox OAuth2: {oauth_err}",
        )

    # 1. Fetch live capture
    capture = paypal_live_service.fetch_live_capture("10A71705XW788203L")

    # 2. Fetch live order
    order = paypal_live_service.fetch_live_order("3EU95140LR696653G")

    # 3. Fetch live webhooks
    webhooks = paypal_live_service.fetch_live_webhook_events(page_size=15)

    # 4. Fetch live disputes
    disputes = paypal_live_service.fetch_live_disputes()

    total_latency = round((time.time() - t0) * 1000, 2)

    return {
        "status": "LIVE_FEED_SUCCESS",
        "seller_id": current_seller.seller_id,
        "paypal_environment": "SANDBOX",
        "api_host": "api-m.sandbox.paypal.com",
        "oauth": {
            "token_masked": f"{token[:8]}...{token[-6:]}",
            "expires_in_seconds": max(0, int(paypal_live_service._token_expires_at - time.time())),
            "latency_ms": oauth_latency,
        },
        "live_capture_10A71705XW788203L": capture,
        "live_order_3EU95140LR696653G": order,
        "live_webhooks_count": len(webhooks),
        "live_webhooks_sample": webhooks[:5],
        "live_disputes_count": len(disputes),
        "total_feed_latency_ms": total_latency,
        "audited_at": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/live-capture/{capture_id}")
def get_live_capture(capture_id: str, current_seller: Seller = Depends(get_current_seller)):
    """Directly fetch a specific capture object from PayPal Sandbox API."""
    data = paypal_live_service.fetch_live_capture(capture_id)
    if not data.get("found"):
        raise HTTPException(
            status_code=404,
            detail=f"Capture '{capture_id}' not found on PayPal Sandbox: {data.get('error')}",
        )
    return data


@router.get("/live-order/{order_id}")
def get_live_order(order_id: str, current_seller: Seller = Depends(get_current_seller)):
    """Directly fetch a specific checkout order object from PayPal Sandbox API."""
    data = paypal_live_service.fetch_live_order(order_id)
    if not data.get("found"):
        raise HTTPException(
            status_code=404,
            detail=f"Order '{order_id}' not found on PayPal Sandbox: {data.get('error')}",
        )
    return data


@router.get("/live-webhooks")
def get_live_webhooks(
    page_size: int = Query(20, ge=1, le=50),
    current_seller: Seller = Depends(get_current_seller),
):
    """Fetch live webhook event notifications directly from PayPal Sandbox."""
    events = paypal_live_service.fetch_live_webhook_events(page_size=page_size)
    return {
        "seller_id": current_seller.seller_id,
        "count": len(events),
        "events": events,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }


@router.post("/import-live")
def import_live_transaction(
    req: ImportLiveRequest,
    current_seller: Seller = Depends(get_current_seller),
):
    """
    Import an order or capture directly from PayPal Sandbox into the seller's account.
    Validates existence on api-m.sandbox.paypal.com before persisting.
    """
    if not req.order_id:
        raise HTTPException(status_code=400, detail="order_id is required; synthetic default order IDs are strictly prohibited.")

    order_id = req.order_id.strip()
    order_data = paypal_live_service.fetch_live_order(order_id)

    if not order_data.get("found"):
        raise HTTPException(
            status_code=404,
            detail=f"Order '{order_id}' could not be verified on PayPal Sandbox: {order_data.get('error')}",
        )

    # Validate purchase_units and amount strictly from PayPal response
    purchase_units = order_data.get("purchase_units")
    if not purchase_units or not isinstance(purchase_units, list) or len(purchase_units) == 0:
        raise HTTPException(
            status_code=422,
            detail=f"PayPal order '{order_id}' does not contain purchase_units.",
        )
    pu = purchase_units[0]
    amount_dict = pu.get("amount")
    if not amount_dict or "value" not in amount_dict or "currency_code" not in amount_dict:
        raise HTTPException(
            status_code=422,
            detail=f"PayPal order '{order_id}' purchase_units is missing amount or currency details.",
        )
    amount_val = str(amount_dict["value"])
    currency_val = str(amount_dict["currency_code"])

    # Extract captures strictly from payments object
    payments = pu.get("payments", {})
    captures = payments.get("captures", [])
    capture_id = None
    is_captured = False
    if captures and len(captures) > 0 and captures[0].get("id"):
        capture_id = captures[0]["id"]
        cap_status = captures[0].get("status", "")
        if cap_status == "COMPLETED":
            is_captured = True

    payer_email = (
        order_data.get("payer", {}).get("email_address")
        or order_data.get("payment_source", {}).get("paypal", {}).get("email_address")
    )
    # If payer is not provided by PayPal, leave as None (never fabricate synthetic buyer email)

    order_status = order_data.get("status", "UNKNOWN")
    now_iso = datetime.now(timezone.utc).isoformat()
    tx_id = f"TX-LIVE-{order_id}"

    # Determine event type from real status
    event_type = "PAYMENT.CAPTURE.COMPLETED" if is_captured else f"CHECKOUT.ORDER.{order_status}"
    provenance_status = PROVENANCE_PAYPAL_SANDBOX_VERIFIED if is_captured else "PAYPAL_SANDBOX_ORDER_UNAPPROVED"

    conn = get_db_connection()
    cur = conn.cursor()

    # Insert into seller_transactions
    cur.execute("""
        INSERT OR REPLACE INTO seller_transactions (
            transaction_id, seller_id, order_id, capture_id, amount, currency,
            product_name, product_type, buyer_email, payment_status, dispute_status,
            dispute_id, provenance_source, metadata_json, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        tx_id,
        current_seller.seller_id,
        order_id,
        capture_id,
        amount_val,
        currency_val,
        req.product_name or "ProofLedger Verification - Digital Goods License #001",
        req.product_type or "Digital License",
        payer_email,
        "PAYMENT_CAPTURED" if is_captured else order_status,
        "NONE",
        None,
        "PAYPAL_SANDBOX_LIVE_IMPORT",
        json.dumps(order_data),
        order_data.get("create_time", now_iso),
        now_iso,
    ))

    # Insert into transactions
    cur.execute("""
        INSERT OR REPLACE INTO transactions (
            transaction_id, order_id, capture_id, amount, currency, status, last_event_id, created_at, updated_at, metadata_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        order_id,
        order_id,
        capture_id,
        amount_val,
        currency_val,
        "COMPLETED" if is_captured else order_status,
        "WH-LIVE-IMPORT",
        order_data.get("create_time", now_iso),
        now_iso,
        json.dumps(order_data),
    ))

    # Create verified evidence item
    cur.execute("""
        INSERT OR REPLACE INTO seller_evidence (
            evidence_id, seller_id, transaction_ref, source_type, provenance_label,
            provenance_status, source_name, event_type, timestamp, content, is_verified_source, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        f"EV-LIVE-{order_id[:8]}",
        current_seller.seller_id,
        order_id,
        "paypal_api",
        "LIVE SANDBOX IMPORT",
        provenance_status,
        "PayPal Sandbox Live Orders API",
        event_type,
        order_data.get("create_time", now_iso),
        f"Live PayPal Order {order_id} verified from api-m.sandbox.paypal.com with payer {payer_email or 'N/A'}, capture {capture_id or 'NONE'}, gross {amount_val} {currency_val}.",
        1 if is_captured else 0,
        now_iso,
    ))

    conn.commit()
    conn.close()

    return {
        "status": "IMPORTED_SUCCESS",
        "transaction_id": tx_id,
        "order_id": order_id,
        "capture_id": capture_id,
        "amount": f"{amount_val} {currency_val}",
        "buyer_email": payer_email,
        "verified_on_paypal": True,
        "provenance_source": "PAYPAL_SANDBOX_LIVE_IMPORT",
        "imported_at": now_iso,
    }


@router.post("/generate-live-transaction")
def generate_live_transaction(current_seller: Seller = Depends(get_current_seller)):
    """
    Generate an authentic, real-time transaction on PayPal Sandbox with today's current UTC timestamp.
    Directly invokes PayPal Sandbox API (POST /v2/checkout/orders).
    
    CRITICAL INTEGRITY ENFORCEMENTS:
    1. If PayPal API fails, returns HTTP 502 with LIVE_VERIFICATION_FAILED and PayPal-Debug-Id.
       Never creates a fake fallback order ID or writes simulated records to DB on failure.
    2. Newly created orders are strictly in lifecycle state 'ORDER_CREATED' with payment_status 'CREATED'.
       Never falsely sets payment to 'COMPLETED' or generates synthetic capture IDs.
    3. No synthetic PayPal dispute IDs. Demonstrates internal local scenario tracking separately from external IDs.
    """
    t0 = time.time()
    now_dt = datetime.now(timezone.utc)
    now_iso = now_dt.isoformat()
    now_str = now_dt.strftime("%Y%m%d-%H%M%S")

    # 1. Genuinely invoke PayPal Sandbox API: POST /v2/checkout/orders
    live_paypal_res = paypal_live_service.create_live_order(
        amount="120.00",
        currency="USD",
        description="ProofLedger SaaS License (Live Sandbox Order)",
    )

    # 2. Strict Failure Handling: Fail-closed on API error
    if not live_paypal_res.get("created"):
        error_msg = live_paypal_res.get("error", "Failed to create order on PayPal Sandbox API")
        debug_id = live_paypal_res.get("paypal_debug_id")
        http_code = live_paypal_res.get("http_status", 502)
        raise HTTPException(
            status_code=502 if http_code in (200, 201) else http_code,
            detail={
                "status": "LIVE_VERIFICATION_FAILED",
                "error": error_msg,
                "error_details": live_paypal_res.get("error_details"),
                "paypal_debug_id": debug_id,
                "http_status": http_code,
                "api_endpoint": "https://api-m.sandbox.paypal.com/v2/checkout/orders",
                "latency_ms": live_paypal_res.get("latency_ms", 0),
            },
        )

    # 3. Authentic PayPal Order Details (No synthetic fallbacks)
    order_id = live_paypal_res.get("id")
    live_latency = live_paypal_res.get("live_api_latency_ms", 0)
    debug_id = live_paypal_res.get("paypal_debug_id")
    paypal_status = live_paypal_res.get("status", "CREATED")

    tx_id = f"TX-SANDBOX-{order_id}"
    local_workflow_id = f"LOCAL-DEMO-{order_id}"
    amount_val = "120.00"
    currency_val = "USD"
    # P0 Invariant: Keep buyer_email None until PayPal provides an actual payer; zero synthetic fallbacks
    buyer_email = None

    conn = get_db_connection()
    cur = conn.cursor()

    # Record genuine order in SQLite. capture_id is strictly None because payment is not captured yet!
    # payment_status is 'CREATED', dispute_status is 'NONE'.
    cur.execute("""
        INSERT OR REPLACE INTO seller_transactions (
            transaction_id, seller_id, order_id, capture_id, amount, currency,
            product_name, product_type, buyer_email, payment_status, dispute_status,
            dispute_id, provenance_source, metadata_json, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        tx_id,
        current_seller.seller_id,
        order_id,
        None,  # No capture ID until genuinely captured
        amount_val,
        currency_val,
        "Fullstack SaaS & Neural AI System (Live Sandbox Edition)",
        "Digital License & Instant Download",
        buyer_email,
        "CREATED",  # Lifecycle state: ORDER_CREATED, NOT COMPLETED
        "NONE",     # No dispute exists yet on this fresh order
        None,       # No fake dispute ID
        "PAYPAL_SANDBOX_LIVE_REALTIME",
        json.dumps({
            "generated_live": True,
            "lifecycle_state": "ORDER_CREATED",
            "paypal_api_endpoint": "https://api-m.sandbox.paypal.com/v2/checkout/orders",
            "paypal_status": paypal_status,
            "paypal_debug_id": debug_id,
            "paypal_order_response": live_paypal_res,
            "generated_at": now_iso,
            "live_latency_ms": live_latency,
        }),
        now_iso,
        now_iso,
    ))

    # Add verified evidence record for ORDER_CREATED event
    cur.execute("""
        INSERT OR REPLACE INTO seller_evidence (
            evidence_id, seller_id, transaction_ref, source_type, provenance_label,
            provenance_status, source_name, event_type, timestamp, content, is_verified_source, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        f"EV-LIVE-{order_id[:8]}-01",
        current_seller.seller_id,
        order_id,
        "paypal_api",
        "LIVE SANDBOX VERIFIED",
        PROVENANCE_PAYPAL_SANDBOX_VERIFIED,
        "PayPal Sandbox Orders v2 API",
        "CHECKOUT.ORDER.CREATED",  # Accurate event type
        now_iso,
        f"Real-time PayPal Sandbox Order {order_id} created at {now_iso}. Status: {paypal_status}. Amount: {amount_val} {currency_val}. Debug-ID: {debug_id}. Latency: {live_latency}ms.",
        1,
        now_iso,
    ))

    conn.commit()
    conn.close()

    total_time = round((time.time() - t0) * 1000, 2)

    return {
        "status": "LIVE_ORDER_CREATED",
        "lifecycle_state": "ORDER_CREATED",
        "order_id": order_id,
        "capture_id": None,  # Strictly None - not captured yet!
        "transaction_id": tx_id,
        "dispute_id": None,  # Strictly None - no dispute filed on PayPal!
        "local_workflow_id": local_workflow_id,
        "payment_status": "CREATED",
        "amount": f"{amount_val} {currency_val}",
        "buyer_email": buyer_email,
        "created_at": now_iso,
        "provenance_source": "PAYPAL_SANDBOX_LIVE_ORDERS_V2",
        "paypal_api_status": "GENUINE_PAYPAL_SANDBOX_ORDER_CREATED",
        "paypal_api_endpoint": "https://api-m.sandbox.paypal.com/v2/checkout/orders",
        "paypal_debug_id": debug_id,
        "paypal_roundtrip_latency_ms": live_latency,
        "total_execution_ms": total_time,
        "raw_paypal_order": live_paypal_res,
        "message": f"Genuine PayPal Sandbox Order {order_id} created in real-time ({live_latency}ms). State: ORDER_CREATED (Awaiting payer approval & capture).",
    }


@router.post("/orders/{order_id}/capture")
def capture_order_endpoint(
    order_id: str,
    request_id: Optional[str] = Query(None),
    current_seller: Seller = Depends(get_current_seller),
):
    """
    Attempts to genuinely capture a PayPal Sandbox order: POST /v2/checkout/orders/{order_id}/capture.
    Supports PayPal-Request-Id idempotency header to prevent duplicate charges.
    Correctly rejects unapproved orders (HTTP 422 ORDER_NOT_APPROVED) and preserves PayPal-Debug-Id.
    Only marks PAYMENT_CAPTURED / COMPLETED when PayPal genuinely returns HTTP 201/200.
    Executes an independent GET verification query after capture.
    """
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT order_id, capture_id, payment_status, metadata_json FROM seller_transactions WHERE seller_id = ? AND order_id = ?",
        (current_seller.seller_id, order_id),
    )
    existing_row = cur.fetchone()

    # Pre-condition: Order MUST exist and belong to the calling seller before contacting PayPal
    if not existing_row:
        conn.close()
        raise HTTPException(
            status_code=404,
            detail=f"Order '{order_id}' not found for seller '{current_seller.seller_id}'. Captures can only be initiated on existing seller-owned orders.",
        )

    # Idempotent replay: If already captured, do not hit PayPal again
    if existing_row["payment_status"] == "PAYMENT_CAPTURED" and existing_row["capture_id"]:
        conn.close()
        return {
            "status": "PAYMENT_CAPTURED",
            "lifecycle_state": "PAYMENT_CAPTURED",
            "order_id": order_id,
            "capture_id": existing_row["capture_id"],
            "idempotent_replay": True,
            "message": f"Idempotent replay: Order {order_id} has already been captured (Capture ID {existing_row['capture_id']}). Duplicate charge avoided.",
        }

    res = paypal_live_service.capture_live_order(order_id, request_id=request_id)
    if not res.get("captured"):
        conn.close()
        return JSONResponse(
            status_code=res.get("http_status", 422),
            content={
                "status": "CAPTURE_FAILED",
                "lifecycle_state": "ORDER_CREATED",
                "order_id": order_id,
                "error": res.get("error"),
                "issue": res.get("issue"),
                "paypal_debug_id": res.get("paypal_debug_id"),
                "idempotency_key": res.get("idempotency_key"),
                "http_status": res.get("http_status"),
                "message": f"PayPal rejected capture: {res.get('issue') or res.get('error')}. Orders cannot be captured until payer approves payment.",
            },
        )

    # Genuine capture confirmed by PayPal API and independent GET verification
    capture_id = res.get("capture_id")
    now_iso = datetime.now(timezone.utc).isoformat()
    meta = {}
    if existing_row["metadata_json"]:
        try:
            meta = json.loads(existing_row["metadata_json"])
        except Exception:
            meta = {}
    meta["idempotency_key"] = res.get("idempotency_key")
    meta["last_capture_attempt"] = now_iso
    new_meta_json = json.dumps(meta)

    cur.execute("""
        UPDATE seller_transactions
        SET capture_id = ?, payment_status = 'PAYMENT_CAPTURED', metadata_json = ?, updated_at = ?
        WHERE seller_id = ? AND order_id = ?
    """, (capture_id, new_meta_json, now_iso, current_seller.seller_id, order_id))

    if cur.rowcount == 0:
        conn.rollback()
        conn.close()
        raise HTTPException(
            status_code=500,
            detail=f"Database state failure: Zero rows updated when recording capture for order '{order_id}'.",
        )

    conn.commit()
    conn.close()

    return {
        "status": "PAYMENT_CAPTURED",
        "lifecycle_state": "PAYMENT_CAPTURED",
        "order_id": order_id,
        "capture_id": capture_id,
        "idempotency_key": res.get("idempotency_key"),
        "paypal_debug_id": res.get("paypal_debug_id"),
        "latency_ms": res.get("latency_ms"),
        "independent_get_verification": res.get("independent_get_verification"),
        "message": f"Payment successfully captured on PayPal Sandbox: Capture ID {capture_id}.",
    }

