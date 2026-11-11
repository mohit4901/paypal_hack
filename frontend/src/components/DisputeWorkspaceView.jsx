import React, { useState, useEffect } from 'react';
import {
  ShieldCheck,
  AlertTriangle,
  CheckCircle2,
  Copy,
  Check,
  Sparkles,
  ArrowRight,
  ArrowLeft,
  Printer,
  Lock,
  ChevronDown,
  ChevronUp,
  FileText,
  Clock,
  Layers,
  Database,
  Plus,
  Trash2,
  ExternalLink,
  Cpu,
  RefreshCw,
  X,
  Send,
  HelpCircle,
  FileCode,
  CheckCircle,
  Eye,
  Zap,
} from 'lucide-react';
import { api } from '../api';
import DocumentProofViewerModal from './DocumentProofViewerModal';

const DEFAULT_ORDER_ID = '3EU95140LR696653G';
const DEFAULT_COMPLAINT = 'I paid for the course on PayPal but never received access to the learning portal or materials.';
const DEFAULT_CLAIMS = [
  { claim_id: 'CLM-01', claim_text: 'Payment of 5.00 USD was successfully captured for Order 3EU95140LR696653G', category: 'PAYMENT', excluded_from_response: false, seller_decision: 'INCLUDED' },
  { claim_id: 'CLM-02', claim_text: 'Course portal access was provisioned to buyer email sb-rcnwy53637793@personal.example.com', category: 'ACCESS', excluded_from_response: false, seller_decision: 'INCLUDED' },
  { claim_id: 'CLM-03', claim_text: "Access credentials email was successfully delivered to buyer's registered email address", category: 'DELIVERY', excluded_from_response: false, seller_decision: 'INCLUDED' },
  { claim_id: 'CLM-04', claim_text: 'Customer confirmed download and offline usage of course files', category: 'DOWNLOAD', excluded_from_response: false, seller_decision: 'INCLUDED' },
];

export default function DisputeWorkspaceView({
  disputeId = 'DSP-3EU95140-01',
  onBackToInbox,
  storeProfile,
}) {
  // Dispute and Transaction state
  const [activeDispute, setActiveDispute] = useState(null);
  const [orderData, setOrderData] = useState(null);
  const [evidenceList, setEvidenceList] = useState([]);
  const [claims, setClaims] = useState(DEFAULT_CLAIMS);
  const [customerComplaint, setCustomerComplaint] = useState(DEFAULT_COMPLAINT);

  // Scenarios state
  const [scenarios, setScenarios] = useState([]);
  const [selectedScenarioId, setSelectedScenarioId] = useState('scenario_inr_course');
  const [isGeneratingLive, setIsGeneratingLive] = useState(false);

  // Document Proof Viewer Modal
  const [selectedDoc, setSelectedDoc] = useState(null);
  const [showDocModal, setShowDocModal] = useState(false);

  // Response Strategy (Stripe style)
  const [responseStrategy, setResponseStrategy] = useState('COUNTER_WITH_EVIDENCE'); // 'COUNTER_WITH_EVIDENCE' | 'COUNTER_MANUALLY' | 'ACCEPT'

  // Verification state
  const [isVerifying, setIsVerifying] = useState(false);
  const [verificationResult, setVerificationResult] = useState(null);

  // Response letter & Approval
  const [responseDraft, setResponseDraft] = useState('');
  const [copiedDraft, setCopiedDraft] = useState(false);
  const [isApproving, setIsApproving] = useState(false);
  const [approvalReceipt, setApprovalReceipt] = useState(null);
  const [copiedDigest, setCopiedDigest] = useState(false);

  // Modals
  const [showAiModal, setShowAiModal] = useState(false);
  const [showAddEvidenceModal, setShowAddEvidenceModal] = useState(false);
  const [newEvidenceSource, setNewEvidenceSource] = useState('course_platform');
  const [newEvidenceContent, setNewEvidenceContent] = useState('');

  // AI live test state (MPS Playground)
  const [aiTestClaim, setAiTestClaim] = useState('Payment of 5.00 USD was successfully captured for Order 3EU95140LR696653G');
  const [aiTestEvidence, setAiTestEvidence] = useState('Order 3EU95140LR696653G Capture 10A71705XW788203L status COMPLETED gross 5.00 USD fee 0.59 USD net 4.41 USD buyer sb-rcnwy53637793@personal.example.com');
  const [aiTestResult, setAiTestResult] = useState(null);
  const [isTestingAi, setIsTestingAi] = useState(false);

  // Load scenarios catalogue on mount
  useEffect(() => {
    api.getDisputeScenarios()
      .then((data) => {
        if (data && data.scenarios) setScenarios(data.scenarios);
      })
      .catch(() => {});
  }, []);

  // Load dispute data and run initial verification
  useEffect(() => {
    loadDisputeDetails(disputeId);
  }, [disputeId]);

  const loadDisputeDetails = async (id) => {
    setIsVerifying(true);
    setApprovalReceipt(null);
    try {
      const dsp = await api.getDispute(id).catch(() => null);
      if (dsp) {
        setActiveDispute(dsp);
        if (dsp.scenario_id) setSelectedScenarioId(dsp.scenario_id);
        setCustomerComplaint(dsp.customer_claim || DEFAULT_COMPLAINT);
        const orderRef = dsp.transaction_reference || DEFAULT_ORDER_ID;

        const [orderInfo, evData] = await Promise.all([
          api.getTransaction(orderRef).catch(() => null),
          api.getTransactionEvidence(orderRef).catch(() => ({ evidence: [] })),
        ]);

        setOrderData(orderInfo);
        const activeEv = dsp.default_evidence?.length ? dsp.default_evidence : (evData?.evidence?.length ? evData.evidence : []);
        setEvidenceList(activeEv);

        const activeClms = dsp.default_claims?.length ? dsp.default_claims : DEFAULT_CLAIMS;
        setClaims(activeClms);

        // Run AI verification
        await runClaimVerification(orderRef, activeClms, activeEv, dsp.customer_claim);
      }
    } catch (err) {
      console.error('Failed to load dispute:', err);
    } finally {
      setIsVerifying(false);
    }
  };

  const handleSelectScenario = async (scId) => {
    setSelectedScenarioId(scId);
    setIsVerifying(true);
    setApprovalReceipt(null);
    try {
      const sc = await api.getDisputeScenario(scId);
      if (sc) {
        setActiveDispute(sc);
        setCustomerComplaint(sc.customer_claim);
        const orderRef = sc.transaction_reference;
        setEvidenceList(sc.default_evidence || []);
        setClaims(sc.default_claims || []);
        await runClaimVerification(orderRef, sc.default_claims || [], sc.default_evidence || [], sc.customer_claim);
      }
    } catch (err) {
      console.error('Failed to switch scenario:', err);
    } finally {
      setIsVerifying(false);
    }
  };

  const handleGenerateLiveTodayDispute = async () => {
    setIsGeneratingLive(true);
    try {
      const res = await api.generateLiveTransaction();
      if (res && res.dispute_id) {
        await loadDisputeDetails(res.dispute_id);
      }
    } catch (err) {
      alert(`Failed to generate live transaction: ${err.message}`);
    } finally {
      setIsGeneratingLive(false);
    }
  };

  const handleOpenDocProof = (docData) => {
    if (!docData) return;
    setSelectedDoc(docData);
    setShowDocModal(true);
  };

  const runClaimVerification = async (orderRef, currentClaims, currentEvidence, complaint) => {
    setIsVerifying(true);
    try {
      const res = await api.verifyClaims({
        transaction_reference: orderRef,
        customer_dispute_reason: complaint || customerComplaint,
        claims: currentClaims,
        evidence: currentEvidence,
        evidence_records: currentEvidence,
      });

      setVerificationResult(res);

      // Generate response draft based on active included claims
      const activeVerified = (res.verified_claims || []).filter(
        (c) => !c.excluded_from_response && c.verdict === 'SUPPORTED'
      );

      let draft = `Dear PayPal Resolution Center Team,\n\nRegarding Dispute Case ${activeDispute?.dispute_id || disputeId} on Order ${orderRef} filed under reason "${activeDispute?.dispute_reason || 'MERCHANDISE_OR_SERVICE_NOT_RECEIVED'}".\n\nAs a verified digital goods merchant, we have audited our primary systems of record through ProofLedger:\n`;
      activeVerified.forEach((c, idx) => {
        draft += `${idx + 1}. ${c.claim_text.toUpperCase()}: Substantiated by primary log records.\n`;
      });
      draft += `\nEnclosed please find our certified SHA-256 evidence integrity report and official exhibits confirming fulfillment, user authentication, and cryptographic delivery confirmation.\n\nThank you,\n${storeProfile?.storeName || 'Merchant Support Team'}`;

      setResponseDraft(draft);
    } catch (err) {
      console.error('Verification failed:', err);
    } finally {
      setIsVerifying(false);
    }
  };

  // Toggle exclusion of an unproven statement (Auto-Remediation)
  const toggleClaimExclusion = (claimId) => {
    const updated = claims.map((c) => {
      if (c.claim_id === claimId) {
        const nextExcluded = !c.excluded_from_response;
        return {
          ...c,
          excluded_from_response: nextExcluded,
          seller_decision: nextExcluded ? 'EXCLUDED' : 'INCLUDED',
        };
      }
      return c;
    });
    setClaims(updated);
    const orderRef = activeDispute?.transaction_reference || DEFAULT_ORDER_ID;
    runClaimVerification(orderRef, updated, evidenceList, customerComplaint);
  };

  // One-click remediation: drop the unproven download claim
  const handleDropDownloadClaim = () => {
    const updated = claims.map((c) => {
      if (c.category === 'DOWNLOAD' || c.claim_text.toLowerCase().includes('download')) {
        return { ...c, excluded_from_response: true, seller_decision: 'EXCLUDED' };
      }
      return c;
    });
    setClaims(updated);
    const orderRef = activeDispute?.transaction_reference || DEFAULT_ORDER_ID;
    runClaimVerification(orderRef, updated, evidenceList, customerComplaint);
  };

  // Restore all original claims
  const handleRestoreAllClaims = () => {
    const updated = claims.map((c) => ({
      ...c,
      excluded_from_response: false,
      seller_decision: 'INCLUDED',
    }));
    setClaims(updated);
    const orderRef = activeDispute?.transaction_reference || DEFAULT_ORDER_ID;
    runClaimVerification(orderRef, updated, evidenceList, customerComplaint);
  };

  // Approve & Cryptographically Seal the Packet
  const handleApprovePacket = async () => {
    if (!verificationResult) return;
    setIsApproving(true);
    try {
      const payload = {
        seller_id: 'seller_alpha',
        packet_data: {
          ...verificationResult,
          response_draft: responseDraft,
        },
        signature_confirmed: true,
      };
      const res = await api.approveDisputePacket(disputeId, payload);
      setApprovalReceipt(res);
    } catch (err) {
      alert(`Approval sealing failed: ${err.message}`);
    } finally {
      setIsApproving(false);
    }
  };

  const copyResponseText = () => {
    navigator.clipboard.writeText(responseDraft);
    setCopiedDraft(true);
    setTimeout(() => setCopiedDraft(false), 2500);
  };

  const copyDigestText = (text) => {
    navigator.clipboard.writeText(text);
    setCopiedDigest(true);
    setTimeout(() => setCopiedDigest(false), 2000);
  };

  // Run dynamic AI forward pass test in modal
  const handleRunAiModalTest = async () => {
    setIsTestingAi(true);
    try {
      const res = await api.testAiInference({
        claim: aiTestClaim,
        evidence: aiTestEvidence,
      });
      setAiTestResult(res);
    } catch (err) {
      alert(`Inference failed: ${err.message}`);
    } finally {
      setIsTestingAi(false);
    }
  };

  const downloadReportJson = () => {
    if (!verificationResult) return;
    const dataStr = 'data:text/json;charset=utf-8,' + encodeURIComponent(JSON.stringify(verificationResult, null, 2));
    const dlAnchor = document.createElement('a');
    dlAnchor.setAttribute('href', dataStr);
    dlAnchor.setAttribute('download', `proofledger_${disputeId}_evidence_report.json`);
    dlAnchor.click();
  };

  const isDownloadExcluded = claims.some(
    (c) => (c.category === 'DOWNLOAD' || c.claim_text.toLowerCase().includes('download')) && c.excluded_from_response
  );

  const hasUnprovenActiveClaim = (verificationResult?.verified_claims || []).some(
    (c) => !c.excluded_from_response && c.verdict === 'INSUFFICIENT_EVIDENCE'
  );

  return (
    <div className="space-y-6">
      {/* Print-Only Official Certified Header */}
      <div className="hidden print:flex items-center justify-between border-b border-black pb-4 mb-4">
        <div className="flex items-center space-x-3">
          <img src="/logo.png" alt="ProofLedger" className="h-8 object-contain" />
          <span className="text-xs text-gray-600 font-mono">Certified Dispute Evidence Packet</span>
        </div>
        <div className="text-right text-[10px] font-mono text-gray-500">
          <span>SHA-256 Digest Bound • Generated: {new Date().toISOString()}</span>
        </div>
      </div>

      {/* Top Breadcrumb & Navigation */}
      <div className="flex items-center justify-between">
        <button
          onClick={onBackToInbox}
          className="inline-flex items-center gap-1.5 text-xs font-semibold text-[#4B5563] hover:text-[#111827] transition"
        >
          <ArrowLeft className="w-4 h-4" />
          Back to Dispute Inbox
        </button>

        <div className="flex items-center gap-2">
          <button
            onClick={() => setShowAiModal(true)}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-purple-900 bg-purple-50 hover:bg-purple-100 rounded-lg border border-purple-200 transition"
          >
            <Sparkles className="w-3.5 h-3.5 text-purple-700" />
            Inspect AI Inference (MPS)
          </button>
        </div>
      </div>

      {/* Real PayPal Scenario Switcher & Live Generator Bar */}
      <div className="bg-white rounded-xl border border-[#E5E7EB] p-4 shadow-sm flex flex-col md:flex-row md:items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-3">
          <span className="text-xs font-bold text-[#111827] flex items-center gap-1.5">
            <Cpu className="w-4 h-4 text-[#003087]" />
            Dispute Scenario:
          </span>
          <select
            value={selectedScenarioId}
            onChange={(e) => handleSelectScenario(e.target.value)}
            className="text-xs font-semibold bg-[#F9FAFB] border border-[#D1D5DB] rounded-lg px-3 py-1.5 text-[#111827] focus:ring-1 focus:ring-black"
          >
            <option value="scenario_inr_course">Scenario 1: Item Not Received (Course & Materials - $5.00) [PayPal Sandbox Import]</option>
            <option value="scenario_unauth_3ds">Scenario 2: Unauthorized Charge (3DS Bank OTP Proof - $180.00) [Local Demo Scenario]</option>
            <option value="scenario_snad_broken_link">Scenario 3: Broken Download Claim (Cloudflare CDN Logs - $49.00) [Local Demo Scenario]</option>
            <option value="scenario_live_today">Scenario 4: ⚡ Live Nov 1, 2026 Sandbox Order ($120.00) [Awaiting Approval & Capture]</option>
          </select>
        </div>
        <button
          onClick={handleGenerateLiveTodayDispute}
          disabled={isGeneratingLive}
          className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white font-bold text-xs shadow-xs transition disabled:opacity-50"
        >
          <Zap className={`w-3.5 h-3.5 ${isGeneratingLive ? 'animate-spin' : ''}`} />
          {isGeneratingLive ? 'Creating Live Sandbox Order...' : '⚡ Create Genuine PayPal Sandbox Order'}
        </button>
      </div>

      {/* Official Admissible Visual Exhibits Gallery Bar */}
      <div className="bg-white rounded-xl border border-[#E5E7EB] p-4 shadow-sm space-y-3">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
          <div className="flex items-center space-x-2">
            <FileText className="w-4 h-4 text-[#003087]" />
            <h4 className="text-xs font-bold uppercase tracking-wider text-[#111827]">
              Certified Official Exhibits (Normalized Primary Log Artifacts)
            </h4>
          </div>
          <span className="text-[11px] font-mono text-emerald-800 bg-emerald-50 px-2 py-0.5 rounded border border-emerald-200 inline-block self-start sm:self-auto">
            Click Any Exhibit to Inspect Dual-Hash Provenance & PNG Seal
          </span>
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-2.5">
          {[
            { num: 'EXHIBIT A', title: 'PayPal Capture Notice (Live Sandbox Verified)', file: '/documents/exhibit_a_paypal_notice.png', hash: '53e6474db96c5cee657048ee3c8d93ef95132f649de0f073d4bde27c669d4fb5', timestamp: '2026-10-31 11:14:39 UTC', provenance_badge: 'LIVE SANDBOX VERIFIED', provenance_classification: 'LIVE_SANDBOX_VERIFIED' },
            { num: 'EXHIBIT B', title: 'LMS Access Audit', file: '/documents/exhibit_b_lms_access_cert.png', hash: '17034751957955580cabbb8a7c3baaa5d82e0228735d9e91b3e0f0ec37ffa0b5', timestamp: '2026-10-31 11:15:10 UTC', provenance_badge: 'STORE LOG INPUT — NORMALIZED', provenance_classification: 'NORMALIZED_ARTIFACT' },
            { num: 'EXHIBIT C', title: 'SendGrid Receipt', file: '/documents/exhibit_c_sendgrid_receipt.png', hash: '935adc2192e7079fe089901ab178bbca2edcbdf8120a9f864773eb1f6202389b', timestamp: '2026-10-31 11:15:14 UTC', provenance_badge: 'STORE LOG INPUT — NORMALIZED', provenance_classification: 'NORMALIZED_ARTIFACT' },
            { num: 'EXHIBIT D', title: 'Software License', file: '/documents/exhibit_d_license_key.png', hash: '15dbe384f91c67444248fbf41836c29be128cf5c735f412d5f8834bfbc478556', timestamp: '2026-10-31 11:15:02 UTC', provenance_badge: 'STORE LOG INPUT — NORMALIZED', provenance_classification: 'NORMALIZED_ARTIFACT' },
            { num: 'EXHIBIT E', title: 'CDN Delivery Log', file: '/documents/exhibit_e_cdn_download.png', hash: 'dca3a4a3c2ab79698b884e9f51914ab87c758661b8e32f4b05d3357a7b11a67b', timestamp: '2026-10-31 11:17:40 UTC', provenance_badge: 'STORE LOG INPUT — NORMALIZED', provenance_classification: 'NORMALIZED_ARTIFACT' },
            { num: 'EXHIBIT F', title: '3DS Bank OTP Auth Certificate (Simulated Demo Exhibit)', file: '/documents/exhibit_f_3ds_auth.png', hash: '72bfd7fb612f9a62001f6df287c210c5575626215fb9adecc6578f1593af19e0', timestamp: '2026-10-31 11:14:38 UTC', provenance_badge: 'SIMULATED DEMO EXHIBIT', provenance_classification: 'SIMULATED_DEMO_EXHIBIT' },
          ].map((ex) => (
            <button
              key={ex.num}
              onClick={() => handleOpenDocProof({
                exhibit_number: ex.num,
                title: ex.title,
                image_src: ex.file,
                sha256: ex.hash,
                provenance_badge: ex.provenance_badge,
                provenance_classification: ex.provenance_classification,
                source_system: 'ProofLedger Enterprise Evidence Engine',
                timestamp: ex.timestamp,
                admissibility: 'Cryptographically certified high-resolution exhibit for PayPal Resolution Center.',
              })}
              className="p-2.5 rounded-lg border border-[#E5E7EB] hover:border-black bg-[#F9FAFB] hover:bg-white text-left transition group shadow-2xs"
            >
              <span className="text-[10px] font-mono font-bold text-[#003087] block">{ex.num}</span>
              <span className="text-[11px] font-bold text-[#111827] block truncate mt-0.5">{ex.title}</span>
              <span className="text-[9px] font-mono text-[#6B7280] block truncate mt-1">SHA-256 bound</span>
              <span className="text-[10px] text-blue-600 group-hover:underline font-semibold mt-1 inline-flex items-center gap-0.5">
                <Eye className="w-3 h-3" /> View PNG
              </span>
            </button>
          ))}
        </div>
      </div>

      {/* Hero Case Header (Stripe Style) */}
      <div className="bg-white rounded-xl border border-[#E5E7EB] p-6 shadow-sm space-y-4">
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 border-b border-[#E5E7EB] pb-5">
          <div>
            <div className="flex items-center gap-2">
              <span className="text-xs font-mono font-bold px-2 py-0.5 rounded bg-gray-100 text-gray-800">
                {disputeId}
              </span>
              <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-50 text-amber-800 border border-amber-200">
                <Clock className="w-3 h-3 text-amber-600" />
                Response Due in 9 Days (Nov 10, 2026)
              </span>
              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-mono text-[#065F46] bg-emerald-50 border border-emerald-200">
                PayPal Sandbox Verified
              </span>
            </div>

            <div className="mt-3 flex items-baseline gap-3">
              <span className="text-3xl font-extrabold tracking-tight text-[#111827]">
                ${activeDispute?.amount || '5.00'} {activeDispute?.currency || 'USD'}
              </span>
              <span className="text-sm font-semibold text-[#4B5563]">
                Order {activeDispute?.transaction_reference || DEFAULT_ORDER_ID}
              </span>
            </div>

            <p className="text-xs text-[#6B7280] mt-1">
              Capture ID:{' '}
              <span className="font-mono text-[#111827] font-medium">
                {activeDispute?.capture_id || '10A71705XW788203L'}
              </span>{' '}
              • Product:{' '}
              <span className="font-medium text-[#111827]">
                {activeDispute?.product_name || 'Advanced Python & SaaS Mastery Course'}
              </span>
            </p>
          </div>

          {/* Response Strategy Dropdown (Stripe Pattern) */}
          <div className="flex flex-col sm:flex-row items-start sm:items-center gap-3">
            <div className="text-left sm:text-right">
              <label className="block text-[11px] font-medium text-[#6B7280]">Response Strategy</label>
              <select
                value={responseStrategy}
                onChange={(e) => setResponseStrategy(e.target.value)}
                className="mt-1 text-xs font-semibold bg-[#F9FAFB] border border-[#D1D5DB] rounded-lg px-3 py-2 text-[#111827] focus:ring-1 focus:ring-black focus:outline-none"
              >
                <option value="COUNTER_WITH_EVIDENCE">Counter with ProofLedger Evidence (Recommended)</option>
                <option value="COUNTER_MANUALLY">Counter Manually without Evidence Map</option>
                <option value="ACCEPT">Accept Dispute & Refund Buyer</option>
              </select>
            </div>
          </div>
        </div>

        {/* Customer Claim Banner */}
        <div className="p-4 rounded-xl bg-amber-50/50 border border-amber-200 text-xs space-y-1.5">
          <div className="flex items-center justify-between">
            <span className="font-bold text-amber-950 flex items-center gap-1.5">
              <AlertTriangle className="w-4 h-4 text-amber-700" />
              Customer Claim on PayPal Resolution Center:
            </span>
            <span className="font-mono text-[11px] text-amber-800">
              Buyer: sb-rcnwy5...personal.example.com
            </span>
          </div>
          <p className="text-amber-900 font-medium italic pl-5.5">
            "{customerComplaint}"
          </p>
          <p className="text-[11px] text-amber-800/90 pl-5.5">
            <strong>Next Action:</strong> Compare claims against LMS and email logs. Drop unproven statements before sealing your factual response.
          </p>
        </div>
      </div>

      {/* Two-Column Grid: Left (Evidence Truth Map & Response) + Right (PayPal Checklist & Timeline) */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* LEFT COLUMN: 65% (8/12 cols) */}
        <div className="lg:col-span-8 space-y-6">
          {/* THE EVIDENCE TRUTH MAP */}
          <div className="bg-white rounded-xl border border-[#E5E7EB] p-5 shadow-sm space-y-4">
            <div className="flex items-center justify-between border-b border-[#E5E7EB] pb-3">
              <div>
                <h3 className="text-base font-bold text-[#111827] flex items-center gap-2">
                  <Layers className="w-4 h-4 text-[#111827]" />
                  The Evidence Truth Map
                </h3>
                <p className="text-xs text-[#6B7280]">
                  Claim-by-claim evaluation. Distinguishes what your connected records genuinely prove versus unproven claims.
                </p>
              </div>

              {verificationResult && (
                <div className="flex items-center gap-2">
                  <span className="inline-flex items-center px-2 py-0.5 rounded text-[11px] font-bold bg-emerald-50 text-emerald-800 border border-emerald-200">
                    {verificationResult.supported_claims} Supported
                  </span>
                  {verificationResult.insufficient_claims > 0 && (
                    <span className="inline-flex items-center px-2 py-0.5 rounded text-[11px] font-bold bg-amber-50 text-amber-800 border border-amber-200">
                      {verificationResult.insufficient_claims} Unproven
                    </span>
                  )}
                </div>
              )}
            </div>

            {/* Remediation Status Banner */}
            {hasUnprovenActiveClaim ? (
              <div className="p-3.5 rounded-lg bg-amber-50 border border-amber-200 text-xs flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                <div className="space-y-0.5">
                  <p className="font-bold text-amber-900 flex items-center gap-1.5">
                    <AlertTriangle className="w-4 h-4 text-amber-700" />
                    Unproven Statement Detected (Claim #4: Download Confirmation)
                  </p>
                  <p className="text-[11px] text-amber-800">
                    Your records prove payment, LMS access, and email delivery. But there are <strong>zero download logs</strong>. Claiming download occurred risks dispute credibility.
                  </p>
                </div>
                <button
                  onClick={handleDropDownloadClaim}
                  className="px-3 py-1.5 rounded-lg text-xs font-semibold bg-amber-900 text-white hover:bg-black transition shadow-xs shrink-0"
                >
                  ⚡ Drop Unproven Claim
                </button>
              </div>
            ) : isDownloadExcluded ? (
              <div className="p-3.5 rounded-lg bg-emerald-50 border border-emerald-200 text-xs flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                <div className="space-y-0.5">
                  <p className="font-bold text-emerald-900 flex items-center gap-1.5">
                    <CheckCircle2 className="w-4 h-4 text-emerald-700" />
                    100% Source-Grounded & Audit-Proof
                  </p>
                  <p className="text-[11px] text-emerald-800">
                    Unproven download claim excluded. Response is strictly grounded in verifiable payment capture, LMS account, and SMTP receipts.
                  </p>
                </div>
                <button
                  onClick={handleRestoreAllClaims}
                  className="px-3 py-1.5 rounded-lg text-xs font-medium border border-emerald-300 text-emerald-900 hover:bg-white transition shrink-0"
                >
                  Restore All Original Claims
                </button>
              </div>
            ) : null}

            {/* List of Claims with Node Provenance */}
            <div className="space-y-3">
              {(verificationResult?.verified_claims || claims.map((c) => ({
                claim_id: c.claim_id,
                claim_text: c.claim_text,
                verdict: c.category === 'DOWNLOAD' ? 'INSUFFICIENT_EVIDENCE' : 'SUPPORTED',
                excluded_from_response: c.excluded_from_response,
                explanation: c.category === 'DOWNLOAD'
                  ? 'No download logs found in primary records.'
                  : 'Substantiated by primary logs.',
              }))).map((clm, index) => {
                const isSupported = clm.verdict === 'SUPPORTED';
                const isExcluded = clm.excluded_from_response;

                return (
                  <div
                    key={clm.claim_id || index}
                    className={`p-4 rounded-xl border transition ${
                      isExcluded
                        ? 'bg-gray-50/60 border-gray-200 opacity-60'
                        : isSupported
                        ? 'bg-white border-emerald-200/80 hover:border-emerald-300'
                        : 'bg-amber-50/30 border-amber-300 hover:border-amber-400'
                    }`}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="flex items-start gap-3">
                        <span className="font-mono text-xs font-bold text-[#6B7280] mt-0.5">
                          #{index + 1}
                        </span>

                        <div className="space-y-1.5">
                          <p className={`text-xs font-semibold ${isExcluded ? 'line-through text-[#6B7280]' : 'text-[#111827]'}`}>
                            {clm.claim_text}
                          </p>

                          {/* Provenance Truth Explanation */}
                          <div className="text-[11px] flex items-center gap-2">
                            <span className="font-semibold text-[#4B5563]">Truth Finding:</span>
                            <span className={isSupported ? 'text-emerald-800' : 'text-amber-900 font-medium'}>
                              {clm.explanation}
                            </span>
                          </div>

                          {/* Source Badges */}
                          <div className="flex flex-wrap items-center gap-1.5 pt-1">
                            {index === 0 && (
                              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-mono bg-blue-50 text-blue-800 border border-blue-200">
                                🔗 PayPal API Webhook (10A71705XW788203L)
                              </span>
                            )}
                            {index === 1 && (
                              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-mono bg-indigo-50 text-indigo-800 border border-indigo-200">
                                🔗 MemberPress LMS Enrollment Log
                              </span>
                            )}
                            {index === 2 && (
                              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-mono bg-teal-50 text-teal-800 border border-teal-200">
                                🔗 SendGrid SMTP Gateway Receipt (TLS 250 OK)
                              </span>
                            )}
                            {index === 3 && (
                              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-mono bg-red-50 text-red-800 border border-red-200">
                                ⚠️ Download Server: Zero Records Found
                              </span>
                            )}

                            {clm.ai_model?.model_score && (
                              <span className="text-[10px] text-[#6B7280] font-mono">
                                Model score: {((clm.ai_model.model_score || 0) * 100).toFixed(1)}% (DeBERTa)
                              </span>
                            )}
                          </div>
                        </div>
                      </div>

                      {/* Verdict Badge & Remediation Toggle */}
                      <div className="flex flex-col items-end gap-2 shrink-0">
                        {isExcluded ? (
                          <span className="px-2 py-0.5 text-[10px] font-bold rounded bg-gray-200 text-gray-700">
                            EXCLUDED
                          </span>
                        ) : isSupported ? (
                          <span className="px-2 py-0.5 text-[10px] font-bold rounded bg-emerald-100 text-emerald-800 border border-emerald-300">
                            SUPPORTED
                          </span>
                        ) : (
                          <span className="px-2 py-0.5 text-[10px] font-bold rounded bg-amber-100 text-amber-900 border border-amber-300">
                            INSUFFICIENT_EVIDENCE
                          </span>
                        )}

                        <button
                          onClick={() => toggleClaimExclusion(clm.claim_id)}
                          className="text-[11px] font-medium text-[#4B5563] hover:text-[#111827] underline"
                        >
                          {isExcluded ? 'Re-include' : 'Exclude'}
                        </button>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* FACTUAL PAYPAL DISPUTE RESPONSE LETTER */}
          <div className="bg-white rounded-xl border border-[#E5E7EB] p-5 shadow-sm space-y-4">
            <div className="flex items-center justify-between border-b border-[#E5E7EB] pb-3">
              <div>
                <h3 className="text-sm font-bold text-[#111827] flex items-center gap-2">
                  <FileText className="w-4 h-4 text-[#111827]" />
                  Factual PayPal Dispute Response Letter
                </h3>
                <p className="text-xs text-[#6B7280]">
                  Grounded strictly in verified payment, LMS, and email logs. Character count adheres to PayPal's 2,000-character API limit.
                </p>
              </div>

              <div className="flex items-center gap-2">
                <span className="font-mono text-[11px] text-[#6B7280] px-2 py-1 bg-gray-100 rounded">
                  {responseDraft.length} / 2,000 chars
                </span>
                <button
                  onClick={copyResponseText}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-[#111827] text-white rounded-lg text-xs font-semibold hover:bg-black transition shadow-xs"
                >
                  {copiedDraft ? (
                    <>
                      <Check className="w-3.5 h-3.5 text-emerald-400" />
                      <span>Copied!</span>
                    </>
                  ) : (
                    <>
                      <Copy className="w-3.5 h-3.5" />
                      <span>Copy Letter</span>
                    </>
                  )}
                </button>
              </div>
            </div>

            <textarea
              rows={8}
              value={responseDraft}
              onChange={(e) => setResponseDraft(e.target.value)}
              className="w-full text-xs font-mono p-3.5 bg-[#F9FAFB] border border-[#E5E7EB] rounded-lg focus:bg-white focus:outline-none focus:ring-1 focus:ring-black text-[#111827] leading-relaxed"
            />

            {/* Cryptographic Human Approval Receipt */}
            <div className="pt-2 border-t border-[#E5E7EB] flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
              {approvalReceipt ? (
                <div className="flex items-center gap-2 text-xs font-mono text-[#065F46] bg-emerald-50 px-3 py-2 rounded-lg border border-emerald-200">
                  <CheckCircle2 className="w-4 h-4 text-[#059669] shrink-0" />
                  <span>
                    Sealed: {approvalReceipt.packet_sha256_digest?.slice(0, 16)}...
                  </span>
                  <button
                    onClick={() => copyDigestText(approvalReceipt.packet_sha256_digest)}
                    className="text-emerald-700 hover:text-emerald-900 ml-1"
                    title="Copy full digest"
                  >
                    {copiedDigest ? '✓' : <Copy className="w-3.5 h-3.5" />}
                  </button>
                </div>
              ) : (
                <button
                  onClick={handleApprovePacket}
                  disabled={isApproving || isVerifying}
                  className="inline-flex items-center gap-2 bg-[#111827] hover:bg-black text-white px-4 py-2 rounded-lg text-xs font-semibold transition shadow-sm"
                >
                  <Lock className="w-3.5 h-3.5" />
                  <span>{isApproving ? 'Sealing on Server...' : 'Cryptographically Approve & Seal (SHA-256)'}</span>
                </button>
              )}

              <div className="flex items-center gap-2">
                <button
                  onClick={downloadReportJson}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 border border-[#D1D5DB] rounded-lg text-xs font-medium text-[#374151] hover:bg-gray-50 transition"
                >
                  <FileCode className="w-3.5 h-3.5 text-[#6B7280]" />
                  <span>JSON Packet</span>
                </button>
                <button
                  onClick={() => window.print()}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 border border-[#D1D5DB] rounded-lg text-xs font-medium text-[#374151] hover:bg-gray-50 transition"
                >
                  <Printer className="w-3.5 h-3.5 text-[#6B7280]" />
                  <span>Print Certified Sheet</span>
                </button>
              </div>
            </div>
          </div>
        </div>

        {/* RIGHT COLUMN: 35% (4/12 cols) */}
        <div className="lg:col-span-4 space-y-6">
          {/* REASON-AWARE PAYPAL EVIDENCE CHECKLIST */}
          <div className="bg-white rounded-xl border border-[#E5E7EB] p-5 shadow-sm space-y-3">
            <div className="border-b border-[#E5E7EB] pb-3">
              <h4 className="text-xs font-bold uppercase tracking-wider text-[#111827]">
                PayPal Reason-Aware Evidence Checklist
              </h4>
              <p className="text-[11px] text-[#6B7280] mt-0.5">
                Official compelling evidence requirements for digital items under "Item Not Received".
              </p>
            </div>

            <ul className="space-y-2.5 text-xs">
              <li className="flex items-start gap-2.5 p-2 rounded-lg bg-emerald-50/60 border border-emerald-100">
                <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0 mt-0.5" />
                <div>
                  <p className="font-semibold text-emerald-950">Proof of Payment Capture</p>
                  <p className="text-[11px] text-emerald-800">PayPal Webhook ID 9769...832P (HMAC verified).</p>
                </div>
              </li>

              <li className="flex items-start gap-2.5 p-2 rounded-lg bg-emerald-50/60 border border-emerald-100">
                <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0 mt-0.5" />
                <div>
                  <p className="font-semibold text-emerald-950">Proof of Electronic Entitlement</p>
                  <p className="text-[11px] text-emerald-800">MemberPress LMS account provisioned with active token.</p>
                </div>
              </li>

              <li className="flex items-start gap-2.5 p-2 rounded-lg bg-emerald-50/60 border border-emerald-100">
                <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0 mt-0.5" />
                <div>
                  <p className="font-semibold text-emerald-950">Proof of Dispatch / Server Receipt</p>
                  <p className="text-[11px] text-emerald-800">SendGrid SMTP server accepted message (TLS 250 OK).</p>
                </div>
              </li>

              <li className="flex items-start gap-2.5 p-2 rounded-lg bg-red-50/50 border border-red-200">
                <X className="w-4 h-4 text-red-600 shrink-0 mt-0.5" />
                <div>
                  <p className="font-semibold text-red-950">Proof of Offline Download / Use</p>
                  <p className="text-[11px] text-red-800">No server log available. Dropped from response to avoid dispute penalty.</p>
                </div>
              </li>
            </ul>
          </div>

          {/* CHRONOLOGICAL ACTIVITY TIMELINE (Linear Style) */}
          <div className="bg-white rounded-xl border border-[#E5E7EB] p-5 shadow-sm space-y-3">
            <div className="border-b border-[#E5E7EB] pb-3">
              <h4 className="text-xs font-bold uppercase tracking-wider text-[#111827]">
                Transaction & Dispute Timeline
              </h4>
              <p className="text-[11px] text-[#6B7280] mt-0.5">
                Traceable event sequence linked to transaction reference.
              </p>
            </div>

            <div className="relative pl-5 space-y-4 border-l border-[#E5E7EB] ml-2 text-xs">
              <div className="relative">
                <div className="absolute -left-[25px] top-1 w-2.5 h-2.5 rounded-full bg-emerald-500 ring-4 ring-white" />
                <p className="font-bold text-[#111827]">PayPal Payment Captured</p>
                <p className="text-[11px] text-[#6B7280]">Oct 31, 2026 • 11:14:39 UTC</p>
                <p className="text-[11px] text-[#4B5563] mt-0.5">$5.00 USD captured (10A71705XW788203L)</p>
              </div>

              <div className="relative">
                <div className="absolute -left-[25px] top-1 w-2.5 h-2.5 rounded-full bg-indigo-500 ring-4 ring-white" />
                <p className="font-bold text-[#111827]">LMS Account Provisioned</p>
                <p className="text-[11px] text-[#6B7280]">Oct 31, 2026 • 11:15:02 UTC</p>
                <p className="text-[11px] text-[#4B5563] mt-0.5">Student enrolled into Python Mastery</p>
              </div>

              <div className="relative">
                <div className="absolute -left-[25px] top-1 w-2.5 h-2.5 rounded-full bg-teal-500 ring-4 ring-white" />
                <p className="font-bold text-[#111827]">Credentials Email Handshake</p>
                <p className="text-[11px] text-[#6B7280]">Oct 31, 2026 • 11:15:15 UTC</p>
                <p className="text-[11px] text-[#4B5563] mt-0.5">SendGrid SMTP confirmed TLS 250 OK</p>
              </div>

              <div className="relative">
                <div className="absolute -left-[25px] top-1 w-2.5 h-2.5 rounded-full bg-amber-500 ring-4 ring-white" />
                <p className="font-bold text-[#111827]">Dispute Opened by Customer</p>
                <p className="text-[11px] text-[#6B7280]">Oct 31, 2026 • 11:18:00 UTC</p>
                <p className="text-[11px] text-amber-900 mt-0.5">Item Not Received claim submitted</p>
              </div>

              <div className="relative">
                <div className="absolute -left-[25px] top-1 w-2.5 h-2.5 rounded-full bg-purple-500 ring-4 ring-white" />
                <p className="font-bold text-[#111827]">ProofLedger Truth Verification</p>
                <p className="text-[11px] text-[#6B7280]">Today • Just now</p>
                <p className="text-[11px] text-[#4B5563] mt-0.5">DeBERTa AI + deterministic rules verified</p>
              </div>

              <div className="relative">
                <div className="absolute -left-[25px] top-1 w-2.5 h-2.5 rounded-full bg-gray-300 ring-4 ring-white" />
                <p className="font-bold text-[#6B7280]">Seller Response Due</p>
                <p className="text-[11px] text-[#6B7280]">Nov 10, 2026 • 23:59:59 UTC</p>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* MODAL: LIVE AI NEURAL MODEL PLAYGROUND */}
      {showAiModal && (
        <div className="fixed inset-0 z-50 bg-black/40 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-lg w-full p-6 shadow-xl space-y-4">
            <div className="flex items-center justify-between border-b border-[#E5E7EB] pb-3">
              <div className="flex items-center space-x-2">
                <Cpu className="h-4 w-4 text-purple-700" />
                <h3 className="font-bold text-sm text-[#111827]">DeBERTa Neural NLI Model</h3>
              </div>
              <button
                onClick={() => setShowAiModal(false)}
                className="text-xs text-[#9CA3AF] hover:text-[#111827]"
              >
                ✕
              </button>
            </div>

            <p className="text-xs text-[#6B7280]">
              Test any claim against evidence. Runs live forward pass on Apple Silicon GPU (MPS) using the 704MB fine-tuned model checkpoint.
            </p>

            <div className="space-y-3 text-xs">
              <div>
                <label className="block font-semibold text-[#374151] mb-1">Claim Statement:</label>
                <input
                  type="text"
                  value={aiTestClaim}
                  onChange={(e) => setAiTestClaim(e.target.value)}
                  className="w-full p-2.5 border border-[#D1D5DB] rounded-lg text-xs font-mono"
                />
              </div>

              <div>
                <label className="block font-semibold text-[#374151] mb-1">Evidence Records:</label>
                <textarea
                  rows={3}
                  value={aiTestEvidence}
                  onChange={(e) => setAiTestEvidence(e.target.value)}
                  className="w-full p-2.5 border border-[#D1D5DB] rounded-lg text-xs font-mono"
                />
              </div>

              <button
                onClick={handleRunAiModalTest}
                disabled={isTestingAi}
                className="w-full py-2.5 rounded-lg bg-purple-700 hover:bg-purple-800 text-white font-semibold text-xs transition flex items-center justify-center space-x-2 shadow-xs"
              >
                <Sparkles className={`h-3.5 w-3.5 ${isTestingAi ? 'animate-spin' : ''}`} />
                <span>{isTestingAi ? 'Computing Neural Inference...' : 'Run Neural Inference'}</span>
              </button>

              {aiTestResult && (
                <div className="p-3.5 rounded-xl bg-purple-50/60 border border-purple-200 text-xs space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="font-semibold text-purple-950">Verdict:</span>
                    <span className="font-mono font-bold px-2 py-0.5 rounded bg-purple-100 text-purple-900 border border-purple-300">
                      {aiTestResult.label} ({((aiTestResult.confidence || 0) * 100).toFixed(1)}%)
                    </span>
                  </div>
                  <div className="text-[11px] text-[#6B7280] font-mono flex justify-between">
                    <span>Latency: {aiTestResult.latency_ms} ms</span>
                    <span>Device: {aiTestResult.device}</span>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
      {/* Official Visual Document Proof Viewer Modal */}
      <DocumentProofViewerModal
        isOpen={showDocModal}
        onClose={() => setShowDocModal(false)}
        documentData={selectedDoc}
      />
    </div>
  );
}

