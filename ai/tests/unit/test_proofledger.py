"""
Comprehensive test suite for ProofLedger.

Tests:
- Data parsing and label conversion
- EvidenceBench generation
- Input formatting
- Deterministic validator
- Evidence compiler (hash chain)
- API schemas
- PayPal client (mocked)
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import MagicMock, patch

import pytest

# Ensure the ai/ directory is on the path
sys.path.insert(0, str(Path(__file__).parents[2]))

from src.models.labels import (
    FEVEROUS_TO_APP,
    AppLabel,
    IDX_TO_APP,
    APP_TO_IDX,
    APP_LABEL_NAMES,
)
from src.models.input_format import EvidenceRecord, build_nli_input
from src.models.deterministic_validator import DeterministicValidator
from src.models.evidence_compiler import EvidenceCompiler, EventLog


# ===========================================================================
# Label conversion tests
# ===========================================================================

class TestLabelConversion:
    def test_supports_maps_to_supported(self):
        assert FEVEROUS_TO_APP["SUPPORTS"] == AppLabel.SUPPORTED

    def test_refutes_maps_to_contradicted(self):
        assert FEVEROUS_TO_APP["REFUTES"] == AppLabel.CONTRADICTED

    def test_nei_maps_to_insufficient(self):
        assert FEVEROUS_TO_APP["NOT ENOUGH INFO"] == AppLabel.INSUFFICIENT_EVIDENCE

    def test_all_three_labels_present(self):
        assert len(APP_LABEL_NAMES) == 3
        assert "SUPPORTED" in APP_LABEL_NAMES
        assert "CONTRADICTED" in APP_LABEL_NAMES
        assert "INSUFFICIENT_EVIDENCE" in APP_LABEL_NAMES

    def test_idx_roundtrip(self):
        for idx, label in IDX_TO_APP.items():
            assert APP_TO_IDX[label] == idx


# ===========================================================================
# Input formatter tests
# ===========================================================================

class TestInputFormatter:
    def test_single_evidence(self):
        ev = [EvidenceRecord("ev_001", "paypal_api", "2025-01-01T12:00:00Z", "Payment COMPLETED.")]
        result = build_nli_input("Payment was confirmed.", ev)
        assert "ev_001" in result.premise
        assert "Payment COMPLETED" in result.premise
        assert result.hypothesis == "Payment was confirmed."
        assert not result.truncated
        assert result.evidence_ids == ["ev_001"]

    def test_empty_evidence(self):
        result = build_nli_input("Some claim.", [])
        assert "[NO EVIDENCE PROVIDED]" in result.premise
        assert result.evidence_ids == []

    def test_truncation_warning(self):
        long_content = "A" * 5000
        ev = [
            EvidenceRecord("ev_001", "delivery", None, long_content),
            EvidenceRecord("ev_002", "delivery", None, "Short content."),
        ]
        result = build_nli_input("Some claim.", ev, max_chars=200)
        assert result.truncated
        assert result.truncation_warning is not None
        assert "ev_001" in result.evidence_ids  # first record included

    def test_empty_claim_raises(self):
        with pytest.raises(ValueError):
            build_nli_input("", [])

    def test_multiple_evidence_ids_preserved(self):
        ev = [
            EvidenceRecord(f"ev_{i:03d}", "api", None, f"Content {i}")
            for i in range(5)
        ]
        result = build_nli_input("Multi-evidence claim.", ev)
        for i in range(5):
            assert f"ev_{i:03d}" in result.evidence_ids


# ===========================================================================
# EvidenceBench generation tests
# ===========================================================================

class TestEvidenceBenchGeneration:
    @pytest.fixture(scope="class")
    def generated(self, tmp_path_factory):
        tmp = tmp_path_factory.mktemp("evb")
        from src.data.generate_evidencebench import generate
        report = generate(str(tmp), seed=42, target_count=500)
        return tmp, report

    def test_files_created(self, generated):
        tmp, report = generated
        for fname in ("train.jsonl", "validation.jsonl", "test.jsonl",
                      "challenge_test.jsonl", "manifest.json", "generation_report.json", "schema.json"):
            assert (tmp / fname).exists(), f"Missing {fname}"

    def test_no_validation_errors(self, generated):
        _, report = generated
        assert report["validation_errors"] == []

    def test_labels_valid(self, generated):
        tmp, _ = generated
        for split in ("train", "validation", "test", "challenge_test"):
            with open(tmp / f"{split}.jsonl") as f:
                for line in f:
                    row = json.loads(line)
                    assert row["label"] in ("SUPPORTED", "CONTRADICTED", "INSUFFICIENT_EVIDENCE")

    def test_group_split_no_family_overlap(self, generated):
        tmp, report = generated
        val_fams = set(report["val_families"])
        test_fams = set(report["test_families"])
        assert val_fams.isdisjoint(test_fams)

        def get_families(split):
            fams = set()
            with open(tmp / f"{split}.jsonl") as f:
                for line in f:
                    fams.add(json.loads(line)["scenario_family"])
            return fams

        train_fams = get_families("train")
        val_families = get_families("validation")
        test_families = get_families("test")
        assert train_fams.isdisjoint(val_families), "Train/val family overlap!"
        assert train_fams.isdisjoint(test_families), "Train/test family overlap!"

    def test_reproducibility(self, tmp_path):
        from src.data.generate_evidencebench import generate
        r1 = generate(str(tmp_path / "run1"), seed=99, target_count=100)
        r2 = generate(str(tmp_path / "run2"), seed=99, target_count=100)
        assert r1["total_main"] == r2["total_main"]

    def test_no_duplicate_ids(self, generated):
        tmp, _ = generated
        all_ids = []
        for split in ("train", "validation", "test"):
            with open(tmp / f"{split}.jsonl") as f:
                for line in f:
                    all_ids.append(json.loads(line)["example_id"])
        assert len(all_ids) == len(set(all_ids)), "Duplicate example IDs found!"

    def test_challenge_is_synthetic(self, generated):
        tmp, _ = generated
        with open(tmp / "challenge_test.jsonl") as f:
            for line in f:
                row = json.loads(line)
                assert row["is_synthetic"] is True


# ===========================================================================
# Deterministic validator tests
# ===========================================================================

class TestDeterministicValidator:
    def setup_method(self):
        self.v = DeterministicValidator()

    def _ev(self, eid, src, content, ts=None):
        return {"evidence_id": eid, "source_type": src, "timestamp": ts, "content": content}

    def test_capture_completed_supported(self):
        ev = [self._ev("cap_001", "paypal_api", "Capture cap_001 status=COMPLETED order=ord_123.")]
        result = self.v.check_capture_completed(ev, "ord_123")
        assert result.passed

    def test_capture_not_completed(self):
        ev = [self._ev("cap_001", "paypal_api", "Order status=CREATED order=ord_123.")]
        result = self.v.check_capture_completed(ev, "ord_123")
        assert not result.passed

    def test_delivery_recorded(self):
        ev = [self._ev("del_001", "delivery_service", "File test.zip delivery SUCCESS order=ord_123.")]
        result = self.v.check_delivery_recorded(ev)
        assert result.passed

    def test_no_delivery_record(self):
        ev = [self._ev("del_001", "delivery_service", "File test.zip delivery link sent.")]
        result = self.v.check_delivery_recorded(ev)
        assert not result.passed

    def test_order_id_consistent(self):
        ev = [self._ev("del_001", "delivery_service", "Delivered for order ord_123.")]
        result = self.v.check_order_id_consistent(ev, "ord_123")
        assert result.passed

    def test_order_id_mismatch(self):
        ev = [self._ev("del_001", "delivery_service", "Delivered for order ord_999.")]
        result = self.v.check_order_id_consistent(ev, "ord_123")
        assert not result.passed

    def test_conflicting_delivery_detected(self):
        ev = [
            self._ev("d1", "delivery_service", "File delivery SUCCESS order=ord_1."),
            self._ev("d2", "delivery_service", "File delivery FAILED order=ord_1."),
        ]
        result = self.v.check_no_conflicting_delivery(ev)
        assert not result.passed

    def test_impossible_event_order(self):
        ev = [
            self._ev("dl_1", "delivery_service", "Download completed.", "2025-01-01T08:00:00Z"),
            self._ev("pay_1", "paypal_api", "Payment captured completed.", "2025-01-01T10:00:00Z"),
        ]
        result = self.v.check_event_order(ev)
        assert not result.passed

    def test_empty_evidence_insufficient(self):
        label, checks = self.v.run_all("Some claim.", [])
        assert label == AppLabel.INSUFFICIENT_EVIDENCE

    def test_recipient_email_mismatch(self):
        ev = [
            self._ev("pay_1", "paypal_api", "Order payer=Alice email=alice@gmail.com."),
            self._ev("del_1", "delivery_service", "Delivered to Bob email=bob@yahoo.com."),
        ]
        result = self.v.check_recipient_match(ev, "Alice")
        assert not result.passed


# ===========================================================================
# Evidence compiler (hash chain) tests
# ===========================================================================

class TestEventLog:
    def test_append_and_verify(self):
        log = EventLog()
        log.append("ord_1", "paypal_api", "ev_1", "2025-01-01T00:00:00Z", {"action": "payment"})
        log.append("ord_1", "delivery", "ev_2", "2025-01-01T01:00:00Z", {"action": "delivery"})
        valid, errors = log.verify_chain()
        assert valid, f"Chain invalid: {errors}"

    def test_tamper_detection(self):
        log = EventLog()
        log.append("ord_1", "paypal_api", "ev_1", "2025-01-01T00:00:00Z", {})
        # Tamper with the event
        log._events[0]["payload"]["tampered"] = True
        valid, errors = log.verify_chain()
        assert not valid
        assert len(errors) > 0

    def test_broken_chain_link(self):
        log = EventLog()
        log.append("ord_1", "a", "ev_1", "2025-01-01T00:00:00Z", {})
        log.append("ord_1", "b", "ev_2", "2025-01-01T01:00:00Z", {})
        # Break the chain link
        log._events[1]["previous_hash"] = "fake_hash"
        valid, errors = log.verify_chain()
        assert not valid


class TestEvidenceCompiler:
    def test_supported_claim(self):
        compiler = EvidenceCompiler()
        ev = [
            {"evidence_id": "cap_1", "source_type": "paypal_api", "timestamp": "2025-01-01T10:00:00Z",
             "content": "Capture cap_1 status=COMPLETED order=ord_123."},
            {"evidence_id": "del_1", "source_type": "delivery_service", "timestamp": "2025-01-01T11:00:00Z",
             "content": "File test.zip delivery SUCCESS order=ord_123."},
        ]
        report = compiler.compile(
            claim="Payment was captured and file was delivered.",
            evidence=ev,
            transaction_reference="ord_123",
        )
        assert "compilation_id" in report
        assert report["human_review_required"] is True  # always required
        assert report["human_approved"] is False

    def test_empty_evidence_not_ready(self):
        compiler = EvidenceCompiler()
        report = compiler.compile("Some claim.", evidence=[])
        assert report["evidence_readiness"] == "NOT_READY"

    def test_contradicted_not_ready(self):
        compiler = EvidenceCompiler()
        ev = [
            {"evidence_id": "d1", "source_type": "delivery_service", "timestamp": None,
             "content": "File delivered for order ord_999."},  # wrong order
        ]
        report = compiler.compile(
            claim="File was delivered for order ord_123.",
            evidence=ev,
            transaction_reference="ord_123",
        )
        assert report["evidence_readiness"] == "NOT_READY"

    def test_structure_errors_detected(self):
        compiler = EvidenceCompiler()
        ev = [{"source_type": "api", "timestamp": None, "content": ""}]  # missing evidence_id, empty content
        report = compiler.compile("Some claim.", evidence=ev)
        assert len(report["structure_errors"]) > 0


# ===========================================================================
# API schema validation tests
# ===========================================================================

class TestAPISchemas:
    def test_predict_request_valid(self):
        from src.api.schemas import PredictRequest, EvidenceItem
        req = PredictRequest(
            claim="Payment was completed.",
            evidence=[EvidenceItem(
                evidence_id="ev_001",
                source_type="paypal_api",
                timestamp="2025-01-01T00:00:00Z",
                content="Payment COMPLETED order=ord_123.",
            )],
        )
        assert req.claim == "Payment was completed."

    def test_empty_content_raises(self):
        from pydantic import ValidationError
        from src.api.schemas import EvidenceItem
        with pytest.raises(ValidationError):
            EvidenceItem(evidence_id="ev_001", source_type="api", content="   ")

    def test_duplicate_evidence_ids_raises(self):
        from pydantic import ValidationError
        from src.api.schemas import PredictRequest, EvidenceItem
        with pytest.raises(ValidationError):
            PredictRequest(
                claim="Some claim.",
                evidence=[
                    EvidenceItem(evidence_id="ev_001", source_type="api", content="Content A"),
                    EvidenceItem(evidence_id="ev_001", source_type="api", content="Content B"),
                ],
            )

    def test_claim_min_length(self):
        from pydantic import ValidationError
        from src.api.schemas import PredictRequest
        with pytest.raises(ValidationError):
            PredictRequest(claim="Hi")  # too short


# ===========================================================================
# PayPal client tests (mocked — explicitly labelled MOCK)
# ===========================================================================

class TestPayPalClientMocked:
    """These tests use MOCK responses. NOT real PayPal API calls."""

    def test_unconfigured_raises(self):
        from src.integrations.paypal_client import PayPalClient, PayPalClientError
        client = PayPalClient(client_id="", client_secret="")
        with pytest.raises(PayPalClientError, match="environment variables"):
            client._get_access_token()

    def test_live_mode_requires_confirmation(self):
        from src.integrations.paypal_client import PayPalClient, PayPalClientError
        with pytest.raises(PayPalClientError, match="sandbox"):
            PayPalClient(
                client_id="fake_id",
                client_secret="fake_secret",
                mode="live",
            )

    @patch("src.integrations.paypal_client.requests.post")
    def test_token_mock(self, mock_post):
        """MOCK: simulates token response — not a real PayPal call."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"access_token": "mock_token", "expires_in": 3600}
        mock_post.return_value = mock_resp

        from src.integrations.paypal_client import PayPalClient
        client = PayPalClient(client_id="mock_id", client_secret="mock_secret", mode="sandbox")
        token = client._get_access_token()
        assert token == "mock_token"

    @patch("src.integrations.paypal_client.requests.get")
    @patch("src.integrations.paypal_client.requests.post")
    def test_dispute_403_raises_helpful_error(self, mock_post, mock_get):
        """MOCK: simulates a 403 from PayPal disputes API."""
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: {"access_token": "mock_tok", "expires_in": 3600},
        )
        mock_get.return_value = MagicMock(status_code=403)
        from src.integrations.paypal_client import PayPalClient, PayPalClientError
        client = PayPalClient(client_id="mock_id", client_secret="mock_secret")
        with pytest.raises(PayPalClientError, match="CUSTOMER_DISPUTE.READ"):
            client.list_disputes()


# ===========================================================================
# FEVEROUS label parsing tests (integer labels — actual FEVEROUS encoding)
# ===========================================================================

class TestFeverousParser:
    def test_int_supports_maps_to_supported(self):
        from src.data.parse_feverous import INT_TO_APP
        assert INT_TO_APP[0] == AppLabel.SUPPORTED

    def test_int_refutes_maps_to_contradicted(self):
        from src.data.parse_feverous import INT_TO_APP
        assert INT_TO_APP[1] == AppLabel.CONTRADICTED

    def test_int_nei_maps_to_insufficient(self):
        from src.data.parse_feverous import INT_TO_APP
        assert INT_TO_APP[2] == AppLabel.INSUFFICIENT_EVIDENCE

    def test_unknown_int_returns_none(self):
        from src.data.parse_feverous import INT_TO_APP
        assert INT_TO_APP.get(99) is None

    def test_context_text_extraction_basic(self):
        from src.data.parse_feverous import _extract_context_text
        evidence_list = [{"content": ["Page_cell_0_1_2"], "context": [["Some evidence text here."]]}]
        text = _extract_context_text(evidence_list)
        assert "Some evidence text" in text

    def test_context_text_skips_cell_refs(self):
        from src.data.parse_feverous import _extract_context_text
        evidence_list = [{"content": ["Page_cell_0_1_2"], "context": [["Page_cell_0_1_2", "Real text here."]]}]
        text = _extract_context_text(evidence_list)
        assert "Page_cell_0_1_2" not in text
        assert "Real text here." in text


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
