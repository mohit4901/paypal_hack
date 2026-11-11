"""
Comprehensive Diagnostic Audit for ProofLedger Model & EvidenceBench.
Executes Item 1, 2, 3, 4 of the post-training diagnostic audit.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import torch
import torch.nn.functional as F
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_recall_fscore_support,
)
from torch.utils.data import DataLoader, Dataset
from transformers import AutoConfig, AutoModelForSequenceClassification, AutoTokenizer

from src.models.labels import APP_LABEL_NAMES

LABEL2ID = {name: i for i, name in enumerate(APP_LABEL_NAMES)}
ID2LABEL = {i: name for name, i in LABEL2ID.items()}


def _load_jsonl(path: str) -> List[Dict[str, Any]]:
    rows = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _get_text(row: Dict[str, Any]) -> Tuple[str, str]:
    if "evidence" in row:
        ev_parts = []
        for ev in row["evidence"]:
            if isinstance(ev, dict):
                eid = ev.get("evidence_id", "")
                src = ev.get("source_type", "")
                ts = ev.get("timestamp", "")
                content = ev.get("content", "")
                part = f"[{src.upper()}|{eid}]"
                if ts:
                    part += f" {ts}"
                part += f": {content}"
                ev_parts.append(part)
        premise = " | ".join(ev_parts) if ev_parts else "[NO EVIDENCE]"
    elif "evidence_text" in row:
        premise = row.get("evidence_text", "[NO EVIDENCE]")
    else:
        premise = "[NO EVIDENCE]"
    hypothesis = row.get("claim", "")
    return premise, hypothesis


class AuditDataset(Dataset):
    def __init__(self, rows: List[Dict[str, Any]], tokenizer: Any, max_length: int = 256):
        self.rows = rows
        self.tokenizer = tokenizer
        self.max_length = max_length

    def __len__(self) -> int:
        return len(self.rows)

    def __getitem__(self, idx: int) -> Dict[str, Any]:
        row = self.rows[idx]
        premise, hypothesis = _get_text(row)
        label_str = row.get("label", "INSUFFICIENT_EVIDENCE")
        label_id = LABEL2ID.get(label_str, 2)
        enc = self.tokenizer(
            premise,
            hypothesis,
            truncation=True,
            max_length=self.max_length,
            padding="max_length",
            return_tensors="pt",
        )
        return {
            "example_id": row.get("example_id", f"ex_{idx}"),
            "scenario_family": row.get("scenario_family", "unknown"),
            "input_ids": enc["input_ids"].squeeze(0),
            "attention_mask": enc["attention_mask"].squeeze(0),
            "label": label_id,
            "claim": hypothesis,
            "premise": premise,
        }


def run_model_inference(
    model_path: str,
    data_path: str,
    device: torch.device,
    batch_size: int = 32,
    max_length: int = 256,
) -> Dict[str, Any]:
    tokenizer = AutoTokenizer.from_pretrained(model_path)
    model = AutoModelForSequenceClassification.from_pretrained(model_path)
    model.to(device)
    model.eval()

    cfg = model.config
    raw_id2label = {int(k): v for k, v in cfg.id2label.items()}
    out_idx_to_app_idx: Dict[int, int] = {}
    for idx, name in raw_id2label.items():
        name_str = str(name).strip().upper()
        if name_str in ("ENTAILMENT", "SUPPORTED", "SUPPORTS"):
            out_idx_to_app_idx[idx] = LABEL2ID["SUPPORTED"]
        elif name_str in ("CONTRADICTION", "CONTRADICTED", "REFUTES"):
            out_idx_to_app_idx[idx] = LABEL2ID["CONTRADICTED"]
        elif name_str in ("NEUTRAL", "INSUFFICIENT_EVIDENCE", "NOT ENOUGH INFO"):
            out_idx_to_app_idx[idx] = LABEL2ID["INSUFFICIENT_EVIDENCE"]
        else:
            out_idx_to_app_idx[idx] = LABEL2ID["INSUFFICIENT_EVIDENCE"]

    rows = _load_jsonl(data_path)
    ds = AuditDataset(rows, tokenizer, max_length)
    loader = DataLoader(ds, batch_size=batch_size, shuffle=False)

    records = []
    all_raw_logits = []
    all_mapped_logits = []
    all_raw_preds = []
    all_mapped_preds = []
    all_true_labels = []

    with torch.no_grad():
        for batch in loader:
            input_ids = batch["input_ids"].to(device)
            attention_mask = batch["attention_mask"].to(device)
            outputs = model(input_ids=input_ids, attention_mask=attention_mask)
            logits = outputs.logits.cpu().numpy()
            probs = F.softmax(torch.tensor(logits), dim=-1).numpy()
            preds = np.argmax(logits, axis=-1)

            for i in range(len(preds)):
                raw_p = int(preds[i])
                mapped_p = out_idx_to_app_idx.get(raw_p, raw_p)
                true_l = int(batch["label"][i].item())

                # Reordered logits into [SUPPORTED, CONTRADICTED, INSUFFICIENT_EVIDENCE]
                mapped_logit_vec = [0.0, 0.0, 0.0]
                for raw_i, val in enumerate(logits[i]):
                    target_i = out_idx_to_app_idx.get(raw_i, raw_i)
                    mapped_logit_vec[target_i] = float(val)

                mapped_prob_vec = F.softmax(torch.tensor(mapped_logit_vec), dim=-1).tolist()

                all_raw_logits.append(logits[i].tolist())
                all_mapped_logits.append(mapped_logit_vec)
                all_raw_preds.append(raw_p)
                all_mapped_preds.append(mapped_p)
                all_true_labels.append(true_l)

                records.append({
                    "example_id": batch["example_id"][i],
                    "scenario_family": batch["scenario_family"][i],
                    "true_label_id": true_l,
                    "true_label_name": ID2LABEL[true_l],
                    "predicted_label_id": mapped_p,
                    "predicted_label_name": ID2LABEL[mapped_p],
                    "raw_predicted_id": raw_p,
                    "raw_predicted_name": raw_id2label.get(raw_p, str(raw_p)),
                    "raw_logits": logits[i].tolist(),
                    "mapped_logits": mapped_logit_vec,
                    "mapped_probs": mapped_prob_vec,
                    "claim": batch["claim"][i],
                    "premise": batch["premise"][i][:200] + ("..." if len(batch["premise"][i]) > 200 else ""),
                })

    # Compute exact metrics from all_mapped_preds and all_true_labels
    y_true = np.array(all_true_labels)
    y_pred = np.array(all_mapped_preds)

    acc = float(accuracy_score(y_true, y_pred))
    macro_f1 = float(f1_score(y_true, y_pred, average="macro", zero_division=0))
    weighted_f1 = float(f1_score(y_true, y_pred, average="weighted", zero_division=0))

    prec, rec, f1, support = precision_recall_fscore_support(
        y_true, y_pred, labels=[0, 1, 2], zero_division=0
    )
    cm = confusion_matrix(y_true, y_pred, labels=[0, 1, 2]).tolist()

    # FDR & FPR for SUPPORTED (label 0)
    # cm: row = true, col = pred
    # cm[0][0]: True SUP, Pred SUP (TP)
    # cm[1][0]: True CON, Pred SUP (FP from CON)
    # cm[2][0]: True INS, Pred SUP (FP from INS)
    # Total Pred SUP = cm[0][0] + cm[1][0] + cm[2][0]
    # False Pred SUP = cm[1][0] + cm[2][0]
    # Total Non-SUP in Ground Truth = support[1] + support[2]
    tp_sup = cm[0][0]
    fp_sup = cm[1][0] + cm[2][0]
    total_pred_sup = tp_sup + fp_sup
    total_non_sup = support[1] + support[2]

    fpr_sup = float(fp_sup / total_non_sup) if total_non_sup > 0 else 0.0
    fdr_sup: Optional[float] = float(fp_sup / total_pred_sup) if total_pred_sup > 0 else None

    # Represented classes Macro-F1
    represented_f1s = [float(f1[i]) for i in range(3) if support[i] > 0]
    rep_macro_f1 = float(np.mean(represented_f1s)) if represented_f1s else 0.0

    metrics = {
        "model_path": model_path,
        "data_path": data_path,
        "n_examples": len(records),
        "raw_id2label": {str(k): v for k, v in raw_id2label.items()},
        "out_idx_to_app_idx": {str(k): v for k, v in out_idx_to_app_idx.items()},
        "accuracy": acc,
        "macro_f1": macro_f1,
        "represented_classes_macro_f1": rep_macro_f1,
        "weighted_f1": weighted_f1,
        "contradiction_recall": float(rec[1]),
        "insufficient_evidence_recall": float(rec[2]),
        "supported_recall": float(rec[0]),
        "supported_fpr": fpr_sup,
        "supported_fdr": fdr_sup,
        "confusion_matrix": cm,
        "confusion_matrix_labels": APP_LABEL_NAMES,
        "per_class": {
            APP_LABEL_NAMES[i]: {
                "precision": float(prec[i]),
                "recall": float(rec[i]),
                "f1": float(f1[i]),
                "support": int(support[i]),
            }
            for i in range(3)
        },
        "records": records,
    }
    return metrics

