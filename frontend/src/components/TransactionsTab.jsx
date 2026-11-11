import React, { useState } from 'react';
import {
  Search,
  Filter,
  ArrowRight,
  CheckCircle2,
  AlertCircle,
  ExternalLink,
  Plus,
  FileText,
  DollarSign,
  Package,
  RefreshCw,
  ShieldCheck,
  Zap,
} from 'lucide-react';
import { api } from '../api';

export default function TransactionsTab({
  transactions,
  onStartVerification,
  onRefresh,
  onSyncPayPal,
  onOpenPayPalInspector,
  loading = false,
}) {
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('ALL');
  const [showImportModal, setShowImportModal] = useState(false);
  const [importMode, setImportMode] = useState('live_paypal'); // 'live_paypal' | 'manual'
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [liveImportError, setLiveImportError] = useState(null);

  // Live PayPal Import Form
  const [liveOrderId, setLiveOrderId] = useState('3EU95140LR696653G');

  // Manual Form state
  const [orderId, setOrderId] = useState(`ORD-${Math.floor(100000 + Math.random() * 900000)}`);
  const [amount, setAmount] = useState('49.00');
  const [currency, setCurrency] = useState('USD');
  const [productName, setProductName] = useState('Fullstack SaaS Template & License');
  const [productType, setProductType] = useState('Digital License Key');
  const [buyerEmail, setBuyerEmail] = useState('customer.buyer@example.com');

  const items = transactions || [];

  const filtered = items.filter((tx) => {
    const matchesSearch =
      !search ||
      tx.order_id?.toLowerCase().includes(search.toLowerCase()) ||
      tx.capture_id?.toLowerCase().includes(search.toLowerCase()) ||
      tx.buyer_email?.toLowerCase().includes(search.toLowerCase()) ||
      tx.product_name?.toLowerCase().includes(search.toLowerCase());

    const matchesStatus =
      statusFilter === 'ALL' ||
      (statusFilter === 'DISPUTED' && tx.dispute_status !== 'NONE') ||
      (statusFilter === 'COMPLETED' && tx.payment_status === 'COMPLETED');

    return matchesSearch && matchesStatus;
  });

  const handleLiveImport = async (e) => {
    e.preventDefault();
    if (!liveOrderId.trim()) return;
    setIsSubmitting(true);
    setLiveImportError(null);
    try {
      await api.importLivePayPalOrder({ order_id: liveOrderId.trim() });
      setShowImportModal(false);
      if (onRefresh) onRefresh();
    } catch (err) {
      setLiveImportError(err.message || 'Failed to import from PayPal Sandbox');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleCreateTransaction = async (e) => {
    e.preventDefault();
    if (!orderId.trim() || !amount.trim()) {
      alert('Order ID and Amount are required.');
      return;
    }

    setIsSubmitting(true);
    try {
      await api.createTransaction({
        order_id: orderId.trim(),
        amount: amount.trim(),
        currency: currency.trim(),
        product_name: productName.trim(),
        product_type: productType.trim(),
        buyer_email: buyerEmail.trim(),
      });
      setShowImportModal(false);
      if (onRefresh) onRefresh();
      // Reset form
      setOrderId(`ORD-${Math.floor(100000 + Math.random() * 900000)}`);
    } catch (err) {
      alert(`Failed to save transaction: ${err.message}`);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="space-y-6 font-sans">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-[#E5E7EB]">
        <div>
          <div className="flex items-center space-x-2">
            <h1 className="text-xl font-bold text-[#111827] tracking-tight">Transactions & Orders</h1>
            <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-emerald-50 text-emerald-800 border border-emerald-200">
              {items.length} RECORDS
            </span>
          </div>
          <p className="text-xs text-[#6B7280] mt-0.5">
            Synchronized directly with PayPal Sandbox captures, webhooks, and digital fulfillment records.
          </p>
        </div>

        <div className="flex items-center space-x-2">
          {onOpenPayPalInspector && (
            <button
              onClick={onOpenPayPalInspector}
              className="border border-[#E5E7EB] hover:bg-[#F9FAFB] text-[#374151] px-3 py-2 rounded-lg text-xs font-medium flex items-center space-x-1.5 transition-colors shadow-2xs"
            >
              <ShieldCheck className="h-3.5 w-3.5 text-blue-600" />
              <span>Inspect PayPal API</span>
            </button>
          )}
          <button
            onClick={onSyncPayPal || onRefresh}
            disabled={loading}
            className="border border-[#E5E7EB] hover:bg-[#F9FAFB] text-[#374151] px-3 py-2 rounded-lg text-xs font-medium flex items-center space-x-1.5 transition-colors shadow-2xs"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${loading ? 'animate-spin text-black' : 'text-[#6B7280]'}`} />
            <span>Sync PayPal Sandbox</span>
          </button>
          <button
            onClick={async () => {
              try {
                const res = await api.generateLiveTransaction();
                if (onRefresh) await onRefresh();
                if (res && res.order_id && onStartVerification) {
                  onStartVerification(res.order_id);
                }
              } catch (err) {
                alert(`Failed to create live transaction: ${err.message}`);
              }
            }}
            className="bg-emerald-600 hover:bg-emerald-700 text-white px-3.5 py-2 rounded-lg text-xs font-bold flex items-center space-x-1.5 transition-colors shadow-xs"
          >
            <Zap className="h-3.5 w-3.5" />
            <span>⚡ Generate Live Nov 1 Dispute</span>
          </button>
          <button
            onClick={() => setShowImportModal(true)}
            className="bg-[#111827] hover:bg-[#1F2937] text-white px-3.5 py-2 rounded-lg text-xs font-semibold flex items-center space-x-1.5 transition-colors shadow-xs"
          >
            <Plus className="h-3.5 w-3.5" />
            <span>+ Import / Add Transaction</span>
          </button>
        </div>
      </div>

      {/* Filter and Search Bar */}
      <div className="p-4 rounded-xl border border-[#E5E7EB] bg-white flex flex-col md:flex-row gap-3 items-center justify-between shadow-xs">
        <div className="relative w-full md:w-96">
          <Search className="h-4 w-4 text-[#9CA3AF] absolute left-3 top-2.5" />
          <input
            type="text"
            placeholder="Search by Order ID, Capture ID, product or buyer email..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-9 pr-3 py-1.5 border border-[#D1D5DB] rounded-lg text-xs text-[#111827] focus:outline-none focus:border-[#111827]"
          />
        </div>

        <div className="flex items-center space-x-2 text-xs text-[#4B5563]">
          <span className="text-[#6B7280]">Status:</span>
          {['ALL', 'DISPUTED', 'COMPLETED'].map((st) => (
            <button
              key={st}
              onClick={() => setStatusFilter(st)}
              className={`px-2.5 py-1 rounded-md text-xs font-medium transition-colors ${
                statusFilter === st
                  ? 'bg-[#111827] text-white'
                  : 'bg-[#F3F4F6] text-[#4B5563] hover:text-[#111827]'
              }`}
            >
              {st}
            </button>
          ))}
        </div>
      </div>

      {/* Table */}
      <div className="bg-white rounded-xl border border-[#E5E7EB] overflow-hidden shadow-xs">
        <table className="w-full text-left text-xs">
          <thead className="bg-[#F9FAFB] border-b border-[#E5E7EB] text-[#6B7280] uppercase text-[10px] tracking-wider font-semibold">
            <tr>
              <th className="py-3 px-4">Order / Product</th>
              <th className="py-3 px-4">Capture ID</th>
              <th className="py-3 px-4">Buyer Email</th>
              <th className="py-3 px-4">Amount</th>
              <th className="py-3 px-4">Provenance Source</th>
              <th className="py-3 px-4">Payment</th>
              <th className="py-3 px-4">Dispute Status</th>
              <th className="py-3 px-4 text-right">Action</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[#E5E7EB] text-[#374151]">
            {filtered.length === 0 ? (
              <tr>
                <td colSpan="8" className="py-8 text-center text-xs text-[#6B7280]">
                  No transactions match your search.
                </td>
              </tr>
            ) : (
              filtered.map((tx) => {
                const isPayPalLive =
                  tx.provenance_source === 'PAYPAL_SANDBOX_LIVE_SYNC' ||
                  tx.provenance_source === 'PAYPAL_SANDBOX_CAPTURE' ||
                  tx.provenance_source === 'PAYPAL_SANDBOX_LIVE_IMPORT' ||
                  tx.provenance_source === 'PAYPAL_SANDBOX_WEBHOOK';

                return (
                  <tr key={tx.order_id} className="hover:bg-[#F9FAFB] transition-colors">
                    <td className="py-3 px-4">
                      <div className="font-mono font-bold text-[#111827]">{tx.order_id}</div>
                      <div className="text-[11px] text-[#6B7280]">{tx.product_name}</div>
                      <div className="text-[10px] text-emerald-800 font-mono mt-0.5 flex items-center gap-1">
                        <span className="w-1.5 h-1.5 rounded-full bg-emerald-500"></span>
                        {tx.created_at ? new Date(tx.created_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }) : 'Nov 1, 2026'} • Live Synced
                      </div>
                    </td>
                    <td className="py-3 px-4 font-mono text-[11px] text-[#4B5563]">
                      {tx.capture_id || '—'}
                    </td>
                    <td className="py-3 px-4 text-[11px] font-mono text-[#374151]">
                      {tx.buyer_email || '—'}
                    </td>
                    <td className="py-3 px-4 font-mono font-semibold text-[#111827]">
                      ${tx.amount} {tx.currency}
                    </td>
                    <td className="py-3 px-4">
                      {isPayPalLive ? (
                        <span className="inline-flex items-center space-x-1 px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-blue-50 text-blue-800 border border-blue-200">
                          <ShieldCheck className="h-3 w-3 text-blue-600" />
                          <span>PAYPAL SANDBOX</span>
                        </span>
                      ) : (
                        <span className="inline-flex items-center space-x-1 px-2 py-0.5 rounded text-[10px] font-mono bg-gray-50 text-gray-700 border border-gray-200">
                          <span>SELLER IMPORT</span>
                        </span>
                      )}
                    </td>
                    <td className="py-3 px-4">
                      <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-emerald-50 text-emerald-800 border border-emerald-200">
                        {tx.payment_status}
                      </span>
                    </td>
                    <td className="py-3 px-4">
                      {tx.dispute_status !== 'NONE' ? (
                        <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-amber-50 text-amber-800 border border-amber-200">
                          {tx.dispute_status}
                        </span>
                      ) : (
                        <span className="text-[11px] text-[#9CA3AF]">None</span>
                      )}
                    </td>
                    <td className="py-3 px-4 text-right">
                      {tx.dispute_status !== 'NONE' ? (
                        <button
                          onClick={() => onStartVerification(tx.order_id)}
                          className="inline-flex items-center space-x-1 text-xs font-semibold text-[#111827] hover:text-[#374151] bg-[#F3F4F6] hover:bg-[#E5E7EB] px-2.5 py-1 rounded transition-colors"
                        >
                          <span>Review Dispute</span>
                          <ArrowRight className="h-3 w-3" />
                        </button>
                      ) : (
                        <button
                          onClick={() => onStartVerification(tx.order_id)}
                          className="inline-flex items-center space-x-1 text-xs text-[#6B7280] hover:text-[#111827] px-2 py-1"
                        >
                          <span>Inspect</span>
                        </button>
                      )}
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>

      {/* Modal: Import / Add Transaction */}
      {showImportModal && (
        <div className="fixed inset-0 z-50 bg-black/40 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-lg w-full p-6 shadow-xl space-y-4">
            <div className="flex items-center justify-between border-b border-[#E5E7EB] pb-3">
              <div>
                <h3 className="font-bold text-sm text-[#111827]">Import / Add Digital Transaction</h3>
                <p className="text-[11px] text-[#6B7280]">
                  Import directly from PayPal Sandbox or add custom store sales.
                </p>
              </div>
              <button
                onClick={() => setShowImportModal(false)}
                className="text-xs text-[#9CA3AF] hover:text-[#111827]"
              >
                ✕
              </button>
            </div>

            {/* Mode Selector Tabs */}
            <div className="flex border-b border-[#E5E7EB] text-xs font-semibold">
              <button
                onClick={() => setImportMode('live_paypal')}
                className={`flex-1 py-2 text-center border-b-2 transition ${
                  importMode === 'live_paypal'
                    ? 'border-[#111827] text-[#111827]'
                    : 'border-transparent text-[#6B7280] hover:text-[#111827]'
                }`}
              >
                Live PayPal Sandbox Import
              </button>
              <button
                onClick={() => setImportMode('manual')}
                className={`flex-1 py-2 text-center border-b-2 transition ${
                  importMode === 'manual'
                    ? 'border-[#111827] text-[#111827]'
                    : 'border-transparent text-[#6B7280] hover:text-[#111827]'
                }`}
              >
                Manual Store Record
              </button>
            </div>

            {/* TAB 1: Live PayPal Import */}
            {importMode === 'live_paypal' && (
              <form onSubmit={handleLiveImport} className="space-y-3 text-xs">
                {liveImportError && (
                  <div className="p-2.5 rounded-lg bg-rose-50 border border-rose-200 text-rose-800 text-xs">
                    {liveImportError}
                  </div>
                )}
                <div className="p-3 rounded-xl bg-blue-50/50 border border-blue-200 text-blue-900 space-y-1">
                  <div className="flex items-center space-x-1.5 font-bold">
                    <Zap className="h-3.5 w-3.5 text-blue-600" />
                    <span>Live Verification from api-m.sandbox.paypal.com</span>
                  </div>
                  <p className="text-[11px] text-blue-800">
                    Queries PayPal servers via OAuth2, extracts genuine buyer email, gross amounts, and logs verified evidence.
                  </p>
                </div>

                <div>
                  <label className="block font-semibold text-[#374151] mb-1">
                    PayPal Sandbox Order ID
                  </label>
                  <input
                    type="text"
                    value={liveOrderId}
                    onChange={(e) => setLiveOrderId(e.target.value)}
                    placeholder="e.g. 3EU95140LR696653G"
                    className="w-full p-2.5 border border-[#D1D5DB] rounded-lg font-mono text-xs focus:outline-none focus:border-[#111827]"
                    required
                  />
                  <span className="text-[10px] text-[#6B7280] mt-1 block">
                    Pre-filled with verified Sandbox order 3EU95140LR696653G.
                  </span>
                </div>

                <div className="flex justify-end space-x-2 pt-2 border-t border-[#E5E7EB]">
                  <button
                    type="button"
                    onClick={() => setShowImportModal(false)}
                    className="px-3 py-1.5 border border-[#D1D5DB] rounded-lg text-xs text-[#374151] hover:bg-[#F9FAFB]"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={isSubmitting || !liveOrderId.trim()}
                    className="px-4 py-1.5 bg-[#111827] hover:bg-black text-white rounded-lg text-xs font-semibold flex items-center space-x-1.5 transition disabled:opacity-50"
                  >
                    <RefreshCw className={`h-3 w-3 ${isSubmitting ? 'animate-spin' : ''}`} />
                    <span>{isSubmitting ? 'Verifying with PayPal...' : 'Fetch & Import from PayPal'}</span>
                  </button>
                </div>
              </form>
            )}

            {/* TAB 2: Manual Entry */}
            {importMode === 'manual' && (
              <form onSubmit={handleCreateTransaction} className="space-y-3 text-xs">
                <div>
                  <label className="block font-semibold text-[#374151] mb-1">Order ID / Reference</label>
                  <input
                    type="text"
                    value={orderId}
                    onChange={(e) => setOrderId(e.target.value)}
                    className="w-full p-2.5 border border-[#D1D5DB] rounded-lg font-mono text-xs"
                    required
                  />
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block font-semibold text-[#374151] mb-1">Amount ($)</label>
                    <input
                      type="text"
                      value={amount}
                      onChange={(e) => setAmount(e.target.value)}
                      className="w-full p-2.5 border border-[#D1D5DB] rounded-lg font-mono text-xs"
                      required
                    />
                  </div>
                  <div>
                    <label className="block font-semibold text-[#374151] mb-1">Currency</label>
                    <input
                      type="text"
                      value={currency}
                      onChange={(e) => setCurrency(e.target.value)}
                      className="w-full p-2.5 border border-[#D1D5DB] rounded-lg font-mono text-xs"
                      required
                    />
                  </div>
                </div>

                <div>
                  <label className="block font-semibold text-[#374151] mb-1">Product Name</label>
                  <input
                    type="text"
                    value={productName}
                    onChange={(e) => setProductName(e.target.value)}
                    className="w-full p-2.5 border border-[#D1D5DB] rounded-lg text-xs"
                    required
                  />
                </div>

                <div>
                  <label className="block font-semibold text-[#374151] mb-1">Buyer Email</label>
                  <input
                    type="email"
                    value={buyerEmail}
                    onChange={(e) => setBuyerEmail(e.target.value)}
                    className="w-full p-2.5 border border-[#D1D5DB] rounded-lg font-mono text-xs"
                    required
                  />
                </div>

                <div className="flex justify-end space-x-2 pt-2 border-t border-[#E5E7EB]">
                  <button
                    type="button"
                    onClick={() => setShowImportModal(false)}
                    className="px-3 py-1.5 border border-[#D1D5DB] rounded-lg text-xs text-[#374151] hover:bg-[#F9FAFB]"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={isSubmitting}
                    className="px-4 py-1.5 bg-[#111827] hover:bg-black text-white rounded-lg text-xs font-semibold transition disabled:opacity-50"
                  >
                    {isSubmitting ? 'Saving...' : 'Save Transaction'}
                  </button>
                </div>
              </form>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
