import React, { useState, useEffect } from 'react';
import { KeyRound, ShieldAlert, CheckCircle2, History, AlertOctagon } from 'lucide-react';
import { api } from '../api';

export default function KeysTab() {
  const [keys, setKeys] = useState([]);
  const [policy, setPolicy] = useState({});
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      try {
        const data = await api.getKeys();
        setKeys(data.keys || []);
        setPolicy(data.governance_policy || {});
      } catch (err) {
        console.error(err);
      } finally {
        setLoading(false);
      }
    };
    load();
  }, []);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="bg-[#0e1424] border border-slate-800 rounded-xl p-5">
        <div className="flex items-center space-x-3 mb-1">
          <div className="h-8 w-8 rounded-lg bg-cyan-500/10 border border-cyan-500/30 flex items-center justify-center text-cyan-400">
            <KeyRound className="h-4 w-4" />
          </div>
          <div>
            <h2 className="text-base font-bold text-white">Cryptographic Key Lifecycle Governance</h2>
            <p className="text-xs text-slate-400">
              Finding F-04 Remediation: Tri-state key status (ACTIVE, RETIRED, REVOKED) with strict signature verification rules.
            </p>
          </div>
        </div>
      </div>

      {/* Governance Policies Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs">
        <div className="bg-emerald-950/20 border border-emerald-800/40 p-4 rounded-xl space-y-2">
          <div className="flex items-center space-x-2 text-emerald-400 font-semibold">
            <CheckCircle2 className="h-4 w-4" />
            <span>ACTIVE STATUS</span>
          </div>
          <p className="text-slate-300 text-[11px] leading-relaxed">
            Authorized to sign new manifests and external checkpoints. Signatures pass full trust authentication.
          </p>
        </div>

        <div className="bg-blue-950/20 border border-blue-800/40 p-4 rounded-xl space-y-2">
          <div className="flex items-center space-x-2 text-blue-400 font-semibold">
            <History className="h-4 w-4" />
            <span>RETIRED STATUS</span>
          </div>
          <p className="text-slate-300 text-[11px] leading-relaxed">
            Cannot sign new manifests. Strictly accepted for historical manifests signed before the retirement date.
          </p>
        </div>

        <div className="bg-rose-950/20 border border-rose-800/40 p-4 rounded-xl space-y-2">
          <div className="flex items-center space-x-2 text-rose-400 font-semibold">
            <AlertOctagon className="h-4 w-4" />
            <span>REVOKED STATUS</span>
          </div>
          <p className="text-slate-300 text-[11px] leading-relaxed">
            Compromised key. Even if HMAC mathematically matches, the manifest trust verdict is set to COMPROMISED.
          </p>
        </div>
      </div>

      {/* Key Registry Table */}
      <div className="space-y-3">
        <h3 className="text-sm font-semibold text-white">Registered Cryptographic Signing Keys</h3>

        <div className="space-y-3">
          {keys.map((k) => {
            const isRevoked = k.status === 'REVOKED';
            const isRetired = k.status === 'RETIRED';

            return (
              <div
                key={k.key_id}
                className={`bg-[#0e1424] border rounded-xl p-4 text-xs space-y-2.5 transition-colors ${
                  isRevoked
                    ? 'border-rose-900/60 bg-rose-950/10'
                    : isRetired
                    ? 'border-blue-900/60'
                    : 'border-slate-800 hover:border-slate-700'
                }`}
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-2">
                    <span className="font-mono text-cyan-300 font-bold">{k.key_id}</span>
                    <span
                      className={`px-2 py-0.5 rounded text-[10px] font-mono font-semibold ${
                        isRevoked
                          ? 'bg-rose-950 text-rose-300 border border-rose-800'
                          : isRetired
                          ? 'bg-blue-950 text-blue-300 border border-blue-800'
                          : 'bg-emerald-950 text-emerald-300 border border-emerald-800'
                      }`}
                    >
                      {k.status}
                    </span>
                  </div>
                  <span className="text-[11px] text-slate-500 font-mono">Algorithm: HMAC-SHA256</span>
                </div>

                <p className="text-slate-300 text-[11px]">{k.description}</p>

                {k.revocation_reason && (
                  <div className="p-2 rounded bg-rose-950/40 border border-rose-800/60 text-[11px] text-rose-300">
                    <strong>Revocation Reason:</strong> {k.revocation_reason}
                  </div>
                )}

                <div className="flex flex-wrap items-center gap-4 text-[11px] text-slate-500 font-mono pt-1 border-t border-slate-800/60">
                  <span>Activated: {k.activated_at || 'N/A'}</span>
                  {k.retired_at && <span>Retired: {k.retired_at}</span>}
                  {k.revoked_at && <span>Revoked: {k.revoked_at}</span>}
                  <span className="text-slate-400">Secret: [REDACTED_SECURE_STORAGE]</span>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

