import React, { useState } from 'react';
import {
  AlertTriangle,
  Clock,
  ShieldCheck,
  CheckCircle2,
  ChevronRight,
  Filter,
  Search,
  ExternalLink,
  Plus,
  ArrowUpRight,
  RefreshCw,
  FileText,
  AlertCircle,
  HelpCircle,
  Check,
  Zap,
} from 'lucide-react';
import { api } from '../api';

export default function DisputeInboxTab({
  disputes = [],
  onSelectDispute,
  onOpenImportModal,
  loading = false,
  onRefresh,
  onSyncPayPal,
  onOpenPayPalInspector,
}) {
  const [filterTab, setFilterTab] = useState('ALL'); // 'ALL' | 'NEEDS_ACTION' | 'UNDER_REVIEW' | 'RESOLVED'
  const [searchQuery, setSearchQuery] = useState('');
  const [isGeneratingLive, setIsGeneratingLive] = useState(false);

  const handleGenerateLiveDispute = async () => {
    setIsGeneratingLive(true);
    try {
      const res = await api.generateLiveTransaction();
      if (onRefresh) await onRefresh();
      if (res && res.dispute_id && onSelectDispute) {
        onSelectDispute(res.dispute_id);
      }
    } catch (err) {
      alert(`Failed to generate live transaction: ${err.message}`);
    } finally {
      setIsGeneratingLive(false);
    }
  };

  // Counts for tab badges & dynamic metrics
  const totalCount = disputes.length;
  const liveCount = disputes.filter((d) => d.is_live_paypal_dispute).length;
  const needsActionCount = disputes.filter(
    (d) => d.status === 'WAITING_FOR_SELLER_RESPONSE' || d.evidence_readiness === 'NEEDS_ATTENTION'
  ).length;
  const underReviewCount = disputes.filter(
    (d) => d.status === 'UNDER_PAYPAL_REVIEW'
  ).length;
  const resolvedCount = disputes.filter(
    (d) => d.status === 'RESOLVED_SELLER_FAVOR' || d.status === 'RESOLVED'
  ).length;
  const totalDisputedRevenue = disputes
    .reduce((acc, d) => acc + (parseFloat(d.amount) || 0), 0)
    .toFixed(2);
  const earliestDeadline = disputes
    .filter((d) => d.seller_response_due_date)
    .sort((a, b) => new Date(a.seller_response_due_date) - new Date(b.seller_response_due_date))[0];

  // Filtered dispute list
  const filteredDisputes = disputes.filter((d) => {
    // Tab filter
    if (filterTab === 'NEEDS_ACTION' && d.status !== 'WAITING_FOR_SELLER_RESPONSE') {
      return false;
    }
    if (filterTab === 'UNDER_REVIEW' && d.status !== 'UNDER_PAYPAL_REVIEW') {
      return false;
    }
    if (filterTab === 'RESOLVED' && !d.status.startsWith('RESOLVED')) {
      return false;
    }

    // Search query
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      const matchId = (d.dispute_id || '').toLowerCase().includes(q);
      const matchTx = (d.transaction_reference || '').toLowerCase().includes(q);
      const matchProd = (d.product_name || '').toLowerCase().includes(q);
      const matchEmail = (d.buyer_email || '').toLowerCase().includes(q);
      const matchReason = (d.dispute_reason || '').toLowerCase().includes(q);
      return matchId || matchTx || matchProd || matchEmail || matchReason;
    }
    return true;
  });

  const getReasonLabel = (reason) => {
    if (!reason) return 'Item Not Received';
    if (reason === 'MERCHANDISE_OR_SERVICE_NOT_RECEIVED') return 'Item / Service Not Received';
    if (reason === 'UNAUTHORISED_TRANSACTION') return 'Unauthorised Payment';
    if (reason === 'INCORRECT_AMOUNT') return 'Incorrect Amount';
    return reason.replace(/_/g, ' ');
  };

  const getStatusBadge = (status) => {
    switch (status) {
      case 'WAITING_FOR_SELLER_RESPONSE':
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-amber-50 text-amber-800 border border-amber-200">
            <Clock className="w-3.5 h-3.5 text-amber-600" />
            Response Due
          </span>
        );
      case 'UNDER_PAYPAL_REVIEW':
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-blue-50 text-blue-800 border border-blue-200">
            <RefreshCw className="w-3.5 h-3.5 text-blue-600 animate-spin" />
            Under Review
          </span>
        );
      case 'RESOLVED_SELLER_FAVOR':
      case 'RESOLVED':
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-800 border border-emerald-200">
            <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
            Resolved (Won)
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-gray-100 text-gray-700">
            {status}
          </span>
        );
    }
  };

  return (
    <div className="space-y-6">
      {/* Top Header & Metrics Bar */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-[#111827]">Dispute Inbox</h1>
          <p className="text-sm text-[#4B5563] mt-0.5">
            Manage payment disputes, evaluate fulfillment evidence, and submit source-grounded responses to PayPal.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <span className="hidden xl:inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-[11px] font-mono bg-emerald-50 text-emerald-800 border border-emerald-200">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse"></span>
            api-m.sandbox.paypal.com
          </span>
          {onOpenPayPalInspector && (
            <button
              onClick={onOpenPayPalInspector}
              className="inline-flex items-center gap-1.5 px-3 py-2 border border-[#E5E7EB] rounded-lg text-xs font-medium text-[#374151] bg-white hover:bg-[#F9FAFB] transition shadow-xs"
            >
              <ShieldCheck className="w-3.5 h-3.5 text-blue-600" />
              Live PayPal JSON
            </button>
          )}
          <button
            onClick={onSyncPayPal || onRefresh}
            disabled={loading}
            className="inline-flex items-center gap-1.5 px-3 py-2 border border-[#E5E7EB] rounded-lg text-xs font-medium text-[#374151] bg-white hover:bg-[#F9FAFB] transition shadow-xs"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin text-black' : 'text-[#6B7280]'}`} />
            Sync PayPal Sandbox
          </button>
          <button
            onClick={handleGenerateLiveDispute}
            disabled={isGeneratingLive}
            className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-lg text-xs font-bold bg-emerald-600 text-white hover:bg-emerald-700 transition shadow-xs disabled:opacity-50"
          >
            <Zap className={`w-3.5 h-3.5 ${isGeneratingLive ? 'animate-spin' : ''}`} />
            {isGeneratingLive ? 'Creating...' : '⚡ Generate Live Nov 1 Dispute'}
          </button>
          <button
            onClick={onOpenImportModal}
            className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-lg text-xs font-semibold bg-[#111827] text-white hover:bg-black transition shadow-xs"
          >
            <Plus className="w-4 h-4" />
            New Dispute / Import
          </button>
        </div>
      </div>

      {/* Honest Live PayPal Empty State Banner when 0 live disputes exist */}
      {!loading && liveCount === 0 && (
        <div className="p-3.5 rounded-xl border border-amber-200 bg-amber-50/70 flex flex-col sm:flex-row sm:items-center justify-between gap-2 text-xs text-amber-950">
          <div className="flex items-start sm:items-center gap-2.5">
            <AlertCircle className="w-4 h-4 text-amber-700 shrink-0 mt-0.5 sm:mt-0" />
            <span>
              <strong>Live PayPal Sandbox: 0 active disputes</strong> returned from <code className="font-mono bg-amber-100 px-1 py-0.5 rounded">GET /v1/customer/disputes</code>.
              Showing clearly labelled <strong>LOCAL DEMO</strong> scenarios below for workflow demonstration.
            </span>
          </div>
          <span className="px-2 py-0.5 text-[10px] font-mono font-bold rounded bg-amber-100 text-amber-900 border border-amber-300 shrink-0">
            NO LIVE DISPUTES IN SANDBOX
          </span>
        </div>
      )}

      {/* Operational Summary Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-white p-4 rounded-xl border border-[#E5E7EB] shadow-sm">
          <div className="flex items-center justify-between text-xs font-medium text-[#6B7280]">
            <span>Active Disputes</span>
            <span className="w-2 h-2 rounded-full bg-amber-500"></span>
          </div>
          <div className="mt-2 flex items-baseline gap-2">
            <span className="text-2xl font-bold text-[#111827]">{needsActionCount}</span>
            <span className="text-xs text-amber-700 font-medium">Require seller response</span>
          </div>
        </div>

        <div className="bg-white p-4 rounded-xl border border-[#E5E7EB] shadow-sm">
          <div className="flex items-center justify-between text-xs font-medium text-[#6B7280]">
            <span>Disputed Volume</span>
            <ShieldCheck className="w-4 h-4 text-[#9CA3AF]" />
          </div>
          <div className="mt-2 flex items-baseline gap-2">
            <span className="text-2xl font-bold text-[#111827]">${totalDisputedRevenue}</span>
            <span className="text-xs text-[#6B7280]">Across {totalCount} listed cases</span>
          </div>
        </div>

        <div className="bg-white p-4 rounded-xl border border-[#E5E7EB] shadow-sm">
          <div className="flex items-center justify-between text-xs font-medium text-[#6B7280]">
            <span>Earliest Deadline</span>
            <Clock className="w-4 h-4 text-amber-600" />
          </div>
          <div className="mt-2 flex items-baseline gap-2">
            <span className="text-2xl font-bold text-amber-800">
              {earliestDeadline?.urgency_days_left != null ? `${earliestDeadline.urgency_days_left} Days` : '—'}
            </span>
            <span className="text-xs text-[#6B7280]">
              {earliestDeadline?.seller_response_due_date
                ? new Date(earliestDeadline.seller_response_due_date).toLocaleDateString()
                : 'No live deadline'}
            </span>
          </div>
        </div>

        <div className="bg-white p-4 rounded-xl border border-[#E5E7EB] shadow-sm">
          <div className="flex items-center justify-between text-xs font-medium text-[#6B7280]">
            <span>Live vs Local Provenance</span>
            <CheckCircle2 className="w-4 h-4 text-emerald-600" />
          </div>
          <div className="mt-2 flex items-baseline gap-2">
            <span className="text-2xl font-bold text-[#111827]">{liveCount} Live</span>
            <span className="text-xs text-[#6B7280]">/ {totalCount - liveCount} Local Demo</span>
          </div>
        </div>
      </div>

      {/* Main Table Container (Ramp + Stripe Pattern) */}
      <div className="bg-white rounded-xl border border-[#E5E7EB] shadow-sm overflow-hidden">
        {/* Navigation Tabs with Count Badges */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between border-b border-[#E5E7EB] px-4 pt-3 gap-3">
          <div className="flex items-center gap-1 overflow-x-auto">
            <button
              onClick={() => setFilterTab('ALL')}
              className={`px-3 py-2 text-xs font-semibold rounded-t-lg border-b-2 flex items-center gap-1.5 transition ${
                filterTab === 'ALL'
                  ? 'border-[#111827] text-[#111827]'
                  : 'border-transparent text-[#6B7280] hover:text-[#111827]'
              }`}
            >
              <span>All Cases</span>
              <span className="px-1.5 py-0.5 text-[10px] rounded-full bg-gray-100 text-gray-700">
                {totalCount}
              </span>
            </button>

            <button
              onClick={() => setFilterTab('NEEDS_ACTION')}
              className={`px-3 py-2 text-xs font-semibold rounded-t-lg border-b-2 flex items-center gap-1.5 transition ${
                filterTab === 'NEEDS_ACTION'
                  ? 'border-amber-600 text-amber-900'
                  : 'border-transparent text-[#6B7280] hover:text-[#111827]'
              }`}
            >
              <span>Needs Attention</span>
              <span className="px-1.5 py-0.5 text-[10px] rounded-full bg-amber-100 text-amber-800 font-bold">
                {needsActionCount}
              </span>
            </button>

            <button
              onClick={() => setFilterTab('UNDER_REVIEW')}
              className={`px-3 py-2 text-xs font-semibold rounded-t-lg border-b-2 flex items-center gap-1.5 transition ${
                filterTab === 'UNDER_REVIEW'
                  ? 'border-blue-600 text-blue-900'
                  : 'border-transparent text-[#6B7280] hover:text-[#111827]'
              }`}
            >
              <span>Under Review</span>
              <span className="px-1.5 py-0.5 text-[10px] rounded-full bg-blue-100 text-blue-800 font-bold">
                {underReviewCount}
              </span>
            </button>

            <button
              onClick={() => setFilterTab('RESOLVED')}
              className={`px-3 py-2 text-xs font-semibold rounded-t-lg border-b-2 flex items-center gap-1.5 transition ${
                filterTab === 'RESOLVED'
                  ? 'border-emerald-600 text-emerald-900'
                  : 'border-transparent text-[#6B7280] hover:text-[#111827]'
              }`}
            >
              <span>Resolved</span>
              <span className="px-1.5 py-0.5 text-[10px] rounded-full bg-emerald-100 text-emerald-800">
                {resolvedCount}
              </span>
            </button>
          </div>

          {/* Search Box */}
          <div className="pb-2.5 sm:pb-3 w-full sm:w-72">
            <div className="relative">
              <Search className="w-3.5 h-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-[#9CA3AF]" />
              <input
                type="text"
                placeholder="Filter by case, order, buyer..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full pl-9 pr-3 py-1.5 text-xs bg-[#F9FAFB] border border-[#E5E7EB] rounded-lg focus:outline-none focus:ring-1 focus:ring-black focus:bg-white transition"
              />
            </div>
          </div>
        </div>

        {/* Dense Table View */}
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-[#F9FAFB] text-[#6B7280] font-semibold border-b border-[#E5E7EB]">
              <tr>
                <th className="py-3 px-4 w-12 text-center">#</th>
                <th className="py-3 px-4">Dispute & Order</th>
                <th className="py-3 px-4">Dispute Reason</th>
                <th className="py-3 px-4">Amount</th>
                <th className="py-3 px-4">Response Due</th>
                <th className="py-3 px-4">Evidence Truth Readiness</th>
                <th className="py-3 px-4">Status</th>
                <th className="py-3 px-4 text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#E5E7EB]">
              {filteredDisputes.length === 0 ? (
                <tr>
                  <td colSpan={8} className="py-12 text-center text-[#6B7280]">
                    <AlertCircle className="w-8 h-8 text-[#9CA3AF] mx-auto mb-2" />
                    <p className="font-medium text-sm text-[#111827]">No disputes found</p>
                    <p className="text-xs text-[#6B7280] mt-1">
                      No records match the selected filter criteria.
                    </p>
                  </td>
                </tr>
              ) : (
                filteredDisputes.map((d, idx) => {
                  const isUrgent = d.status === 'WAITING_FOR_SELLER_RESPONSE';
                  return (
                    <tr
                      key={d.dispute_id || idx}
                      onClick={() => onSelectDispute(d.dispute_id)}
                      className="hover:bg-[#F9FAFB] cursor-pointer transition group"
                    >
                      <td className="py-3.5 px-4 text-center text-[#9CA3AF] font-mono text-[11px]">
                        {idx + 1}
                      </td>

                      {/* Dispute & Order Reference + Provenance */}
                      <td className="py-3.5 px-4">
                        <div className="flex flex-col gap-0.5">
                          <div className="flex items-center gap-2 flex-wrap">
                            <span className="font-mono font-bold text-[#111827] group-hover:text-blue-600 transition">
                              {d.dispute_id}
                            </span>
                            {d.is_live_paypal_dispute ? (
                              <span className="px-1.5 py-0.5 text-[10px] font-bold rounded bg-emerald-100 text-emerald-800 border border-emerald-300">
                                LIVE PAYPAL
                              </span>
                            ) : (
                              <span className="px-1.5 py-0.5 text-[10px] font-bold rounded bg-purple-100 text-purple-800 border border-purple-200">
                                LOCAL DEMO — NOT A PAYPAL DISPUTE
                              </span>
                            )}
                          </div>
                          <span className="text-[11px] text-[#4B5563] truncate max-w-xs font-medium">
                            {d.product_name || 'Digital Course / License'}
                          </span>
                          <span className="text-[10px] text-[#9CA3AF] font-mono">
                            Ref: {d.transaction_reference} · Req: {d.required_evidence_type || 'PROOF_OF_FULFILLMENT'}
                          </span>
                        </div>
                      </td>

                      {/* Dispute Reason */}
                      <td className="py-3.5 px-4">
                        <span className="inline-flex items-center px-2 py-0.5 rounded text-[11px] font-medium bg-gray-100 text-[#374151]">
                          {getReasonLabel(d.dispute_reason)}
                        </span>
                      </td>

                      {/* Amount */}
                      <td className="py-3.5 px-4 font-mono font-bold text-[#111827]">
                        ${d.amount} {d.currency || 'USD'}
                      </td>

                      {/* Response Due / Urgency */}
                      <td className="py-3.5 px-4">
                        {isUrgent ? (
                          <div className="flex flex-col">
                            <span className="font-semibold text-amber-700 flex items-center gap-1">
                              <Clock className="w-3 h-3 text-amber-600" />
                              {d.urgency_days_left !== undefined && d.urgency_days_left !== null ? `${d.urgency_days_left} days left` : 'Action Required'}
                            </span>
                            <span className="text-[10px] text-[#6B7280]">
                              {d.seller_response_due_date
                                ? `Due: ${new Date(d.seller_response_due_date).toLocaleDateString()}`
                                : 'Deadline unavailable'}
                            </span>
                          </div>
                        ) : (
                          <span className="text-[11px] text-[#6B7280]">
                            {d.status === 'UNDER_PAYPAL_REVIEW' ? 'Evidence Submitted' : 'Closed'}
                          </span>
                        )}
                      </td>

                      {/* Preparation Progress / Evidence Readiness */}
                      <td className="py-3.5 px-4">
                        {d.status === 'UNDER_PAYPAL_REVIEW' ? (
                          <div className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-[11px] font-semibold bg-blue-50 text-blue-800 border border-blue-200">
                            <Check className="w-3 h-3 text-blue-600 shrink-0" />
                            <span>Submitted / Sealed</span>
                          </div>
                        ) : d.evidence_readiness === 'NEEDS_ATTENTION' ? (
                          <div className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-[11px] font-semibold bg-amber-50 text-amber-800 border border-amber-200">
                            <AlertTriangle className="w-3 h-3 text-amber-600 shrink-0" />
                            <span>Fulfillment Proof Needed</span>
                          </div>
                        ) : (
                          <div className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-[11px] font-semibold bg-emerald-50 text-emerald-800 border border-emerald-200">
                            <Check className="w-3 h-3 text-emerald-600 shrink-0" />
                            <span>Ready for Analysis</span>
                          </div>
                        )}
                      </td>

                      {/* Status */}
                      <td className="py-3.5 px-4">
                        {getStatusBadge(d.status)}
                      </td>

                      {/* Action */}
                      <td className="py-3.5 px-4 text-right">
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            onSelectDispute(d.dispute_id);
                          }}
                          className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs font-semibold bg-white border border-[#D1D5DB] text-[#111827] hover:bg-[#111827] hover:text-white transition shadow-sm"
                        >
                          Review Case
                          <ChevronRight className="w-3.5 h-3.5" />
                        </button>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>

        {/* Table Footer info */}
        <div className="bg-[#F9FAFB] border-t border-[#E5E7EB] px-4 py-2.5 flex items-center justify-between text-[11px] text-[#6B7280]">
          <span className="flex items-center gap-1.5">
            <ShieldCheck className="w-3.5 h-3.5 text-emerald-600" />
            Showing {filteredDisputes.length} disputes linked to authenticated PayPal merchant account.
          </span>
          <span className="font-mono text-[#9CA3AF]">
            Sandbox Merchant: sb-n8g5t31140994@business.example.com
          </span>
        </div>
      </div>
    </div>
  );
}

