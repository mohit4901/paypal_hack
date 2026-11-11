"""
API integration tests for the FastAPI inference service.

These tests start the app with TestClient (no real server needed).
Model loading is mocked — tests focus on API contract and validation.
"""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


class TestAPIWithMockedModel:
    """API contract tests with mocked model — no real model weights needed."""

    @pytest.fixture(autouse=True)
    def mock_verifier(self):
        """Patch EvidenceVerifier to avoid loading real model weights."""
        mock_v = MagicMock()
        mock_v.is_loaded = True
        mock_v.model_info = {
            "model_path": "mock/model",
            "architecture": "deberta-v3",
            "num_labels": 3,
            "id2label": {0: "SUPPORTED", 1: "CONTRADICTED", 2: "INSUFFICIENT_EVIDENCE"},
            "nli_to_app": {"entailment": "SUPPORTED", "contradiction": "CONTRADICTED", "neutral": "INSUFFICIENT_EVIDENCE"},
            "device": "cpu",
        }
        mock_v.predict.return_value = {
            "label": "SUPPORTED",
            "confidence": 0.91,
            "note_confidence": "Raw model score.",
            "scores": {"SUPPORTED": 0.91, "CONTRADICTED": 0.05, "INSUFFICIENT_EVIDENCE": 0.04},
            "nli_scores": {"entailment": 0.91},
            "evidence_ids": ["ev_001"],
            "truncated": False,
            "truncation_warning": None,
            "model_path": "mock/model",
        }
        with patch("src.api.main._verifier", mock_v):
            from src.api.main import app
            with TestClient(app) as client:
                self.client = client
                yield

    def test_health_ok(self):
        resp = self.client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["model_loaded"] is True

    def test_model_info(self):
        resp = self.client.get("/model/info")
        assert resp.status_code == 200
        data = resp.json()
        assert "model_path" in data
        assert "disclaimer" in data

    def test_predict_valid(self):
        resp = self.client.post("/predict", json={
            "claim": "Payment was confirmed for order ord_123.",
            "evidence": [{
                "evidence_id": "ev_001",
                "source_type": "paypal_api",
                "timestamp": "2025-01-01T10:00:00Z",
                "content": "Capture status=COMPLETED order=ord_123.",
            }],
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["label"] in ("SUPPORTED", "CONTRADICTED", "INSUFFICIENT_EVIDENCE")
        assert "human_review_required" in data
        assert "limitations" in data
        assert len(data["limitations"]) > 0

    def test_predict_empty_claim_rejected(self):
        resp = self.client.post("/predict", json={"claim": "Hi", "evidence": []})
        assert resp.status_code == 422  # Pydantic validation error

    def test_predict_empty_content_rejected(self):
        resp = self.client.post("/predict", json={
            "claim": "Valid claim about something.",
            "evidence": [{"evidence_id": "ev1", "source_type": "api", "content": "   "}],
        })
        assert resp.status_code == 422

    def test_predict_duplicate_evidence_ids_rejected(self):
        resp = self.client.post("/predict", json={
            "claim": "Some valid claim here.",
            "evidence": [
                {"evidence_id": "ev_001", "source_type": "api", "content": "Content A"},
                {"evidence_id": "ev_001", "source_type": "api", "content": "Content B"},
            ],
        })
        assert resp.status_code == 422

    def test_predict_no_evidence_allowed(self):
        resp = self.client.post("/predict", json={
            "claim": "Some valid claim here for testing.",
            "evidence": [],
        })
        assert resp.status_code == 200  # empty evidence is valid (returns INSUFFICIENT_EVIDENCE)

    def test_validate_evidence_endpoint(self):
        resp = self.client.post("/validate-evidence", json={
            "claim": "Payment was captured.",
            "evidence": [{
                "evidence_id": "ev_001",
                "source_type": "paypal_api",
                "timestamp": "2025-01-01T10:00:00Z",
                "content": "Capture status=COMPLETED order=ord_123.",
            }],
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "label" in data
        assert "deterministic_checks" in data
        assert data["human_review_required"] is True

    def test_batch_predict(self):
        resp = self.client.post("/batch-predict", json={
            "items": [
                {
                    "claim": "Payment was confirmed for order ord_123.",
                    "evidence": [{
                        "evidence_id": "ev_001",
                        "source_type": "paypal_api",
                        "content": "Capture status=COMPLETED order=ord_123.",
                    }],
                },
                {
                    "claim": "File was delivered to buyer for order ord_456.",
                    "evidence": [{
                        "evidence_id": "ev_002",
                        "source_type": "delivery_service",
                        "content": "File delivered order=ord_456.",
                    }],
                },
            ]
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 2
        assert len(data["results"]) == 2

    def test_batch_predict_too_many_items(self):
        items = [
            {
                "claim": f"Claim number {i}.",
                "evidence": [{"evidence_id": f"ev_{i}", "source_type": "api", "content": f"Content {i}"}]
            }
            for i in range(51)  # exceeds limit of 50
        ]
        resp = self.client.post("/batch-predict", json={"items": items})
        assert resp.status_code in (422, 400)

    def test_metrics_endpoint(self):
        resp = self.client.get("/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert "evaluation_summaries" in data

    def test_evidence_ids_in_response_are_subset_of_input(self):
        """Model must not return evidence IDs not present in the input."""
        resp = self.client.post("/predict", json={
            "claim": "Payment confirmed for order ord_999.",
            "evidence": [{"evidence_id": "real_ev_001", "source_type": "api", "content": "Payment COMPLETED order=ord_999."}],
        })
        assert resp.status_code == 200
        data = resp.json()
        input_ids = {"real_ev_001"}
        for eid in data.get("supporting_evidence_ids", []):
            assert eid in input_ids, f"Model returned non-existent evidence ID: {eid}"
        for eid in data.get("contradicting_evidence_ids", []):
            assert eid in input_ids, f"Model returned non-existent evidence ID: {eid}"

    def test_submit_dispute_evidence_requires_human_approval(self):
        """Automated submission without seller human approval must be rejected with 422/400."""
        resp = self.client.post("/paypal/disputes/PP-D-12345/submit-evidence", json={
            "dispute_id": "PP-D-12345",
            "evidence_type": "PROOF_OF_DELIVERY",
            "evidence_info": {"tracking_number": "TRK9988"},
            "notes": "Verified delivery proof.",
            "seller_human_approved": False,
        })
        assert resp.status_code in (400, 422)

    def test_submit_dispute_evidence_mismatched_id_rejected(self):
        """Mismatched dispute ID in URL and body must be rejected."""
        resp = self.client.post("/paypal/disputes/PP-D-12345/submit-evidence", json={
            "dispute_id": "PP-D-99999",
            "evidence_type": "PROOF_OF_DELIVERY",
            "evidence_info": {"tracking_number": "TRK9988"},
            "notes": "Verified delivery proof.",
            "seller_human_approved": True,
        })
        assert resp.status_code == 400
        assert "Mismatched dispute_id" in resp.json()["detail"]

    @patch("src.integrations.paypal_client.PayPalClient.is_configured", False)
    def test_submit_dispute_evidence_unconfigured_sandbox_returns_503(self):
        """When PayPal credentials are not configured, endpoint cleanly returns 503 rather than mocking."""
        resp = self.client.post("/paypal/disputes/PP-D-12345/submit-evidence", json={
            "dispute_id": "PP-D-12345",
            "evidence_type": "PROOF_OF_DELIVERY",
            "evidence_info": {"tracking_number": "TRK9988"},
            "notes": "Verified delivery proof.",
            "seller_human_approved": True,
        })
        assert resp.status_code == 503
        assert "PAYPAL_CLIENT_ID and PAYPAL_CLIENT_SECRET not configured" in resp.json()["detail"]


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
