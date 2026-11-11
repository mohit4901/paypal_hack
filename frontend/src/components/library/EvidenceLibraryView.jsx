import React, { useState, useEffect } from 'react';
import { FolderOpen, RefreshCw, PlusCircle, ArrowRight, FileText } from 'lucide-react';
import PageHeader from '../layout/PageHeader';
import StatusBadge from '../ui/StatusBadge';
import LoadingState from '../ui/LoadingState';
import EmptyState from '../ui/EmptyState';
import { api } from '../../services/api';

export default function EvidenceLibraryView({
  transactions = [],
  loading = false,
  onRefresh,
  onNewAnalysis,
  onSelectOrderForDispute,
}) {
  const [selectedOrderId, setSelectedOrderId] = useState(transactions[0]?.order_id || null);
  const [evidenceItems, setEvidenceItems] = useState([]);
  const [loadingEv, setLoadingEv] = useState(false);

  useEffect(() => {
    if (!selectedOrderId && transactions.length > 0) {
      setSelectedOrderId(transactions[0].order_id);
    }
  }, [transactions, selectedOrderId]);

  useEffect(() => {
    if (!selectedOrderId) return;
    let active = true;
    setLoadingEv(true);
    api
      .getTransactionEvidence(selectedOrderId)
      .then((res) => {
        if (active) setEvidenceItems(res?.evidence || []);
      })
      .catch(() => {
        if (active) setEvidenceItems([]);
      })
      .finally(() => {
        if (active) setLoadingEv(false);
      });
    return () => {
      active = false;
    };
  }, [selectedOrderId]);

  return (
    <div className="space-y-6">
      <PageHeader
        title="Evidence Library"
        subtitle="Inspect persisted order transactions and stored merchant evidence records linked across SQLite."
        actions={
          <>
            {onRefresh && (
              <button
                type="button"
                onClick={onRefresh}
                disabled={loading}
                className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-lg text-xs font-medium bg-white text-[#18181B] border border-[#E6E4DD] hover:bg-[#F8F7F3] transition-colors"
              >
                <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
                <span>Refresh</span>
              </button>
            )}
            <button
              type="button"
              onClick={onNewAnalysis}
              className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-lg text-xs font-medium bg-[#18181B] text-white hover:bg-[#27272A] transition-colors"
            >
              <PlusCircle className="w-3.5 h-3.5" />
              <span>New Analysis</span>
            </button>
          </>
        }
      />

      {loading && transactions.length === 0 ? (
        <LoadingState rows={3} label="Loading stored merchant orders..." />
      ) : transactions.length === 0 ? (
        <EmptyState
          icon={FolderOpen}
          title="No store transactions recorded yet"
          description="Create a new dispute analysis or import a PayPal Sandbox order to populate stored evidence records."
        />
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
          {/* Left: Orders List */}
          <div className="lg:col-span-5 bg-white rounded-xl border border-[#E6E4DD] overflow-hidden">
            <div className="px-4 py-3 border-b border-[#EFECE4] bg-[#FCFBF8] text-xs font-semibold text-[#18181B]">
              Orders &amp; Captures ({transactions.length})
            </div>
            <div className="divide-y divide-[#EFECE4] max-h-[540px] overflow-y-auto">
              {transactions.map((tx) => {
                const isSelected = selectedOrderId === tx.order_id;
                return (
                  <button
                    key={tx.order_id}
                    type="button"
                    onClick={() => setSelectedOrderId(tx.order_id)}
                    className={`w-full text-left px-4 py-3 text-xs transition-colors flex items-center justify-between gap-2 ${
                      isSelected ? 'bg-[#F0FDFA] border-l-2 border-l-[#0F766E]' : 'hover:bg-[#FCFBF8]'
                    }`}
                  >
                    <div className="min-w-0">
                      <div className="font-mono font-semibold text-[#18181B] truncate">
                        {tx.order_id}
                      </div>
                      <div className="text-[11px] text-[#52525B] truncate mt-0.5">
                        {tx.product_name || 'Merchant Order'} · {tx.amount} {tx.currency}
                      </div>
                    </div>
                    <StatusBadge size="xs" status={tx.payment_status || 'COMPLETED'} showIcon={false} />
                  </button>
                );
              })}
            </div>
          </div>

          {/* Right: Linked Evidence Records */}
          <div className="lg:col-span-7 bg-white rounded-xl border border-[#E6E4DD] p-5 space-y-4">
            <div className="flex flex-wrap items-center justify-between gap-2 pb-3 border-b border-[#EFECE4]">
              <div>
                <div className="text-[11px] font-mono text-[#71717A]">Selected Order</div>
                <h2 className="text-sm font-semibold font-mono text-[#18181B]">
                  {selectedOrderId}
                </h2>
              </div>

              {onSelectOrderForDispute && selectedOrderId && (
                <button
                  type="button"
                  onClick={() => onSelectOrderForDispute(selectedOrderId)}
                  className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs font-medium bg-[#18181B] text-white hover:bg-[#27272A]"
                >
                  <span>Open Dispute Workspace</span>
                  <ArrowRight className="w-3.5 h-3.5" />
                </button>
              )}
            </div>

            {loadingEv ? (
              <LoadingState rows={2} label="Loading order evidence..." />
            ) : evidenceItems.length === 0 ? (
              <div className="text-xs text-[#71717A] py-4">
                No evidence rows linked to this order yet.
              </div>
            ) : (
              <div className="space-y-3">
                {evidenceItems.map((ev, idx) => (
                  <div
                    key={ev.evidence_id || idx}
                    className="rounded-lg border border-[#E6E4DD] bg-[#FCFBF8] p-3.5 space-y-1.5 text-xs"
                  >
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <span className="inline-flex items-center gap-1.5 font-semibold text-[#18181B]">
                        <FileText className="w-3.5 h-3.5 text-[#0F766E]" />
                        {ev.source_name || ev.source_type || 'Store Evidence'}
                      </span>
                      <StatusBadge
                        size="xs"
                        variant={ev.is_verified_source ? 'verified' : 'warning'}
                        label={ev.is_verified_source ? 'Verified Source' : 'Unverified Store Input'}
                      />
                    </div>
                    <p className="text-[#3F3F46] font-mono text-[11px] leading-relaxed break-words">
                      {ev.content}
                    </p>
                    {ev.timestamp && (
                      <div className="text-[10px] font-mono text-[#71717A]">
                        Logged: {ev.timestamp}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

