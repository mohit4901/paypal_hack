import React from 'react';
import {
  Inbox,
  Sparkles,
  CreditCard,
  ShieldCheck,
  Settings,
  LayoutDashboard,
} from 'lucide-react';

const NAV_ITEMS = [
  { id: 'inbox', label: 'Dispute Inbox', icon: Inbox, badge: '1 Action' },
  { id: 'resolve', label: 'Resolve Dispute', icon: Sparkles, badge: 'Active' },
  { id: 'transactions', label: 'Orders & Evidence', icon: CreditCard, badge: null },
  { id: 'overview', label: 'Store Overview', icon: LayoutDashboard, badge: null },
  { id: 'settings', label: 'Integrations & Setup', icon: Settings, badge: null },
];

export default function Sidebar({ activeTab, onSelectTab, systemStatus, isOffline, openDisputeCount = 1 }) {
  const paypalConnected = systemStatus?.paypal?.auth_status === 'AUTHENTICATED';
  const aiDevice = systemStatus?.ai_model?.device ? systemStatus.ai_model.device.toUpperCase() : 'MPS';
  const aiLoaded = systemStatus?.ai_model?.status === 'MODEL_LOADED';

  return (
    <aside className="w-60 bg-[#FAFAFA] border-r border-[#E5E7EB] flex flex-col justify-between py-5 shrink-0 min-h-[calc(100vh-57px)] font-sans">
      <div className="space-y-1 px-3">
        <div className="px-3 pb-2 text-[10px] font-bold tracking-wider text-[#9CA3AF] uppercase">
          Seller Workspace
        </div>

        {NAV_ITEMS.map((item) => {
          const Icon = item.icon;
          const isActive = activeTab === item.id;
          return (
            <button
              key={item.id}
              onClick={() => onSelectTab(item.id)}
              className={`w-full flex items-center justify-between px-3 py-2 rounded-lg text-xs font-medium transition-all ${
                isActive
                  ? 'bg-white text-[#111827] border border-[#E5E7EB] shadow-xs'
                  : 'text-[#4B5563] hover:text-[#111827] hover:bg-[#F3F4F6] border border-transparent'
              }`}
            >
              <div className="flex items-center space-x-2.5">
                <Icon
                  className={`h-4 w-4 ${
                    isActive ? 'text-[#111827]' : 'text-[#9CA3AF]'
                  }`}
                />
                <span>{item.label}</span>
              </div>
              {item.badge && (
                <span
                  className={`text-[10px] font-mono px-1.5 py-0.5 rounded ${
                    isActive
                      ? 'bg-[#111827] text-white font-medium'
                      : 'bg-[#E5E7EB] text-[#4B5563]'
                  }`}
                >
                  {item.badge}
                </span>
              )}
            </button>
          );
        })}
      </div>

      <div className="px-4 pt-4 border-t border-[#E5E7EB] mx-3 text-[#6B7280] text-[11px] space-y-1">
        <div className="flex justify-between items-center">
          <span>PayPal Sandbox:</span>
          <span className={`font-medium ${paypalConnected ? 'text-[#059669]' : isOffline ? 'text-rose-600' : 'text-amber-600'}`}>
            {paypalConnected ? 'Connected' : isOffline ? 'Offline' : 'Pending'}
          </span>
        </div>
        <div className="flex justify-between items-center">
          <span>AI Verifier:</span>
          <span className="text-[#111827] font-medium font-mono text-[10px]">
            {aiLoaded ? `DeBERTa-v3 ${aiDevice}` : isOffline ? 'Offline' : 'Ready'}
          </span>
        </div>
      </div>
    </aside>
  );
}
