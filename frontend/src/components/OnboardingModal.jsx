import React, { useState } from 'react';
import {
  ShieldCheck,
  Check,
  ArrowRight,
  ArrowLeft,
  X,
  CreditCard,
  Layers,
  FileCheck2,
} from 'lucide-react';

export default function OnboardingModal({ isOpen, onClose, onFinish }) {
  const [step, setStep] = useState(1);
  const [storeName, setStoreName] = useState('Python Mastery Academy');
  const [productType, setProductType] = useState('Online Courses & Coaching');
  const [websiteUrl, setWebsiteUrl] = useState('https://pythonmastery.academy');
  const [evidenceSources, setEvidenceSources] = useState([
    'Course Platform Access Logs',
    'Email Delivery Receipts (SendGrid)',
    'Digital License Key System',
  ]);

  if (!isOpen) return null;

  const toggleSource = (src) => {
    if (evidenceSources.includes(src)) {
      setEvidenceSources(evidenceSources.filter((s) => s !== src));
    } else {
      setEvidenceSources([...evidenceSources, src]);
    }
  };

  const handleNext = () => {
    if (step < 3) {
      setStep(step + 1);
    } else {
      onFinish({
        storeName,
        productType,
        websiteUrl,
        evidenceSources,
      });
    }
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/50 backdrop-blur-sm flex items-center justify-center p-4">
      <div className="bg-white border border-[#E5E7EB] rounded-2xl w-full max-w-xl shadow-2xl overflow-hidden flex flex-col animate-in fade-in zoom-in-95 duration-150">
        {/* Progress Bar & Header */}
        <div className="border-b border-[#E5E7EB] px-6 py-4 flex items-center justify-between bg-[#F9FAFB]">
          <div className="flex items-center space-x-2">
            <span className="text-xs font-semibold text-[#111827]">
              Workspace Setup — Step {step} of 3
            </span>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded-lg text-[#6B7280] hover:text-[#111827] hover:bg-[#E5E7EB]/50"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Step Indicator */}
        <div className="h-1 w-full bg-[#E5E7EB]">
          <div
            className="h-full bg-[#111827] transition-all duration-300"
            style={{ width: `${(step / 3) * 100}%` }}
          />
        </div>

        {/* Body Content */}
        <div className="p-6 space-y-6 flex-1">
          {step === 1 && (
            <div className="space-y-4">
              <div>
                <h3 className="text-base font-bold text-[#111827]">Your Business Profile</h3>
                <p className="text-xs text-[#6B7280] mt-1">
                  Tell us what kind of digital products you sell to configure evidence validation rules.
                </p>
              </div>

              <div className="space-y-3 text-xs">
                <div>
                  <label className="block font-medium text-[#374151] mb-1">Store / Business Name</label>
                  <input
                    type="text"
                    value={storeName}
                    onChange={(e) => setStoreName(e.target.value)}
                    className="w-full px-3 py-2 border border-[#D1D5DB] rounded-lg text-xs focus:outline-none focus:border-[#111827]"
                    placeholder="e.g. Acme SaaS Ltd or DevCourse Academy"
                  />
                </div>

                <div>
                  <label className="block font-medium text-[#374151] mb-1">Product Category</label>
                  <select
                    value={productType}
                    onChange={(e) => setProductType(e.target.value)}
                    className="w-full px-3 py-2 border border-[#D1D5DB] rounded-lg text-xs bg-white focus:outline-none focus:border-[#111827]"
                  >
                    <option value="Online Courses & Coaching">Online Courses & Education</option>
                    <option value="SaaS & Software Subscriptions">SaaS Subscriptions & Licenses</option>
                    <option value="E-Books & Digital Downloads">E-Books, Guides & PDFs</option>
                    <option value="Design Assets & Templates">Design Templates & Presets</option>
                    <option value="Plugins & Themes">Plugins, Themes & Source Code</option>
                  </select>
                </div>

                <div>
                  <label className="block font-medium text-[#374151] mb-1">Store URL (Optional)</label>
                  <input
                    type="text"
                    value={websiteUrl}
                    onChange={(e) => setWebsiteUrl(e.target.value)}
                    className="w-full px-3 py-2 border border-[#D1D5DB] rounded-lg text-xs focus:outline-none focus:border-[#111827]"
                    placeholder="https://yourstore.com"
                  />
                </div>
              </div>
            </div>
          )}

          {step === 2 && (
            <div className="space-y-4">
              <div>
                <h3 className="text-base font-bold text-[#111827]">Payment Gateway Connection</h3>
                <p className="text-xs text-[#6B7280] mt-1">
                  ProofLedger pulls verified payment capture events directly from PayPal.
                </p>
              </div>

              <div className="p-4 rounded-xl border border-[#E5E7EB] bg-[#F9FAFB] space-y-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-2">
                    <div className="h-8 w-8 rounded-lg bg-[#111827] text-white flex items-center justify-center font-bold text-xs">
                      PP
                    </div>
                    <div>
                      <span className="font-semibold text-xs text-[#111827] block">PayPal Sandbox Integration</span>
                      <span className="text-[11px] text-[#059669] font-medium flex items-center space-x-1">
                        <Check className="h-3 w-3" />
                        <span>Connected & Webhooks Verified</span>
                      </span>
                    </div>
                  </div>
                  <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-emerald-50 text-emerald-700 border border-emerald-200">
                    LIVE_ACTIVE
                  </span>
                </div>

                <div className="pt-2 border-t border-[#E5E7EB] text-[11px] text-[#4B5563] space-y-1 font-mono">
                  <div className="flex justify-between">
                    <span>Endpoint:</span>
                    <span className="text-[#111827]">api-m.sandbox.paypal.com</span>
                  </div>
                  <div className="flex justify-between">
                    <span>Account:</span>
                    <span className="text-[#111827]">sb-n8g5t31140994@business</span>
                  </div>
                  <div className="flex justify-between">
                    <span>Sample Order:</span>
                    <span className="text-[#111827]">3EU95140LR696653G ($5.00 USD)</span>
                  </div>
                </div>
              </div>
            </div>
          )}

          {step === 3 && (
            <div className="space-y-4">
              <div>
                <h3 className="text-base font-bold text-[#111827]">Evidence Sources Used</h3>
                <p className="text-xs text-[#6B7280] mt-1">
                  Select which systems produce logs when a customer receives their digital purchase.
                </p>
              </div>

              <div className="space-y-2 text-xs">
                {[
                  {
                    name: 'Course Platform Access Logs',
                    desc: 'MemberPress, Teachable, Thinkific, Kajabi access logs',
                  },
                  {
                    name: 'Email Delivery Receipts (SendGrid)',
                    desc: 'SMTP delivery, bounce check, and open events',
                  },
                  {
                    name: 'Digital License Key System',
                    desc: 'License generator, API key creation, activation logs',
                  },
                  {
                    name: 'AWS S3 / CloudFront Download History',
                    desc: 'File download completion, IP address, and byte telemetry',
                  },
                ].map((src) => {
                  const isChecked = evidenceSources.includes(src.name);
                  return (
                    <div
                      key={src.name}
                      onClick={() => toggleSource(src.name)}
                      className={`p-3 rounded-xl border cursor-pointer transition-all flex items-start justify-between ${
                        isChecked
                          ? 'border-[#111827] bg-[#F9FAFB]'
                          : 'border-[#E5E7EB] hover:border-[#D1D5DB]'
                      }`}
                    >
                      <div>
                        <span className="font-semibold text-[#111827] block">{src.name}</span>
                        <span className="text-[11px] text-[#6B7280]">{src.desc}</span>
                      </div>
                      <div
                        className={`h-4 w-4 rounded border flex items-center justify-center shrink-0 mt-0.5 ${
                          isChecked
                            ? 'bg-[#111827] border-[#111827] text-white'
                            : 'border-[#D1D5DB]'
                        }`}
                      >
                        {isChecked && <Check className="h-3 w-3" />}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>

        {/* Footer Navigation */}
        <div className="border-t border-[#E5E7EB] px-6 py-4 flex items-center justify-between bg-[#F9FAFB]">
          {step > 1 ? (
            <button
              onClick={() => setStep(step - 1)}
              className="text-xs font-medium text-[#4B5563] hover:text-[#111827] px-3 py-2 rounded-lg flex items-center space-x-1"
            >
              <ArrowLeft className="h-3.5 w-3.5" />
              <span>Back</span>
            </button>
          ) : (
            <div />
          )}

          <button
            onClick={handleNext}
            className="text-xs font-medium bg-[#111827] hover:bg-[#1F2937] text-white px-4 py-2 rounded-lg flex items-center space-x-1.5 shadow-sm"
          >
            <span>{step === 3 ? 'Launch Workspace' : 'Continue'}</span>
            <ArrowRight className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>
    </div>
  );
}

