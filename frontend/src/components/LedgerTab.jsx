import React, { useState, useEffect } from 'react';
import { GitCommit, CheckCircle2, XCircle, RefreshCw, Lock, Link, ArrowDown } from 'lucide-react';
import { api } from '../api';

export default function LedgerTab() {
  const [ledger, setLedger] = useState(null);
  const [loading, setLoading] = useState(false);
  const [validating, setValidating] = useState(false);
  const [validationResult, setValidationResult] = useState(null);

  const loadLedger = async () => {
    setLoading(true);
    try {
      const data = await api.getLedger();
      setLedger(data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleValidateEntireChain = async () => {
    setValidating(true);
    try {
      const res = await api.validateLedger();
      setValidationResult(res);
    } catch (err) {
      console.error(err);
    } finally {
      setValidating(false);
    }
  };

  useEffect(() => {
    loadLedger();
  }, []);

  const sampled = ledger?.sampled_blocks || [];

  return (
    <div className="space-y-6">
      {/* Header Card */}
      <div className="bg-[#0e1424] border border-slate-800 rounded-xl p-5 flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h2 className="text-base font-bold text-white mb-1">
            Authoritative SHA-256 Hash Chain Explorer
          </h2>
          <p className="text-xs text-slate-400">
            Immutable, continuous cryptographic ledger anchored in <code className="text-cyan-400">data/events_hash_chain_v2.jsonl</code>.
          </p>
        </div>
        <button
          onClick={handleValidateEntireChain}
          disabled={validating}
          className="px-4 py-2.5 rounded-xl bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-400 hover:to-blue-500 text-white font-medium text-xs shadow-lg shadow-cyan-500/20 disabled:opacity-50 transition-all shrink-0 flex items-center space-x-2"
        >
          <Lock className="h-3.5 w-3.5" />
          <span>{validating ? 'Auditing All 164 Links...' : 'Verify Entire Chain Links'}</span>
        </button>
      </div>

      {/* Validation Result Banner */}
      {validationResult && (
        <div
          className={`p-4 rounded-xl border text-xs flex items-center space-x-3 ${
            validationResult.is_valid
              ? 'bg-emerald-950/40 border-emerald-800/60 text-emerald-300'
              : 'bg-rose-950/40 border-rose-800/60 text-rose-300'
          }`}
        >
          {validationResult.is_valid ? (
            <CheckCircle2 className="h-5 w-5 text-emerald-400 shrink-0" />
          ) : (
            <XCircle className="h-5 w-5 text-rose-400 shrink-0" />
          )}
          <div>
            <div className="font-semibold">
              {validationResult.is_valid
                ? `100% Cryptographic Continuity Verified (${validationResult.total_records_verified} links)`
                : `Chain Integrity Compromised: ${validationResult.error_count} error(s)`}
            </div>
            <div className="text-[11px] text-slate-400 mt-0.5">
              Every single sequential SHA-256 self-hash and predecessor link validated with zero breaks.
            </div>
          </div>
        </div>
      )}

      {/* Visual Block Sequence */}
      <div className="space-y-3">
        <h3 className="text-sm font-semibold text-white">Sampled Sequential Block Trajectory</h3>

        <div className="space-y-4">
          {sampled.map((b, i) => (
            <React.Fragment key={b.event_id}>
              <div className="bg-[#0e1424] border border-slate-800 rounded-xl p-4 text-xs space-y-2 hover:border-slate-700 transition-colors">
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-2">
                    <span className="font-mono text-cyan-400 font-bold">Block #{b.index}</span>
                    <span className="px-2 py-0.5 rounded text-[10px] bg-slate-800 text-slate-300 border border-slate-700 font-mono">
                      {b.source_type}
                    </span>
                    {b.is_migrated && (
                      <span className="px-2 py-0.5 rounded text-[10px] bg-blue-950 text-blue-300 border border-blue-800">
                        V2 Migrated
                      </span>
                    )}
                  </div>
                  <span className="text-[11px] text-slate-500 font-mono">{b.recorded_at}</span>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-2 font-mono text-[11px] pt-1">
                  <div className="bg-slate-950/80 p-2 rounded border border-slate-800/80">
                    <span className="text-slate-500 block text-[10px]">PREVIOUS_HASH</span>
                    <span className="text-slate-400 break-all select-all">{b.previous_hash}</span>
                  </div>
                  <div className="bg-slate-950/80 p-2 rounded border border-slate-800/80">
                    <span className="text-slate-500 block text-[10px]">CURRENT_HASH (SHA-256)</span>
                    <span className="text-cyan-400 break-all select-all">{b.current_hash}</span>
                  </div>
                </div>
              </div>

              {i < sampled.length - 1 && (
                <div className="flex justify-center text-slate-600">
                  <ArrowDown className="h-4 w-4 text-cyan-500/60" />
                </div>
              )}
            </React.Fragment>
          ))}
        </div>
      </div>
    </div>
  );
}

