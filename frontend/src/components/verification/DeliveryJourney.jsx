import React from 'react';
import { Truck, Info, AlertCircle } from 'lucide-react';
import DeliveryTimelineEvent from './DeliveryTimelineEvent';
import { detectChronologicalAnomalies } from '../../utils/evidenceRules';

/**
 * Derives truthful chronological shipping milestones strictly from real backend outputs,
 * store evidence records, and merchant inputs — never fabricating scans or timestamps.
 */
function buildJourneyEvents({
  carrierName,
  trackingNumber,
  documentName,
  fulfillmentNotes,
  aiPrep,
  dispute,
  txEvidence = [],
  merchantContext = {},
}) {
  const events = [];
  const items = aiPrep?.evidence_items || [];
  const trackingItem = items.find((i) => i.item === 'Tracking Number') || {};
  const scanItem = items.find((i) => i.item === 'Carrier Delivery Scan') || {};

  const trackingValid =
    trackingItem.status === 'FORMAT_VALID' ||
    Boolean(trackingNumber && /^[A-Za-z0-9\-_]{6,35}$/.test(trackingNumber.trim()));
  const lookupNotConfigured =
    scanItem.status === 'LOOKUP_NOT_CONFIGURED' || !dispute?.carrier_api_verified;

  // Combine textual records to inspect ONLY actual supplied carrier/shipment signals
  const allTexts = [
    fulfillmentNotes || '',
    ...txEvidence.map((e) => `${e.source_type || ''} ${e.event_type || ''} ${e.content || ''}`),
    ...(dispute?.default_evidence || []).map((e) => `${e.source_type || ''} ${e.event_type || ''} ${e.content || ''}`),
  ]
    .join('\n')
    .toLowerCase();

  // Verified carrier records only if explicit verified courier telemetry is flagged is_verified_source
  const verifiedCarrierRecords = [...(dispute?.default_evidence || []), ...txEvidence].filter(
    (e) =>
      e.is_verified_source &&
      /carrier|shipping|delivery|tracking/i.test(`${e.source_type || ''} ${e.source_name || ''}`)
  );

  // Check chronological ordering if dates supplied
  const chronoIssues = detectChronologicalAnomalies({
    orderDate: merchantContext?.orderDate,
    shipmentDate: merchantContext?.shipmentDate,
    deliveryDate: merchantContext?.deliveryDate,
  }).map((m) => `Chronological inconsistency: ${m}`);

  // 00 / 01: Label & Tracking Registration
  if (trackingNumber) {
    events.push({
      stepNumber: '01',
      title: 'Shipping Label Created / Tracking Supplied',
      visualState: trackingValid ? 'FORMAT_VALID' : 'EXCEPTION',
      statusCode: trackingValid ? 'FORMAT_VALID' : 'FORMAT_INVALID',
      badgeLabel: trackingValid ? 'FORMAT_VALID' : 'FORMAT_INVALID',
      carrier: carrierName || undefined,
      trackingNumber,
      timestamp: merchantContext?.shipmentDate || undefined,
      location: merchantContext?.shippingAddress || undefined,
      source: 'Merchant Input (Syntax Validator)',
      explanation: trackingValid
        ? 'The tracking number follows the expected format, but no independent carrier scan was retrieved.'
        : 'The supplied tracking number failed syntax validation.',
    });
  } else {
    events.push({
      stepNumber: '01',
      title: 'Shipping Label Created / Tracking Number',
      visualState: 'MISSING_EVIDENCE',
      statusCode: 'NOT_PROVIDED',
      badgeLabel: 'NOT PROVIDED',
      source: 'Merchant Fulfillment Form',
      explanation: 'No tracking number has been provided yet.',
    });
  }

  // 02: Carrier Pickup / Parcel Collected
  const verifiedPickup = verifiedCarrierRecords.find((e) =>
    /pickup|collected|acceptance|origin scan/i.test(e.content || '')
  );
  const attestedPickup =
    !verifiedPickup && /pickup|collected|dropped off|carrier scan|acceptance/i.test(allTexts);

  if (verifiedPickup) {
    events.push({
      stepNumber: '02',
      title: 'Carrier Pickup / Parcel Collected',
      visualState: 'VERIFIED',
      statusCode: 'VERIFIED',
      badgeLabel: 'VERIFIED',
      carrier: carrierName || undefined,
      trackingNumber: trackingNumber || undefined,
      timestamp: verifiedPickup.timestamp || undefined,
      source: verifiedPickup.source_name || verifiedPickup.source_type,
      explanation: 'Physical carrier collection is confirmed by the supplied verified carrier record.',
    });
  } else if (attestedPickup && documentName) {
    events.push({
      stepNumber: '02',
      title: 'Carrier Pickup / Parcel Collected',
      visualState: 'MERCHANT_ATTESTATION',
      statusCode: 'MERCHANT_ATTESTATION',
      badgeLabel: 'MERCHANT_ATTESTATION',
      carrier: carrierName || undefined,
      trackingNumber: trackingNumber || undefined,
      timestamp: merchantContext?.shipmentDate || undefined,
      source: `Uploaded document (${documentName})`,
      explanation: 'Merchant notes/document reference carrier pickup, pending independent courier API confirmation.',
    });
  } else {
    events.push({
      stepNumber: '02',
      title: 'Carrier Pickup / Parcel Collected',
      visualState: 'MISSING_EVIDENCE',
      statusCode: 'NOT_INDEPENDENTLY_VERIFIED',
      badgeLabel: 'NOT VERIFIED',
      carrier: carrierName || undefined,
      source: 'Carrier Pickup Scan',
      explanation:
        'Physical carrier collection is NOT VERIFIED. Label generation or tracking number syntax alone does not establish physical carrier possession.',
    });
  }

  // 03–05: Only display Transit / Regional Facility / Out for Delivery when actually present in evidence
  if (/in transit|departed facility|transit/i.test(allTexts)) {
    events.push({
      stepNumber: '03',
      title: 'In Transit',
      visualState: verifiedCarrierRecords.length ? 'VERIFIED' : 'MERCHANT_ATTESTATION',
      statusCode: verifiedCarrierRecords.length ? 'VERIFIED' : 'MERCHANT_ATTESTATION',
      badgeLabel: verifiedCarrierRecords.length ? 'VERIFIED' : 'MERCHANT_ATTESTATION',
      carrier: carrierName || undefined,
      source: documentName || 'Merchant fulfillment record',
      explanation: 'Transit event noted in submitted fulfillment text/records.',
    });
  }

  if (/regional facility|arrived at hub|sorting hub|customs gateway/i.test(allTexts)) {
    events.push({
      stepNumber: '04',
      title: 'Arrived at Regional Facility',
      visualState: verifiedCarrierRecords.length ? 'VERIFIED' : 'MERCHANT_ATTESTATION',
      statusCode: verifiedCarrierRecords.length ? 'VERIFIED' : 'MERCHANT_ATTESTATION',
      badgeLabel: verifiedCarrierRecords.length ? 'VERIFIED' : 'MERCHANT_ATTESTATION',
      carrier: carrierName || undefined,
      source: documentName || 'Submitted carrier text',
      explanation: 'Intermediate facility scan noted in submitted records (does not verify final delivery).',
    });
  }

  if (/out for delivery/i.test(allTexts)) {
    events.push({
      stepNumber: '05',
      title: 'Out for Delivery',
      visualState: verifiedCarrierRecords.length ? 'VERIFIED' : 'MERCHANT_ATTESTATION',
      statusCode: verifiedCarrierRecords.length ? 'VERIFIED' : 'MERCHANT_ATTESTATION',
      badgeLabel: verifiedCarrierRecords.length ? 'VERIFIED' : 'MERCHANT_ATTESTATION',
      carrier: carrierName || undefined,
      source: documentName || 'Submitted carrier text',
      explanation: 'Out-for-delivery scan noted in submitted records.',
    });
  }

  // 06: Final Delivery Confirmation (or 07 Exception/RTS if explicitly present)
  const hasDeliveryException = /returned to sender|return to sender|undeliverable|delivery failed|refused|lost in transit/i.test(allTexts);
  if (hasDeliveryException) {
    events.push({
      stepNumber: '07',
      title: 'Delivery Exception / Returned',
      visualState: 'EXCEPTION',
      statusCode: 'CONTRADICTED',
      badgeLabel: 'EXCEPTION / RETURNED',
      carrier: carrierName || undefined,
      trackingNumber: trackingNumber || undefined,
      source: documentName || 'Submitted Evidence',
      explanation: 'Submitted records contain a delivery exception or return-to-sender indicator that conflicts with confirmed delivery.',
    });
  } else {
    const verifiedDeliv = verifiedCarrierRecords.find((e) =>
      /delivered|signed pod|proof of delivery/i.test(e.content || '')
    );
    const verifiedDelivTimestamp = verifiedDeliv?.timestamp || merchantContext?.deliveryDate;
    if (verifiedDeliv && verifiedDelivTimestamp) {
      events.push({
        stepNumber: '06',
        title: 'Delivered',
        visualState: 'VERIFIED',
        statusCode: 'DELIVERY_CONFIRMED',
        badgeLabel: 'VERIFIED',
        carrier: carrierName || undefined,
        trackingNumber: trackingNumber || undefined,
        timestamp: verifiedDelivTimestamp,
        location: merchantContext?.deliveryAddress || undefined,
        source: verifiedDeliv.source_name || verifiedDeliv.source_type,
        explanation: 'Delivery confirmation established by an independently verified source record and explicit delivery date.',
      });
    } else if (merchantContext?.deliveryDate) {
      events.push({
        stepNumber: '06',
        title: 'Delivery Claimed by Merchant (Unverified)',
        visualState: 'MERCHANT_ATTESTATION',
        statusCode: 'MERCHANT_ATTESTATION',
        badgeLabel: 'MERCHANT_ATTESTATION',
        carrier: carrierName || undefined,
        trackingNumber: trackingNumber || undefined,
        timestamp: merchantContext.deliveryDate,
        location: merchantContext?.deliveryAddress || undefined,
        source: documentName ? `Merchant entry + attached ${documentName} (CONTENT_NOT_EXTRACTED)` : 'Merchant delivery date entry',
        explanation: documentName
          ? `Merchant entered a delivery date and attached "${documentName}" (SHA-256 integrity verified · CONTENT_NOT_EXTRACTED). Because no independent carrier scan is verified, Delivered status is not established.`
          : 'Merchant supplied delivery date as attestation only; no independent carrier delivery record confirms Delivered status.',
      });
    } else {
      events.push({
        stepNumber: '06',
        title: 'Delivery Confirmation Pending',
        visualState: lookupNotConfigured ? 'UNAVAILABLE' : 'MISSING_EVIDENCE',
        statusCode: 'LOOKUP_NOT_CONFIGURED',
        badgeLabel: 'LOOKUP_NOT_CONFIGURED',
        carrier: carrierName || undefined,
        trackingNumber: trackingNumber || undefined,
        location: merchantContext?.deliveryAddress || undefined,
        source: documentName ? `Courier Tracking API · Attached ${documentName} (CONTENT_NOT_EXTRACTED)` : 'Courier Tracking API',
        explanation: documentName
          ? `Attachment "${documentName}" has SHA-256 integrity verified (CONTENT_NOT_EXTRACTED); attaching a file alone does not establish delivery, and courier delivery scan lookup is unavailable.`
          : 'No verified delivery date or independent carrier delivery scan has been provided.',
      });
    }
  }

  return { events, chronoIssues, lookupNotConfigured };
}

export default function DeliveryJourney({
  carrierName,
  trackingNumber,
  documentName,
  fulfillmentNotes,
  aiPrep,
  dispute,
  txEvidence,
  merchantContext,
}) {
  const { events, chronoIssues, lookupNotConfigured } = buildJourneyEvents({
    carrierName,
    trackingNumber,
    documentName,
    fulfillmentNotes,
    aiPrep,
    dispute,
    txEvidence,
    merchantContext,
  });

  return (
    <section className="bg-white rounded-xl border border-[#E6E4DD] p-5 sm:p-6 space-y-5">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-4 border-b border-[#EFECE4]">
        <div className="flex items-start gap-3">
          <div className="w-9 h-9 rounded-lg bg-[#F0FDFA] border border-[#99F6E4] flex items-center justify-center shrink-0">
            <Truck className="w-4 h-4 text-[#0F766E]" />
          </div>
          <div>
            <h2 className="text-base font-semibold text-[#18181B]">
              Delivery Verification Journey
            </h2>
            <p className="text-xs text-[#52525B] mt-0.5">
              Follow every available shipping event, from shipment preparation to final delivery.
            </p>
          </div>
        </div>

        {carrierName && (
          <div className="text-xs font-mono text-[#52525B] bg-[#F8F7F3] border border-[#E6E4DD] px-2.5 py-1 rounded-md self-start sm:self-center">
            {carrierName}{trackingNumber ? ` · ${trackingNumber}` : ''}
          </div>
        )}
      </div>

      {/* Honest Provenance Separation Strip: Merchant Attestation vs Independent Carrier Verification */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5 text-[11px]">
        <div className="rounded-lg border border-sky-200 bg-sky-50/60 px-3 py-2 flex items-center justify-between gap-2">
          <span className="font-medium text-sky-950">Merchant Attestation &amp; Uploads</span>
          <span className="font-mono text-[10px] px-1.5 py-0.5 rounded bg-white border border-sky-200 text-sky-800">
            MERCHANT_ATTESTATION / FORMAT_VALID
          </span>
        </div>
        <div className="rounded-lg border border-stone-200 bg-[#F8F7F3] px-3 py-2 flex items-center justify-between gap-2">
          <span className="font-medium text-[#18181B]">Independent Carrier Verification</span>
          <span className="font-mono text-[10px] px-1.5 py-0.5 rounded bg-white border border-stone-200 text-stone-700">
            {lookupNotConfigured ? 'LOOKUP_NOT_CONFIGURED' : 'CARRIER_API_VERIFIED'}
          </span>
        </div>
      </div>

      {/* Honest Carrier Lookup Unavailable Notice */}
      {lookupNotConfigured && (
        <div className="rounded-lg border border-stone-200 bg-[#F8F7F3] p-3.5 flex items-start gap-2.5 text-xs text-[#3F3F46]">
          <Info className="w-4 h-4 text-[#71717A] shrink-0 mt-0.5" />
          <div>
            <div className="font-semibold text-[#18181B]">
              Independent carrier verification unavailable.
            </div>
            <div className="text-[#52525B] mt-0.5">
              Delivery information shown here is based only on submitted merchant records and documents.
            </div>
          </div>
        </div>
      )}

      {/* Chronological Order Flag */}
      {chronoIssues.length > 0 && (
        <div className="rounded-lg border border-rose-200 bg-rose-50 p-3.5 space-y-1 text-xs text-rose-900">
          <div className="font-semibold flex items-center gap-1.5">
            <AlertCircle className="w-4 h-4 text-rose-600" />
            <span>Chronological timestamp anomaly detected</span>
          </div>
          {chronoIssues.map((msg, i) => (
            <div key={i}>{msg}</div>
          ))}
        </div>
      )}

      {/* Vertical Connected Milestone Rail */}
      <div className="pt-1">
        {events.map((ev, idx) => (
          <DeliveryTimelineEvent
            key={`${ev.stepNumber}-${ev.title}`}
            event={ev}
            isLast={idx === events.length - 1}
          />
        ))}
      </div>
    </section>
  );
}
