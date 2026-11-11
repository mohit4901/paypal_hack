import React from 'react';
import { CheckCircle2, AlertCircle, Info, X } from 'lucide-react';

export default function ToastContainer({ toasts = [], onDismiss }) {
  if (!toasts.length) return null;

  return (
    <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2 max-w-sm w-full px-4 sm:px-0 pointer-events-none">
      {toasts.map((t) => {
        const isErr = t.type === 'error';
        const isOk = t.type === 'success';
        const Icon = isErr ? AlertCircle : isOk ? CheckCircle2 : Info;
        const cls = isErr
          ? 'border-rose-200 bg-white text-rose-950'
          : isOk
          ? 'border-emerald-200 bg-white text-emerald-950'
          : 'border-[#E6E4DD] bg-white text-[#18181B]';

        return (
          <div
            key={t.id}
            className={`pointer-events-auto rounded-xl border p-3.5 shadow-lg flex items-start gap-2.5 ${cls}`}
          >
            <Icon
              className={`w-4 h-4 shrink-0 mt-0.5 ${
                isErr ? 'text-rose-600' : isOk ? 'text-emerald-600' : 'text-[#0F766E]'
              }`}
            />
            <div className="flex-1 min-w-0">
              {t.title && <div className="text-xs font-semibold">{t.title}</div>}
              {t.message && <div className="text-xs text-[#52525B] mt-0.5 break-words">{t.message}</div>}
            </div>
            {onDismiss && (
              <button
                type="button"
                onClick={() => onDismiss(t.id)}
                className="p-0.5 rounded text-[#71717A] hover:text-[#18181B]"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            )}
          </div>
        );
      })}
    </div>
  );
}

