"""
Download FEVEROUS dataset from Hugging Face Hub.

FEVEROUS licence: CC BY-SA 3.0
Source: https://huggingface.co/datasets/fever/feverous
Paper: https://openreview.net/forum?id=h-flVCIlstW
DOI:   https://doi.org/10.5281/zenodo.4911508

Usage:
    python -m src.data.download_feverous --output-dir data/raw/feverous
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

RAW_DIR = Path("data/raw/feverous")
PROCESSED_DIR = Path("data/processed/feverous")

HF_DATASET_NAME = "fever/feverous"
HF_REVISION = "main"  # pin to a revision after first successful download


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def download_feverous(output_dir: str = str(RAW_DIR)) -> dict:
    """Download FEVEROUS splits from Hugging Face and record metadata."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    try:
        from datasets import load_dataset  # type: ignore
    except ImportError:
        raise RuntimeError(
            "The 'datasets' library is required: pip install datasets"
        )

    print(f"Downloading FEVEROUS from HuggingFace ({HF_DATASET_NAME}) ...")
    # FEVEROUS has a custom loading script that must be executed locally.
    # The script is reviewed: https://huggingface.co/datasets/fever/feverous/blob/main/feverous.py
    ds = load_dataset(HF_DATASET_NAME, revision=HF_REVISION, trust_remote_code=True)

    splits_saved = {}
    for split_name, split_data in ds.items():
        # We skip the unlabelled test split intentionally
        if split_name.lower() in ("test", "test_unlabelled"):
            print(f"  Skipping unlabelled split: {split_name}")
            continue

        out_path = out / f"{split_name}.jsonl"
        split_data.to_json(str(out_path))
        file_hash = sha256(out_path)
        row_count = len(split_data)
        splits_saved[split_name] = {
            "path": str(out_path),
            "row_count": row_count,
            "sha256": file_hash,
        }
        print(f"  Saved {split_name}: {row_count} rows → {out_path} (sha256={file_hash[:12]}…)")

    # Inspect actual column names
    sample_split = next(iter(ds.values()))
    columns = sample_split.column_names

    # Record one sample to understand schema
    sample = sample_split[0] if len(sample_split) > 0 else {}

    manifest = {
        "dataset_name": "FEVEROUS",
        "hf_dataset": HF_DATASET_NAME,
        "revision": HF_REVISION,
        "licence": "CC BY-SA 3.0 (verify at https://fever.ai/dataset/feverous.html)",
        "citation": "Aly et al. (2021), FEVEROUS: Fact Extraction and VERification Over Unstructured and Structured information.",
        "doi": "https://doi.org/10.5281/zenodo.4911508",
        "downloaded_at": datetime.now(timezone.utc).isoformat(),
        "splits": splits_saved,
        "columns": columns,
        "sample_keys": list(sample.keys()) if isinstance(sample, dict) else [],
        "note": (
            "The blind test split is excluded from supervised training per project policy. "
            "Only train and dev splits are used."
        ),
    }

    manifest_path = out / "manifest.json"
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)
    print(f"\nManifest saved → {manifest_path}")

    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default=str(RAW_DIR))
    args = parser.parse_args()
    result = download_feverous(args.output_dir)
    print(f"\nFEVEROUS columns: {result.get('columns', [])}")
    print(f"Splits downloaded: {list(result.get('splits', {}).keys())}")
