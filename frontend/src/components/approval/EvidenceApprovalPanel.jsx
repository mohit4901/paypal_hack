import React from 'react';
import { ShieldCheck, Send, Lock, Loader2, CheckCircle2, Info } from 'lucide-react';
import StatusBadge from '../ui/StatusBadge';

export default function EvidenceApprovalPanel({
  dispute,
  carrierName,
  trackingNumber,
  merchantChecked,
  onToggleChecked,
  approving = false,
  approvalReceipt = null,
  approvalError = null,
  submitting = false,
  submissionResult = null,
  onRequestApprove,
  onSubmitEvidence,
}) {
  const isLive = Boolean(dispute?.is_live_paypal_dispute);
  const canApprove = Boolean(merchantChecked && carrierName?.trim() && trackingNumber?.trim() && !approving);

  return (
    <section className="bg-white rounded-xl border border-[#E6E4DD] p-5 sm:p-6 space-y-5">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pb-4 border-b border-[#EFECE4]">
        <div>
          <h2 className="text-base font-semibold text-[#18181B]">
            Merchant Review &amp; SHA-256 Approval
          </h2>
          <p className="text-xs text-[#52525B] mt-0.5">
            Explicit merchant review and cryptographic digest binding are enforced server-side before submission.
          </p>
        </div>

        <StatusBadge
          size="sm"
          variant={submissionResult ? 'verified' : approvalReceipt ? 'verified' : 'warning'}
          label={
            submissionResult
              ? isLive
                ? 'Submitted to PayPal'
                : 'LOCAL_SIMULATED_SUBMISSION'
              : approvalReceipt
              ? 'Server Approval Sealed'
              : 'Awaiting Merchant Approval'
          }
        />
      </div>

      {approvalError && (
        <div className="rounded-lg border border-rose-200 bg-rose-50 px-3.5 py-2.5 text-xs text-rose-900">
          {approvalError}
        </div>
      )}

      {/* Mandatory Review Checkbox */}
      <label
        htmlFor="merchantApprovalCheck"
        className="flex items-start gap-3 p-3.5 rounded-xl border border-[#E6E4DD] bg-[#FCFBF8] cursor-pointer hover:border-[#0F766E]/50 transition-colors"
      >
        <input
          id="merchantApprovalCheck"
          type="checkbox"
          checked={merchantChecked}
          onChange={(e) => onToggleChecked(e.target.checked)}
          disabled={Boolean(submissionResult)}
          className="mt-0.5 h-4 w-4 rounded border-[#D4D4D8] text-[#0F766E] focus:ring-[#0F766E]"
        />
        <span className="text-xs text-[#18181B] leading-relaxed">
          I have reviewed the order verification, Delivery Verification Journey, AI advisory assessments, and editable response draft, and I authorize sealing this exact evidence package under server-side SHA-256 binding.
        </span>
      </label>

      {/* Active Server-Side SHA-256 Receipt */}
      {approvalReceipt && (
        <div className="rounded-xl border border-emerald-200 bg-emerald-50/70 p-4 space-y-2 text-xs text-emerald-950">
          <div className="flex items-center justify-between gap-2">
            <span className="font-semibold inline-flex items-center gap-1.5">
              <CheckCircle2 className="w-4 h-4 text-emerald-700" />
              <span>Server Approval Sealed</span>
            </span>
            <span className="font-mono text-[11px] bg-white px-2 py-0.5 rounded border border-emerald-200">
              {approvalReceipt.approval_id}
            </span>
          </div>
          <div className="font-mono text-[11px] text-emerald-900 break-all">
            SHA-256 Digest: {approvalReceipt.evidence_digest}
          </div>
          <div className="text-[11px] text-emerald-800">
            Approved at: {new Date(approvalReceipt.approved_at).toLocaleString()}
          </div>
        </div>
      )}

      {/* Submission Receipt */}
      {submissionResult && (
        <div className="rounded-xl border border-[#E6E4DD] bg-[#F8F7F3] p-4 space-y-2 text-xs">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <span className="font-semibold text-[#18181B]">
              {isLive
                ? 'Evidence Packet Submitted to PayPal Disputes API'
                : 'Local Simulated Submission Recorded (LOCAL DEMO — NOT SUBMITTED TO PAYPAL)'}
            </span>
            <span className="font-mono text-[11px] px-2 py-0.5 rounded bg-white border border-[#E6E4DD]">
              {submissionResult.submission_id}
            </span>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 text-[11px] text-[#52525B] font-mono">
            <div>State: {submissionResult.dispute_state || submissionResult.status || 'RECORDED'}</div>
            <div>Carrier: {submissionResult.carrier_name || carrierName}</div>
            <div>Tracking: {submissionResult.tracking_number || trackingNumber}</div>
          </div>
        </div>
      )}

      {/* Action Buttons */}
      {!submissionResult && (
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pt-1">
          <div className="text-[11px] text-[#71717A] flex items-center gap-1.5">
            <Info className="w-3.5 h-3.5 shrink-0" />
            <span>
              {isLive
                ? 'Live PayPal Sandbox dispute: submission calls PayPal Disputes API and performs follow-up GET.'
                : 'LOCAL DEMO scenario: records LOCAL_SIMULATED_SUBMISSION locally and never submits to live PayPal.'}
            </span>
          </div>

          <div className="flex flex-wrap items-center gap-2.5 shrink-0">
            <button
              type="button"
              onClick={onRequestApprove}
              disabled={!canApprove}
              className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg text-xs font-medium bg-[#18181B] text-white hover:bg-[#27272A] disabled:opacity-45 disabled:cursor-not-allowed transition-colors"
            >
              {approving ? (
                <>
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  <span>Approving...</span>
                </>
              ) : (
                <>
                  <ShieldCheck className="w-3.5 h-3.5 text-[#99F6E4]" />
                  <span>1. Approve Evidence Package</span>
                </>
              )}
            </button>

            <button
              type="button"
              onClick={() => onSubmitEvidence({ requireLivePayPal: isLive })}
              disabled={!approvalReceipt || submitting}
              className={`inline-flex items-center gap-1.5 px-4 py-2 rounded-lg text-xs font-medium transition-colors disabled:opacity-45 disabled:cursor-not-allowed ${
                isLive
                  ? 'bg-[#0F766E] text-white hover:bg-[#115E59]'
                  : 'bg-white text-[#18181B] border border-[#E6E4DD] hover:bg-[#F8F7F3]'
              }`}
            >
              {submitting ? (
                <>
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  <span>Submitting...</span>
                </>
              ) : isLive ? (
                <>
                  <Send className="w-3.5 h-3.5" />
                  <span>2. Submit Approved Evidence to PayPal</span>
                </>
              ) : (
                <>
                  <Lock className="w-3.5 h-3.5 text-[#0F766E]" />
                  <span>2. Record Local Simulated Submission</span>
                </>
              )}
            </button>
          </div>
        </div>
      )}
    </section>
  );
}

