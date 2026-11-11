import { useState, useRef, useCallback } from 'react';
import { api } from '../services/api';

export const BACKEND_STAGE_DEFINITIONS = [
  { step: 1, key: 'retrieve_dispute', title: 'Retrieve Dispute', description: 'Fetching dispute record and provenance context' },
  { step: 2, key: 'read_requested_evidence', title: 'Read Policy Requirement', description: 'Mapping PayPal evidence requirement type' },
  { step: 3, key: 'link_payment_order', title: 'Match PayPal Transaction', description: 'Linking Order ID and PayPal Capture ID deterministically' },
  { step: 4, key: 'validate_amount_currency', title: 'Validate Payment', description: 'Checking captured amount and currency consistency' },
  { step: 5, key: 'validate_tracking', title: 'Validate Tracking Syntax', description: 'Checking tracking ID format (syntax only — not carrier scan)' },
  { step: 6, key: 'check_delivery_evidence', title: 'Verify Delivery Evidence', description: 'Inspecting carrier telemetry and merchant attachments' },
  { step: 7, key: 'semantic_nli', title: 'Evaluate Claim vs Evidence', description: 'Running advisory DeBERTa-v3 semantic NLI alignment' },
  { step: 8, key: 'identify_gaps', title: 'Identify Contradictions & Gaps', description: 'Listing unverified or missing fulfillment facts' },
  { step: 9, key: 'prepare_grounded_response', title: 'Prepare Grounded Draft', description: 'Compiling response strictly from verified statements' },
  { step: 10, key: 'ready_for_review', title: 'Prepare Review Findings', description: 'Packaging findings for explicit merchant approval' },
];

function buildInitialStages() {
  return BACKEND_STAGE_DEFINITIONS.map((def) => ({
    ...def,
    status: 'PENDING',
    detail: 'Waiting for backend execution...',
    tone: 'pending',
    receivedAtIso: null,
    elapsedMs: null,
  }));
}

export function useDisputeAnalysis() {
  const [streamPhase, setStreamPhase] = useState('IDLE'); // 'IDLE' | 'STREAMING' | 'COMPLETE' | 'ERROR'
  const [analyzing, setAnalyzing] = useState(false);
  const [analysisError, setAnalysisError] = useState(null);
  const [stages, setStages] = useState(buildInitialStages);
  const [aiPrep, setAiPrep] = useState(null);
  const [claimVerification, setClaimVerification] = useState(null);
  const [claimsStale, setClaimsStale] = useState(false);
  const [verifyingClaims, setVerifyingClaims] = useState(false);

  const abortRef = useRef(null);
  const streamStartRef = useRef(null);

  const runStream = useCallback(async (disputeId, payload, { onCompleteResult } = {}) => {
    if (abortRef.current) {
      abortRef.current.abort();
    }
    const controller = new AbortController();
    abortRef.current = controller;
    streamStartRef.current = performance.now();

    setAnalyzing(true);
    setStreamPhase('STREAMING');
    setAnalysisError(null);
    setStages(
      buildInitialStages().map((s, idx) =>
        idx === 0 ? { ...s, status: 'RUNNING', detail: 'Connecting to backend SSE pipeline...' } : s
      )
    );

    try {
      const result = await api.streamAnalyzeDispute(disputeId, payload, {
        signal: controller.signal,
        onStage: (incoming) => {
          const nowMs = Math.round(performance.now() - (streamStartRef.current || performance.now()));
          const nowIso = new Date().toISOString();
          setStages((prev) =>
            prev.map((s) => {
              if (s.step === incoming.step) {
                return {
                  ...s,
                  ...incoming,
                  title: s.title, // Keep clear human-readable title while keeping incoming detail/status/tone
                  backendTitle: incoming.title,
                  receivedAtIso: nowIso,
                  elapsedMs: nowMs,
                };
              }
              if (s.step === incoming.step + 1 && s.status === 'PENDING') {
                return { ...s, status: 'RUNNING', detail: 'Processing...' };
              }
              return s;
            })
          );
        },
        onComplete: (finalResult) => {
          setAiPrep(finalResult);
          const nowIso = new Date().toISOString();
          if (Array.isArray(finalResult?.analysis_stages) && finalResult.analysis_stages.length) {
            setStages((prev) =>
              prev.map((s) => {
                const match = finalResult.analysis_stages.find((x) => x.step === s.step);
                if (!match) return s;
                return {
                  ...s,
                  ...match,
                  title: s.title,
                  backendTitle: match.title,
                  receivedAtIso: s.receivedAtIso || nowIso,
                };
              })
            );
          }
          setStreamPhase('COMPLETE');
          if (onCompleteResult) onCompleteResult(finalResult);
        },
        onError: (err) => {
          setAnalysisError(err.message || 'Streaming analysis failed');
          setStreamPhase('ERROR');
        },
      });
      return result;
    } catch (err) {
      if (err.name !== 'AbortError') {
        setAnalysisError(err.message || 'Failed to analyze dispute evidence');
        setStreamPhase('ERROR');
      }
      return null;
    } finally {
      setAnalyzing(false);
    }
  }, []);

  const runClaimAlignment = useCallback(async ({
    transactionReference,
    claims,
    evidenceRecords,
    customerDisputeReason = 'MERCHANDISE_OR_SERVICE_NOT_RECEIVED',
    claimedRecipient,
  }) => {
    if (!claims?.length || !evidenceRecords?.length) return null;
    setVerifyingClaims(true);
    try {
      const res = await api.verifyClaims({
        transaction_reference: transactionReference || 'UNKNOWN-ORDER',
        claims,
        evidence: evidenceRecords,
        evidence_records: evidenceRecords,
        customer_dispute_reason: customerDisputeReason,
        claimed_recipient: claimedRecipient || undefined,
      });
      setClaimVerification(res);
      setClaimsStale(false);
      return res;
    } catch (err) {
      setAnalysisError((prev) => prev || err.message || 'Claim alignment verification failed');
      return null;
    } finally {
      setVerifyingClaims(false);
    }
  }, []);

  const cancelStream = useCallback(() => {
    if (abortRef.current) abortRef.current.abort();
  }, []);

  const resetAnalysis = useCallback(() => {
    cancelStream();
    setStreamPhase('IDLE');
    setAnalyzing(false);
    setAnalysisError(null);
    setStages(buildInitialStages());
    setAiPrep(null);
    setClaimVerification(null);
    setClaimsStale(false);
  }, [cancelStream]);

  return {
    streamPhase,
    analyzing,
    analysisError,
    stages,
    aiPrep,
    setAiPrep,
    claimVerification,
    setClaimVerification,
    claimsStale,
    setClaimsStale,
    verifyingClaims,
    runStream,
    runClaimAlignment,
    cancelStream,
    resetAnalysis,
  };
}

