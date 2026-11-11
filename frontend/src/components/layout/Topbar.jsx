import React from 'react';
import { Menu, RefreshCw, AlertTriangle, Cpu, Activity } from 'lucide-react';

export default function Topbar({
  onOpenMobileMenu,
  onRefresh,
  loading,
  systemStatus,
  isOffline,
  onOpenSystemModal,
}) {
  const aiModel = systemStatus?.ai_model || {};
  const aiLoaded = aiModel.status === 'MODEL_LOADED' && aiModel.is_loaded !== false;
  const paypalAuth = systemStatus?.paypal?.auth_status === 'AUTHENTICATED';

  return (
    <header className="sticky top-0 z-10 bg-[#FCFBF8]/95 backdrop-blur-xs border-b border-[#E6E4DD] px-4 sm:px-6 lg:px-8 h-14 flex items-center justify-between gap-3">
      <div className="flex items-center gap-3 min-w-0">
        <button
          type="button"
          onClick={onOpenMobileMenu}
          aria-label="Open navigation menu"
          className="lg:hidden p-2 -ml-2 rounded-lg text-[#3F3F46] hover:bg-[#EFECE4] transition-colors"
        >
          <Menu className="w-5 h-5" />
        </button>

        <div className="flex items-center gap-2 lg:hidden">
          <span className="text-xs font-bold tracking-[0.08em] text-[#18181B] uppercase">
            PROOFLEDGER
          </span>
        </div>

        <div className="hidden sm:flex items-center gap-2 text-xs text-[#52525B]">
          <span className="font-medium text-[#18181B]">Evidence Verification Workspace</span>
          <span className="text-[#D4D4D8]">/</span>
          <span className="text-[#71717A] truncate">Deterministic Rules + Advisory NLI</span>
        </div>
      </div>

      <div className="flex items-center gap-2 shrink-0">
        {isOffline ? (
          <button
            type="button"
            onClick={onOpenSystemModal}
            className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-medium bg-rose-50 text-rose-800 border border-rose-200 hover:bg-rose-100 transition-colors"
          >
            <AlertTriangle className="w-3.5 h-3.5" />
            <span>Backend Offline</span>
          </button>
        ) : !aiLoaded && systemStatus ? (
          <button
            type="button"
            onClick={onOpenSystemModal}
            className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-medium bg-rose-50 text-rose-800 border border-rose-200 hover:bg-rose-100 transition-colors"
          >
            <AlertTriangle className="w-3.5 h-3.5" />
            <span>MODEL_UNAVAILABLE</span>
          </button>
        ) : (
          <button
            type="button"
            onClick={onOpenSystemModal}
            className="hidden md:inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-medium bg-white text-[#3F3F46] border border-[#E6E4DD] hover:border-[#0F766E]/40 transition-colors"
            title={aiModel.loaded_model_path || 'Inspect AI and system health'}
          >
            <Cpu className="w-3.5 h-3.5 text-[#0F766E]" />
            <span>{aiLoaded ? 'DeBERTa Candidate Active' : 'Checking AI...'}</span>
          </button>
        )}

        <button
          type="button"
          onClick={onOpenSystemModal}
          className={`hidden sm:inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-medium border transition-colors ${
            paypalAuth
              ? 'bg-emerald-50 text-emerald-800 border-emerald-200'
              : 'bg-stone-100 text-stone-700 border-stone-200'
          }`}
        >
          <Activity className="w-3.5 h-3.5" />
          <span>{paypalAuth ? 'PayPal Sandbox Live' : 'Sandbox Pending'}</span>
        </button>

        {onRefresh && (
          <button
            type="button"
            onClick={onRefresh}
            disabled={loading}
            aria-label="Refresh workspace data"
            className="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-medium bg-white text-[#18181B] border border-[#E6E4DD] hover:bg-[#F8F7F3] disabled:opacity-50 transition-colors"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
            <span className="hidden sm:inline">Refresh</span>
          </button>
        )}
      </div>
    </header>
  );
}

