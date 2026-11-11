import React from 'react';
import { Truck, Info } from 'lucide-react';

const CARRIERS = ['USPS', 'UPS', 'FedEx', 'DHL', 'Royal Mail', 'Canada Post', 'Other'];

export default function ShippingInformationForm({ form, onChange, errors = {} }) {
  return (
    <section className="bg-white rounded-xl border border-[#E6E4DD] p-5 sm:p-6 space-y-5">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pb-4 border-b border-[#EFECE4]">
        <div>
          <span className="text-[11px] font-mono font-medium text-[#0F766E] uppercase tracking-wider">
            Section 3
          </span>
          <h2 className="text-base font-semibold text-[#18181B]">Shipping &amp; Delivery Information</h2>
        </div>

        <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-[11px] font-medium bg-stone-100 text-stone-700 border border-stone-200 self-start sm:self-center">
          <Truck className="w-3.5 h-3.5" />
          <span>Carrier lookup not configured.</span>
        </span>
      </div>

      {/* Explicit Provenance Distinction Callout */}
      <div className="rounded-lg border border-amber-200 bg-amber-50/70 p-3.5 text-xs text-amber-950 flex items-start gap-2.5">
        <Info className="w-4 h-4 text-amber-700 shrink-0 mt-0.5" />
        <div className="space-y-1 leading-relaxed">
          <div className="font-semibold">
            Merchant entries below are treated strictly as MERCHANT_ATTESTATION — not independently verified carrier data.
          </div>
          <div className="text-[11px] text-amber-900">
            ProofLedger separates: (1) merchant-entered shipping inputs, (2) merchant-uploaded PDF/image files, and (3) automated carrier API lookups (currently unconfigured — no independent carrier scan is retrieved).
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div>
          <label htmlFor="carrierNameSelect" className="block text-xs font-medium text-[#3F3F46] mb-1.5">
            Carrier name
          </label>
          <select
            id="carrierNameSelect"
            value={form.carrierName || 'USPS'}
            onChange={(e) => onChange('carrierName', e.target.value)}
            className="w-full px-3 py-2 rounded-lg text-xs bg-white border border-[#E6E4DD] text-[#18181B] focus:outline-none focus:ring-2 focus:ring-[#0F766E]/20 focus:border-[#0F766E]"
          >
            {CARRIERS.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label htmlFor="trackingNumberInput" className="block text-xs font-medium text-[#3F3F46] mb-1.5">
            Tracking number
          </label>
          <input
            id="trackingNumberInput"
            type="text"
            value={form.trackingNumber || ''}
            onChange={(e) => onChange('trackingNumber', e.target.value)}
            placeholder="e.g., 9400111899223192348571 (optional if unavailable)"
            className={`w-full px-3 py-2 rounded-lg text-xs font-mono bg-white border ${
              errors.trackingNumber ? 'border-rose-400 ring-2 ring-rose-100' : 'border-[#E6E4DD]'
            } text-[#18181B] focus:outline-none focus:ring-2 focus:ring-[#0F766E]/20 focus:border-[#0F766E]`}
          />
          {errors.trackingNumber && <p className="mt-1 text-xs text-rose-700">{errors.trackingNumber}</p>}
        </div>

        <div>
          <label htmlFor="shippingAddressInput" className="block text-xs font-medium text-[#3F3F46] mb-1.5">
            Origin / shipping warehouse address
          </label>
          <input
            id="shippingAddressInput"
            type="text"
            value={form.shippingAddress || ''}
            onChange={(e) => onChange('shippingAddress', e.target.value)}
            placeholder="Optional (e.g., 210 Commerce Way, Austin, TX)"
            className="w-full px-3 py-2 rounded-lg text-xs bg-white border border-[#E6E4DD] text-[#18181B] focus:outline-none focus:ring-2 focus:ring-[#0F766E]/20 focus:border-[#0F766E]"
          />
        </div>

        <div>
          <label htmlFor="deliveryAddressInput" className="block text-xs font-medium text-[#3F3F46] mb-1.5">
            Customer delivery address
          </label>
          <input
            id="deliveryAddressInput"
            type="text"
            value={form.deliveryAddress || ''}
            onChange={(e) => onChange('deliveryAddress', e.target.value)}
            placeholder="Optional (e.g., 410 Pine St, Seattle, WA 98101)"
            className="w-full px-3 py-2 rounded-lg text-xs bg-white border border-[#E6E4DD] text-[#18181B] focus:outline-none focus:ring-2 focus:ring-[#0F766E]/20 focus:border-[#0F766E]"
          />
        </div>

        <div>
          <label htmlFor="shipmentDateInput" className="block text-xs font-medium text-[#3F3F46] mb-1.5">
            Shipment date
          </label>
          <input
            id="shipmentDateInput"
            type="date"
            value={form.shipmentDate || ''}
            onChange={(e) => onChange('shipmentDate', e.target.value)}
            className="w-full px-3 py-2 rounded-lg text-xs bg-white border border-[#E6E4DD] text-[#18181B] focus:outline-none focus:ring-2 focus:ring-[#0F766E]/20 focus:border-[#0F766E]"
          />
        </div>

        <div>
          <label htmlFor="estimatedDeliveryDateInput" className="block text-xs font-medium text-[#3F3F46] mb-1.5">
            Estimated delivery date (if known)
          </label>
          <input
            id="estimatedDeliveryDateInput"
            type="date"
            value={form.estimatedDeliveryDate || ''}
            onChange={(e) => onChange('estimatedDeliveryDate', e.target.value)}
            className="w-full px-3 py-2 rounded-lg text-xs bg-white border border-[#E6E4DD] text-[#18181B] focus:outline-none focus:ring-2 focus:ring-[#0F766E]/20 focus:border-[#0F766E]"
          />
        </div>

        <div>
          <label htmlFor="deliveryDateInput" className="block text-xs font-medium text-[#3F3F46] mb-1.5">
            Delivery date (only if supported by a source document)
          </label>
          <input
            id="deliveryDateInput"
            type="date"
            value={form.deliveryDate || ''}
            onChange={(e) => onChange('deliveryDate', e.target.value)}
            className="w-full px-3 py-2 rounded-lg text-xs bg-white border border-[#E6E4DD] text-[#18181B] focus:outline-none focus:ring-2 focus:ring-[#0F766E]/20 focus:border-[#0F766E]"
          />
        </div>

        <div className="md:col-span-2">
          <label htmlFor="fulfillmentNotesInput" className="block text-xs font-medium text-[#3F3F46] mb-1.5">
            Fulfillment &amp; dispatch notes
          </label>
          <textarea
            id="fulfillmentNotesInput"
            rows={2}
            value={form.fulfillmentNotes || ''}
            onChange={(e) => onChange('fulfillmentNotes', e.target.value)}
            placeholder="Summarize label creation, carrier pickup scan, or delivery notes supported by attached records."
            className="w-full px-3 py-2 rounded-lg text-xs bg-white border border-[#E6E4DD] text-[#18181B] focus:outline-none focus:ring-2 focus:ring-[#0F766E]/20 focus:border-[#0F766E]"
          />
        </div>
      </div>
    </section>
  );
}

