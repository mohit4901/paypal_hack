import React from 'react';
import { FileText, Image as ImageIcon, CheckCircle2, AlertCircle, Trash2, RefreshCw } from 'lucide-react';
import { formatBytes, EVIDENCE_CATEGORIES } from '../../hooks/useEvidenceUpload';

export default function FileCard({ item, onRemove, onRetry, disabled = false }) {
  const isImage = (item.type || '').startsWith('image/') || /\.(jpg|jpeg|png)$/i.test(item.name || '');
  const Icon = isImage ? ImageIcon : FileText;
  const catLabel =
    EVIDENCE_CATEGORIES.find((c) => c.value === item.category)?.label || item.category || 'Supporting evidence';

  return (
    <div className="bg-white rounded-lg border border-[#E6E4DD] p-3 flex flex-col gap-2">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-start gap-2.5 min-w-0">
          <div className="w-8 h-8 rounded-lg bg-[#F8F7F3] border border-[#E6E4DD] flex items-center justify-center shrink-0">
            <Icon className="w-4 h-4 text-[#3F3F46]" />
          </div>
          <div className="min-w-0">
            <div className="text-xs font-medium text-[#18181B] truncate">{item.name}</div>
            <div className="flex flex-wrap items-center gap-x-2 gap-y-0.5 text-[11px] text-[#71717A] mt-0.5">
              <span>{catLabel}</span>
              <span>·</span>
              <span>{formatBytes(item.size)}</span>
              <span>·</span>
              <span className="uppercase">{item.type || 'document'}</span>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-1.5 shrink-0">
          {item.status === 'error' && onRetry && (
            <button
              type="button"
              onClick={() => onRetry(item.localId)}
              disabled={disabled}
              title="Retry upload"
              className="p-1.5 rounded-md text-amber-700 hover:bg-amber-50 border border-amber-200 transition-colors"
            >
              <RefreshCw className="w-3.5 h-3.5" />
            </button>
          )}
          {onRemove && (
            <button
              type="button"
              onClick={() => onRemove(item.localId)}
              disabled={disabled}
              title="Remove file"
              className="p-1.5 rounded-md text-[#71717A] hover:text-rose-700 hover:bg-rose-50 transition-colors"
            >
              <Trash2 className="w-3.5 h-3.5" />
            </button>
          )}
        </div>
      </div>

      {item.status === 'uploading' && (
        <div className="space-y-1">
          <div className="flex justify-between text-[11px] text-[#52525B]">
            <span>Uploading to ProofLedger...</span>
            <span className="tabular-nums font-mono">{item.progress || 0}%</span>
          </div>
          <div className="h-1.5 bg-[#EFECE4] rounded-full overflow-hidden">
            <div
              className="h-full bg-[#0F766E] transition-all duration-150"
              style={{ width: `${item.progress || 0}%` }}
            />
          </div>
        </div>
      )}

      {item.status === 'uploaded' && item.response && (
        <div className="space-y-1.5 text-[11px] bg-emerald-50/70 border border-emerald-200 rounded-md px-2.5 py-2 text-emerald-950">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <span className="inline-flex items-center gap-1 font-semibold text-emerald-900">
              <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
              SHA-256 integrity verified
            </span>
            <span className="inline-flex items-center px-1.5 py-0.5 rounded font-mono text-[10px] font-medium bg-sky-50 text-sky-800 border border-sky-200">
              CONTENT_NOT_EXTRACTED
            </span>
          </div>
          {item.response.file_sha256 && (
            <div className="font-mono text-[10px] text-emerald-800 break-all">
              SHA-256: {item.response.file_sha256}
            </div>
          )}
          <div className="text-[10px] text-[#52525B]">
            File bytes hashed for integrity only — contents are not OCR-parsed or verified by AI.
          </div>
        </div>
      )}

      {item.status === 'error' && (
        <div className="flex items-center gap-1.5 text-[11px] bg-rose-50 border border-rose-200 rounded-md px-2.5 py-1.5 text-rose-800">
          <AlertCircle className="w-3.5 h-3.5 text-rose-600 shrink-0" />
          <span>{item.error || 'Upload failed.'}</span>
        </div>
      )}
    </div>
  );
}

