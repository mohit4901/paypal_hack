import React from 'react';
import { Search } from 'lucide-react';

export const INBOX_FILTERS = [
  { id: 'ALL', label: 'All' },
  { id: 'NEEDS_REVIEW', label: 'Needs review' },
  { id: 'EVIDENCE_INCOMPLETE', label: 'Evidence incomplete' },
  { id: 'APPROVED', label: 'Approved' },
  { id: 'LIVE_PAYPAL', label: 'Live PayPal' },
  { id: 'LOCAL_DEMO', label: 'Local demo' },
];

export default function DisputeFilters({
  activeFilter,
  onChangeFilter,
  searchQuery,
  onChangeSearch,
  counts = {},
}) {
  return (
    <div className="flex flex-col md:flex-row md:items-center justify-between gap-3">
      <div className="flex flex-wrap items-center gap-1.5">
        {INBOX_FILTERS.map((f) => {
          const isActive = activeFilter === f.id;
          const count = counts[f.id];
          return (
            <button
              key={f.id}
              type="button"
              onClick={() => onChangeFilter(f.id)}
              className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium border transition-colors ${
                isActive
                  ? 'bg-[#18181B] text-white border-[#18181B]'
                  : 'bg-white text-[#52525B] border-[#E6E4DD] hover:text-[#18181B] hover:border-[#D4D4D8]'
              }`}
            >
              <span>{f.label}</span>
              {typeof count === 'number' && (
                <span
                  className={`text-[10px] font-mono tabular-nums px-1.5 py-0.2 rounded ${
                    isActive ? 'bg-white/20 text-white' : 'bg-[#F8F7F3] text-[#71717A]'
                  }`}
                >
                  {count}
                </span>
              )}
            </button>
          );
        })}
      </div>

      <div className="relative w-full md:w-72 shrink-0">
        <Search className="w-3.5 h-3.5 text-[#71717A] absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" />
        <input
          type="text"
          value={searchQuery}
          onChange={(e) => onChangeSearch(e.target.value)}
          placeholder="Search Dispute ID, Order ID, reason..."
          aria-label="Search disputes"
          className="w-full pl-8 pr-3 py-1.5 rounded-lg text-xs bg-white border border-[#E6E4DD] text-[#18181B] placeholder:text-[#A1A1AA] focus:outline-none focus:ring-2 focus:ring-[#0F766E]/20 focus:border-[#0F766E]"
        />
      </div>
    </div>
  );
}

