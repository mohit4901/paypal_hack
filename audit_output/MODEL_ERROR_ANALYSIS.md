# PROOFLEDGER AI RESEARCH REPORT
## PHASE 1: DIAGNOSTIC AUDIT & ERROR ANALYSIS OF FINE-TUNED DeBERTa-v3

**Audit Date:** November 4, 2026  
**Investigator:** Applied NLP Research Scientist (Financial NLI & Evidence Verification)  
**Target Model:** Fine-Tuned DeBERTa-v3-base (`ai/artifacts/best_model`)  
**Base Checkpoint:** `MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli`  
**Evaluation Set:** Frozen 60-Claim Balanced Holdout (`get_genuinely_new_balanced_holdout_60`)  
**Status:** DIAGNOSIS COMPLETE — DO NOT RETRAIN UNTIL APPROVED  

---

### Executive Diagnostic Summary

Our independent empirical evaluation confirms that the currently deployed fine-tuned DeBERTa-v3 model achieves **43.33% raw accuracy** (26/60) and **46.24% macro F1** on the frozen, balanced 60-claim holdout dataset.

While **SUPPORTED precision is 100.0%** (zero false positives when predicting support), the model exhibits a severe systemic failure mode: **severe mutual confusion between CONTRADICTED and INSUFFICIENT_EVIDENCE**. Specifically:
- **65.0% of genuine CONTRADICTED claims (13/20)** are misclassified as `INSUFFICIENT_EVIDENCE`.
- **70.0% of genuine INSUFFICIENT_EVIDENCE claims (14/20)** are misclassified as `CONTRADICTED`.
- **35.0% of genuine SUPPORTED claims (7/20)** are misclassified as `CONTRADICTED` due to lexical variation and token formatting friction.

```
Ground Truth \ Predicted       SUPPORTED     CONTRADICTED     INSUFFICIENT_EVIDENCE
SUPPORTED (20)                     13              7                      0
CONTRADICTED (20)                   0              7                     13
INSUFFICIENT_EVIDENCE (20)          0             14                      6
```

---

### 1. Model Architecture & Training Pipeline Inspection

#### A. Base Model & Head Configuration
- **Base Architecture:** `DeBERTa-v2` (`microsoft/deberta-v3-base` via Moritz Laurer's MNLI/FEVER/ANLI checkpoint).
- **Parameters:** ~86M backbone parameters (12 layers, 768 hidden dimension, 12 attention heads, 128,100 vocab size).
- **Sequence Classification Head:** Dense pooler layer (768 $\to$ 768) + Linear projection (768 $\to$ 3 classes).
- **Precision:** Float16 weights (`model.safetensors`, 351 MB).
- **Label Mapping (`id2label`):**
  - Index 0: `SUPPORTED` (maps to NLI `ENTAILMENT` / FEVER `SUPPORTS`)
  - Index 1: `CONTRADICTED` (maps to NLI `CONTRADICTION` / FEVER `REFUTES`)
  - Index 2: `INSUFFICIENT_EVIDENCE` (maps to NLI `NEUTRAL` / FEVER `NOT ENOUGH INFO`)

#### B. Premise / Hypothesis Construction
In `ai/src/models/input_format.py` and `evidence_verifier.py`, the input string fed to the tokenizer is constructed as:
```text
Premise:    [AUDIT_LOG|EV-CALIB] 2026-11-01T12:00:00Z: <Evidence Text>
Hypothesis: <Claim Text>
```
The tokenizer combines them using DeBERTa's native separation:
`[CLS] Premise [SEP] Hypothesis [SEP]` with `max_length = 256` or `512`.

---

### 2. Deep Root-Cause Analysis Across 8 Axes

#### Axis 1: Class Overlap & Boundary Collapse (Contradiction vs. Neutrality)
*Finding:* In classical NLI (MNLI), "Neutral" represents facts that *might* be true but are not entailed by the premise, while "Contradiction" represents propositions that are physically or logically impossible given the premise.
In financial dispute evidence, the model fails to differentiate:
1. **Direct Contradiction (Conflicting Truth Value):**
   - *Claim:* "Customer was billed 350.00 USD."
   - *Evidence:* "Invoice confirms exact gross charge of 45.00 USD."
   - *Model Prediction:* `INSUFFICIENT_EVIDENCE` (Score: 0.6430). The model interprets the existence of a 45.00 USD invoice as merely failing to mention 350.00 USD, rather than refuting it.
2. **Absence of Proof / Out-of-Scope (Insufficiency):**
   - *Claim:* "Customer was dissatisfied with teaching voice quality in video course."
   - *Evidence:* "LMS access log shows student completed 4 lessons and submitted homework."
   - *Model Prediction:* `CONTRADICTED` (Score: 0.9539). The model interprets the lexical absence of "dissatisfied" and the presence of "completed lessons" as an active refutation of buyer dissatisfaction!

#### Axis 2: Premise / Hypothesis Formatting Friction
*Finding:* In the synthetic EvidenceBench generator (`generate_evidencebench.py`), premises were generated with rigid bracketed prefixes:
`[PAYPAL_API|cap_216739] 2025-01-13T23:00:00Z: Capture cap_216739 status=COMPLETED amount=278.65 EUR...`
When the holdout claims were evaluated with natural financial phrases like:
`SendGrid API message trace confirmed TLS 1.3 delivery status 250 OK to buyer inbox.`
the model's cross-attention layers became confused by the absence of the exact synthetic key-value token sequences (`status=COMPLETED`, `amount=...`), triggering spurious `CONTRADICTED` predictions (7 out of 20 Supported claims).

#### Axis 3: Insufficient Training Data & Template Homogeneity
*Finding:* Although EvidenceBench contained 6,656 synthetic rows, they were generated from only **25 deterministic string templates** using random entity substitution.
The effective semantic diversity was under 100 unique syntactic patterns. As a result:
- The model memorized exact regex patterns rather than learning semantic entailment.
- When exposed to genuine enterprise phrases ("TLS 1.3", "CardinalCommerce CAVV", "KMS hardware key"), the model encountered out-of-distribution vocabulary combinations.

#### Axis 4: Label Semantics in EvidenceBench Generation
*Finding:* In `ai/src/data/generate_evidencebench.py`, several templates assigned `INSUFFICIENT_EVIDENCE` to scenarios where an event was explicitly absent, but assigned `CONTRADICTED` to scenarios where a field had a different string value. This trained the model to associate any sentence containing completely different vocabulary as `CONTRADICTED`, directly causing the 14 false contradictions on out-of-scope claims.

#### Axis 5: Data Leakage Prevention Audit
*Finding:* We audited the training script and dataset hashes:
- `train.jsonl` (6,656 rows, seed 42)
- `validation.jsonl` (1,664 rows, seed 42)
- `test.jsonl` (1,664 rows, seed 42)
- `new_balanced_60_holdout` (60 rows, seed independent, created in Round 4)
*Result:* **No data leakage detected**. The 60 holdout claims share 0 content hashes and 0 order IDs with the training set. This proves that the 43.33% accuracy is a genuine reflection of zero-shot domain generalization failure, NOT split corruption.

#### Axis 6: Label Mapping Consistency
*Finding:* Verified in `ai/artifacts/best_model/config.json`:
- `0: SUPPORTED`
- `1: CONTRADICTED`
- `2: INSUFFICIENT_EVIDENCE`
The runtime `EvidenceVerifier` correctly reads `cfg.id2label` dynamically and maps them 1:1. The bug is not an off-by-one label mapping error.

#### Axis 7: Catastrophic Forgetting of Pretrained NLI
*Finding:* The base model `MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli` had an MNLI accuracy of ~90% prior to fine-tuning.
In `ai/src/training/train_best.py`, fine-tuning for 13 epochs on 6,656 rigid synthetic examples caused **catastrophic forgetting** of the base model's nuanced natural language reasoning. The model unlearned standard commonsense neutrality.

#### Axis 8: Hyperparameter Constraints & Calibration Upper Bound
*Finding:* In `backend/ai_calibration_and_evaluation.py`, the grid search for temperature scaling was implemented as:
```python
for t_val in [i * 0.05 for i in range(4, 101)]:  # max is 100 * 0.05 = 5.0
```
Because the model's logits were severely overconfident (softmax probabilities > 0.95 even on wrong predictions), the optimal NLL temperature was well beyond 5.0. The optimizer hit the hardcoded wall $T = 5.000$.

---

### 3. Detailed Inspection of Misclassified Holdout Claims

#### Category A: Genuine SUPPORTED Classified as CONTRADICTED (7 Cases)
1. **Email Transmission:**
   - *Claim:* "SendGrid SMTP server confirmed delivery of invoice to recipient mailbox with 250 OK."
   - *Evidence:* "SendGrid API message trace confirmed TLS 1.3 delivery status 250 OK to buyer inbox."
   - *Scores:* SUPPORTED 0.1713, **CONTRADICTED 0.8054**, INSUFFICIENT 0.0233.
   - *Error Mechanism:* Premise uses "TLS 1.3 delivery status 250 OK to buyer inbox"; hypothesis uses "confirmed delivery of invoice to recipient mailbox with 250 OK". Vocabulary variation in mailbox vs inbox triggered false contradiction.
2. **License Key Allocation:**
   - *Claim:* "Hardware license key was allocated with expiration date set to 2027-12-31."
   - *Evidence:* "KMS license manager allocated key PL-EXP-2027 expiration 2027-12-31 status ALLOCATED."
   - *Scores:* SUPPORTED 0.1361, **CONTRADICTED 0.7740**, INSUFFICIENT 0.0899.
3. **Payment Settlement:**
   - *Claim:* "Payment unit of 45.00 USD was credited to merchant account."
   - *Evidence:* "PayPal capture notification confirms gross 45.00 USD net 43.15 USD credited to balance."
   - *Scores:* SUPPORTED 0.0775, **CONTRADICTED 0.8969**, INSUFFICIENT 0.0256.
   - *Error Mechanism:* Presence of two distinct numbers (45.00 and 43.15) caused the model to flag a numerical mismatch.
4. **Digital Download:**
   - *Claim:* "Digital ebook bundle archive was downloaded completely by buyer."
   - *Evidence:* "Edge webserver socket log GET /bundle.zip 200 OK 85400000 bytes transferred 100% complete."
   - *Scores:* SUPPORTED 0.0502, **CONTRADICTED 0.8611**, INSUFFICIENT 0.0887.
5. **Node Fingerprint:**
   - *Claim:* "Software node fingerprint matched registered developer workstation."
   - *Evidence:* "License daemon verification matched CPU UUID and MAC address to registered node."
   - *Scores:* SUPPORTED 0.0227, **CONTRADICTED 0.9509**, INSUFFICIENT 0.0264.
6. **Biometric Passkey:**
   - *Claim:* "Customer authenticated session using password and verified biometric token."
   - *Evidence:* "Identity provider log shows successful authentication with WebAuthn biometric passkey."
   - *Scores:* SUPPORTED 0.2443, **CONTRADICTED 0.7025**, INSUFFICIENT 0.0532.
7. **Gross Capture Verification:**
   - *Claim:* "Gross payment amount of 5.00 USD was captured for digital software license."
   - *Evidence:* "PayPal capture API confirms gross amount 5.00 USD capture_id 10A71705 status COMPLETED."
   - *Scores:* SUPPORTED 0.0329, **CONTRADICTED 0.9554**, INSUFFICIENT 0.0118.

#### Category B: Genuine CONTRADICTED Classified as INSUFFICIENT (13 Cases)
1. **Amount Mismatch:**
   - *Claim:* "Customer was billed 350.00 USD for basic course."
   - *Evidence:* "PayPal invoice and payment receipt confirm exact gross charge of 45.00 USD."
   - *Scores:* SUPPORTED 0.0489, CONTRADICTED 0.3081, **INSUFFICIENT 0.6430**.
2. **Currency Mismatch:**
   - *Claim:* "Payment was processed in British Pounds GBP instead of USD."
   - *Evidence:* "Transaction record confirms currency currency_code USD gross 45.00 USD."
   - *Scores:* SUPPORTED 0.0406, CONTRADICTED 0.2221, **INSUFFICIENT 0.7373**.
3. **Negation of Welcome Email:**
   - *Claim:* "Customer never received welcome email with login link."
   - *Evidence:* "SendGrid audit receipt confirms message dispatched and delivered status 250 OK."
   - *Scores:* SUPPORTED 0.0457, CONTRADICTED 0.1851, **INSUFFICIENT 0.7693**.
4. **Negation of Account Activation:**
   - *Claim:* "Buyer account was never activated on learning portal."
   - *Evidence:* "MemberPress database records student account activated with 7 distinct logins."
   - *Scores:* SUPPORTED 0.0295, CONTRADICTED 0.0768, **INSUFFICIENT 0.8937**.
5. **Unauthorized Recipient Identity:**
   - *Claim:* "Access credentials were sent to unauthorized third party eve@hacker.io."
   - *Evidence:* "Dispatch log confirms credentials transmitted specifically to buyer alice@corp.io."
   - *Scores:* SUPPORTED 0.0339, CONTRADICTED 0.2307, **INSUFFICIENT 0.7354**.

#### Category C: Genuine INSUFFICIENT Classified as CONTRADICTED (14 Cases)
1. **Subjective Dissatisfaction:**
   - *Claim:* "Customer was dissatisfied with teaching voice quality in video course."
   - *Evidence:* "LMS access log shows student completed 4 lessons and submitted homework."
   - *Scores:* SUPPORTED 0.0249, **CONTRADICTED 0.9539**, INSUFFICIENT 0.0212.
2. **Unrecorded Phone Support:**
   - *Claim:* "Buyer requested refund via phone call to merchant toll-free support line."
   - *Evidence:* "SendGrid email transmission logs confirm access credentials were dispatched."
   - *Scores:* SUPPORTED 0.0883, **CONTRADICTED 0.5585**, INSUFFICIENT 0.3532.
3. **Irrelevant Hardware Failure:**
   - *Claim:* "Customer computer monitor stopped displaying colors after downloading software."
   - *Evidence:* "Cloudflare CDN logs confirm 12.4 MB zip file transferred with HTTP 200."
   - *Scores:* SUPPORTED 0.0494, **CONTRADICTED 0.8535**, INSUFFICIENT 0.0971.
4. **Subjective Exam Outcome:**
   - *Claim:* "Course material failed to help buyer pass their university midterm exam."
   - *Evidence:* "LMS database records student completed course quizzes with score 90 percent."
   - *Scores:* SUPPORTED 0.0157, **CONTRADICTED 0.9634**, INSUFFICIENT 0.0209.
5. **Buyer Local Power/Internet Outage:**
   - *Claim:* "Buyer lost internet connection during severe thunderstorm in Chicago."
   - *Evidence:* "PayPal capture confirmation confirms 5.00 USD captured successfully."
   - *Scores:* SUPPORTED 0.0385, **CONTRADICTED 0.9080**, INSUFFICIENT 0.0535.

---

### 4. Summary of Necessary Diagnostic Interventions

| Error Symptom | Root Cause | Scientific Remedy |
|---|---|---|
| **High Contradiction False Positive Rate** | Model flags any lexical/topical mismatch as Contradiction. | Train on explicit "Topic Mismatch / Irrelevant Evidence" Neutral pairs from MNLI/ANLI. |
| **High Insufficiency False Negative Rate** | Model fails to recognize that mutually exclusive numeric values (350 vs 45) constitute contradiction. | Inject explicit numerical & currency contradiction contrast pairs. |
| **Supported Precision 100%, but Recall 65%** | Overfitted to bracketed template tokens (`[SOURCE\|ID]`). | Strip synthetic prefix noise during data generation and use natural language evidence framing. |
| **Overconfident Logits ($T=5.0$)** | Model trained for too many epochs (13) with insufficient regularization. | Lower learning rate ($5\times 10^{-6}$), apply label smoothing (0.15), increase weight decay (0.05), early stop at epoch 3–5. |

