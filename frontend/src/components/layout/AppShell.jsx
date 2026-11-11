import React, { useState } from 'react';
import Sidebar from './Sidebar';
import Topbar from './Topbar';

export default function AppShell({
  activeTab,
  onSelectTab,
  openDisputeCount,
  systemStatus,
  isOffline,
  sellerProfile,
  storeProfile,
  loading,
  onRefresh,
  onOpenSystemModal,
  children,
}) {
  const [mobileOpen, setMobileOpen] = useState(false);

  return (
    <div className="min-h-screen bg-[#F8F7F3] text-[#18181B] flex">
      <Sidebar
        activeTab={activeTab}
        onSelectTab={onSelectTab}
        openDisputeCount={openDisputeCount}
        systemStatus={systemStatus}
        isOffline={isOffline}
        sellerProfile={sellerProfile}
        storeProfile={storeProfile}
        mobileOpen={mobileOpen}
        onCloseMobile={() => setMobileOpen(false)}
      />

      <div className="flex-1 min-w-0 flex flex-col">
        <Topbar
          onOpenMobileMenu={() => setMobileOpen(true)}
          onRefresh={onRefresh}
          loading={loading}
          systemStatus={systemStatus}
          isOffline={isOffline}
          onOpenSystemModal={onOpenSystemModal}
        />

        <main className="flex-1 w-full max-w-[1240px] mx-auto px-4 sm:px-6 lg:px-8 py-6">
          {children}
        </main>
      </div>
    </div>
  );
}

