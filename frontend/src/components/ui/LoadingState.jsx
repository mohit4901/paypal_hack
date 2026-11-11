import React from 'react';

export default function LoadingState({ rows = 3, label = 'Loading verification records...' }) {
  return (
    <div className="bg-white rounded-xl border border-[#E6E4DD] p-6 space-y-4">
      <div className="flex items-center gap-2 text-xs text-[#52525B]">
        <div className="w-3.5 h-3.5 rounded-full border-2 border-[#0F766E] border-t-transparent animate-spin" />
        <span>{label}</span>
      </div>
      <div className="space-y-3 animate-pulse">
        {Array.from({ length: rows }).map((_, i) => (
          <div key={i} className="h-10 bg-[#F8F7F3] rounded-lg border border-[#EFECE4]" />
        ))}
      </div>
    </div>
  );
}

