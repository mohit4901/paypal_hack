# ProofLedger AI

Source-grounded evidence compiler for PayPal digital-goods sellers.

## What it does

ProofLedger helps digital-product sellers verify whether the evidence available for a PayPal transaction adequately supports, contradicts, or is insufficient to establish each factual claim they want to make.

It combines:
- **Deterministic rule-based checks** (transparent, unit-tested)
- **Fine-tuned DeBERTa-v3 NLI model** (trained on synthetic domain data)
- **Tamper-evident event log** (SHA-256 hash chain)
- **FastAPI inference service**

> [!IMPORTANT]
> This system does NOT determine PayPal Seller Protection eligibility and does NOT automatically submit anything to PayPal. Human review is always required.

---

## Quick Start

```bash
cd ai/
pip3 install -r requirements.txt

# 1. Download and parse FEVEROUS
python3 -m src.data.download_feverous
python3 -m src.data.parse_feverous

# 2. Generate EvidenceBench (synthetic domain dataset)
python3 -m src.data.generate_evidencebench --seed 42 --target-count 10000

# 3. Run baselines
python3 -m src.training.evaluate_rules_baseline
python3 -m src.training.train_baseline

# 4. Run smoke test (verifies model + training pipeline)
python3 -m src.training.train_classifier --smoke-test

# 5. Fine-tune (full run — ~30 min/epoch on Apple Silicon)
python3 -m src.training.train_classifier \
    --data-dir data/processed/evidencebench \
    --base-model MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli \
    --output-dir artifacts/checkpoints/exp_001 \
    --epochs 5 --batch-size 8 --lr 2e-5

# 6. Evaluate on held-out test set (AFTER checkpoint selection is frozen)
python3 -m src.evaluation.evaluate \
    --model-path artifacts/checkpoints/exp_001/best \
    --split test

# 7. Run the inference API
uvicorn src.api.main:app --port 8000

# 8. Run all tests
python3 -m pytest tests/ -v
```

---

## Project Structure

```
ai/
├── config/               Training, evaluation, and inference YAML configs
├── data/
│   ├── raw/feverous/     Downloaded FEVEROUS files (71K train, 7.9K val)
│   ├── interim/          Intermediate processing outputs
│   └── processed/
│       ├── feverous/     Parsed FEVEROUS (79K examples, 0 excluded)
│       ├── evidencebench/Generated domain dataset (6.6K train, 1.6K val/test, 400 challenge)
│       └── paypal_sandbox/ PayPal sandbox integration results
├── src/
│   ├── data/             Download, parse, generate, validate scripts
│   ├── models/           Labels, input formatter, verifier, compiler, validator
│   ├── training/         Train classifier, baselines, experiments, checkpoint selection
│   ├── evaluation/       Evaluate, error analysis, generate report
│   ├── api/              FastAPI main, schemas
│   ├── integrations/     PayPal client, sandbox tests, webhook verifier
│   └── utils/            Reproducibility, logging (secret-redacting)
├── tests/unit/           48 unit tests (all passing)
├── artifacts/
│   ├── baseline/         Rules-only and TF-IDF+LR baseline results
│   ├── checkpoints/      Per-epoch and best model checkpoints
│   ├── best_model/       Selected final model
│   └── reports/          Evaluation JSON reports
├── docs/
│   ├── MODEL_CARD.md
│   ├── DATASET_CARD.md
│   ├── EXPERIMENT_REPORT.md
│   ├── PAYPAL_INTEGRATION.md
│   └── LIMITATIONS.md
├── requirements.txt      Pinned dependencies
├── pyproject.toml
└── .env.example          Environment variable template (no secrets)
```

---

## Datasets

| Dataset | Type | Size | Licence |
|---|---|---|---|
| FEVEROUS | Public / downloaded | 71K+7.9K | CC BY-SA 3.0 |
| EvidenceBench | Synthetic / generated | 10K total | Proprietary |
| PayPal Sandbox | API integration | — | PayPal TOS |

---

## Baseline Results (Measured)

| Model | Dataset | Split | Accuracy | Macro-F1 | Contradiction Recall |
|---|---|---|---:|---:|---:|
| Rules-only | EvidenceBench | validation | 0.4123 | 0.1946 | 0.0000 |
| Rules-only | EvidenceBench | test | 0.7500 | 0.7333 | 0.5000 |
| TF-IDF + LR | EvidenceBench | validation | 0.4531 | 0.4524 | 0.5439 |
| TF-IDF + LR | EvidenceBench | test | 0.2752 | 0.1835 | 0.0829 |
| Fine-tuned DeBERTa | EvidenceBench | test | *see reports/* | *see reports/* | *see reports/* |

The TF-IDF collapse on the held-out test split (0.45 → 0.18 macro-F1) confirms the group-based split effectively prevents template leakage.

---

## API

```
GET  /health                  Service health check
GET  /model/info              Model version, architecture, label mapping
POST /predict                 Verify a single claim against evidence
POST /batch-predict           Verify up to 50 claims
POST /validate-evidence       Deterministic checks only (no ML)
GET  /metrics                 Precomputed evaluation summaries
```

**Example request:**
```json
POST /predict
{
  "claim": "PayPal confirmed the payment capture for order ord_123.",
  "evidence": [
    {
      "evidence_id": "cap_001",
      "source_type": "paypal_api",
      "timestamp": "2025-10-09T10:30:00Z",
      "content": "Capture cap_001 status=COMPLETED order=ord_123."
    }
  ]
}
```

---

## PayPal Integration

PayPal sandbox credentials are required for integration tests:

```bash
export PAYPAL_CLIENT_ID=your_sandbox_client_id
export PAYPAL_CLIENT_SECRET=your_sandbox_client_secret
python3 -m src.integrations.paypal_sandbox_tests
```

Without credentials: all PayPal tests are reported as BLOCKED (not failed).

Required scope for dispute operations: `CUSTOMER_DISPUTE.READ` + `CUSTOMER_DISPUTE.UPDATE`

See `docs/PAYPAL_INTEGRATION.md` for full details.

---

## Tests

```bash
python3 -m pytest tests/ -v
# 48 passed, 0 failed (all unit tests pass without model or API credentials)
```

Test categories: label conversion, input formatting, EvidenceBench generation, deterministic validator, evidence compiler, hash chain tamper detection, API schemas, PayPal client (mocked), FEVEROUS parser.

---

## Limitations

See `docs/LIMITATIONS.md` for a full list. Key points:

- Training data is **entirely synthetic** — real-world performance is unvalidated
- Confidence scores are **uncalibrated** raw softmax outputs
- System does **not** determine PayPal Seller Protection eligibility
- Hash chain indicates tampering but does **not** prove original event truth

---

## Licence

Base model (`MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli`): MIT  
FEVEROUS dataset: CC BY-SA 3.0  
EvidenceBench: Proprietary (synthetic)  
ProofLedger AI code: Proprietary
