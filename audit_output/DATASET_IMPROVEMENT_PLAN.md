# PROOFLEDGER AI RESEARCH REPORT
## PHASE 2: DATASET IMPROVEMENT PROPOSAL & SYNTHETIC INR SPECIFICATION

**Audit Date:** November 4, 2026  
**Investigator:** Applied NLP Research Scientist  
**Focus:** Resolving CONTRADICTED vs INSUFFICIENT_EVIDENCE Boundary Confusion  
**Application Domain:** PayPal Merchant Dispute Evidence Verification (INR & Digital Fulfillment)  

---

### 1. Conceptual Framework: Factual Contradiction vs. Evidentiary Insufficiency

To eliminate the 65–70% mutual misclassification between `CONTRADICTED` and `INSUFFICIENT_EVIDENCE`, the training data must instantiate a rigorous mathematical and linguistic distinction:

| Formal Property | `CONTRADICTED` (Factual Disproof) | `INSUFFICIENT_EVIDENCE` (Information Gap) |
|---|---|---|
| **Semantic Definition** | The available verified evidence **directly negates** or is **logically incompatible** with the claim. | The evidence **neither establishes nor refutes** the claim. The claim may be true or false; evidence is silent or orthogonal. |
| **Truth Value Relationship** | $P(\text{Claim} \mid \text{Evidence}) \approx 0$ | $0 < P(\text{Claim} \mid \text{Evidence}) < 1$ (Indeterminate) |
| **Typical PayPal Scenario** | Carrier GPS shows delivery to recipient address, but buyer claims non-receipt. | Tracking number exists, but carrier shows "Label Created — Awaiting Package". |
| **Legal / Dispute Significance** | Merchant has affirmative counter-evidence to win the dispute. | Merchant has incomplete proof; case requires merchant follow-up before submission. |

---

### 2. 12 Realistic PayPal INR Scenario Families (Contrastive Pairs)

The proposed expanded dataset (`EvidenceBench-v2`) defines 12 core scenario families specifically crafted with side-by-side **Hard Contradiction** vs. **Hard Insufficient** variants:

#### Scenario 1: Delivery Confirmation vs. Missing Carrier Scan
- *Claim:* "I never received the merchandise ordered."
- **Variant A (CONTRADICTED):** Verified carrier record confirms package delivered to linked street address and signed by cardholder on 2026-11-01.  
  $\implies$ *Contradicts buyer's claim of non-receipt.*
- **Variant B (INSUFFICIENT_EVIDENCE):** Carrier record confirms tracking number generated and parcel accepted at post office, but no delivery scan exists.  
  $\implies$ *Insufficient to prove delivery.*

#### Scenario 2: Label Created vs. Parcel Not Collected
- *Claim:* "Merchant never dispatched my goods."
- **Variant A (CONTRADICTED):** Carrier scan shows parcel was picked up by courier van at merchant warehouse and scanned at sorting hub.  
  $\implies$ *Directly refutes non-dispatch.*
- **Variant B (INSUFFICIENT_EVIDENCE):** Shipping system shows label created by merchant software, but carrier API shows "Pre-Shipment: Carrier awaiting item".  
  $\implies$ *Label generation alone does not prove physical handover.*

#### Scenario 3: Parcel in Transit
- *Claim:* "The item was delivered to the wrong house."
- **Variant A (CONTRADICTED):** Proof of delivery photograph and geocode coordinates match buyer's verified PayPal shipping address.  
  $\implies$ *Refutes wrong-house claim.*
- **Variant B (INSUFFICIENT_EVIDENCE):** Parcel is currently marked "In Transit — Out for Delivery" with no completed delivery scan.  
  $\implies$ *Cannot determine if final delivery will be correct or wrong.*

#### Scenario 4: Wrong Recipient Name / Address
- *Claim:* "Package was addressed and delivered to an unrelated person in another state."
- **Variant A (CONTRADICTED):** Waybill and recipient manifest confirm shipping address matches buyer's PayPal checkout address in Austin, TX.  
  $\implies$ *Refutes out-of-state claim.*
- **Variant B (INSUFFICIENT_EVIDENCE):** Carrier record shows delivery to zip code 78701, but does not display recipient name or street address.  
  $\implies$ *Zip-code match alone is insufficient under PayPal strict Seller Protection.*

#### Scenario 5: Partial Fulfillment
- *Claim:* "The order contained 3 items, but only 1 item was in the box."
- **Variant A (CONTRADICTED):** Warehouse weigh-scale log shows dispatched package weighed 4.8 kg, matching the exact combined weight of all 3 items.  
  $\implies$ *Strong physical contradiction of single-item weight (1.6 kg).*
- **Variant B (INSUFFICIENT_EVIDENCE):** Packing slip lists all 3 items, but carrier record contains no weight telemetry or multi-package trace.  
  $\implies$ *Packing slip alone does not prove all items were packed.*

#### Scenario 6: Order ID & Transaction Reference Mismatch
- *Claim:* "This payment was for Order ORD-991, not ORD-102."
- **Variant A (CONTRADICTED):** PayPal checkout capture API explicitly binds payment transaction `10A71705` to Order `ORD-991`.  
  $\implies$ *Direct relational contradiction.*
- **Variant B (INSUFFICIENT_EVIDENCE):** PayPal transaction record lists payment gross amount, but internal custom field `invoice_id` is blank.  
  $\implies$ *Insufficient linkage.*

#### Scenario 7: Conflicting Carrier Records
- *Claim:* "The package was returned to sender."
- **Variant A (CONTRADICTED):** Carrier supervisor investigation note confirms "Return to Sender" scan was an operator error; package was re-delivered and accepted on 2026-11-02.  
  $\implies$ *Refutes return status.*
- **Variant B (INSUFFICIENT_EVIDENCE):** Carrier tracking log shows "Exception: Delivery Attempted" followed by two conflicting scans on the same day.  
  $\implies$ *Conflicting evidence requires human carrier reconciliation.*

#### Scenario 8: Missing Delivery Evidence (FORMAT_VALID Trap)
- *Claim:* "Buyer states: I paid, but never received the tracking information."
- **Variant A (CONTRADICTED):** Automated email dispatch log confirms tracking number and tracking URL were sent to buyer's registered email with SMTP 250 OK.  
  $\implies$ *Refutes non-communication claim.*
- **Variant B (INSUFFICIENT_EVIDENCE):** Merchant database contains a valid USPS tracking number `9400111899223192348571`, but dispatch timestamp is null.  
  $\implies$ *Format is valid, but dispatch proof is insufficient.*

#### Scenario 9: Digital Fulfillment Without Access Logs
- *Claim:* "I purchased access to the developer course but was locked out."
- **Variant A (CONTRADICTED):** Identity provider logs 14 successful user logins, 3 completed module exams, and active certificate generation.  
  $\implies$ *Refutes lockout claim.*
- **Variant B (INSUFFICIENT_EVIDENCE):** Stripe/PayPal receipt confirms payment captured, but learning management system shows account status "Pending Email Verification".  
  $\implies$ *Insufficient to prove access was successfully delivered.*

#### Scenario 10: Refund Already Processed
- *Claim:* "Merchant refused to refund my money after cancellation."
- **Variant A (CONTRADICTED):** PayPal REST API shows refund transaction `REF-88192` completed for gross amount with credit back to buyer card.  
  $\implies$ *Direct factual refutation.*
- **Variant B (INSUFFICIENT_EVIDENCE):** Merchant internal support ticket is marked "Refund Approved", but PayPal refund API call was never dispatched.  
  $\implies$ *Internal approval alone does not constitute completed financial refund.*

#### Scenario 11: Multiple Packages Under Single Order
- *Claim:* "Package 2 of 2 never arrived."
- **Variant A (CONTRADICTED):** Carrier confirms tracking numbers `TRACK-A` and `TRACK-B` both show completed signed delivery on 2026-11-01.  
  $\implies$ *Refutes missing second parcel.*
- **Variant B (INSUFFICIENT_EVIDENCE):** Carrier confirms `TRACK-A` delivered, but `TRACK-B` has zero tracking updates since dispatch.  
  $\implies$ *Insufficient proof for the full order.*

#### Scenario 12: Buyer Subjective Complaints & Orthogonal Context
- *Claim:* "The item was delivered, but the packaging color was ugly and customer support was rude."
- **Variant A (INSUFFICIENT_EVIDENCE):** Delivery confirmation proves physical fulfillment, but cannot verify customer support tone.  
  $\implies$ *Proof of delivery is orthogonal to subjective merchant interaction.*
- **Variant B (INSUFFICIENT_EVIDENCE):** Buyer claims delivery truck damaged their driveway. Delivery record confirms parcel drop-off.  
  $\implies$ *Delivery proof neither proves nor disproves peripheral property damage.*

---

### 3. Contrastive Hard-Negative Pairs (Direct Comparison)

| Pair ID | Claim | Evidence Text | Correct Label | Explanation |
|---|---|---|:---:|---|
| **CP-01** | "Order was never delivered." | "USPS tracking 94001... shows Delivered In/At Mailbox on 2026-11-02." | `CONTRADICTED` | Affirmative delivery scan disproves non-delivery. |
| **CP-02** | "Order was never delivered." | "USPS tracking 94001... shows Accepted at USPS Origin Facility." | `INSUFFICIENT_EVIDENCE` | Origin acceptance is evidence of transit, NOT delivery. |
| **CP-03** | "Customer was charged $150.00." | "PayPal capture details confirm gross charge of $45.00 USD." | `CONTRADICTED` | Exact numerical conflict on same transaction. |
| **CP-04** | "Customer was charged $150.00." | "Order confirmation email mentions upcoming annual renewal." | `INSUFFICIENT_EVIDENCE` | Mention of renewal does not confirm or refute current charge amount. |
| **CP-05** | "Merchant sent goods to wrong address." | "Shipping label created for 742 Evergreen Terrace; buyer registered address is 742 Evergreen Terrace." | `CONTRADICTED` | Address match directly refutes wrong-address claim. |
| **CP-06** | "Merchant sent goods to wrong address." | "Shipping label created with tracking 1Z999; destination street address suppressed in carrier privacy feed." | `INSUFFICIENT_EVIDENCE` | Suppressed street address cannot prove address correctness. |

---

### 4. Split Strategy & Data Leakage Prevention

To guarantee 100% scientific integrity, the expanded dataset will enforce **Strict Merchant & Order-Level Grouping**:

```mermaid
flowchart TD
    RawData["Raw Generated Scenario Pairs (N = 3,000)"]
    Group["Group by Merchant ID & Order Hash"]
    RawData --> Group
    
    Group -->|60% Merchants (Zero overlap)| TrainSplit["Training Partition (N = 1,800)"]
    Group -->|20% Merchants (Zero overlap)| ValSplit["Validation Partition (N = 600)<br>Hyperparameter Tuning & Temperature Scaling"]
    Group -->|20% Merchants (Zero overlap)| TestSplit["Test Partition (N = 600)"]
    
    Frozen["Existing 60-Claim Balanced Holdout"] -.->|STRICTLY UNTOUCHED| FinalEval["Final Benchmark Comparison"]
```

1. **Merchant-Level Splitting:** All claims, evidence records, and paraphrases relating to a specific merchant or transaction are assigned exclusively to ONE split. No cross-split entity leakage.
2. **Frozen Holdout Preservation:** The existing 60-claim balanced holdout (`get_genuinely_new_balanced_holdout_60`) is **NEVER** exposed to training or validation. It remains the strict external test oracle.
3. **Synthetic Transparency:** Every generated example contains `is_synthetic: true` and an explicit `generation_rationale`. No synthetic record uses genuine personal or merchant data.

---

### 5. Target Class Distribution Plan

| Class | Current Dataset (EvidenceBench-v1) | Proposed Improved Dataset (v2) | Target Split Ratio |
|---|:---:|:---:|:---:|
| `SUPPORTED` | 33.3% (template-based) | 33.3% (natural financial fulfillment) | 1,000 pairs |
| `CONTRADICTED` | 33.3% (token substitutions) | 33.3% (explicit logical contradictions) | 1,000 pairs |
| `INSUFFICIENT_EVIDENCE` | 33.3% (missing records) | 33.3% (hard negatives, partial proof, orthogonal) | 1,000 pairs |
| **Total Pairs** | **850 (active subset) / 6,656** | **3,000 curated pairs** | **100% Balanced** |

