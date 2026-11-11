import React from 'react';
import { Info, ShieldAlert } from 'lucide-react';

export default function DisputeInformationForm({
  form,
  onChange,
  errors = {},
  existingDisputes = [],
  onSelectPrefill,
}) {
  const isLive = form.environment === 'LIVE_PAYPAL';

  return (
    <section className="bg-white rounded-xl border border-[#E6E4DD] p-5 sm:p-6 space-y-5">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-4 border-b border-[#EFECE4]">
        <div>
          <span className="text-[11px] font-mono font-medium text-[#0F766E] uppercase tracking-wider">
            Section 1
          </span>
          <h2 className="text-base font-semibold text-[#18181B]">Dispute Information</h2>
        </div>

        {existingDisputes.length > 0 && onSelectPrefill && (
          <div className="flex items-center gap-2">
            <label htmlFor="prefillSelect" className="text-xs text-[#71717A] whitespace-nowrap">
              Load existing record:
            </label>
            <select
              id="prefillSelect"
              value={form.prefillDisputeId || ''}
              onChange={(e) => onSelectPrefill(e.target.value)}
              className="px-2.5 py-1.5 rounded-lg text-xs bg-[#F8F7F3] border border-[#E6E4DD] text-[#18181B] focus:outline-none focus:ring-2 focus:ring-[#0F766E]/20"
            >
              <option value="">Start blank case...</option>
              {existingDisputes.map((d) => (
                <option key={d.dispute_id} value={d.dispute_id}>
                  {d.dispute_id} ({d.is_live_paypal_dispute ? 'Live PayPal' : 'Local Demo'})
                </option>
              ))}
            </select>
          </div>
        )}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Environment */}
        <div>
          <label className="block text-xs font-medium text-[#3F3F46] mb-1.5">
            Environment <span className="text-rose-600">*</span>
          </label>
          <div className="grid grid-cols-2 gap-2">
            <button
              type="button"
              onClick={() => onChange('environment', 'LOCAL_DEMO')}
              className={`px-3 py-2.5 rounded-lg text-xs font-medium border text-left transition-colors ${
                !isLive
                  ? 'bg-[#18181B] text-white border-[#18181B]'
                  : 'bg-[#F8F7F3] text-[#3F3F46] border-[#E6E4DD] hover:bg-white'
              }`}
            >
              <div>Local demo scenario</div>
              <div className={`text-[10px] mt-0.5 ${!isLive ? 'text-zinc-300' : 'text-[#71717A]'}`}>
                Safe non-PayPal testing
              </div>
            </button>
            <button
              type="button"
              onClick={() => onChange('environment', 'LIVE_PAYPAL')}
              className={`px-3 py-2.5 rounded-lg text-xs font-medium border text-left transition-colors ${
                isLive
                  ? 'bg-[#0F766E] text-white border-[#0F766E]'
                  : 'bg-[#F8F7F3] text-[#3F3F46] border-[#E6E4DD] hover:bg-white'
              }`}
            >
              <div>Existing live PayPal dispute</div>
              <div className={`text-[10px] mt-0.5 ${isLive ? 'text-teal-100' : 'text-[#71717A]'}`}>
                Requires real PayPal ID
              </div>
            </button>
          </div>
        </div>

        {/* Dispute Category */}
        <div>
          <label htmlFor="disputeCategorySelect" className="block text-xs font-medium text-[#3F3F46] mb-1.5">
            Dispute category
          </label>
          <select
            id="disputeCategorySelect"
            value="MERCHANDISE_OR_SERVICE_NOT_RECEIVED"
            disabled
            className="w-full px-3 py-2.5 rounded-lg text-xs bg-[#F8F7F3] border border-[#E6E4DD] text-[#3F3F46] cursor-not-allowed"
          >
            <option value="MERCHANDISE_OR_SERVICE_NOT_RECEIVED">
              Merchandise or Service Not Received (MERCHANDISE_OR_SERVICE_NOT_RECEIVED)
            </option>
          </select>
          <p className="mt-1 text-[11px] text-[#71717A]">
            ProofLedger is scoped exclusively to Item / Service Not Received disputes.
          </p>
        </div>

        {/* Live PayPal Dispute ID (required only when LIVE_PAYPAL) */}
        {isLive && (
          <div className="md:col-span-2">
            <label htmlFor="paypalDisputeIdInput" className="block text-xs font-medium text-[#3F3F46] mb-1.5">
              PayPal Dispute ID <span className="text-rose-600">*</span>
            </label>
            <input
              id="paypalDisputeIdInput"
              type="text"
              value={form.paypalDisputeId || ''}
              onChange={(e) => onChange('paypalDisputeId', e.target.value)}
              placeholder="e.g., PP-D-12345678"
              className={`w-full px-3 py-2 rounded-lg text-xs font-mono bg-white border ${
                errors.paypalDisputeId ? 'border-rose-400 ring-2 ring-rose-100' : 'border-[#E6E4DD]'
              } text-[#18181B] focus:outline-none focus:ring-2 focus:ring-[#0F766E]/20 focus:border-[#0F766E]`}
            />
            {errors.paypalDisputeId ? (
              <p className="mt-1 text-xs text-rose-700 flex items-center gap-1">
                <ShieldAlert className="w-3.5 h-3.5" />
                {errors.paypalDisputeId}
              </p>
            ) : (
              <p className="mt-1 text-[11px] text-[#71717A]">
                Must match a genuine live PayPal dispute identifier. Local demo IDs (e.g., DSP-*) cannot be submitted as live PayPal disputes.
              </p>
            )}
          </div>
        )}

        {/* Seller's Understanding */}
        <div className="md:col-span-2">
          <label htmlFor="sellerUnderstandingInput" className="block text-xs font-medium text-[#3F3F46] mb-1.5">
            Seller&apos;s understanding of the dispute
          </label>
          <textarea
            id="sellerUnderstandingInput"
            rows={2}
            value={form.sellerUnderstanding || ''}
            onChange={(e) => onChange('sellerUnderstanding', e.target.value)}
            placeholder="Describe what the buyer claims and what you believe actually happened."
            className="w-full px-3 py-2 rounded-lg text-xs bg-white border border-[#E6E4DD] text-[#18181B] placeholder:text-[#A1A1AA] focus:outline-none focus:ring-2 focus:ring-[#0F766E]/20 focus:border-[#0F766E]"
          />
        </div>

        {/* Seller Factual Claim */}
        <div className="md:col-span-2">
          <label htmlFor="sellerClaimInput" className="block text-xs font-medium text-[#3F3F46] mb-1.5">
            Seller response / factual claim to verify <span className="text-rose-600">*</span>
          </label>
          <textarea
            id="sellerClaimInput"
            rows={2}
            value={form.sellerClaim || ''}
            onChange={(e) => onChange('sellerClaim', e.target.value)}
            placeholder="e.g., The order was dispatched and delivered to the buyer's address."
            className={`w-full px-3 py-2 rounded-lg text-xs bg-white border ${
              errors.sellerClaim ? 'border-rose-400 ring-2 ring-rose-100' : 'border-[#E6E4DD]'
            } text-[#18181B] placeholder:text-[#A1A1AA] focus:outline-none focus:ring-2 focus:ring-[#0F766E]/20 focus:border-[#0F766E]`}
          />
          {errors.sellerClaim && (
            <p className="mt-1 text-xs text-rose-700">{errors.sellerClaim}</p>
          )}
          <div className="mt-1.5 flex items-start gap-1.5 text-[11px] text-[#52525B] bg-[#F8F7F3] border border-[#EFECE4] rounded-lg px-3 py-2">
            <Info className="w-3.5 h-3.5 text-[#0F766E] shrink-0 mt-0.5" />
            <span>
              The AI model evaluates submitted records strictly against this factual statement. It does not assume your claim is true.
            </span>
          </div>
        </div>
      </div>
    </section>
  );
}

