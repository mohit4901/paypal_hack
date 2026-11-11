import React, { useState, useEffect } from 'react';
import { Anchor, Plus, CheckCircle2, XCircle, ShieldCheck, Clock } from 'lucide-react';
import { api } from '../api';

export default function CheckpointsTab() {
  const [checkpoints, setCheckpoints] = useState([]);
  const [loading, setLoading] = useState(false);
  const [creating, setCreating] = useState(false);
  const [createMsg, setCreateMsg] = useState(null);

  const loadCheckpoints = async () => {
    setLoading(true);
    try {
      const res = await api.getCheckpoints();
      setCheckpoints(res.checkpoints || []);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleCreate = async () => {
    setCreating(true);
    setCreateMsg(null);
    try {
      const res = await api.createCheckpoint('v1-sandbox-202610');
      setCreateMsg({ success: true, text: `Created checkpoint: ${res.file}` });
      loadCheckpoints();
    } catch (err) {
      setCreateMsg({ success: false, text: err.message || 'Creation failed' });
    } finally {
      setCreating(false);
    }
  };

  useEffect(() => {
    loadCheckpoints();
  }, []);

  return (
    <div className="space-y-6">
      <div className="bg-[#0e1424] border border-slate-800 rounded-xl p-5 flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h2 className="text-base font-bold text-white mb-1">
            External Cryptographic Checkpoints
          </h2>
          <p className="text-xs text-slate-400">
            Checkpoints anchored outside the primary ledger directory to protect against coordinated replacement attacks.
          </p>
        </div>
        <button
          onClick={handleCreate}
          disabled={creating}
          className="px-4 py-2.5 rounded-xl bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-400 hover:to-blue-500 text-white font-medium text-xs shadow-lg shadow-cyan-500/20 disabled:opacity-50 transition-all shrink-0 flex items-center space-x-1.5"
        >
          <Plus className="h-4 w-4" />
          <span>{creating ? 'Anchoring Checkpoint...' : 'Anchor New Checkpoint'}</span>
        </button>
      </div>

      {createMsg && (
        <div
          className={`p-3 rounded-xl border text-xs flex items-center space-x-2 ${
            createMsg.success
              ? 'bg-emerald-950/40 border-emerald-800/60 text-emerald-300'
              : 'bg-rose-950/40 border-rose-800/60 text-rose-300'
          }`}
        >
          {createMsg.success ? <CheckCircle2 className="h-4 w-4" /> : <XCircle className="h-4 w-4" />}
          <span>{createMsg.text}</span>
        </div>
      )}

      {/* Checkpoint list */}
      <div className="space-y-3">
        <h3 className="text-sm font-semibold text-white">Anchored Integrity Checkpoints</h3>

        {checkpoints.length === 0 ? (
          <div className="bg-[#0e1424] border border-slate-800 rounded-xl p-8 text-center text-xs text-slate-500">
            No external checkpoints anchored yet. Click "Anchor New Checkpoint" to create the first external anchor.
          </div>
        ) : (
          checkpoints.map((cp, idx) => (
            <div
              key={cp._filename || idx}
              className="bg-[#0e1424] border border-slate-800 rounded-xl p-4 text-xs space-y-3 hover:border-slate-700 transition-colors"
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-2">
                  <Anchor className="h-4 w-4 text-cyan-400" />
                  <span className="font-mono text-white font-semibold">{cp._filename}</span>
                  <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-cyan-950 text-cyan-300 border border-cyan-800">
                    Height: {cp.total_events} events
                  </span>
                </div>
                {cp._is_valid ? (
                  <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-emerald-950 text-emerald-400 border border-emerald-800">
                    DIGEST_VERIFIED
                  </span>
                ) : (
                  <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-rose-950 text-rose-400 border border-rose-800">
                    CHECKPOINT_MISMATCH
                  </span>
                )}
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-2 font-mono text-[11px]">
                <div className="bg-slate-950 p-2 rounded border border-slate-800">
                  <span className="text-slate-500 block text-[10px]">HEAD_HASH_AT_CHECKPOINT</span>
                  <span className="text-slate-300 break-all select-all">{cp.head_hash}</span>
                </div>
                <div className="bg-slate-950 p-2 rounded border border-slate-800">
                  <span className="text-slate-500 block text-[10px]">CHECKPOINT_DIGEST (SHA-256)</span>
                  <span className="text-cyan-400 break-all select-all">{cp.checkpoint_digest}</span>
                </div>
              </div>

              <div className="flex items-center justify-between text-[11px] text-slate-500 pt-1">
                <span>Key ID: {cp.signing?.key_id || 'v1-sandbox-202610'}</span>
                <span>Timestamp: {cp.checkpoint_timestamp}</span>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}

