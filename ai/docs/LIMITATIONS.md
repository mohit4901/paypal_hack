# Limitations — ProofLedger AI System

## 1. Training Data Limitations

### Synthetic-only training
The EvidenceBench dataset is entirely synthetic. It was generated programmatically with deterministic rules. The model has **never been trained on real PayPal dispute evidence, real delivery records, or real customer transactions.**

Measured performance on EvidenceBench does **not** establish real-world performance.

### Template sensitivity
The TF-IDF baseline achieves macro-F1=0.45 on validation but only 0.18 on the held-out test split. This collapse confirms that models trained on synthetic templates can learn surface patterns rather than reasoning about claim/evidence relationships. The fine-tuned DeBERTa model may partially overcome this, but this risk is not eliminated.

### FEVEROUS domain mismatch
FEVEROUS covers general Wikipedia fact verification. PayPal digital-goods disputes are a narrow, specialized domain with different vocabulary, evidence types, and reasoning patterns. Transfer from FEVEROUS is not guaranteed.

## 2. Model Limitations

### Uncalibrated confidence scores
The `confidence` field is a raw softmax output. It has **not been calibrated** against held-out data. A confidence of 0.9 does **not** mean the claim has a 90% probability of being supported. Calibration against actual ground-truth labels using temperature scaling or isotonic regression would be required to make probabilistic interpretations.

### Evidence truncation
When evidence exceeds the maximum context length (256 tokens), it is truncated. The system explicitly flags truncation via `truncated: true` and a `truncation_warning`. However, truncation may silently discard the record that would contradict a claim.

### Context window constraints
The tokenizer's maximum length limits how much evidence can be processed in a single forward pass. Very long evidence chains (e.g., complete transaction histories) may require evidence chunking, which introduces aggregation decisions that can affect results.

### No chain-of-thought reasoning
The model produces a label without an explicit evidence trace. It cannot reliably identify *which* evidence record caused a particular prediction. The `supporting_evidence_ids` and `contradicting_evidence_ids` in the API response are heuristic assignments from the deterministic validator, not model-generated attributions.

## 3. Deterministic Validator Limitations

### Keyword-based pattern matching
The rule-based validator uses simple keyword and regex patterns. It may miss subtle contradictions expressed in unusual language. It may also produce false positives if irrelevant evidence contains matching keywords.

### No semantic understanding
The rules cannot detect paraphrased contradictions, implicit contradictions, or contradictions that require combining information across records.

## 4. Evidence Compiler Limitations

### Hash chain scope
The tamper-evident event log uses a SHA-256 hash chain. This can detect whether a **logged** event was modified after the fact. It cannot:
- Prove that the original event actually occurred.
- Prevent fabrication of the first event.
- Detect if the log file itself was replaced.
- Provide cryptographic provenance of external source records.

The hash chain is a tamper-**indication** mechanism, not a provenance guarantee.

## 5. PayPal Integration Limitations

### Sandbox credentials not included
PayPal sandbox credentials must be provided by the user. Without them, all PayPal-dependent tests are blocked.

### Dispute API access requires special permissions
The `CUSTOMER_DISPUTE.READ` and `CUSTOMER_DISPUTE.UPDATE` scopes require explicit permission grants in the PayPal Developer Dashboard. Standard sandbox accounts may not have these permissions.

### No production integration
This system is implemented for **sandbox use only**. Live production integration requires:
- PayPal Live credentials (separate from sandbox)
- Compliance review
- Webhook endpoint exposed to the internet
- Rate limit handling in production volumes

## 6. What This System Does NOT Do

| Claim | Reality |
|---|---|
| "Dispute will be won" | The system cannot predict dispute outcomes |
| "Seller Protection applies" | Only PayPal can determine Seller Protection eligibility |
| "Evidence verified by PayPal" | The system verifies internal consistency; PayPal has not reviewed any output |
| "Submitted to PayPal" | Nothing is submitted without explicit human approval and a real API call |
| "Customer downloaded the file" | If no download event is in the records, this cannot be established |
| "Model is state of the art" | The model is fine-tuned on synthetic data; no external benchmarks have been run |

## 7. Recommended Mitigations

1. Obtain real-world labelled examples and evaluate on them before deployment.
2. Calibrate confidence scores using validation data.
3. Implement human review for all predictions before any submission.
4. Add retrieval-based evidence grounding for long transaction histories.
5. Test with actual PayPal sandbox credentials and real dispute flows.
6. Run periodic model performance audits as PayPal API responses evolve.
7. Do not use this system for high-stakes decisions without independent legal review.

