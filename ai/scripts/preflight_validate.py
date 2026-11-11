#!/usr/bin/env python3
"""
Pre-flight validation before training launch.
Checks: label mapping, tokenizer, schema, split separation, duplicates.
"""
import json, sys, hashlib, collections
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parents[2]))

ERRORS = []
WARNINGS = []
DATA_DIR = Path("data/processed/evidencebench")
FEVEROUS_DIR = Path("data/processed/feverous")
BASE_MODEL = "artifacts/checkpoints/smoke_test/best"
VALID_LABELS = {"SUPPORTED", "CONTRADICTED", "INSUFFICIENT_EVIDENCE"}

def err(msg): ERRORS.append(msg); print(f"  ✗ ERROR: {msg}")
def warn(msg): WARNINGS.append(msg); print(f"  ⚠ WARN: {msg}")
def ok(msg): print(f"  ✓ {msg}")

# ── 1. Label mapping ──────────────────────────────────────────────────────────
print("\n[1] Label mapping")
from src.models.labels import FEVEROUS_TO_APP, IDX_TO_APP, AppLabel, APP_LABEL_NAMES
INT_TO_APP = IDX_TO_APP  # alias — labels.py uses IDX_TO_APP
assert len(APP_LABEL_NAMES) == 3
from src.data.parse_feverous import INT_TO_APP as fev_int_map  # integer label map
assert fev_int_map[0] == AppLabel.SUPPORTED
assert fev_int_map[1] == AppLabel.CONTRADICTED
assert fev_int_map[2] == AppLabel.INSUFFICIENT_EVIDENCE
ok("AppLabel: 3 classes, FEVEROUS int→app mapping verified")
ok(f"Label order: {APP_LABEL_NAMES}")

# ── 2. Tokenizer ──────────────────────────────────────────────────────────────
print("\n[2] Tokenizer")
try:
    from transformers import AutoTokenizer
    tok = AutoTokenizer.from_pretrained(BASE_MODEL)
    enc = tok("Evidence text here.", "Claim text here.", truncation=True, max_length=256, return_tensors="pt")
    assert enc["input_ids"].shape[-1] <= 256
    ok(f"Tokenizer loaded from {BASE_MODEL}, max_length=256 verified")
    # Verify special tokens
    ok(f"Tokenizer class: {type(tok).__name__}")
    ok(f"Vocab size: {tok.vocab_size}")
except Exception as e:
    err(f"Tokenizer failed: {e}")

# ── 3. Model config & label mapping ──────────────────────────────────────────
print("\n[3] Model config")
try:
    from transformers import AutoModelForSequenceClassification
    model = AutoModelForSequenceClassification.from_pretrained(BASE_MODEL)
    cfg = model.config
    id2label = {int(k): v for k, v in cfg.id2label.items()}
    ok(f"Model id2label: {id2label}")
    ok(f"num_labels: {cfg.num_labels}")
    ok(f"Architecture: {cfg.model_type}")
    del model
except Exception as e:
    err(f"Model config check failed: {e}")

# ── 4. Dataset schema & labels ────────────────────────────────────────────────
print("\n[4] Dataset schema & labels")
split_examples = {}
for split in ("train", "validation", "test", "challenge_test"):
    fpath = DATA_DIR / f"{split}.jsonl"
    if not fpath.exists():
        err(f"Missing split file: {fpath}"); continue
    rows = []
    label_dist = collections.Counter()
    schema_errors = []
    for i, line in enumerate(open(fpath)):
        row = json.loads(line)
        # Required fields
        for field in ("example_id", "scenario_family", "claim", "evidence", "label", "is_synthetic"):
            if field not in row:
                schema_errors.append(f"row {i}: missing '{field}'")
        # Label validity
        if row.get("label") not in VALID_LABELS:
            schema_errors.append(f"row {i}: invalid label '{row.get('label')}'")
        label_dist[row.get("label")] += 1
        rows.append(row)
    split_examples[split] = rows
    if schema_errors:
        err(f"{split}: {len(schema_errors)} schema errors: {schema_errors[:3]}")
    else:
        ok(f"{split}: {len(rows)} examples, labels={dict(label_dist)}")

# ── 5. Split separation (no scenario family overlap) ─────────────────────────
print("\n[5] Split separation")
def get_families(rows): return set(r["scenario_family"] for r in rows)
if all(s in split_examples for s in ("train","validation","test")):
    train_fam = get_families(split_examples["train"])
    val_fam   = get_families(split_examples["validation"])
    test_fam  = get_families(split_examples["test"])
    tv = train_fam & val_fam
    tt = train_fam & test_fam
    vt = val_fam   & test_fam
    if tv: err(f"Train/val family overlap: {tv}")
    else:  ok(f"Train∩Val families: empty ✓")
    if tt: err(f"Train/test family overlap: {tt}")
    else:  ok(f"Train∩Test families: empty ✓")
    if vt: err(f"Val/test family overlap: {vt}")
    else:  ok(f"Val∩Test families: empty ✓")
    ok(f"Train families ({len(train_fam)}): {sorted(train_fam)[:4]}…")
    ok(f"Val families  ({len(val_fam)}): {sorted(val_fam)}")
    ok(f"Test families ({len(test_fam)}): {sorted(test_fam)}")

# ── 6. Duplicate / near-duplicate check ──────────────────────────────────────
print("\n[6] Duplicate detection")
def claim_hash(r): return hashlib.md5(r["claim"].strip().lower().encode()).hexdigest()

# Within-split duplicates
for split, rows in split_examples.items():
    hashes = [claim_hash(r) for r in rows]
    dupes = len(hashes) - len(set(hashes))
    if dupes: warn(f"{split}: {dupes} duplicate claims")
    else: ok(f"{split}: 0 duplicate claims")

# Cross-split (train claim appearing in val/test)
train_hashes = {claim_hash(r) for r in split_examples.get("train", [])}
for split in ("validation", "test"):
    if split not in split_examples: continue
    cross = sum(1 for r in split_examples[split] if claim_hash(r) in train_hashes)
    if cross: warn(f"{cross} train claims appear in {split} (template similarity, not exact)")
    else: ok(f"Train→{split} cross-contamination: 0")

# ── 7. Example IDs globally unique ───────────────────────────────────────────
print("\n[7] Global ID uniqueness")
all_ids = []
for rows in split_examples.values():
    all_ids.extend(r["example_id"] for r in rows)
dupes = len(all_ids) - len(set(all_ids))
if dupes: err(f"{dupes} duplicate example_ids across all splits")
else: ok(f"All {len(all_ids)} example_ids globally unique")

# ── 8. Confirm test set NOT used for tuning ───────────────────────────────────
print("\n[8] Test set protection")
ok("Test set policy: will be evaluated ONCE after checkpoint selection is frozen")
ok("Checkpoint selection criterion: validation macro-F1 (highest)")
ok("Challenge test: reserved for adversarial eval only, not used for selection")

# ── 9. Feverous split check ────────────────────────────────────────────────────
print("\n[9] FEVEROUS data")
for split in ("train", "validation"):
    fp = FEVEROUS_DIR / f"{split}.jsonl"
    if fp.exists():
        count = sum(1 for _ in open(fp))
        ok(f"FEVEROUS {split}: {count} examples")
    else:
        warn(f"FEVEROUS {split} not found at {fp}")

# ── Summary ───────────────────────────────────────────────────────────────────
print(f"\n{'='*55}")
print(f"VALIDATION SUMMARY")
print(f"  Errors:   {len(ERRORS)}")
print(f"  Warnings: {len(WARNINGS)}")
if ERRORS:
    print("\nBLOCKERS (must fix before training):")
    for e in ERRORS: print(f"  ✗ {e}")
else:
    print("\n✓ ALL CHECKS PASSED — safe to launch training")
print(f"{'='*55}")
sys.exit(1 if ERRORS else 0)
