import React from 'react';
import { ShieldAlert, Cpu, CheckCircle2, AlertTriangle, XCircle, HelpCircle } from 'lucide-react';
import StatusBadge from '../ui/StatusBadge';

export default function VerificationSummary({
  aiPrep,
  claimVerification,
  systemStatus,
  deterministicFailures = [],
}) {
  const aiModelStatus = systemStatus?.ai_model || {};
  const rel = aiPrep?.relevance_signal || {};
  const engineMeta = claimVerification?.ai_engine || {};

  const isModelOffline =
    aiModelStatus.status === 'MODEL_UNAVAILABLE' ||
    aiModelStatus.is_loaded === false ||
    rel.status === 'MODEL_UNAVAILABLE' ||
    rel.status === 'MODEL_OFFLINE' ||
    rel.status === 'MODEL_FAILED' ||
    engineMeta.status === 'OFFLINE';

  const activeCheckpoint =
    rel.model_path ||
    engineMeta.checkpoint ||
    aiModelStatus.loaded_model_path ||
    'Unavailable';

  const items = aiPrep?.evidence_items || [];
  const verifiedCount = items.filter((it) =>
    ['VERIFIED_ON_PAYPAL', 'VERIFIED_ON_MERCHANT_RECORD', 'FORMAT_VALID'].includes(it.status)
  ).length;
  const warningCount = items.filter((it) =>
    ['MERCHANT_ATTESTATION', 'LOOKUP_NOT_CONFIGURED', 'NOT_INDEPENDENTLY_VERIFIED'].includes(it.status)
  ).length;
  const unresolvedCount = (aiPrep?.missing_evidence || []).length;

  const nliClaims = claimVerification?.verified_claims || [];
  const aiContradictions = nliClaims.filter((c) => c.verdict === 'CONTRADICTED').length;
  const totalContradictions =
    deterministicFailures.length +
    aiContradictions +
    (rel.verdict === 'CONTRADICTED' && aiContradictions === 0 ? 1 : 0);

  const readiness = isModelOffline
    ? 'MODEL_UNAVAILABLE'
    : aiPrep?.evidence_readiness || 'NEEDS_ATTENTION';

  return (
    <section className="bg-white rounded-xl border border-[#E6E4DD] p-5 sm:p-6 space-y-5">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-4 border-b border-[#EFECE4]">
        <div>
          <h2 className="text-base font-semibold text-[#18181B]">Verification Summary</h2>
          <p className="text-xs text-[#52525B] mt-0.5">
            AI-assisted assessment — merchant review required. Does not predict or determine PayPal&apos;s dispute ruling.
          </p>
        </div>

        <StatusBadge
          status={readiness}
          label={
            readiness === 'READY_FOR_SELLER_APPROVAL'
              ? 'Ready for Merchant Review'
              : readiness === 'MODEL_UNAVAILABLE'
              ? 'MODEL_UNAVAILABLE (Fail-Closed)'
              : readiness.replace(/_/g, ' ')
          }
        />
      </div>

      {isModelOffline && (
        <div className="rounded-xl border border-rose-200 bg-rose-50 p-4 flex items-start gap-3">
          <ShieldAlert className="w-5 h-5 text-rose-600 shrink-0 mt-0.5" />
          <div className="text-xs text-rose-900 space-y-1">
            <div className="font-semibold">
              Neural NLI model unavailable — failing closed to deterministic checks only
            </div>
            <p className="text-rose-800 leading-relaxed">
              {rel.error ||
                aiModelStatus.model_load_error ||
                'Configured DeBERTa-v3 candidate checkpoint is not loaded. Semantic claim predictions are unavailable and will never silently fall back to legacy weights or fabricated scores.'}
            </p>
          </div>
        </div>
      )}

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <div className="p-3.5 rounded-lg bg-[#FCFBF8] border border-[#EFECE4]">
          <div className="flex items-center justify-between text-xs text-[#52525B]">
            <span>Checks passed</span>
            <CheckCircle2 className="w-4 h-4 text-emerald-600" />
          </div>
          <div className="mt-1.5 text-xl font-semibold tabular-nums text-[#18181B]">
            {verifiedCount}
          </div>
        </div>

        <div className="p-3.5 rounded-lg bg-[#FCFBF8] border border-[#EFECE4]">
          <div className="flex items-center justify-between text-xs text-[#52525B]">
            <span>Warnings</span>
            <AlertTriangle className="w-4 h-4 text-amber-600" />
          </div>
          <div className="mt-1.5 text-xl font-semibold tabular-nums text-[#18181B]">
            {warningCount}
          </div>
        </div>

        <div className="p-3.5 rounded-lg bg-[#FCFBF8] border border-[#EFECE4]">
          <div className="flex items-center justify-between text-xs text-[#52525B]">
            <span>Unresolved items</span>
            <HelpCircle className="w-4 h-4 text-[#71717A]" />
          </div>
          <div className="mt-1.5 text-xl font-semibold tabular-nums text-[#18181B]">
            {unresolvedCount}
          </div>
        </div>

        <div className="p-3.5 rounded-lg bg-[#FCFBF8] border border-[#EFECE4]">
          <div className="flex items-center justify-between text-xs text-[#52525B]">
            <span>Contradictions</span>
            <XCircle className="w-4 h-4 text-rose-600" />
          </div>
          <div className="mt-1.5 text-xl font-semibold tabular-nums text-[#18181B]">
            {totalContradictions}
          </div>
        </div>
      </div>

      {/* Model Provenance Strip */}
      <div className="rounded-lg bg-[#F8F7F3] border border-[#EFECE4] px-3.5 py-2.5 flex flex-col sm:flex-row sm:items-center justify-between gap-2 text-xs">
        <div className="flex items-center gap-2 min-w-0">
          <Cpu className="w-3.5 h-3.5 text-[#0F766E] shrink-0" />
          <span className="text-[#52525B] shrink-0">Active model checkpoint:</span>
          <span className="font-mono text-[11px] text-[#18181B] truncate" title={activeCheckpoint}>
            {activeCheckpoint}
          </span>
        </div>
        <div className="text-[11px] font-mono text-[#71717A] shrink-0">
          Device: {(aiModelStatus.device || engineMeta.device || 'unknown').toUpperCase()} · Status: {isModelOffline ? 'MODEL_UNAVAILABLE' : 'INVOKED'}
        </div>
      </div>
    </section>
  );
}

