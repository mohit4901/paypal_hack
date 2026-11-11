import React, { useState, useEffect, useCallback } from 'react';
import AppShell from './components/layout/AppShell';
import ToastContainer from './components/ui/ToastContainer';
import DashboardPage from './pages/DashboardPage';
import DisputesPage from './pages/DisputesPage';
import NewAnalysisPage from './pages/NewAnalysisPage';
import ResolveDisputePage from './pages/ResolveDisputePage';
import EvidenceLibraryView from './components/library/EvidenceLibraryView';
import ActivityView from './components/activity/ActivityView';
import SettingsTab from './components/SettingsTab';
import SystemStatusPanel from './components/SystemStatusPanel';
import PayPalSandboxInspectorModal from './components/PayPalSandboxInspectorModal';
import { api } from './services/api';

export default function App() {
  const [activeTab, setActiveTab] = useState('inbox'); // 'overview' | 'inbox' | 'new_analysis' | 'resolve' | 'evidence_library' | 'activity' | 'settings'
  const [selectedDisputeId, setSelectedDisputeId] = useState('DSP-3EU95140-01');
  const [resolveLaunchContext, setResolveLaunchContext] = useState(null);

  const [loading, setLoading] = useState(false);
  const [systemStatus, setSystemStatus] = useState(null);
  const [isOffline, setIsOffline] = useState(false);
  const [offlineError, setOfflineError] = useState(null);
  const [overview, setOverview] = useState(null);
  const [transactions, setTransactions] = useState([]);
  const [disputes, setDisputes] = useState([]);
  const [sellerProfile, setSellerProfile] = useState(null);

  const [showSystemModal, setShowSystemModal] = useState(false);
  const [showPayPalInspectorModal, setShowPayPalInspectorModal] = useState(false);
  const [toasts, setToasts] = useState([]);

  const [storeProfile, setStoreProfile] = useState({
    storeName: 'Python Mastery Academy',
    productType: 'Online Courses & Digital Goods',
    websiteUrl: 'https://pythonmastery.academy',
  });

  const addToast = useCallback(({ type = 'info', title, message }) => {
    const id = `${Date.now()}-${Math.random().toString(36).slice(2, 6)}`;
    setToasts((prev) => [...prev, { id, type, title, message }]);
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, 5000);
  }, []);

  const dismissToast = useCallback((id) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [sysData, ovData, txData, dspData, profileData] = await Promise.all([
        api.getSystemStatus().catch((err) => {
          setIsOffline(true);
          setOfflineError(
            err.message ||
              'Cannot connect to the ProofLedger backend server. Ensure FastAPI is running.'
          );
          return null;
        }),
        api.getOverview().catch(() => null),
        api.getTransactions().catch(() => ({ transactions: [] })),
        api.getDisputes().catch(() => ({ disputes: [] })),
        api.getSellerProfile().catch(() => null),
      ]);

      if (sysData) {
        setSystemStatus(sysData);
        setIsOffline(false);
        setOfflineError(null);
      }
      if (ovData) setOverview(ovData);
      if (txData?.transactions) setTransactions(txData.transactions);
      if (dspData?.disputes) setDisputes(dspData.disputes);
      if (profileData) setSellerProfile(profileData);
    } catch (err) {
      addToast({ type: 'error', title: 'Workspace load failed', message: err.message });
    } finally {
      setLoading(false);
    }
  }, [addToast]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleSyncPayPal = async () => {
    setLoading(true);
    try {
      const syncRes = await api.syncPayPal();
      addToast({
        type: 'success',
        title: 'PayPal Sandbox synced',
        message: `Synced in ${syncRes.total_latency_ms || 300} ms (${syncRes.webhook_events_synced || 0} webhooks).`,
      });
      await loadData();
    } catch (err) {
      addToast({ type: 'error', title: 'PayPal sync error', message: err.message });
    } finally {
      setLoading(false);
    }
  };

  const openDisputeWorkspace = (disputeId, context = null) => {
    setSelectedDisputeId(disputeId);
    setResolveLaunchContext(context);
    setActiveTab('resolve');
  };

  const openDisputeCount = disputes.filter(
    (d) => d.status === 'WAITING_FOR_SELLER_RESPONSE' || d.status === 'UNDER_PAYPAL_REVIEW'
  ).length;

  return (
    <>
      <AppShell
        activeTab={activeTab}
        onSelectTab={setActiveTab}
        openDisputeCount={openDisputeCount}
        systemStatus={systemStatus}
        isOffline={isOffline}
        sellerProfile={sellerProfile}
        storeProfile={storeProfile}
        loading={loading}
        onRefresh={loadData}
        onOpenSystemModal={() => setShowSystemModal(true)}
      >
        {activeTab === 'overview' && (
          <DashboardPage
            overview={overview}
            disputes={disputes}
            transactions={transactions}
            systemStatus={systemStatus}
            isOffline={isOffline}
            offlineError={offlineError}
            onRefresh={loadData}
            onNavigate={setActiveTab}
            onOpenDispute={(id) => openDisputeWorkspace(id)}
            onOpenPayPalInspector={() => setShowPayPalInspectorModal(true)}
          />
        )}

        {activeTab === 'inbox' && (
          <DisputesPage
            disputes={disputes}
            loading={loading}
            onSelectDispute={(id) => openDisputeWorkspace(id)}
            onNewAnalysis={() => setActiveTab('new_analysis')}
            onRefresh={loadData}
            onSyncPayPal={handleSyncPayPal}
          />
        )}

        {activeTab === 'new_analysis' && (
          <NewAnalysisPage
            disputes={disputes}
            onBackToInbox={() => setActiveTab('inbox')}
            onStartResolve={(id, ctx) => openDisputeWorkspace(id, ctx)}
            onToast={addToast}
            onRefreshData={loadData}
          />
        )}

        {activeTab === 'resolve' && (
          <ResolveDisputePage
            disputeId={selectedDisputeId}
            launchContext={resolveLaunchContext}
            systemStatus={systemStatus}
            onBackToInbox={() => setActiveTab('inbox')}
            onToast={addToast}
            onRefreshParent={loadData}
          />
        )}

        {activeTab === 'evidence_library' && (
          <EvidenceLibraryView
            transactions={transactions}
            loading={loading}
            onRefresh={loadData}
            onNewAnalysis={() => setActiveTab('new_analysis')}
            onSelectOrderForDispute={(orderId) => openDisputeWorkspace(orderId)}
          />
        )}

        {activeTab === 'activity' && <ActivityView />}

        {activeTab === 'settings' && (
          <SettingsTab
            storeProfile={storeProfile}
            systemStatus={systemStatus}
            onUpdateProfile={(prof) => setStoreProfile((prev) => ({ ...prev, ...prof }))}
          />
        )}
      </AppShell>

      {/* System Health Modal */}
      {showSystemModal && (
        <div className="fixed inset-0 z-50 bg-black/45 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl border border-[#E6E4DD] max-w-4xl w-full p-6 shadow-xl space-y-4 max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between border-b border-[#EFECE4] pb-3">
              <h3 className="font-semibold text-sm text-[#18181B]">
                System &amp; Model Infrastructure Health
              </h3>
              <button
                type="button"
                onClick={() => setShowSystemModal(false)}
                className="text-xs text-[#71717A] hover:text-[#18181B] px-2 py-1"
              >
                Close
              </button>
            </div>
            <SystemStatusPanel
              systemStatus={systemStatus}
              loading={loading}
              onRefresh={loadData}
              isOffline={isOffline}
              offlineError={offlineError}
              onOpenPayPalInspector={() => {
                setShowSystemModal(false);
                setShowPayPalInspectorModal(true);
              }}
            />
          </div>
        </div>
      )}

      {/* PayPal Sandbox Live Inspector Modal */}
      <PayPalSandboxInspectorModal
        isOpen={showPayPalInspectorModal}
        onClose={() => setShowPayPalInspectorModal(false)}
        onSyncComplete={loadData}
      />

      <ToastContainer toasts={toasts} onDismiss={dismissToast} />
    </>
  );
}
