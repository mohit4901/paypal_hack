import React from 'react';
import { ArrowRight } from 'lucide-react';
import StatusBadge from '../ui/StatusBadge';
import CopyButton from '../ui/CopyButton';

function formatReason(reason) {
  if (!reason) return 'Not specified';
  if (reason === 'MERCHANDISE_OR_SERVICE_NOT_RECEIVED') return 'Merchandise / Service Not Received';
  if (reason === 'UNAUTHORISED_TRANSACTION') return 'Unauthorised Transaction';
  if (reason === 'INCORRECT_AMOUNT') return 'Incorrect Amount';
  return String(reason).replace(/_/g, ' ');
}

function formatDeadline(iso) {
  if (!iso) return 'Not provided';
  const dt = new Date(iso);
  if (Number.isNaN(dt.getTime())) return String(iso);
  return dt.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
}

function formatEvidenceStatus(d) {
  const r = d.evidence_readiness;
  if (r === 'SUBMITTED_TO_PAYPAL') return { label: 'Submitted', variant: 'verified' };
  if (r === 'READY_FOR_SELLER_REVIEW') return { label: 'Ready for review', variant: 'info' };
  if (r === 'NEEDS_ATTENTION') return { label: 'Evidence incomplete', variant: 'warning' };
  return { label: r || 'Pending', variant: 'neutral' };
}

function formatWorkflowStatus(status) {
  switch (status) {
    case 'WAITING_FOR_SELLER_RESPONSE':
      return { label: 'Needs review', variant: 'warning' };
    case 'UNDER_PAYPAL_REVIEW':
      return { label: 'Submitted / Review', variant: 'info' };
    case 'RESOLVED_SELLER_FAVOR':
    case 'RESOLVED':
      return { label: 'Resolved', variant: 'verified' };
    case 'LOCAL_SCENARIO_READY_FOR_REVIEW':
      return { label: 'Ready (Demo)', variant: 'info' };
    case 'LOCAL_SCENARIO_NEEDS_EVIDENCE':
      return { label: 'Needs evidence', variant: 'warning' };
    default: {
      const cleaned = String(status || 'Open')
        .replace(/^LOCAL_SCENARIO_/, '')
        .replace(/_/g, ' ')
        .toLowerCase();
      return {
        label: cleaned.charAt(0).toUpperCase() + cleaned.slice(1),
        variant: 'neutral',
      };
    }
  }
}

export default function DisputeTable({ disputes = [], onSelectDispute }) {
  return (
    <div className="space-y-3">
      {/* Desktop Table */}
      <div className="hidden lg:block bg-white rounded-xl border border-[#E6E4DD] overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse table-auto">
            <thead>
              <tr className="border-b border-[#E6E4DD] bg-[#FCFBF8] text-[10px] font-semibold text-[#52525B] uppercase tracking-wider">
                <th className="py-2.5 px-3">Dispute ID</th>
                <th className="py-2.5 px-3">Order &amp; Reference</th>
                <th className="py-2.5 px-3">Dispute Reason</th>
                <th className="py-2.5 px-3">Amount &amp; Deadline</th>
                <th className="py-2.5 px-3">Evidence &amp; Status</th>
                <th className="py-2.5 px-3 text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#EFECE4] text-xs">
              {disputes.map((d) => {
                const isLive = Boolean(d.is_live_paypal_dispute);
                const evSt = formatEvidenceStatus(d);
                const wfSt = formatWorkflowStatus(d.status);
                const refText = d.buyer_email || d.capture_id || null;

                return (
                  <tr
                    key={d.dispute_id}
                    onClick={() => onSelectDispute && onSelectDispute(d.dispute_id)}
                    className="hover:bg-[#F8F7F3]/70 cursor-pointer transition-colors"
                  >
                    <td className="py-3 px-3 align-top">
                      <div className="font-mono font-semibold text-[#18181B] whitespace-nowrap">
                        {d.dispute_id}
                      </div>
                      <div className="mt-1">
                        {isLive ? (
                          <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium bg-emerald-50 text-emerald-800 border border-emerald-200 whitespace-nowrap">
                            PAYPAL SANDBOX LIVE
                          </span>
                        ) : (
                          <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium bg-stone-100 text-stone-700 border border-stone-200 whitespace-nowrap">
                            LOCAL DEMO — NOT A PAYPAL DISPUTE
                          </span>
                        )}
                      </div>
                    </td>
                    <td className="py-3 px-2.5 align-top font-mono text-[11px] text-[#3F3F46] max-w-[165px]">
                      <div className="flex items-center gap-1">
                        <span className="truncate" title={d.transaction_reference}>{d.transaction_reference || '—'}</span>
                        {d.transaction_reference && (
                          <CopyButton value={d.transaction_reference} />
                        )}
                      </div>
                      <div className="font-sans text-[11px] text-[#71717A] truncate mt-0.5" title={refText || 'Not provided'}>
                        {refText || 'Ref: Not provided'}
                      </div>
                    </td>
                    <td className="py-3 px-2.5 align-top text-[#18181B] max-w-[180px]">
                      <div className="font-medium leading-snug">{formatReason(d.dispute_reason)}</div>
                      {d.product_name && (
                        <div className="text-[11px] text-[#71717A] truncate mt-0.5" title={d.product_name}>
                          {d.product_name}
                        </div>
                      )}
                    </td>
                    <td className="py-3 px-3 align-top font-medium tabular-nums text-[#18181B] whitespace-nowrap">
                      <div>{d.amount ? `${d.amount} ${d.currency || 'USD'}` : '—'}</div>
                      <div className="text-[11px] font-normal text-[#71717A] mt-0.5">
                        Due {formatDeadline(d.seller_response_due_date || d.response_deadline)}
                      </div>
                    </td>
                    <td className="py-3 px-3 align-top">
                      <div className="flex flex-wrap items-center gap-1.5">
                        <StatusBadge size="xs" variant={evSt.variant} label={evSt.label} />
                        <StatusBadge size="xs" variant={wfSt.variant} label={wfSt.label} />
                      </div>
                    </td>
                    <td className="py-3 px-3 align-top text-right">
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          onSelectDispute && onSelectDispute(d.dispute_id);
                        }}
                        className="inline-flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-xs font-medium bg-white text-[#18181B] border border-[#E6E4DD] hover:border-[#0F766E] hover:text-[#0F766E] transition-colors whitespace-nowrap"
                      >
                        <span>Resolve</span>
                        <ArrowRight className="w-3.5 h-3.5" />
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* Mobile & Tablet Cards */}
      <div className="lg:hidden space-y-3">
        {disputes.map((d) => {
          const isLive = Boolean(d.is_live_paypal_dispute);
          const evSt = formatEvidenceStatus(d);
          const wfSt = formatWorkflowStatus(d.status);

          return (
            <div
              key={d.dispute_id}
              onClick={() => onSelectDispute && onSelectDispute(d.dispute_id)}
              className="bg-white rounded-xl border border-[#E6E4DD] p-4 space-y-3 cursor-pointer hover:border-[#0F766E]/50 transition-colors"
            >
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <div className="font-mono text-sm font-semibold text-[#18181B] truncate">
                    {d.dispute_id}
                  </div>
                  <div className="mt-1">
                    {isLive ? (
                      <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium bg-emerald-50 text-emerald-800 border border-emerald-200">
                        PAYPAL SANDBOX LIVE
                      </span>
                    ) : (
                      <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium bg-stone-100 text-stone-700 border border-stone-200">
                        LOCAL DEMO — NOT A PAYPAL DISPUTE
                      </span>
                    )}
                  </div>
                </div>
                <div className="text-right font-semibold text-sm tabular-nums text-[#18181B] shrink-0">
                  {d.amount ? `${d.amount} ${d.currency || 'USD'}` : '—'}
                </div>
              </div>

              <div className="text-xs text-[#3F3F46] space-y-1">
                <div className="font-medium">{formatReason(d.dispute_reason)}</div>
                <div className="text-[#71717A] font-mono text-[11px]">
                  Order: {d.transaction_reference || '—'} · Due:{' '}
                  {formatDeadline(d.seller_response_due_date || d.response_deadline)}
                </div>
              </div>

              <div className="flex flex-wrap items-center justify-between gap-2 pt-2 border-t border-[#EFECE4]">
                <div className="flex flex-wrap items-center gap-1.5">
                  <StatusBadge size="xs" variant={wfSt.variant} label={wfSt.label} />
                  <StatusBadge size="xs" variant={evSt.variant} label={evSt.label} />
                </div>
                <span className="inline-flex items-center gap-1 text-xs font-medium text-[#0F766E]">
                  <span>Resolve</span>
                  <ArrowRight className="w-3.5 h-3.5" />
                </span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

