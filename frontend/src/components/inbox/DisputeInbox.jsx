import React, { useState, useMemo } from 'react';
import { Inbox, Clock, CheckCircle2, ShieldCheck, AlertCircle, PlusCircle, RefreshCw, Info } from 'lucide-react';
import PageHeader from '../layout/PageHeader';
import MetricCard from '../ui/MetricCard';
import LoadingState from '../ui/LoadingState';
import DisputeFilters from './DisputeFilters';
import DisputeTable from './DisputeTable';
import EmptyDisputesState from './EmptyDisputesState';

export default function DisputeInbox({
  disputes = [],
  loading = false,
  onSelectDispute,
  onNewAnalysis,
  onRefresh,
  onSyncPayPal,
}) {
  const [activeFilter, setActiveFilter] = useState('ALL');
  const [searchQuery, setSearchQuery] = useState('');

  const metrics = useMemo(() => {
    const open = disputes.filter(
      (d) => d.status === 'WAITING_FOR_SELLER_RESPONSE' || d.status === 'UNDER_PAYPAL_REVIEW'
    ).length;
    const awaitingReview = disputes.filter(
      (d) => d.status === 'WAITING_FOR_SELLER_RESPONSE'
    ).length;
    const approved = disputes.filter(
      (d) => d.evidence_readiness === 'SUBMITTED_TO_PAYPAL' || d.status === 'UNDER_PAYPAL_REVIEW'
    ).length;
    const resolved = disputes.filter((d) => String(d.status || '').startsWith('RESOLVED')).length;
    const livePayPal = disputes.filter((d) => Boolean(d.is_live_paypal_dispute)).length;
    const localDemo = disputes.filter((d) => !d.is_live_paypal_dispute).length;
    const incomplete = disputes.filter((d) => d.evidence_readiness === 'NEEDS_ATTENTION').length;

    return {
      ALL: disputes.length,
      NEEDS_REVIEW: awaitingReview,
      EVIDENCE_INCOMPLETE: incomplete,
      APPROVED: approved,
      LIVE_PAYPAL: livePayPal,
      LOCAL_DEMO: localDemo,
      open,
      awaitingReview,
      approved,
      resolved,
    };
  }, [disputes]);

  const filteredDisputes = useMemo(() => {
    return disputes.filter((d) => {
      if (activeFilter === 'NEEDS_REVIEW' && d.status !== 'WAITING_FOR_SELLER_RESPONSE') return false;
      if (activeFilter === 'EVIDENCE_INCOMPLETE' && d.evidence_readiness !== 'NEEDS_ATTENTION') return false;
      if (
        activeFilter === 'APPROVED' &&
        d.evidence_readiness !== 'SUBMITTED_TO_PAYPAL' &&
        d.status !== 'UNDER_PAYPAL_REVIEW'
      ) {
        return false;
      }
      if (activeFilter === 'LIVE_PAYPAL' && !d.is_live_paypal_dispute) return false;
      if (activeFilter === 'LOCAL_DEMO' && d.is_live_paypal_dispute) return false;

      if (searchQuery.trim()) {
        const q = searchQuery.trim().toLowerCase();
        const fields = [
          d.dispute_id,
          d.transaction_reference,
          d.dispute_reason,
          d.buyer_email,
          d.capture_id,
          d.product_name,
        ];
        return fields.some((val) => String(val || '').toLowerCase().includes(q));
      }
      return true;
    });
  }, [disputes, activeFilter, searchQuery]);

  return (
    <div className="space-y-6">
      <PageHeader
        title="Disputes"
        subtitle="Review claims, verify evidence and prepare grounded responses."
        actions={
          <>
            {onRefresh && (
              <button
                type="button"
                onClick={onRefresh}
                disabled={loading}
                className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-lg text-xs font-medium bg-white text-[#18181B] border border-[#E6E4DD] hover:bg-[#F8F7F3] disabled:opacity-50 transition-colors"
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

      {/* Backend Summary Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4">
        <MetricCard
          label="Open disputes"
          value={metrics.open}
          sublabel={`${metrics.LIVE_PAYPAL} live · ${metrics.LOCAL_DEMO} demo`}
          icon={Inbox}
          onClick={() => setActiveFilter('ALL')}
          active={activeFilter === 'ALL'}
        />
        <MetricCard
          label="Awaiting merchant review"
          value={metrics.awaitingReview}
          sublabel="Response required"
          icon={Clock}
          tone={metrics.awaitingReview > 0 ? 'warning' : 'default'}
          onClick={() => setActiveFilter('NEEDS_REVIEW')}
          active={activeFilter === 'NEEDS_REVIEW'}
        />
        <MetricCard
          label="Approved evidence"
          value={metrics.approved}
          sublabel="SHA-256 bound or under review"
          icon={ShieldCheck}
          onClick={() => setActiveFilter('APPROVED')}
          active={activeFilter === 'APPROVED'}
        />
        <MetricCard
          label="Resolved / completed"
          value={metrics.resolved}
          sublabel="Closed cases"
          icon={CheckCircle2}
          tone="success"
        />
      </div>

      {/* Honest Live PayPal Empty Disclosure */}
      {metrics.LIVE_PAYPAL === 0 && (
        <div className="rounded-xl border border-[#E6E4DD] bg-white px-4 py-3 flex flex-col sm:flex-row sm:items-center justify-between gap-2 text-xs">
          <div className="flex items-start sm:items-center gap-2.5 text-[#3F3F46]">
            <Info className="w-4 h-4 text-[#0F766E] shrink-0 mt-0.5 sm:mt-0" />
            <span>
              <strong className="font-semibold text-[#18181B]">No live PayPal disputes found.</strong>{' '}
              Local demonstration scenarios remain available and are explicitly marked{' '}
              <span className="font-mono text-[11px] px-1.5 py-0.5 rounded bg-stone-100 border border-stone-200">
                LOCAL DEMO — NOT A PAYPAL DISPUTE
              </span>
              .
            </span>
          </div>
          {onSyncPayPal && (
            <button
              type="button"
              onClick={onSyncPayPal}
              className="text-xs font-medium text-[#0F766E] hover:underline shrink-0 self-start sm:self-center"
            >
              Sync PayPal Sandbox
            </button>
          )}
        </div>
      )}

      {/* Filter Bar */}
      <DisputeFilters
        activeFilter={activeFilter}
        onChangeFilter={setActiveFilter}
        searchQuery={searchQuery}
        onChangeSearch={setSearchQuery}
        counts={metrics}
      />

      {/* Content */}
      {loading && disputes.length === 0 ? (
        <LoadingState rows={4} label="Fetching disputes from backend..." />
      ) : filteredDisputes.length === 0 ? (
        activeFilter === 'LIVE_PAYPAL' && metrics.LIVE_PAYPAL === 0 ? (
          <EmptyDisputesState
            mode="no_live_paypal"
            onStartNewAnalysis={onNewAnalysis}
            onShowLocalDemo={() => setActiveFilter('LOCAL_DEMO')}
          />
        ) : (
          <EmptyDisputesState
            mode="filtered"
            onSyncPayPal={onSyncPayPal}
          />
        )
      ) : (
        <DisputeTable disputes={filteredDisputes} onSelectDispute={onSelectDispute} />
      )}
    </div>
  );
}

