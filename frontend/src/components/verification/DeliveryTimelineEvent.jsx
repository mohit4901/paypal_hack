import React from 'react';
import {
  CheckCircle2,
  UserCheck,
  FileCode2,
  AlertTriangle,
  XCircle,
  MinusCircle,
} from 'lucide-react';
import StatusBadge from '../ui/StatusBadge';

const STATE_CONFIG = {
  VERIFIED: {
    variant: 'verified',
    dotCls: 'bg-emerald-50 border-emerald-400 text-emerald-700',
    cardCls: 'border-emerald-200 bg-white',
    icon: CheckCircle2,
  },
  MERCHANT_ATTESTATION: {
    variant: 'info',
    dotCls: 'bg-sky-50 border-sky-400 text-sky-700',
    cardCls: 'border-[#E6E4DD] bg-white',
    icon: UserCheck,
  },
  FORMAT_VALID: {
    variant: 'info',
    dotCls: 'bg-sky-50 border-sky-300 text-sky-700',
    cardCls: 'border-[#E6E4DD] bg-white',
    icon: FileCode2,
  },
  MISSING_EVIDENCE: {
    variant: 'warning',
    dotCls: 'bg-amber-50 border-amber-400 text-amber-700',
    cardCls: 'border-amber-200 bg-amber-50/25',
    icon: AlertTriangle,
  },
  EXCEPTION: {
    variant: 'error',
    dotCls: 'bg-rose-50 border-rose-400 text-rose-700',
    cardCls: 'border-rose-200 bg-rose-50/30',
    icon: XCircle,
  },
  UNAVAILABLE: {
    variant: 'neutral',
    dotCls: 'bg-stone-100 border-stone-300 text-stone-500',
    cardCls: 'border-[#E6E4DD] bg-[#FCFBF8]',
    icon: MinusCircle,
  },
};

export default function DeliveryTimelineEvent({ event, isLast = false }) {
  const cfg = STATE_CONFIG[event.visualState] || STATE_CONFIG.UNAVAILABLE;
  const Icon = cfg.icon;

  return (
    <div className="relative flex gap-4 pb-6">
      {!isLast && (
        <span
          className="absolute left-[15px] top-8 bottom-0 w-px bg-[#E4E0D5]"
          aria-hidden="true"
        />
      )}

      <div
        className={`w-8 h-8 rounded-full border flex items-center justify-center shrink-0 z-10 ${cfg.dotCls}`}
      >
        <Icon className="w-4 h-4" />
      </div>

      <div className={`flex-1 rounded-xl border p-4 space-y-2 ${cfg.cardCls}`}>
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex items-center gap-2 min-w-0">
            <span className="font-mono text-[11px] text-[#71717A]">
              {event.stepNumber}
            </span>
            <h3 className="text-sm font-semibold text-[#18181B]">
              {event.title}
            </h3>
          </div>
          <StatusBadge
            size="xs"
            variant={cfg.variant}
            status={event.statusCode}
            label={event.badgeLabel}
          />
        </div>

        {(event.timestamp || event.carrier || event.location || event.trackingNumber || event.source) && (
          <div className="flex flex-wrap gap-x-4 gap-y-1 text-[11px] text-[#52525B]">
            {event.carrier && (
              <span>
                <strong className="font-medium text-[#18181B]">Carrier:</strong> {event.carrier}
              </span>
            )}
            {event.trackingNumber && (
              <span className="font-mono">
                <strong className="font-sans font-medium text-[#18181B]">Tracking:</strong> {event.trackingNumber}
              </span>
            )}
            {event.timestamp && (
              <span>
                <strong className="font-medium text-[#18181B]">Date:</strong> {event.timestamp}
              </span>
            )}
            {event.location && (
              <span>
                <strong className="font-medium text-[#18181B]">Location:</strong> {event.location}
              </span>
            )}
            {event.source && (
              <span>
                <strong className="font-medium text-[#18181B]">Source:</strong> {event.source}
              </span>
            )}
          </div>
        )}

        <p className="text-xs text-[#3F3F46] leading-relaxed">
          {event.explanation}
        </p>
      </div>
    </div>
  );
}

