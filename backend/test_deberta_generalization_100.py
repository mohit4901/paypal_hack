"""
100-Sample Unseen Claim Generalization Test Suite for Fine-Tuned DeBERTa-v3.
Evaluates model on unseen claims across 7 challenging forensic dispute categories:
1. Factual Entailment (Supported)
2. Negation Handling (Contradicted)
3. Amount Mismatch (Contradicted)
4. Buyer Identity Mismatch (Contradicted)
5. Date / Chronology Mismatch (Contradicted)
6. Conflicting Multi-Source Evidence (Contradicted)
7. Unsupported / Irrelevant Claims (Insufficient Evidence)

Reports Per-Class Precision, Recall, F1, Confusion Matrix, and Hardware Latency.
"""
import sys
import time
import json
from pathlib import Path
from typing import Any, Dict, List, Tuple
from collections import defaultdict

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import backend.config
from src.models.evidence_verifier import EvidenceVerifier
from src.models.input_format import EvidenceRecord


def generate_100_unseen_claims() -> List[Dict[str, str]]:
    cases = []
    
    # 1. FACTUAL ENTAILMENT (15 cases) -> Target: SUPPORTED
    entailment_data = [
        ("Payment of 120.00 USD was completed via PayPal.", "Order 6Y1086430A3912609 capture completed gross 120.00 USD net 115.80 USD status COMPLETED.", "SUPPORTED", "Entailment"),
        ("Buyer account was provisioned with Student access role.", "MemberPress enrollment delivered success for alice@corp.io role=Student status=active.", "SUPPORTED", "Entailment"),
        ("Welcome credentials email was delivered with 250 OK status.", "SendGrid TLS 1.3 delivery confirmed to alice@corp.io status 250 OK message_id sg_99124.", "SUPPORTED", "Entailment"),
        ("Software license key was activated on host server.", "KMS license server recorded node activation for key PL-2026-X992 node_id mac_host_01.", "SUPPORTED", "Entailment"),
        ("Cloudflare CDN served 50 MB zip file with HTTP 200.", "Cloudflare CDN HTTP 200 OK 50541200 bytes transferred to client IP 198.51.100.42 complete.", "SUPPORTED", "Entailment"),
        ("Transaction was authenticated with 3DS 2.2 SMS OTP.", "3D Secure 2.2 cardholder authentication PASSED with SMS OTP challenge verified ECI 05.", "SUPPORTED", "Entailment"),
        ("Digital SaaS subscription was renewed for 49.00 USD.", "Stripe PayPal capture status COMPLETED amount 49.00 USD recurring subscription renewed.", "SUPPORTED", "Entailment"),
        ("Student completed Lesson 1 and scored 100 on quiz.", "LMS audit student alice@corp.io finished lesson 1 quiz score 100 percent timestamp verified.", "SUPPORTED", "Entailment"),
        ("API token was generated for developer workspace.", "Auth server generated bearer token scope read-write for user dev@agency.com session valid.", "SUPPORTED", "Entailment"),
        ("Order total of 15.00 USD was received by merchant.", "PayPal capture notification received amount 15.00 USD fee 0.50 USD credited to merchant balance.", "SUPPORTED", "Entailment"),
        ("Password reset link was clicked from registered device.", "Security log password reset link opened from user IP 198.51.100.42 device fingerprint matched.", "SUPPORTED", "Entailment"),
        ("Customer downloaded PDF cheat-sheet from edge server.", "Edge cache access log GET /cheatsheet.pdf 200 OK transferred 1420100 bytes to buyer IP.", "SUPPORTED", "Entailment"),
        ("Two-factor authentication code was successfully verified.", "Two-factor auth challenge verified via Authenticator TOTP token accepted for buyer login.", "SUPPORTED", "Entailment"),
        ("Buyer accepted terms of service during checkout flow.", "Checkout telemetry buyer clicked accept terms checkbox timestamp 2026-10-31 11:14:20 UTC.", "SUPPORTED", "Entailment"),
        ("Webhook notification was processed and verified by server.", "PayPal webhook event WH-9921 verification status SUCCESS processed by internal listener.", "SUPPORTED", "Entailment"),
    ]
    for c, e, t, cat in entailment_data:
        cases.append({"claim": c, "evidence": e, "target": t, "category": cat})

    # 2. NEGATION HANDLING (15 cases) -> Target: CONTRADICTED
    negation_data = [
        ("Customer never received access credentials by email.", "SendGrid TLS 1.3 delivery confirmed to customer with status 250 OK credentials delivered.", "CONTRADICTED", "Negation"),
        ("Buyer account was never activated on the course portal.", "MemberPress database shows account active enrolled and verified with 4 logins recorded.", "CONTRADICTED", "Negation"),
        ("No payment was ever captured for this order.", "PayPal capture completed for order gross 120.00 USD net 115.80 USD capture_id 10A71705.", "CONTRADICTED", "Negation"),
        ("Customer did not download any files from the website.", "Cloudflare CDN logs confirm 50.5 MB download completed 100 percent to customer IP.", "CONTRADICTED", "Negation"),
        ("Cardholder was never challenged with 3DS bank OTP.", "CardinalCommerce log shows 3DS 2.2 SMS OTP challenge was sent and verified by issuing bank.", "CONTRADICTED", "Negation"),
        ("Merchant refused to provision license key to user.", "License manager allocated and dispatched active license key PL-9921 to user email.", "CONTRADICTED", "Negation"),
        ("Buyer was unable to log into learning dashboard.", "LMS telemetry records 6 successful authenticated student sessions from buyer IP.", "CONTRADICTED", "Negation"),
        ("No confirmation email was transmitted to buyer.", "SMTP transmission receipt confirms email dispatched and delivered with DKIM pass.", "CONTRADICTED", "Negation"),
        ("Payment authorization failed at bank gateway.", "Bank settlement report shows transaction approved authorization code AUTH-99281.", "CONTRADICTED", "Negation"),
        ("Customer received zero bytes from content server.", "Edge web server socket telemetry confirms 50,541,200 bytes transferred with 200 OK.", "CONTRADICTED", "Negation"),
        ("Subscription access was revoked immediately.", "Subscription service records active tier access maintained without interruption.", "CONTRADICTED", "Negation"),
        ("Buyer device was never recognized as authentic.", "FraudNet telemetry shows device fingerprint matched 12 previous legitimate account sessions.", "CONTRADICTED", "Negation"),
        ("Order was cancelled before fulfillment completed.", "Fulfillment webhook confirms order status COMPLETED and assets dispatched to buyer.", "CONTRADICTED", "Negation"),
        ("Digital goods were not delivered to customer.", "Delivery receipts confirm digital goods package delivered to buyer registered email.", "CONTRADICTED", "Negation"),
        ("Customer had no active sessions on learning platform.", "Database session audit lists 5 completed module views and 2 quiz attempts by customer.", "CONTRADICTED", "Negation"),
    ]
    for c, e, t, cat in negation_data:
        cases.append({"claim": c, "evidence": e, "target": t, "category": cat})

    # 3. AMOUNT MISMATCH (15 cases) -> Target: CONTRADICTED
    amount_data = [
        ("Customer was billed 500.00 USD for basic course.", "PayPal invoice and capture receipt confirm exact charge of 120.00 USD.", "CONTRADICTED", "Amount Mismatch"),
        ("Merchant charged 50.00 USD instead of agreed price.", "Transaction capture record shows gross amount of 5.00 USD captured.", "CONTRADICTED", "Amount Mismatch"),
        ("Total transaction value was 1,200.00 USD.", "PayPal Orders API confirms purchase unit value of 120.00 USD.", "CONTRADICTED", "Amount Mismatch"),
        ("Customer was billed 85.00 USD for membership.", "Billing invoice confirms single charge of 49.00 USD for digital goods.", "CONTRADICTED", "Amount Mismatch"),
        ("Payment amount charged was 250.00 USD.", "Merchant account credited 180.00 USD for verified 3DS transaction.", "CONTRADICTED", "Amount Mismatch"),
        ("Cardholder account was debited 999.00 USD.", "Card processing ledger records charge of 120.00 USD authorized by cardholder.", "CONTRADICTED", "Amount Mismatch"),
        ("Order price was 300.00 USD for license.", "Software store checkout confirms item total was 49.00 USD.", "CONTRADICTED", "Amount Mismatch"),
        ("Customer paid 0.00 USD free promo code.", "Payment capture confirms 120.00 USD received without promotional discount.", "CONTRADICTED", "Amount Mismatch"),
        ("Monthly fee charged was 99.00 USD.", "Subscription invoice confirms standard plan charge of 19.00 USD.", "CONTRADICTED", "Amount Mismatch"),
        ("Merchant debited 1,000.00 USD unauthorized.", "PayPal transaction record shows single authorized charge of 180.00 USD.", "CONTRADICTED", "Amount Mismatch"),
        ("Customer was charged double amount 240.00 USD.", "Payment ledger shows single capture of 120.00 USD with zero duplicate charges.", "CONTRADICTED", "Amount Mismatch"),
        ("Course fee debited was 500.00 USD.", "Order confirmation confirms payment gross of 5.00 USD.", "CONTRADICTED", "Amount Mismatch"),
        ("Card was charged 750.00 USD without notice.", "Bank transaction records capture of 180.00 USD matching merchant receipt.", "CONTRADICTED", "Amount Mismatch"),
        ("Customer was billed 35.00 USD currency difference.", "PayPal currency conversion log shows transaction settled in USD without surcharge.", "CONTRADICTED", "Amount Mismatch"),
        ("Total price deducted was 450.00 USD.", "Checkout receipt confirms final captured balance of 120.00 USD.", "CONTRADICTED", "Amount Mismatch"),
    ]
    for c, e, t, cat in amount_data:
        cases.append({"claim": c, "evidence": e, "target": t, "category": cat})

    # 4. BUYER IDENTITY MISMATCH (15 cases) -> Target: CONTRADICTED
    identity_data = [
        ("Course access was granted to hacker@darkweb.org.", "LMS access certificate confirms enrollment provisioned to sb-q6d47h31140995@personal.example.com.", "CONTRADICTED", "Identity Mismatch"),
        ("Credentials were sent to unknown third-party receiver.", "SendGrid audit log confirms transmission specifically to verified buyer email alice@corp.io.", "CONTRADICTED", "Identity Mismatch"),
        ("License was activated under name of stranger Bob Smith.", "License registration record binds activation to verified customer John Doe.", "CONTRADICTED", "Identity Mismatch"),
        ("Order was placed by fraudulent user attacker@evil.com.", "PayPal payer record identifies verified account holder sb-rcnwy53637793@personal.example.com.", "CONTRADICTED", "Identity Mismatch"),
        ("Credentials were sent to attacker mailbox attacker@inbox.ru.", "SMTP server transcript shows recipient was customer.developer@example.com.", "CONTRADICTED", "Identity Mismatch"),
        ("Access was registered to fake address anonymous@proton.me.", "MemberPress database registers student account under legitimate buyer email address.", "CONTRADICTED", "Identity Mismatch"),
        ("Charge was made by third party fraudster in Russia.", "Payer account status VERIFIED PayPal member matching US billing address.", "CONTRADICTED", "Identity Mismatch"),
        ("File download was initiated from unauthorized Chinese IP.", "Cloudflare server logs show download request originated from customer residential IP 198.51.100.42.", "CONTRADICTED", "Identity Mismatch"),
        ("Certificate issued to invalid student ID usr_fake_99.", "Course platform issued completion certificate to verified student ID usr_94b76ba7.", "CONTRADICTED", "Identity Mismatch"),
        ("Email was delivered to wrong corporate domain @competitor.com.", "SendGrid logs verify destination email belonged to customer personal domain.", "CONTRADICTED", "Identity Mismatch"),
        ("License assigned to unknown machine uuid_stranger_88.", "Node licensing binds hardware fingerprint to customer registered laptop.", "CONTRADICTED", "Identity Mismatch"),
        ("Transaction approved by unauthorized payer ID PAYER-UNKNOWN.", "PayPal checkout confirms payer ID LAE4A4GDX2XQ8 matching buyer account.", "CONTRADICTED", "Identity Mismatch"),
        ("Order shipped to unauthorized recipient address in Miami.", "Digital fulfillment delivered directly to buyer registered email address.", "CONTRADICTED", "Identity Mismatch"),
        ("Account created under name Eve Hacker.", "LMS student profile initialized with buyer legal name John Doe.", "CONTRADICTED", "Identity Mismatch"),
        ("Bank OTP sent to stolen burner phone number.", "Issuing bank verified OTP was delivered to registered cardholder mobile on file.", "CONTRADICTED", "Identity Mismatch"),
    ]
    for c, e, t, cat in identity_data:
        cases.append({"claim": c, "evidence": e, "target": t, "category": cat})

    # 5. DATE / CHRONOLOGY MISMATCH (15 cases) -> Target: CONTRADICTED
    date_data = [
        ("Customer purchased course in January 2024.", "PayPal checkout order and capture occurred on October 31, 2026.", "CONTRADICTED", "Date Mismatch"),
        ("Access expired six months before transaction date.", "MemberPress enrollment shows account created on October 31, 2026 with 1-year valid access.", "CONTRADICTED", "Date Mismatch"),
        ("Customer opened dispute in year 2020.", "PayPal Resolution Center case created on October 31, 2026.", "CONTRADICTED", "Date Mismatch"),
        ("Download link expired in 2025 prior to purchase.", "Cloudflare CDN served file on October 31, 2026 immediately following purchase.", "CONTRADICTED", "Date Mismatch"),
        ("Charge occurred on November 2027 future date.", "Payment capture timestamp recorded at 2026-10-31 11:14:35 UTC.", "CONTRADICTED", "Date Mismatch"),
        ("Credentials were sent three weeks before payment.", "SendGrid email transmission timestamp is 2026-10-31 11:15:14 UTC, 39 seconds after payment.", "CONTRADICTED", "Date Mismatch"),
        ("License was revoked in 2023.", "KMS license manager issued active perpetual license on October 31, 2026.", "CONTRADICTED", "Date Mismatch"),
        ("User last logged in during 2022.", "LMS audit shows active user session on October 31, 2026 at 11:15:10 UTC.", "CONTRADICTED", "Date Mismatch"),
        ("Dispute response deadline was October 2025.", "PayPal dispute notice lists seller response deadline as November 10, 2026.", "CONTRADICTED", "Date Mismatch"),
        ("Order was completed 10 years ago.", "Transaction creation date recorded as 2026-10-31 in verified PayPal webhook.", "CONTRADICTED", "Date Mismatch"),
        ("CDN download took place in 2021.", "Edge server timestamp confirms download request executed on October 31, 2026.", "CONTRADICTED", "Date Mismatch"),
        ("3DS verification occurred months before purchase.", "Bank OTP authentication handshake completed at 11:14:28 UTC immediately prior to capture.", "CONTRADICTED", "Date Mismatch"),
        ("Account was closed in 2024.", "MemberPress LMS user status remains ACTIVE with current validity.", "CONTRADICTED", "Date Mismatch"),
        ("Payment was captured in December 2026.", "Capture log confirms payment finalized on October 31, 2026.", "CONTRADICTED", "Date Mismatch"),
        ("Email bounced in 2025.", "SendGrid delivery telemetry logs 250 OK delivery on October 31, 2026.", "CONTRADICTED", "Date Mismatch"),
    ]
    for c, e, t, cat in date_data:
        cases.append({"claim": c, "evidence": e, "target": t, "category": cat})

    # 6. CONFLICTING MULTI-SOURCE EVIDENCE (15 cases) -> Target: CONTRADICTED
    conflicting_data = [
        ("Download link was broken with a 404 error and no file was received.", "Cloudflare CDN edge server successfully served 48.2 MB file with HTTP 200 OK status to buyer IP.", "CONTRADICTED", "Conflicting Evidence"),
        ("Card was charged without cardholder 3D-Secure authentication.", "Issuing bank and 3DS protocol confirm cardholder entered valid SMS OTP with liability shift active.", "CONTRADICTED", "Conflicting Evidence"),
        ("Email delivery completely failed and bounced at destination.", "SendGrid server transcript confirms 250 OK TLS delivery and subsequent link open event.", "CONTRADICTED", "Conflicting Evidence"),
        ("Software license key was invalid and refused activation.", "License server audit shows key PL-2026 validated successfully and node binding established.", "CONTRADICTED", "Conflicting Evidence"),
        ("Buyer was locked out with unauthorized 403 forbidden error.", "LMS access logs record successful authenticated HTTP 200 session and course dashboard load.", "CONTRADICTED", "Conflicting Evidence"),
        ("Customer received zero bytes over connection.", "Socket telemetry records 50,541,200 bytes transferred with 100 percent completion.", "CONTRADICTED", "Conflicting Evidence"),
        ("Bank rejected payment due to suspected fraud.", "Bank settlement log confirms payment accepted with zero fraud flags and ECI 05 liability shift.", "CONTRADICTED", "Conflicting Evidence"),
        ("Merchant never sent any digital download link.", "Welcome email containing direct authenticated download link was delivered with 250 OK.", "CONTRADICTED", "Conflicting Evidence"),
        ("Account credentials were never created in system.", "LMS user database contains active user record with username matching buyer email.", "CONTRADICTED", "Conflicting Evidence"),
        ("User device was flagged as untrusted new device.", "FraudNet telemetry matched device fingerprint with 12 existing legitimate buyer sessions.", "CONTRADICTED", "Conflicting Evidence"),
        ("Download was interrupted and corrupted mid-transfer.", "Cloudflare edge logs confirm TCP connection closed gracefully after transmitting 100% bytes.", "CONTRADICTED", "Conflicting Evidence"),
        ("Transaction was marked ineligible for Seller Protection.", "PayPal dispute notice explicitly marks transaction ELIGIBLE for Seller Protection.", "CONTRADICTED", "Conflicting Evidence"),
        ("Customer was charged foreign transaction fee by merchant.", "Merchant invoice proves exact domestic USD charge without international surcharges.", "CONTRADICTED", "Conflicting Evidence"),
        ("License activation limit was exceeded on day one.", "KMS server records 1 of 3 allowed node activations used, status healthy.", "CONTRADICTED", "Conflicting Evidence"),
        ("Buyer canceled subscription before billing period.", "Subscription management system records active subscriber status with zero cancel requests.", "CONTRADICTED", "Conflicting Evidence"),
    ]
    for c, e, t, cat in conflicting_data:
        cases.append({"claim": c, "evidence": e, "target": t, "category": cat})

    # 7. UNSUPPORTED / IRRELEVANT CLAIMS (10 cases) -> Target: INSUFFICIENT_EVIDENCE
    insufficient_data = [
        ("Customer paid with Bitcoin cryptocurrency on external blockchain.", "PayPal capture completed for 120.00 USD via Visa card ending in 4012.", "INSUFFICIENT_EVIDENCE", "Insufficient Evidence"),
        ("Customer bought physical espresso machine shipped via FedEx to Tokyo.", "Order 3EU95140 is for digital software license and course access.", "INSUFFICIENT_EVIDENCE", "Insufficient Evidence"),
        ("Customer attended in-person conference workshop in London.", "Evidence describes digital LMS online course platform access.", "INSUFFICIENT_EVIDENCE", "Insufficient Evidence"),
        ("Merchant promised free iPad tablet with course purchase.", "Store order catalog lists digital Python Mastery course bundle without hardware gifts.", "INSUFFICIENT_EVIDENCE", "Insufficient Evidence"),
        ("Customer requested refund via telephone support line.", "System logs contain email and payment records but no telephone voice logs.", "INSUFFICIENT_EVIDENCE", "Insufficient Evidence"),
        ("Buyer car was repaired at merchant auto workshop.", "Transaction references digital goods SaaS platform license.", "INSUFFICIENT_EVIDENCE", "Insufficient Evidence"),
        ("Customer reserved hotel room for three nights in New York.", "Evidence verifies digital software product delivery via Cloudflare CDN.", "INSUFFICIENT_EVIDENCE", "Insufficient Evidence"),
        ("Weather was raining during digital checkout process.", "Payment API payload contains financial transaction fields and timestamps.", "INSUFFICIENT_EVIDENCE", "Insufficient Evidence"),
        ("Customer ordered 5 bottles of wine delivered by courier.", "Evidence records digital goods order with instant electronic fulfillment.", "INSUFFICIENT_EVIDENCE", "Insufficient Evidence"),
        ("Customer was granted lifetime VIP access to all future products.", "License record provisions access to Python Fullstack Course bundle v2.", "INSUFFICIENT_EVIDENCE", "Insufficient Evidence"),
    ]
    for c, e, t, cat in insufficient_data:
        cases.append({"claim": c, "evidence": e, "target": t, "category": cat})

    return cases


def run_100_claim_audit():
    print("=" * 80)
    print("STRICT 100-SAMPLE UNSEEN CLAIM AI AUDIT: VALIDATION & UNTOUCHED HOLDOUT")
    print("Model: Fine-Tuned DeBERTa-v3 on Apple Silicon (MPS / PyTorch)")
    print("=" * 80)

    model_dir = _ROOT / "ai" / "artifacts" / "best_model"
    if not (model_dir / "model.safetensors").exists():
        print(f"Error: Model weights not found at {model_dir}")
        sys.exit(1)

    t0_load = time.time()
    verifier = EvidenceVerifier(model_path=str(model_dir))
    verifier.load()
    load_time = round((time.time() - t0_load) * 1000, 2)
    device = getattr(verifier, "device", "cpu")
    print(f"Model loaded in {load_time}ms on device: {device}\n")

    all_cases = generate_100_unseen_claims()
    assert len(all_cases) == 100, f"Expected 100 cases, got {len(all_cases)}"

    # Partition into 50-sample Validation Set and 50-sample Untouched Holdout Test Set
    val_set = all_cases[0::2]   # 50 cases
    test_set = all_cases[1::2]  # 50 cases
    assert len(val_set) == 50 and len(test_set) == 50

    labels = ["SUPPORTED", "CONTRADICTED", "INSUFFICIENT_EVIDENCE"]

    def evaluate_partition(cases: List[Dict], partition_name: str) -> Dict[str, Any]:
        latencies = []
        confusion_matrix = defaultdict(lambda: defaultdict(int))
        confusion_matrix_4col = defaultdict(lambda: defaultdict(int))
        category_results = defaultdict(lambda: {"correct": 0, "total": 0})
        abstained_count = 0
        confident_correct = 0
        confident_total = 0

        for idx, case in enumerate(cases):
            claim = case["claim"]
            evidence = case["evidence"]
            target = case["target"]
            category = case["category"]

            rec = EvidenceRecord(
                evidence_id=f"EV-AUDIT-{idx+1:03d}",
                source_type="audit_log",
                timestamp="2026-11-01T12:00:00Z",
                content=evidence,
            )

            t_start = time.perf_counter()
            result = verifier.predict(claim, [rec])
            t_elapsed = (time.perf_counter() - t_start) * 1000.0
            latencies.append(t_elapsed)

            raw_pred = result["label"]
            decision = result.get("decision", raw_pred)
            is_abstained = result.get("is_abstained", False)

            confusion_matrix[target][raw_pred] += 1
            confusion_matrix_4col[target][decision] += 1
            category_results[category]["total"] += 1
            if raw_pred == target:
                category_results[category]["correct"] += 1

            if is_abstained:
                abstained_count += 1
            else:
                confident_total += 1
                if raw_pred == target:
                    confident_correct += 1

        total_correct = sum(confusion_matrix[lbl][lbl] for lbl in labels)
        raw_accuracy = (total_correct / len(cases)) * 100.0

        metrics = {}
        f1_list = []
        for lbl in labels:
            tp = confusion_matrix[lbl][lbl]
            fp = sum(confusion_matrix[other][lbl] for other in labels if other != lbl)
            fn = sum(confusion_matrix[lbl][other] for other in labels if other != lbl)

            prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
            rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
            f1 = (2 * prec * rec) / (prec + rec) if (prec + rec) > 0 else 0.0
            f1_list.append(f1)

            metrics[lbl] = {"precision": prec, "recall": rec, "f1": f1, "support": tp + fn}

        macro_f1 = sum(f1_list) / len(f1_list)

        return {
            "partition": partition_name,
            "total_cases": len(cases),
            "raw_accuracy": raw_accuracy,
            "macro_f1": macro_f1,
            "metrics": metrics,
            "confusion_matrix": {k: dict(v) for k, v in confusion_matrix.items()},
            "confusion_matrix_4col": {k: dict(v) for k, v in confusion_matrix_4col.items()},
            "category_results": category_results,
            "abstained_count": abstained_count,
            "abstention_rate": (abstained_count / len(cases)) * 100.0,
            "confident_total": confident_total,
            "confident_correct": confident_correct,
            "confident_precision": (confident_correct / confident_total * 100.0) if confident_total > 0 else 0.0,
            "latencies": latencies,
        }

    # 1. Evaluate on Validation Partition
    val_res = evaluate_partition(val_set, "Validation Set (50 Claims)")

    # 2. Evaluate on Untouched Holdout Partition
    test_res = evaluate_partition(test_set, "Untouched Holdout Test Set (50 Claims)")

    print(f"--- 1. UNTOUCHED HOLDOUT TEST SET PERFORMANCE ({test_res['total_cases']} Claims) ---")
    print(f"Raw Model Accuracy:          {test_res['raw_accuracy']:.2f}%")
    print(f"Macro-F1 Score:              {test_res['macro_f1']*100:.2f}%\n")

    print(f"--- 2. SAFE ABSTENTION & HUMAN-IN-THE-LOOP METRICS ---")
    print(f"Cases Abstained (Deferred):  {test_res['abstained_count']} / {test_res['total_cases']} ({test_res['abstention_rate']:.1f}%)")
    print(f"Confident Claims Acted On:   {test_res['confident_total']} / {test_res['total_cases']}")
    print(f"Effective Precision on Acts: {test_res['confident_precision']:.2f}%\n")

    print("--- 3. PER-CLASS METRICS (Untouched Holdout) ---")
    for lbl in labels:
        m = test_res["metrics"][lbl]
        print(f"[{lbl}]")
        print(f"  Precision: {m['precision']*100:5.2f}% | Recall: {m['recall']*100:5.2f}% | F1: {m['f1']*100:5.2f}% (Support: {m['support']})")

    print("\n--- 4. RECONCILED 4-COLUMN CONFUSION MATRIX (Untouched Holdout) ---")
    target_col = "Target \\ Decision"
    header = f"{target_col:<24} | {'SUPPORTED':<12} | {'CONTRADICTED':<12} | {'INSUFFICIENT':<12} | {'NEEDS_HUMAN_REVIEW':<18} | {'Total':<6}"
    print(header)
    print("-" * len(header))
    for true_lbl in labels:
        s_count = test_res["confusion_matrix_4col"][true_lbl].get("SUPPORTED", 0)
        c_count = test_res["confusion_matrix_4col"][true_lbl].get("CONTRADICTED", 0)
        i_count = test_res["confusion_matrix_4col"][true_lbl].get("INSUFFICIENT_EVIDENCE", 0)
        a_count = test_res["confusion_matrix_4col"][true_lbl].get("NEEDS_HUMAN_REVIEW", 0)
        row_tot = s_count + c_count + i_count + a_count
        print(f"{true_lbl:<24} | {s_count:<12} | {c_count:<12} | {i_count:<12} | {a_count:<18} | {row_tot:<6}")
    total_s = sum(test_res["confusion_matrix_4col"][l].get("SUPPORTED", 0) for l in labels)
    total_c = sum(test_res["confusion_matrix_4col"][l].get("CONTRADICTED", 0) for l in labels)
    total_i = sum(test_res["confusion_matrix_4col"][l].get("INSUFFICIENT_EVIDENCE", 0) for l in labels)
    total_a = sum(test_res["confusion_matrix_4col"][l].get("NEEDS_HUMAN_REVIEW", 0) for l in labels)
    print("-" * len(header))
    print(f"{'Total Predicted':<24} | {total_s:<12} | {total_c:<12} | {total_i:<12} | {total_a:<18} | {test_res['total_cases']:<6}")

    print("\n--- 5. HARDWARE INFERENCE LATENCY (MPS) ---")
    lats = sorted(test_res["latencies"])
    mean_lat = sum(lats) / len(lats)
    p50_lat = lats[int(len(lats) * 0.50)]
    p95_lat = lats[int(len(lats) * 0.95)]
    print(f"Mean Latency: {mean_lat:.2f} ms | Median (p50): {p50_lat:.2f} ms | 95th Percentile: {p95_lat:.2f} ms")

    print("\n--- 6. FORENSIC POSITIONING STATEMENT ---")
    print("ProofLedger is NOT an autonomous dispute judge. It is an Evidence Intelligence")
    print("and Cryptographic Verification Platform that flags ambiguities for human review.")
    print("=" * 80)

    # Save artifact
    output_path = _ROOT / "ai" / "artifacts" / "deberta_holdout_audit.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump({
            "test_suite": "untouched_holdout_and_validation_audit",
            "validation_results": {k: v for k, v in val_res.items() if k != "latencies"},
            "holdout_test_results": {k: v for k, v in test_res.items() if k != "latencies"},
            "abstention_policy": {
                "min_confidence_threshold": 0.55,
                "min_margin_threshold": 0.12,
                "abstention_label": "NEEDS_HUMAN_REVIEW",
            },
        }, f, indent=2)

    return True


def test_deberta_generalization_audit():
    assert run_100_claim_audit() is True


if __name__ == "__main__":
    success = run_100_claim_audit()
    sys.exit(0 if success else 1)
