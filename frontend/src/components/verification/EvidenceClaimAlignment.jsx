import React, { useState } from 'react';
import { RefreshCw, Info, ChevronDown, ChevronUp } from 'lucide-react';
import StatusBadge from '../ui/StatusBadge';

const NLI_DESCRIPTIONS = {
  SUPPORTED: 'The available evidence supports this statement.',
  CONTRADICTED: 'The available evidence conflicts with this statement.',
  INSUFFICIENT_EVIDENCE: 'The evidence provided does not establish this statement.',
  NEEDS_HUMAN_REVIEW: 'Model confidence/margin below abstention threshold — merchant human review required.',
  UNAVAILABLE: 'Neural AI model unavailable.',
};

export default function EvidenceClaimAlignment({
  claimText,
  onChangeClaimText,
  onReverifyClaim,
  claimsStale = false,
  verifyingClaims = false,
  claimVerification = null,
  aiPrep = null,
  uploadedFiles = [],
}) {
  const [expandedRow, setExpandedRow] = useState(null);

  const verifiedClaims = claimVerification?.verified_claims || [];
  const evidenceRecords = claimVerification?.evidence_records || [];
  const groundingSources = aiPrep?.grounding_sources || [];
  const rel = aiPrep?.relevance_signal || {};

  return (
    <section className="bg-white rounded-xl border border-[#E6E4DD] p-5 sm:p-6 space-y-5">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-4 border-b border-[#EFECE4]">
        <div>
          <h2 className="text-base font-semibold text-[#18181B]">
            How Your Evidence Supports the Claim
          </h2>
          <p className="text-xs text-[#52525B] mt-0.5">
            AI assessment — not an independently verified fact. Evaluates structured order text and merchant notes only (uploaded PDF/image contents are not OCR-parsed).
          </p>
        </div>

        {claimsStale && (
          <StatusBadge size="xs" status="STALE" label="Claim modified — re-verify required" />
        )}
      </div>

      {/* Inline Editable Claim + Re-Verify Control (for Test 9) */}
      <div className="rounded-lg bg-[#FCFBF8] border border-[#E6E4DD] p-4 space-y-2.5">
        <div className="flex items-center justify-between gap-2">
          <label htmlFor="editableClaimInput" className="text-xs font-semibold text-[#18181B]">
            Active merchant claim under evaluation
          </label>
          <span className="text-[11px] text-[#71717A]">
            Editing invalidates previous approval
          </span>
        </div>
        <div className="flex flex-col sm:flex-row gap-2">
          <input
            id="editableClaimInput"
            type="text"
            value={claimText || ''}
            onChange={(e) => onChangeClaimText && onChangeClaimText(e.target.value)}
            placeholder="Enter a factual statement to test against evidence..."
            className="flex-1 px-3 py-2 rounded-lg text-xs bg-white border border-[#E6E4DD] text-[#18181B] focus:outline-none focus:ring-2 focus:ring-[#0F766E]/20 focus:border-[#0F766E]"
          />
          {onReverifyClaim && (
            <button
              type="button"
              onClick={onReverifyClaim}
              disabled={verifyingClaims || !claimText?.trim()}
              className="inline-flex items-center justify-center gap-1.5 px-3.5 py-2 rounded-lg text-xs font-medium bg-[#18181B] text-white hover:bg-[#27272A] disabled:opacity-50 transition-colors shrink-0"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${verifyingClaims ? 'animate-spin' : ''}`} />
              <span>{verifyingClaims ? 'Evaluating...' : 'Re-verify Claim'}</span>
            </button>
          )}
        </div>
      </div>

      {/* Claim Alignment Results */}
      {verifiedClaims.length > 0 ? (
        <div className="space-y-3">
          {verifiedClaims.map((vc, idx) => {
            const label = vc.verdict || vc.ai_model?.label || 'INSUFFICIENT_EVIDENCE';
            const desc = NLI_DESCRIPTIONS[label] || NLI_DESCRIPTIONS.INSUFFICIENT_EVIDENCE;
            const isOpen = expandedRow === idx;
            const matchingEv =
              evidenceRecords.find((ev) =>
                (vc.supporting_sources || vc.contradicting_sources || []).includes(ev.evidence_id)
              ) || evidenceRecords[0];

            return (
              <div
                key={vc.claim_id || idx}
                className="rounded-xl border border-[#E6E4DD] bg-white overflow-hidden"
              >
                <div className="p-4 space-y-3">
                  <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-2">
                    <div className="space-y-1">
                      <div className="text-[11px] font-mono text-[#71717A]">
                        Merchant Claim · {vc.claim_id || `CLM-${idx + 1}`}
                        {vc.deterministic_rule_triggered && ' · DETERMINISTIC OVERRIDE'}
                      </div>
                      <div className="text-sm font-medium text-[#18181B]">
                        &ldquo;{vc.claim_text}&rdquo;
                      </div>
                    </div>
                    <StatusBadge size="sm" status={label} />
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs bg-[#F8F7F3] border border-[#EFECE4] rounded-lg p-3">
                    <div>
                      <div className="text-[11px] text-[#71717A]">Evidence document / source</div>
                      <div className="font-medium text-[#18181B] mt-0.5">
                        {matchingEv?.source_name ||
                          matchingEv?.source_type ||
                          uploadedFiles[0]?.response?.filename ||
                          'Submitted Transaction & Fulfillment Records'}
                      </div>
                      {matchingEv?.content && (
                        <div className="text-[11px] text-[#52525B] mt-1 line-clamp-2 font-mono">
                          {matchingEv.content}
                        </div>
                      )}
                    </div>
                    <div>
                      <div className="text-[11px] text-[#71717A]">AI assessment</div>
                      <div className="font-medium text-[#18181B] mt-0.5">{desc}</div>
                      <div className="text-[11px] text-[#52525B] mt-1">
                        {vc.explanation || 'Evaluated via deterministic rules and DeBERTa NLI.'}
                      </div>
                    </div>
                  </div>

                  <div className="flex flex-wrap items-center justify-between gap-2 text-[11px] text-[#71717A]">
                    <span className="inline-flex items-center gap-1">
                      <Info className="w-3.5 h-3.5 text-[#0F766E]" />
                      AI assessment — not an independently verified fact.
                      {vc.ai_model?.calibrated_confidence != null && (
                        <span className="font-mono ml-1">
                          · Calibrated score: {(vc.ai_model.calibrated_confidence * 100).toFixed(1)}%
                        </span>
                      )}
                    </span>

                    <button
                      type="button"
                      onClick={() => setExpandedRow(isOpen ? null : idx)}
                      className="inline-flex items-center gap-1 font-medium text-[#52525B] hover:text-[#18181B]"
                    >
                      <span>Deterministic &amp; model details</span>
                      {isOpen ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
                    </button>
                  </div>
                </div>

                {isOpen && (
                  <div className="px-4 pb-4 pt-2 border-t border-[#EFECE4] bg-[#FCFBF8] space-y-2 text-xs">
                    <div className="font-medium text-[#3F3F46]">
                      Verdict engine: <code className="font-mono">{vc.verdict_engine}</code>
                      {vc.ai_model?.calibration_status && (
                        <span> · Calibration: <code className="font-mono">{vc.ai_model.calibration_status}</code></span>
                      )}
                    </div>
                    {Array.isArray(vc.deterministic_checks) && vc.deterministic_checks.length > 0 && (
                      <div className="space-y-1">
                        {vc.deterministic_checks.map((chk, cIdx) => (
                          <div key={cIdx} className="text-[11px] font-mono text-[#52525B]">
                            [{chk.passed ? 'PASS' : 'FLAG'}] {chk.check}: {chk.message}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      ) : (
        /* Fallback display using stream relevance_signal when verify-claims hasn't returned yet */
        rel.verdict && (
          <div className="rounded-lg border border-[#E6E4DD] p-4 space-y-2 text-xs">
            <div className="flex items-center justify-between gap-2">
              <span className="font-medium text-[#18181B]">
                Fulfillment Statement Semantic Alignment
              </span>
              <StatusBadge size="xs" status={rel.verdict} />
            </div>
            <p className="text-[#52525B]">
              {NLI_DESCRIPTIONS[rel.verdict] || 'Evaluated via streaming NLI check.'}
            </p>
            <div className="text-[11px] text-[#71717A]">
              AI assessment — not an independently verified fact.
            </div>
          </div>
        )
      )}

      {/* Sentence-Level Grounding Sources from Backend */}
      {groundingSources.length > 0 && (
        <div className="space-y-2 pt-2">
          <div className="text-xs font-semibold text-[#3F3F46]">
            Source-Linked Citations (returned by backend)
          </div>
          <div className="overflow-x-auto border border-[#E6E4DD] rounded-lg">
            <table className="w-full text-left text-xs border-collapse">
              <thead>
                <tr className="bg-[#FCFBF8] border-b border-[#E6E4DD] text-[11px] text-[#52525B]">
                  <th className="py-2 px-3">Statement</th>
                  <th className="py-2 px-3">Source</th>
                  <th className="py-2 px-3">Reference</th>
                  <th className="py-2 px-3">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#EFECE4]">
                {groundingSources.map((src, i) => (
                  <tr key={i}>
                    <td className="py-2.5 px-3 text-[#18181B]">{src.statement}</td>
                    <td className="py-2.5 px-3 text-[#52525B] whitespace-nowrap">{src.supporting_source}</td>
                    <td className="py-2.5 px-3 font-mono text-[11px] text-[#52525B]">{src.source_reference}</td>
                    <td className="py-2.5 px-3">
                      <StatusBadge size="xs" status={src.verification_status} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </section>
  );
}

