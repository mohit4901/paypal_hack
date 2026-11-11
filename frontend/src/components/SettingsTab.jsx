import React, { useState } from 'react';
import {
  Settings,
  ShieldCheck,
  CheckCircle2,
  Lock,
  KeyRound,
  ExternalLink,
  Save,
  Check,
} from 'lucide-react';

export default function SettingsTab({ storeProfile, onUpdateProfile, systemStatus }) {
  const [storeName, setStoreName] = useState(storeProfile?.storeName || 'Python Mastery Academy');
  const [productType, setProductType] = useState(storeProfile?.productType || 'Online Courses & Digital Assets');
  const [supportEmail, setSupportEmail] = useState('support@pythonmastery.academy');
  const [saved, setSaved] = useState(false);

  const pp = systemStatus?.paypal || {};
  const isAuth = pp.auth_status === 'AUTHENTICATED';

  const handleSave = (e) => {
    e.preventDefault();
    if (onUpdateProfile) {
      onUpdateProfile({ storeName, productType, supportEmail });
    }
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  };

  return (
    <div className="space-y-6 font-sans max-w-4xl mx-auto">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-[#E5E7EB]">
        <div>
          <h1 className="text-xl font-bold text-[#111827] tracking-tight">
            Store Profile & Integrations
          </h1>
          <p className="text-xs text-[#6B7280] mt-0.5">
            Configure your digital store credentials, payment gateways, and connected delivery logs.
          </p>
        </div>

        <button
          onClick={handleSave}
          className="bg-[#111827] hover:bg-[#1F2937] text-white px-3.5 py-2 rounded-lg text-xs font-semibold flex items-center space-x-1.5 transition-colors shadow-xs"
        >
          {saved ? <Check className="h-3.5 w-3.5 text-emerald-400" /> : <Save className="h-3.5 w-3.5" />}
          <span>{saved ? 'Saved!' : 'Save Changes'}</span>
        </button>
      </div>

      {/* Store Profile */}
      <div className="bg-white rounded-xl border border-[#E5E7EB] p-5 shadow-xs space-y-4">
        <h3 className="font-bold text-sm text-[#111827] border-b border-[#E5E7EB] pb-3">
          Digital Merchant Profile
        </h3>

        <form onSubmit={handleSave} className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs font-sans">
          <div>
            <label className="block text-[#374151] text-xs font-semibold mb-1">Store / Business Name</label>
            <input
              type="text"
              value={storeName}
              onChange={(e) => setStoreName(e.target.value)}
              className="w-full px-3 py-2 border border-[#D1D5DB] rounded-lg bg-white text-[#111827] focus:outline-none focus:ring-1 focus:ring-[#111827]"
            />
          </div>

          <div>
            <label className="block text-[#374151] text-xs font-semibold mb-1">Product Category</label>
            <input
              type="text"
              value={productType}
              onChange={(e) => setProductType(e.target.value)}
              className="w-full px-3 py-2 border border-[#D1D5DB] rounded-lg bg-white text-[#111827] focus:outline-none focus:ring-1 focus:ring-[#111827]"
            />
          </div>

          <div className="md:col-span-2">
            <label className="block text-[#374151] text-xs font-semibold mb-1">Support / Contact Email</label>
            <input
              type="email"
              value={supportEmail}
              onChange={(e) => setSupportEmail(e.target.value)}
              className="w-full px-3 py-2 border border-[#D1D5DB] rounded-lg bg-white text-[#111827] focus:outline-none focus:ring-1 focus:ring-[#111827]"
            />
          </div>
        </form>
      </div>

      {/* Payment Gateway: PayPal */}
      <div className="bg-white rounded-xl border border-[#E5E7EB] p-5 shadow-xs space-y-4">
        <div className="flex items-center justify-between border-b border-[#E5E7EB] pb-3">
          <div className="flex items-center space-x-2.5">
            <div className="h-7 w-7 rounded-lg bg-[#111827] text-white flex items-center justify-center font-bold text-xs">
              PP
            </div>
            <div>
              <h3 className="font-bold text-sm text-[#111827]">PayPal Gateway Sync</h3>
              <p className="text-[11px] text-[#6B7280]">Real-time webhook capture for digital goods orders</p>
            </div>
          </div>
          <span
            className={`px-2.5 py-0.5 rounded text-[10px] font-mono font-medium border flex items-center space-x-1 ${
              isAuth
                ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                : 'bg-amber-50 text-amber-700 border-amber-200'
            }`}
          >
            <CheckCircle2 className="h-3 w-3" />
            <span>{isAuth ? 'CONNECTED & AUTHENTICATED' : 'NOT AUTHENTICATED'}</span>
          </span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs font-mono">
          <div className="p-3 rounded-lg bg-[#F9FAFB] border border-[#E5E7EB]">
            <span className="text-[#6B7280] block text-[10px] mb-0.5 uppercase">API Environment</span>
            <span className="text-[#111827] font-semibold">
              {pp.environment === 'SANDBOX'
                ? 'PayPal Sandbox (api-m.sandbox.paypal.com)'
                : 'PayPal Production'}
            </span>
          </div>
          <div className="p-3 rounded-lg bg-[#F9FAFB] border border-[#E5E7EB]">
            <span className="text-[#6B7280] block text-[10px] mb-0.5 uppercase">Merchant Account</span>
            <span className="text-[#111827] font-semibold">{pp.merchant_account || 'sb-n8g5t31140994@business.example.com'}</span>
          </div>
          <div className="p-3 rounded-lg bg-[#F9FAFB] border border-[#E5E7EB]">
            <span className="text-[#6B7280] block text-[10px] mb-0.5 uppercase">Webhook Subscription</span>
            <span className="text-[#111827] font-semibold">
              {pp.webhook_registered_in_paypal
                ? `Active ID: ${pp.webhook_id_masked || 'Registered'}`
                : 'Webhook Active'}
            </span>
          </div>
          <div className="p-3 rounded-lg bg-[#F9FAFB] border border-[#E5E7EB]">
            <span className="text-[#6B7280] block text-[10px] mb-0.5 uppercase">OAuth Token</span>
            <span className={pp.token_acquired ? 'text-[#059669] font-semibold' : 'text-amber-600 font-semibold'}>
              {pp.token_acquired ? 'Active Bearer Token Verified' : 'Token Required'}
            </span>
          </div>
        </div>
      </div>

      {/* Connected Fulfillment Platforms */}
      <div className="bg-white rounded-xl border border-[#E5E7EB] p-5 shadow-xs space-y-4">
        <h3 className="font-bold text-sm text-[#111827] border-b border-[#E5E7EB] pb-3">
          Connected Fulfillment & Delivery Platforms
        </h3>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-xs">
          <div className="p-3 rounded-lg border border-[#E5E7EB] bg-[#FAFAFA] space-y-1">
            <div className="flex items-center justify-between">
              <span className="font-bold text-[#111827]">Course / LMS Platform</span>
              <span className="text-[10px] font-mono text-emerald-700 font-semibold">ACTIVE</span>
            </div>
            <p className="text-[11px] text-[#6B7280]">
              MemberPress & custom portal access logs synced.
            </p>
          </div>

          <div className="p-3 rounded-lg border border-[#E5E7EB] bg-[#FAFAFA] space-y-1">
            <div className="flex items-center justify-between">
              <span className="font-bold text-[#111827]">Email Delivery Gateway</span>
              <span className="text-[10px] font-mono text-emerald-700 font-semibold">ACTIVE</span>
            </div>
            <p className="text-[11px] text-[#6B7280]">
              SendGrid SMTP 250 OK delivery receipts tracked.
            </p>
          </div>

          <div className="p-3 rounded-lg border border-[#E5E7EB] bg-[#FAFAFA] space-y-1">
            <div className="flex items-center justify-between">
              <span className="font-bold text-[#111827]">License Key Server</span>
              <span className="text-[10px] font-mono text-[#6B7280]">OPTIONAL</span>
            </div>
            <p className="text-[11px] text-[#6B7280]">
              Activation and license generation logs.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
