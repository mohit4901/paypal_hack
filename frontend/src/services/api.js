/**
 * Production API Client for ProofLedger Backend (/api/v2/*).
 * Preserves authentic server error states, timeouts, auth headers, and real XHR upload progress.
 */
import { getAuthHeaderValue, streamDisputeAnalysis } from './analysisStream';
import {
  ALLOWED_EVIDENCE_MIME_TYPES,
  ALLOWED_EVIDENCE_EXTENSIONS,
  MAX_EVIDENCE_BYTES,
  validateEvidenceFile,
} from '../utils/evidenceRules';

const API_BASE = (import.meta.env && import.meta.env.VITE_API_BASE_URL) || '/api/v2';

export {
  ALLOWED_EVIDENCE_MIME_TYPES,
  ALLOWED_EVIDENCE_EXTENSIONS,
  MAX_EVIDENCE_BYTES,
  validateEvidenceFile,
};

export class ApiError extends Error {
  constructor(message, status, detail, data) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.detail = detail || message;
    this.data = data;
    this.isOffline = status === 0 || status === 502 || status === 503 || status === 504;
    this.isNotFound = status === 404;
    this.isUnprocessable = status === 422;
    this.isUnauthorized = status === 401 || status === 403;
    this.isConflict = status === 409;
  }
}

async function fetchJson(endpoint, options = {}) {
  const timeoutMs = options.timeout || 20000;
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);
  const signal = options.signal ? options.signal : controller.signal;

  const customHeaders = options.headers || {};
  const authHeader =
    customHeaders.Authorization ||
    customHeaders['X-Seller-Key'] ||
    getAuthHeaderValue();

  try {
    const res = await fetch(`${API_BASE}${endpoint}`, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        Accept: 'application/json',
        Authorization: authHeader,
        ...customHeaders,
      },
      signal,
    });

    clearTimeout(timeoutId);

    if (!res.ok) {
      let errDetail = `HTTP error ${res.status}`;
      let errJson = null;
      try {
        errJson = await res.json();
        errDetail = errJson.detail || errDetail;
      } catch (_) {
        try {
          errDetail = (await res.text()) || errDetail;
        } catch (__) {}
      }
      throw new ApiError(errDetail, res.status, errDetail, errJson);
    }

    return await res.json();
  } catch (err) {
    clearTimeout(timeoutId);
    if (err instanceof ApiError) throw err;
    if (err.name === 'AbortError') {
      throw new ApiError(`Request to ${endpoint} timed out after ${timeoutMs}ms`, 408, 'REQUEST_TIMEOUT');
    }
    throw new ApiError(
      `Cannot connect to backend server at ${API_BASE}. Ensure the FastAPI service is running.`,
      0,
      'BACKEND_OFFLINE'
    );
  }
}

export function uploadEvidenceWithProgress(disputeId, file, onProgress) {
  const validation = validateEvidenceFile(file);
  if (!validation.valid) {
    return Promise.reject(new ApiError(validation.reason, 415, 'UNSUPPORTED_MEDIA_TYPE'));
  }

  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open('POST', `${API_BASE}/disputes/${encodeURIComponent(disputeId)}/upload-evidence`);
    xhr.setRequestHeader('Authorization', getAuthHeaderValue());

    xhr.upload.onprogress = (evt) => {
      if (evt.lengthComputable && onProgress) {
        const pct = Math.min(100, Math.round((evt.loaded / evt.total) * 100));
        onProgress(pct);
      }
    };

    xhr.onload = () => {
      let body = null;
      try {
        body = JSON.parse(xhr.responseText);
      } catch (_) {}

      if (xhr.status >= 200 && xhr.status < 300) {
        if (onProgress) onProgress(100);
        resolve(body);
      } else {
        const detail = body?.detail || `Upload failed (${xhr.status})`;
        reject(new ApiError(detail, xhr.status, detail, body));
      }
    };

    xhr.onerror = () => {
      reject(new ApiError('Network error during file upload.', 0, 'BACKEND_OFFLINE'));
    };

    xhr.onabort = () => {
      reject(new ApiError('Upload cancelled.', 499, 'UPLOAD_ABORTED'));
    };

    const formData = new FormData();
    formData.append('file', file);
    xhr.send(formData);
  });
}

export const api = {
  getBaseUrl: () => API_BASE,

  // Consolidated Readiness
  getSystemStatus: (options) => fetchJson('/system/status', options),
  getOverview: (options) => fetchJson('/overview', options),

  // Live PayPal Sandbox
  syncPayPal: (options) => fetchJson('/paypal/sync', { method: 'POST', ...options }),
  getPayPalLiveFeed: (options) => fetchJson('/paypal/live-feed', options),
  getLiveCapture: (id, options) => fetchJson(`/paypal/live-capture/${encodeURIComponent(id)}`, options),
  getLiveOrder: (id, options) => fetchJson(`/paypal/live-order/${encodeURIComponent(id)}`, options),
  getLiveWebhooks: (options) => fetchJson('/paypal/live-webhooks', options),
  generateLiveTransaction: (options) => fetchJson('/paypal/generate-live-transaction', { method: 'POST', ...options }),
  importLivePayPalOrder: (payload, options) =>
    fetchJson('/paypal/import-live', {
      method: 'POST',
      body: JSON.stringify(payload),
      ...options,
    }),

  // Transactions & Store Evidence
  getTransactions: (options) => fetchJson('/transactions', options),
  getTransaction: (id, options) => fetchJson(`/transactions/${encodeURIComponent(id)}`, options),
  getTransactionEvidence: (id, options) => fetchJson(`/transactions/${encodeURIComponent(id)}/evidence`, options),
  createTransaction: (payload, options) =>
    fetchJson('/transactions', {
      method: 'POST',
      body: JSON.stringify(payload),
      ...options,
    }),
  addCustomEvidence: (orderId, payload, options) =>
    fetchJson(`/transactions/${encodeURIComponent(orderId)}/evidence`, {
      method: 'POST',
      body: JSON.stringify(payload),
      ...options,
    }),

  // Disputes, SSE Streaming, Upload, SHA-256 Approval & Submission
  getDisputes: (options) => fetchJson('/disputes', options),
  getDispute: (id, options) => fetchJson(`/disputes/${encodeURIComponent(id)}`, options),
  prepareDisputeResponse: (disputeId, payload, options) =>
    fetchJson(`/disputes/${encodeURIComponent(disputeId)}/prepare-response`, {
      method: 'POST',
      body: JSON.stringify(payload),
      ...options,
    }),
  streamAnalyzeDispute: (disputeId, payload, handlers = {}) =>
    streamDisputeAnalysis({
      apiBase: API_BASE,
      disputeId,
      payload,
      ApiErrorClass: ApiError,
      ...handlers,
    }),
  uploadSupportingEvidence: (disputeId, file, onProgress) =>
    uploadEvidenceWithProgress(disputeId, file, onProgress),
  approveFulfillmentEvidence: (disputeId, payload, options) =>
    fetchJson(`/disputes/${encodeURIComponent(disputeId)}/approve-evidence`, {
      method: 'POST',
      body: JSON.stringify(payload),
      ...options,
    }),
  submitDisputeEvidence: (disputeId, payload, options) =>
    fetchJson(`/disputes/${encodeURIComponent(disputeId)}/provide-evidence`, {
      method: 'POST',
      body: JSON.stringify(payload),
      ...options,
    }),
  getDisputeScenarios: (options) => fetchJson('/disputes/scenarios', options),
  getDisputeScenario: (id, options) => fetchJson(`/disputes/scenarios/${encodeURIComponent(id)}`, options),
  getVerificationRuns: (params = {}, options) => {
    const query = new URLSearchParams(params).toString();
    return fetchJson(`/disputes/runs${query ? `?${query}` : ''}`, options);
  },
  getVerificationRun: (runId, options) => fetchJson(`/disputes/runs/${encodeURIComponent(runId)}`, options),
  verifyClaims: (payload, options) =>
    fetchJson('/disputes/verify-claims', {
      method: 'POST',
      body: JSON.stringify(payload),
      timeout: 30000,
      ...options,
    }),
  approveDisputePacket: (disputeId, payload, options) =>
    fetchJson(`/disputes/${encodeURIComponent(disputeId)}/approve`, {
      method: 'POST',
      body: JSON.stringify(payload),
      ...options,
    }),

  // Seller Multi-Tenant Identity
  getSellerProfile: (options) => fetchJson('/sellers/me', options),
  registerSeller: (payload, options) =>
    fetchJson('/sellers/register', {
      method: 'POST',
      body: JSON.stringify(payload),
      ...options,
    }),
  rotateSellerKey: (options) =>
    fetchJson('/sellers/rotate-key', {
      method: 'POST',
      ...options,
    }),

  // AI Model Diagnostics
  getAiStatus: (options) => fetchJson('/ai/status', options),
  testAiInference: (payload, options) =>
    fetchJson('/ai/test-inference', {
      method: 'POST',
      body: JSON.stringify(payload),
      timeout: 30000,
      ...options,
    }),

  // Forensic Events, Ledger & Security
  getEvents: (params = {}, options) => {
    const query = new URLSearchParams(params).toString();
    return fetchJson(`/events${query ? `?${query}` : ''}`, options);
  },
  getEventById: (id, options) => fetchJson(`/events/${encodeURIComponent(id)}`, options),
  verifyEvent: (id, options) => fetchJson(`/verification/${encodeURIComponent(id)}`, options),
  getLedger: (options) => fetchJson('/ledger', options),
  validateLedger: (options) => fetchJson('/ledger/validate', options),
  getMigration: (options) => fetchJson('/migration', options),
  getCheckpoints: (options) => fetchJson('/checkpoints', options),
  createCheckpoint: (keyId, options) =>
    fetchJson('/checkpoints/create', {
      method: 'POST',
      body: JSON.stringify({ key_id: keyId }),
      ...options,
    }),
  getKeys: (options) => fetchJson('/keys', options),
  getSecurity: (options) => fetchJson('/security', options),
  getReconciliation: (options) => fetchJson('/reconciliation', options),
};
