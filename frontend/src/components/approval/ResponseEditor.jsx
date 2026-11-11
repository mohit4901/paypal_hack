import React from 'react';
import { FileText, AlertTriangle, CheckCircle2 } from 'lucide-react';
import CopyButton from '../ui/CopyButton';
import StatusBadge from '../ui/StatusBadge';

export default function ResponseEditor({
  dispute,
  aiPrep,
  editableDraft,
  onChangeDraft,
  uploadedFiles = [],
  approvalReceipt = null,
  approvalInvalidatedMsg = null,
}) {
  const isLive = Boolean(dispute?.is_live_paypal_dispute);
  const grounding = aiPrep?.grounding_sources || [];
  const missing = aiPrep?.missing_evidence || [];

  return (
    <div className="bg-white rounded-xl border border-[#E6E4DD] p-5 sm:p-6 space-y-5">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pb-4 border-b border-[#EFECE4]">
        <div>
          <h2 className="text-base font-semibold text-[#18181B]">
            Prepare Your PayPal Response
          </h2>
          <p className="text-xs text-[#52525B] mt-0.5">
            Inspect verified evidence references on the left and edit your defense statement on the right.
          </p>
        </div>

        <span
          className={`inline-flex items-center px-2.5 py-1 rounded-md text-[11px] font-medium border self-start sm:self-center ${
            isLive
              ? 'bg-emerald-50 text-emerald-800 border-emerald-200'
              : 'bg-stone-100 text-stone-700 border-stone-200'
          }`}
        >
          {isLive ? 'PAYPAL SANDBOX LIVE' : 'LOCAL DEMO — NOT A PAYPAL DISPUTE'}
        </span>
      </div>

      {approvalInvalidatedMsg && (
        <div className="rounded-xl border border-amber-300 bg-amber-50 p-3.5 flex items-start gap-2.5 text-xs text-amber-950">
          <AlertTriangle className="w-4 h-4 text-amber-700 shrink-0 mt-0.5" />
          <div>
            <div className="font-semibold">Approval Invalidated — Changes require re-approval</div>
            <div className="mt-0.5 text-amber-900">{approvalInvalidatedMsg}</div>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
        {/* Left: Evidence & Verification References */}
        <div className="lg:col-span-5 space-y-4">
          <div className="rounded-xl border border-[#E6E4DD] bg-[#FCFBF8] p-4 space-y-3">
            <div className="text-xs font-semibold text-[#18181B] flex items-center gap-1.5">
              <FileText className="w-4 h-4 text-[#0F766E]" />
              <span>Evidence &amp; Verification References</span>
            </div>

            {grounding.length === 0 ? (
              <p className="text-xs text-[#71717A]">
                Run analysis to populate grounded evidence references.
              </p>
            ) : (
              <ul className="space-y-2">
                {grounding.map((g, i) => (
                  <li key={i} className="bg-white rounded-lg border border-[#EFECE4] p-2.5 text-xs space-y-1">
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-medium text-[#18181B]">{g.supporting_source}</span>
                      <StatusBadge size="xs" status={g.verification_status} />
                    </div>
                    <div className="font-mono text-[11px] text-[#52525B]">{g.source_reference}</div>
                  </li>
                ))}
              </ul>
            )}

            {uploadedFiles.length > 0 && (
              <div className="pt-2 border-t border-[#EFECE4] space-y-1.5">
                <div className="text-[11px] font-medium text-[#52525B]">Supporting attachments</div>
                {uploadedFiles.map((f) => (
                  <div key={f.localId} className="flex flex-wrap items-center justify-between gap-1.5 text-[11px] bg-white border border-[#EFECE4] rounded-md px-2.5 py-1.5">
                    <span className="truncate font-medium text-[#18181B]">{f.name}</span>
                    <div className="flex items-center gap-1 shrink-0">
                      <span className="font-mono text-[10px] text-emerald-700">
                        <CheckCircle2 className="w-3 h-3 inline mr-0.5" />
                        SHA-256 verified
                      </span>
                      <span className="font-mono text-[10px] px-1 py-0.5 rounded bg-sky-50 text-sky-800 border border-sky-200">
                        CONTENT_NOT_EXTRACTED
                      </span>
                    </div>
                  </div>
                ))}
                <p className="text-[10px] text-[#71717A] leading-relaxed">
                  Uploaded PDFs/images are SHA-256 integrity verified only (`CONTENT_NOT_EXTRACTED`); file contents are not OCR-extracted or verified automatically.
                </p>
              </div>
            )}

            {missing.length > 0 && (
              <div className="pt-2 border-t border-[#EFECE4] space-y-1">
                <div className="text-[11px] font-medium text-amber-800">Outstanding items</div>
                {missing.map((m, i) => (
                  <div key={i} className="text-[11px] text-amber-900">
                    • {m}
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Right: Editable Response Draft */}
        <div className="lg:col-span-7 space-y-2.5">
          <div className="flex items-center justify-between gap-2">
            <label htmlFor="draftResponseTextarea" className="text-xs font-semibold text-[#18181B]">
              Merchant Response Statement (Editable)
            </label>
            <div className="flex items-center gap-2">
              {approvalReceipt ? (
                <StatusBadge size="xs" variant="verified" label="Draft locked to SHA-256 seal" />
              ) : (
                <span className="text-[11px] text-[#71717A]">
                  Editing clears prior approval
                </span>
              )}
              <CopyButton value={editableDraft} label="Copy" />
            </div>
          </div>

          <textarea
            id="draftResponseTextarea"
            rows={11}
            value={editableDraft}
            onChange={(e) => onChangeDraft(e.target.value)}
            placeholder="Your factual merchant defense response will appear here once analysis completes..."
            className="w-full px-3.5 py-3 rounded-xl text-xs leading-relaxed bg-white border border-[#E6E4DD] text-[#18181B] focus:outline-none focus:ring-2 focus:ring-[#0F766E]/20 focus:border-[#0F766E] font-sans"
          />

          <div className="flex items-center justify-between text-[11px] text-[#71717A]">
            <span>Only assert facts backed by order, capture, or carrier records.</span>
            <span className="font-mono tabular-nums">{editableDraft.length} chars</span>
          </div>
        </div>
      </div>
    </div>
  );
}

