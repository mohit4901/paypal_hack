import React from 'react';

export default function PageHeader({ title, subtitle, badge, actions }) {
  return (
    <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-4 pb-5 border-b border-[#E6E4DD]">
      <div className="space-y-1 min-w-0">
        {badge && <div className="mb-1.5">{badge}</div>}
        <h1 className="text-xl sm:text-2xl font-semibold text-[#18181B] tracking-tight">
          {title}
        </h1>
        {subtitle && (
          <p className="text-sm text-[#52525B] max-w-2xl leading-relaxed">
            {subtitle}
          </p>
        )}
      </div>
      {actions && (
        <div className="flex flex-wrap items-center gap-2 shrink-0">
          {actions}
        </div>
      )}
    </div>
  );
}

