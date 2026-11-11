"""
NLI input formatter for ProofLedger.

Premise  = normalized evidence text (source records)
Hypothesis = factual claim to verify
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional

MAX_EVIDENCE_CHARS = 3000  # soft cap before truncation warning
EVIDENCE_SEPARATOR = " | "


@dataclass
class EvidenceRecord:
    evidence_id: str
    source_type: str
    timestamp: Optional[str]
    content: str


@dataclass
class FormattedInput:
    premise: str
    hypothesis: str
    evidence_ids: List[str]
    truncated: bool = False
    truncation_warning: Optional[str] = None


def format_evidence(records: List[EvidenceRecord], max_chars: int = MAX_EVIDENCE_CHARS) -> tuple[str, List[str], bool, Optional[str]]:
    """Concatenate evidence records into a single premise string.

    Returns (premise_text, evidence_ids, truncated, warning_message).
    Source IDs are preserved; truncation is flagged explicitly.
    """
    if not records:
        return "", [], False, None

    parts = []
    ids = []
    total = 0
    truncated = False
    warning = None

    for rec in records:
        prefix = f"[{rec.source_type.upper()}|{rec.evidence_id}]"
        if rec.timestamp:
            prefix += f" {rec.timestamp}"
        fragment = f"{prefix}: {rec.content.strip()}"

        if total + len(fragment) > max_chars and parts:
            truncated = True
            warning = (
                f"Evidence truncated: {len(records) - len(parts)} record(s) omitted. "
                "This may affect contradiction detection."
            )
            break

        parts.append(fragment)
        ids.append(rec.evidence_id)
        total += len(fragment) + len(EVIDENCE_SEPARATOR)

    return EVIDENCE_SEPARATOR.join(parts), ids, truncated, warning


def build_nli_input(
    claim: str,
    evidence_records: List[EvidenceRecord],
    max_chars: int = MAX_EVIDENCE_CHARS,
) -> FormattedInput:
    """Build a FormattedInput (premise/hypothesis pair) for NLI inference."""
    claim = claim.strip()
    if not claim:
        raise ValueError("Claim text must not be empty.")

    premise, ids, truncated, warning = format_evidence(evidence_records, max_chars)

    if not premise:
        premise = "[NO EVIDENCE PROVIDED]"

    return FormattedInput(
        premise=premise,
        hypothesis=claim,
        evidence_ids=ids,
        truncated=truncated,
        truncation_warning=warning,
    )

