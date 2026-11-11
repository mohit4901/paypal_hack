import React from 'react';

export default function MetricCard({
  label,
  value,
  sublabel,
  icon: Icon,
  tone = 'default',
  onClick,
  active = false,
}) {
  const toneBorder =
    tone === 'warning'
      ? 'border-amber-200/80'
      : tone === 'success'
      ? 'border-emerald-200/80'
      : tone === 'error'
      ? 'border-rose-200/80'
      : 'border-[#E6E4DD]';

  const interactiveCls = onClick
    ? `cursor-pointer hover:border-[#0F766E]/50 transition-colors ${active ? 'ring-2 ring-[#0F766E]/20 border-[#0F766E]' : ''}`
    : '';

  return (
    <div
      onClick={onClick}
      role={onClick ? 'button' : undefined}
      tabIndex={onClick ? 0 : undefined}
      onKeyDown={onClick ? (e) => (e.key === 'Enter' || e.key === ' ') && onClick() : undefined}
      className={`bg-white rounded-xl border ${toneBorder} p-4 ${interactiveCls}`}
    >
      <div className="flex items-center justify-between gap-2">
        <span className="text-xs font-medium text-[#52525B]">{label}</span>
        {Icon && <Icon className="w-4 h-4 text-[#71717A] shrink-0" />}
      </div>
      <div className="mt-2 text-2xl font-semibold text-[#18181B] tabular-nums tracking-tight">
        {value}
      </div>
      {sublabel && (
        <div className="mt-1 text-xs text-[#71717A] truncate">{sublabel}</div>
      )}
    </div>
  );
}

