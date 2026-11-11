"""
EvidenceBench dataset generator.

Generates ~10 000 labelled claim/evidence examples across 25 scenario families
for PayPal digital-goods dispute evidence verification.

Usage:
    python -m src.data.generate_evidencebench \
        --output-dir data/processed/evidencebench \
        --seed 42 \
        --target-count 10000

Label-generation logic is fully deterministic: given a seed, the output
is identical on every run.  Ground-truth labels are derived from
explicit rule-based logic, NOT from model predictions.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import re
from copy import deepcopy
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

@dataclass
class EvidenceItem:
    evidence_id: str
    source_type: str
    timestamp: Optional[str]
    content: str


@dataclass
class Example:
    example_id: str
    scenario_family: str
    claim: str
    evidence: List[Dict[str, Any]]
    label: str  # SUPPORTED | CONTRADICTED | INSUFFICIENT_EVIDENCE
    label_rationale: str
    is_synthetic: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

LABELS = ["SUPPORTED", "CONTRADICTED", "INSUFFICIENT_EVIDENCE"]


def _ts(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _ev(eid: str, stype: str, ts: Optional[datetime], content: str) -> Dict[str, Any]:
    return {
        "evidence_id": eid,
        "source_type": stype,
        "timestamp": _ts(ts) if ts else None,
        "content": content,
    }


def _id(rng: random.Random, prefix: str = "ord") -> str:
    return f"{prefix}_{rng.randint(100000, 999999)}"


def _amount(rng: random.Random) -> Tuple[str, str]:
    amt = round(rng.uniform(5.0, 999.99), 2)
    cur = rng.choice(["USD", "EUR", "GBP", "CAD", "AUD"])
    return f"{amt:.2f}", cur


def _name(rng: random.Random) -> str:
    first = rng.choice(["Alice", "Bob", "Carol", "Dave", "Eve", "Frank", "Grace", "Hank",
                         "Iris", "Jack", "Karen", "Liam", "Maya", "Nora", "Owen"])
    last = rng.choice(["Smith", "Jones", "Patel", "Garcia", "Kim", "Nguyen", "Brown",
                        "Lee", "Davis", "Miller", "Wilson", "Moore"])
    return f"{first} {last}"


def _email(name: str, rng: random.Random) -> str:
    domain = rng.choice(["gmail.com", "yahoo.com", "outlook.com", "proton.me"])
    local = name.lower().replace(" ", ".") + str(rng.randint(1, 99))
    return f"{local}@{domain}"


def _file(rng: random.Random) -> str:
    names = ["ProTools_Plugin", "DesignTemplate", "CodeSnippetPack", "EbookBundle",
              "WebinarRecording", "SoftwareLicense", "PhotoPreset", "MusicSample",
              "VideoAsset", "DatasetPro"]
    return f"{rng.choice(names)}_v{rng.randint(1,5)}.{rng.choice(['zip','pdf','mp4','exe','dmg'])}"


def _base_dt(rng: random.Random) -> datetime:
    base = datetime(2025, 1, 1, tzinfo=timezone.utc)
    return base + timedelta(days=rng.randint(0, 360), hours=rng.randint(0, 23))


# ---------------------------------------------------------------------------
# Scenario generators — each returns list[Example]
# ---------------------------------------------------------------------------

class ScenarioGenerator:
    """Base class. Subclasses implement `generate(rng, count) -> list[Example]`."""

    family: str = "base"

    def __init__(self):
        self._counter = 0

    def _next_id(self) -> str:
        self._counter += 1
        return f"evb_{self._counter:07d}"

    def generate(self, rng: random.Random, count: int) -> List[Example]:
        raise NotImplementedError


# EvidenceBench v1.1 Generator with reconciled semantics
class PaymentCapturedVsCreated(ScenarioGenerator):
    family = "payment_captured_vs_created"

    def generate(self, rng, count):
        examples = []
        for _ in range(count):
            order_id = _id(rng, "order")
            cap_id = _id(rng, "cap")
            dt = _base_dt(rng)
            amt, cur = _amount(rng)
            variant = rng.choice(["captured", "created", "pending"])

            claim = f"PayPal confirmed the payment capture for order {order_id}."

            if variant == "captured":
                ev = [_ev(cap_id, "paypal_api", dt,
                          f"Capture {cap_id} status=COMPLETED amount={amt} {cur} order={order_id}.")]
                label = "SUPPORTED"
                rationale = "Capture event shows COMPLETED status matching the claimed order."
            elif variant == "created":
                ev = [_ev(cap_id, "paypal_api", dt,
                          f"Order {order_id} status=CREATED amount={amt} {cur}. No capture recorded.")]
                label = "CONTRADICTED"
                rationale = "Only an ORDER CREATED event exists; no capture confirmation is present."
            else:
                ev = [_ev(cap_id, "paypal_api", dt,
                          f"Capture {cap_id} status=PENDING amount={amt} {cur} order={order_id}.")]
                label = "INSUFFICIENT_EVIDENCE"
                rationale = "Capture status is PENDING (in progress); payment capture confirmation is not yet established."

            examples.append(Example(
                example_id=self._next_id(),
                scenario_family=self.family,
                claim=claim,
                evidence=ev,
                label=label,
                label_rationale=rationale,
            ))
        return examples


class LicenceIssuedVsAccessed(ScenarioGenerator):
    family = "licence_issued_vs_accessed"

    def generate(self, rng, count):
        examples = []
        for _ in range(count):
            order_id = _id(rng, "order")
            lic_id = _id(rng, "lic")
            buyer = _name(rng)
            dt = _base_dt(rng)
            variant = rng.choice(["accessed", "issued_only", "no_record"])
            fname = _file(rng)

            claim = f"The customer accessed the software licence for {fname}."

            if variant == "accessed":
                ev = [
                    _ev(lic_id, "licence_server", dt,
                        f"Licence {lic_id} issued for {fname} to {buyer} order={order_id}."),
                    _ev(_id(rng, "acc"), "licence_server", dt + timedelta(hours=2),
                        f"Licence {lic_id} activated by {buyer} at {_ts(dt + timedelta(hours=2))}."),
                ]
                label = "SUPPORTED"
                rationale = "Licence issued and activation event recorded for the same buyer."
            elif variant == "issued_only":
                ev = [_ev(lic_id, "licence_server", dt,
                           f"Licence {lic_id} issued for {fname} to {buyer} order={order_id}. No activation logged.")]
                label = "INSUFFICIENT_EVIDENCE"
                rationale = "Licence was issued but no access/activation event is present."
            else:
                ev = []
                label = "INSUFFICIENT_EVIDENCE"
                rationale = "No licence or access records found."

            examples.append(Example(
                example_id=self._next_id(),
                scenario_family=self.family,
                claim=claim,
                evidence=ev,
                label=label,
                label_rationale=rationale,
            ))
        return examples


class FileSentVsDownloaded(ScenarioGenerator):
    family = "file_sent_vs_downloaded"

    def generate(self, rng, count):
        examples = []
        for _ in range(count):
            order_id = _id(rng, "order")
            fname = _file(rng)
            buyer = _name(rng)
            dt = _base_dt(rng)
            variant = rng.choice(["downloaded", "sent_only", "no_record"])

            claim = f"The buyer downloaded the digital file {fname}."

            if variant == "downloaded":
                ev = [
                    _ev(_id(rng, "dl"), "delivery_service", dt + timedelta(minutes=10),
                        f"File {fname} download completed by {buyer} order={order_id}."),
                ]
                label = "SUPPORTED"
                rationale = "Download completion event recorded for the buyer."
            elif variant == "sent_only":
                ev = [_ev(_id(rng, "snd"), "delivery_service", dt,
                           f"File {fname} delivery link sent to {buyer} order={order_id}.")]
                label = "INSUFFICIENT_EVIDENCE"
                rationale = "A delivery link was sent, but no download event is recorded."
            else:
                ev = []
                label = "INSUFFICIENT_EVIDENCE"
                rationale = "No delivery or download records available."

            examples.append(Example(
                example_id=self._next_id(),
                scenario_family=self.family,
                claim=claim,
                evidence=ev,
                label=label,
                label_rationale=rationale,
            ))
        return examples


class DeliveryTimestampMismatch(ScenarioGenerator):
    family = "delivery_timestamp_mismatch"

    def generate(self, rng, count):
        examples = []
        for _ in range(count):
            order_id = _id(rng, "order")
            fname = _file(rng)
            actual_dt = _base_dt(rng)
            offset_days = rng.choice([-2, -1, 1, 2])
            claimed_dt = actual_dt + timedelta(days=offset_days)
            variant = rng.choice(["wrong_date", "correct_date", "missing"])

            claimed_date_str = claimed_dt.strftime("%B %-d")
            actual_date_str = actual_dt.strftime("%B %-d")

            claim = f"The digital file {fname} was delivered on {claimed_date_str}."

            if variant == "wrong_date":
                ev = [_ev(_id(rng, "del"), "delivery_service", actual_dt,
                           f"File {fname} delivered for order {order_id} at {_ts(actual_dt)}.")]
                label = "CONTRADICTED"
                rationale = (
                    f"Delivery record shows {actual_date_str}, not {claimed_date_str}."
                )
            elif variant == "correct_date":
                ev = [_ev(_id(rng, "del"), "delivery_service", claimed_dt,
                           f"File {fname} delivered for order {order_id} at {_ts(claimed_dt)}.")]
                label = "SUPPORTED"
                rationale = "Delivery record date matches the claimed date."
            else:
                ev = []
                label = "INSUFFICIENT_EVIDENCE"
                rationale = "No delivery record found to verify the claimed date."

            examples.append(Example(
                example_id=self._next_id(),
                scenario_family=self.family,
                claim=claim,
                evidence=ev,
                label=label,
                label_rationale=rationale,
            ))
        return examples


class RecipientMismatch(ScenarioGenerator):
    family = "recipient_mismatch"

    def generate(self, rng, count):
        examples = []
        for _ in range(count):
            order_id = _id(rng, "order")
            fname = _file(rng)
            buyer = _name(rng)
            other_person = _name(rng)
            while other_person == buyer:
                other_person = _name(rng)
            dt = _base_dt(rng)
            variant = rng.choice(["correct_recipient", "wrong_recipient", "name_only_match"])

            claim = f"The file {fname} was delivered to the buyer {buyer} associated with order {order_id}."

            if variant == "correct_recipient":
                buyer_email = _email(buyer, rng)
                ev = [
                    _ev(_id(rng, "pay"), "paypal_api", dt,
                        f"Payment for order {order_id} payer={buyer} email={buyer_email}."),
                    _ev(_id(rng, "del"), "delivery_service", dt + timedelta(hours=1),
                        f"File {fname} delivered to {buyer} email={buyer_email} order={order_id}."),
                ]
                label = "SUPPORTED"
                rationale = "Payment payer and delivery recipient match by name and email."
            elif variant == "wrong_recipient":
                other_email = _email(other_person, rng)
                buyer_email = _email(buyer, rng)
                ev = [
                    _ev(_id(rng, "pay"), "paypal_api", dt,
                        f"Payment for order {order_id} payer={buyer} email={buyer_email}."),
                    _ev(_id(rng, "del"), "delivery_service", dt + timedelta(hours=1),
                        f"File {fname} delivered to {other_person} email={other_email} order={order_id}."),
                ]
                label = "CONTRADICTED"
                rationale = "Delivery recipient differs from the payment payer by both name and email."
            else:
                # name matches but emails differ — insufficient to establish identity
                shared_name = buyer
                ev = [
                    _ev(_id(rng, "pay"), "paypal_api", dt,
                        f"Payment for order {order_id} payer={shared_name} email={_email(shared_name, rng)}."),
                    _ev(_id(rng, "del"), "delivery_service", dt + timedelta(hours=1),
                        f"File {fname} delivered to {shared_name} email={_email(shared_name, rng)} order={order_id}."),
                ]
                label = "INSUFFICIENT_EVIDENCE"
                rationale = "Name matches but email addresses differ; identity not definitively established."

            examples.append(Example(
                example_id=self._next_id(),
                scenario_family=self.family,
                claim=claim,
                evidence=ev,
                label=label,
                label_rationale=rationale,
            ))
        return examples


class OrderIdMismatch(ScenarioGenerator):
    family = "order_id_mismatch"

    def generate(self, rng, count):
        examples = []
        for _ in range(count):
            order_id = _id(rng, "order")
            wrong_order_id = _id(rng, "order")
            while wrong_order_id == order_id:
                wrong_order_id = _id(rng, "order")
            fname = _file(rng)
            dt = _base_dt(rng)
            variant = rng.choice(["correct_order", "wrong_order"])

            claim = f"The delivery record for {fname} is associated with order {order_id}."

            if variant == "correct_order":
                ev = [_ev(_id(rng, "del"), "delivery_service", dt,
                           f"File {fname} delivered for order {order_id}.")]
                label = "SUPPORTED"
                rationale = "Delivery record order ID matches the claimed order ID."
            else:
                ev = [_ev(_id(rng, "del"), "delivery_service", dt,
                           f"File {fname} delivered for order {wrong_order_id}.")]
                label = "CONTRADICTED"
                rationale = f"Delivery record references order {wrong_order_id}, not {order_id}."

            examples.append(Example(
                example_id=self._next_id(),
                scenario_family=self.family,
                claim=claim,
                evidence=ev,
                label=label,
                label_rationale=rationale,
            ))
        return examples


class CourseAccessGrantedVsAccessed(ScenarioGenerator):
    family = "course_access_granted_vs_accessed"

    def generate(self, rng, count):
        examples = []
        course_names = ["Python Mastery", "Design Fundamentals", "ML Bootcamp",
                        "SEO Essentials", "Video Editing Pro", "Web Security 101"]
        for _ in range(count):
            buyer = _name(rng)
            course = rng.choice(course_names)
            dt = _base_dt(rng)
            variant = rng.choice(["enrolled_and_accessed", "enrolled_only", "no_record"])

            claim = f"The buyer {buyer} accessed the online course '{course}'."

            if variant == "enrolled_and_accessed":
                ev = [
                    _ev(_id(rng, "enr"), "lms", dt,
                        f"Enrollment confirmed: {buyer} → '{course}'."),
                    _ev(_id(rng, "acc"), "lms", dt + timedelta(days=1),
                        f"Course session started: {buyer} accessed '{course}' for 42 minutes."),
                ]
                label = "SUPPORTED"
                rationale = "LMS records both enrollment and a course access session."
            elif variant == "enrolled_only":
                ev = [_ev(_id(rng, "enr"), "lms", dt,
                           f"Enrollment confirmed: {buyer} → '{course}'. No session events recorded.")]
                label = "INSUFFICIENT_EVIDENCE"
                rationale = "Enrollment exists but no course access/session event is recorded."
            else:
                ev = []
                label = "INSUFFICIENT_EVIDENCE"
                rationale = "No LMS enrollment or access records found."

            examples.append(Example(
                example_id=self._next_id(),
                scenario_family=self.family,
                claim=claim,
                evidence=ev,
                label=label,
                label_rationale=rationale,
            ))
        return examples


class AssetVersionMismatch(ScenarioGenerator):
    family = "asset_version_mismatch"

    def generate(self, rng, count):
        examples = []
        for _ in range(count):
            base_name = rng.choice(["DesignKit", "CodeBundle", "MediaPack", "Plugin"])
            claimed_ver = rng.randint(2, 6)
            actual_ver = rng.choice([v for v in range(1, 7) if v != claimed_ver])
            dt = _base_dt(rng)
            order_id = _id(rng, "order")
            variant = rng.choice(["correct_version", "wrong_version"])

            if variant == "correct_version":
                fname = f"{base_name}_v{claimed_ver}.zip"
                ev = [_ev(_id(rng, "del"), "delivery_service", dt,
                           f"Delivered {fname} for order {order_id}.")]
                label = "SUPPORTED"
                rationale = "Delivered file version matches the claimed version."
                claim = f"Version {claimed_ver} of {base_name} was delivered for order {order_id}."
            else:
                fname = f"{base_name}_v{actual_ver}.zip"
                ev = [_ev(_id(rng, "del"), "delivery_service", dt,
                           f"Delivered {fname} for order {order_id}.")]
                label = "CONTRADICTED"
                rationale = f"Delivery record shows v{actual_ver}, not v{claimed_ver}."
                claim = f"Version {claimed_ver} of {base_name} was delivered for order {order_id}."

            examples.append(Example(
                example_id=self._next_id(),
                scenario_family=self.family,
                claim=claim,
                evidence=ev,
                label=label,
                label_rationale=rationale,
            ))
        return examples


class ImpossibleEventOrder(ScenarioGenerator):
    family = "impossible_event_order"

    def generate(self, rng, count):
        examples = []
        for _ in range(count):
            order_id = _id(rng, "order")
            fname = _file(rng)
            dt = _base_dt(rng)
            # Impossible: download before payment
            pay_dt = dt + timedelta(hours=3)
            dl_dt = dt  # earlier than payment

            variant = rng.choice(["impossible", "valid_order"])
            claim = f"The buyer downloaded {fname} after payment was confirmed for order {order_id}."

            if variant == "impossible":
                ev = [
                    _ev(_id(rng, "dl"), "delivery_service", dl_dt,
                        f"Download of {fname} completed at {_ts(dl_dt)}."),
                    _ev(_id(rng, "pay"), "paypal_api", pay_dt,
                        f"Payment COMPLETED for order {order_id} at {_ts(pay_dt)}."),
                ]
                label = "CONTRADICTED"
                rationale = "Download timestamp precedes payment timestamp — impossible sequence."
            else:
                ev = [
                    _ev(_id(rng, "pay"), "paypal_api", pay_dt - timedelta(hours=3),
                        f"Payment COMPLETED for order {order_id} at {_ts(pay_dt - timedelta(hours=3))}."),
                    _ev(_id(rng, "dl"), "delivery_service", pay_dt,
                        f"Download of {fname} completed at {_ts(pay_dt)}."),
                ]
                label = "SUPPORTED"
                rationale = "Download timestamp follows payment confirmation — valid sequence."

            examples.append(Example(
                example_id=self._next_id(),
                scenario_family=self.family,
                claim=claim,
                evidence=ev,
                label=label,
                label_rationale=rationale,
            ))
        return examples


class MissingEvidence(ScenarioGenerator):
    family = "missing_evidence"

    def generate(self, rng, count):
        examples = []
        for _ in range(count):
            fname = _file(rng)
            order_id = _id(rng, "order")
            claim_type = rng.choice(["delivery", "payment", "access"])

            if claim_type == "delivery":
                claim = f"The file {fname} was delivered for order {order_id}."
            elif claim_type == "payment":
                claim = f"Payment was captured for order {order_id}."
            else:
                claim = f"The buyer accessed the product associated with order {order_id}."

            examples.append(Example(
                example_id=self._next_id(),
                scenario_family=self.family,
                claim=claim,
                evidence=[],
                label="INSUFFICIENT_EVIDENCE",
                label_rationale="No evidence records provided.",
            ))
        return examples


class ConflictingDeliveryEvents(ScenarioGenerator):
    family = "conflicting_delivery_events"

    def generate(self, rng, count):
        examples = []
        for _ in range(count):
            order_id = _id(rng, "order")
            fname = _file(rng)
            dt = _base_dt(rng)

            ev = [
                _ev(_id(rng, "del1"), "delivery_service", dt,
                    f"File {fname} delivery SUCCESSFUL order={order_id}."),
                _ev(_id(rng, "del2"), "delivery_service", dt + timedelta(minutes=5),
                    f"File {fname} delivery FAILED (recipient not found) order={order_id}."),
            ]
            claim = f"The file {fname} was successfully delivered for order {order_id}."
            examples.append(Example(
                example_id=self._next_id(),
                scenario_family=self.family,
                claim=claim,
                evidence=ev,
                label="CONTRADICTED",
                label_rationale="Conflicting events: one records success, another records failure.",
            ))
        return examples


class MultipleRecordsSupporting(ScenarioGenerator):
    family = "multiple_records_supporting"

    def generate(self, rng, count):
        examples = []
        for _ in range(count):
            order_id = _id(rng, "order")
            fname = _file(rng)
            buyer = _name(rng)
            buyer_email = _email(buyer, rng)
            dt = _base_dt(rng)
            amt, cur = _amount(rng)

            ev = [
                _ev(_id(rng, "pay"), "paypal_api", dt,
                    f"Payment COMPLETED order={order_id} payer={buyer} email={buyer_email} amount={amt} {cur}."),
                _ev(_id(rng, "del"), "delivery_service", dt + timedelta(hours=1),
                    f"File {fname} delivered to {buyer} email={buyer_email} order={order_id}."),
                _ev(_id(rng, "dl"), "delivery_service", dt + timedelta(hours=2),
                    f"Download CONFIRMED {fname} by {buyer} order={order_id}."),
            ]
            claim = f"The buyer {buyer} paid and downloaded {fname} for order {order_id}."
            examples.append(Example(
                example_id=self._next_id(),
                scenario_family=self.family,
                claim=claim,
                evidence=ev,
                label="SUPPORTED",
                label_rationale="Payment, delivery, and download records all align with the claim.",
            ))
        return examples


class BroaderThanEvidence(ScenarioGenerator):
    family = "claim_broader_than_evidence"

    def generate(self, rng, count):
        examples = []
        for _ in range(count):
            order_id = _id(rng, "order")
            fname = _file(rng)
            buyer = _name(rng)
            dt = _base_dt(rng)

            ev = [_ev(_id(rng, "del"), "delivery_service", dt,
                       f"File {fname} delivery link sent to {buyer} order={order_id}.")]
            # Claim says "downloaded and used" — evidence only shows delivery link sent
            claim = f"The buyer downloaded and actively used {fname} for order {order_id}."
            examples.append(Example(
                example_id=self._next_id(),
                scenario_family=self.family,
                claim=claim,
                evidence=ev,
                label="INSUFFICIENT_EVIDENCE",
                label_rationale=(
                    "Delivery link sent but no download or usage events recorded; "
                    "claim is broader than the available evidence."
                ),
            ))
        return examples


class UnsupportedClaimDetails(ScenarioGenerator):
    family = "unsupported_claim_details"

    def generate(self, rng, count):
        examples = []
        for _ in range(count):
            order_id = _id(rng, "order")
            fname = _file(rng)
            buyer = _name(rng)
            dt = _base_dt(rng)
            amt, cur = _amount(rng)
            wrong_amt = str(round(float(amt) + rng.uniform(5, 50), 2))

            ev = [_ev(_id(rng, "pay"), "paypal_api", dt,
                       f"Payment COMPLETED order={order_id} payer={buyer} amount={amt} {cur}.")]
            # Claim states the wrong amount
            claim = f"A payment of {wrong_amt} {cur} was confirmed for order {order_id}."
            examples.append(Example(
                example_id=self._next_id(),
                scenario_family=self.family,
                claim=claim,
                evidence=ev,
                label="CONTRADICTED",
                label_rationale=f"Payment record shows {amt} {cur}, not {wrong_amt} {cur}.",
            ))
        return examples


class CurrencyAmountMismatch(ScenarioGenerator):
    family = "currency_amount_mismatch"

    def generate(self, rng, count):
        examples = []
        for _ in range(count):
            order_id = _id(rng, "order")
            amt, cur = _amount(rng)
            wrong_cur = rng.choice([c for c in ["USD", "EUR", "GBP", "CAD", "AUD"] if c != cur])
            dt = _base_dt(rng)
            variant = rng.choice(["correct", "wrong_currency", "wrong_amount"])

            if variant == "correct":
                ev = [_ev(_id(rng, "pay"), "paypal_api", dt,
                           f"Payment COMPLETED order={order_id} amount={amt} {cur}.")]
                claim = f"A payment of {amt} {cur} was captured for order {order_id}."
                label = "SUPPORTED"
                rationale = "Amount and currency match the payment record."
            elif variant == "wrong_currency":
                ev = [_ev(_id(rng, "pay"), "paypal_api", dt,
                           f"Payment COMPLETED order={order_id} amount={amt} {cur}.")]
                claim = f"A payment of {amt} {wrong_cur} was captured for order {order_id}."
                label = "CONTRADICTED"
                rationale = f"Currency in claim is {wrong_cur}; record shows {cur}."
            else:
                wrong_amt = str(round(float(amt) * rng.uniform(1.1, 2.0), 2))
                ev = [_ev(_id(rng, "pay"), "paypal_api", dt,
                           f"Payment COMPLETED order={order_id} amount={amt} {cur}.")]
                claim = f"A payment of {wrong_amt} {cur} was captured for order {order_id}."
                label = "CONTRADICTED"
                rationale = f"Amount in claim is {wrong_amt}; record shows {amt}."

            examples.append(Example(
                example_id=self._next_id(),
                scenario_family=self.family,
                claim=claim,
                evidence=ev,
                label=label,
                label_rationale=rationale,
            ))
        return examples


class RefundClaimMissingConfirmation(ScenarioGenerator):
    family = "refund_claim_missing_confirmation"

    def generate(self, rng, count):
        examples = []
        for _ in range(count):
            order_id = _id(rng, "order")
            amt, cur = _amount(rng)
            dt = _base_dt(rng)
            variant = rng.choice(["refund_confirmed", "refund_initiated", "no_refund"])

            claim = f"A refund of {amt} {cur} was issued for order {order_id}."

            if variant == "refund_confirmed":
                ev = [_ev(_id(rng, "ref"), "paypal_api", dt,
                           f"Refund COMPLETED order={order_id} amount={amt} {cur}.")]
                label = "SUPPORTED"
                rationale = "Refund completion record matches the claimed amount and order."
            elif variant == "refund_initiated":
                ev = [_ev(_id(rng, "ref"), "paypal_api", dt,
                           f"Refund PENDING order={order_id} amount={amt} {cur}.")]
                label = "INSUFFICIENT_EVIDENCE"
                rationale = "Refund initiated but not yet confirmed as completed."
            else:
                ev = [_ev(_id(rng, "pay"), "paypal_api", dt - timedelta(days=5),
                           f"Payment COMPLETED order={order_id} amount={amt} {cur}.")]
                label = "INSUFFICIENT_EVIDENCE"
                rationale = "Only payment record exists; no refund event found."

            examples.append(Example(
                example_id=self._next_id(),
                scenario_family=self.family,
                claim=claim,
                evidence=ev,
                label=label,
                label_rationale=rationale,
            ))
        return examples


class UnrelatedTransaction(ScenarioGenerator):
    family = "evidence_from_unrelated_transaction"

    def generate(self, rng, count):
        examples = []
        for _ in range(count):
            order_id = _id(rng, "order")
            other_order_id = _id(rng, "order")
            while other_order_id == order_id:
                other_order_id = _id(rng, "order")
            fname = _file(rng)
            dt = _base_dt(rng)

            ev = [_ev(_id(rng, "del"), "delivery_service", dt,
                       f"File {fname} delivered for order {other_order_id}.")]
            claim = f"The file {fname} was delivered for order {order_id}."
            examples.append(Example(
                example_id=self._next_id(),
                scenario_family=self.family,
                claim=claim,
                evidence=ev,
                label="CONTRADICTED",
                label_rationale=f"Delivery record belongs to order {other_order_id}, not {order_id}.",
            ))
        return examples


class TamperedEventHistory(ScenarioGenerator):
    family = "tampered_event_history"

    def generate(self, rng, count):
        examples = []
        for _ in range(count):
            order_id = _id(rng, "order")
            fname = _file(rng)
            dt = _base_dt(rng)

            ev = [
                _ev(_id(rng, "del1"), "delivery_service", dt,
                    f"File {fname} delivered for order {order_id} status=SUCCESS."),
                _ev(_id(rng, "del2"), "delivery_service", dt,
                    f"File {fname} delivered for order {order_id} status=FAILED. "
                    f"[NOTE: timestamp matches prior success record — possible duplicate or tamper]."),
            ]
            claim = f"The file {fname} was successfully delivered for order {order_id}."
            examples.append(Example(
                example_id=self._next_id(),
                scenario_family=self.family,
                claim=claim,
                evidence=ev,
                label="INSUFFICIENT_EVIDENCE",
                label_rationale=(
                    "Internally inconsistent event history: duplicate timestamp with conflicting status."
                ),
            ))
        return examples


class ConflictingStatusSnapshots(ScenarioGenerator):
    family = "conflicting_status_snapshots"

    def generate(self, rng, count):
        examples = []
        for _ in range(count):
            order_id = _id(rng, "order")
            dt = _base_dt(rng)
            snapshot_a = rng.choice(["COMPLETED", "APPROVED"])
            snapshot_b = rng.choice(["DECLINED", "VOIDED", "PENDING"])

            ev = [
                _ev(_id(rng, "ss1"), "paypal_api", dt,
                    f"Order {order_id} status snapshot: {snapshot_a}."),
                _ev(_id(rng, "ss2"), "paypal_api", dt + timedelta(seconds=30),
                    f"Order {order_id} status snapshot: {snapshot_b}."),
            ]
            claim = f"Payment for order {order_id} was completed."
            examples.append(Example(
                example_id=self._next_id(),
                scenario_family=self.family,
                claim=claim,
                evidence=ev,
                label="INSUFFICIENT_EVIDENCE",
                label_rationale=(
                    f"Conflicting status snapshots ({snapshot_a} vs {snapshot_b}); "
                    "final state cannot be determined from available records."
                ),
            ))
        return examples


class PlausibleButUnestablished(ScenarioGenerator):
    family = "plausible_but_unestablished"

    def generate(self, rng, count):
        examples = []
        for _ in range(count):
            buyer = _name(rng)
            fname = _file(rng)
            dt = _base_dt(rng)
            order_id = _id(rng, "order")

            ev = [_ev(_id(rng, "pay"), "paypal_api", dt,
                       f"Payment COMPLETED order={order_id} payer={buyer}.")]
            claim = f"The buyer {buyer} is satisfied with the product {fname}."
            examples.append(Example(
                example_id=self._next_id(),
                scenario_family=self.family,
                claim=claim,
                evidence=ev,
                label="INSUFFICIENT_EVIDENCE",
                label_rationale=(
                    "Payment record confirms transaction but cannot establish buyer satisfaction."
                ),
            ))
        return examples


class FullySupported(ScenarioGenerator):
    family = "fully_supported_claim"

    def generate(self, rng, count):
        examples = []
        for _ in range(count):
            order_id = _id(rng, "order")
            fname = _file(rng)
            buyer = _name(rng)
            buyer_email = _email(buyer, rng)
            dt = _base_dt(rng)
            amt, cur = _amount(rng)

            ev = [
                _ev(_id(rng, "pay"), "paypal_api", dt,
                    f"Payment COMPLETED order={order_id} payer={buyer} email={buyer_email} amount={amt} {cur}."),
                _ev(_id(rng, "del"), "delivery_service", dt + timedelta(minutes=30),
                    f"File {fname} delivered to {buyer} email={buyer_email} order={order_id} status=SUCCESS."),
            ]
            claim = (
                f"A payment of {amt} {cur} was captured and the file {fname} "
                f"was delivered to {buyer} for order {order_id}."
            )
            examples.append(Example(
                example_id=self._next_id(),
                scenario_family=self.family,
                claim=claim,
                evidence=ev,
                label="SUPPORTED",
                label_rationale="Payment and delivery records fully align with the claim.",
            ))
        return examples


class MultipleConflictingRecords(ScenarioGenerator):
    family = "multiple_conflicting_records"

    def generate(self, rng, count):
        examples = []
        for _ in range(count):
            order_id = _id(rng, "order")
            fname = _file(rng)
            buyer = _name(rng)
            other_buyer = _name(rng)
            while other_buyer == buyer:
                other_buyer = _name(rng)
            dt = _base_dt(rng)

            ev = [
                _ev(_id(rng, "pay"), "paypal_api", dt,
                    f"Payment COMPLETED order={order_id} payer={buyer}."),
                _ev(_id(rng, "del"), "delivery_service", dt + timedelta(hours=1),
                    f"File {fname} delivered to {other_buyer} order={order_id}."),
            ]
            claim = f"The file {fname} was delivered to the paying buyer {buyer} for order {order_id}."
            examples.append(Example(
                example_id=self._next_id(),
                scenario_family=self.family,
                claim=claim,
                evidence=ev,
                label="CONTRADICTED",
                label_rationale=f"Payment is from {buyer} but delivery is to {other_buyer}.",
            ))
        return examples


class IncompleteRecords(ScenarioGenerator):
    family = "incomplete_records_unknown_verdict"

    def generate(self, rng, count):
        examples = []
        for _ in range(count):
            order_id = _id(rng, "order")
            fname = _file(rng)
            dt = _base_dt(rng)

            # Partial payment record only
            ev = [_ev(_id(rng, "pay"), "paypal_api", dt,
                       f"Payment CREATED order={order_id} status=CREATED (not yet captured).")]
            claim = f"The buyer received and confirmed delivery of {fname} for order {order_id}."
            examples.append(Example(
                example_id=self._next_id(),
                scenario_family=self.family,
                claim=claim,
                evidence=ev,
                label="INSUFFICIENT_EVIDENCE",
                label_rationale=(
                    "Only a CREATED payment status exists; no capture or delivery records available."
                ),
            ))
        return examples


class DeliveryMissingTimestamp(ScenarioGenerator):
    family = "delivery_timestamp_missing"

    def generate(self, rng, count):
        examples = []
        for _ in range(count):
            order_id = _id(rng, "order")
            fname = _file(rng)

            ev = [{"evidence_id": _id(rng, "del"), "source_type": "delivery_service",
                   "timestamp": None,
                   "content": f"File {fname} delivered for order {order_id} (timestamp not recorded)."}]
            claim = f"The file {fname} was delivered on October 8."
            examples.append(Example(
                example_id=self._next_id(),
                scenario_family=self.family,
                claim=claim,
                evidence=ev,
                label="INSUFFICIENT_EVIDENCE",
                label_rationale="Delivery record exists but has no timestamp; date claim cannot be verified.",
            ))
        return examples


# ---------------------------------------------------------------------------
# Challenge test scenarios (harder adversarial cases)
# ---------------------------------------------------------------------------

class ChallengeUnsupportedDetails(ScenarioGenerator):
    family = "challenge_unsupported_detail_in_correct_claim"

    def generate(self, rng, count):
        examples = []
        for _ in range(count):
            order_id = _id(rng, "order")
            fname = _file(rng)
            buyer = _name(rng)
            dt = _base_dt(rng)
            amt, cur = _amount(rng)

            ev = [
                _ev(_id(rng, "pay"), "paypal_api", dt,
                    f"Payment COMPLETED order={order_id} payer={buyer} amount={amt} {cur}."),
                _ev(_id(rng, "del"), "delivery_service", dt + timedelta(hours=1),
                    f"File {fname} delivered to {buyer} order={order_id}."),
            ]
            # Adds unsupported "5-star rating"
            claim = (
                f"Payment was completed and {fname} was delivered to {buyer} for order {order_id}, "
                "and the buyer gave a 5-star rating."
            )
            examples.append(Example(
                example_id=self._next_id(),
                scenario_family=self.family,
                claim=claim,
                evidence=ev,
                label="INSUFFICIENT_EVIDENCE",
                label_rationale=(
                    "Payment and delivery are supported, but the 5-star rating is not evidenced."
                ),
            ))
        return examples


class ChallengeCorrectDateWrongRecipient(ScenarioGenerator):
    family = "challenge_correct_date_wrong_recipient"

    def generate(self, rng, count):
        examples = []
        for _ in range(count):
            order_id = _id(rng, "order")
            fname = _file(rng)
            buyer = _name(rng)
            other = _name(rng)
            while other == buyer:
                other = _name(rng)
            dt = _base_dt(rng)
            date_str = dt.strftime("%B %-d")

            ev = [_ev(_id(rng, "del"), "delivery_service", dt,
                       f"File {fname} delivered to {other} on {date_str} order={order_id}.")]
            claim = f"The file {fname} was delivered to {buyer} on {date_str} for order {order_id}."
            examples.append(Example(
                example_id=self._next_id(),
                scenario_family=self.family,
                claim=claim,
                evidence=ev,
                label="CONTRADICTED",
                label_rationale=f"Date is correct but recipient is {other}, not {buyer}.",
            ))
        return examples


class ChallengeCorrectPaymentNoDelivery(ScenarioGenerator):
    family = "challenge_correct_payment_no_delivery_proof"

    def generate(self, rng, count):
        examples = []
        for _ in range(count):
            order_id = _id(rng, "order")
            fname = _file(rng)
            buyer = _name(rng)
            dt = _base_dt(rng)
            amt, cur = _amount(rng)

            ev = [_ev(_id(rng, "pay"), "paypal_api", dt,
                       f"Payment COMPLETED order={order_id} payer={buyer} amount={amt} {cur}.")]
            claim = f"The buyer {buyer} paid for and received {fname} for order {order_id}."
            examples.append(Example(
                example_id=self._next_id(),
                scenario_family=self.family,
                claim=claim,
                evidence=ev,
                label="INSUFFICIENT_EVIDENCE",
                label_rationale="Payment confirmed but no delivery or download record available.",
            ))
        return examples


class ChallengeOnlyOneSupports(ScenarioGenerator):
    family = "challenge_only_one_of_multiple_supports"

    def generate(self, rng, count):
        examples = []
        for _ in range(count):
            order_id = _id(rng, "order")
            fname = _file(rng)
            buyer = _name(rng)
            buyer_email = _email(buyer, rng)
            other = _name(rng)
            dt = _base_dt(rng)

            # One record supports, one contradicts
            ev = [
                _ev(_id(rng, "del1"), "delivery_service", dt,
                    f"File {fname} delivered to {buyer} email={buyer_email} order={order_id}."),
                _ev(_id(rng, "del2"), "delivery_service", dt + timedelta(minutes=5),
                    f"File {fname} delivery failed for order {order_id} — recipient not found."),
            ]
            claim = f"The file {fname} was successfully delivered to {buyer} for order {order_id}."
            examples.append(Example(
                example_id=self._next_id(),
                scenario_family=self.family,
                claim=claim,
                evidence=ev,
                label="CONTRADICTED",
                label_rationale=(
                    "First event records delivery success, but a subsequent event records delivery failure."
                ),
            ))
        return examples


# ---------------------------------------------------------------------------
# Generator registry and split logic
# ---------------------------------------------------------------------------

ALL_GENERATORS = [
    PaymentCapturedVsCreated,
    LicenceIssuedVsAccessed,
    FileSentVsDownloaded,
    DeliveryTimestampMismatch,
    RecipientMismatch,
    OrderIdMismatch,
    CourseAccessGrantedVsAccessed,
    AssetVersionMismatch,
    ImpossibleEventOrder,
    MissingEvidence,
    ConflictingDeliveryEvents,
    MultipleRecordsSupporting,
    BroaderThanEvidence,
    UnsupportedClaimDetails,
    CurrencyAmountMismatch,
    RefundClaimMissingConfirmation,
    UnrelatedTransaction,
    TamperedEventHistory,
    ConflictingStatusSnapshots,
    PlausibleButUnestablished,
    FullySupported,
    MultipleConflictingRecords,
    IncompleteRecords,
    DeliveryMissingTimestamp,
]

CHALLENGE_GENERATORS = [
    ChallengeUnsupportedDetails,
    ChallengeCorrectDateWrongRecipient,
    ChallengeCorrectPaymentNoDelivery,
    ChallengeOnlyOneSupports,
]


def _group_split(
    examples: list[Example],
    families: list[str],
    val_families: list[str],
    test_families: list[str],
) -> tuple[list[Example], list[Example], list[Example]]:
    """Group-based split: held-out families go to val/test."""
    train, val, test = [], [], []
    for ex in examples:
        if ex.scenario_family in test_families:
            test.append(ex)
        elif ex.scenario_family in val_families:
            val.append(ex)
        else:
            train.append(ex)
    return train, val, test


def _validate_examples(examples: list[Example]) -> list[str]:
    """Return list of error messages."""
    errors = []
    seen_ids = set()
    for ex in examples:
        if ex.example_id in seen_ids:
            errors.append(f"Duplicate example_id: {ex.example_id}")
        seen_ids.add(ex.example_id)
        if ex.label not in LABELS:
            errors.append(f"{ex.example_id}: invalid label '{ex.label}'")
        if not ex.claim.strip():
            errors.append(f"{ex.example_id}: empty claim")
    return errors


def _write_jsonl(examples: list[Example], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for ex in examples:
            f.write(json.dumps(ex.to_dict(), ensure_ascii=False) + "\n")


def _label_dist(examples: list[Example]) -> dict:
    dist: dict[str, int] = {}
    for ex in examples:
        dist[ex.label] = dist.get(ex.label, 0) + 1
    return dist


def generate(
    output_dir: str = "data/processed/evidencebench",
    seed: int = 42,
    target_count: int = 10000,
) -> dict:
    rng = random.Random(seed)
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    all_families = [g.family for g in ALL_GENERATORS]
    n_gen = len(ALL_GENERATORS)
    per_gen = max(1, target_count // n_gen)

    # Assign a counter offset so IDs don't collide across generators
    all_examples: list[Example] = []
    counter_offset = 1
    for GenClass in ALL_GENERATORS:
        gen = GenClass()
        gen._counter = counter_offset
        batch = gen.generate(rng, per_gen)
        all_examples.extend(batch)
        counter_offset += per_gen + 100

    # Challenge examples
    challenge_examples: list[Example] = []
    challenge_offset = counter_offset + 100000
    per_challenge = 100
    for GenClass in CHALLENGE_GENERATORS:
        gen = GenClass()
        gen._counter = challenge_offset
        batch = gen.generate(rng, per_challenge)
        challenge_examples.extend(batch)
        challenge_offset += per_challenge + 50

    # Validation
    errors = _validate_examples(all_examples + challenge_examples)
    if errors:
        print(f"VALIDATION WARNINGS ({len(errors)}):")
        for e in errors[:20]:
            print(f"  {e}")

    # Group-based split: hold out ~4 families each for val/test
    rng2 = random.Random(seed + 1)
    shuffled_families = list(all_families)
    rng2.shuffle(shuffled_families)
    n = len(shuffled_families)
    val_families = set(shuffled_families[:4])
    test_families = set(shuffled_families[4:8])

    train, val, test = _group_split(all_examples, all_families, val_families, test_families)

    _write_jsonl(train, out / "train.jsonl")
    _write_jsonl(val, out / "validation.jsonl")
    _write_jsonl(test, out / "test.jsonl")
    _write_jsonl(challenge_examples, out / "challenge_test.jsonl")

    schema = {
        "version": "1.1",
        "fields": {
            "example_id": "string",
            "scenario_family": "string",
            "claim": "string",
            "evidence": "list of {evidence_id, source_type, timestamp, content}",
            "label": "SUPPORTED | CONTRADICTED | INSUFFICIENT_EVIDENCE",
            "label_rationale": "string",
            "is_synthetic": "bool",
        },
        "labels": LABELS,
        "scenario_families": all_families + [g.family for g in CHALLENGE_GENERATORS],
    }
    with open(out / "schema.json", "w") as f:
        json.dump(schema, f, indent=2)

    report = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "seed": seed,
        "target_count": target_count,
        "total_main": len(all_examples),
        "train_count": len(train),
        "validation_count": len(val),
        "test_count": len(test),
        "challenge_count": len(challenge_examples),
        "val_families": sorted(val_families),
        "test_families": sorted(test_families),
        "train_label_dist": _label_dist(train),
        "val_label_dist": _label_dist(val),
        "test_label_dist": _label_dist(test),
        "challenge_label_dist": _label_dist(challenge_examples),
        "validation_errors": errors,
        "generators_used": [g.family for g in ALL_GENERATORS],
        "challenge_generators_used": [g.family for g in CHALLENGE_GENERATORS],
        "split_type": "group_based_by_scenario_family",
    }
    with open(out / "generation_report.json", "w") as f:
        json.dump(report, f, indent=2)

    manifest = {
        "dataset_name": "EvidenceBench",
        "version": "1.1",
        "description": "Synthetic domain-specific benchmark for PayPal digital-goods evidence verification.",
        "licence": "Proprietary — synthetic data, not derived from real customer records.",
        "is_synthetic": True,
        "generated_at": report["generated_at"],
        "seed": seed,
        "splits": {
            "train": str(out / "train.jsonl"),
            "validation": str(out / "validation.jsonl"),
            "test": str(out / "test.jsonl"),
            "challenge_test": str(out / "challenge_test.jsonl"),
        },
        "counts": {
            "train": len(train),
            "validation": len(val),
            "test": len(test),
            "challenge": len(challenge_examples),
        },
        "label_mapping": {
            "SUPPORTED": "claim is adequately established by available evidence",
            "CONTRADICTED": "available evidence conflicts with the claim",
            "INSUFFICIENT_EVIDENCE": "evidence neither establishes nor contradicts the claim",
        },
    }
    with open(out / "manifest.json", "w") as f:
        json.dump(manifest, f, indent=2)

    print(f"\nEvidenceBench generated → {out}")
    print(f"  Train: {len(train)}  Val: {len(val)}  Test: {len(test)}  Challenge: {len(challenge_examples)}")
    print(f"  Train labels: {_label_dist(train)}")
    print(f"  Validation errors: {len(errors)}")

    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default="data/processed/evidencebench_v1_1")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--target-count", type=int, default=10000)
    args = parser.parse_args()
    generate(args.output_dir, args.seed, args.target_count)

