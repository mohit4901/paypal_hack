import React, { useState, useRef } from 'react';
import { Upload, AlertCircle } from 'lucide-react';
import { EVIDENCE_CATEGORIES } from '../../hooks/useEvidenceUpload';
import FileCard from '../ui/FileCard';

export default function EvidenceUploader({
  disputeId,
  files = [],
  selectedCategory,
  onChangeCategory,
  validationError,
  onFilesSelected,
  onRetry,
  onRemove,
  disabled = false,
  compact = false,
}) {
  const [isDragging, setIsDragging] = useState(false);
  const inputRef = useRef(null);

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
    if (disabled) return;
    if (e.dataTransfer?.files?.length) {
      onFilesSelected(disputeId, e.dataTransfer.files, selectedCategory);
    }
  };

  const handleBrowseChange = (e) => {
    if (e.target.files?.length) {
      onFilesSelected(disputeId, e.target.files, selectedCategory);
    }
    e.target.value = '';
  };

  return (
    <div className={compact ? 'space-y-4' : 'bg-white rounded-xl border border-[#E6E4DD] p-5 sm:p-6 space-y-5'}>
      {!compact ? (
        <div className="pb-4 border-b border-[#EFECE4] flex flex-col sm:flex-row sm:items-center justify-between gap-2">
          <div>
            <span className="text-[11px] font-mono font-medium text-[#0F766E] uppercase tracking-wider">
              Section 4
            </span>
            <h2 className="text-base font-semibold text-[#18181B]">Evidence Upload</h2>
            <p className="text-xs text-[#71717A] mt-0.5">
              Accepted formats: PDF, JPG/JPEG, PNG (up to 10 MB). Files are stored with a SHA-256 integrity hash only — document contents are not automatically OCR-extracted, parsed, or verified.
            </p>
          </div>
        </div>
      ) : (
        <p className="text-[11px] text-[#71717A]">
          Accepted formats: PDF, JPG/JPEG, PNG (up to 10 MB). Uploaded files are SHA-256 hashed for integrity only; file contents are not automatically OCR-extracted or independently verified.
        </p>
      )}

      {/* Evidence Category */}
      <div>
        <label htmlFor="evidenceCategorySelect" className="block text-xs font-medium text-[#3F3F46] mb-1.5">
          Evidence category
        </label>
        <select
          id="evidenceCategorySelect"
          value={selectedCategory}
          onChange={(e) => onChangeCategory(e.target.value)}
          disabled={disabled}
          className="w-full sm:w-80 px-3 py-2 rounded-lg text-xs bg-white border border-[#E6E4DD] text-[#18181B] focus:outline-none focus:ring-2 focus:ring-[#0F766E]/20 focus:border-[#0F766E]"
        >
          {EVIDENCE_CATEGORIES.map((cat) => (
            <option key={cat.value} value={cat.value}>
              {cat.label}
            </option>
          ))}
        </select>
      </div>

      {/* Drop Zone */}
      <div
        onDragOver={(e) => {
          e.preventDefault();
          if (!disabled) setIsDragging(true);
        }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={handleDrop}
        className={`rounded-xl border-2 border-dashed p-6 text-center transition-colors ${
          isDragging
            ? 'border-[#0F766E] bg-teal-50/50'
            : 'border-[#D4D4D8] bg-[#FCFBF8] hover:border-[#0F766E]/60'
        }`}
      >
        <input
          ref={inputRef}
          id="evidenceFileInput"
          type="file"
          accept=".pdf,.jpg,.jpeg,.png,application/pdf,image/jpeg,image/png"
          onChange={handleBrowseChange}
          disabled={disabled}
          className="sr-only"
        />

        <div className="mx-auto w-9 h-9 rounded-full bg-white border border-[#E6E4DD] flex items-center justify-center mb-2.5">
          <Upload className="w-4 h-4 text-[#0F766E]" />
        </div>
        <div className="text-xs font-medium text-[#18181B]">
          Drag &amp; drop fulfillment documents here
        </div>
        <div className="text-[11px] text-[#71717A] mt-1">
          PDF, JPG/JPEG, or PNG · Maximum file size 10 MB
        </div>

        <button
          type="button"
          onClick={() => inputRef.current?.click()}
          disabled={disabled}
          className="mt-3 inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg text-xs font-medium bg-white text-[#18181B] border border-[#E6E4DD] hover:bg-[#F8F7F3] disabled:opacity-50 transition-colors"
        >
          <span>Browse files</span>
        </button>
      </div>

      {validationError && (
        <div className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-xs text-rose-800 flex items-center gap-2">
          <AlertCircle className="w-4 h-4 text-rose-600 shrink-0" />
          <span>{validationError}</span>
        </div>
      )}

      {files.length > 0 && (
        <div className="space-y-2">
          <div className="text-xs font-medium text-[#52525B]">
            Attached files ({files.length})
          </div>
          {files.map((item) => (
            <FileCard
              key={item.localId}
              item={item}
              onRemove={onRemove}
              onRetry={(localId) => onRetry(disputeId, localId)}
              disabled={disabled}
            />
          ))}
        </div>
      )}
    </div>
  );
}

