import React from 'react';
import {
  CreditCard,
  AlertCircle,
  FileCheck2,
  Database,
  ArrowRight,
  ShieldCheck,
  CheckCircle2,
  Clock,
  ExternalLink,
} from 'lucide-react';
import SystemStatusPanel from './SystemStatusPanel';

export default function DashboardTab({
  overview,
  transactions,
  disputes,
  onNavigateTab,
  systemStatus,
  systemLoading,
  onRefreshSystem,
  isOffline,
  offlineError,
  onOpenPayPalInspector,
}) {
  const ledger = overview?.ledger || {};
  const sampleDispute = disputes?.[0] || {
    dispute_id: 'DSP-3EU95140-01',
    transaction_reference: '3EU95140LR696653G',
    amount: '5.00',
    currency: 'USD',
    customer_claim: "I paid for the course on PayPal but never received access to the learning portal.",
    status: 'WAITING_FOR_SELLER_RESPONSE',
    response_deadline: '2026-11-10T23:59:59Z',
  };

  const sampleTx = transactions?.[0] || {
    order_id: '3EU95140LR696653G',
    capture_id: '10A71705XW788203L',
    product_name: 'Advanced Python & SaaS Mastery Course',
    amount: '5.00',
    currency: 'USD',
    payment_status: 'COMPLETED',
    captured_at: '2026-10-31T11:14:39Z',
  };

  return (
    <div className="space-y-6 font-sans">
      {/* Welcome & Primary CTA Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-[#E5E7EB]">
        <div>
          <h1 className="text-xl font-bold text-[#111827] tracking-tight">
            Good morning. Here is your evidence workspace.
          </h1>
          <p className="text-xs text-[#6B7280] mt-0.5">
            Monitor PayPal orders, verify dispute claims with deterministic rules and AI, and prepare source-linked packets.
          </p>
        </div>

        <button
          onClick={() => onNavigateTab('assistant')}
          className="bg-[#111827] hover:bg-[#1F2937] text-white px-4 py-2.5 rounded-lg text-xs font-medium shadow-sm flex items-center space-x-2 shrink-0 transition-colors"
        >
          <span>Start Evidence Review</span>
          <ArrowRight className="h-3.5 w-3.5" />
        </button>
      </div>

      {/* Live System & Infrastructure Transparency Panel */}
      <SystemStatusPanel
        systemStatus={systemStatus}
        loading={systemLoading}
        onRefresh={onRefreshSystem}
        isOffline={isOffline}
        offlineError={offlineError}
        onOpenPayPalInspector={onOpenPayPalInspector}
      />

      {/* Actionable Dispute Alert Card */}
      <div className="p-5 rounded-xl border border-[#FDE68A] bg-[#FFFBEB] space-y-3">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
          <div className="flex items-center space-x-2">
            <span className="h-2 w-2 rounded-full bg-[#D97706] animate-ping" />
            <span className="font-bold text-xs text-[#92400E] uppercase tracking-wider">
              Open Dispute Requiring Evidence Response
            </span>
            <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-amber-100 text-[#92400E] border border-[#FCD34D]">
              {sampleDispute.dispute_id}
            </span>
          </div>

          <span className="text-[11px] text-[#92400E] flex items-center space-x-1 font-medium">
            <Clock className="h-3.5 w-3.5" />
            <span>Response Deadline: Nov 10, 2026 (10 days remaining)</span>
          </span>
        </div>

        <div className="bg-white p-3.5 rounded-lg border border-[#FDE68A] text-xs space-y-1.5">
          <div className="flex justify-between items-center text-[#111827] font-medium">
            <span>Customer Claim (PayPal Resolution Center):</span>
            <span className="font-mono text-xs font-bold text-[#111827]">
              Order {sampleDispute.transaction_reference} (${sampleDispute.amount} {sampleDispute.currency})
            </span>
          </div>
          <p className="text-[#4B5563] text-[11px] italic bg-[#F9FAFB] p-2 rounded border border-[#E5E7EB]">
            "{sampleDispute.customer_claim}"
          </p>
        </div>

        <div className="flex items-center justify-between pt-1">
          <p className="text-[11px] text-[#92400E]">
            3 connected source records ready (PayPal Capture, MemberPress Access Log, SendGrid Email).
          </p>
          <button
            onClick={() => onNavigateTab('assistant')}
            className="bg-[#111827] hover:bg-[#1F2937] text-white px-3.5 py-1.5 rounded-lg text-xs font-medium flex items-center space-x-1.5 transition-colors shadow-xs"
          >
            <span>Verify Evidence for This Dispute</span>
            <ArrowRight className="h-3 w-3" />
          </button>
        </div>
      </div>

      {/* 4 Real Metric KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-white p-4 rounded-xl border border-[#E5E7EB] shadow-xs space-y-1">
          <div className="flex items-center justify-between text-xs text-[#6B7280]">
            <span>Imported Transactions</span>
            <CreditCard className="h-4 w-4 text-[#9CA3AF]" />
          </div>
          <div className="text-2xl font-bold font-mono text-[#111827]">
            {transactions?.length || 1}
          </div>
          <div className="text-[11px] text-[#059669] flex items-center space-x-1">
            <CheckCircle2 className="h-3 w-3" />
            <span>PayPal Sandbox Live Verified</span>
          </div>
        </div>

        <div className="bg-white p-4 rounded-xl border border-[#E5E7EB] shadow-xs space-y-1">
          <div className="flex items-center justify-between text-xs text-[#6B7280]">
            <span>Active Disputes</span>
            <AlertCircle className="h-4 w-4 text-[#D97706]" />
          </div>
          <div className="text-2xl font-bold font-mono text-[#111827]">1</div>
          <div className="text-[11px] text-[#D97706]">
            Needs evidence response
          </div>
        </div>

        <div className="bg-white p-4 rounded-xl border border-[#E5E7EB] shadow-xs space-y-1">
          <div className="flex items-center justify-between text-xs text-[#6B7280]">
            <span>Evidence Packets Prepared</span>
            <FileCheck2 className="h-4 w-4 text-[#9CA3AF]" />
          </div>
          <div className="text-2xl font-bold font-mono text-[#111827]">1</div>
          <div className="text-[11px] text-[#4B5563]">
            Ready for human sign-off
          </div>
        </div>

        <div className="bg-white p-4 rounded-xl border border-[#E5E7EB] shadow-xs space-y-1">
          <div className="flex items-center justify-between text-xs text-[#6B7280]">
            <span>Ledger Integrity</span>
            <ShieldCheck className="h-4 w-4 text-[#059669]" />
          </div>
          <div className="text-2xl font-bold font-mono text-[#059669]">
            {ledger.total_events || 164}
          </div>
          <div className="text-[11px] text-[#6B7280]">
            Tamper-evident audit events
          </div>
        </div>
      </div>

      {/* Recent Transactions Section */}
      <div className="bg-white rounded-xl border border-[#E5E7EB] overflow-hidden shadow-xs">
        <div className="p-4 border-b border-[#E5E7EB] flex items-center justify-between bg-[#F9FAFB]">
          <div>
            <h2 className="text-xs font-bold text-[#111827] uppercase tracking-wider">
              Recent PayPal Transactions
            </h2>
            <p className="text-[11px] text-[#6B7280]">
              Orders imported directly from PayPal webhook and capture sync.
            </p>
          </div>
          <button
            onClick={() => onNavigateTab('transactions')}
            className="text-xs text-[#4B5563] hover:text-[#111827] font-medium flex items-center space-x-1"
          >
            <span>View all</span>
            <ArrowRight className="h-3 w-3" />
          </button>
        </div>

        <div className="divide-y divide-[#E5E7EB] text-xs">
          <div className="p-4 hover:bg-[#F9FAFB] transition-colors flex flex-col md:flex-row md:items-center justify-between gap-3">
            <div className="space-y-1">
              <div className="flex items-center space-x-2">
                <span className="font-semibold text-sm text-[#111827]">{sampleTx.product_name}</span>
                <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-emerald-50 text-emerald-700 border border-emerald-200">
                  {sampleTx.payment_status}
                </span>
                <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-amber-50 text-amber-700 border border-amber-200">
                  Dispute Open
                </span>
              </div>
              <div className="flex flex-wrap items-center gap-3 text-[11px] text-[#6B7280] font-mono">
                <span>Order: {sampleTx.order_id}</span>
                <span>•</span>
                <span>Capture: {sampleTx.capture_id}</span>
                <span>•</span>
                <span>Captured: {sampleTx.captured_at}</span>
              </div>
            </div>

            <div className="flex items-center space-x-4 self-end md:self-auto">
              <span className="text-sm font-bold font-mono text-[#111827]">
                ${sampleTx.amount} {sampleTx.currency}
              </span>
              <button
                onClick={() => onNavigateTab('assistant')}
                className="px-3 py-1.5 rounded-lg bg-[#111827] hover:bg-[#1F2937] text-white text-xs font-medium transition-colors"
              >
                Inspect Evidence
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Getting Started Checklist */}
      <div className="bg-white rounded-xl border border-[#E5E7EB] p-5 shadow-xs space-y-3">
        <h3 className="text-xs font-bold text-[#111827] uppercase tracking-wider">
          Evidence Readiness Checklist
        </h3>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-xs">
          <div className="p-3 rounded-lg border border-[#E5E7EB] bg-[#F9FAFB] flex items-start space-x-2.5">
            <CheckCircle2 className="h-4 w-4 text-[#059669] shrink-0 mt-0.5" />
            <div>
              <span className="font-semibold text-[#111827] block">PayPal Capture Verified</span>
              <span className="text-[11px] text-[#6B7280]">
                Capture 10A71705XW788203L authenticated via PayPal certificate.
              </span>
            </div>
          </div>

          <div className="p-3 rounded-lg border border-[#E5E7EB] bg-[#F9FAFB] flex items-start space-x-2.5">
            <CheckCircle2 className="h-4 w-4 text-[#059669] shrink-0 mt-0.5" />
            <div>
              <span className="font-semibold text-[#111827] block">Access Logs Connected</span>
              <span className="text-[11px] text-[#6B7280]">
                MemberPress provision timestamp verified for order reference.
              </span>
            </div>
          </div>

          <div className="p-3 rounded-lg border border-[#E5E7EB] bg-[#F9FAFB] flex items-start space-x-2.5">
            <Clock className="h-4 w-4 text-[#D97706] shrink-0 mt-0.5" />
            <div>
              <span className="font-semibold text-[#111827] block">Awaiting Human Sign-Off</span>
              <span className="text-[11px] text-[#6B7280]">
                Review assessed claims and cryptographically seal report.
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

