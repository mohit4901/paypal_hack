import React from 'react';
import {
  ShieldCheck,
  ArrowRight,
  FileText,
  CheckCircle2,
  AlertTriangle,
  Layers,
  Database,
  Lock,
  ExternalLink,
} from 'lucide-react';

export default function LandingPage({ onGetStarted, onTryDemo }) {
  return (
    <div className="min-h-screen bg-white text-[#111827] flex flex-col font-sans">
      {/* Top Navbar */}
      <header className="border-b border-[#E5E7EB] bg-white sticky top-0 z-40">
        <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <img
              src="/logo.png"
              alt="ProofLedger Logo"
              className="h-8 w-auto object-contain"
            />
            <span className="text-xs text-[#6B7280] font-normal hidden sm:inline border-l border-gray-300 pl-3">
              for Digital Goods Sellers
            </span>
          </div>

          <div className="flex items-center space-x-3">
            <button
              onClick={onTryDemo}
              className="text-xs font-medium text-[#4B5563] hover:text-[#111827] px-3 py-2 rounded-lg transition-colors"
            >
              Live Dispute Demo
            </button>
            <button
              onClick={onGetStarted}
              className="text-xs font-medium bg-[#111827] hover:bg-[#1F2937] text-white px-4 py-2 rounded-lg transition-colors flex items-center space-x-1.5 shadow-sm"
            >
              <span>Launch Workspace</span>
              <ArrowRight className="h-3.5 w-3.5" />
            </button>
          </div>
        </div>
      </header>

      {/* Hero Section */}
      <section className="py-20 px-6 max-w-4xl mx-auto text-center">
        <div className="inline-flex items-center space-x-2 px-3 py-1 rounded-full bg-[#F3F4F6] border border-[#E5E7EB] text-[#4B5563] text-xs font-medium mb-6">
          <ShieldCheck className="h-3.5 w-3.5 text-[#111827]" />
          <span>Source-Grounded Evidence Verification for Digital Products</span>
        </div>

        <h1 className="text-4xl sm:text-5xl lg:text-6xl font-bold tracking-tight text-[#111827] leading-[1.15] mb-6">
          Know what your evidence <br className="hidden sm:block" />
          actually proves.
        </h1>

        <p className="text-base sm:text-lg text-[#4B5563] max-w-2xl mx-auto leading-relaxed mb-10">
          Connect payment and delivery records, verify dispute claims with deterministic rules and AI,
          and prepare source-linked evidence packets for PayPal Resolution Center — all in one workspace.
        </p>

        <div className="flex flex-col sm:flex-row items-center justify-center gap-3">
          <button
            onClick={onTryDemo}
            className="w-full sm:w-auto px-6 py-3 rounded-lg bg-[#111827] hover:bg-[#1F2937] text-white font-medium text-sm transition-all shadow-md flex items-center justify-center space-x-2"
          >
            <span>Start $49 Course Dispute Demo</span>
            <ArrowRight className="h-4 w-4" />
          </button>
          <button
            onClick={onGetStarted}
            className="w-full sm:w-auto px-6 py-3 rounded-lg border border-[#D1D5DB] hover:bg-[#F9FAFB] text-[#111827] font-medium text-sm transition-all"
          >
            Open Seller Dashboard
          </button>
        </div>

        <div className="mt-8 text-xs text-[#6B7280]">
          No credit card required. Connects directly to PayPal Sandbox or Live API.
        </div>

        {/* Hero Interactive App Mockup (Inspired by Image 1 & Image 3) */}
        <div className="mt-14 text-left rounded-2xl border border-[#E5E7EB] bg-white shadow-2xl overflow-hidden transition-all hover:shadow-3xl">
          {/* Browser Header Bar */}
          <div className="bg-[#F9FAFB] border-b border-[#E5E7EB] px-4 py-3 flex items-center justify-between">
            <div className="flex items-center space-x-2">
              <div className="h-3 w-3 rounded-full bg-[#EF4444]" />
              <div className="h-3 w-3 rounded-full bg-[#F59E0B]" />
              <div className="h-3 w-3 rounded-full bg-[#10B981]" />
              <span className="ml-3 text-[11px] font-mono text-[#6B7280]">
                https://proofledger.internal/disputes/DSP-3EU95140-01/review
              </span>
            </div>
            <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-50 text-emerald-700 border border-emerald-200 font-semibold">
              SANDBOX LIVE
            </span>
          </div>

          {/* Arthur&Co / Vera Style Evidence Review Assistant Panel */}
          <div className="p-6 sm:p-8 space-y-6">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-4 border-b border-[#E5E7EB]">
              <div>
                <span className="text-[10px] font-bold tracking-widest text-[#9CA3AF] uppercase">
                  Evidence Review Assistant • Run by ProofLedger
                </span>
                <h3 className="text-xl font-bold text-[#111827] tracking-tight mt-0.5">
                  Compliance Verification Results
                </h3>
              </div>
              <button
                onClick={onTryDemo}
                className="self-start sm:self-auto px-3.5 py-1.5 rounded-lg bg-[#111827] text-white text-xs font-medium hover:bg-[#1F2937] transition-colors flex items-center space-x-1.5 shadow-xs"
              >
                <span>Interactive Workspace</span>
                <ArrowRight className="h-3 w-3" />
              </button>
            </div>

            {/* Review Summary Box */}
            <div className="p-4 rounded-xl border border-[#E5E7EB] bg-[#F9FAFB] space-y-2">
              <span className="text-[11px] font-bold tracking-wider text-[#6B7280] uppercase block">
                Review Summary
              </span>
              <p className="text-xs text-[#374151] leading-relaxed">
                Verification completed for Order <span className="font-mono font-semibold text-[#111827]">3EU95140LR696653G</span>.
                3 out of 4 claims are source-grounded. 1 claim is flagged for <strong>missing evidence</strong> (download confirmed).
                Review the proof details below before granting final approval.
              </p>
            </div>

            {/* Mini Claim Rows */}
            <div className="space-y-2.5">
              <div className="p-3.5 rounded-lg border border-[#E5E7EB] bg-white flex items-center justify-between text-xs">
                <div className="flex items-center space-x-3">
                  <CheckCircle2 className="h-4 w-4 text-[#059669] shrink-0" />
                  <span className="text-[#111827] font-medium">Payment of 5.00 USD captured on PayPal</span>
                </div>
                <div className="flex items-center space-x-2">
                  <span className="text-[10px] font-mono text-[#6B7280] hidden md:inline">Source: PayPal Webhook (EV-01)</span>
                  <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-[#ECFDF5] text-[#065F46] border border-[#A7F3D0]">
                    SUPPORTED
                  </span>
                </div>
              </div>

              <div className="p-3.5 rounded-lg border border-[#E5E7EB] bg-white flex items-center justify-between text-xs">
                <div className="flex items-center space-x-3">
                  <CheckCircle2 className="h-4 w-4 text-[#059669] shrink-0" />
                  <span className="text-[#111827] font-medium">Course portal access provisioned to buyer email</span>
                </div>
                <div className="flex items-center space-x-2">
                  <span className="text-[10px] font-mono text-[#6B7280] hidden md:inline">Source: MemberPress LMS (EV-02)</span>
                  <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-[#ECFDF5] text-[#065F46] border border-[#A7F3D0]">
                    SUPPORTED
                  </span>
                </div>
              </div>

              <div className="p-3.5 rounded-lg border border-[#E5E7EB] bg-white flex items-center justify-between text-xs">
                <div className="flex items-center space-x-3">
                  <CheckCircle2 className="h-4 w-4 text-[#059669] shrink-0" />
                  <span className="text-[#111827] font-medium">Access credentials email delivered to customer</span>
                </div>
                <div className="flex items-center space-x-2">
                  <span className="text-[10px] font-mono text-[#6B7280] hidden md:inline">Source: SendGrid SMTP (EV-03)</span>
                  <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-[#ECFDF5] text-[#065F46] border border-[#A7F3D0]">
                    SUPPORTED
                  </span>
                </div>
              </div>

              <div className="p-3.5 rounded-lg border border-amber-200 bg-[#FFFBEB] flex items-center justify-between text-xs">
                <div className="flex items-center space-x-3">
                  <AlertTriangle className="h-4 w-4 text-[#D97706] shrink-0" />
                  <div>
                    <span className="text-[#111827] font-medium">Customer downloaded and used offline files</span>
                    <p className="text-[11px] text-[#92400E] mt-0.5">
                      ⚠️ Access granted ≠ download confirmed. Missing download telemetry.
                    </p>
                  </div>
                </div>
                <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-[#FEF3C7] text-[#92400E] border border-[#FDE68A] shrink-0">
                  INSUFFICIENT EVIDENCE
                </span>
              </div>
            </div>

            <div className="pt-2 flex items-center justify-between text-[11px] text-[#6B7280]">
              <span>Cryptographic Proof: SHA-256 Ledger + DeBERTa NLI Cross-Examination</span>
              <button
                onClick={onTryDemo}
                className="font-medium text-[#111827] hover:underline flex items-center space-x-1"
              >
                <span>Open full interactive verification flow &rarr;</span>
              </button>
            </div>
          </div>
        </div>
      </section>

      {/* The Evidence Reality Check Section */}
      <section className="py-16 bg-[#F9FAFB] border-y border-[#E5E7EB] px-6">
        <div className="max-w-6xl mx-auto">
          <div className="text-center max-w-2xl mx-auto mb-12">
            <h2 className="text-2xl font-bold text-[#111827] tracking-tight">
              Why digital merchants lose PayPal disputes
            </h2>
            <p className="text-xs sm:text-sm text-[#4B5563] mt-2">
              PayPal requires clear proof of digital delivery. But merchants often submit records that don't prove what they think they prove.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            <div className="bg-white p-5 rounded-xl border border-[#E5E7EB] shadow-sm space-y-2">
              <span className="text-xs font-mono font-semibold text-[#EF4444] block">Payment Captured</span>
              <p className="text-xs text-[#111827] font-semibold">≠ Proof of Product Delivery</p>
              <p className="text-[11px] text-[#6B7280] leading-relaxed">
                Money arriving in your PayPal account only proves a transaction occurred, never that the buyer received access.
              </p>
            </div>

            <div className="bg-white p-5 rounded-xl border border-[#E5E7EB] shadow-sm space-y-2">
              <span className="text-xs font-mono font-semibold text-[#EF4444] block">License Key Issued</span>
              <p className="text-xs text-[#111827] font-semibold">≠ Proof of Download</p>
              <p className="text-[11px] text-[#6B7280] leading-relaxed">
                Generating a license key in a database does not prove the customer downloaded or activated the software.
              </p>
            </div>

            <div className="bg-white p-5 rounded-xl border border-[#E5E7EB] shadow-sm space-y-2">
              <span className="text-xs font-mono font-semibold text-[#EF4444] block">Email Sent</span>
              <p className="text-xs text-[#111827] font-semibold">≠ Email Received / Read</p>
              <p className="text-[11px] text-[#6B7280] leading-relaxed">
                A server egress log doesn't prove the customer received or opened the access email without delivery telemetry.
              </p>
            </div>

            <div className="bg-white p-5 rounded-xl border border-[#E5E7EB] shadow-sm space-y-2">
              <span className="text-xs font-mono font-semibold text-[#EF4444] block">User Login Event</span>
              <p className="text-xs text-[#111827] font-semibold">≠ Successful Course Usage</p>
              <p className="text-[11px] text-[#6B7280] leading-relaxed">
                A session token creation does not substantiate that the buyer consumed lessons or received promised digital assets.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* How ProofLedger Works */}
      <section className="py-20 px-6 max-w-5xl mx-auto">
        <div className="text-center max-w-xl mx-auto mb-16">
          <h2 className="text-2xl sm:text-3xl font-bold text-[#111827] tracking-tight">
            How ProofLedger Works
          </h2>
          <p className="text-xs sm:text-sm text-[#4B5563] mt-2">
            A guided 3-step workflow to verify your evidence before you respond to PayPal.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
          <div className="space-y-3">
            <div className="h-10 w-10 rounded-lg bg-[#F3F4F6] border border-[#E5E7EB] flex items-center justify-center font-bold text-sm text-[#111827]">
              1
            </div>
            <h3 className="font-semibold text-sm text-[#111827]">Connect Records to Order</h3>
            <p className="text-xs text-[#6B7280] leading-relaxed">
              Import the disputed PayPal transaction and link your LMS access logs, SendGrid receipts, or download server events. ProofLedger strictly validates order references.
            </p>
          </div>

          <div className="space-y-3">
            <div className="h-10 w-10 rounded-lg bg-[#F3F4F6] border border-[#E5E7EB] flex items-center justify-center font-bold text-sm text-[#111827]">
              2
            </div>
            <h3 className="font-semibold text-sm text-[#111827]">Verify Factual Claims</h3>
            <p className="text-xs text-[#6B7280] leading-relaxed">
              Define your claims. Deterministic checks and NLI evaluate each claim against available records, classifying them as SUPPORTED, CONTRADICTED, or INSUFFICIENT.
            </p>
          </div>

          <div className="space-y-3">
            <div className="h-10 w-10 rounded-lg bg-[#F3F4F6] border border-[#E5E7EB] flex items-center justify-center font-bold text-sm text-[#111827]">
              3
            </div>
            <h3 className="font-semibold text-sm text-[#111827]">Review & Export Packet</h3>
            <p className="text-xs text-[#6B7280] leading-relaxed">
              Inspect missing evidence notes. Once verified, review and cryptographically seal the evidence packet with your approval for submission to PayPal Resolution Center.
            </p>
          </div>
        </div>
      </section>

      {/* Target Digital Sellers */}
      <section className="py-16 bg-[#F9FAFB] border-t border-[#E5E7EB] px-6">
        <div className="max-w-5xl mx-auto">
          <div className="text-center mb-10">
            <h3 className="text-lg font-bold text-[#111827]">Built for All Digital Goods Sellers</h3>
            <p className="text-xs text-[#6B7280]">Wherever you sell digital products using PayPal checkout</p>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3 text-center text-xs">
            <div className="p-3 bg-white rounded-lg border border-[#E5E7EB]">
              <span className="font-semibold text-[#111827] block">SaaS & Apps</span>
              <span className="text-[10px] text-[#6B7280]">Subscriptions</span>
            </div>
            <div className="p-3 bg-white rounded-lg border border-[#E5E7EB]">
              <span className="font-semibold text-[#111827] block">Course Creators</span>
              <span className="text-[10px] text-[#6B7280]">Video lessons</span>
            </div>
            <div className="p-3 bg-white rounded-lg border border-[#E5E7EB]">
              <span className="font-semibold text-[#111827] block">E-Books</span>
              <span className="text-[10px] text-[#6B7280]">PDFs & guides</span>
            </div>
            <div className="p-3 bg-white rounded-lg border border-[#E5E7EB]">
              <span className="font-semibold text-[#111827] block">Plugins & Code</span>
              <span className="text-[10px] text-[#6B7280]">WordPress, APIs</span>
            </div>
            <div className="p-3 bg-white rounded-lg border border-[#E5E7EB]">
              <span className="font-semibold text-[#111827] block">Digital Agency</span>
              <span className="text-[10px] text-[#6B7280]">Design assets</span>
            </div>
            <div className="p-3 bg-white rounded-lg border border-[#E5E7EB]">
              <span className="font-semibold text-[#111827] block">Marketplaces</span>
              <span className="text-[10px] text-[#6B7280]">Stock files</span>
            </div>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-[#E5E7EB] py-8 px-6 text-center text-xs text-[#6B7280] bg-white">
        <p className="mb-2">
          <strong>ProofLedger</strong> — Source-Grounded Evidence Verification Assistant for Digital Goods Sellers.
        </p>
        <p className="max-w-2xl mx-auto text-[11px] text-[#9CA3AF]">
          Disclaimer: ProofLedger assists merchants in assembling and evaluating source-grounded evidence packets. AI evaluations do not constitute a legal determination or a guarantee of PayPal Seller Protection eligibility. Human approval is strictly required before external submission.
        </p>
      </footer>
    </div>
  );
}
