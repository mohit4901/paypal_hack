# PayPal Sandbox Connectivity & Verification Report

## 1. Verified Live Sandbox Integration

ProofLedger connects directly to the official PayPal Sandbox REST API environment:
- **Base URL**: `https://api-m.sandbox.paypal.com`
- **Authentication**: OAuth 2.0 Client Credentials (`/v1/oauth2/token`)
- **Verified Credentials**: Validated merchant client credentials with `grant_type=client_credentials`
- **Disputes Endpoint**: `GET /v1/customer/disputes` returns **HTTP 200 OK**.

---

## 2. Live API Connectivity Evidence

```bash
# Live Sandbox Disputes Endpoint Verification
curl -s -X GET "https://api-m.sandbox.paypal.com/v1/customer/disputes" \
  -H "Authorization: Bearer <SANDBOX_OAUTH_TOKEN>" \
  -H "Content-Type: application/json"
```

**Live PayPal HTTP Response**:
```json
{
  "items": [],
  "links": [
    {
      "href": "https://api-m.sandbox.paypal.com/v1/customer/disputes?page_size=10",
      "rel": "self",
      "method": "GET"
    }
  ]
}
```

### Key Observation & Explicit Verification Boundaries:
- The live PayPal Sandbox Disputes API responded with **HTTP 200 OK** (`GET /v1/customer/disputes`, `items: []`).
- **Live Dispute Evidence Submission Remains UNVERIFIED**: Because Sandbox currently holds 0 genuine buyer disputes, live end-to-end `POST /v1/customer/disputes/PP-D-XXXXX/provide-evidence` against a real PayPal dispute ID has **not** been executed. Submitting local scenario `DSP-3EU95140-01` against PayPal returned HTTP 404 `RESOURCE_NOT_FOUND` (`Paypal-Debug-Id: f240973116103`) and stays quarantined as `LOCAL_SIMULATED_SUBMISSION`.
- **Automated Carrier Delivery Scan Lookup Remains NOT CONFIGURED**: No live USPS/UPS/FedEx/DHL tracking API integration is configured; delivery scan checks return `LOOKUP_NOT_CONFIGURED`.

---

## 3. Separation of Provenance (Local vs Live)

To demonstrate the full end-to-end evidence preparation and resolution workflow during testing and demo presentations without falsifying records, ProofLedger clearly segregates dispute provenance:

1. **`PAYPAL_SANDBOX_LIVE`**:
   - Pulled live from PayPal REST API (`GET /v1/customer/disputes`, latest `Paypal-Debug-Id: f9491489e3ad1`, HTTP 200 OK).
   - Tagged in the UI with a green indicator: `● LIVE PAYPAL SANDBOX DISPUTE`.
2. **`LOCAL_DEMO_SCENARIO`**:
   - Seeded from real captured PayPal orders (`3EU95140LR696653G`).
   - Tagged in the UI with an explicit warning badge: `LOCAL DEMO — NOT A PAYPAL DISPUTE`.
   - Live PayPal submission is disabled in UI and rejected server-side when `require_live_paypal: true`.

---

## 4. PayPal Agent Toolkit Bridge

- Integrated with official `@paypal/agent-toolkit` (v1.11.0).
- Configured with read-only tools: `get_dispute_details`, `list_disputes`.
- Financial mutation tools are disabled in accordance with the principle of least privilege.

