# PROOFLEDGER AI RESEARCH REPORT
## PHASE 4: PAIRED STATISTICAL COMPARISON & HYPOTHESIS TESTING

**Audit Date:** November 5, 2026  
**Investigator:** Applied NLP Research Scientist & Statistical Auditor  
**Focus:** Three Paired McNemar Tests, Discordant Decompositions & Paired Bootstrap CIs  
**Evaluated Cohorts:**  
1. Development Balanced Holdout ($N=60$, repeated-evaluation cohort)  
2. Independently Sourced Hidden Evaluation Set ($N=30$, pristine test cohort)  

---

### 1. Executive Statistical Summary

| Paired Model Comparison | Evaluation Cohort | Discordant Pairs ($n_{10} \mid n_{01}$) | Accuracy Difference ($\hat{\Delta}$) | 95% Confidence Interval | McNemar Exact $p$-value | Statistical Significance ($\alpha = 0.05$) |
|---|:---:|:---:|:---:|:---:|:---:|:---:|
| **Rules (A) vs. Pretrained NLI (B)** | Dev Holdout ($N=60$) | $n_{10}=12 \mid n_{01}=14$ | $+3.33\%$ | $[-13.30\%, +19.97\%]$ | **$p = 0.84502$** | **NOT SIGNIFICANT** ($p > 0.05$) |
| **Rules (A) vs. Rules + Pretrained (C)** | Dev Holdout ($N=60$) | $n_{10}=12 \mid n_{01}=14$ | $+3.33\%$ | $[-13.30\%, +19.97\%]$ | **$p = 0.84502$** | **NOT SIGNIFICANT** ($p > 0.05$) |
| **Legacy Hybrid (D) vs. Rules + Pretrained (C)** | Dev Holdout ($N=60$) | $n_{10}=4 \mid n_{01}=14$ | **$+16.67\%$** | **$[+3.46\%, +29.87\%]$** | **$p = 0.03088$** | **STATISTICALLY SIGNIFICANT** ($p < 0.05$) |
| **Rules (A) vs. Pretrained NLI (B)** | **Hidden Set ($N=30$)** | $n_{10}=13 \mid n_{01}=3$ | **$-33.33\%$** | **$[-52.14\%, -14.53\%]$** | **$p = 0.02127$** | **SIGNIFICANT FAVORING RULES** ($p < 0.05$) |
| **Rules (A) vs. Rules + Pretrained (C)** | **Hidden Set ($N=30$)** | $n_{10}=6 \mid n_{01}=3$ | $-10.00\%$ | $[-28.81\%, +8.81\%]$ | **$p = 0.50781$** | **NOT SIGNIFICANT** ($p > 0.05$) |
| **Legacy Hybrid (D) vs. Rules + Pretrained (C)** | **Hidden Set ($N=30$)** | $n_{10}=3 \mid n_{01}=12$ | **$+30.00\%$** | **$[+9.84\%, +50.16\%]$** | **$p = 0.03516$** | **STATISTICALLY SIGNIFICANT** ($p < 0.05$) |

---

### 2. Paired 2x2 Contingency Table Analysis (Dev Cohort, $N=60$)

#### Comparison 1: Rules-Only (A) vs. Pretrained NLI (B)
- Concordant Success ($n_{11}$): **31 claims** (both correctly identified)
- Concordant Failure ($n_{00}$): **3 claims** (both failed on obscure logs)
- Rules Won ($n_{10}$): **12 claims** (Rules correctly identified `INSUFFICIENT_EVIDENCE`; Pretrained NLI fired false contradictions)
- Pretrained Won ($n_{01}$): **14 claims** (Pretrained NLI parsed subtle semantic fulfillment; Rules defaulted to insufficient)
- **Discordant Pairs:** 26 ($12 \text{ vs } 14$)
- **Two-Tailed Binomial Test:** $P(X \le 12 \mid n=26, p=0.5) \times 2 = \mathbf{0.84502}$
- **Conclusion:** Pretrained NLI's marginal 2-sample advantage (45 vs 43) is completely within random sampling noise.

#### Comparison 2: Legacy Hybrid (D) vs. Rules + Pretrained NLI (C)
- Concordant Success ($n_{11}$): **31 claims**
- Concordant Failure ($n_{00}$): **11 claims**
- Legacy Hybrid Won ($n_{10}$): **4 claims**
- Rules + Pretrained Won ($n_{01}$): **14 claims**
- **Discordant Pairs:** 18 ($4 \text{ vs } 14$)
- **Two-Tailed Binomial Test:** $P(X \le 4 \mid n=18, p=0.5) \times 2 = \mathbf{0.03088}$
- **Conclusion:** Rules + Pretrained NLI is **statistically significantly superior to the legacy fine-tuned model** ($p = 0.031$). The lower bound of the paired 95% CI is $+3.46\%$, completely excluding zero.

---

### 3. Paired Analysis on the Pristine Hidden Evaluation Set ($N=30$)

When evaluated on the 30 brand-new, unseen claims representing authentic physical and digital dispute scenarios:

1. **Rules-Only achieved 90.00% accuracy (27/30)**.
2. **Pretrained NLI achieved 56.67% accuracy (17/30)**.
3. In the paired comparison:
   - Rules succeeded in 13 cases where Pretrained NLI failed ($n_{10} = 13$).
   - Pretrained succeeded in only 3 cases where Rules failed ($n_{01} = 3$).
   - **McNemar Exact $p$-value:** **$p = 0.02127$**.

> [!IMPORTANT]
> **STATISTICAL FINDING ON INDEPENDENT DATA:**  
> On unseen real-world dispute language, **Deterministic Financial Rules are statistically significantly superior to Pretrained NLI alone ($p = 0.021$)**.  
> Standalone neural models consistently over-predict contradiction when confronted with irrelevant customer statements (e.g. broken screens, power outages).

---

### 4. 1,000-Sample Paired Bootstrap Distributions

```carousel
#### Bootstrap: Rules (A) vs. Pretrained NLI (B) [N=60]
```text
Empirical Mean Accuracy Difference: +3.33%
2.5th Percentile:  -13.33%
97.5th Percentile: +20.00%
95% Bootstrap CI: [-13.33%, +20.00%]  --> SPANS ZERO (p > 0.05)
```
<!-- slide -->
#### Bootstrap: Legacy Hybrid (D) vs. Rules + Pretrained (C) [N=60]
```text
Empirical Mean Accuracy Difference: +16.67%
2.5th Percentile:  +3.33%
97.5th Percentile: +30.00%
95% Bootstrap CI: [+3.33%, +30.00%]  --> COMPLETELY ABOVE ZERO (p < 0.05)
```
<!-- slide -->
#### Bootstrap: Rules (A) vs. Pretrained NLI (B) [Hidden Set N=30]
```text
Empirical Mean Accuracy Difference: -33.33% (Favoring Rules)
2.5th Percentile:  -53.33%
97.5th Percentile: -13.33%
95% Bootstrap CI: [-53.33%, -13.33%] --> STATISTICALLY SIGNIFICANT FAVORING RULES
```
````

---

### 5. Final Scientific Conclusion of the Paired Analysis

1. **The Legacy Fine-Tuned Model is Obsolete:** On both the dev holdout ($p=0.031$) and hidden test set ($p=0.035$), the legacy fine-tuned model is statistically significantly inferior. Its 21 false contradictions make it unsafe for autonomous classification.
2. **Pretrained NLI Does Not Beat Rules:** On the dev set, Pretrained NLI shows no significant difference ($p=0.845$); on the hidden set, it is significantly worse than rules ($p=0.021$).
3. **The Optimal Architectural Blueprint:** ProofLedger must be architected as a **Rules-First Deterministic Engine**, utilizing Pretrained NLI strictly as an assistive drafting copilot for text similarity, never allowing neural logits to override deterministic financial validation.

