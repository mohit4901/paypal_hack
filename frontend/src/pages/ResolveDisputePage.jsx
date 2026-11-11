import React, { useState, useEffect, useRef } from 'react';
import { ArrowLeft, RefreshCw, Sparkles, ChevronDown, ChevronUp } from 'lucide-react';
import PageHeader from '../components/layout/PageHeader';
import LoadingState from '../components/ui/LoadingState';
import ErrorState from '../components/ui/ErrorState';
import StatusBadge from '../components/ui/StatusBadge';
import LiveAnalysisTimeline from '../components/analysis/LiveAnalysisTimeline';
import EvidenceUploader from '../components/analysis/EvidenceUploader';
import VerificationSummary from '../components/verification/VerificationSummary';
import OrderPaymentVerification from '../components/verification/OrderPaymentVerification';
import DeliveryJourney from '../components/verification/DeliveryJourney';
import EvidenceClaimAlignment from '../components/verification/EvidenceClaimAlignment';
import ContradictionList from '../components/verification/ContradictionList';
import MissingEvidencePanel from '../components/verification/MissingEvidencePanel';
import RecommendedActions from '../components/verification/RecommendedActions';
import ResponseEditor from '../components/approval/ResponseEditor';
import EvidenceApprovalPanel from '../components/approval/EvidenceApprovalPanel';
import ApprovalConfirmationModal from '../components/approval/ApprovalConfirmationModal';
import { useDisputeAnalysis } from '../hooks/useDisputeAnalysis';
import { useEvidenceUpload } from '../hooks/useEvidenceUpload';
import { useApproval } from '../hooks/useApproval';
import { api } from '../services/api';

export default function ResolveDisputePage({
  disputeId = 'DSP-3EU95140-01',
  launchContext = null,
  systemStatus = null,
  onBackToInbox,
  onToast,
  onRefreshParent,
}) {
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(null);
  const [dispute, setDispute] = useState(null);
  const [transaction, setTransaction] = useState(null);
  const [txEvidence, setTxEvidence] = useState([]);

  // Editable fulfillment inputs on the resolve page (for live re-analysis & Test 3/9/11)
  const [carrierName, setCarrierName] = useState(launchContext?.initialCarrier || 'USPS');
  const [trackingNumber, setTrackingNumber] = useState(
    launchContext?.initialTracking ?? '9400111899223192348571'
  );
  const [deliveryNotes, setDeliveryNotes] = useState(
    launchContext?.initialNotes ||
      'Order dispatched via USPS Priority Mail to registered buyer address.'
  );
  const [claimText, setClaimText] = useState(launchContext?.customClaim || '');
  const [showLiveTimeline, setShowLiveTimeline] = useState(true);
  const [showUploaderPanel, setShowUploaderPanel] = useState(false);

  const uploaderRef = useRef(null);

  const approval = useApproval({ onToast });
  const upload = useEvidenceUpload({
    onToast,
    onEvidenceChanged: (reason) => {
      approval.invalidateApproval(reason);
    },
  });
  const analysis = useDisputeAnalysis();

  const buildCombinedEvidenceRecords = (disp, txEvList, currNotes, currCarrier, currTracking, docName) => {
    const base = [...(disp?.default_evidence || []), ...(txEvList || [])];
    if (currTracking || currNotes || docName) {
      base.push({
        evidence_id: 'EV-MERCHANT-FULFILLMENT',
        source_type: docName ? 'merchant_document' : 'merchant_attestation',
        source_name: 'Merchant Dispute Workspace Input',
        timestamp: new Date().toISOString(),
        transaction_ref: disp?.transaction_reference || '',
        content: [
          disp?.transaction_reference ? `Order ${disp.transaction_reference}` : null,
          currCarrier ? `Carrier ${currCarrier}` : null,
          currTracking ? `Tracking ${currTracking}` : null,
          docName ? `Document ${docName}` : null,
          currNotes || null,
        ]
          .filter(Boolean)
          .join(' · '),
      });
    }
    if (base.length === 0) {
      base.push({
        evidence_id: 'EV-DISPUTE-RECORD',
        source_type: 'store_record',
        content: `Dispute ${disp?.dispute_id || disputeId} for ${disp?.amount || '0.00'} ${disp?.currency || 'USD'}`,
      });
    }
    return base;
  };

  const executeFullAnalysis = async (
    currDispute,
    currTxEv,
    cName,
    tNum,
    dNotes,
    dName,
    activeClaimText
  ) => {
    const targetId = currDispute?.dispute_id || disputeId;
    const prepResult = await analysis.runStream(
      targetId,
      {
        carrier_name: cName,
        tracking_number: tNum,
        delivery_document_name: dName,
        fulfillment_notes: dNotes,
      },
      {
        onCompleteResult: (res) => {
          if (res?.draft_response) {
            approval.setEditableDraft(res.draft_response);
          }
        },
      }
    );

    const effectiveClaim =
      activeClaimText?.trim() ||
      currDispute?.default_claims?.[0]?.claim_text ||
      `Order ${currDispute?.transaction_reference || targetId} payment was captured and fulfillment tracking ${tNum || 'record'} was provided via ${cName || 'carrier'}.`;

    if (!activeClaimText?.trim()) {
      setClaimText(effectiveClaim);
    }

    const evRecords = buildCombinedEvidenceRecords(
      currDispute,
      currTxEv,
      dNotes,
      cName,
      tNum,
      dName
    );
    await analysis.runClaimAlignment({
      transactionReference: currDispute?.transaction_reference || targetId,
      claims: [
        {
          claim_id: 'CLM-MERCHANT-01',
          claim_text: effectiveClaim,
        },
      ],
      evidenceRecords: evRecords,
      customerDisputeReason: currDispute?.dispute_reason || 'MERCHANDISE_OR_SERVICE_NOT_RECEIVED',
      claimedRecipient: currDispute?.buyer_email || undefined,
    });

    return prepResult;
  };

  const loadDisputeData = async () => {
    setLoading(true);
    setLoadError(null);
    approval.resetApprovalState();

    try {
      const data = await api.getDispute(disputeId);
      setDispute(data);

      let fetchedTx = null;
      let fetchedTxEv = [];
      if (data.transaction_reference) {
        const [txObj, txEvObj] = await Promise.all([
          api.getTransaction(data.transaction_reference).catch(() => null),
          api.getTransactionEvidence(data.transaction_reference).catch(() => null),
        ]);
        fetchedTx = txObj;
        fetchedTxEv = txEvObj?.evidence || [];
      }
      setTransaction(fetchedTx);
      setTxEvidence(fetchedTxEv);

      let initCarrier = launchContext?.initialCarrier || 'USPS';
      let initTracking =
        launchContext?.initialTracking !== undefined
          ? launchContext.initialTracking
          : '9400111899223192348571';
      let initNotes =
        launchContext?.initialNotes ||
        'Order dispatched via USPS Priority Mail to registered buyer address.';
      let initDoc = launchContext?.initialDocName || '';

      if (data.submitted_evidence) {
        approval.setSubmissionResult({
          success: true,
          submitted: true,
          carrier_name: data.submitted_evidence.carrier_name,
          tracking_number: data.submitted_evidence.tracking_number,
          submission_id: data.submitted_evidence.submission_id,
          submitted_at: data.submitted_evidence.submitted_at,
          dispute_state: data.status || 'LOCAL_SIMULATED_SUBMISSION',
        });
        initCarrier = data.submitted_evidence.carrier_name || initCarrier;
        initTracking = data.submitted_evidence.tracking_number || initTracking;
      } else {
        approval.setSubmissionResult(null);
      }

      const initClaim =
        launchContext?.customClaim ||
        data.default_claims?.[0]?.claim_text ||
        `Order ${data.transaction_reference || data.dispute_id} payment of ${data.amount || '0.00'} ${data.currency || 'USD'} was captured and shipment tracking ${initTracking || 'record'} was provided.`;

      setCarrierName(initCarrier);
      setTrackingNumber(initTracking);
      setDeliveryNotes(initNotes);
      setClaimText(initClaim);

      setLoading(false);

      await executeFullAnalysis(
        data,
        fetchedTxEv,
        initCarrier,
        initTracking,
        initNotes,
        initDoc,
        initClaim
      );
    } catch (err) {
      setLoadError(err.message || `Failed to load dispute ${disputeId}`);
      setLoading(false);
    }
  };

  useEffect(() => {
    loadDisputeData();
    return () => {
      analysis.cancelStream();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [disputeId]);

  const activeDocName =
    upload.primaryUploaded?.response?.filename || launchContext?.initialDocName || '';
  const activeProofUrl =
    upload.primaryUploaded?.response?.proof_document_url ||
    (activeDocName ? `https://proofledger.local/docs/${activeDocName}` : null);

  const handleAnalyzeClick = async () => {
    approval.invalidateApproval('Re-running evidence analysis clears any prior approval.');
    setShowLiveTimeline(true);
    await executeFullAnalysis(
      dispute,
      txEvidence,
      carrierName,
      trackingNumber,
      deliveryNotes,
      activeDocName,
      claimText
    );
  };

  const handleReverifyClaim = async () => {
    approval.invalidateApproval('Claim statement updated — prior approval invalidated.');
    const evRecords = buildCombinedEvidenceRecords(
      dispute,
      txEvidence,
      deliveryNotes,
      carrierName,
      trackingNumber,
      activeDocName
    );
    await analysis.runClaimAlignment({
      transactionReference: dispute?.transaction_reference || disputeId,
      claims: [{ claim_id: 'CLM-MERCHANT-EDIT', claim_text: claimText }],
      evidenceRecords: evRecords,
      customerDisputeReason: dispute?.dispute_reason || 'MERCHANDISE_OR_SERVICE_NOT_RECEIVED',
      claimedRecipient: dispute?.buyer_email || undefined,
    });
  };

  const scrollToUploader = () => {
    setShowUploaderPanel(true);
    setTimeout(() => {
      uploaderRef.current?.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }, 80);
  };

  if (loading) {
    return <LoadingState rows={5} label={`Loading dispute workspace for ${disputeId}...`} />;
  }

  if (loadError) {
    return (
      <div className="space-y-4">
        <ErrorState
          title="Could not load dispute workspace"
          message={loadError}
          onRetry={loadDisputeData}
        />
        {onBackToInbox && (
          <button
            type="button"
            onClick={onBackToInbox}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-white border border-[#E6E4DD]"
          >
            <ArrowLeft className="w-3.5 h-3.5" />
            <span>Return to Dispute Inbox</span>
          </button>
        )}
      </div>
    );
  }

  const isLivePayPal = Boolean(dispute?.is_live_paypal_dispute);
  const validationErrors = analysis.aiPrep?.validation_errors || [];

  return (
    <div className="space-y-6">
      <PageHeader
        title={`Resolve Dispute · ${dispute?.dispute_id || disputeId}`}
        subtitle={
          dispute?.customer_claim ||
          'Deterministic payment/order validation paired with advisory NLI claim alignment and grounded merchant review.'
        }
        badge={
          <div className="flex flex-wrap items-center gap-2">
            {isLivePayPal ? (
              <span className="inline-flex items-center px-2.5 py-0.5 rounded-md text-[11px] font-medium bg-emerald-50 text-emerald-800 border border-emerald-200">
                PAYPAL SANDBOX LIVE
              </span>
            ) : (
              <span className="inline-flex items-center px-2.5 py-0.5 rounded-md text-[11px] font-medium bg-stone-100 text-stone-700 border border-stone-200">
                LOCAL DEMO — NOT A PAYPAL DISPUTE
              </span>
            )}
            <StatusBadge size="xs" status={dispute?.status || 'WAITING_FOR_SELLER_RESPONSE'} />
          </div>
        }
        actions={
          <>
            {onBackToInbox && (
              <button
                type="button"
                onClick={onBackToInbox}
                className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs font-medium bg-white text-[#18181B] border border-[#E6E4DD] hover:bg-[#F8F7F3] transition-colors"
              >
                <ArrowLeft className="w-3.5 h-3.5" />
                <span>Inbox</span>
              </button>
            )}
            <button
              type="button"
              onClick={handleAnalyzeClick}
              disabled={analysis.analyzing}
              className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg text-xs font-medium bg-[#18181B] text-white hover:bg-[#27272A] disabled:opacity-50 transition-colors"
            >
              {analysis.analyzing ? (
                <>
                  <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                  <span>Analyzing...</span>
                </>
              ) : (
                <>
                  <Sparkles className="w-3.5 h-3.5 text-[#99F6E4]" />
                  <span>Analyze Evidence</span>
                </>
              )}
            </button>
          </>
        }
      />

      {/* Quick Inline Fulfillment & Evidence Inputs */}
      <section className="bg-white rounded-xl border border-[#E6E4DD] p-4 sm:p-5 space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <h2 className="text-sm font-semibold text-[#18181B]">
              Fulfillment Inputs &amp; Supporting Documents
            </h2>
            <p className="text-xs text-[#71717A]">
              Carrier/tracking entries are treated as merchant attestation until an independent carrier scan is attached.
            </p>
          </div>

          <button
            type="button"
            onClick={() => setShowUploaderPanel((v) => !v)}
            className="inline-flex items-center gap-1 text-xs font-medium text-[#0F766E] hover:underline"
          >
            <span>{showUploaderPanel ? 'Hide document uploader' : 'Attach PDF / image proof'}</span>
            {showUploaderPanel ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
          </button>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          <div>
            <label htmlFor="resolveCarrierSelect" className="block text-[11px] font-medium text-[#52525B] mb-1">
              Carrier Name
            </label>
            <select
              id="resolveCarrierSelect"
              value={carrierName}
              onChange={(e) => {
                setCarrierName(e.target.value);
                approval.invalidateApproval('Carrier name changed after approval — re-approval required.');
              }}
              className="w-full px-3 py-2 rounded-lg text-xs bg-white border border-[#E6E4DD] text-[#18181B] focus:outline-none focus:ring-2 focus:ring-[#0F766E]/20"
            >
              {['USPS', 'UPS', 'FedEx', 'DHL', 'Royal Mail', 'Canada Post', 'Other'].map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label htmlFor="trackingNumberInput" className="block text-[11px] font-medium text-[#52525B] mb-1">
              Tracking Number
            </label>
            <input
              id="trackingNumberInput"
              type="text"
              value={trackingNumber}
              onChange={(e) => {
                setTrackingNumber(e.target.value);
                approval.invalidateApproval('Tracking number changed after approval — re-approval required.');
              }}
              placeholder="Enter tracking number"
              className="w-full px-3 py-2 rounded-lg text-xs font-mono bg-white border border-[#E6E4DD] text-[#18181B] focus:outline-none focus:ring-2 focus:ring-[#0F766E]/20"
            />
          </div>

          <div>
            <label htmlFor="resolveNotesInput" className="block text-[11px] font-medium text-[#52525B] mb-1">
              Delivery / Fulfillment Notes
            </label>
            <input
              id="resolveNotesInput"
              type="text"
              value={deliveryNotes}
              onChange={(e) => {
                setDeliveryNotes(e.target.value);
                approval.invalidateApproval('Fulfillment notes edited after approval — re-approval required.');
              }}
              placeholder="Add carrier or delivery notes"
              className="w-full px-3 py-2 rounded-lg text-xs bg-white border border-[#E6E4DD] text-[#18181B] focus:outline-none focus:ring-2 focus:ring-[#0F766E]/20"
            />
          </div>
        </div>

        {(showUploaderPanel || upload.files.length > 0) && (
          <div ref={uploaderRef} className="pt-2 border-t border-[#EFECE4]">
            <EvidenceUploader
              compact
              disputeId={dispute?.dispute_id || disputeId}
              files={upload.files}
              selectedCategory={upload.selectedCategory}
              onChangeCategory={upload.setSelectedCategory}
              validationError={upload.validationError}
              onFilesSelected={upload.addAndUploadFiles}
              onRetry={upload.retryUpload}
              onRemove={upload.removeFile}
              disabled={analysis.analyzing}
            />
          </div>
        )}
      </section>

      {/* SCREEN C: Live AI Analysis Timeline */}
      <div>
        <div className="flex items-center justify-between mb-2">
          <span className="text-xs font-medium text-[#52525B]">
            Real-time SSE Verification Pipeline (10 stages)
          </span>
          <button
            type="button"
            onClick={() => setShowLiveTimeline((v) => !v)}
            className="text-xs font-medium text-[#0F766E] hover:underline"
          >
            {showLiveTimeline ? 'Collapse pipeline view' : 'Expand pipeline view'}
          </button>
        </div>

        {showLiveTimeline && (
          <LiveAnalysisTimeline
            disputeId={dispute?.dispute_id || disputeId}
            stages={analysis.stages}
            streamPhase={analysis.streamPhase}
            analysisError={analysis.analysisError}
            onRetry={handleAnalyzeClick}
          />
        )}
      </div>

      {/* SCREEN D: Detailed Verification Results */}
      {analysis.aiPrep && (
        <div className="space-y-6">
          <VerificationSummary
            aiPrep={analysis.aiPrep}
            claimVerification={analysis.claimVerification}
            systemStatus={systemStatus}
            deterministicFailures={validationErrors}
          />

          <OrderPaymentVerification
            dispute={dispute}
            transaction={transaction}
            aiPrep={analysis.aiPrep}
            merchantContext={launchContext?.merchantContext}
            validationErrors={validationErrors}
          />

          <DeliveryJourney
            carrierName={carrierName}
            trackingNumber={trackingNumber}
            documentName={activeDocName}
            fulfillmentNotes={deliveryNotes}
            aiPrep={analysis.aiPrep}
            dispute={dispute}
            txEvidence={txEvidence}
            merchantContext={launchContext?.merchantContext}
          />

          <EvidenceClaimAlignment
            claimText={claimText}
            onChangeClaimText={(next) => {
              setClaimText(next);
              analysis.setClaimsStale(true);
              approval.invalidateApproval('Merchant claim modified — re-verify claim and re-approve.');
            }}
            onReverifyClaim={handleReverifyClaim}
            claimsStale={analysis.claimsStale}
            verifyingClaims={analysis.verifyingClaims}
            claimVerification={analysis.claimVerification}
            aiPrep={analysis.aiPrep}
            uploadedFiles={upload.uploadedFiles}
          />

          <ContradictionList
            validationErrors={validationErrors}
            aiPrep={analysis.aiPrep}
            claimVerification={analysis.claimVerification}
          />

          <MissingEvidencePanel
            aiPrep={analysis.aiPrep}
            onUploadClick={scrollToUploader}
          />

          <RecommendedActions
            aiPrep={analysis.aiPrep}
            claimVerification={analysis.claimVerification}
            validationErrors={validationErrors}
            approvalReceipt={approval.approvalReceipt}
          />

          {/* SCREEN E: Merchant Response & Approval */}
          <ResponseEditor
            dispute={dispute}
            aiPrep={analysis.aiPrep}
            editableDraft={approval.editableDraft}
            onChangeDraft={approval.updateDraft}
            uploadedFiles={upload.uploadedFiles}
            approvalReceipt={approval.approvalReceipt}
            approvalInvalidatedMsg={approval.approvalInvalidatedMsg}
          />

          <EvidenceApprovalPanel
            dispute={dispute}
            carrierName={carrierName}
            trackingNumber={trackingNumber}
            merchantChecked={approval.merchantChecked}
            onToggleChecked={approval.setMerchantChecked}
            approving={approval.approving}
            approvalReceipt={approval.approvalReceipt}
            approvalError={approval.approvalError}
            submitting={approval.submitting}
            submissionResult={approval.submissionResult}
            onRequestApprove={() => {
              if (!approval.merchantChecked) {
                approval.setApprovalError(
                  'Please check the confirmation attestation box before sealing approval.'
                );
                return;
              }
              approval.setApprovalError(null);
              approval.setShowConfirmModal(true);
            }}
            onSubmitEvidence={({ requireLivePayPal }) =>
              approval.executeSubmission({
                disputeId: dispute?.dispute_id || disputeId,
                isLivePayPal: requireLivePayPal,
                carrierName,
                trackingNumber,
                deliveryNotes,
                proofDocumentUrl: activeProofUrl,
                onRefreshDispute: async () => {
                  if (onRefreshParent) await onRefreshParent();
                },
              })
            }
          />
        </div>
      )}

      <ApprovalConfirmationModal
        isOpen={approval.showConfirmModal}
        onClose={() => approval.setShowConfirmModal(false)}
        approving={approval.approving}
        disputeId={dispute?.dispute_id || disputeId}
        isLivePayPal={isLivePayPal}
        carrierName={carrierName}
        trackingNumber={trackingNumber}
        proofDocumentUrl={activeProofUrl}
        draftExcerpt={approval.editableDraft}
        onConfirm={() =>
          approval.executeApproval({
            disputeId: dispute?.dispute_id || disputeId,
            carrierName,
            trackingNumber,
            deliveryNotes,
            proofDocumentUrl: activeProofUrl,
          })
        }
      />
    </div>
  );
}
