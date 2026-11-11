import React from 'react';
import { Upload, AlertTriangle } from 'lucide-react';
import StatusBadge from '../ui/StatusBadge';

export default function MissingEvidencePanel({
  aiPrep = null,
  onUploadClick,
}) {
  const missingList = aiPrep?.missing_evidence || [];
  const items = aiPrep?.evidence_items || [];
  const scanItem = items.find((i) => i.item === 'Carrier Delivery Scan');

  const cards = [];

  for (const gap of missingList) {
    const lower = gap.toLowerCase();
    const isMandatory = lower.includes('carrier') || lower.includes('tracking');
    cards.push({
      title: gap,
      mandatory: isMandatory,
      why: isMandatory
        ? 'Required by PayPal MERCHANDISE_OR_SERVICE_NOT_RECEIVED evidence policy before merchant defense submission.'
        : 'Substantiates physical dispatch or delivery in the seller response packet.',
      claimRel: 'Fulfillment & delivery claim',
      suggestion: lower.includes('tracking')
        ? 'Enter a valid carrier tracking number or upload the shipping label.'
        : lower.includes('carrier')
        ? 'Specify the shipping carrier name (e.g., USPS, UPS, FedEx, DHL).'
        : 'Upload the carrier proof-of-delivery receipt, shipping manifest, or signed invoice.',
    });
  }

  if (scanItem && scanItem.status === 'LOOKUP_NOT_CONFIGURED') {
    cards.push({
      title: 'Independent proof of delivery',
      mandatory: false,
      why: 'Supplied tracking format may be valid, but automated courier delivery scan lookup is not configured.',
      claimRel: 'Physical delivery confirmation',
      suggestion: 'Upload the carrier’s delivery confirmation receipt or official tracking export (PDF/PNG/JPG).',
    });
  }

  return (
    <section className="bg-white rounded-xl border border-[#E6E4DD] p-5 sm:p-6 space-y-4">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-4 border-b border-[#EFECE4]">
        <div>
          <h2 className="text-base font-semibold text-[#18181B]">Evidence Still Needed</h2>
          <p className="text-xs text-[#52525B] mt-0.5">
            Attach remaining supporting proof to strengthen verification before merchant approval.
          </p>
        </div>

        {onUploadClick && (
          <button
            type="button"
            onClick={onUploadClick}
            className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-lg text-xs font-medium bg-[#0F766E] text-white hover:bg-[#115E59] transition-colors self-start sm:self-center"
          >
            <Upload className="w-3.5 h-3.5" />
            <span>Upload Supporting Evidence</span>
          </button>
        )}
      </div>

      {cards.length === 0 ? (
        <div className="text-xs text-[#52525B] py-2">
          All required backend evidence fields are present.
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {cards.map((c, idx) => (
            <div
              key={idx}
              className="rounded-xl border border-amber-200 bg-amber-50/40 p-4 space-y-2"
            >
              <div className="flex items-start justify-between gap-2">
                <div className="flex items-center gap-2 text-xs font-semibold text-[#18181B]">
                  <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0" />
                  <span>{c.title}</span>
                </div>
                <StatusBadge
                  size="xs"
                  variant={c.mandatory ? 'error' : 'warning'}
                  label={c.mandatory ? 'Mandatory' : 'Recommended'}
                  showIcon={false}
                />
              </div>
              <div className="text-xs text-[#3F3F46] space-y-1 leading-relaxed">
                <div>
                  <strong className="font-medium">Why it matters:</strong> {c.why}
                </div>
                <div>
                  <strong className="font-medium">Related claim:</strong> {c.claimRel}
                </div>
                <div>
                  <strong className="font-medium">Suggested action:</strong> {c.suggestion}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

