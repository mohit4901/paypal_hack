import React, { useState, useEffect } from 'react';
import {
  Search,
  Filter,
  ChevronLeft,
  ChevronRight,
  ShieldCheck,
  Eye,
  X,
  Copy,
  Check,
} from 'lucide-react';
import { api } from '../api';

export default function EventsTab({ onSelectEventToVerify }) {
  const [events, setEvents] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(15);
  const [totalPages, setTotalPages] = useState(1);
  const [sourceType, setSourceType] = useState('');
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(false);
  const [selectedEvent, setSelectedEvent] = useState(null);
  const [copiedKey, setCopiedKey] = useState(null);

  const loadEvents = async () => {
    setLoading(true);
    try {
      const data = await api.getEvents({
        page,
        page_size: pageSize,
        source_type: sourceType || undefined,
        search: search || undefined,
      });
      setEvents(data.events || []);
      setTotal(data.total || 0);
      setTotalPages(data.total_pages || 1);
    } catch (err) {
      console.error('Failed to load events:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadEvents();
  }, [page, pageSize, sourceType]);

  const handleSearchSubmit = (e) => {
    e.preventDefault();
    setPage(1);
    loadEvents();
  };

  const copyToClipboard = (text, key) => {
    navigator.clipboard.writeText(text);
    setCopiedKey(key);
    setTimeout(() => setCopiedKey(null), 2000);
  };

  return (
    <div className="space-y-4">
      {/* Controls Bar */}
      <div className="bg-[#0e1424] border border-slate-800 p-4 rounded-xl flex flex-col md:flex-row gap-3 items-center justify-between">
        <form onSubmit={handleSearchSubmit} className="relative w-full md:w-96">
          <Search className="h-4 w-4 text-slate-500 absolute left-3 top-2.5" />
          <input
            type="text"
            placeholder="Search by Event ID, Order ID, Hash, or payload..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full bg-slate-900 border border-slate-800 text-xs rounded-lg pl-9 pr-3 py-2 text-slate-200 placeholder-slate-500 focus:outline-none focus:border-cyan-500 transition-colors"
          />
        </form>

        <div className="flex items-center space-x-3 w-full md:w-auto justify-end">
          <div className="flex items-center space-x-2 text-xs text-slate-400">
            <Filter className="h-3.5 w-3.5 text-slate-500" />
            <select
              value={sourceType}
              onChange={(e) => {
                setSourceType(e.target.value);
                setPage(1);
              }}
              className="bg-slate-900 border border-slate-800 rounded-lg px-2.5 py-1.5 text-xs text-slate-300 focus:outline-none focus:border-cyan-500"
            >
              <option value="">All Source Types</option>
              <option value="paypal_api">paypal_api</option>
              <option value="paypal_webhook">paypal_webhook</option>
              <option value="delivery">delivery</option>
              <option value="admin_resolution">admin_resolution</option>
            </select>
          </div>

          <span className="text-xs text-slate-500 font-mono">
            {total} records
          </span>
        </div>
      </div>

      {/* Events Table */}
      <div className="bg-[#0e1424] border border-slate-800 rounded-xl overflow-hidden shadow-xl">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-900/80 border-b border-slate-800 text-slate-400 uppercase text-[10px] tracking-wider">
              <tr>
                <th className="py-3 px-4">Index</th>
                <th className="py-3 px-4">Event ID</th>
                <th className="py-3 px-4">Source Type</th>
                <th className="py-3 px-4">Transaction / Target</th>
                <th className="py-3 px-4">Current SHA-256 Hash</th>
                <th className="py-3 px-4">Status / Provenance</th>
                <th className="py-3 px-4 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60 text-slate-300">
              {loading ? (
                <tr>
                  <td colSpan="7" className="py-12 text-center text-slate-500">
                    Loading hash-chain records...
                  </td>
                </tr>
              ) : events.length === 0 ? (
                <tr>
                  <td colSpan="7" className="py-12 text-center text-slate-500">
                    No matching events found.
                  </td>
                </tr>
              ) : (
                events.map((ev) => {
                  const isSandboxCapture =
                    ev.source_event_id === '10A71705XW788203L' ||
                    ev.transaction_ref === '3EU95140LR696653G' ||
                    (ev.payload && ev.payload.capture_id === '10A71705XW788203L');

                  return (
                    <tr
                      key={ev.event_id}
                      className={`hover:bg-slate-850/50 transition-colors ${
                        isSandboxCapture ? 'bg-cyan-950/20' : ''
                      }`}
                    >
                      <td className="py-3 px-4 font-mono text-[11px] text-slate-500">
                        #{ev._ledger_index}
                      </td>
                      <td className="py-3 px-4 font-mono text-[11px] text-slate-300 max-w-[140px] truncate" title={ev.event_id}>
                        {ev.event_id}
                      </td>
                      <td className="py-3 px-4">
                        <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-slate-800 text-slate-300 border border-slate-700/60">
                          {ev.source_type}
                        </span>
                      </td>
                      <td className="py-3 px-4 font-mono text-[11px] text-cyan-400 max-w-[140px] truncate">
                        {ev.transaction_ref || ev.source_event_id}
                      </td>
                      <td className="py-3 px-4 font-mono text-[11px] text-slate-400">
                        {ev.current_hash ? `${ev.current_hash.slice(0, 10)}...${ev.current_hash.slice(-8)}` : 'N/A'}
                      </td>
                      <td className="py-3 px-4">
                        {ev.v2_migration ? (
                          <span className="px-2 py-0.5 rounded text-[10px] font-medium bg-blue-950/60 text-blue-300 border border-blue-800/40">
                            Migrated V2
                          </span>
                        ) : (
                          <span className="px-2 py-0.5 rounded text-[10px] font-medium bg-emerald-950/60 text-emerald-400 border border-emerald-800/40">
                            Active V2 Native
                          </span>
                        )}
                      </td>
                      <td className="py-3 px-4 text-right space-x-2">
                        <button
                          onClick={() => setSelectedEvent(ev)}
                          className="px-2 py-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 text-[11px] transition-colors"
                          title="View JSON Payload"
                        >
                          <Eye className="h-3 w-3 inline" />
                        </button>
                        <button
                          onClick={() => onSelectEventToVerify(ev.event_id)}
                          className="px-2.5 py-1 rounded bg-cyan-600/20 hover:bg-cyan-600/40 text-cyan-400 border border-cyan-500/30 text-[11px] font-medium transition-colors"
                        >
                          Verify
                        </button>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination Bar */}
        <div className="bg-slate-900/80 px-4 py-3 border-t border-slate-800 flex items-center justify-between text-xs text-slate-400">
          <div>
            Showing Page <span className="font-semibold text-slate-200">{page}</span> of{' '}
            <span className="font-semibold text-slate-200">{totalPages}</span>
          </div>
          <div className="flex items-center space-x-2">
            <button
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page <= 1}
              className="p-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 disabled:opacity-40"
            >
              <ChevronLeft className="h-4 w-4" />
            </button>
            <button
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              disabled={page >= totalPages}
              className="p-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 disabled:opacity-40"
            >
              <ChevronRight className="h-4 w-4" />
            </button>
          </div>
        </div>
      </div>

      {/* Raw Event JSON Drawer / Modal */}
      {selectedEvent && (
        <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-[#0b1120] border border-slate-800 rounded-2xl w-full max-w-2xl max-h-[85vh] flex flex-col shadow-2xl">
            <div className="p-4 border-b border-slate-800 flex items-center justify-between">
              <div>
                <h3 className="text-sm font-semibold text-white">Event Inspector</h3>
                <span className="text-xs font-mono text-slate-400">{selectedEvent.event_id}</span>
              </div>
              <div className="flex items-center space-x-2">
                <button
                  onClick={() => copyToClipboard(JSON.stringify(selectedEvent, null, 2), 'raw_json')}
                  className="px-2.5 py-1 text-xs rounded bg-slate-800 text-slate-300 hover:bg-slate-700 flex items-center space-x-1"
                >
                  {copiedKey === 'raw_json' ? <Check className="h-3 w-3 text-emerald-400" /> : <Copy className="h-3 w-3" />}
                  <span>Copy JSON</span>
                </button>
                <button
                  onClick={() => setSelectedEvent(null)}
                  className="p-1 rounded bg-slate-800 text-slate-400 hover:text-white"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>
            </div>
            <div className="p-4 overflow-y-auto font-mono text-xs text-cyan-300 bg-slate-950/70">
              <pre>{JSON.stringify(selectedEvent, null, 2)}</pre>
            </div>
            <div className="p-3 border-t border-slate-800 bg-slate-900/50 flex justify-end">
              <button
                onClick={() => {
                  const id = selectedEvent.event_id;
                  setSelectedEvent(null);
                  onSelectEventToVerify(id);
                }}
                className="px-4 py-2 rounded-lg bg-gradient-to-r from-cyan-500 to-blue-600 text-white font-medium text-xs"
              >
                Launch Multi-Dimensional Verification
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

