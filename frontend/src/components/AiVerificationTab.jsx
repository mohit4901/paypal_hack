import React from 'react';
import {
  CheckCircle2,
  AlertTriangle,
  XCircle,
  FileCheck2,
  ArrowRight,
  ShieldCheck,
  FileText,
  HelpCircle,
  Sparkles,
} from 'lucide-react';

export default function AiVerificationTab({
  packet,
  onProceedToReport,
  onBackToClaims,
}) {
  if (!packet) {
    return (
      <div className="bg-white p-12 rounded-xl border border-[#E5E7EB] text-center space-y-4">
        <Sparkles className="h-8 w-8 text-[#9CA3AF] mx-auto" />
        <h3 className="font-bold text-sm text-[#111827]">No Claims Evaluated Yet</h3>
        <p className="text-xs text-[#6B7280] max-w-sm mx-auto">
          Return to the Claim Builder to run deterministic rules and AI verification on your dispute claims.
        </p>
        <button
          onClick={onBackToClaims}
          className="px-4 py-2 bg-[#111827] text-white text-xs font-medium rounded-lg"
        >
          Open Claim Builder
        </button>
      </div>
    );
  }

  const claims = packet.verified_claims || [];
  const supportedCount = packet.supported_claims || 0;
  const insufficientCount = packet.insufficient_claims || 0;
  const contradictedCount = packet.contradicted_claims || 0;

  return (
    <div className="space-y-6 font-sans">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-[#E5E7EB]">
        <div>
          <h1 className="text-xl font-bold text-[#111827] tracking-tight">
            Claim Verification Findings
          </h1>
          <p className="text-xs text-[#6B7280] mt-0.5">
            Deterministic rule validation + DeBERTa NLI cross-examination against Order <code className="text-[#111827] font-bold">{packet.transaction_reference}</code>.
          </p>
        </div>

        <button
          onClick={onProceedToReport}
          className="bg-[#111827] hover:bg-[#1F2937] text-white px-5 py-2.5 rounded-lg text-xs font-medium shadow-sm flex items-center space-x-2 shrink-0 transition-colors"
        >
          <span>Assemble Evidence Packet</span>
          <ArrowRight className="h-3.5 w-3.5" />
        </button>
      </div>

      {/* Summary Score Banner */}
      <div className="p-5 rounded-xl border border-[#E5E7EB] bg-[#F9FAFB] flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div className="space-y-1">
          <div className="flex items-center space-x-2">
            <span className="font-bold text-sm text-[#111827]">
              Factual Assessment: {supportedCount} of {claims.length} Claims Proven
            </span>
            <span className="px-2 py-0.5 rounded text-[10px] font-mono font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
              {packet.overall_readiness}
            </span>
          </div>
          <p className="text-xs text-[#6B7280]">
            Payment and course access are verified by concrete records. Missing download logs flagged as insufficient to prevent overclaiming.
          </p>
        </div>

        <div className="flex items-center space-x-3 text-xs shrink-0 font-mono">
          <div className="px-3 py-1.5 rounded-lg bg-emerald-50 border border-emerald-200 text-emerald-800 text-center">
            <span className="block font-bold text-sm">{supportedCount}</span>
            <span className="text-[10px]">SUPPORTED</span>
          </div>
          <div className="px-3 py-1.5 rounded-lg bg-amber-50 border border-amber-200 text-amber-800 text-center">
            <span className="block font-bold text-sm">{insufficientCount}</span>
            <span className="text-[10px]">INSUFFICIENT</span>
          </div>
          <div className="px-3 py-1.5 rounded-lg bg-rose-50 border border-rose-200 text-rose-800 text-center">
            <span className="block font-bold text-sm">{contradictedCount}</span>
            <span className="text-[10px]">CONTRADICTED</span>
          </div>
        </div>
      </div>

      {/* Evaluated Claims Breakdown */}
      <div className="space-y-4">
        <h3 className="text-xs font-bold text-[#111827] uppercase tracking-wider">
          Claim-by-Claim Verification
        </h3>

        <div className="space-y-3">
          {claims.map((c, i) => {
            const isSupported = c.verdict === 'SUPPORTED';
            const isInsufficient = c.verdict === 'INSUFFICIENT_EVIDENCE';
            const isContradicted = c.verdict === 'CONTRADICTED';

            return (
              <div
                key={i}
                className="bg-white rounded-xl border border-[#E5E7EB] p-5 shadow-xs space-y-3 hover:border-[#D1D5DB] transition-colors"
              >
                <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-3">
                  <div className="flex items-start space-x-3">
                    <span className="h-5 w-5 rounded-full bg-[#F3F4F6] text-[#6B7280] font-mono text-[10px] font-bold flex items-center justify-center shrink-0 mt-0.5">
                      {i + 1}
                    </span>
                    <div>
                      <h4 className="text-xs font-bold text-[#111827] leading-relaxed">
                        {c.claim_text}
                      </h4>
                      <p className="text-[11px] text-[#4B5563] mt-1 leading-relaxed">
                        {c.explanation}
                      </p>
                    </div>
                  </div>

                  <div className="shrink-0 self-start sm:self-auto">
                    {isSupported && (
                      <span className="px-2.5 py-1 rounded text-[11px] font-bold font-mono bg-emerald-50 text-emerald-800 border border-emerald-200 flex items-center space-x-1">
                        <CheckCircle2 className="h-3 w-3" />
                        <span>SUPPORTED</span>
                      </span>
                    )}
                    {isInsufficient && (
                      <span className="px-2.5 py-1 rounded text-[11px] font-bold font-mono bg-amber-50 text-amber-800 border border-amber-200 flex items-center space-x-1">
                        <AlertTriangle className="h-3 w-3" />
                        <span>INSUFFICIENT</span>
                      </span>
                    )}
                    {isContradicted && (
                      <span className="px-2.5 py-1 rounded text-[11px] font-bold font-mono bg-rose-50 text-rose-800 border border-rose-200 flex items-center space-x-1">
                        <XCircle className="h-3 w-3" />
                        <span>CONTRADICTED</span>
                      </span>
                    )}
                  </div>
                </div>

                {/* Supporting Source Citations */}
                {c.supporting_sources && c.supporting_sources.length > 0 && (
                  <div className="bg-[#F9FAFB] p-2.5 rounded-lg border border-[#E5E7EB] text-[11px] flex items-center space-x-2">
                    <span className="font-semibold text-[#111827]">Corroborated by:</span>
                    <div className="flex flex-wrap gap-1.5">
                      {c.supporting_sources.map((src, sIdx) => (
                        <span
                          key={sIdx}
                          className="px-2 py-0.5 rounded font-mono text-[10px] bg-white border border-[#D1D5DB] text-[#111827]"
                        >
                          {src}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {/* Missing Evidence Notes */}
                {c.missing_evidence && c.missing_evidence.length > 0 && (
                  <div className="bg-[#FFFBEB] p-2.5 rounded-lg border border-[#FDE68A] text-[11px] text-[#92400E] space-y-0.5">
                    <span className="font-semibold block">Missing Information:</span>
                    {c.missing_evidence.map((m, mIdx) => (
                      <p key={mIdx}>• {m}</p>
                    ))}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

