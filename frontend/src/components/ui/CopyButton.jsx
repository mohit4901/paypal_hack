import React, { useState } from 'react';
import { Copy, Check } from 'lucide-react';

export default function CopyButton({ value, label, className = '' }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async (e) => {
    e.stopPropagation();
    if (!value) return;
    try {
      await navigator.clipboard.writeText(String(value));
      setCopied(true);
      setTimeout(() => setCopied(false), 1600);
    } catch (_) {}
  };

  return (
    <button
      type="button"
      onClick={handleCopy}
      title={copied ? 'Copied' : `Copy ${label || 'value'}`}
      className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[11px] text-[#71717A] hover:text-[#18181B] hover:bg-[#EFECE4] transition-colors ${className}`}
    >
      {copied ? (
        <Check className="w-3 h-3 text-emerald-600" />
      ) : (
        <Copy className="w-3 h-3" />
      )}
      {label && <span>{copied ? 'Copied' : label}</span>}
    </button>
  );
}

