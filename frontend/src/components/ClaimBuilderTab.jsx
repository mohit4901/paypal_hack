import React, { useState } from 'react';
import {
  ListCheck,
  Plus,
  Trash2,
  ArrowRight,
  HelpCircle,
  CheckCircle2,
  Sparkles,
} from 'lucide-react';

const SUGGESTED_TEMPLATES = [
  "Payment of 5.00 USD was successfully captured for Order 3EU95140LR696653G",
  "Course portal access was provisioned to buyer email sb-rcnwy53637793@personal.example.com",
  "Access credentials email was successfully delivered to buyer's registered email address",
  "Customer confirmed download and offline usage of course files",
  "Digital software license key was successfully activated on customer device",
];

export default function ClaimBuilderTab({
  claims,
  onAddClaim,
  onRemoveClaim,
  onRunVerification,
  loading,
}) {
  const [newClaimText, setNewClaimText] = useState('');

  const handleAdd = (e) => {
    e.preventDefault();
    if (!newClaimText.trim()) return;
    onAddClaim(newClaimText.trim());
    setNewClaimText('');
  };

  return (
    <div className="space-y-6 font-sans">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-[#E5E7EB]">
        <div>
          <h1 className="text-xl font-bold text-[#111827] tracking-tight">
            Claim Builder
          </h1>
          <p className="text-xs text-[#6B7280] mt-0.5">
            What factual statements do you need to establish to resolve this PayPal dispute?
          </p>
        </div>

        <button
          onClick={onRunVerification}
          disabled={loading || claims.length === 0}
          className="bg-[#111827] hover:bg-[#1F2937] text-white px-5 py-2.5 rounded-lg text-xs font-medium shadow-sm flex items-center space-x-2 shrink-0 transition-colors disabled:opacity-40"
        >
          <Sparkles className="h-3.5 w-3.5" />
          <span>{loading ? 'Evaluating Claims...' : 'Run Factual Verification'}</span>
          <ArrowRight className="h-3.5 w-3.5" />
        </button>
      </div>

      {/* Guidance Banner */}
      <div className="p-4 rounded-xl border border-[#E5E7EB] bg-[#F9FAFB] text-xs space-y-1.5">
        <span className="font-semibold text-[#111827] block">Independent Claim Rule</span>
        <p className="text-[#4B5563] text-[11px] leading-relaxed">
          Every dispute claim is evaluated independently against your attached evidence.
          Payment proof does not prove delivery, and access logs do not prove file download.
          Only claim what your records can legitimately substantiate.
        </p>
      </div>

      {/* Claims List */}
      <div className="space-y-3">
        <div className="flex items-center justify-between text-xs">
          <h3 className="font-bold text-[#111827] uppercase tracking-wider text-[11px]">
            Claims for Evaluation ({claims.length})
          </h3>
          <span className="text-[#6B7280]">Each evaluated by deterministic checks + NLI</span>
        </div>

        <div className="space-y-2.5">
          {claims.map((c, i) => (
            <div
              key={i}
              className="bg-white p-4 rounded-xl border border-[#E5E7EB] shadow-xs flex items-center justify-between gap-4 hover:border-[#D1D5DB] transition-colors"
            >
              <div className="flex items-start space-x-3">
                <span className="h-5 w-5 rounded-full bg-[#F3F4F6] text-[#6B7280] font-mono text-[10px] font-bold flex items-center justify-center shrink-0 mt-0.5">
                  {i + 1}
                </span>
                <div>
                  <span className="text-xs font-medium text-[#111827] block leading-relaxed">
                    {c}
                  </span>
                  <span className="text-[10px] text-[#9CA3AF]">
                    Factual dispute statement
                  </span>
                </div>
              </div>

              {claims.length > 1 && (
                <button
                  onClick={() => onRemoveClaim(i)}
                  className="text-[#9CA3AF] hover:text-[#EF4444] p-1 rounded transition-colors"
                  title="Remove claim"
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* Add Custom Claim Input */}
      <div className="bg-white p-4 rounded-xl border border-[#E5E7EB] shadow-xs space-y-3">
        <h4 className="text-xs font-bold text-[#111827] uppercase tracking-wider">
          Add Custom Dispute Claim
        </h4>
        <form onSubmit={handleAdd} className="flex gap-2">
          <input
            type="text"
            value={newClaimText}
            onChange={(e) => setNewClaimText(e.target.value)}
            placeholder="e.g. Customer logged in to view course module 1 on 2026-10-31..."
            className="flex-1 px-3 py-2 border border-[#D1D5DB] rounded-lg text-xs focus:outline-none focus:border-[#111827]"
          />
          <button
            type="submit"
            className="px-4 py-2 bg-[#111827] hover:bg-[#1F2937] text-white text-xs font-medium rounded-lg shrink-0 flex items-center space-x-1"
          >
            <Plus className="h-3.5 w-3.5" />
            <span>Add Claim</span>
          </button>
        </form>
      </div>

      {/* Quick Suggested Templates */}
      <div className="bg-white p-4 rounded-xl border border-[#E5E7EB] shadow-xs space-y-2.5">
        <span className="text-xs font-bold text-[#111827] uppercase tracking-wider block">
          Recommended Digital Goods Claim Templates
        </span>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-2 text-xs">
          {SUGGESTED_TEMPLATES.map((tmpl, idx) => (
            <button
              key={idx}
              onClick={() => onAddClaim(tmpl)}
              className="text-left p-2.5 rounded-lg border border-[#E5E7EB] hover:bg-[#F9FAFB] hover:border-[#111827] transition-all text-[11px] text-[#374151]"
            >
              + {tmpl}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}

