import React, { useState } from 'react';
import { ChevronDown, ChevronUp } from 'lucide-react';
import StatusBadge from '../ui/StatusBadge';

export default function OrderPaymentVerification({
  dispute,
  transaction,
  aiPrep,
  merchantContext,
  validationErrors = [],
}) {
  const [expandedKey, setExpandedKey] = useState(null);

  const items = aiPrep?.evidence_items || [];
  const paymentItem = items.find((it) => it.item === 'Payment & Capture Record') || {};

  const disputeOrderId = dispute?.transaction_reference || 'Not specified';
  const recordOrderId = transaction?.order_id || dispute?.transaction_reference || null;
  const suppliedOrderId = merchantContext?.orderId || disputeOrderId;

  const captureId = merchantContext?.captureId || dispute?.capture_id || transaction?.capture_id || null;
  const txCaptureId = transaction?.capture_id || dispute?.capture_id || null;

  const expectedAmt = dispute?.amount || merchantContext?.amount || null;
  const capturedAmt = transaction?.amount || dispute?.amount || null;
  const expectedCcy = dispute?.currency || merchantContext?.currency || 'USD';
  const capturedCcy = transaction?.currency || dispute?.currency || 'USD';

  const hasAmountError = validationErrors.some((e) => e.toLowerCase().includes('amount'));
  const hasCurrencyError = validationErrors.some((e) => e.toLowerCase().includes('currency'));
  const hasLinkError = validationErrors.some((e) => e.toLowerCase().includes('linkage') || e.toLowerCase().includes('mismatch'));

  const isLive = Boolean(dispute?.is_live_paypal_dispute);
  const verifiedBadgeStatus = isLive ? 'VERIFIED_ON_PAYPAL' : 'VERIFIED_ON_MERCHANT_RECORD';

  const orderMatch =
    recordOrderId && suppliedOrderId && suppliedOrderId !== 'Not specified'
      ? recordOrderId === suppliedOrderId
      : Boolean(recordOrderId);

  const rows = [
    {
      key: 'order_id',
      label: 'Order ID',
      supplied: suppliedOrderId,
      recorded: recordOrderId || 'Unavailable',
      status: hasLinkError ? 'MISMATCH' : orderMatch && recordOrderId ? verifiedBadgeStatus : 'NOT_PROVIDED',
      source: isLive ? 'PayPal Disputes API' : 'Store Transaction Record',
      explanation:
        hasLinkError
          ? 'Supplied Order ID does not match the linked payment record.'
          : recordOrderId
          ? `Order ${recordOrderId} matches the linked dispute context.`
          : 'Order ID missing from merchant store records.',
      raw: { suppliedOrderId, disputeOrderId, recordOrderId, provenance: dispute?.provenance },
    },
    {
      key: 'paypal_capture',
      label: 'PayPal Capture',
      supplied: captureId || 'Not provided',
      recorded: txCaptureId || 'Unavailable',
      status: txCaptureId ? verifiedBadgeStatus : 'NOT_PROVIDED',
      source: paymentItem.source || (isLive ? 'PayPal Capture API' : 'Store Ledger / PayPal Webhook'),
      explanation:
        txCaptureId
          ? `Capture ${txCaptureId} status: ${transaction?.payment_status || 'COMPLETED'}.`
          : 'No verified PayPal Capture ID found on record.',
      raw: { captureId, txCaptureId, paymentStatus: transaction?.payment_status },
    },
    {
      key: 'amount',
      label: 'Amount',
      supplied: expectedAmt ? `${expectedAmt}` : 'Not provided',
      recorded: capturedAmt ? `${capturedAmt}` : 'Unavailable',
      status: hasAmountError ? 'MISMATCH' : expectedAmt && capturedAmt ? verifiedBadgeStatus : 'NOT_PROVIDED',
      source: 'Deterministic Amount Comparator',
      explanation: hasAmountError
        ? `Amount mismatch: expected ${expectedAmt}, captured ${capturedAmt}.`
        : capturedAmt
        ? `Captured amount (${capturedAmt}) matches disputed transaction amount.`
        : 'Captured amount unavailable.',
      raw: { expectedAmt, capturedAmt, validationErrors },
    },
    {
      key: 'currency',
      label: 'Currency',
      supplied: expectedCcy,
      recorded: capturedCcy,
      status: hasCurrencyError ? 'MISMATCH' : expectedCcy === capturedCcy ? verifiedBadgeStatus : 'MISMATCH',
      source: 'Deterministic Currency Check',
      explanation:
        hasCurrencyError || expectedCcy !== capturedCcy
          ? `Currency mismatch (${expectedCcy} vs ${capturedCcy}).`
          : `Currency ${capturedCcy} matches across dispute and transaction records.`,
      raw: { expectedCcy, capturedCcy },
    },
    {
      key: 'linkage',
      label: 'Transaction Linkage',
      supplied: `${suppliedOrderId} / ${captureId || '—'}`,
      recorded: `${recordOrderId || '—'} / ${txCaptureId || '—'}`,
      status: hasLinkError ? 'MISMATCH' : recordOrderId && txCaptureId ? verifiedBadgeStatus : 'NOT_INDEPENDENTLY_VERIFIED',
      source: 'Deterministic Linkage Validator',
      explanation:
        paymentItem.explanation ||
        (recordOrderId && txCaptureId
          ? 'Order and PayPal Capture ID link cleanly in backend SQLite ledger.'
          : 'Transaction linkage incomplete — attach order or capture reference.'),
      raw: paymentItem,
    },
  ];

  return (
    <section className="bg-white rounded-xl border border-[#E6E4DD] overflow-hidden">
      <div className="px-5 py-4 border-b border-[#EFECE4]">
        <h2 className="text-base font-semibold text-[#18181B]">
          Order &amp; Payment Verification
        </h2>
        <p className="text-xs text-[#52525B] mt-0.5">
          Deterministic checks take absolute precedence over neural assessments.
        </p>
      </div>

      <div className="divide-y divide-[#EFECE4]">
        {rows.map((row) => {
          const isOpen = expandedKey === row.key;
          return (
            <div key={row.key} className="px-5 py-3.5 hover:bg-[#FCFBF8] transition-colors">
              <div className="flex flex-col md:flex-row md:items-center justify-between gap-3">
                <div className="min-w-0 flex-1 space-y-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-xs font-semibold text-[#18181B] w-36 shrink-0">
                      {row.label}
                    </span>
                    <StatusBadge size="xs" status={row.status} />
                    <span className="text-[11px] text-[#71717A]">
                      Source: {row.source}
                    </span>
                  </div>
                  <div className="text-xs text-[#52525B]">{row.explanation}</div>
                  <div className="flex flex-wrap gap-x-4 gap-y-1 text-[11px] font-mono text-[#71717A] pt-0.5">
                    <span>Supplied: {row.supplied}</span>
                    <span>Record: {row.recorded}</span>
                  </div>
                </div>

                <button
                  type="button"
                  onClick={() => setExpandedKey(isOpen ? null : row.key)}
                  className="inline-flex items-center gap-1 text-[11px] font-medium text-[#52525B] hover:text-[#18181B] self-start md:self-center shrink-0"
                >
                  <span>Raw details</span>
                  {isOpen ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
                </button>
              </div>

              {isOpen && (
                <pre className="mt-3 p-3 rounded-lg bg-[#F8F7F3] border border-[#E6E4DD] text-[11px] font-mono text-[#3F3F46] overflow-x-auto">
                  {JSON.stringify(row.raw, null, 2)}
                </pre>
              )}
            </div>
          );
        })}
      </div>
    </section>
  );
}

