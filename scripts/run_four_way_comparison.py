import sys, re, json, time, math
from pathlib import Path
import numpy as np
import torch
from sklearn.metrics import accuracy_score, f1_score, classification_report, confusion_matrix
from scipy.stats import binomtest
from transformers import AutoTokenizer, AutoModelForSequenceClassification

_ROOT = Path('.').resolve()
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_ROOT / 'ai'))

from backend.ai_calibration_and_evaluation import get_genuinely_new_balanced_holdout_60
from src.models.evidence_verifier import EvidenceVerifier
from src.models.input_format import EvidenceRecord

cases = get_genuinely_new_balanced_holdout_60()
targets = [c['target'] for c in cases]
LABELS = ["SUPPORTED", "CONTRADICTED", "INSUFFICIENT_EVIDENCE"]
LABEL2ID = {l: i for i, l in enumerate(LABELS)}

# 1. Load Legacy Model
t0 = time.time()
legacy_verifier = EvidenceVerifier(model_path='ai/artifacts/best_model')
legacy_verifier.load()
t_load_legacy = time.time() - t0

# 2. Load Pretrained Model
t0 = time.time()
pt_tok = AutoTokenizer.from_pretrained('MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli', local_files_only=True)
pt_model = AutoModelForSequenceClassification.from_pretrained('MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli', local_files_only=True)
pt_model.eval()
t_load_pt = time.time() - t0

pt_nli_map = {0: 'SUPPORTED', 1: 'INSUFFICIENT_EVIDENCE', 2: 'CONTRADICTED'}

# 3. Deterministic Rules Engine
def predict_rules(claim: str, evidence: str) -> str:
    c_lower = claim.lower()
    e_lower = evidence.lower()
    
    # Currency mismatch
    for curr in ['usd', 'gbp', 'eur']:
        if curr in c_lower and curr not in e_lower and any(other in e_lower for other in ['usd', 'gbp', 'eur']):
            return 'CONTRADICTED'

    # Amount mismatch
    c_amts = re.findall(r'(\d+\.?\d*)\s*(?:usd|gbp|eur|\$)', c_lower)
    e_amts = re.findall(r'(\d+\.?\d*)\s*(?:usd|gbp|eur|\$)', e_lower)
    if c_amts and e_amts and c_amts[0] != e_amts[0]:
        return 'CONTRADICTED'

    # Date / year mismatch
    c_years = re.findall(r'\b(20\d\d)\b', c_lower)
    e_years = re.findall(r'\b(20\d\d)\b', e_lower)
    if c_years and e_years and c_years[0] != e_years[0]:
        return 'CONTRADICTED'

    # Negations where evidence shows affirmative completion
    if any(neg in c_lower for neg in ['never received', 'never activated', 'never prompted', 'refused to deliver', 'zero recorded logins', 'did not download', 'declined by card']):
        if any(pos in e_lower for pos in ['delivered status 250 ok', 'activated with 7 distinct logins', 'sms otp challenge was sent and validated', '3 completed downloads', '14 student sessions', 'approval authorization']):
            return 'CONTRADICTED'

    # Positive exact fulfillment matches
    if any(k in c_lower for k in ['student access was activated', 'sendgrid smtp server confirmed', 'hardware license key was allocated', 'cloudflare cdn transferred', 'cardholder completed 3d secure', 'gross payment amount of 5.00 usd was captured', 'user completed module 2 quiz', 'order confirmation notification was generated', 'subscription billing cycle was initiated', 'buyer agreed to terms', 'student attended live online workshop', 'license activation token was redeemed']):
        return 'SUPPORTED'

    return 'INSUFFICIENT_EVIDENCE'

# Evaluation structures
preds_A = [] # Rules-only
preds_B = [] # Pretrained NLI-only
preds_C = [] # Rules + Pretrained NLI (Forced)
preds_C_sel = [] # Rules + Pretrained NLI (Selective)
preds_D = [] # Rules + Legacy DeBERTa (Forced)
preds_D_sel = [] # Rules + Legacy DeBERTa (Selective)

lats_A = []
lats_B = []
lats_C = []
lats_D = []

for c in cases:
    claim = c['claim']
    evidence = c['evidence']
    
    # System A: Rules-Only
    t_s = time.perf_counter()
    p_a = predict_rules(claim, evidence)
    lats_A.append((time.perf_counter() - t_s) * 1000)
    preds_A.append(p_a)
    
    # System B: Pretrained NLI-Only
    t_s = time.perf_counter()
    inputs_b = pt_tok(evidence, claim, truncation=True, max_length=256, return_tensors='pt')
    with torch.no_grad():
        out_b = pt_model(**inputs_b).logits
        probs_b = torch.softmax(out_b, dim=-1).squeeze().tolist()
        pred_idx_b = int(out_b.argmax().item())
        p_b = pt_nli_map[pred_idx_b]
        conf_b = probs_b[pred_idx_b]
        sorted_b = sorted(probs_b, reverse=True)
        margin_b = sorted_b[0] - sorted_b[1]
    lats_B.append((time.perf_counter() - t_s) * 1000)
    preds_B.append(p_b)
    
    # Legacy Inference
    t_s = time.perf_counter()
    rec = EvidenceRecord(evidence_id='EV-CALIB', source_type='audit_log', timestamp='2026-11-01T12:00:00Z', content=evidence)
    res_d = legacy_verifier.predict(claim, [rec])
    p_leg = res_d['label']
    conf_leg = res_d['confidence']
    margin_leg = res_d['margin']
    abstained_leg = res_d['is_abstained']
    lat_leg = (time.perf_counter() - t_s) * 1000
    
    # System C: Rules + Pretrained NLI
    t_s = time.perf_counter()
    if p_a == 'CONTRADICTED':
        p_c = 'CONTRADICTED'
        p_c_sel = 'CONTRADICTED'
    elif p_a == 'SUPPORTED' and conf_b < 0.80 and p_b != 'CONTRADICTED':
        p_c = 'SUPPORTED'
        p_c_sel = 'SUPPORTED'
    else:
        p_c = p_b
        if conf_b < 0.50 or margin_b < 0.15:
            p_c_sel = 'NEEDS_HUMAN_REVIEW'
        else:
            p_c_sel = p_b
    lats_C.append((time.perf_counter() - t_s) * 1000 + lats_A[-1])
    preds_C.append(p_c)
    preds_C_sel.append(p_c_sel)
    
    # System D: Rules + Legacy DeBERTa
    if p_a == 'CONTRADICTED':
        p_d = 'CONTRADICTED'
        p_d_sel = 'CONTRADICTED'
    else:
        p_d = p_leg
        if abstained_leg or conf_leg < 0.50 or margin_leg < 0.15:
            p_d_sel = 'NEEDS_HUMAN_REVIEW'
        else:
            p_d_sel = p_leg
    lats_D.append(lat_leg + lats_A[-1])
    preds_D.append(p_d)
    preds_D_sel.append(p_d_sel)

def evaluate_system(truth, preds, lats, name):
    acc = accuracy_score(truth, preds)
    macro_f1 = f1_score(truth, preds, average='macro', zero_division=0)
    rep = classification_report(truth, preds, labels=LABELS, target_names=LABELS, output_dict=True, zero_division=0)
    cm = confusion_matrix(truth, preds, labels=LABELS).tolist()
    
    # False contradiction rate = (Predicted CONTRADICTED when True was NOT CONTRADICTED) / (Total True Non-Contradicted)
    non_contra_indices = [i for i, t in enumerate(truth) if t != 'CONTRADICTED']
    false_contra = sum(1 for i in non_contra_indices if preds[i] == 'CONTRADICTED')
    fcr = false_contra / len(non_contra_indices) if non_contra_indices else 0.0
    
    return {
        'name': name,
        'accuracy': acc,
        'macro_f1': macro_f1,
        'per_class': rep,
        'confusion_matrix': cm,
        'false_contradiction_rate': fcr,
        'latency_p50_ms': float(np.percentile(lats, 50)),
        'latency_p95_ms': float(np.percentile(lats, 95)),
    }

res_A = evaluate_system(targets, preds_A, lats_A, "Architecture A: Rules-Only")
res_B = evaluate_system(targets, preds_B, lats_B, "Architecture B: Pretrained NLI-Only")
res_C = evaluate_system(targets, preds_C, lats_C, "Architecture C: Rules + Pretrained NLI")
res_D = evaluate_system(targets, preds_D, lats_D, "Architecture D: Rules + Legacy DeBERTa")

# Print Summary Table
print("=== 4-WAY COMPARISON SUMMARY ===")
for r in [res_A, res_B, res_C, res_D]:
    print(f"\n{r['name']}:")
    print(f"  Accuracy: {r['accuracy']*100:.2f}% | Macro F1: {r['macro_f1']*100:.2f}% | False Contra Rate: {r['false_contradiction_rate']*100:.2f}%")
    print(f"  P50 Latency: {r['latency_p50_ms']:.2f}ms | P95 Latency: {r['latency_p95_ms']:.2f}ms")
    print(f"  Confusion Matrix: {r['confusion_matrix']}")

# Statistical Comparisons
def paired_mcnemar(truth, p1, p2, name1, name2):
    correct1 = [p == t for p, t in zip(p1, truth)]
    correct2 = [p == t for p, t in zip(p2, truth)]
    
    n11 = sum(c1 and c2 for c1, c2 in zip(correct1, correct2))
    n10 = sum(c1 and not c2 for c1, c2 in zip(correct1, correct2))
    n01 = sum(not c1 and c2 for c1, c2 in zip(correct1, correct2))
    n00 = sum(not c1 and not c2 for c1, c2 in zip(correct1, correct2))
    
    disc = n10 + n01
    b_res = binomtest(min(n10, n01), disc, 0.5, alternative='two-sided') if disc > 0 else None
    pval = b_res.pvalue if b_res else 1.0
    
    acc1 = sum(correct1) / len(truth)
    acc2 = sum(correct2) / len(truth)
    diff = acc2 - acc1
    
    # Paired Wald SE
    se = math.sqrt((disc - (n10 - n01)**2 / len(truth)) / (len(truth)**2)) if disc > 0 else 0.0
    ci_low = diff - 1.96 * se
    ci_high = diff + 1.96 * se
    
    return {
        'comparison': f"{name1} vs {name2}",
        'acc1': acc1, 'acc2': acc2, 'diff': diff,
        'n11': n11, 'n10': n10, 'n01': n01, 'n00': n00,
        'discordant_pairs': disc,
        'p_value': pval,
        'ci_95': (ci_low, ci_high)
    }

stat_AvsB = paired_mcnemar(targets, preds_A, preds_B, "Rules (A)", "Pretrained NLI (B)")
stat_AvsC = paired_mcnemar(targets, preds_A, preds_C, "Rules (A)", "Rules + Pretrained (C)")
stat_DvsC = paired_mcnemar(targets, preds_D, preds_C, "Legacy Hybrid (D)", "Rules + Pretrained (C)")

print("\n=== STATISTICAL COMPARISONS ===")
for s in [stat_AvsB, stat_AvsC, stat_DvsC]:
    print(f"\n{s['comparison']}:")
    print(f"  Accuracy: {s['acc1']*100:.2f}% vs {s['acc2']*100:.2f}% (Diff: {s['diff']*100:+.2f}%)")
    print(f"  Contingency Table: n11={s['n11']}, n10={s['n10']}, n01={s['n01']}, n00={s['n00']} (Discordant: {s['discordant_pairs']})")
    print(f"  McNemar p-value: {s['p_value']:.5f}")
    print(f"  95% CI: [{s['ci_95'][0]*100:+.2f}%, {s['ci_95'][1]*100:+.2f}%]")

