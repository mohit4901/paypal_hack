import React from 'react';
import { Sparkles, Save, Loader2 } from 'lucide-react';

export default function AnalysisReviewSummary({
  form,
  uploadedFiles = [],
  onAnalyze,
  onSaveDraft,
  submitting = false,
  draftSavedAt = null,
}) {
  return (
    <section className="bg-white rounded-xl border border-[#E6E4DD] p-5 sm:p-6 space-y-5">
      <div className="pb-4 border-b border-[#EFECE4]">
        <span className="text-[11px] font-mono font-medium text-[#0F766E] uppercase tracking-wider">
          Section 5
        </span>
        <h2 className="text-base font-semibold text-[#18181B]">Review Before Analysis</h2>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 text-xs">
        <div className="p-3 rounded-lg bg-[#F8F7F3] border border-[#EFECE4]">
          <div className="text-[11px] text-[#71717A]">Environment</div>
          <div className="font-medium text-[#18181B] mt-0.5">
            {form.environment === 'LIVE_PAYPAL'
              ? `Live PayPal (${form.paypalDisputeId || 'Missing ID'})`
              : 'Local Demo Scenario'}
          </div>
        </div>

        <div className="p-3 rounded-lg bg-[#F8F7F3] border border-[#EFECE4]">
          <div className="text-[11px] text-[#71717A]">Order &amp; Amount</div>
          <div className="font-mono font-medium text-[#18181B] mt-0.5 truncate">
            {form.orderId || 'Not specified'} · {form.amount || '0.00'} {form.currency || 'USD'}
          </div>
        </div>

        <div className="p-3 rounded-lg bg-[#F8F7F3] border border-[#EFECE4]">
          <div className="text-[11px] text-[#71717A]">Shipping Attestation</div>
          <div className="font-mono font-medium text-[#18181B] mt-0.5 truncate">
            {form.carrierName || '—'} · {form.trackingNumber || 'No tracking'}
          </div>
        </div>

        <div className="p-3 rounded-lg bg-[#F8F7F3] border border-[#EFECE4]">
          <div className="text-[11px] text-[#71717A]">Attached Evidence Files</div>
          <div className="font-medium text-[#18181B] mt-0.5">
            {uploadedFiles.length} uploaded document{uploadedFiles.length === 1 ? '' : 's'}
          </div>
        </div>
      </div>

      <div className="p-3.5 rounded-lg bg-[#FCFBF8] border border-[#EFECE4] text-xs">
        <div className="text-[11px] text-[#71717A] mb-1">Merchant claim to evaluate</div>
        <div className="text-[#18181B] italic">
          {form.sellerClaim?.trim()
            ? `"${form.sellerClaim.trim()}"`
            : 'No factual claim entered yet.'}
        </div>
      </div>

      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pt-2">
        <div className="text-[11px] text-[#71717A]">
          {draftSavedAt
            ? `Draft saved locally at ${new Date(draftSavedAt).toLocaleTimeString()}`
            : 'All backend checks run deterministically first; AI alignment remains advisory.'}
        </div>

        <div className="flex flex-wrap items-center gap-2.5">
          <button
            type="button"
            onClick={onSaveDraft}
            disabled={submitting}
            className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg text-xs font-medium bg-white text-[#18181B] border border-[#E6E4DD] hover:bg-[#F8F7F3] disabled:opacity-50 transition-colors"
          >
            <Save className="w-3.5 h-3.5" />
            <span>Save Draft</span>
          </button>

          <button
            type="button"
            onClick={onAnalyze}
            disabled={submitting}
            className="inline-flex items-center gap-1.5 px-5 py-2 rounded-lg text-xs font-medium bg-[#18181B] text-white hover:bg-[#27272A] disabled:opacity-50 transition-colors"
          >
            {submitting ? (
              <>
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
                <span>Starting Analysis...</span>
              </>
            ) : (
              <>
                <Sparkles className="w-3.5 h-3.5 text-[#99F6E4]" />
                <span>Analyze Evidence</span>
              </>
            )}
          </button>
        </div>
      </div>
    </section>
  );
}

