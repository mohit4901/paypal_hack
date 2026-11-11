import React, { useEffect } from 'react';
import { ShieldCheck, X, Lock, Loader2 } from 'lucide-react';

export default function ApprovalConfirmationModal({
  isOpen,
  onClose,
  onConfirm,
  approving = false,
  disputeId,
  isLivePayPal = false,
  carrierName,
  trackingNumber,
  proofDocumentUrl,
  draftExcerpt,
}) {
  useEffect(() => {
    if (!isOpen) return;
    const onKey = (e) => {
      if (e.key === 'Escape' && !approving) onClose();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [isOpen, approving, onClose]);

  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 z-50 bg-black/45 flex items-center justify-center p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="approvalModalTitle"
    >
      <div className="bg-white rounded-2xl border border-[#E6E4DD] max-w-lg w-full p-6 shadow-xl space-y-4">
        <div className="flex items-start justify-between gap-3 border-b border-[#EFECE4] pb-3">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-emerald-50 border border-emerald-200 flex items-center justify-center">
              <ShieldCheck className="w-4 h-4 text-emerald-700" />
            </div>
            <div>
              <h3 id="approvalModalTitle" className="text-sm font-semibold text-[#18181B]">
                Confirm Cryptographic Evidence Approval
              </h3>
              <p className="text-[11px] text-[#71717A]">
                Binds a server-side SHA-256 digest to your exact merchant response
              </p>
            </div>
          </div>

          <button
            type="button"
            onClick={onClose}
            disabled={approving}
            aria-label="Close modal"
            className="p-1 rounded-lg text-[#71717A] hover:text-[#18181B] hover:bg-[#F8F7F3]"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="space-y-2.5 text-xs bg-[#FCFBF8] border border-[#E6E4DD] rounded-xl p-4">
          <div className="flex justify-between gap-2">
            <span className="text-[#71717A]">Dispute ID</span>
            <span className="font-mono font-semibold text-[#18181B]">{disputeId}</span>
          </div>
          <div className="flex justify-between gap-2">
            <span className="text-[#71717A]">Scope</span>
            <span className="font-medium text-[#18181B]">
              {isLivePayPal ? 'Live PayPal Sandbox Dispute' : 'LOCAL DEMO — NOT A PAYPAL DISPUTE'}
            </span>
          </div>
          <div className="flex justify-between gap-2">
            <span className="text-[#71717A]">Carrier &amp; Tracking</span>
            <span className="font-mono text-[#18181B]">
              {carrierName} · {trackingNumber}
            </span>
          </div>
          {proofDocumentUrl && (
            <div className="space-y-1">
              <div className="flex justify-between gap-2">
                <span className="text-[#71717A]">Attachment</span>
                <span className="font-mono text-[#18181B] truncate max-w-[260px]">
                  {proofDocumentUrl}
                </span>
              </div>
              <div className="text-[10px] text-[#71717A] text-right">
                Integrity hashed (SHA-256); file contents are not automatically parsed or verified.
              </div>
            </div>
          )}
          <div className="pt-2 border-t border-[#EFECE4]">
            <div className="text-[11px] text-[#71717A] mb-1">Response excerpt bound to digest:</div>
            <div className="text-[11px] text-[#3F3F46] line-clamp-3 whitespace-pre-line">
              {draftExcerpt}
            </div>
          </div>
        </div>

        <div className="text-[11px] text-[#52525B] flex items-start gap-2">
          <Lock className="w-3.5 h-3.5 text-[#0F766E] shrink-0 mt-0.5" />
          <span>
            Any edit to carrier, tracking, claims, uploaded files, or response text after sealing will immediately invalidate this SHA-256 approval receipt.
          </span>
        </div>

        <div className="flex items-center justify-end gap-2.5 pt-2">
          <button
            type="button"
            onClick={onClose}
            disabled={approving}
            className="px-3.5 py-2 rounded-lg text-xs font-medium bg-white text-[#18181B] border border-[#E6E4DD] hover:bg-[#F8F7F3] transition-colors"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={onConfirm}
            disabled={approving}
            className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg text-xs font-medium bg-[#0F766E] text-white hover:bg-[#115E59] disabled:opacity-50 transition-colors"
          >
            {approving ? (
              <>
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
                <span>Sealing SHA-256 Receipt...</span>
              </>
            ) : (
              <>
                <ShieldCheck className="w-3.5 h-3.5" />
                <span>Confirm &amp; Seal Approval</span>
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}

