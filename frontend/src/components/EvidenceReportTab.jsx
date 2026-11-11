import React, { useState } from 'react';
import {
  FileText,
  Printer,
  CheckCircle2,
  Lock,
  ShieldCheck,
  AlertTriangle,
  ArrowLeft,
  Copy,
  Check,
} from 'lucide-react';
import { api } from '../api';

export default function EvidenceReportTab({
  packet,
  onBackToVerification,
  storeProfile,
}) {
  const [confirmed, setConfirmed] = useState(false);
  const [approving, setApproving] = useState(false);
  const [approvalReceipt, setApprovalReceipt] = useState(null);
  const [copiedDigest, setCopiedDigest] = useState(false);

  if (!packet) {
    return (
      <div className="bg-white p-12 rounded-xl border border-[#E5E7EB] text-center space-y-4 font-sans">
        <FileText className="h-8 w-8 text-[#9CA3AF] mx-auto" />
        <h3 className="font-bold text-sm text-[#111827]">No Evidence Packet Prepared</h3>
        <p className="text-xs text-[#6B7280]">
          Please run verification on your claims before viewing the report.
        </p>
        <button
          onClick={onBackToVerification}
          className="px-4 py-2 bg-[#111827] text-white text-xs font-medium rounded-lg"
        >
          Return to Verification
        </button>
      </div>
    );
  }

  const handleApprove = async () => {
    if (!confirmed) return;
    setApproving(true);
    try {
      const res = await api.approveDisputePacket('DSP-3EU95140-01', {
        seller_id: storeProfile?.storeName || 'seller_sandbox_01',
        packet_data: packet,
        signature_confirmed: true,
      });
      setApprovalReceipt(res);
    } catch (err) {
      alert(`Approval failed: ${err.message}`);
    } finally {
      setApproving(false);
    }
  };

  const copyDigest = (text) => {
    navigator.clipboard.writeText(text);
    setCopiedDigest(true);
    setTimeout(() => setCopiedDigest(false), 2000);
  };

  return (
    <div className="space-y-6 font-sans max-w-4xl mx-auto">
      {/* Top Controls (Hidden during Print) */}
      <div className="no-print flex items-center justify-between pb-4 border-b border-[#E5E7EB]">
        <button
          onClick={onBackToVerification}
          className="text-xs font-medium text-[#4B5563] hover:text-[#111827] flex items-center space-x-1"
        >
          <ArrowLeft className="h-3.5 w-3.5" />
          <span>Back to Findings</span>
        </button>

        <div className="flex items-center space-x-2">
          <button
            onClick={() => window.print()}
            className="px-3 py-1.5 rounded-lg border border-[#D1D5DB] hover:bg-[#F9FAFB] text-xs font-medium text-[#111827] flex items-center space-x-1.5 transition-colors"
          >
            <Printer className="h-3.5 w-3.5" />
            <span>Print / Save PDF</span>
          </button>
        </div>
      </div>

      {/* Human Approval Status Banner */}
      {approvalReceipt ? (
        <div className="no-print p-4 rounded-xl border border-emerald-300 bg-emerald-50 text-emerald-900 text-xs space-y-2">
          <div className="flex items-center justify-between">
            <span className="font-bold flex items-center space-x-1.5 text-sm">
              <CheckCircle2 className="h-4 w-4 text-[#059669]" />
              <span>Evidence Packet Approved & Cryptographically Sealed</span>
            </span>
            <span className="font-mono text-[10px] bg-emerald-100 text-emerald-800 px-2 py-0.5 rounded border border-emerald-200">
              {approvalReceipt.approval_id}
            </span>
          </div>
          <p className="text-[11px] text-emerald-800">
            Immutable SHA-256 seal generated. Ready for submission to PayPal Resolution Center.
          </p>
          <div className="font-mono text-[10px] bg-white p-2 rounded border border-emerald-200 break-all flex items-center justify-between">
            <span>SHA-256 Digest: {approvalReceipt.packet_sha256_digest}</span>
            <button
              onClick={() => copyDigest(approvalReceipt.packet_sha256_digest)}
              className="ml-2 text-emerald-700 hover:text-emerald-900"
            >
              {copiedDigest ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
            </button>
          </div>
        </div>
      ) : (
        <div className="no-print p-4 rounded-xl border border-[#FDE68A] bg-[#FFFBEB] text-xs space-y-3">
          <div className="flex items-center space-x-2 text-[#92400E] font-semibold">
            <Lock className="h-4 w-4 text-[#D97706]" />
            <span>Mandatory Seller Human Approval Required</span>
          </div>
          <p className="text-[11px] text-[#4B5563] leading-relaxed">
            PayPal rules require merchants to personally inspect and verify their dispute evidence before submission.
            Review the packet below and confirm authenticity.
          </p>
          <div className="flex items-center space-x-2 pt-1">
            <input
              type="checkbox"
              id="confirmCheck"
              checked={confirmed}
              onChange={(e) => setConfirmed(e.target.checked)}
              className="h-4 w-4 rounded border-[#D1D5DB] text-[#111827] focus:ring-[#111827]"
            />
            <label htmlFor="confirmCheck" className="text-xs font-medium text-[#111827] cursor-pointer">
              I confirm these source records are authentic and accurately reflect Order {packet.transaction_reference}.
            </label>
          </div>
          <button
            onClick={handleApprove}
            disabled={!confirmed || approving}
            className="px-4 py-2 bg-[#111827] hover:bg-[#1F2937] text-white text-xs font-medium rounded-lg disabled:opacity-40 transition-colors shadow-xs"
          >
            {approving ? 'Sealing Packet...' : 'Approve & Cryptographically Seal Packet'}
          </button>
        </div>
      )}

      {/* Formal Printable Document Card */}
      <div className="bg-white border border-[#E5E7EB] rounded-2xl p-8 shadow-sm space-y-8 text-xs text-[#111827] print:border-none print:shadow-none print:p-0">
        {/* Document Header */}
        <div className="flex justify-between items-start border-b border-[#E5E7EB] pb-6">
          <div>
            <span className="font-mono text-[10px] text-[#6B7280] uppercase tracking-wider block mb-1">
              PayPal Dispute Evidence Packet
            </span>
            <h2 className="text-xl font-bold tracking-tight text-[#111827]">
              Source-Grounded Evidence Report
            </h2>
            <p className="text-xs text-[#6B7280] mt-0.5">
              Merchant: {storeProfile?.storeName || 'Python Mastery Academy'}
            </p>
          </div>

          <div className="text-right font-mono text-[11px] space-y-0.5">
            <div>Packet ID: <strong className="text-[#111827]">{packet.packet_id}</strong></div>
            <div className="text-[#6B7280]">Date: {new Date(packet.generated_at).toLocaleDateString()}</div>
            <div className="text-[#059669] font-semibold">{packet.overall_readiness}</div>
          </div>
        </div>

        {/* Dispute & Transaction Context */}
        <div className="bg-[#F9FAFB] p-4 rounded-xl border border-[#E5E7EB] space-y-2">
          <h3 className="font-bold text-xs uppercase tracking-wider text-[#111827]">
            1. Dispute & Transaction Context
          </h3>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 font-mono text-[11px]">
            <div>
              <span className="text-[#6B7280] block text-[10px]">PAYPAL ORDER ID</span>
              <strong>{packet.transaction_reference}</strong>
            </div>
            <div>
              <span className="text-[#6B7280] block text-[10px]">PAYPAL CAPTURE ID</span>
              <strong>10A71705XW788203L</strong>
            </div>
            <div>
              <span className="text-[#6B7280] block text-[10px]">AMOUNT</span>
              <strong>5.00 USD</strong>
            </div>
            <div>
              <span className="text-[#6B7280] block text-[10px]">DISPUTE REASON</span>
              <span>Item Not Received</span>
            </div>
          </div>
        </div>

        {/* Assessed Claims Table */}
        <div className="space-y-3">
          <h3 className="font-bold text-xs uppercase tracking-wider text-[#111827]">
            2. Verified Dispute Claims
          </h3>
          <table className="w-full text-left text-xs border border-[#E5E7EB] rounded-lg overflow-hidden">
            <thead className="bg-[#F9FAFB] border-b border-[#E5E7EB] text-[10px] text-[#6B7280] uppercase tracking-wider">
              <tr>
                <th className="py-2.5 px-3">#</th>
                <th className="py-2.5 px-3">Factual Statement</th>
                <th className="py-2.5 px-3">Verdict</th>
                <th className="py-2.5 px-3">Citing Sources</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#E5E7EB]">
              {packet.verified_claims?.map((c, idx) => (
                <tr key={idx} className="hover:bg-[#F9FAFB]">
                  <td className="py-2.5 px-3 font-mono text-[#6B7280]">{idx + 1}</td>
                  <td className="py-2.5 px-3">
                    <span className="font-medium text-[#111827] block">{c.claim_text}</span>
                    <span className="text-[11px] text-[#6B7280]">{c.explanation}</span>
                  </td>
                  <td className="py-2.5 px-3">
                    <span
                      className={`px-2 py-0.5 rounded text-[10px] font-mono font-bold ${
                        c.verdict === 'SUPPORTED'
                          ? 'bg-emerald-50 text-emerald-800'
                          : c.verdict === 'INSUFFICIENT_EVIDENCE'
                          ? 'bg-amber-50 text-amber-800'
                          : 'bg-rose-50 text-rose-800'
                      }`}
                    >
                      {c.verdict}
                    </span>
                  </td>
                  <td className="py-2.5 px-3 font-mono text-[10px] text-[#4B5563]">
                    {c.supporting_sources?.join(', ') || 'None (Missing)'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Detailed Supporting Records */}
        <div className="space-y-3">
          <h3 className="font-bold text-xs uppercase tracking-wider text-[#111827]">
            3. Attached Source Evidence Telemetry
          </h3>
          <div className="space-y-2">
            {packet.evidence_records?.map((ev, eIdx) => (
              <div key={eIdx} className="p-3 bg-[#F9FAFB] rounded-lg border border-[#E5E7EB] space-y-1">
                <div className="flex justify-between font-mono text-[10px] text-[#6B7280]">
                  <span>{ev.evidence_id} • {ev.source_type}</span>
                  <span>{ev.timestamp}</span>
                </div>
                <div className="font-mono text-[11px] text-[#111827]">{ev.content}</div>
              </div>
            ))}
          </div>
        </div>

        {/* Mandatory Limitations & Legal Notice */}
        <div className="border-t border-[#E5E7EB] pt-4 text-[10px] text-[#6B7280] leading-relaxed space-y-1">
          <span className="font-bold text-[#111827] block">Legal & Verification Notice:</span>
          <p>{packet.disclaimer}</p>
        </div>

        {/* Cryptographic Seal Sign-Off Box */}
        <div className="border-t border-[#E5E7EB] pt-4 flex justify-between items-center text-[11px] text-[#4B5563]">
          <div>
            <span>Merchant Approval: </span>
            <strong className="text-[#111827]">
              {approvalReceipt ? 'Confirmed & Sealed' : 'Pending Sign-Off'}
            </strong>
          </div>
          <div className="font-mono text-[10px]">
            SHA-256 Digest: {packet.packet_sha256_digest?.slice(0, 24)}...
          </div>
        </div>
      </div>
    </div>
  );
}

