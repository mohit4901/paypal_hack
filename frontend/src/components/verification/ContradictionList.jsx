import React from 'react';
import { XCircle, AlertTriangle, Info } from 'lucide-react';
import StatusBadge from '../ui/StatusBadge';

export default function ContradictionList({
  validationErrors = [],
  aiPrep = null,
  claimVerification = null,
}) {
  const verifiedClaims = claimVerification?.verified_claims || [];
  const rel = aiPrep?.relevance_signal || {};

  // 1. Deterministic Mismatches
  const detContradictions = [...validationErrors];
  for (const vc of verifiedClaims) {
    if (vc.deterministic_rule_triggered && vc.verdict === 'CONTRADICTED') {
      detContradictions.push(`${vc.claim_text}: ${vc.explanation}`);
    }
  }

  // 2. AI-Identified Inconsistencies
  const aiInconsistencies = [];
  for (const vc of verifiedClaims) {
    if (!vc.deterministic_rule_triggered && (vc.verdict === 'CONTRADICTED' || vc.rule_vs_model_disagreement)) {
      aiInconsistencies.push({
        text: vc.claim_text,
        detail: vc.disagreement_detail || vc.explanation || 'Model detected conflict between claim and supplied evidence.',
        status: vc.verdict,
      });
    }
  }
  if (rel.verdict === 'CONTRADICTED' && aiInconsistencies.length === 0) {
    aiInconsistencies.push({
      text: 'Fulfillment statement alignment',
      detail: 'Advisory NLI model flagged a potential contradiction in submitted fulfillment text.',
      status: 'CONTRADICTED',
    });
  }

  // 3. Missing / Unverified Evidence
  const unverifiedItems = [];
  for (const it of aiPrep?.evidence_items || []) {
    if (['LOOKUP_NOT_CONFIGURED', 'NOT_PROVIDED', 'NOT_INDEPENDENTLY_VERIFIED'].includes(it.status)) {
      unverifiedItems.push({
        label: it.item,
        status: it.status,
        detail: it.explanation,
      });
    }
  }

  return (
    <section className="bg-white rounded-xl border border-[#E6E4DD] p-5 sm:p-6 space-y-5">
      <div className="pb-4 border-b border-[#EFECE4]">
        <h2 className="text-base font-semibold text-[#18181B]">
          Contradictions &amp; Risk Indicators
        </h2>
        <p className="text-xs text-[#52525B] mt-0.5">
          Separates authoritative deterministic mismatches from advisory AI suggestions and missing records.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* Confirmed Deterministic Mismatch */}
        <div className="rounded-xl border border-[#E6E4DD] bg-[#FCFBF8] p-4 space-y-2.5">
          <div className="flex items-center gap-2 text-xs font-semibold text-[#18181B]">
            <XCircle className="w-4 h-4 text-rose-600 shrink-0" />
            <span>Confirmed deterministic mismatch</span>
          </div>
          {detContradictions.length === 0 ? (
            <p className="text-xs text-[#71717A]">
              No deterministic order, capture, currency, or amount mismatches detected.
            </p>
          ) : (
            <ul className="space-y-2">
              {detContradictions.map((err, i) => (
                <li key={i} className="text-xs text-rose-900 bg-rose-50 border border-rose-200 rounded-lg p-2.5">
                  {err}
                </li>
              ))}
            </ul>
          )}
        </div>

        {/* AI-Identified Inconsistency */}
        <div className="rounded-xl border border-[#E6E4DD] bg-[#FCFBF8] p-4 space-y-2.5">
          <div className="flex items-center gap-2 text-xs font-semibold text-[#18181B]">
            <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0" />
            <span>AI-identified inconsistency</span>
          </div>
          {aiInconsistencies.length === 0 ? (
            <p className="text-xs text-[#71717A]">
              No semantic contradictions flagged by the DeBERTa advisory model.
            </p>
          ) : (
            <ul className="space-y-2">
              {aiInconsistencies.map((inc, i) => (
                <li key={i} className="text-xs bg-amber-50/70 border border-amber-200 rounded-lg p-2.5 space-y-1">
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-semibold text-amber-950">AI suggestion — review required</span>
                    <StatusBadge size="xs" status={inc.status} />
                  </div>
                  <div className="text-amber-900">{inc.detail}</div>
                </li>
              ))}
            </ul>
          )}
        </div>

        {/* Missing / Unverified Evidence */}
        <div className="rounded-xl border border-[#E6E4DD] bg-[#FCFBF8] p-4 space-y-2.5">
          <div className="flex items-center gap-2 text-xs font-semibold text-[#18181B]">
            <Info className="w-4 h-4 text-[#71717A] shrink-0" />
            <span>Missing / not independently verified</span>
          </div>
          {unverifiedItems.length === 0 ? (
            <p className="text-xs text-[#71717A]">No missing or unverified fields reported.</p>
          ) : (
            <ul className="space-y-2">
              {unverifiedItems.map((it, i) => (
                <li key={i} className="text-xs bg-white border border-[#E6E4DD] rounded-lg p-2.5 space-y-1">
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-medium text-[#18181B]">{it.label}</span>
                    <StatusBadge
                      size="xs"
                      status={it.status}
                      label={it.status === 'NOT_PROVIDED' ? 'Not provided' : 'Not independently verified'}
                    />
                  </div>
                  <div className="text-[11px] text-[#52525B]">{it.detail}</div>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </section>
  );
}

