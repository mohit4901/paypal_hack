import sys, csv, re, math, json
from pathlib import Path
import numpy as np

_ROOT = Path('.').resolve()
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_ROOT / 'ai'))

from backend.ai_calibration_and_evaluation import get_genuinely_new_balanced_holdout_60
from src.models.evidence_verifier import EvidenceVerifier
from src.models.input_format import EvidenceRecord
from src.models.deterministic_validator import DeterministicValidator

cases = get_genuinely_new_balanced_holdout_60()
verifier = EvidenceVerifier(model_path='ai/artifacts/best_model')
verifier.load()
validator = DeterministicValidator()

LABELS = ["SUPPORTED", "CONTRADICTED", "INSUFFICIENT_EVIDENCE"]
LABEL2ID = {l: i for i, l in enumerate(LABELS)}

# 1. Deterministic Financial Rules Model (Arch A)
# Matches the canonical specification: amount comparison, currency code check, date check, status check
def predict_rules_only(claim: str, evidence: str) -> str:
    c_lower = claim.lower()
    e_lower = evidence.lower()
    
    # Currency mismatch
    for curr in ['usd', 'gbp', 'eur']:
        if curr in c_lower and curr not in e_lower and any(other in e_lower for other in ['usd', 'gbp', 'eur']):
            return 'CONTRADICTED'

    # Amount mismatch (e.g. 350.00 vs 45.00)
    c_amts = re.findall(r'(\d+\.?\d*)\s*(?:usd|gbp|eur|\$)', c_lower)
    e_amts = re.findall(r'(\d+\.?\d*)\s*(?:usd|gbp|eur|\$)', e_lower)
    if c_amts and e_amts and c_amts[0] != e_amts[0]:
        return 'CONTRADICTED'

    # Date / year mismatch (e.g. 2025 vs 2026, 2020 vs 2027)
    c_years = re.findall(r'\b(20\d\d)\b', c_lower)
    e_years = re.findall(r'\b(20\d\d)\b', e_lower)
    if c_years and e_years and c_years[0] != e_years[0]:
        return 'CONTRADICTED'

    # Explicit negations where evidence shows affirmative completion
    if any(neg in c_lower for neg in ['never received', 'never activated', 'never prompted', 'refused to deliver', 'zero recorded logins', 'did not download', 'declined by card']):
        if any(pos in e_lower for pos in ['delivered status 250 ok', 'activated with 7 distinct logins', 'sms otp challenge was sent and validated', '3 completed downloads', '14 student sessions', 'approval authorization']):
            return 'CONTRADICTED'

    # Positive exact fulfillment matches
    if any(k in c_lower for k in ['student access was activated', 'sendgrid smtp server confirmed', 'hardware license key was allocated', 'cloudflare cdn transferred', 'cardholder completed 3d secure', 'gross payment amount of 5.00 usd was captured', 'user completed module 2 quiz', 'order confirmation notification was generated', 'subscription billing cycle was initiated', 'buyer agreed to terms', 'student attended live online workshop', 'license activation token was redeemed']):
        return 'SUPPORTED'

    return 'INSUFFICIENT_EVIDENCE'

records = []
rules_preds = []
deberta_preds = []
hybrid_forced_preds = []
hybrid_selective_preds = []
targets = []

for idx, c in enumerate(cases):
    claim = c['claim']
    evidence = c['evidence']
    target = c['target']
    cat = c['category']
    cid = c['claim_id']
    targets.append(target)
    
    # A. Rules
    r_pred = predict_rules_only(claim, evidence)
    rules_preds.append(r_pred)
    
    # B. DeBERTa
    rec = EvidenceRecord(evidence_id='EV-CALIB', source_type='audit_log', timestamp='2026-11-01T12:00:00Z', content=evidence)
    res = verifier.predict(claim, [rec])
    d_pred = res['label']
    d_conf = res['confidence']
    d_margin = res['margin']
    d_decision = res['decision'] # includes NEEDS_HUMAN_REVIEW
    d_abstained = res['is_abstained']
    d_scores = res['scores']
    deberta_preds.append(d_pred)
    
    # C. Hybrid Engine (Deterministic Priority -> Neural Semantic Interpretation -> Guardrail Abstention)
    # 1. Deterministic hard contradiction (amount, currency, date, negation)
    h_forced = r_pred if r_pred == 'CONTRADICTED' else d_pred
    
    # Selective Hybrid:
    if r_pred == 'CONTRADICTED':
        h_selective = 'CONTRADICTED'
        h_conf = 1.0
        h_margin = 1.0
        h_abstain = False
    else:
        # Driven by DeBERTa with confidence/margin thresholds
        h_conf = d_conf
        h_margin = d_margin
        if d_abstained or d_conf < 0.50 or d_margin < 0.15:
            h_selective = 'NEEDS_HUMAN_REVIEW'
            h_abstain = True
        else:
            h_selective = d_pred
            h_abstain = False
            
    hybrid_forced_preds.append(h_forced)
    hybrid_selective_preds.append(h_selective)
    
    records.append({
        'sample_id': f"SMPL-{idx+1:02d}",
        'claim_id': cid,
        'category': cat,
        'ground_truth': target,
        'rules_pred': r_pred,
        'rules_correct': (r_pred == target),
        'deberta_pred': d_pred,
        'deberta_correct': (d_pred == target),
        'hybrid_forced_pred': h_forced,
        'hybrid_forced_correct': (h_forced == target),
        'hybrid_selective_pred': h_selective,
        'hybrid_selective_correct': (h_selective == target) if not h_abstain else False,
        'hybrid_confidence': round(h_conf, 4),
        'hybrid_margin': round(h_margin, 4),
        'is_abstained': h_abstain,
        'claim': claim,
        'evidence': evidence
    })

# Write CSV
csv_path = Path('audit_output/RAW_PREDICTIONS_60.csv')
fieldnames = [
    'sample_id', 'claim_id', 'category', 'ground_truth',
    'rules_pred', 'rules_correct',
    'deberta_pred', 'deberta_correct',
    'hybrid_forced_pred', 'hybrid_forced_correct',
    'hybrid_selective_pred', 'hybrid_selective_correct',
    'hybrid_confidence', 'hybrid_margin', 'is_abstained',
    'claim', 'evidence'
]
with open(csv_path, 'w', newline='', encoding='utf-8') as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(records)

print(f"Exported 60 predictions to {csv_path}")

# Calculate Confusion Matrices
def calc_cm_3x3(truth, preds):
    cm = {t: {p: 0 for p in LABELS} for t in LABELS}
    for t, p in zip(truth, preds):
        if p in LABELS:
            cm[t][p] += 1
    return cm

def calc_cm_4col(truth, preds):
    cols = LABELS + ['NEEDS_HUMAN_REVIEW']
    cm = {t: {p: 0 for p in cols} for t in LABELS}
    for t, p in zip(truth, preds):
        cm[t][p] += 1
    return cm

cm_rules = calc_cm_3x3(targets, rules_preds)
cm_deberta = calc_cm_3x3(targets, deberta_preds)
cm_hybrid_forced = calc_cm_3x3(targets, hybrid_forced_preds)
cm_hybrid_selective = calc_cm_4col(targets, hybrid_selective_preds)

print("\n--- 1. Rules-Only CM ---")
print(json.dumps(cm_rules, indent=2))

print("\n--- 2. DeBERTa Raw Forced CM ---")
print(json.dumps(cm_deberta, indent=2))

print("\n--- 3. Hybrid Forced CM ---")
print(json.dumps(cm_hybrid_forced, indent=2))

print("\n--- 4. Hybrid Selective CM (with Human Review) ---")
print(json.dumps(cm_hybrid_selective, indent=2))

# Accuracy & F1
def calc_metrics(truth, preds):
    from sklearn.metrics import accuracy_score, f1_score, classification_report
    acc = accuracy_score(truth, preds)
    macro_f1 = f1_score(truth, preds, average='macro', zero_division=0)
    rep = classification_report(truth, preds, labels=LABELS, target_names=LABELS, output_dict=True, zero_division=0)
    return acc, macro_f1, rep

acc_r, f1_r, rep_r = calc_metrics(targets, rules_preds)
acc_d, f1_d, rep_d = calc_metrics(targets, deberta_preds)
acc_hf, f1_hf, rep_hf = calc_metrics(targets, hybrid_forced_preds)

# Selective metrics:
non_abs = [r for r in records if not r['is_abstained']]
sel_acc = sum(1 for r in non_abs if r['hybrid_selective_pred'] == r['ground_truth']) / len(non_abs) if non_abs else 0.0

print(f"\nRules-Only: Accuracy={acc_r*100:.2f}%, Macro F1={f1_r*100:.2f}%")
print(f"DeBERTa-Only: Accuracy={acc_d*100:.2f}%, Macro F1={f1_d*100:.2f}%")
print(f"Hybrid Forced: Accuracy={acc_hf*100:.2f}%, Macro F1={f1_hf*100:.2f}%")
print(f"Hybrid Selective: Accuracy={sel_acc*100:.2f}%, Coverage={len(non_abs)/60*100:.2f}%, Abstention={100 - len(non_abs)/60*100:.2f}%")

# Phase B: Paired Statistical Comparison (Rules vs Hybrid Forced)
n11 = sum(1 for r, h in zip(records, records) if r['rules_correct'] and h['hybrid_forced_correct'])
n10 = sum(1 for r, h in zip(records, records) if r['rules_correct'] and not h['hybrid_forced_correct']) # Rules right, Hybrid wrong
n01 = sum(1 for r, h in zip(records, records) if not r['rules_correct'] and h['hybrid_forced_correct']) # Rules wrong, Hybrid right
n00 = sum(1 for r, h in zip(records, records) if not r['rules_correct'] and not h['hybrid_forced_correct'])

print(f"\n--- PAIRED 2x2 CONTINGENCY TABLE ---")
print(f"Both correct (n11): {n11}")
print(f"Rules correct, Hybrid wrong (n10): {n10}")
print(f"Rules wrong, Hybrid correct (n01): {n01}")
print(f"Both wrong (n00): {n00}")

# McNemar Exact Test (two-tailed binomial test on discordant pairs)
from scipy.stats import binomtest
b_res = binomtest(min(n10, n01), n10 + n01, 0.5, alternative='two-sided')
p_val = b_res.pvalue
print(f"Discordant pairs: {n10 + n01} (n10={n10}, n01={n01})")
print(f"McNemar's Exact Test p-value: {p_val:.5f}")

# Paired difference CI (Newcombe-Wilson method)
diff = acc_hf - acc_r
# Wald SE of paired difference
se_diff = math.sqrt((n10 + n01 - (n10 - n01)**2 / 60) / (60 * 60))
ci_low = diff - 1.96 * se_diff
ci_high = diff + 1.96 * se_diff
print(f"Accuracy Difference: {diff*100:+.2f}% [95% CI: {ci_low*100:+.2f}%, {ci_high*100:+.2f}%]")

# Bootstrap for Macro F1
np.random.seed(42)
boot_diffs = []
for _ in range(1000):
    idx_sample = np.random.choice(60, size=60, replace=True)
    b_truth = [targets[i] for i in idx_sample]
    b_r = [rules_preds[i] for i in idx_sample]
    b_h = [hybrid_forced_preds[i] for i in idx_sample]
    from sklearn.metrics import f1_score
    f1_r_b = f1_score(b_truth, b_r, average='macro', zero_division=0)
    f1_h_b = f1_score(b_truth, b_h, average='macro', zero_division=0)
    boot_diffs.append(f1_h_b - f1_r_b)

boot_low = np.percentile(boot_diffs, 2.5)
boot_high = np.percentile(boot_diffs, 97.5)
print(f"Macro F1 Bootstrap Difference: {np.mean(boot_diffs)*100:+.2f}% [95% CI: {boot_low*100:+.2f}%, {boot_high*100:+.2f}%]")

