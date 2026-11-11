"""
Parse and preprocess FEVEROUS data for NLI training.

FEVEROUS uses integer labels: 0=SUPPORTS, 1=REFUTES, 2=NOT ENOUGH INFO
Evidence content contains reference IDs (cell/sentence identifiers), not raw text.
Context field contains the associated evidence text strings.

This parser extracts context strings as evidence text, skipping examples
where evidence text cannot be reconstructed.

Label mapping:
    0 (SUPPORTS)        → SUPPORTED
    1 (REFUTES)         → CONTRADICTED
    2 (NOT ENOUGH INFO) → INSUFFICIENT_EVIDENCE

Usage:
    python -m src.data.parse_feverous \
        --raw-dir data/raw/feverous \
        --output-dir data/processed/feverous
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from src.models.labels import AppLabel

RAW_DIR = Path("data/raw/feverous")
PROCESSED_DIR = Path("data/processed/feverous")

# Integer label → AppLabel (verified against ClassLabel in HF dataset features)
INT_TO_APP = {
    0: AppLabel.SUPPORTED,      # SUPPORTS
    1: AppLabel.CONTRADICTED,   # REFUTES
    2: AppLabel.INSUFFICIENT_EVIDENCE,  # NOT ENOUGH INFO
}
INT_TO_STR = {0: "SUPPORTS", 1: "REFUTES", 2: "NOT ENOUGH INFO"}


def _extract_context_text(evidence_list: list) -> str:
    """
    Extract human-readable text from FEVEROUS evidence context.

    Each evidence item has:
      - 'content': list of cell/sentence reference IDs (e.g. 'Page_cell_0_1_2')
      - 'context': list of lists of context strings (the actual text)

    We flatten all context strings as the evidence text.
    """
    all_texts = []
    for ev_item in evidence_list:
        if not isinstance(ev_item, dict):
            continue
        context = ev_item.get("context", [])
        if isinstance(context, list):
            for sub in context:
                if isinstance(sub, list):
                    for item in sub:
                        if isinstance(item, str) and item.strip():
                            # Skip pure reference IDs (contain _title, _cell_, _section_)
                            if not any(kw in item for kw in ("_cell_", "_section_", "_header_")):
                                all_texts.append(item.strip())
                elif isinstance(sub, str) and sub.strip():
                    if not any(kw in sub for kw in ("_cell_", "_section_", "_header_")):
                        all_texts.append(sub.strip())
    # Deduplicate while preserving order
    seen = set()
    unique = []
    for t in all_texts:
        if t not in seen:
            seen.add(t)
            unique.append(t)
    return " ".join(unique).strip()


def parse_feverous(
    raw_dir: str = str(RAW_DIR),
    output_dir: str = str(PROCESSED_DIR),
    max_per_split: Optional[int] = None,
) -> dict:
    raw = Path(raw_dir)
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    stats: dict = {
        "parsed_at": datetime.now(timezone.utc).isoformat(),
        "label_mapping": {str(k): v.value for k, v in INT_TO_APP.items()},
        "splits": {},
        "total_processed": 0,
        "total_excluded": 0,
    }

    for jsonl_file in sorted(raw.glob("*.jsonl")):
        split_name = jsonl_file.stem
        if split_name == "manifest":
            continue

        out_path = out / f"{split_name}.jsonl"
        processed_count = 0
        excluded_count = 0
        exclusion_log = []
        label_dist: dict[str, int] = {}

        with open(jsonl_file, encoding="utf-8") as f_in, \
             open(out_path, "w", encoding="utf-8") as f_out:

            for line_no, line in enumerate(f_in):
                if max_per_split and processed_count >= max_per_split:
                    break

                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError as e:
                    excluded_count += 1
                    exclusion_log.append(f"line {line_no}: JSON error — {e}")
                    continue

                # --- Claim ---
                claim = row.get("claim", "")
                if not isinstance(claim, str) or not claim.strip():
                    excluded_count += 1
                    exclusion_log.append(f"line {line_no}: missing claim")
                    continue

                # --- Integer label ---
                raw_label = row.get("label")
                if raw_label is None:
                    excluded_count += 1
                    exclusion_log.append(f"line {line_no}: missing label")
                    continue

                try:
                    label_int = int(raw_label)
                except (TypeError, ValueError):
                    excluded_count += 1
                    exclusion_log.append(f"line {line_no}: non-integer label '{raw_label}'")
                    continue

                app_label = INT_TO_APP.get(label_int)
                if app_label is None:
                    excluded_count += 1
                    exclusion_log.append(f"line {line_no}: unknown label int {label_int}")
                    continue

                # --- Evidence text ---
                evidence_list = row.get("evidence", [])
                evidence_text = _extract_context_text(evidence_list)

                if not evidence_text.strip():
                    if app_label == AppLabel.INSUFFICIENT_EVIDENCE:
                        # NEI with no reconstructable evidence is acceptable
                        evidence_text = "[NO EVIDENCE PROVIDED]"
                    else:
                        excluded_count += 1
                        exclusion_log.append(
                            f"line {line_no}: no reconstructable evidence text for label={app_label.value}"
                        )
                        continue

                record = {
                    "example_id": f"feverous_{split_name}_{line_no:07d}",
                    "source_dataset": "feverous",
                    "split": split_name,
                    "claim": claim.strip(),
                    "evidence_text": evidence_text[:4000],
                    "original_label_int": label_int,
                    "original_label_str": INT_TO_STR.get(label_int, "UNKNOWN"),
                    "label": app_label.value,
                    "is_synthetic": False,
                }
                f_out.write(json.dumps(record, ensure_ascii=False) + "\n")
                processed_count += 1
                label_dist[app_label.value] = label_dist.get(app_label.value, 0) + 1

        split_stats = {
            "processed": processed_count,
            "excluded": excluded_count,
            "label_dist": label_dist,
            "exclusion_sample": exclusion_log[:10],
        }
        stats["splits"][split_name] = split_stats
        stats["total_processed"] += processed_count
        stats["total_excluded"] += excluded_count
        print(
            f"  {split_name}: processed={processed_count} excluded={excluded_count} labels={label_dist}"
        )

    with open(out / "parse_stats.json", "w") as f:
        json.dump(stats, f, indent=2)
    print(f"\nFEVEROUS parsed → {out}")
    print(f"  Total processed: {stats['total_processed']}  Excluded: {stats['total_excluded']}")
    return stats


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw-dir", default=str(RAW_DIR))
    parser.add_argument("--output-dir", default=str(PROCESSED_DIR))
    parser.add_argument("--max-per-split", type=int, default=None)
    args = parser.parse_args()
    parse_feverous(args.raw_dir, args.output_dir, args.max_per_split)
