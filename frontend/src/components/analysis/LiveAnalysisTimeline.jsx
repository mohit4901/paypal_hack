import React from 'react';
import {
  CheckCircle2,
  AlertTriangle,
  XCircle,
  Loader2,
  Circle,
  MinusCircle,
  RefreshCw,
  ArrowRight,
  Cpu,
} from 'lucide-react';
import StatusBadge from '../ui/StatusBadge';
import ErrorState from '../ui/ErrorState';

function resolveStageVisual(stage) {
  const status = String(stage.status || 'PENDING').toUpperCase();
  const tone = String(stage.tone || '').toLowerCase();

  if (status === 'RUNNING') {
    return {
      stateLabel: 'Running',
      icon: Loader2,
      iconCls: 'text-[#0F766E] animate-spin',
      dotCls: 'bg-teal-50 border-[#0F766E]',
    };
  }
  if (status === 'SKIPPED' || status === 'UNSUPPORTED') {
    return {
      stateLabel: 'Skipped',
      icon: MinusCircle,
      iconCls: 'text-stone-500',
      dotCls: 'bg-stone-100 border-stone-300',
    };
  }
  if (tone === 'error' || ['FAILED', 'MISMATCH', 'FORMAT_INVALID', 'MODEL_FAILED', 'MODEL_OFFLINE', 'MODEL_UNAVAILABLE'].includes(status)) {
    return {
      stateLabel: status === 'MODEL_OFFLINE' || status === 'MODEL_UNAVAILABLE' ? 'Unavailable' : 'Failed',
      icon: XCircle,
      iconCls: 'text-rose-600',
      dotCls: 'bg-rose-50 border-rose-300',
    };
  }
  if (
    tone === 'warning' ||
    ['WARNING', 'GAPS_IDENTIFIED', 'LOOKUP_NOT_CONFIGURED', 'MERCHANT_ATTESTATION', 'ACTION_REQUIRED', 'NOT_PROVIDED'].includes(status)
  ) {
    return {
      stateLabel: 'Warning',
      icon: AlertTriangle,
      iconCls: 'text-amber-600',
      dotCls: 'bg-amber-50 border-amber-300',
    };
  }
  if (
    tone === 'success' ||
    ['COMPLETED', 'VERIFIED', 'FORMAT_VALID', 'READY'].includes(status)
  ) {
    return {
      stateLabel: 'Completed',
      icon: CheckCircle2,
      iconCls: 'text-emerald-600',
      dotCls: 'bg-emerald-50 border-emerald-300',
    };
  }
  return {
    stateLabel: 'Pending',
    icon: Circle,
    iconCls: 'text-zinc-300',
    dotCls: 'bg-white border-zinc-200',
  };
}

export default function LiveAnalysisTimeline({
  disputeId,
  stages = [],
  streamPhase = 'IDLE', // 'IDLE' | 'STREAMING' | 'COMPLETE' | 'ERROR'
  analysisError = null,
  onRetry,
  onViewResults,
}) {
  const activeStage =
    stages.find((s) => s.status === 'RUNNING') ||
    [...stages].reverse().find((s) => s.status !== 'PENDING') ||
    stages[0];

  const completedCount = stages.filter((s) => s.status !== 'PENDING' && s.status !== 'RUNNING').length;

  return (
    <div className="space-y-4">
      {streamPhase === 'ERROR' && (
        <ErrorState
          title="Live analysis stream interrupted"
          message={analysisError || 'The backend SSE stream encountered an error. Existing inputs are preserved.'}
          onRetry={onRetry}
          retryLabel="Retry Analysis"
        />
      )}

      <div className="bg-white rounded-xl border border-[#E6E4DD] p-5 sm:p-6">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-4 border-b border-[#EFECE4]">
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-base font-semibold text-[#18181B]">
                Live Evidence Analysis
              </h2>
              {streamPhase === 'STREAMING' && (
                <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[11px] font-medium bg-teal-50 text-[#0F766E] border border-teal-200">
                  <span className="w-1.5 h-1.5 rounded-full bg-[#0F766E] animate-ping" />
                  <span>Streaming SSE ({completedCount}/{stages.length})</span>
                </span>
              )}
              {streamPhase === 'COMPLETE' && (
                <StatusBadge size="xs" variant="verified" label="Analysis Complete" />
              )}
              {streamPhase === 'ERROR' && (
                <StatusBadge size="xs" variant="error" label="Stream Failed" />
              )}
            </div>
            <p className="text-xs text-[#71717A] mt-0.5 font-mono">
              Target case: {disputeId} · Real-time Server-Sent Events (/analyze-stream)
            </p>
          </div>

          <div className="flex items-center gap-2">
            {onRetry && (
              <button
                type="button"
                onClick={onRetry}
                disabled={streamPhase === 'STREAMING'}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-white text-[#18181B] border border-[#E6E4DD] hover:bg-[#F8F7F3] disabled:opacity-50 transition-colors"
              >
                <RefreshCw className={`w-3.5 h-3.5 ${streamPhase === 'STREAMING' ? 'animate-spin' : ''}`} />
                <span>Re-run</span>
              </button>
            )}
            {streamPhase === 'COMPLETE' && onViewResults && (
              <button
                type="button"
                onClick={onViewResults}
                className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg text-xs font-medium bg-[#18181B] text-white hover:bg-[#27272A] transition-colors"
              >
                <span>Open Verification Report</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </button>
            )}
          </div>
        </div>

        <div className="mt-5 grid grid-cols-1 lg:grid-cols-12 gap-6">
          {/* Left: Vertical 10-Stage Timeline */}
          <div className="lg:col-span-7 space-y-0">
            {stages.map((stage, idx) => {
              const vis = resolveStageVisual(stage);
              const Icon = vis.icon;
              const isLast = idx === stages.length - 1;

              return (
                <div key={stage.step} className="relative flex gap-3.5 pb-4">
                  {!isLast && (
                    <span
                      className="absolute left-[13px] top-7 bottom-0 w-px bg-[#E6E4DD]"
                      aria-hidden="true"
                    />
                  )}
                  <div
                    className={`w-7 h-7 rounded-full border flex items-center justify-center shrink-0 z-10 ${vis.dotCls}`}
                  >
                    <Icon className={`w-3.5 h-3.5 ${vis.iconCls}`} />
                  </div>
                  <div className="flex-1 min-w-0 pt-0.5">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <div className="flex items-center gap-2 min-w-0">
                        <span className="font-mono text-[11px] text-[#71717A]">
                          {String(stage.step).padStart(2, '0')}
                        </span>
                        <span className="text-xs font-semibold text-[#18181B] truncate">
                          {stage.title}
                        </span>
                      </div>
                      <div className="flex items-center gap-2">
                        {stage.elapsedMs != null && (
                          <span className="text-[10px] font-mono text-[#71717A] tabular-nums">
                            {stage.elapsedMs} ms
                          </span>
                        )}
                        <StatusBadge
                          size="xs"
                          status={stage.status}
                          tone={stage.tone}
                          label={stage.status === 'PENDING' ? 'Pending' : stage.status}
                          showIcon={false}
                        />
                      </div>
                    </div>
                    <p className="text-xs text-[#52525B] mt-0.5 leading-relaxed">
                      {stage.detail}
                    </p>
                  </div>
                </div>
              );
            })}
          </div>

          {/* Right: Current Activity Details Panel */}
          <div className="lg:col-span-5">
            <div className="sticky top-20 rounded-xl border border-[#E6E4DD] bg-[#FCFBF8] p-4 space-y-4">
              <div className="flex items-center justify-between">
                <span className="text-[11px] font-mono uppercase tracking-wider text-[#71717A]">
                  Current Pipeline Activity
                </span>
                <Cpu className="w-4 h-4 text-[#0F766E]" />
              </div>

              {activeStage && (
                <div className="bg-white rounded-lg border border-[#E6E4DD] p-4 space-y-2">
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-mono text-xs text-[#0F766E] font-semibold">
                      Stage {String(activeStage.step).padStart(2, '0')} / 10
                    </span>
                    <StatusBadge
                      size="xs"
                      status={activeStage.status}
                      tone={activeStage.tone}
                      label={activeStage.status}
                    />
                  </div>
                  <div className="text-sm font-semibold text-[#18181B]">
                    {activeStage.backendTitle || activeStage.title}
                  </div>
                  <div className="text-xs text-[#52525B] leading-relaxed">
                    {activeStage.detail}
                  </div>
                  {activeStage.receivedAtIso && (
                    <div className="pt-2 border-t border-[#EFECE4] text-[11px] font-mono text-[#71717A] flex justify-between">
                      <span>Received</span>
                      <span>{new Date(activeStage.receivedAtIso).toLocaleTimeString()}</span>
                    </div>
                  )}
                </div>
              )}

              <div className="text-[11px] text-[#52525B] leading-relaxed space-y-1.5">
                <div className="font-medium text-[#18181B]">Audit guarantee</div>
                <p>
                  Stages reflect live events emitted by <code className="font-mono">POST /api/v2/disputes/{disputeId}/analyze-stream</code>. Deterministic payment and tracking checks cannot be bypassed by neural predictions.
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

