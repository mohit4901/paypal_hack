# PROOFLEDGER AI RESEARCH REPORT
## PHASE B: PAIRED STATISTICAL COMPARISON & HYPOTHESIS TESTING

**Audit Date:** November 4, 2026  
**Investigator:** Applied NLP Research Scientist & Statistical Auditor  
**Focus:** Paired McNemar Test, Discordant Pair Decomposition & Bootstrap Confidence Intervals  
**Evaluation Set:** Frozen 60-Claim Balanced Holdout ($N=60$)  
**Baseline Model:** Deterministic Financial Rules (Arch A)  
**Candidate Model:** ProofLedger Hybrid Engine (Arch C)  

---

### 1. Executive Statistical Verdict

> [!CAUTION]
> **STATISTICAL HYPOTHESIS TEST OUTCOME: FAILED TO REJECT NULL HYPOTHESIS ($p = 0.16864$)**  
> An exact, paired statistical test between Deterministic Rules and the DeBERTa-powered Hybrid Engine demonstrates that **the apparent performance difference is NOT statistically significant** at the standard $\alpha = 0.05$ threshold.
> 
> Furthermore, all 95% confidence intervals for both accuracy difference ($[-29.64\%, +2.98\%]$) and Macro F1 difference ($[-28.04\%, +1.50\%]$) cross zero.  
> Claiming that the current fine-tuned DeBERTa model provides proven superiority over deterministic rules is scientifically invalid.

---

### 2. Paired 2x2 Contingency Table

Because the evaluation was conducted on the identical set of 60 claims, standard independent two-sample t-tests are invalid due to paired dependencies. We construct the canonical $2\times 2$ paired contingency table:

| Paired Prediction Outcome | Hybrid Correct | Hybrid Incorrect | Marginal Total (Rules) |
|---|:---:|:---:|:---:|
| **Rules Correct** | $n_{11} = 26$ | $n_{10} = 17$ | **43** (71.67%) |
| **Rules Incorrect** | $n_{01} = 9$ | $n_{00} = 8$ | **17** (28.33%) |
| **Marginal Total (Hybrid)** | **35** (58.33%) | **25** (41.67%) | **60** (100.0%) |

#### Interpretation of Cells:
- **$n_{11} = 26$ (Concordant Success):** Both systems correctly classified the claim.
- **$n_{00} = 8$ (Concordant Failure):** Both systems failed (primarily subtle digital fulfillment claims and ambiguous logs).
- **$n_{10} = 17$ (Rules Advantage):** Rules succeeded where Hybrid failed. In all 17 cases, Rules correctly returned `INSUFFICIENT_EVIDENCE`, but DeBERTa overrode the decision with an aggressive, false `CONTRADICTED` verdict.
- **$n_{01} = 9$ (Hybrid Advantage):** Hybrid succeeded where Rules failed. In these 9 cases, Rules failed closed to `INSUFFICIENT_EVIDENCE`, but DeBERTa correctly identified positive semantic fulfillment (e.g. LMS user sessions, 2FA logins, workshop duration).

---

### 3. Formal Hypothesis Testing: McNemar's Exact Test

We test the null hypothesis:
$$H_0: P(\text{Rules Correct, Hybrid Incorrect}) = P(\text{Rules Incorrect, Hybrid Correct}) \iff p_{10} = p_{01}$$
against the two-sided alternative $H_1: p_{10} \neq p_{01}$.

Under $H_0$, the number of discordant pairs $n_{01}$ out of $N_{\text{discordant}} = n_{10} + n_{01} = 17 + 9 = 26$ follows a binomial distribution:
$$n_{01} \sim \text{Binomial}(26, 0.5)$$

Using the exact two-tailed binomial test:
$$p\text{-value} = 2 \times \sum_{k=0}^{9} \binom{26}{k} (0.5)^k (0.5)^{26 - k} = 0.16864$$

#### Decision:
Since $p = 0.16864 > 0.05$, we **fail to reject $H_0$**. There is no statistically significant evidence that the hybrid engine outperforms deterministic financial rules on this holdout.

---

### 4. Confidence Intervals for Paired Difference

#### A. Accuracy Difference (Newcombe-Wilson Paired Method)
$$\hat{\Delta} = \text{Acc}_{\text{Hybrid}} - \text{Acc}_{\text{Rules}} = 58.33\% - 71.67\% = -13.33\%$$
The standard error of the paired difference is:
$$\text{SE}(\hat{\Delta}) = \frac{\sqrt{n_{10} + n_{01} - \frac{(n_{10} - n_{01})^2}{N}}}{N} = \frac{\sqrt{26 - \frac{(8)^2}{60}}}{60} = \frac{\sqrt{26 - 1.067}}{60} = \frac{4.993}{60} \approx 0.0832\ (8.32\%)$$
At 95% confidence level ($z = 1.96$):
$$\text{CI}_{95\%} = -13.33\% \pm (1.96 \times 8.32\%) = -13.33\% \pm 16.31\% = \mathbf{[-29.64\%, +2.98\%]}$$

#### B. 1,000-Sample Bootstrap for Macro F1 Difference
We executed 1,000 paired bootstrap resamples of size 60 with replacement:
- Empirical Mean Macro F1 Difference: **$-13.78\%$**
- 2.5th Percentile: **$-28.04\%$**
- 97.5th Percentile: **$+1.50\%$**
- **$95\%$ Bootstrap CI:** $\mathbf{[-28.04\%, +1.50\%]}$

Both the asymptotic parametric CI and the non-parametric bootstrap CI span zero, confirming that neither metric achieves statistical separation.

---

### 5. Detailed Breakdown of the 26 Discordant Cases

#### A. The 17 Cases Where Rules Won ($n_{10}$)
In all 17 instances, the ground truth was `INSUFFICIENT_EVIDENCE` or subtle contradiction. The deterministic rules engine safely defaulted to `INSUFFICIENT_EVIDENCE` (100% correct). However, DeBERTa-v3 suffered from its catastrophic domain bias: it observed lexical dissimilarity between claim and evidence and assigned $>80\%$ probability to `CONTRADICTED`.
- *Example 1 (SMPL-41):* Claim: "dissatisfied with teaching voice quality". Evidence: "completed 4 lessons". Rules: `INSUFFICIENT_EVIDENCE` (Correct). DeBERTa: `CONTRADICTED` (Wrong).
- *Example 2 (SMPL-44):* Claim: "computer monitor stopped displaying colors". Evidence: "CDN transferred 12.4 MB". Rules: `INSUFFICIENT_EVIDENCE` (Correct). DeBERTa: `CONTRADICTED` (Wrong).

#### B. The 9 Cases Where Hybrid Won ($n_{01}$)
In these 9 instances, the claim required semantic reasoning that simple regex keywords could not parse. DeBERTa successfully identified semantic entailment:
- *Example 1 (SMPL-07):* Claim: "Two-factor login was confirmed from registered mobile device." Evidence: "Auth service log shows 2FA TOTP token verified from registered iPhone device." Rules: `INSUFFICIENT_EVIDENCE` (keyword missed). DeBERTa: `SUPPORTED` (Correct, 94.0% confidence).
- *Example 2 (SMPL-14):* Claim: "Student attended live online workshop session for 65 minutes." Evidence: "Webinar telemetry logs student connected duration 65 minutes." Rules: `INSUFFICIENT_EVIDENCE`. DeBERTa: `SUPPORTED` (Correct, 92.5% confidence).

---

### 6. Selective Risk vs. Coverage Analysis

When the abstention threshold ($\text{Margin} < 0.15$ or $\text{Conf} < 0.50$) is applied:
- **Total Abstentions:** 4 claims (6.67%)
- **Coverage:** 56 / 60 claims (93.33%)
- **Selective Accuracy:** 33 / 56 acted claims (**58.93%**)
- **Selective Risk (Error Rate on Acted Cases):** 23 / 56 (**41.07%**)

```
Coverage Rate (%)      100.0%       93.33%       80.00% (High Thresh)
Selective Acc (%)       58.33%       58.93%       62.50%
Selective Risk (%)      41.67%       41.07%       37.50%
```
Because the current model's false contradictions are assigned with high uncalibrated confidence ($>85\%$), the abstention threshold only filtered out 4 cases. To effectively reduce selective risk below 20%, temperature scaling and recalibration on a clean validation dataset are mandatory.

