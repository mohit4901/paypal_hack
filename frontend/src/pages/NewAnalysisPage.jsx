import React, { useState, useEffect } from 'react';
import { ArrowLeft, AlertCircle } from 'lucide-react';
import PageHeader from '../components/layout/PageHeader';
import DisputeInformationForm from '../components/analysis/DisputeInformationForm';
import OrderPaymentForm from '../components/analysis/OrderPaymentForm';
import ShippingInformationForm from '../components/analysis/ShippingInformationForm';
import EvidenceUploader from '../components/analysis/EvidenceUploader';
import AnalysisReviewSummary from '../components/analysis/AnalysisReviewSummary';
import { useEvidenceUpload } from '../hooks/useEvidenceUpload';
import { api } from '../services/api';

const DRAFT_STORAGE_KEY = 'proofledger_new_analysis_draft_v1';

const DEFAULT_FORM = {
  environment: 'LOCAL_DEMO',
  prefillDisputeId: '',
  paypalDisputeId: '',
  disputeCategory: 'MERCHANDISE_OR_SERVICE_NOT_RECEIVED',
  sellerUnderstanding: '',
  sellerClaim: 'The order was dispatched and delivered to the buyer’s registered address.',
  orderId: '',
  captureId: '',
  amount: '',
  currency: 'USD',
  backendPaymentStatus: '',
  orderDate: '',
  productDescription: '',
  parcelCount: '',
  buyerEmail: '',
  carrierName: 'USPS',
  trackingNumber: '',
  shippingAddress: '',
  deliveryAddress: '',
  shipmentDate: '',
  estimatedDeliveryDate: '',
  deliveryDate: '',
  fulfillmentNotes: '',
};

export default function NewAnalysisPage({
  disputes = [],
  onBackToInbox,
  onStartResolve,
  onToast,
  onRefreshData,
}) {
  const [form, setForm] = useState(() => {
    try {
      const saved = window.localStorage.getItem(DRAFT_STORAGE_KEY);
      if (saved) {
        return { ...DEFAULT_FORM, ...JSON.parse(saved) };
      }
    } catch (_) {}
    return DEFAULT_FORM;
  });
  const [errors, setErrors] = useState({});
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState(null);
  const [draftSavedAt, setDraftSavedAt] = useState(null);

  const upload = useEvidenceUpload({ onToast });

  const targetDisputeId =
    form.environment === 'LIVE_PAYPAL' && form.paypalDisputeId.trim()
      ? form.paypalDisputeId.trim()
      : form.prefillDisputeId ||
        (form.orderId.trim() ? `DSP-${form.orderId.trim().slice(0, 12)}` : 'DSP-LOCAL-NEW');

  const updateField = (key, val) => {
    setForm((prev) => ({ ...prev, [key]: val }));
    setErrors((prev) => {
      if (!prev[key]) return prev;
      const copy = { ...prev };
      delete copy[key];
      return copy;
    });
  };

  const handleSelectPrefill = async (disputeId) => {
    if (!disputeId) {
      setForm((prev) => ({ ...DEFAULT_FORM, environment: prev.environment }));
      return;
    }
    try {
      const d = await api.getDispute(disputeId);
      let tx = null;
      if (d.transaction_reference) {
        tx = await api.getTransaction(d.transaction_reference).catch(() => null);
      }
      setForm((prev) => ({
        ...prev,
        prefillDisputeId: d.dispute_id,
        environment: d.is_live_paypal_dispute ? 'LIVE_PAYPAL' : 'LOCAL_DEMO',
        paypalDisputeId: d.is_live_paypal_dispute ? d.dispute_id : '',
        sellerUnderstanding: d.customer_claim || prev.sellerUnderstanding,
        sellerClaim:
          d.default_claims?.[0]?.claim_text ||
          `Order ${d.transaction_reference || d.dispute_id} payment was captured and fulfillment records were supplied.`,
        orderId: d.transaction_reference || tx?.order_id || '',
        captureId: d.capture_id || tx?.capture_id || '',
        amount: d.amount || tx?.amount || '',
        currency: d.currency || tx?.currency || 'USD',
        backendPaymentStatus: tx?.payment_status || '',
        orderDate: tx?.created_at ? tx.created_at.slice(0, 10) : '',
        productDescription: d.product_name || tx?.product_name || '',
        buyerEmail: d.buyer_email || tx?.buyer_email || '',
      }));
      if (onToast) {
        onToast({
          type: 'info',
          title: 'Record loaded',
          message: `Populated order and dispute fields from ${disputeId}.`,
        });
      }
    } catch (err) {
      if (onToast) onToast({ type: 'error', title: 'Could not load dispute', message: err.message });
    }
  };

  useEffect(() => {
    setSubmitError(null);
  }, [form.environment, form.orderId]);

  const validate = () => {
    const nextErr = {};
    if (form.environment === 'LIVE_PAYPAL') {
      const pid = form.paypalDisputeId.trim();
      if (!pid) {
        nextErr.paypalDisputeId = 'PayPal Dispute ID is required for an existing live PayPal dispute.';
      } else if (/^(DSP-|PP-D-EXAMPLE|LOCAL)/i.test(pid)) {
        nextErr.paypalDisputeId = 'Local demo IDs (e.g., DSP-* or PP-D-EXAMPLE) cannot be treated as live PayPal disputes.';
      }
    }
    if (!form.sellerClaim.trim()) {
      nextErr.sellerClaim = 'Enter the factual merchant claim to evaluate against evidence.';
    }
    if (!form.orderId.trim()) {
      nextErr.orderId = 'Order ID is required to link payment and fulfillment records.';
    }
    if (!form.amount.trim() || Number.isNaN(Number(form.amount)) || Number(form.amount) <= 0) {
      nextErr.amount = 'Enter a valid numeric order amount (e.g., 49.00).';
    }
    if (form.trackingNumber.trim() && !/^[A-Za-z0-9\-_]{6,35}$/.test(form.trackingNumber.trim())) {
      nextErr.trackingNumber = 'Tracking number must be 6–35 alphanumeric/hyphen characters.';
    }
    setErrors(nextErr);
    return Object.keys(nextErr).length === 0;
  };

  const handleSaveDraft = () => {
    try {
      window.localStorage.setItem(DRAFT_STORAGE_KEY, JSON.stringify(form));
      const now = Date.now();
      setDraftSavedAt(now);
      if (onToast) onToast({ type: 'success', title: 'Draft saved', message: 'Form inputs saved to local workspace storage.' });
    } catch (_) {}
  };

  const handleAnalyze = async () => {
    setSubmitError(null);
    if (!validate()) {
      setSubmitError('Please correct the highlighted required fields before starting analysis.');
      return;
    }
    if (upload.isUploading) {
      setSubmitError('Wait for active file upload(s) to finish before running analysis.');
      return;
    }

    setSubmitting(true);
    try {
      const orderId = form.orderId.trim();
      let disputeIdToOpen =
        form.environment === 'LIVE_PAYPAL'
          ? form.paypalDisputeId.trim()
          : form.prefillDisputeId || `DSP-${orderId.slice(0, 12)}`;

      // If starting a fresh non-live order analysis, persist order + shipment attestation evidence in backend SQLite
      if (form.environment !== 'LIVE_PAYPAL' && !form.prefillDisputeId) {
        try {
          await api.createTransaction({
            order_id: orderId,
            capture_id: form.captureId.trim() || undefined,
            amount: String(form.amount).trim(),
            currency: form.currency || 'USD',
            product_name: form.productDescription.trim() || 'Merchant Fulfillment Order',
            product_type: 'Merchandise / Digital Fulfillment',
            buyer_email: form.buyerEmail.trim() || 'buyer@example.com',
            status: form.backendPaymentStatus || 'COMPLETED',
          });
        } catch (err) {
          // 409 means order already exists; safe to attach custom evidence & analyze
          if (!err.isConflict) {
            throw err;
          }
        }

        // Persist merchant shipping & delivery attestation as explicit store evidence record
        const evContentParts = [
          `Order ${orderId}`,
          form.captureId.trim() ? `Capture ${form.captureId.trim()}` : null,
          `Amount ${form.amount.trim()} ${form.currency}`,
          form.carrierName ? `Carrier ${form.carrierName}` : null,
          form.trackingNumber.trim() ? `Tracking ${form.trackingNumber.trim()}` : null,
          form.shipmentDate ? `Shipped ${form.shipmentDate}` : null,
          form.deliveryDate ? `Merchant stated delivery date ${form.deliveryDate}` : null,
          form.deliveryAddress.trim() ? `Destination ${form.deliveryAddress.trim()}` : null,
          form.fulfillmentNotes.trim() ? `Notes: ${form.fulfillmentNotes.trim()}` : null,
          upload.primaryUploaded?.response?.filename
            ? `Attached file: ${upload.primaryUploaded.response.filename}`
            : null,
        ].filter(Boolean);

        await api.addCustomEvidence(orderId, {
          source_type: 'merchant_attestation',
          source_name: 'Merchant Dispute Intake Form',
          event_type: 'SHIPMENT_ATTESTATION',
          content: evContentParts.join(' · '),
        }).catch(() => null);

        if (onRefreshData) {
          await onRefreshData();
        }
      }

      try {
        window.localStorage.setItem(DRAFT_STORAGE_KEY, JSON.stringify(form));
      } catch (_) {}

      onStartResolve(disputeIdToOpen, {
        initialCarrier: form.carrierName || 'USPS',
        initialTracking: form.trackingNumber.trim(),
        initialNotes:
          form.fulfillmentNotes.trim() ||
          [
            form.sellerUnderstanding.trim(),
            form.deliveryAddress.trim() ? `Destination: ${form.deliveryAddress.trim()}` : '',
          ]
            .filter(Boolean)
            .join(' · '),
        initialDocName: upload.primaryUploaded?.response?.filename || '',
        initialUploadedFiles: upload.uploadedFiles,
        customClaim: form.sellerClaim.trim(),
        merchantContext: {
          orderId,
          captureId: form.captureId.trim(),
          amount: form.amount.trim(),
          currency: form.currency,
          orderDate: form.orderDate,
          productDescription: form.productDescription.trim(),
          parcelCount: form.parcelCount,
          shippingAddress: form.shippingAddress.trim(),
          deliveryAddress: form.deliveryAddress.trim(),
          shipmentDate: form.shipmentDate,
          estimatedDeliveryDate: form.estimatedDeliveryDate,
          deliveryDate: form.deliveryDate,
          sellerUnderstanding: form.sellerUnderstanding.trim(),
          buyerEmail: form.buyerEmail.trim(),
        },
        autoRun: true,
      });
    } catch (err) {
      setSubmitError(err.message || 'Unable to start verification analysis.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="space-y-6 max-w-4xl">
      <PageHeader
        title="Analyze a Dispute"
        subtitle="Provide your transaction details and evidence. ProofLedger will verify what the records actually establish."
        actions={
          onBackToInbox && (
            <button
              type="button"
              onClick={onBackToInbox}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-white text-[#18181B] border border-[#E6E4DD] hover:bg-[#F8F7F3] transition-colors"
            >
              <ArrowLeft className="w-3.5 h-3.5" />
              <span>Back to Inbox</span>
            </button>
          )
        }
      />

      {submitError && (
        <div className="rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-xs text-rose-900 flex items-start gap-2.5">
          <AlertCircle className="w-4 h-4 text-rose-600 shrink-0 mt-0.5" />
          <span>{submitError}</span>
        </div>
      )}

      <DisputeInformationForm
        form={form}
        onChange={updateField}
        errors={errors}
        existingDisputes={disputes}
        onSelectPrefill={handleSelectPrefill}
      />

      <OrderPaymentForm form={form} onChange={updateField} errors={errors} />

      <ShippingInformationForm form={form} onChange={updateField} errors={errors} />

      <EvidenceUploader
        disputeId={targetDisputeId}
        files={upload.files}
        selectedCategory={upload.selectedCategory}
        onChangeCategory={upload.setSelectedCategory}
        validationError={upload.validationError}
        onFilesSelected={upload.addAndUploadFiles}
        onRetry={upload.retryUpload}
        onRemove={upload.removeFile}
        disabled={submitting}
      />

      <AnalysisReviewSummary
        form={form}
        uploadedFiles={upload.uploadedFiles}
        onAnalyze={handleAnalyze}
        onSaveDraft={handleSaveDraft}
        submitting={submitting}
        draftSavedAt={draftSavedAt}
      />
    </div>
  );
}
