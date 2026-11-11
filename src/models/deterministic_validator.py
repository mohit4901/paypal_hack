"""
Deterministic baseline validator — Baseline A.

Rule-based evidence checks that do not use any ML model.
Transparent, unit-tested, and fast.
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from src.models.labels import AppLabel
from src.utils.logging_config import setup_logging

logger = setup_logging(name="deterministic_validator")


def _parse_ts(ts: Optional[str]) -> Optional[datetime]:
    if not ts:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S+00:00", "%Y-%m-%d"):
        try:
            return datetime.strptime(ts, fmt)
        except ValueError:
            continue
    return None


class CheckResult:
    def __init__(self, name: str, passed: bool, message: str):
        self.name = name
        self.passed = passed
        self.message = message

    def to_dict(self) -> Dict[str, Any]:
        return {"check": self.name, "passed": self.passed, "message": self.message}


class DeterministicValidator:
    """
    Run a series of transparent, code-based checks on a claim/evidence pair.
    Each check is independent and produces an explicit result.
    """

    def check_capture_completed(
        self,
        evidence: List[Dict[str, Any]],
        order_id: Optional[str] = None,
    ) -> CheckResult:
        """Check that at least one evidence record confirms a COMPLETED capture."""
        for ev in evidence:
            content = ev.get("content", "").upper()
            if "COMPLETED" in content and "CAPTURE" in content:
                if order_id is None or order_id in ev.get("content", ""):
                    return CheckResult(
                        "capture_completed", True,
                        "At least one record confirms a COMPLETED capture."
                    )
        return CheckResult(
            "capture_completed", False,
            "No record confirming a COMPLETED capture was found."
        )

    def check_delivery_recorded(
        self,
        evidence: List[Dict[str, Any]],
        file_name: Optional[str] = None,
    ) -> CheckResult:
        """Check that a delivery success event is present."""
        for ev in evidence:
            src = ev.get("source_type", "")
            content = ev.get("content", "")
            if "delivery" in src.lower() and (
                "SUCCESS" in content.upper() or "COMPLETED" in content.upper() or "DELIVERED" in content.upper()
            ):
                if file_name is None or file_name.lower() in content.lower():
                    return CheckResult(
                        "delivery_recorded", True,
                        "Delivery success event found."
                    )
        return CheckResult(
            "delivery_recorded", False,
            "No delivery success event found in evidence records."
        )

    def check_download_event(
        self,
        evidence: List[Dict[str, Any]],
    ) -> CheckResult:
        """Check that an explicit download event is present."""
        for ev in evidence:
            content = ev.get("content", "").lower()
            if "download" in content and ("complet" in content or "success" in content or "confirmed" in content):
                return CheckResult("download_event", True, "Download completion event found.")
        return CheckResult(
            "download_event", False,
            "No download completion event found. Delivery link sent ≠ download confirmed."
        )

    def check_provisioning_without_download(
        self,
        evidence: List[Dict[str, Any]],
    ) -> CheckResult:
        """
        Inspect evidence telemetry to determine whether records prove only account
        provisioning / zero-download state without any download or digital utilization confirmation.
        A keyword in the claim alone must never trigger a false insufficient override.
        """
        if self.check_download_event(evidence).passed:
            return CheckResult("provisioning_without_download", True, "Explicit download completion telemetry present.")

        positive_utilization_markers = (
            "downloaded",
            "bytes transferred",
            "bytes_transferred",
            "bytes downloaded",
            "issued pdf certificate",
            "issued certificate",
            "files fetched",
            "attended ",
            "streamed",
        )
        explicit_missing_markers = (
            "zero download",
            "no download",
            "0 download",
            "not downloaded",
            "downloads: 0",
            "download_count: 0",
            "download_count=0",
            "download count: 0",
            "without download",
        )
        provisioning_sources = {"course_platform", "email_delivery", "lms", "digital_provisioning"}
        provisioning_markers = (
            "access enrolled",
            "account provisioned",
            "portal account provisioned",
            "account created",
            "delivery link",
            "link sent",
            "email queued",
            "license queued",
        )

        has_positive_utilization = False
        has_explicit_missing_download = False
        has_provisioning_record = False

        for ev in evidence:
            src = ev.get("source_type", "").lower()
            content = ev.get("content", "").lower()
            if any(m in content for m in explicit_missing_markers):
                has_explicit_missing_download = True
            if any(m in content for m in positive_utilization_markers) or re.search(r"download_count[:=]\s*[1-9]\d*", content):
                has_positive_utilization = True
            if src in provisioning_sources or any(m in content for m in provisioning_markers):
                has_provisioning_record = True

        if has_explicit_missing_download:
            return CheckResult(
                "provisioning_without_download",
                False,
                "Evidence explicitly records zero or missing download activity.",
            )
        if has_provisioning_record and not has_positive_utilization:
            return CheckResult(
                "provisioning_without_download",
                False,
                "Evidence shows only portal/provisioning records with zero download or utilization activity.",
            )
        return CheckResult(
            "provisioning_without_download",
            True,
            "No provisioning-only or zero-download telemetry gap detected in evidence.",
        )

    def check_recipient_match(
        self,
        evidence: List[Dict[str, Any]],
        claimed_recipient: str,
    ) -> CheckResult:
        """
        Check that the recipient in payment AND delivery records matches.
        Name-only match is flagged as insufficient.
        """
        payment_evs = [e for e in evidence if "paypal" in e.get("source_type", "").lower()]
        delivery_evs = [e for e in evidence if "delivery" in e.get("source_type", "").lower()]

        if not payment_evs or not delivery_evs:
            return CheckResult(
                "recipient_match", False,
                "Cannot verify recipient: missing payment or delivery evidence."
            )

        pay_content = " ".join(e.get("content", "") for e in payment_evs)
        del_content = " ".join(e.get("content", "") for e in delivery_evs)

        # Extract emails
        pay_emails = set(re.findall(r"[\w\.\+\-]+@[\w\.\-]+\.\w{2,}", pay_content))
        del_emails = set(re.findall(r"[\w\.\+\-]+@[\w\.\-]+\.\w{2,}", del_content))

        if pay_emails and del_emails:
            if pay_emails & del_emails:
                return CheckResult(
                    "recipient_match", True,
                    f"Matching email found across payment and delivery records: {pay_emails & del_emails}"
                )
            else:
                return CheckResult(
                    "recipient_match", False,
                    f"Email mismatch: payment={pay_emails}, delivery={del_emails}"
                )

        # Fall back to name check only — flag as insufficient
        if claimed_recipient.lower() in pay_content.lower() and claimed_recipient.lower() in del_content.lower():
            return CheckResult(
                "recipient_match", False,
                "Name present in both records, but no email verification. Insufficient for identity confirmation."
            )

        return CheckResult(
            "recipient_match", False,
            f"Recipient '{claimed_recipient}' not confirmed across payment and delivery records."
        )

    def check_order_id_consistent(
        self,
        evidence: List[Dict[str, Any]],
        order_id: str,
    ) -> CheckResult:
        """Check that the claimed order ID appears in the relevant evidence records."""
        matching = [e for e in evidence if order_id in e.get("content", "")]
        if matching:
            return CheckResult(
                "order_id_consistent", True,
                f"Order ID '{order_id}' found in {len(matching)} evidence record(s)."
            )
        return CheckResult(
            "order_id_consistent", False,
            f"Order ID '{order_id}' not found in any evidence record."
        )

    def check_event_order(
        self,
        evidence: List[Dict[str, Any]],
    ) -> CheckResult:
        """
        Check for impossible event ordering: download before payment, etc.
        Returns failed if any impossible ordering is detected.
        """
        payment_times = []
        download_times = []

        for ev in evidence:
            ts = _parse_ts(ev.get("timestamp"))
            content = ev.get("content", "").lower()
            src = ev.get("source_type", "").lower()
            if ts:
                if "paypal" in src and ("complet" in content or "capture" in content):
                    payment_times.append(ts)
                if "delivery" in src and "download" in content:
                    download_times.append(ts)

        if payment_times and download_times:
            earliest_payment = min(payment_times)
            earliest_download = min(download_times)
            if earliest_download < earliest_payment:
                return CheckResult(
                    "event_order", False,
                    f"Impossible: download ({earliest_download}) precedes payment ({earliest_payment})."
                )

        return CheckResult("event_order", True, "No impossible event ordering detected.")

    def check_no_conflicting_delivery(
        self,
        evidence: List[Dict[str, Any]],
    ) -> CheckResult:
        """Detect conflicting delivery outcomes in the same order."""
        success = any(
            "delivery" in e.get("source_type", "").lower() and
            any(kw in e.get("content", "").upper() for kw in ("SUCCESS", "COMPLETED", "DELIVERED"))
            for e in evidence
        )
        failure = any(
            "delivery" in e.get("source_type", "").lower() and
            any(kw in e.get("content", "").upper() for kw in ("FAILED", "FAILURE", "NOT FOUND"))
            for e in evidence
        )
        if success and failure:
            return CheckResult(
                "no_conflicting_delivery", False,
                "Conflicting delivery events: both success and failure records found."
            )
        return CheckResult("no_conflicting_delivery", True, "No conflicting delivery events.")

    def run_all(
        self,
        claim: str,
        evidence: List[Dict[str, Any]],
        order_id: Optional[str] = None,
        claimed_recipient: Optional[str] = None,
    ) -> Tuple[AppLabel, List[Dict[str, Any]]]:
        """
        Run all applicable checks and derive a deterministic label.

        Returns (AppLabel, list_of_check_results).
        """
        checks = []
        checks.append(self.check_no_conflicting_delivery(evidence))
        checks.append(self.check_event_order(evidence))

        if not evidence:
            checks.append(CheckResult("evidence_present", False, "No evidence records provided."))
            return AppLabel.INSUFFICIENT_EVIDENCE, [c.to_dict() for c in checks]

        checks.append(CheckResult("evidence_present", True, f"{len(evidence)} record(s) provided."))

        # Source mismatch check: does evidence only reference other orders?
        mismatched_orders = set()
        if order_id:
            checks.append(self.check_order_id_consistent(evidence, order_id))
            for ev in evidence:
                content = ev.get("content", "")
                found_orders = re.findall(r"order[_\s:=]+([a-zA-Z0-9_]+)", content, re.I)
                for fo in found_orders:
                    if fo.lower() != order_id.lower():
                        mismatched_orders.add(fo)
        else:
            # Try to infer order_id from claim
            m = re.search(r"order[_\s:=]+([a-zA-Z0-9_]+)", claim, re.I)
            if m:
                inferred_order = m.group(1)
                checks.append(self.check_order_id_consistent(evidence, inferred_order))
                for ev in evidence:
                    content = ev.get("content", "")
                    found_orders = re.findall(r"order[_\s:=]+([a-zA-Z0-9_]+)", content, re.I)
                    for fo in found_orders:
                        if fo.lower() != inferred_order.lower():
                            mismatched_orders.add(fo)

        has_source_mismatch = False
        if (order_id or re.search(r"order[_\s:=]+([a-zA-Z0-9_]+)", claim, re.I)):
            target_order = order_id or re.search(r"order[_\s:=]+([a-zA-Z0-9_]+)", claim, re.I).group(1)
            matching_records = [e for e in evidence if target_order.lower() in e.get("content", "").lower()]
            if not matching_records and mismatched_orders:
                has_source_mismatch = True
                checks.append(CheckResult(
                    "source_mismatch_detected", True,
                    f"Evidence linkage failure: records belong to {list(mismatched_orders)}, not claimed order {target_order}."
                ))
            else:
                checks.append(CheckResult("source_mismatch_detected", False, "No source transaction mismatch detected."))

        if claimed_recipient:
            checks.append(self.check_recipient_match(evidence, claimed_recipient))

        # Derive label from check failures
        failed_checks = [c for c in checks if not c.passed]
        critical_failures = [
            c for c in failed_checks
            if c.name in ("no_conflicting_delivery", "event_order", "recipient_match")
        ]

        if critical_failures:
            # Direct contradiction (e.g., conflicting delivery, impossible time sequence)
            return AppLabel.CONTRADICTED, [c.to_dict() for c in checks]

        # Source mismatch or order missing is primarily INSUFFICIENT EVIDENCE (linkage failure), not direct refutation
        if has_source_mismatch:
            return AppLabel.INSUFFICIENT_EVIDENCE, [c.to_dict() for c in checks]

        order_missing_checks = [c for c in failed_checks if c.name == "order_id_consistent"]
        if order_missing_checks:
            return AppLabel.INSUFFICIENT_EVIDENCE, [c.to_dict() for c in checks]

        no_evidence_checks = [c for c in failed_checks if c.name == "evidence_present"]
        if no_evidence_checks:
            return AppLabel.INSUFFICIENT_EVIDENCE, [c.to_dict() for c in checks]

        # No critical failures, but check if we have positive confirmation
        has_positive = any(c.passed for c in checks if c.name in ("capture_completed", "delivery_recorded"))
        if has_positive:
            return AppLabel.SUPPORTED, [c.to_dict() for c in checks]

        return AppLabel.INSUFFICIENT_EVIDENCE, [c.to_dict() for c in checks]

