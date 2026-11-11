import { useState, useCallback } from 'react';
import { api } from '../services/api';

export function useApproval({ onToast } = {}) {
  const [editableDraft, setEditableDraft] = useState('');
  const [merchantChecked, setMerchantChecked] = useState(false);
  const [approving, setApproving] = useState(false);
  const [approvalReceipt, setApprovalReceipt] = useState(null);
  const [approvalInvalidatedMsg, setApprovalInvalidatedMsg] = useState(null);
  const [showConfirmModal, setShowConfirmModal] = useState(false);

  const [submitting, setSubmitting] = useState(false);
  const [submissionResult, setSubmissionResult] = useState(null);
  const [approvalError, setApprovalError] = useState(null);

  const invalidateApproval = useCallback(
    (reason) => {
      if (approvalReceipt || merchantChecked) {
        setApprovalReceipt(null);
        setMerchantChecked(false);
        setApprovalInvalidatedMsg(
          reason ||
            'Evidence, claim, or response draft changed after approval. Previous approval was invalidated — please review and re-approve.'
        );
      }
    },
    [approvalReceipt, merchantChecked]
  );

  const updateDraft = useCallback(
    (nextText) => {
      setEditableDraft(nextText);
      invalidateApproval('Draft response modified after approval — changes require re-approval.');
    },
    [invalidateApproval]
  );

  const resetApprovalState = useCallback(() => {
    setApprovalReceipt(null);
    setMerchantChecked(false);
    setApprovalInvalidatedMsg(null);
    setApprovalError(null);
    setShowConfirmModal(false);
  }, []);

  const executeApproval = useCallback(
    async ({ disputeId, carrierName, trackingNumber, deliveryNotes, proofDocumentUrl }) => {
      if (!merchantChecked) {
        setApprovalError('Confirm the merchant review attestation before approving.');
        return null;
      }
      if (!carrierName?.trim() || !trackingNumber?.trim()) {
        setApprovalError('Carrier name and tracking number are required before cryptographic approval.');
        return null;
      }

      setApproving(true);
      setApprovalError(null);
      setApprovalInvalidatedMsg(null);
      try {
        const receipt = await api.approveFulfillmentEvidence(disputeId, {
          carrier_name: carrierName.trim(),
          tracking_number: trackingNumber.trim(),
          evidence_notes: editableDraft || deliveryNotes || '',
          proof_document_url: proofDocumentUrl || null,
          signature_confirmed: true,
        });
        setApprovalReceipt(receipt);
        setShowConfirmModal(false);
        if (onToast) {
          onToast({
            type: 'success',
            title: 'Approval Sealed',
            message: `Receipt ${receipt.approval_id} bound to SHA-256 evidence digest.`,
          });
        }
        return receipt;
      } catch (err) {
        const msg = err.message || 'Server-side approval failed.';
        setApprovalError(msg);
        if (onToast) onToast({ type: 'error', title: 'Approval Failed', message: msg });
        return null;
      } finally {
        setApproving(false);
      }
    },
    [merchantChecked, editableDraft, onToast]
  );

  const executeSubmission = useCallback(
    async ({
      disputeId,
      isLivePayPal,
      carrierName,
      trackingNumber,
      deliveryNotes,
      proofDocumentUrl,
      onRefreshDispute,
    }) => {
      if (!approvalReceipt || !merchantChecked) {
        setApprovalError('Valid SHA-256 merchant approval receipt is mandatory before submission.');
        return null;
      }

      setSubmitting(true);
      setApprovalError(null);
      try {
        const res = await api.submitDisputeEvidence(disputeId, {
          carrier_name: carrierName.trim(),
          tracking_number: trackingNumber.trim(),
          evidence_notes: editableDraft || deliveryNotes || '',
          proof_document_url: proofDocumentUrl || null,
          merchant_approved: true,
          approval_id: approvalReceipt.approval_id,
          approved_digest: approvalReceipt.evidence_digest,
          require_live_paypal: Boolean(isLivePayPal),
        });
        setSubmissionResult(res);
        if (onToast) {
          onToast({
            type: 'success',
            title: isLivePayPal ? 'Submitted to PayPal' : 'Local Simulated Submission Recorded',
            message: `Submission ID: ${res.submission_id}`,
          });
        }
        if (onRefreshDispute) await onRefreshDispute();
        return res;
      } catch (err) {
        const msg = err.message || 'Evidence submission failed.';
        setApprovalError(msg);
        if (onToast) onToast({ type: 'error', title: 'Submission Blocked', message: msg });
        return null;
      } finally {
        setSubmitting(false);
      }
    },
    [approvalReceipt, merchantChecked, editableDraft, onToast]
  );

  return {
    editableDraft,
    setEditableDraft,
    updateDraft,
    merchantChecked,
    setMerchantChecked,
    approving,
    approvalReceipt,
    approvalInvalidatedMsg,
    setApprovalInvalidatedMsg,
    showConfirmModal,
    setShowConfirmModal,
    submitting,
    submissionResult,
    setSubmissionResult,
    approvalError,
    setApprovalError,
    invalidateApproval,
    resetApprovalState,
    executeApproval,
    executeSubmission,
  };
}

