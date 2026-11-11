import React from 'react';
import { CheckSquare } from 'lucide-react';

export default function RecommendedActions({
  aiPrep = null,
  claimVerification = null,
  validationErrors = [],
  approvalReceipt = null,
}) {
  const actions = [];
  const items = aiPrep?.evidence_items || [];
  const scanItem = items.find((i) => i.item === 'Carrier Delivery Scan');
  const docItem = items.find((i) => i.item === 'Supporting Delivery Document');
  const paymentItem = items.find((i) => i.item === 'Payment & Capture Record');

  if (scanItem?.status === 'LOOKUP_NOT_CONFIGURED' || docItem?.status === 'NOT_PROVIDED') {
    actions.push('Attach official carrier scan or signed proof-of-delivery document (PDF/JPG/PNG).');
  }
  if (validationErrors.length > 0 || paymentItem?.status === 'NOT_PROVIDED') {
    actions.push('Verify order ID, capture ID, amount, and currency linkage in store records.');
  }
  if ((claimVerification?.verified_claims || []).some((c) => c.verdict === 'CONTRADICTED')) {
    actions.push('Review the AI-identified contradiction carefully against source records before approving.');
  }
  if ((aiPrep?.missing_evidence || []).length > 0) {
    actions.push(`Supply missing required fields: ${(aiPrep.missing_evidence || []).join(', ')}.`);
  }
  if (!approvalReceipt) {
    actions.push('Review, edit if needed, and cryptographically approve the merchant response package.');
  }

  if (actions.length === 0) return null;

  return (
    <section className="bg-white rounded-xl border border-[#E6E4DD] p-5 sm:p-6 space-y-3">
      <div className="flex items-center gap-2 pb-3 border-b border-[#EFECE4]">
        <CheckSquare className="w-4 h-4 text-[#0F766E]" />
        <h2 className="text-base font-semibold text-[#18181B]">Recommended Next Actions</h2>
      </div>

      <ol className="space-y-2">
        {actions.map((act, idx) => (
          <li key={idx} className="flex items-start gap-3 text-xs text-[#3F3F46]">
            <span className="w-5 h-5 rounded-full bg-[#F8F7F3] border border-[#E6E4DD] font-mono text-[11px] font-medium text-[#18181B] flex items-center justify-center shrink-0">
              {idx + 1}
            </span>
            <span className="pt-0.5 leading-relaxed">{act}</span>
          </li>
        ))}
      </ol>
    </section>
  );
}

