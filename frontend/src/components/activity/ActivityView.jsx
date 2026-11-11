import React, { useState, useEffect } from 'react';
import { RefreshCw, ShieldCheck, Clock } from 'lucide-react';
import PageHeader from '../layout/PageHeader';
import StatusBadge from '../ui/StatusBadge';
import LoadingState from '../ui/LoadingState';
import ErrorState from '../ui/ErrorState';
import { api } from '../../services/api';

export default function ActivityView() {
  const [runs, setRuns] = useState([]);
  const [events, setEvents] = useState([]);
  const [ledgerCheck, setLedgerCheck] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const loadActivity = async () => {
    setLoading(true);
    setError(null);
    try {
      const [runsRes, evRes, valRes] = await Promise.all([
        api.getVerificationRuns().catch(() => ({ runs: [] })),
        api.getEvents({ page: 1, page_size: 20 }).catch(() => ({ events: [] })),
        api.validateLedger().catch(() => null),
      ]);
      setRuns(runsRes?.runs || []);
      setEvents(evRes?.events || []);
      setLedgerCheck(valRes);
    } catch (err) {
      setError(err.message || 'Failed to fetch activity logs.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadActivity();
  }, []);

  return (
    <div className="space-y-6">
      <PageHeader
        title="Activity"
        subtitle="Audit log of persistent verification runs and cryptographic hash-chain ledger events."
        actions={
          <button
            type="button"
            onClick={loadActivity}
            disabled={loading}
            className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-lg text-xs font-medium bg-white text-[#18181B] border border-[#E6E4DD] hover:bg-[#F8F7F3]"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
            <span>Refresh</span>
          </button>
        }
      />

      {error && <ErrorState message={error} onRetry={loadActivity} />}

      {ledgerCheck && (
        <div className="bg-white rounded-xl border border-[#E6E4DD] p-4 flex flex-wrap items-center justify-between gap-3 text-xs">
          <div className="flex items-center gap-2">
            <ShieldCheck className="w-4 h-4 text-[#0F766E]" />
            <span className="font-semibold text-[#18181B]">V2 Hash-Chain Ledger Integrity:</span>
            <span className="text-[#52525B]">{ledgerCheck.summary || 'Validated'}</span>
          </div>
          <StatusBadge
            size="xs"
            variant={ledgerCheck.valid ? 'verified' : 'error'}
            label={ledgerCheck.valid ? `INTACT (${ledgerCheck.total_events || 0} blocks)` : 'VALIDATION_WARNING'}
          />
        </div>
      )}

      {loading ? (
        <LoadingState rows={4} label="Loading audit runs & events..." />
      ) : (
        <div className="space-y-6">
          {/* Verification Runs */}
          <section className="bg-white rounded-xl border border-[#E6E4DD] overflow-hidden">
            <div className="px-5 py-3.5 border-b border-[#EFECE4] bg-[#FCFBF8] text-xs font-semibold text-[#18181B]">
              Persistent Claim Verification Runs ({runs.length})
            </div>
            {runs.length === 0 ? (
              <div className="p-5 text-xs text-[#71717A]">
                No verification runs recorded for this seller account yet.
              </div>
            ) : (
              <div className="divide-y divide-[#EFECE4]">
                {runs.map((r) => (
                  <div key={r.run_id} className="px-5 py-3.5 text-xs flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                    <div className="space-y-0.5 min-w-0">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="font-mono font-semibold text-[#18181B]">{r.run_id}</span>
                        <span className="font-mono text-[11px] text-[#52525B]">Order: {r.transaction_reference}</span>
                        <span className="font-mono text-[10px] px-1.5 py-0.5 rounded bg-[#F8F7F3] border border-[#E6E4DD] text-[#52525B]">
                          {r.model_checkpoint || r.model_name}
                        </span>
                      </div>
                      <div className="text-[11px] text-[#71717A] flex items-center gap-1.5">
                        <Clock className="w-3 h-3" />
                        <span>{r.created_at ? new Date(r.created_at).toLocaleString() : '—'}</span>
                        <span>·</span>
                        <span className="font-mono">SHA-256: {String(r.packet_sha256_digest || '').slice(0, 14)}...</span>
                      </div>
                    </div>
                    <StatusBadge size="xs" status={r.combined_verdict || 'COMPLETED'} />
                  </div>
                ))}
              </div>
            )}
          </section>

          {/* Ledger Events */}
          <section className="bg-white rounded-xl border border-[#E6E4DD] overflow-hidden">
            <div className="px-5 py-3.5 border-b border-[#EFECE4] bg-[#FCFBF8] text-xs font-semibold text-[#18181B]">
              Recent Cryptographic Ledger Events ({events.length})
            </div>
            {events.length === 0 ? (
              <div className="p-5 text-xs text-[#71717A]">
                Zero ledger events recorded in active chain.
              </div>
            ) : (
              <div className="divide-y divide-[#EFECE4]">
                {events.map((ev, i) => (
                  <div key={ev.event_id || i} className="px-5 py-3 text-xs flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                    <div className="min-w-0">
                      <div className="font-mono font-medium text-[#18181B]">
                        {ev.event_id} · {ev.event_type || ev.source_type}
                      </div>
                      <div className="text-[11px] text-[#52525B] truncate mt-0.5">
                        {ev.summary || ev.content || JSON.stringify(ev.payload || {})}
                      </div>
                    </div>
                    <span className="font-mono text-[10px] text-[#71717A] shrink-0">
                      {ev.timestamp || ''}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </section>
        </div>
      )}
    </div>
  );
}

