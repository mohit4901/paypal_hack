import React from 'react';
import { Inbox } from 'lucide-react';

export default function EmptyState({
  icon: Icon = Inbox,
  title,
  description,
  badge,
  action,
  secondaryAction,
  className = '',
}) {
  return (
    <div className={`bg-white rounded-xl border border-[#E6E4DD] p-8 text-center ${className}`}>
      <div className="mx-auto w-10 h-10 rounded-full bg-[#F8F7F3] border border-[#E6E4DD] flex items-center justify-center mb-3">
        <Icon className="w-5 h-5 text-[#52525B]" />
      </div>
      {badge && (
        <div className="mb-2 flex justify-center">
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-md text-[11px] font-medium bg-stone-100 text-stone-700 border border-stone-200">
            {badge}
          </span>
        </div>
      )}
      <h3 className="text-sm font-semibold text-[#18181B]">{title}</h3>
      {description && (
        <p className="mt-1.5 text-xs text-[#52525B] max-w-md mx-auto leading-relaxed">
          {description}
        </p>
      )}
      {(action || secondaryAction) && (
        <div className="mt-4 flex flex-wrap items-center justify-center gap-2">
          {action}
          {secondaryAction}
        </div>
      )}
    </div>
  );
}

