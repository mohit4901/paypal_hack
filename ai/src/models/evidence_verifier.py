"""
Evidence Verifier — core inference class for ProofLedger.

Loads the selected NLI checkpoint and runs claim/evidence verification.
Label mapping is read from the actual model config, not assumed.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.models.input_format import EvidenceRecord, build_nli_input
from src.models.labels import AppLabel, NLILabel, NLI_TO_APP, APP_LABEL_NAMES
from src.utils.logging_config import setup_logging

logger = setup_logging(name="evidence_verifier")

# Default model: pretrained DeBERTa v3 NLI checkpoint
DEFAULT_MODEL = "MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli"
DEFAULT_REVISION = "main"  # pinned after first download


class EvidenceVerifier:
    """
    Loads an NLI model and performs evidence verification.

    The label mapping is read from the actual model config (id2label).
    The model's NLI labels are mapped to ProofLedger AppLabel values.
    """

    def __init__(
        self,
        model_path: Optional[str] = None,
        device: Optional[str] = None,
        max_length: int = 512,
    ):
        self.model_path = model_path or os.getenv("MODEL_PATH", DEFAULT_MODEL)
        self.max_length = max_length
        self._model = None
        self._tokenizer = None
        self._id2label: Dict[int, str] = {}
        self._nli_to_app: Dict[str, AppLabel] = {}
        self.model_info: Dict[str, Any] = {}

        import torch
        if device is None:
            if torch.cuda.is_available():
                device = "cuda"
            elif torch.backends.mps.is_available():
                device = "mps"
            else:
                device = "cpu"
        self.device = device
        self._torch = torch
        logger.info(f"EvidenceVerifier initializing on device={device}")

    def load(self) -> None:
        """Load model and tokenizer from model_path."""
        from transformers import AutoModelForSequenceClassification, AutoTokenizer

        logger.info(f"Loading model from {self.model_path}")
        t0 = time.time()

        self._tokenizer = AutoTokenizer.from_pretrained(self.model_path)
        self._model = AutoModelForSequenceClassification.from_pretrained(
            self.model_path,
            ignore_mismatched_sizes=False,
        )
        self._model.to(self.device)
        self._model.eval()

        # Read ACTUAL label mapping from model config
        cfg = self._model.config
        self._id2label = {int(k): v for k, v in cfg.id2label.items()}
        logger.info(f"Model id2label: {self._id2label}")

        # Build NLI→App mapping from actual config
        self._nli_to_app = {}
        for idx, raw_label in self._id2label.items():
            upper = raw_label.strip().upper()
            if upper in ("ENTAILMENT", "SUPPORTED", "SUPPORTS"):
                self._nli_to_app[raw_label] = AppLabel.SUPPORTED
            elif upper in ("CONTRADICTION", "CONTRADICTED", "REFUTES"):
                self._nli_to_app[raw_label] = AppLabel.CONTRADICTED
            elif upper in ("NEUTRAL", "INSUFFICIENT_EVIDENCE", "NOT ENOUGH INFO"):
                self._nli_to_app[raw_label] = AppLabel.INSUFFICIENT_EVIDENCE
            else:
                logger.warning(f"Unknown NLI label in model config: '{raw_label}' — will map to INSUFFICIENT_EVIDENCE")
                self._nli_to_app[raw_label] = AppLabel.INSUFFICIENT_EVIDENCE

        elapsed = time.time() - t0
        self.model_info = {
            "model_path": str(self.model_path),
            "architecture": cfg.model_type,
            "num_labels": cfg.num_labels,
            "id2label": {str(k): str(v) for k, v in self._id2label.items()},
            "nli_to_app": {k: v.value for k, v in self._nli_to_app.items()},
            "device": self.device,
            "load_time_s": round(elapsed, 2),
        }
        logger.info(f"Model loaded in {elapsed:.1f}s. NLI→App mapping: {self.model_info['nli_to_app']}")

    @property
    def is_loaded(self) -> bool:
        return self._model is not None and self._tokenizer is not None

    def predict(
        self,
        claim: str,
        evidence_records: List[EvidenceRecord],
    ) -> Dict[str, Any]:
        """
        Verify a claim against evidence records.

        Returns a dict with label, scores, evidence_ids, and metadata.
        """
        if not self.is_loaded:
            raise RuntimeError("Call .load() before .predict()")

        formatted = build_nli_input(claim, evidence_records, self.max_length * 4)

        import torch

        inputs = self._tokenizer(
            formatted.premise,
            formatted.hypothesis,
            truncation=True,
            max_length=self.max_length,
            return_tensors="pt",
            padding=True,
        )
        inputs = {k: v.to(self.device) for k, v in inputs.items()}

        with torch.no_grad():
            outputs = self._model(**inputs)
            logits = outputs.logits
            raw_logits = logits.squeeze().cpu().tolist()
            if isinstance(raw_logits, float):
                raw_logits = [raw_logits]
            probs = torch.softmax(logits, dim=-1).squeeze().cpu().tolist()

        # Build scores dict keyed by raw NLI label
        if isinstance(probs, float):
            probs = [probs]

        scores_by_nli = {self._id2label[i]: float(p) for i, p in enumerate(probs)}
        scores_by_app: Dict[str, float] = {}
        for nli_lbl, prob in scores_by_nli.items():
            app_lbl = self._nli_to_app.get(nli_lbl, AppLabel.INSUFFICIENT_EVIDENCE)
            scores_by_app[app_lbl.value] = scores_by_app.get(app_lbl.value, 0.0) + prob

        # Pick highest-scoring App label
        best_label = max(scores_by_app, key=scores_by_app.__getitem__)
        confidence = scores_by_app[best_label]

        # Safe Abstention Mechanism:
        # Prevents reckless autonomous misclassification when probability is uncalibrated
        # or when the margin between top-2 classes is razor-thin.
        sorted_scores = sorted(scores_by_app.values(), reverse=True)
        top1 = sorted_scores[0]
        top2 = sorted_scores[1] if len(sorted_scores) > 1 else 0.0
        margin = round(top1 - top2, 4)

        is_abstained = False
        abstention_reason = None
        decision = best_label

        if top1 < 0.55:
            is_abstained = True
            abstention_reason = f"Low absolute confidence ({top1:.4f} < 0.55); semantic ambiguity detected."
            decision = "NEEDS_HUMAN_REVIEW"
        elif margin < 0.12:
            is_abstained = True
            abstention_reason = f"Narrow decision margin ({margin:.4f} < 0.12) between competing classes; requires human oversight."
            decision = "NEEDS_HUMAN_REVIEW"

        result = {
            "label": best_label,
            "decision": decision,
            "is_abstained": is_abstained,
            "abstention_reason": abstention_reason,
            "margin": margin,
            "confidence": round(confidence, 4),
            "logits": [round(float(l), 4) for l in raw_logits],
            "note_confidence": (
                "Raw model score — not a calibrated probability. "
                "Does not indicate PayPal dispute outcome."
            ),
            "scores": {k: round(v, 4) for k, v in scores_by_app.items()},
            "nli_scores": {k: round(v, 4) for k, v in scores_by_nli.items()},
            "evidence_ids": formatted.evidence_ids,
            "truncated": formatted.truncated,
            "truncation_warning": formatted.truncation_warning,
            "model_path": str(self.model_path),
        }
        return result

    def batch_predict(
        self,
        items: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Predict for a list of {claim, evidence_records} dicts."""
        results = []
        for item in items:
            claim = item["claim"]
            ev_recs = [
                EvidenceRecord(
                    evidence_id=e.get("evidence_id", f"ev_{i}"),
                    source_type=e.get("source_type", "unknown"),
                    timestamp=e.get("timestamp"),
                    content=e.get("content", ""),
                )
                for i, e in enumerate(item.get("evidence", []))
            ]
            results.append(self.predict(claim, ev_recs))
        return results

