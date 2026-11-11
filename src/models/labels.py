"""
ProofLedger — Canonical label definitions.

Three-class schema used throughout the system.
"""
from __future__ import annotations
from enum import Enum


class AppLabel(str, Enum):
    SUPPORTED = "SUPPORTED"
    CONTRADICTED = "CONTRADICTED"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


class NLILabel(str, Enum):
    ENTAILMENT = "ENTAILMENT"
    CONTRADICTION = "CONTRADICTION"
    NEUTRAL = "NEUTRAL"


# NLI → App label mapping
NLI_TO_APP: dict[NLILabel, AppLabel] = {
    NLILabel.ENTAILMENT: AppLabel.SUPPORTED,
    NLILabel.CONTRADICTION: AppLabel.CONTRADICTED,
    NLILabel.NEUTRAL: AppLabel.INSUFFICIENT_EVIDENCE,
}

# FEVEROUS raw → App label mapping (actual strings from the dataset)
FEVEROUS_TO_APP: dict[str, AppLabel] = {
    "SUPPORTS": AppLabel.SUPPORTED,
    "REFUTES": AppLabel.CONTRADICTED,
    "NOT ENOUGH INFO": AppLabel.INSUFFICIENT_EVIDENCE,
}

APP_LABEL_LIST = [AppLabel.SUPPORTED, AppLabel.CONTRADICTED, AppLabel.INSUFFICIENT_EVIDENCE]
APP_LABEL_NAMES = [l.value for l in APP_LABEL_LIST]

# Index ↔ App label (for training)
IDX_TO_APP: dict[int, AppLabel] = {i: l for i, l in enumerate(APP_LABEL_LIST)}
APP_TO_IDX: dict[AppLabel, int] = {l: i for i, l in IDX_TO_APP.items()}

