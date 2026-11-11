/**
 * Real-time Server-Sent Events (SSE) consumer for ProofLedger's 10-stage
 * dispute analysis pipeline: POST /api/v2/disputes/{disputeId}/analyze-stream.
 *
 * Strictly emits only real backend stages and never invents completion states.
 */

export function getAuthHeaderValue() {
  const storedKey =
    typeof window !== 'undefined' && window.localStorage
      ? window.localStorage.getItem('proofledger_seller_key')
      : null;
  if (storedKey && storedKey.trim()) {
    const clean = storedKey.trim();
    return clean.startsWith('Bearer ') ? clean : `Bearer ${clean}`;
  }
  return 'Bearer key_alpha_123';
}

export async function streamDisputeAnalysis({
  apiBase,
  disputeId,
  payload,
  ApiErrorClass,
  onStage,
  onComplete,
  onError,
  signal,
}) {
  let res;
  try {
    res = await fetch(`${apiBase}/disputes/${encodeURIComponent(disputeId)}/analyze-stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'text/event-stream',
        Authorization: getAuthHeaderValue(),
      },
      body: JSON.stringify(payload || {}),
      signal,
    });
  } catch (networkErr) {
    if (networkErr.name === 'AbortError') {
      throw networkErr;
    }
    const err = new ApiErrorClass(
      'Cannot reach analysis stream endpoint. Verify the backend server is running.',
      0,
      'BACKEND_OFFLINE'
    );
    if (onError) onError(err);
    throw err;
  }

  if (!res.ok) {
    let detail = `HTTP error ${res.status}`;
    try {
      const j = await res.json();
      detail = j.detail || detail;
    } catch (_) {
      try {
        detail = (await res.text()) || detail;
      } catch (__) {}
    }
    const err = new ApiErrorClass(detail, res.status, detail);
    if (onError) onError(err);
    throw err;
  }

  if (!res.body) {
    const err = new ApiErrorClass('Streaming response body unavailable.', 502, 'STREAM_UNAVAILABLE');
    if (onError) onError(err);
    throw err;
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder('utf-8');
  let buffer = '';
  let finalResult = null;

  try {
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const frames = buffer.split('\n\n');
      buffer = frames.pop() || '';
      for (const frame of frames) {
        const dataLines = frame
          .split('\n')
          .filter((l) => l.startsWith('data: '))
          .map((l) => l.slice(6));
        if (!dataLines.length) continue;
        const rawJson = dataLines.join('\n');
        try {
          const msg = JSON.parse(rawJson);
          if (msg.event === 'stage' && onStage) {
            onStage(msg.stage);
          } else if (msg.event === 'complete') {
            finalResult = msg.result;
            if (onComplete) onComplete(msg.result);
          } else if (msg.event === 'error') {
            const err = new ApiErrorClass(msg.detail || 'Stream error', msg.status || 500, msg.detail);
            if (onError) onError(err);
            throw err;
          }
        } catch (parseErr) {
          if (parseErr instanceof ApiErrorClass) throw parseErr;
          console.warn('SSE frame parse skipped:', parseErr);
        }
      }
    }
  } catch (streamErr) {
    if (streamErr.name !== 'AbortError' && onError && !(streamErr instanceof ApiErrorClass)) {
      onError(new ApiErrorClass(streamErr.message || 'SSE connection interrupted', 0, 'STREAM_INTERRUPTED'));
    }
    throw streamErr;
  }

  if (!finalResult) {
    const err = new ApiErrorClass(
      'Analysis stream closed before receiving final verification result.',
      502,
      'INCOMPLETE_STREAM'
    );
    if (onError) onError(err);
    throw err;
  }

  return finalResult;
}

