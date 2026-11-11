import React, { useState } from 'react';
import {
  FolderOpen,
  Plus,
  CheckCircle2,
  AlertTriangle,
  ArrowRight,
  Database,
  Mail,
  Download,
  Key,
  Layers,
  X,
  FileCheck2,
} from 'lucide-react';

export default function EvidenceWorkspaceTab({
  evidence,
  onAddEvidence,
  onRemoveEvidence,
  onProceedToClaims,
  currentOrderRef = '3EU95140LR696653G',
}) {
  const [showAddModal, setShowAddModal] = useState(false);
  const [sourceType, setSourceType] = useState('course_platform');
  const [eventType, setEventType] = useState('ACCESS_GRANTED');
  const [txRef, setTxRef] = useState(currentOrderRef);
  const [content, setContent] = useState('');
  const [validationError, setValidationError] = useState('');

  const handleCreate = (e) => {
    e.preventDefault();
    if (!content.trim()) {
      setValidationError('Record content cannot be empty.');
      return;
    }
    // Strict transaction linkage check:
    if (txRef.trim() !== currentOrderRef) {
      setValidationError(
        `Linkage Failure: Record references '${txRef}', which does not match active dispute order '${currentOrderRef}'. Records from other transactions cannot be attached.`
      );
      return;
    }

    const newRecord = {
      evidence_id: `EV-MANUAL-${Date.now().toString().slice(-6)}`,
      source_type: sourceType,
      event_type: eventType,
      timestamp: new Date().toISOString(),
      transaction_ref: txRef.trim(),
      content: content.trim(),
      is_verified_source: true,
    };

    onAddEvidence(newRecord);
    setContent('');
    setValidationError('');
    setShowAddModal(false);
  };

  const hasDownloadLog = evidence.some(
    (e) => e.content.toLowerCase().includes('download') || e.event_type === 'DOWNLOAD_COMPLETED'
  );

  return (
    <div className="space-y-6 font-sans">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-[#E5E7EB]">
        <div>
          <h1 className="text-xl font-bold text-[#111827] tracking-tight">
            Evidence Workspace
          </h1>
          <p className="text-xs text-[#6B7280] mt-0.5">
            Add records showing what happened after customer payment for Order <code className="text-[#111827] font-bold">{currentOrderRef}</code>.
          </p>
        </div>

        <div className="flex items-center space-x-2">
          <button
            onClick={() => setShowAddModal(true)}
            className="px-3 py-2 rounded-lg border border-[#D1D5DB] hover:bg-[#F9FAFB] text-xs font-medium text-[#111827] flex items-center space-x-1.5 transition-colors"
          >
            <Plus className="h-3.5 w-3.5" />
            <span>Add Evidence Record</span>
          </button>
          <button
            onClick={onProceedToClaims}
            className="px-4 py-2 rounded-lg bg-[#111827] hover:bg-[#1F2937] text-white text-xs font-medium flex items-center space-x-1.5 shadow-sm transition-colors"
          >
            <span>Proceed to Claim Builder</span>
            <ArrowRight className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>

      {/* Critical Delivery Guidance Banner */}
      <div className="p-4 rounded-xl border border-[#E5E7EB] bg-[#F9FAFB] text-xs space-y-2">
        <div className="flex items-center space-x-2 font-semibold text-[#111827]">
          <FileCheck2 className="h-4 w-4 text-[#111827]" />
          <span>Strict Transaction & Provenance Policy</span>
        </div>
        <p className="text-[#4B5563] text-[11px] leading-relaxed">
          Every attached record must explicitly corroborate this specific order (<code className="font-mono text-[#111827]">{currentOrderRef}</code>).
          Records belonging to other transactions are rejected by the deterministic engine to prevent false representation.
        </p>
      </div>

      {/* Missing Record Notice */}
      {!hasDownloadLog && (
        <div className="p-3.5 rounded-lg border border-[#FDE68A] bg-[#FFFBEB] text-xs flex items-center justify-between">
          <div className="flex items-center space-x-2 text-[#92400E]">
            <AlertTriangle className="h-4 w-4 shrink-0 text-[#D97706]" />
            <span>
              <strong>Note on Digital Delivery:</strong> No explicit file download completion log found.
              If the buyer claims non-receipt, access provision logs prove availability, but do not prove download completion.
            </span>
          </div>
        </div>
      )}

      {/* Connected Evidence Records List */}
      <div className="space-y-3">
        <div className="flex items-center justify-between text-xs">
          <h3 className="font-bold text-[#111827] uppercase tracking-wider text-[11px]">
            Connected Evidence Records ({evidence.length})
          </h3>
          <span className="text-[#6B7280]">All records validated against order ID</span>
        </div>

        <div className="space-y-3">
          {evidence.map((ev) => (
            <div
              key={ev.evidence_id}
              className="bg-white p-4 rounded-xl border border-[#E5E7EB] shadow-xs space-y-2 hover:border-[#D1D5DB] transition-colors"
            >
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                <div className="flex items-center space-x-2">
                  <span className="font-mono font-bold text-xs text-[#111827]">
                    {ev.evidence_id}
                  </span>
                  <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-[#F3F4F6] text-[#4B5563] border border-[#E5E7EB]">
                    {ev.source_type}
                  </span>
                  <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-emerald-50 text-emerald-700 border border-emerald-200">
                    {ev.event_type}
                  </span>
                </div>

                <div className="flex items-center space-x-3 text-[11px] text-[#6B7280]">
                  <span>{ev.timestamp}</span>
                  {evidence.length > 2 && (
                    <button
                      onClick={() => onRemoveEvidence(ev.evidence_id)}
                      className="text-[#9CA3AF] hover:text-[#EF4444]"
                      title="Remove record"
                    >
                      <X className="h-3.5 w-3.5" />
                    </button>
                  )}
                </div>
              </div>

              <div className="bg-[#F9FAFB] p-2.5 rounded-lg border border-[#E5E7EB] font-mono text-[11px] text-[#374151] break-all leading-relaxed">
                {ev.content}
              </div>

              <div className="flex items-center justify-between text-[11px] text-[#6B7280] pt-1 border-t border-[#F3F4F6]">
                <span>Order Reference: <strong className="text-[#111827]">{ev.transaction_ref}</strong></span>
                <span className="text-[#059669] flex items-center space-x-1 font-medium">
                  <CheckCircle2 className="h-3 w-3" />
                  <span>Linkage Confirmed</span>
                </span>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Add Evidence Modal */}
      {showAddModal && (
        <div className="fixed inset-0 z-50 bg-black/50 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white border border-[#E5E7EB] rounded-2xl w-full max-w-lg shadow-2xl p-6 space-y-4">
            <div className="flex items-center justify-between border-b border-[#E5E7EB] pb-3">
              <h3 className="font-bold text-sm text-[#111827]">Add Delivery Evidence Record</h3>
              <button
                onClick={() => {
                  setShowAddModal(false);
                  setValidationError('');
                }}
                className="text-[#9CA3AF] hover:text-[#111827]"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            {validationError && (
              <div className="p-3 rounded-lg border border-[#FECDD3] bg-[#FFF1F2] text-[#9F1239] text-xs flex items-start space-x-2">
                <AlertTriangle className="h-4 w-4 shrink-0 mt-0.5" />
                <span>{validationError}</span>
              </div>
            )}

            <form onSubmit={handleCreate} className="space-y-3 text-xs">
              <div>
                <label className="block font-medium text-[#374151] mb-1">Source Platform</label>
                <select
                  value={sourceType}
                  onChange={(e) => setSourceType(e.target.value)}
                  className="w-full px-3 py-2 border border-[#D1D5DB] rounded-lg text-xs bg-white focus:outline-none focus:border-[#111827]"
                >
                  <option value="course_platform">Course Learning Platform (MemberPress / Teachable)</option>
                  <option value="email_delivery">Email Service (SendGrid / Postmark)</option>
                  <option value="download_server">AWS S3 / Download Server</option>
                  <option value="license_manager">License Key Issuer</option>
                  <option value="custom_support">Customer Support Chat Transcript</option>
                </select>
              </div>

              <div>
                <label className="block font-medium text-[#374151] mb-1">Event Type</label>
                <input
                  type="text"
                  value={eventType}
                  onChange={(e) => setEventType(e.target.value)}
                  className="w-full px-3 py-2 border border-[#D1D5DB] rounded-lg text-xs focus:outline-none focus:border-[#111827]"
                  placeholder="e.g. ACCESS_GRANTED, DOWNLOAD_COMPLETED, EMAIL_OPENED"
                />
              </div>

              <div>
                <label className="block font-medium text-[#374151] mb-1">Associated Order Reference</label>
                <input
                  type="text"
                  value={txRef}
                  onChange={(e) => setTxRef(e.target.value)}
                  className="w-full px-3 py-2 border border-[#D1D5DB] rounded-lg text-xs font-mono focus:outline-none focus:border-[#111827]"
                  placeholder="Must match active dispute order reference"
                />
                <span className="text-[10px] text-[#6B7280] mt-0.5 block">
                  Active Dispute: <strong className="text-[#111827]">{currentOrderRef}</strong>
                </span>
              </div>

              <div>
                <label className="block font-medium text-[#374151] mb-1">Log / Raw Content</label>
                <textarea
                  rows="3"
                  value={content}
                  onChange={(e) => setContent(e.target.value)}
                  className="w-full px-3 py-2 border border-[#D1D5DB] rounded-lg text-xs font-mono focus:outline-none focus:border-[#111827]"
                  placeholder="e.g. Order 3EU95140LR696653G enrollment confirmed for sb-rcnwy53637793@personal.example.com"
                />
              </div>

              <div className="pt-3 border-t border-[#E5E7EB] flex items-center justify-end space-x-2">
                <button
                  type="button"
                  onClick={() => setShowAddModal(false)}
                  className="px-3 py-2 text-xs text-[#4B5563] hover:text-[#111827]"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 bg-[#111827] hover:bg-[#1F2937] text-white text-xs font-medium rounded-lg"
                >
                  Attach Record
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

