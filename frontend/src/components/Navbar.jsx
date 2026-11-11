import React from 'react';
import { ShieldCheck, RefreshCw, ExternalLink, Activity, ArrowRight, HelpCircle } from 'lucide-react';

export default function Navbar({
  onRefresh,
  loading,
  onStartVerification,
  onOpenLanding,
  onOpenOnboarding,
  storeProfile,
  systemStatus,
  isOffline,
  onOpenSystemStatus,
}) {
  const isOperational = systemStatus?.overall_status === 'OPERATIONAL';
  const paypalAuth = systemStatus?.paypal?.auth_status === 'AUTHENTICATED';

  return (
    <header className="bg-white border-b border-[#E5E7EB] px-6 py-3.5 flex items-center justify-between sticky top-0 z-30 font-sans">
      <div className="flex items-center space-x-4">
        <button
          onClick={onOpenLanding}
          className="flex items-center space-x-3 focus:outline-none group text-left"
        >
          <img
            src="/logo-icon.png"
            alt="ProofLedger"
            className="h-8 w-8 object-contain"
          />
          <div>
            <div className="flex items-center space-x-2">
              <span className="font-bold text-sm tracking-tight text-[#111827]">ProofLedger</span>
              <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-blue-50 text-blue-800 border border-blue-200">
                Dispute Rescue
              </span>
            </div>
            <p className="text-[11px] text-[#6B7280]">
              Turn a PayPal dispute into an evidence-ready response
            </p>
          </div>
        </button>
      </div>

      <div className="flex items-center space-x-3 text-xs">
        {/* Dynamic Live Status Badge */}
        <button
          onClick={onOpenSystemStatus}
          className={`flex items-center space-x-2 px-2.5 py-1 rounded-md border text-xs transition-colors ${
            isOffline
              ? 'bg-rose-50 border-rose-200 text-rose-700 hover:bg-rose-100'
              : isOperational
              ? 'bg-[#F9FAFB] border-[#E5E7EB] text-[#4B5563] hover:bg-[#F3F4F6]'
              : 'bg-amber-50 border-amber-200 text-amber-800 hover:bg-amber-100'
          }`}
          title="Click to inspect live backend, database, PayPal, and AI engine status"
        >
          <div
            className={`h-2 w-2 rounded-full ${
              isOffline
                ? 'bg-rose-500'
                : isOperational
                ? 'bg-[#10B981] animate-pulse'
                : 'bg-amber-500'
            }`}
          />
          <span className="font-medium">
            {isOffline
              ? 'Backend Offline'
              : paypalAuth
              ? 'PayPal Sandbox: Connected'
              : 'System: Initializing'}
          </span>
          <span className="text-[10px] text-[#9CA3AF] underline font-sans ml-1">Readiness</span>
        </button>

        {/* Setup Wizard */}
        <button
          onClick={onOpenOnboarding}
          className="hidden sm:flex items-center space-x-1 px-2.5 py-1 text-xs text-[#4B5563] hover:text-[#111827] rounded-md hover:bg-[#F3F4F6] transition-colors"
        >
          <HelpCircle className="h-3.5 w-3.5" />
          <span>Setup</span>
        </button>

        {/* Refresh */}
        <button
          onClick={onRefresh}
          disabled={loading}
          className="p-1.5 text-[#4B5563] hover:text-[#111827] rounded-md hover:bg-[#F3F4F6] transition-colors disabled:opacity-40"
          title="Refresh Data"
        >
          <RefreshCw className={`h-3.5 w-3.5 ${loading ? 'animate-spin text-[#111827]' : ''}`} />
        </button>

        {/* Primary Action Button */}
        <button
          onClick={onStartVerification}
          className="bg-[#111827] hover:bg-[#1F2937] text-white px-3.5 py-1.5 rounded-lg font-medium text-xs shadow-sm flex items-center space-x-1.5 transition-colors"
        >
          <span>New Verification</span>
          <ArrowRight className="h-3 w-3" />
        </button>
      </div>
    </header>
  );
}
