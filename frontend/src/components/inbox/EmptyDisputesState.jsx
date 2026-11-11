import React from 'react';
import { Globe, PlusCircle, RefreshCw } from 'lucide-react';
import EmptyState from '../ui/EmptyState';

export default function EmptyDisputesState({
  mode = 'no_live_paypal',
  onStartNewAnalysis,
  onShowLocalDemo,
  onSyncPayPal,
}) {
  if (mode === 'no_live_paypal') {
    return (
      <EmptyState
        icon={Globe}
        badge="PAYPAL SANDBOX API RETURNED 0 LIVE DISPUTES"
        title="No live PayPal disputes found."
        description="Your connected PayPal account currently has zero active disputes. You can analyze a local demonstration scenario (clearly marked LOCAL DEMO — NOT A PAYPAL DISPUTE) or start a new dispute analysis with custom order records."
        action={
          onShowLocalDemo && (
            <button
              type="button"
              onClick={onShowLocalDemo}
              className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-lg text-xs font-medium bg-[#18181B] text-white hover:bg-[#27272A] transition-colors"
            >
              <span>View Local Demo Scenarios</span>
            </button>
          )
        }
        secondaryAction={
          onStartNewAnalysis && (
            <button
              type="button"
              onClick={onStartNewAnalysis}
              className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-lg text-xs font-medium bg-white text-[#18181B] border border-[#E6E4DD] hover:bg-[#F8F7F3] transition-colors"
            >
              <PlusCircle className="w-3.5 h-3.5" />
              <span>New Analysis</span>
            </button>
          )
        }
      />
    );
  }

  return (
    <EmptyState
      badge="NO MATCHING DISPUTES"
      title="No disputes match your current filter."
      description="Clear active search or filter criteria, or refresh from the backend to check for newly synced cases."
      action={
        onSyncPayPal && (
          <button
            type="button"
            onClick={onSyncPayPal}
            className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-lg text-xs font-medium bg-white text-[#18181B] border border-[#E6E4DD] hover:bg-[#F8F7F3] transition-colors"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            <span>Sync PayPal</span>
          </button>
        )
      }
    />
  );
}

