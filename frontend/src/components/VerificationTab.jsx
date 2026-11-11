import React, { useState, useEffect } from 'react';
import {
  CheckCircle2,
  XCircle,
  AlertTriangle,
  Search,
  ShieldCheck,
  Database,
  Link2,
  Fingerprint,
  FileKey,
  ExternalLink,
  Layers,
} from 'lucide-react';
import { api } from '../api';

const QUICK_TARGETS = [
  { label: 'Real Sandbox Capture', id: '10A71705XW788203L' },
  { label: 'Real Sandbox Order', id: '3EU95140LR696653G' },
  { label: 'Genesis Block Event', id: '360b666a-2d2d-4537-8f52-87ad0f8a84fd' },
];

export default function VerificationTab({ initialTargetId }) {
  const [targetId, setTargetId] = useState(initialTargetId || '10A71705XW788203L');
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const runVerification = async (idToVerify) => {
    const queryId = idToVerify || targetId;
    if (!queryId) return;
    setLoading(true);
    setError(null);
    try {
      const res = await api.verifyEvent(queryId);
      setResult(res);
    } catch (err) {
      setError(err.message || 'Verification request failed');
      setResult(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (initialTargetId) {
      setTargetId(initialTargetId);
      runVerification(initialTargetId);
    } else {
      runVerification('10A71705XW788203L');
    }
  }, [initialTargetId]);

  const checks = result?.checks || {};

  return (
    <div className="space-y-6">
      {/* Target Input Card */}
      <div className="bg-[#0e1424] border border-slate-800 rounded-xl p-5 shadow-xl">
        <h2 className="text-base font-bold text-white mb-1">
          Interactive Multi-Dimensional Forensic Verifier
        </h2>
        <p className="text-xs text-slate-400 mb-4">
          Independent cryptographic evaluation: self-hash canonical match, predecessor link integrity, SQLite correlation, and provenance status.
        </p>

        <div className="flex flex-col sm:flex-row gap-3">
          <div className="relative flex-1">
            <Search className="h-4 w-4 text-slate-500 absolute left-3 top-3" />
            <input
              type="text"
              value={targetId}
              onChange={(e) => setTargetId(e.target.value)}
              placeholder="Enter Event ID, Capture ID (e.g. 10A71705XW788203L), or Order ID..."
              className="w-full bg-slate-900 border border-slate-800 text-xs rounded-xl pl-9 pr-3 py-2.5 text-slate-200 placeholder-slate-500 focus:outline-none focus:border-cyan-500 font-mono transition-colors"
            />
          </div>
          <button
            onClick={() => runVerification()}
            disabled={loading || !targetId}
            className="px-5 py-2.5 rounded-xl bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-400 hover:to-blue-500 text-white font-medium text-xs shadow-lg shadow-cyan-500/20 disabled:opacity-50 transition-all shrink-0"
          >
            {loading ? 'Verifying...' : 'Execute Forensic Audit'}
          </button>
        </div>

        {/* Quick Target Chips */}
        <div className="flex items-center space-x-2 mt-3 text-xs">
          <span className="text-slate-500 text-[11px]">Quick Samples:</span>
          {QUICK_TARGETS.map((q) => (
            <button
              key={q.id}
              onClick={() => {
                setTargetId(q.id);
                runVerification(q.id);
              }}
              className="px-2.5 py-1 rounded-lg bg-slate-900 border border-slate-800 hover:border-cyan-500/50 text-slate-300 text-[11px] font-mono transition-colors"
            >
              {q.label}
            </button>
          ))}
        </div>
      </div>

      {/* Error state */}
      {error && (
        <div className="bg-rose-950/40 border border-rose-800/60 rounded-xl p-4 text-rose-300 text-xs flex items-center space-x-2">
          <XCircle className="h-4 w-4 shrink-0 text-rose-400" />
          <span>{error}</span>
        </div>
      )}

      {/* Verification Results Panel */}
      {result && (
        <div className="space-y-6">
          {/* Main Verdict Card */}
          <div
            className={`border rounded-2xl p-6 relative overflow-hidden shadow-2xl ${
              result.verdict_badge === 'HISTORICAL_AUTHENTICATED'
                ? 'bg-gradient-to-br from-[#0c182d] to-[#0a1120] border-cyan-500/40'
                : result.verdict_badge === 'VERIFIED_AUTHENTIC'
                ? 'bg-gradient-to-br from-[#081f1c] to-[#0a1120] border-emerald-500/40'
                : 'bg-rose-950/20 border-rose-800/40'
            }`}
          >
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
              <div>
                <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-400 block mb-1">
                  Cryptographic Forensic Verdict
                </span>
                <h3 className="text-lg md:text-xl font-bold font-mono text-cyan-300 tracking-tight">
                  {result.verdict}
                </h3>
                <p className="text-xs text-slate-300 mt-2 max-w-3xl leading-relaxed">
                  {result.is_migrated ? (
                    <span>
                      Target record is independently <strong>authenticated via SHA-256 self-hash</strong> and correlated with durable SQLite persistence. Because this event originated prior to V2 ledger reconstruction, historical predecessor linkage remains preserved under strict forensic provenance notice.
                    </span>
                  ) : (
                    <span>
                      Target record is completely authenticated with unbroken sequential predecessor linkage and persistent database correlation.
                    </span>
                  )}
                </p>
              </div>

              <div className="shrink-0 flex md:flex-col items-center md:items-end justify-between gap-2 border-t md:border-t-0 pt-3 md:pt-0 border-slate-800">
                <span className="text-xs text-slate-400">Confidence</span>
                <span className="px-3 py-1 rounded-full text-xs font-mono font-bold bg-cyan-950 text-cyan-300 border border-cyan-700/50">
                  {result.confidence}
                </span>
              </div>
            </div>
          </div>

          {/* 6-Dimensional Breakdown Grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {/* Check 1 */}
            <div className="bg-[#0e1424] border border-slate-800 p-4 rounded-xl text-xs space-y-2">
              <div className="flex items-center justify-between">
                <span className="font-semibold text-slate-300 flex items-center space-x-1.5">
                  <Fingerprint className="h-4 w-4 text-cyan-400" />
                  <span>1. Content Self-Hash</span>
                </span>
                {checks.self_hash_valid ? (
                  <span className="text-emerald-400 font-semibold flex items-center space-x-1">
                    <CheckCircle2 className="h-3.5 w-3.5" />
                    <span>AUTHENTICATED</span>
                  </span>
                ) : (
                  <span className="text-rose-400 font-semibold flex items-center space-x-1">
                    <XCircle className="h-3.5 w-3.5" />
                    <span>MISMATCH</span>
                  </span>
                )}
              </div>
              <p className="text-slate-400 text-[11px]">
                Payload SHA-256 digest calculated strictly over canonical serialized JSON matches recorded current_hash.
              </p>
            </div>

            {/* Check 2 */}
            <div className="bg-[#0e1424] border border-slate-800 p-4 rounded-xl text-xs space-y-2">
              <div className="flex items-center justify-between">
                <span className="font-semibold text-slate-300 flex items-center space-x-1.5">
                  <Database className="h-4 w-4 text-blue-400" />
                  <span>2. SQLite Correlation</span>
                </span>
                {checks.database_correlation ? (
                  <span className="text-emerald-400 font-semibold flex items-center space-x-1">
                    <CheckCircle2 className="h-3.5 w-3.5" />
                    <span>CORRELATED</span>
                  </span>
                ) : (
                  <span className="text-amber-400 font-semibold flex items-center space-x-1">
                    <AlertTriangle className="h-3.5 w-3.5" />
                    <span>NOT_FOUND</span>
                  </span>
                )}
              </div>
              <p className="text-slate-400 text-[11px]">
                Target verified against persistent SQLite webhook_events and transactions database tables.
              </p>
            </div>

            {/* Check 3 */}
            <div className="bg-[#0e1424] border border-slate-800 p-4 rounded-xl text-xs space-y-2">
              <div className="flex items-center justify-between">
                <span className="font-semibold text-slate-300 flex items-center space-x-1.5">
                  <Link2 className="h-4 w-4 text-cyan-400" />
                  <span>3. Predecessor Linkage</span>
                </span>
                {checks.predecessor_linkage ? (
                  <span className="text-emerald-400 font-semibold flex items-center space-x-1">
                    <CheckCircle2 className="h-3.5 w-3.5" />
                    <span>LINKED_OK</span>
                  </span>
                ) : (
                  <span className="text-amber-400 font-semibold flex items-center space-x-1">
                    <AlertTriangle className="h-3.5 w-3.5" />
                    <span>UNVERIFIED</span>
                  </span>
                )}
              </div>
              <p className="text-slate-400 text-[11px]">
                Previous hash matches immediate prior block current_hash in the continuous active ledger.
              </p>
            </div>

            {/* Check 4 */}
            <div className="bg-[#0e1424] border border-slate-800 p-4 rounded-xl text-xs space-y-2">
              <div className="flex items-center justify-between">
                <span className="font-semibold text-slate-300 flex items-center space-x-1.5">
                  <ShieldCheck className="h-4 w-4 text-emerald-400" />
                  <span>4. Entire Chain Integrity</span>
                </span>
                {checks.chain_integrity ? (
                  <span className="text-emerald-400 font-semibold flex items-center space-x-1">
                    <CheckCircle2 className="h-3.5 w-3.5" />
                    <span>UNBROKEN</span>
                  </span>
                ) : (
                  <span className="text-rose-400 font-semibold flex items-center space-x-1">
                    <XCircle className="h-3.5 w-3.5" />
                    <span>ERRORS_FOUND</span>
                  </span>
                )}
              </div>
              <p className="text-slate-400 text-[11px]">
                Full hash chain audit from genesis (Event #0) up to current ledger head.
              </p>
            </div>

            {/* Check 5 */}
            <div className="bg-[#0e1424] border border-slate-800 p-4 rounded-xl text-xs space-y-2">
              <div className="flex items-center justify-between">
                <span className="font-semibold text-slate-300 flex items-center space-x-1.5">
                  <FileKey className="h-4 w-4 text-cyan-400" />
                  <span>5. Source Authentication</span>
                </span>
                {checks.source_authentication ? (
                  <span className="text-emerald-400 font-semibold flex items-center space-x-1">
                    <CheckCircle2 className="h-3.5 w-3.5" />
                    <span>VERIFIED</span>
                  </span>
                ) : (
                  <span className="text-amber-400 font-semibold flex items-center space-x-1">
                    <AlertTriangle className="h-3.5 w-3.5" />
                    <span>UNAUTHENTICATED</span>
                  </span>
                )}
              </div>
              <p className="text-slate-400 text-[11px]">
                Originating PayPal webhook signature verified via PayPal API Certificate Chain & TLS endpoints.
              </p>
            </div>

            {/* Check 6 */}
            <div className="bg-[#0e1424] border border-slate-800 p-4 rounded-xl text-xs space-y-2">
              <div className="flex items-center justify-between">
                <span className="font-semibold text-slate-300 flex items-center space-x-1.5">
                  <Layers className="h-4 w-4 text-purple-400" />
                  <span>6. Canonical Serialization</span>
                </span>
                <span className="text-cyan-400 font-mono font-semibold">
                  v{result.canonical_version || '1.0'} NFC
                </span>
              </div>
              <p className="text-slate-400 text-[11px]">
                Normalized recursive Unicode NFC formatting and strict duplicate key elimination (F-01, F-02).
              </p>
            </div>
          </div>

          {/* Cryptographic Hashes Details Card */}
          <div className="bg-[#0e1424] border border-slate-800 rounded-xl p-5 space-y-4 text-xs">
            <h4 className="text-sm font-semibold text-white">Cryptographic Proof Signatures</h4>
            <div className="space-y-3 font-mono">
              <div>
                <span className="text-slate-500 text-[11px] block mb-1">Target Current Hash (SHA-256)</span>
                <div className="bg-slate-950 p-2.5 rounded-lg border border-slate-800 text-cyan-300 break-all select-all">
                  {result.current_hash}
                </div>
              </div>
              <div>
                <span className="text-slate-500 text-[11px] block mb-1">Previous Link Hash (predecessor)</span>
                <div className="bg-slate-950 p-2.5 rounded-lg border border-slate-800 text-slate-300 break-all select-all">
                  {result.previous_hash}
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

