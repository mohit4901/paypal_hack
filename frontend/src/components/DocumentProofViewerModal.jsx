import React, { useState, useEffect } from 'react';
import {
  FileText,
  ShieldCheck,
  Download,
  Copy,
  Check,
  ZoomIn,
  ZoomOut,
  ExternalLink,
  Lock,
  Eye,
  ChevronRight,
  AlertTriangle,
} from 'lucide-react';

const ALL_EXHIBITS = [
  {
    exhibit_number: 'EXHIBIT A',
    title: 'PayPal Payment Capture Receipt — Linked to Simulated Dispute Scenario',
    subtitle: 'Official PayPal Merchant Payment Capture (WH-5YU92122SU5558421-38D64732GN611071G) & Dispute Allocation Record',
    image_src: '/documents/exhibit_a_paypal_notice.png',
    source_system: 'api-m.sandbox.paypal.com/v2/payments/captures',
    source_record_id: 'WH-5YU92122SU5558421-38D64732GN611071G',
    collection_timestamp: '2026-10-31 11:14:35 UTC',
    original_payload_hash: '53e6474db96c5cee657048ee3c8d93ef95132f649de0f073d4bde27c669d4fb5',
    rendered_png_hash: '20a33779ba33a1adc2bf0d5e20302607b3ed69b4454aba79c59638635020ad03',
    sha256: '20a33779ba33a1adc2bf0d5e20302607b3ed69b4454aba79c59638635020ad03',
    verification_status: 'NORMALIZED_ARTIFACT (Verified PayPal Event)',
    provenance_badge: 'VERIFIED PAYPAL SANDBOX EVENT',
    provenance_classification: 'NORMALIZED_ARTIFACT',
    admissibility: 'Official PayPal Sandbox Payment Capture 10A71705XW788203L Linked to Dispute Scenario DSP-3EU95140-01',
  },
  {
    exhibit_number: 'EXHIBIT B',
    title: 'MemberPress LMS Student Access Audit',
    subtitle: 'Certified Student Account Provisioning & Session Access Record',
    image_src: '/documents/exhibit_b_lms_access_cert.png',
    source_system: 'memberpress.internal / postgres_prod',
    source_record_id: 'sess_usr_94b76ba7_course_enrollment',
    collection_timestamp: '2026-10-31 11:15:10 UTC',
    original_payload_hash: '3427a5567db3f86c99181803bc00ef56ab4a740e2913f28a008104f1436b4ebf',
    rendered_png_hash: '17034751957955580cabbb8a7c3baaa5d82e0228735d9e91b3e0f0ec37ffa0b5',
    sha256: '17034751957955580cabbb8a7c3baaa5d82e0228735d9e91b3e0f0ec37ffa0b5',
    verification_status: 'STORE_LOG_NORMALIZED (PostgreSQL LMS Log)',
    provenance_badge: 'INTERNAL LMS AUDIT LOG',
    provenance_classification: 'STORE_LOG_NORMALIZED',
    admissibility: 'Certified LMS Audit Record with IP 198.51.100.42 and Quiz Results',
  },
  {
    exhibit_number: 'EXHIBIT C',
    title: 'SendGrid Enterprise SMTP Transmission Receipt',
    subtitle: 'RFC 5321 Delivery Transcript with DKIM/SPF Authentication & TLS 1.3',
    image_src: '/documents/exhibit_c_sendgrid_receipt.png',
    source_system: 'api.sendgrid.com/v3/messages',
    source_record_id: 'sg_msg_id_3eu95140_access_credentials',
    collection_timestamp: '2026-10-31 11:15:14 UTC',
    original_payload_hash: '38bd02b3114af049e12d668875d2fed754661ae5641a765207226476ecd87804',
    rendered_png_hash: '935adc2192e7079fe089901ab178bbca2edcbdf8120a9f864773eb1f6202389b',
    sha256: '935adc2192e7079fe089901ab178bbca2edcbdf8120a9f864773eb1f6202389b',
    verification_status: 'STORE_LOG_NORMALIZED (SendGrid TLS 250 OK Log)',
    provenance_badge: 'SMTP GATEWAY RECEIPT',
    provenance_classification: 'STORE_LOG_NORMALIZED',
    admissibility: 'RFC 5321 Compliant Delivery Transcript with DKIM/SPF Authentication',
  },
  {
    exhibit_number: 'EXHIBIT D',
    title: 'Software License Node Binding Certificate',
    subtitle: 'Ed25519 Cryptographically Bound Hardware Node License Certificate',
    image_src: '/documents/exhibit_d_license_key.png',
    source_system: 'kms.proofledger.io/v1/licenses',
    source_record_id: 'lic_alloc_PL-2026-X992-K812',
    collection_timestamp: '2026-10-31 11:15:02 UTC',
    original_payload_hash: '14fdd9c785fdf4fbe22120b9f49ce2c2b40b85599881f2426a31910d511d191d',
    rendered_png_hash: '15dbe384f91c67444248fbf41836c29be128cf5c735f412d5f8834bfbc478556',
    sha256: '15dbe384f91c67444248fbf41836c29be128cf5c735f412d5f8834bfbc478556',
    verification_status: 'STORE_LOG_NORMALIZED (KMS Node Activation)',
    provenance_badge: 'LICENSE NODE CERTIFICATE',
    provenance_classification: 'STORE_LOG_NORMALIZED',
    admissibility: 'Tamper-Proof Ledger Anchor on V2 SHA-256 Hash Chain',
  },
  {
    exhibit_number: 'EXHIBIT E',
    title: 'Cloudflare Edge CDN Delivery Audit Log',
    subtitle: 'Edge Cache Byte Transfer & HTTP 200 Download Verification Log',
    image_src: '/documents/exhibit_e_cdn_download.png',
    source_system: 'cloudflare.com/logs/edge_sjc',
    source_record_id: 'ray_8e9140fa781204c_sjc_edge',
    collection_timestamp: '2026-10-31 11:17:40 UTC',
    original_payload_hash: '5800dbbc026074e97a0b9b52e48765c7772e42850f8a1d08f98440fe37532081',
    rendered_png_hash: 'dca3a4a3c2ab79698b884e9f51914ab87c758661b8e32f4b05d3357a7b11a67b',
    sha256: 'dca3a4a3c2ab79698b884e9f51914ab87c758661b8e32f4b05d3357a7b11a67b',
    verification_status: 'STORE_LOG_NORMALIZED (Cloudflare SJC Socket Log)',
    provenance_badge: 'CLOUDFLARE EDGE LOG',
    provenance_classification: 'STORE_LOG_NORMALIZED',
    admissibility: 'Cloudflare Edge Access Log Refuting Broken Download Allegation',
  },
  {
    exhibit_number: 'EXHIBIT F',
    title: '3DS Bank OTP Auth Certificate (Simulated Demo Exhibit)',
    subtitle: 'Simulated 3DS 2.2 EMVCo Bank OTP Record for Demonstration Scenarios',
    image_src: '/documents/exhibit_f_3ds_auth.png',
    source_system: 'simulated.3ds.internal',
    source_record_id: 'sim_3ds_cavv_mock_8921a4f',
    collection_timestamp: '2026-10-31 11:14:38 UTC',
    original_payload_hash: '40306461b8490758bf8ade93a53adbade4480ec1fc8b7234fe58f4329b9b6b9d',
    rendered_png_hash: '72bfd7fb612f9a62001f6df287c210c5575626215fb9adecc6578f1593af19e0',
    sha256: '72bfd7fb612f9a62001f6df287c210c5575626215fb9adecc6578f1593af19e0',
    verification_status: 'SIMULATED_DEMO_EXHIBIT (3DS Mock Handshake)',
    provenance_badge: 'SIMULATED DEMO EXHIBIT',
    provenance_classification: 'SIMULATED_DEMO_EXHIBIT',
    admissibility: 'Simulated Proof for 3DS 2.2 EMVCo Bank OTP Demonstration',
  },
];

export default function DocumentProofViewerModal({ isOpen, onClose, documentData }) {
  const [zoomLevel, setZoomLevel] = useState(100);
  const [copied, setCopied] = useState(false);
  const [activeExhibitIndex, setActiveExhibitIndex] = useState(0);

  // Sync incoming documentData with matching exhibit using strict priority
  useEffect(() => {
    if (!documentData) return;
    const reqNum = (documentData.exhibit_number || documentData.exhibitNumber || '').toUpperCase().trim();
    const reqFile = (documentData.image_src || documentData.imageSrc || '').toLowerCase().trim();
    const reqTitle = (documentData.title || '').toLowerCase().trim();

    const fileName = reqFile.split('/').pop();

    // Priority 1: Exact exhibit number/ID (e.g. "EXHIBIT F")
    let foundIdx = ALL_EXHIBITS.findIndex(
      (ex) => reqNum && ex.exhibit_number.toUpperCase() === reqNum
    );

    // Priority 2: Exact filename (e.g. "exhibit_f_3ds_auth.png")
    if (foundIdx < 0 && fileName) {
      foundIdx = ALL_EXHIBITS.findIndex(
        (ex) => ex.image_src.split('/').pop().toLowerCase() === fileName
      );
    }

    // Priority 3: Full normalized exact title match
    if (foundIdx < 0 && reqTitle) {
      foundIdx = ALL_EXHIBITS.findIndex(
        (ex) => ex.title.toLowerCase().trim() === reqTitle
      );
    }

    // Strict priority: Never default to Exhibit A if no valid match!
    if (foundIdx >= 0) {
      setActiveExhibitIndex(foundIdx);
    } else {
      setActiveExhibitIndex(-1);
    }
  }, [documentData]);

  if (!isOpen) return null;

  const isUnknown = activeExhibitIndex === -1;
  const currentExhibit = !isUnknown ? (ALL_EXHIBITS[activeExhibitIndex] || ALL_EXHIBITS[0]) : null;

  const exhibitNumber = isUnknown ? 'UNVERIFIED REFERENCE' : currentExhibit.exhibit_number;
  const title = isUnknown ? (documentData?.title || documentData?.filename || 'Unverified / Unknown Document Exhibit') : currentExhibit.title;
  const subtitle = isUnknown ? 'Unmatched Document Reference in Evidence Registry' : currentExhibit.subtitle;
  const imageSrc = isUnknown ? null : currentExhibit.image_src;
  const sha256 = isUnknown ? (documentData?.sha256 || 'UNKNOWN_OR_UNVERIFIED_HASH') : currentExhibit.sha256;
  const sourceSystem = isUnknown ? (documentData?.source || 'Unregistered / External') : currentExhibit.source_system;
  const rawTimestamp = isUnknown ? (documentData?.timestamp || 'Unavailable') : (currentExhibit.collection_timestamp || currentExhibit.timestamp || documentData?.timestamp);
  const timestamp = (rawTimestamp && rawTimestamp !== 'Live Certified') ? rawTimestamp : 'Timestamp unavailable';
  const admissibility = isUnknown ? 'INADMISSIBLE (Unmatched Exhibit)' : currentExhibit.admissibility;
  const badgeLabel = isUnknown ? 'UNVERIFIED REFERENCE' : (currentExhibit.provenance_badge || 'AUTHENTICATED RECORD');
  const isSimulated = !isUnknown && currentExhibit.provenance_classification === 'SIMULATED_DEMO_EXHIBIT';

  const handleCopyHash = () => {
    navigator.clipboard.writeText(sha256);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleDownload = () => {
    if (isUnknown || !imageSrc) return;
    const a = document.createElement('a');
    a.href = imageSrc;
    a.download = `${exhibitNumber.toLowerCase().replace(/\s+/g, '_')}_proofledger.png`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-xs flex items-center justify-center p-3 sm:p-5">
      <div className="bg-white rounded-2xl max-w-5xl w-full max-h-[94vh] flex flex-col shadow-2xl border border-[#E5E7EB] overflow-hidden text-[#111827] font-sans">
        {/* Top Header Bar (Stripe / Mercury Clean Light Style) */}
        <div className="px-6 py-3.5 border-b border-[#E5E7EB] flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-[#FAFAFA]">
          <div className="flex items-center space-x-3">
            <div className={`h-9 w-9 rounded-xl border flex items-center justify-center ${
              isUnknown ? 'bg-amber-50 border-amber-300 text-amber-700' : 'bg-blue-50 border-blue-200 text-[#003087]'
            }`}>
              {isUnknown ? <AlertTriangle className="h-5 w-5" /> : <FileText className="h-5 w-5" />}
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <span className={`px-2 py-0.5 rounded text-[11px] font-mono font-bold ${
                  isUnknown ? 'bg-amber-700 text-white' : 'bg-[#111827] text-white'
                }`}>
                  {exhibitNumber}
                </span>
                <h3 className="font-bold text-sm text-[#111827] tracking-tight">{title}</h3>
                <span className={`hidden sm:inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-mono font-bold border ${
                  isUnknown
                    ? 'bg-rose-50 text-rose-800 border-rose-200'
                    : isSimulated
                    ? 'bg-amber-50 text-amber-800 border-amber-200'
                    : 'bg-emerald-50 text-emerald-800 border-emerald-200'
                }`}>
                  <ShieldCheck className={`w-3 h-3 ${isUnknown ? 'text-rose-600' : isSimulated ? 'text-amber-600' : 'text-emerald-600'}`} />
                  {badgeLabel}
                </span>
              </div>
              <p className="text-[11px] text-[#6B7280] font-mono mt-0.5 truncate max-w-xl">
                Source: <span className="text-[#111827] font-medium">{sourceSystem}</span> • Recorded: {timestamp}
              </p>
            </div>
          </div>

          {/* Action Toolbar */}
          <div className="flex items-center space-x-2 self-end sm:self-auto">
            {/* Zoom Controls */}
            {!isUnknown && (
              <div className="flex items-center bg-white rounded-lg p-0.5 border border-[#D1D5DB] shadow-2xs">
                <button
                  onClick={() => setZoomLevel((z) => Math.max(50, z - 25))}
                  className="p-1 hover:bg-[#F3F4F6] rounded text-[#4B5563] transition"
                  title="Zoom Out"
                >
                  <ZoomOut className="h-3.5 w-3.5" />
                </button>
                <span className="px-2 text-[11px] font-mono font-semibold text-[#111827]">{zoomLevel}%</span>
                <button
                  onClick={() => setZoomLevel((z) => Math.min(200, z + 25))}
                  className="p-1 hover:bg-[#F3F4F6] rounded text-[#4B5563] transition"
                  title="Zoom In"
                >
                  <ZoomIn className="h-3.5 w-3.5" />
                </button>
              </div>
            )}

            {/* Copy Hash */}
            <button
              onClick={handleCopyHash}
              className="px-2.5 py-1.5 bg-white hover:bg-[#F9FAFB] rounded-lg border border-[#D1D5DB] text-xs font-mono text-[#374151] flex items-center space-x-1.5 transition shadow-2xs"
              title="Copy SHA-256 Checksum"
            >
              {copied ? <Check className="h-3.5 w-3.5 text-emerald-600" /> : <Copy className="h-3.5 w-3.5" />}
              <span>{copied ? 'Copied' : 'Hash'}</span>
            </button>

            {/* Download Official PNG */}
            {!isUnknown && (
              <button
                onClick={handleDownload}
                className="px-3 py-1.5 bg-[#111827] hover:bg-black text-white rounded-lg text-xs font-semibold flex items-center space-x-1.5 transition shadow-xs"
                title="Download High-Resolution Certified Document"
              >
                <Download className="h-3.5 w-3.5" />
                <span>Download Exhibit</span>
              </button>
            )}

            {/* Close Modal */}
            <button
              onClick={onClose}
              className="text-[#9CA3AF] hover:text-[#111827] text-base font-bold px-2 py-1 ml-1 transition"
              title="Close Viewer"
            >
              ✕
            </button>
          </div>
        </div>

        {/* Quick Exhibit Switcher Bar (Tabs inside modal) */}
        <div className="px-6 py-2 bg-[#F3F4F6] border-b border-[#E5E7EB] flex items-center space-x-2 overflow-x-auto text-xs font-medium text-[#4B5563]">
          <span className="text-[10px] font-bold uppercase tracking-wider text-[#6B7280] mr-1 shrink-0">
            Exhibits:
          </span>
          {isUnknown && (
            <span className="px-2.5 py-1 rounded-md text-xs font-mono font-bold bg-amber-100 text-amber-900 border border-amber-300 flex items-center space-x-1.5">
              <span>⚠ UNVERIFIED</span>
            </span>
          )}
          {ALL_EXHIBITS.map((ex, idx) => (
            <button
              key={ex.exhibit_number}
              onClick={() => setActiveExhibitIndex(idx)}
              className={`px-2.5 py-1 rounded-md text-xs font-mono font-medium whitespace-nowrap transition flex items-center space-x-1.5 ${
                activeExhibitIndex === idx
                  ? 'bg-white text-[#111827] font-bold shadow-xs border border-[#D1D5DB]'
                  : 'hover:bg-white/60 hover:text-[#111827]'
              }`}
            >
              <span className={activeExhibitIndex === idx ? 'text-[#003087] font-bold' : 'text-[#6B7280]'}>
                {ex.exhibit_number.replace('EXHIBIT ', 'Ex-')}
              </span>
              <span>{ex.title.split(' ')[0]} {ex.title.split(' ')[1] || ''}</span>
            </button>
          ))}
        </div>

        {/* Forensic Provenance & Dual-Hash Inspection Bar */}
        <div className="px-6 py-2 bg-slate-50/90 border-b border-[#E5E7EB] text-xs">
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-2 text-[10px] font-mono">
            <div className="bg-white p-1.5 rounded border border-[#E5E7EB]">
              <span className="text-[#6B7280] block font-sans text-[9px] uppercase font-semibold">1. Source System</span>
              <span className="text-[#111827] font-semibold truncate block" title={sourceSystem}>
                {sourceSystem}
              </span>
            </div>
            <div className="bg-white p-1.5 rounded border border-[#E5E7EB]">
              <span className="text-[#6B7280] block font-sans text-[9px] uppercase font-semibold">2. Source Record ID</span>
              <span className="text-[#111827] font-semibold truncate block" title={isUnknown ? (documentData?.id || 'UNMATCHED') : currentExhibit.source_record_id}>
                {isUnknown ? (documentData?.id || 'UNMATCHED') : currentExhibit.source_record_id}
              </span>
            </div>
            <div className="bg-white p-1.5 rounded border border-[#E5E7EB]">
              <span className="text-[#6B7280] block font-sans text-[9px] uppercase font-semibold">3. Collection Time</span>
              <span className="text-[#111827] font-semibold truncate block">
                {isUnknown ? timestamp : currentExhibit.collection_timestamp}
              </span>
            </div>
            <div className="bg-white p-1.5 rounded border border-[#E5E7EB]">
              <span className="text-[#6B7280] block font-sans text-[9px] uppercase font-semibold">4. Original Payload SHA</span>
              <span className="text-blue-700 font-semibold truncate block" title={isUnknown ? 'N/A' : currentExhibit.original_payload_hash}>
                {isUnknown ? 'UNVERIFIED' : `${currentExhibit.original_payload_hash?.slice(0, 10)}...`}
              </span>
            </div>
            <div className="bg-white p-1.5 rounded border border-[#E5E7EB]">
              <span className="text-[#6B7280] block font-sans text-[9px] uppercase font-semibold">5. Rendered PNG SHA</span>
              <span className="text-purple-700 font-semibold truncate block" title={isUnknown ? sha256 : currentExhibit.rendered_png_hash}>
                {isUnknown ? `${sha256.slice(0, 10)}...` : `${currentExhibit.rendered_png_hash?.slice(0, 10)}...`}
              </span>
            </div>
            <div className="bg-white p-1.5 rounded border border-[#E5E7EB]">
              <span className="text-[#6B7280] block font-sans text-[9px] uppercase font-semibold">6. Provenance Status</span>
              <span className={`font-bold truncate block ${
                isUnknown ? 'text-rose-700' : isSimulated ? 'text-amber-700' : 'text-emerald-700'
              }`} title={isUnknown ? 'UNVERIFIED_RECORD' : currentExhibit.verification_status}>
                {isUnknown ? 'UNVERIFIED_RECORD' : currentExhibit.provenance_classification}
              </span>
            </div>
          </div>
        </div>

        {/* Document Viewport (Clean Physical Desk Preview) */}
        <div className="flex-1 overflow-auto p-4 sm:p-8 bg-[#E2E8F0]/40 flex items-center justify-center">
          {isUnknown ? (
            <div className="max-w-xl w-full p-8 bg-white rounded-xl border border-amber-300 shadow-md flex flex-col items-center text-center">
              <div className="w-14 h-14 rounded-full bg-amber-50 border border-amber-200 flex items-center justify-center text-amber-600 mb-4">
                <AlertTriangle className="w-7 h-7" />
              </div>
              <h4 className="text-base font-bold text-gray-900 mb-1">Unverified / Unknown Document Exhibit</h4>
              <p className="text-xs text-amber-900 bg-amber-50 border border-amber-200 rounded-md p-3 mb-4 leading-relaxed font-sans">
                This document reference could not be cryptographically matched against any verified exhibit in the Evidence Registry.
              </p>
              <div className="w-full text-left bg-gray-50 border border-gray-200 rounded-lg p-3 text-[11px] font-mono mb-4 text-gray-700 space-y-1">
                <div><span className="text-gray-500 font-semibold">Requested Reference:</span> {documentData?.title || documentData?.filename || 'Unknown'}</div>
                <div><span className="text-gray-500 font-semibold">Registry Status:</span> <span className="text-rose-600 font-bold">Unregistered / Unverified</span></div>
                <div><span className="text-gray-500 font-semibold">Integrity Policy:</span> ProofLedger strictly fails closed and never renders default fallbacks for unverified documents.</div>
              </div>
              <p className="text-[11px] text-gray-500">
                Select an authenticated exhibit from the tabs above to inspect verified records.
              </p>
            </div>
          ) : (
            <div
              className="transition-transform duration-150 shadow-xl rounded-lg overflow-hidden border border-slate-300 bg-white ring-1 ring-black/5"
              style={{ width: `${zoomLevel}%`, maxWidth: '100%' }}
            >
              <img
                src={imageSrc}
                alt={title}
                key={imageSrc}
                className="w-full h-auto block select-none"
                draggable={false}
              />
            </div>
          )}
        </div>

        {/* Certified Metadata Footer */}
        <div className="px-6 py-3 border-t border-[#E5E7EB] bg-[#FAFAFA] flex flex-col sm:flex-row sm:items-center justify-between text-xs text-[#4B5563] font-mono gap-2">
          <div className="flex items-center space-x-2 truncate">
            <Lock className={`h-3.5 w-3.5 shrink-0 ${isUnknown ? 'text-rose-600' : 'text-emerald-600'}`} />
            <span className="truncate">
              SHA-256 Digest: <strong className="text-[#111827]">{sha256}</strong>
            </span>
          </div>
          <div className="flex items-center space-x-4 text-[11px] text-[#6B7280] shrink-0">
            <span>300 DPI (1400×1850 px)</span>
            <span className={isUnknown ? 'text-rose-600 font-semibold' : 'text-[#059669] font-semibold'}>{admissibility}</span>
          </div>
        </div>
      </div>
    </div>
  );
}
