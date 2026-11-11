import React from 'react';
import {
  CheckCircle2,
  AlertTriangle,
  XCircle,
  Info,
  Clock,
  ShieldAlert,
  MinusCircle,
} from 'lucide-react';

const STATUS_THEMES = {
  verified: {
    cls: 'bg-emerald-50 text-emerald-800 border-emerald-200',
    icon: CheckCircle2,
    iconCls: 'text-emerald-600',
  },
  warning: {
    cls: 'bg-amber-50 text-amber-800 border-amber-200',
    icon: AlertTriangle,
    iconCls: 'text-amber-600',
  },
  error: {
    cls: 'bg-rose-50 text-rose-800 border-rose-200',
    icon: XCircle,
    iconCls: 'text-rose-600',
  },
  info: {
    cls: 'bg-sky-50 text-sky-800 border-sky-200',
    icon: Info,
    iconCls: 'text-sky-600',
  },
  neutral: {
    cls: 'bg-stone-100 text-stone-700 border-stone-200',
    icon: MinusCircle,
    iconCls: 'text-stone-500',
  },
  pending: {
    cls: 'bg-[#F8F7F3] text-zinc-600 border-zinc-200',
    icon: Clock,
    iconCls: 'text-zinc-400',
  },
  risk: {
    cls: 'bg-rose-50 text-rose-800 border-rose-200',
    icon: ShieldAlert,
    iconCls: 'text-rose-600',
  },
};

export function inferStatusVariant(status = '', tone = '') {
  const s = String(status).toUpperCase();
  const t = String(tone).toLowerCase();
  if (
    s === 'VERIFIED_ON_PAYPAL' ||
    s === 'VERIFIED_ON_MERCHANT_RECORD' ||
    s === 'VERIFIED_ON_LEDGER' ||
    s === 'DELIVERY_CONFIRMED' ||
    s === 'SUPPORTED' ||
    s === 'COMPLETED' ||
    s === 'VERIFIED' ||
    s === 'READY' ||
    s === 'AVAILABLE' ||
    s === 'APPROVED' ||
    s === 'RESOLVED_SELLER_FAVOR' ||
    s === 'RESOLVED' ||
    s === 'ONLINE' ||
    s === 'MODEL_LOADED' ||
    t === 'success'
  ) {
    return 'verified';
  }
  if (s === 'FORMAT_VALID' || s === 'MERCHANT_ATTESTATION' || s === 'UNDER_PAYPAL_REVIEW' || t === 'info') {
    return 'info';
  }
  if (
    s === 'CONTRADICTED' ||
    s === 'MISMATCH' ||
    s === 'FAILED' ||
    s === 'FORMAT_INVALID' ||
    s === 'LOOKUP_FAILED' ||
    s === 'MODEL_UNAVAILABLE' ||
    s === 'MODEL_OFFLINE' ||
    s === 'MODEL_FAILED' ||
    t === 'error'
  ) {
    return 'error';
  }
  if (
    s === 'INSUFFICIENT_EVIDENCE' ||
    s === 'WAITING_FOR_SELLER_RESPONSE' ||
    s === 'ACTION_REQUIRED' ||
    s === 'GAPS_IDENTIFIED' ||
    s === 'MISSING' ||
    s === 'NEEDS_REVIEW' ||
    s === 'NEEDS_ATTENTION' ||
    s === 'NOT_INDEPENDENTLY_VERIFIED' ||
    s === 'NEEDS_HUMAN_REVIEW' ||
    s === 'STALE' ||
    t === 'warning'
  ) {
    return 'warning';
  }
  if (s === 'LOOKUP_NOT_CONFIGURED' || s === 'NOT_PROVIDED' || s === 'UNAVAILABLE' || s === 'SKIPPED') {
    return 'neutral';
  }
  return 'neutral';
}

export default function StatusBadge({
  status,
  label,
  tone,
  variant,
  showIcon = true,
  size = 'sm',
  className = '',
}) {
  const resolved = variant || inferStatusVariant(status, tone);
  const theme = STATUS_THEMES[resolved] || STATUS_THEMES.neutral;
  const Icon = theme.icon;
  const sizeCls =
    size === 'xs'
      ? 'px-2 py-0.5 text-[11px] gap-1'
      : 'px-2.5 py-1 text-xs gap-1.5';

  return (
    <span
      className={`inline-flex items-center rounded-md border font-medium whitespace-nowrap ${theme.cls} ${sizeCls} ${className}`}
    >
      {showIcon && <Icon className={`w-3.5 h-3.5 shrink-0 ${theme.iconCls}`} />}
      <span>{label || status}</span>
    </span>
  );
}

