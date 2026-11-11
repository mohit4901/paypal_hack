import React from 'react';
import {
  Inbox,
  PlusCircle,
  Cpu,
  ShieldCheck,
  Database,
  ArrowRight,
  AlertTriangle,
} from 'lucide-react';
import PageHeader from '../components/layout/PageHeader';
import MetricCard from '../components/ui/MetricCard';
import StatusBadge from '../components/ui/StatusBadge';
import ErrorState from '../components/ui/ErrorState';

export default function DashboardPage({
  overview = null,
  disputes = [],
  transactions = [],
  systemStatus = null,
  isOffline = false,
  offlineError = null,
  onRefresh,
  onNavigate,
  onOpenDispute,
  onOpenPayPalInspector,
}) {
  const aiModel = systemStatus?.ai_model || {};
  const pp = systemStatus?.paypal || {};
  const db = systemStatus?.database || {};
  const ledger = systemStatus?.ledger || overview?.ledger || {};

  const aiLoaded = aiModel.status === 'MODEL_LOADED' && aiModel.is_loaded !== false;
  const openCount = disputes.filter(
    (d) => d.status === 'WAITING_FOR_SELLER_RESPONSE' || d.status === 'UNDER_PAYPAL_REVIEW'
  ).length;
  const liveCount = disputes.filter((d) => Boolean(d.is_live_paypal_dispute)).length;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Overview"
        subtitle="System readiness, active dispute caseload, and model provenance across your ProofLedger workspace."
        actions={
          <>
            <button
              type="button"
              onClick={() => onNavigate('inbox')}
              className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-lg text-xs font-medium bg-white text-[#18181B] border border-[#E6E4DD] hover:bg-[#F8F7F3] transition-colors"
            >
              <Inbox className="w-3.5 h-3.5" />
              <span>Dispute Inbox</span>
            </button>
            <button
              type="button"
              onClick={() => onNavigate('new_analysis')}
              className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg text-xs font-medium bg-[#18181B] text-white hover:bg-[#27272A] transition-colors"
            >
              <PlusCircle className="w-3.5 h-3.5 text-[#99F6E4]" />
              <span>Analyze a Dispute</span>
            </button>
          </>
        }
      />

      {isOffline && (
        <ErrorState
          title="Backend Server Unreachable"
          message={offlineError || 'Ensure the FastAPI service is running cleanly.'}
          onRetry={onRefresh}
        />
      )}

      {!isOffline && !aiLoaded && systemStatus && (
        <div className="rounded-xl border border-rose-200 bg-rose-50 p-4 flex items-start gap-3 text-xs text-rose-900">
          <AlertTriangle className="w-5 h-5 text-rose-600 shrink-0 mt-0.5" />
          <div>
            <div className="font-semibold">AI Semantic Verifier Offline (MODEL_UNAVAILABLE)</div>
            <div className="mt-0.5 text-rose-800">
              {aiModel.model_load_error ||
                'Candidate DeBERTa-v3 checkpoint failed to load. Semantic claims fail closed to INSUFFICIENT_EVIDENCE.'}
            </div>
          </div>
        </div>
      )}

      {/* Real Backend Metrics */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4">
        <MetricCard
          label="Open disputes"
          value={openCount}
          sublabel={`${liveCount} live PayPal · ${disputes.length - liveCount} local demo`}
          icon={Inbox}
          onClick={() => onNavigate('inbox')}
        />
        <MetricCard
          label="Orders in store ledger"
          value={transactions.length}
          sublabel="Persistent SQLite records"
          icon={Database}
          onClick={() => onNavigate('evidence_library')}
        />
        <MetricCard
          label="AI Verifier state"
          value={aiLoaded ? 'Online' : 'Offline'}
          sublabel={aiModel.device ? `Device: ${aiModel.device.toUpperCase()}` : 'MODEL_UNAVAILABLE'}
          icon={Cpu}
          tone={aiLoaded ? 'success' : 'error'}
        />
        <MetricCard
          label="Hash-chain ledger blocks"
          value={ledger.total_blocks ?? ledger.total_events ?? 0}
          sublabel={ledger.valid !== false ? 'SHA-256 continuity intact' : 'Verify ledger'}
          icon={ShieldCheck}
          onClick={() => onNavigate('activity')}
        />
      </div>

      {/* Infrastructure & Provenance Details */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="bg-white rounded-xl border border-[#E6E4DD] p-5 space-y-4">
          <div className="flex items-center justify-between border-b border-[#EFECE4] pb-3">
            <h2 className="text-sm font-semibold text-[#18181B]">
              Model &amp; Infrastructure Readiness
            </h2>
            <StatusBadge
              size="xs"
              status={systemStatus?.overall_status || (isOffline ? 'OFFLINE' : 'LOADING')}
            />
          </div>

          <div className="space-y-2.5 text-xs">
            <div className="flex justify-between gap-3">
              <span className="text-[#71717A]">Active checkpoint</span>
              <span className="font-mono text-[11px] text-[#18181B] truncate max-w-[280px]" title={aiModel.loaded_model_path}>
                {aiModel.checkpoint_path || aiModel.loaded_model_path || 'MODEL_UNAVAILABLE'}
              </span>
            </div>
            <div className="flex justify-between gap-3">
              <span className="text-[#71717A]">SQLite database</span>
              <span className="font-mono text-[#18181B]">{db.status || '—'}</span>
            </div>
            <div className="flex justify-between gap-3">
              <span className="text-[#71717A]">PayPal Sandbox OAuth</span>
              <span className="font-mono text-[#18181B]">{pp.auth_status || '—'}</span>
            </div>
          </div>

          {onOpenPayPalInspector && (
            <button
              type="button"
              onClick={onOpenPayPalInspector}
              className="text-xs font-medium text-[#0F766E] hover:underline"
            >
              Inspect PayPal Sandbox Integration →
            </button>
          )}
        </div>

        {/* Active Cases Quick Jump */}
        <div className="bg-white rounded-xl border border-[#E6E4DD] p-5 space-y-4">
          <div className="flex items-center justify-between border-b border-[#EFECE4] pb-3">
            <h2 className="text-sm font-semibold text-[#18181B]">Cases Requiring Attention</h2>
            <button
              type="button"
              onClick={() => onNavigate('inbox')}
              className="text-xs font-medium text-[#0F766E] hover:underline"
            >
              View all
            </button>
          </div>

          {disputes.length === 0 ? (
            <p className="text-xs text-[#71717A]">
              No disputes currently loaded from the backend.
            </p>
          ) : (
            <div className="space-y-2">
              {disputes.slice(0, 3).map((d) => (
                <button
                  key={d.dispute_id}
                  type="button"
                  onClick={() => onOpenDispute(d.dispute_id)}
                  className="w-full text-left p-3 rounded-lg border border-[#E6E4DD] hover:border-[#0F766E]/50 hover:bg-[#FCFBF8] transition-colors flex items-center justify-between gap-3"
                >
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-xs font-semibold text-[#18181B]">
                        {d.dispute_id}
                      </span>
                      {!d.is_live_paypal_dispute && (
                        <span className="text-[10px] px-1.5 py-0.5 rounded bg-stone-100 text-stone-700 border border-stone-200">
                          LOCAL DEMO
                        </span>
                      )}
                    </div>
                    <div className="text-[11px] text-[#71717A] truncate mt-0.5">
                      Order {d.transaction_reference || '—'} · {d.amount || '0.00'} {d.currency || 'USD'}
                    </div>
                  </div>
                  <ArrowRight className="w-4 h-4 text-[#71717A] shrink-0" />
                </button>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
