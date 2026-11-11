# PayPal Integration Guide — ProofLedger

## Overview

ProofLedger integrates with the PayPal REST API to retrieve authentic transaction records for evidence verification. This document covers the implemented integration, required configuration, access restrictions, and the distinction between sandbox, mock, and production modes.

## Architecture

```
PayPal API → PayPalClient → EvidenceCompiler → EvidenceVerifier → API Response
                ↑
          Sandbox only (default)
          No production calls during development
```

## Implemented Functionality

| Endpoint | Method | Status | Notes |
|---|---|---|---|
| `/v1/oauth2/token` | POST | Implemented | Credentials from env vars only |
| `/v2/checkout/orders/{id}` | GET | Implemented | Retrieve order details |
| `/v2/payments/captures/{id}` | GET | Implemented | Retrieve capture details |
| `/v1/customer/disputes` | GET | Implemented | Requires READ scope |
| `/v1/customer/disputes/{id}` | GET | Implemented | Requires READ scope |
| `/v1/notifications/verify-webhook-signature` | POST | Implemented | Webhook verification |
| Evidence submission | POST | Skeleton only | Requires active dispute + WRITE scope |

## Configuration

```bash
# Required environment variables (sandbox)
export PAYPAL_CLIENT_ID=your_sandbox_client_id
export PAYPAL_CLIENT_SECRET=your_sandbox_client_secret
export PAYPAL_MODE=sandbox  # default

# Optional: PayPal webhook ID for signature verification
export PAYPAL_WEBHOOK_ID=your_webhook_id

# NEVER set these in source code or commit them to Git
```

## Sandbox Test Results

| Test | Status | Notes |
|---|---|---|
| credentials_configured | BLOCKED | No credentials provided in this environment |
| sandbox_authentication | BLOCKED | Depends on credentials |
| list_disputes | BLOCKED | Also requires `CUSTOMER_DISPUTE.READ` scope |
| get_order (invalid ID) | BLOCKED | Depends on authentication |
| webhook_signature_verification | SKIPPED | Requires incoming webhook delivery |
| evidence_submission | BLOCKED | Requires active dispute + scope |

To run sandbox tests with credentials:
```bash
PAYPAL_CLIENT_ID=xxx PAYPAL_CLIENT_SECRET=yyy python -m src.integrations.paypal_sandbox_tests
```

## Required PayPal Permissions

| Permission | Purpose | How to Enable |
|---|---|---|
| `CUSTOMER_DISPUTE.READ` | List and retrieve disputes | Developer Dashboard → App → Features → Disputes |
| `CUSTOMER_DISPUTE.UPDATE` | Submit evidence | Same location |
| `ORDERS.READ` | Retrieve order details | Usually included by default |
| `PAYMENTS.READ` | Retrieve capture details | Usually included by default |

See: https://developer.paypal.com/api/disputes/

## Webhook Verification

Webhook signatures are verified using the PayPal Webhook Verification API (`/v1/notifications/verify-webhook-signature`), not by local HMAC. This is the documented approach that handles key rotation automatically.

Required headers from PayPal:
- `PAYPAL-TRANSMISSION-ID`
- `PAYPAL-TRANSMISSION-TIME`
- `PAYPAL-CERT-URL`
- `PAYPAL-AUTH-ALGO`
- `PAYPAL-TRANSMISSION-SIG`

## Safety Guarantees

1. **Sandbox by default**: `PAYPAL_MODE` defaults to `sandbox`. Live mode requires explicit `PAYPAL_LIVE_CONFIRM` environment variable.
2. **No secret logging**: The `RedactingFormatter` in `logging_config.py` redacts Bearer tokens and secrets from all log output.
3. **No fabricated responses**: The client reads actual HTTP status codes and response bodies. A 200 status does not mean business success — the response body is checked.
4. **No mock in production code**: All mocked responses are confined to test files explicitly marked as MOCK.
5. **No auto-submission**: Evidence is never submitted without explicit human approval via the application UI.

## Mock vs. Real API

| Context | Mode | Label |
|---|---|---|
| Unit tests (`TestPayPalClientMocked`) | Mock | Explicitly labelled "MOCK" in docstrings |
| Integration tests (no credentials) | Blocked real | Status: BLOCKED |
| Integration tests (with credentials) | Real sandbox | Status: PASSED/FAILED |
| Production | Real live | Must be explicitly configured |

## Known Blockers

1. **No PayPal credentials available**: Sandbox tests blocked. Provide `PAYPAL_CLIENT_ID` and `PAYPAL_CLIENT_SECRET` to unblock.
2. **Dispute scope**: `CUSTOMER_DISPUTE.READ` requires manual permission grant in the PayPal Developer Dashboard. This cannot be automated.
3. **No active sandbox dispute**: Evidence submission testing requires creating a sandbox buyer account, making a purchase, and filing a test dispute. See https://developer.paypal.com/disputes/test-go-live/ for setup instructions.

## References

- https://developer.paypal.com/api/orders/v2/
- https://developer.paypal.com/api/payments/v2/
- https://developer.paypal.com/api/disputes/
- https://developer.paypal.com/platforms/disputes/integrate-disputes/
- https://developer.paypal.com/disputes/test-go-live/
- https://developer.paypal.com/api/webhooks/v1/#verify-webhook-signature_post

