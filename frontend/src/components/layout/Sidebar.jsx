import React from 'react';
import {
  LayoutDashboard,
  Inbox,
  PlusCircle,
  FolderOpen,
  Activity,
  Settings,
  ShieldCheck,
  X,
  UserCheck,
} from 'lucide-react';

const NAV_ITEMS = [
  { id: 'overview', label: 'Overview', icon: LayoutDashboard },
  { id: 'inbox', label: 'Dispute Inbox', icon: Inbox },
  { id: 'new_analysis', label: 'New Analysis', icon: PlusCircle },
  { id: 'evidence_library', label: 'Evidence Library', icon: FolderOpen },
  { id: 'activity', label: 'Activity', icon: Activity },
];

export default function Sidebar({
  activeTab,
  onSelectTab,
  openDisputeCount,
  systemStatus,
  isOffline,
  sellerProfile,
  storeProfile,
  mobileOpen = false,
  onCloseMobile,
}) {
  const paypalAuth = systemStatus?.paypal?.auth_status === 'AUTHENTICATED';
  const paypalEnv = systemStatus?.paypal?.environment || 'SANDBOX';
  const aiModel = systemStatus?.ai_model || {};
  const aiLoaded = aiModel.status === 'MODEL_LOADED' && aiModel.is_loaded !== false;

  const handleSelect = (tabId) => {
    onSelectTab(tabId);
    if (onCloseMobile) onCloseMobile();
  };

  const sidebarBody = (
    <div className="flex flex-col justify-between h-full bg-[#FCFBF8] border-r border-[#E6E4DD] w-64 shrink-0">
      <div className="p-4 space-y-6">
        {/* Brand */}
        <div className="flex items-center justify-between px-2 pt-1">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-[#18181B] text-white flex items-center justify-center shrink-0">
              <ShieldCheck className="w-4 h-4 text-[#99F6E4]" />
            </div>
            <div className="min-w-0">
              <div className="text-xs font-bold tracking-[0.08em] text-[#18181B] uppercase">
                PROOFLEDGER
              </div>
              <div className="text-[11px] text-[#71717A] truncate">
                PayPal Dispute Rescue
              </div>
            </div>
          </div>
          {onCloseMobile && (
            <button
              type="button"
              onClick={onCloseMobile}
              aria-label="Close navigation"
              className="lg:hidden p-1.5 rounded-lg text-[#71717A] hover:text-[#18181B] hover:bg-[#EFECE4]"
            >
              <X className="w-4 h-4" />
            </button>
          )}
        </div>

        {/* Navigation */}
        <nav className="space-y-1" aria-label="Primary Sidebar Navigation">
          {NAV_ITEMS.map((item) => {
            const Icon = item.icon;
            const isActive =
              activeTab === item.id ||
              (item.id === 'inbox' && activeTab === 'resolve');

            return (
              <button
                key={item.id}
                type="button"
                onClick={() => handleSelect(item.id)}
                className={`w-full flex items-center justify-between px-3 py-2 rounded-lg text-xs font-medium transition-colors ${
                  isActive
                    ? 'bg-white text-[#18181B] border border-[#E6E4DD] shadow-xs'
                    : 'text-[#52525B] hover:text-[#18181B] hover:bg-[#EFECE4]/70 border border-transparent'
                }`}
              >
                <span className="flex items-center gap-2.5 min-w-0">
                  <Icon
                    className={`w-4 h-4 shrink-0 ${
                      isActive ? 'text-[#0F766E]' : 'text-[#71717A]'
                    }`}
                  />
                  <span className="truncate">{item.label}</span>
                </span>
                {item.id === 'inbox' && typeof openDisputeCount === 'number' && openDisputeCount > 0 && (
                  <span
                    className={`text-[11px] font-mono tabular-nums px-1.5 py-0.5 rounded ${
                      isActive
                        ? 'bg-[#0F766E] text-white'
                        : 'bg-[#EFECE4] text-[#3F3F46]'
                    }`}
                  >
                    {openDisputeCount}
                  </span>
                )}
              </button>
            );
          })}
        </nav>
      </div>

      {/* Bottom Environment, Profile & Settings */}
      <div className="p-4 border-t border-[#E6E4DD] space-y-3">
        <div className="bg-white rounded-lg border border-[#E6E4DD] p-3 space-y-2 text-[11px]">
          <div className="flex items-center justify-between gap-2">
            <span className="text-[#71717A]">Environment</span>
            <span
              className={`font-medium px-1.5 py-0.5 rounded text-[10px] border ${
                isOffline
                  ? 'bg-rose-50 text-rose-800 border-rose-200'
                  : paypalAuth
                  ? 'bg-emerald-50 text-emerald-800 border-emerald-200'
                  : 'bg-amber-50 text-amber-800 border-amber-200'
              }`}
            >
              {isOffline ? 'Backend Offline' : `${paypalEnv} + Demo`}
            </span>
          </div>
          <div className="flex items-center justify-between gap-2">
            <span className="text-[#71717A]">NLI Model</span>
            <span
              className={`font-mono text-[10px] truncate max-w-[125px] ${
                aiLoaded ? 'text-[#18181B] font-medium' : 'text-rose-700 font-semibold'
              }`}
              title={aiModel.loaded_model_path || aiModel.model_load_error || 'Unavailable'}
            >
              {aiLoaded ? `DeBERTa (${(aiModel.device || 'cpu').toUpperCase()})` : 'MODEL_UNAVAILABLE'}
            </span>
          </div>
        </div>

        <div className="flex items-center gap-2.5 px-2 py-1">
          <div className="w-7 h-7 rounded-full bg-[#EFECE4] border border-[#E4E0D5] flex items-center justify-center shrink-0">
            <UserCheck className="w-3.5 h-3.5 text-[#3F3F46]" />
          </div>
          <div className="min-w-0 flex-1">
            <div className="text-xs font-medium text-[#18181B] truncate">
              {sellerProfile?.business_name || storeProfile?.storeName || 'Merchant Workspace'}
            </div>
            <div className="text-[11px] font-mono text-[#71717A] truncate">
              {sellerProfile?.seller_id || 'seller_alpha'}
            </div>
          </div>
        </div>

        <button
          type="button"
          onClick={() => handleSelect('settings')}
          className={`w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-xs font-medium transition-colors ${
            activeTab === 'settings'
              ? 'bg-white text-[#18181B] border border-[#E6E4DD] shadow-xs'
              : 'text-[#52525B] hover:text-[#18181B] hover:bg-[#EFECE4]/70 border border-transparent'
          }`}
        >
          <Settings className={`w-4 h-4 ${activeTab === 'settings' ? 'text-[#0F766E]' : 'text-[#71717A]'}`} />
          <span>Settings</span>
        </button>
      </div>
    </div>
  );

  return (
    <>
      {/* Desktop rail */}
      <aside className="hidden lg:block sticky top-0 h-screen shrink-0 z-20">
        {sidebarBody}
      </aside>

      {/* Mobile slide-over drawer */}
      {mobileOpen && (
        <div className="fixed inset-0 z-50 lg:hidden flex">
          <div
            className="fixed inset-0 bg-black/35"
            onClick={onCloseMobile}
            aria-hidden="true"
          />
          <div className="relative z-10 h-full">{sidebarBody}</div>
        </div>
      )}
    </>
  );
}

