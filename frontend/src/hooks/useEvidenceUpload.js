import { useState, useCallback } from 'react';
import { api, validateEvidenceFile } from '../services/api';

export const EVIDENCE_CATEGORIES = [
  { value: 'order_confirmation', label: 'Order confirmation' },
  { value: 'payment_confirmation', label: 'Payment / capture confirmation' },
  { value: 'shipping_label', label: 'Shipping label' },
  { value: 'carrier_tracking_report', label: 'Carrier tracking report' },
  { value: 'proof_of_delivery', label: 'Proof of delivery' },
  { value: 'customer_communication', label: 'Customer communication' },
  { value: 'product_packing_records', label: 'Product / packing records' },
  { value: 'other_supporting_evidence', label: 'Other supporting evidence' },
];

export function formatBytes(bytes) {
  if (!Number.isFinite(bytes) || bytes <= 0) return '0 B';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}

export function useEvidenceUpload({ onEvidenceChanged, onToast } = {}) {
  const [files, setFiles] = useState([]);
  const [selectedCategory, setSelectedCategory] = useState('proof_of_delivery');
  const [validationError, setValidationError] = useState(null);

  const uploadSingle = useCallback(
    async (disputeId, item) => {
      setFiles((prev) =>
        prev.map((f) =>
          f.localId === item.localId
            ? { ...f, status: 'uploading', progress: 0, error: null }
            : f
        )
      );

      try {
        const res = await api.uploadSupportingEvidence(disputeId, item.file, (pct) => {
          setFiles((prev) =>
            prev.map((f) =>
              f.localId === item.localId ? { ...f, progress: pct } : f
            )
          );
        });

        setFiles((prev) =>
          prev.map((f) =>
            f.localId === item.localId
              ? {
                  ...f,
                  status: 'uploaded',
                  progress: 100,
                  error: null,
                  response: res,
                }
              : f
          )
        );
        if (onEvidenceChanged) onEvidenceChanged(`Uploaded "${res.filename}" — prior approval invalidated.`);
        if (onToast) onToast({ type: 'success', title: 'Document attached', message: `${res.filename} stored with SHA-256 digest.` });
        return res;
      } catch (err) {
        const msg = err.message || 'Upload failed';
        setFiles((prev) =>
          prev.map((f) =>
            f.localId === item.localId
              ? { ...f, status: 'error', error: msg }
              : f
          )
        );
        if (onToast) onToast({ type: 'error', title: 'Upload failed', message: msg });
        return null;
      }
    },
    [onEvidenceChanged, onToast]
  );

  const addAndUploadFiles = useCallback(
    async (disputeId, fileList, categoryOverride) => {
      setValidationError(null);
      const arr = Array.from(fileList || []);
      if (!arr.length) return [];

      const category = categoryOverride || selectedCategory;
      const results = [];

      for (const file of arr) {
        const check = validateEvidenceFile(file);
        if (!check.valid) {
          setValidationError(check.reason);
          if (onToast) onToast({ type: 'error', title: 'Unsupported file', message: check.reason });
          continue;
        }
        const localId = `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
        const entry = {
          localId,
          file,
          name: file.name,
          type: file.type || 'application/octet-stream',
          size: file.size,
          category,
          status: 'uploading',
          progress: 0,
          error: null,
          response: null,
        };
        setFiles((prev) => [...prev, entry]);
        const res = await uploadSingle(disputeId, entry);
        if (res) results.push(res);
      }

      return results;
    },
    [selectedCategory, uploadSingle, onToast]
  );

  const retryUpload = useCallback(
    async (disputeId, localId) => {
      const target = files.find((f) => f.localId === localId);
      if (!target || !target.file) return null;
      return await uploadSingle(disputeId, target);
    },
    [files, uploadSingle]
  );

  const removeFile = useCallback(
    (localId) => {
      setFiles((prev) => prev.filter((f) => f.localId !== localId));
      setValidationError(null);
      if (onEvidenceChanged) onEvidenceChanged('Supporting document removed — prior approval invalidated.');
    },
    [onEvidenceChanged]
  );

  const clearFiles = useCallback(() => {
    setFiles([]);
    setValidationError(null);
  }, []);

  const uploadedFiles = files.filter((f) => f.status === 'uploaded' && f.response);
  const primaryUploaded = uploadedFiles[uploadedFiles.length - 1] || null;
  const isUploading = files.some((f) => f.status === 'uploading');

  return {
    files,
    uploadedFiles,
    primaryUploaded,
    isUploading,
    selectedCategory,
    setSelectedCategory,
    validationError,
    setValidationError,
    addAndUploadFiles,
    retryUpload,
    removeFile,
    clearFiles,
  };
}

