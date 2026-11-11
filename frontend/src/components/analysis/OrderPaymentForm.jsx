import React from 'react';
import StatusBadge from '../ui/StatusBadge';

const CURRENCIES = ['USD', 'EUR', 'GBP', 'CAD', 'AUD', 'INR', 'JPY'];

export default function OrderPaymentForm({ form, onChange, errors = {} }) {
  return (
    <section className="bg-white rounded-xl border border-[#E6E4DD] p-5 sm:p-6 space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-2 pb-4 border-b border-[#EFECE4]">
        <div>
          <span className="text-[11px] font-mono font-medium text-[#0F766E] uppercase tracking-wider">
            Section 2
          </span>
          <h2 className="text-base font-semibold text-[#18181B]">Order &amp; Payment Details</h2>
        </div>

        {form.backendPaymentStatus && (
          <StatusBadge
            size="xs"
            status={form.backendPaymentStatus}
            label={`Record payment status: ${form.backendPaymentStatus}`}
          />
        )}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div>
          <label htmlFor="orderIdInput" className="block text-xs font-medium text-[#3F3F46] mb-1.5">
            Order ID <span className="text-rose-600">*</span>
          </label>
          <input
            id="orderIdInput"
            type="text"
            value={form.orderId || ''}
            onChange={(e) => onChange('orderId', e.target.value)}
            placeholder="e.g., ORD-2026-9910"
            className={`w-full px-3 py-2 rounded-lg text-xs font-mono bg-white border ${
              errors.orderId ? 'border-rose-400 ring-2 ring-rose-100' : 'border-[#E6E4DD]'
            } text-[#18181B] focus:outline-none focus:ring-2 focus:ring-[#0F766E]/20 focus:border-[#0F766E]`}
          />
          {errors.orderId && <p className="mt-1 text-xs text-rose-700">{errors.orderId}</p>}
        </div>

        <div>
          <label htmlFor="captureIdInput" className="block text-xs font-medium text-[#3F3F46] mb-1.5">
            PayPal transaction / capture ID
          </label>
          <input
            id="captureIdInput"
            type="text"
            value={form.captureId || ''}
            onChange={(e) => onChange('captureId', e.target.value)}
            placeholder="e.g., 10A71705XW788203L (optional if not captured)"
            className="w-full px-3 py-2 rounded-lg text-xs font-mono bg-white border border-[#E6E4DD] text-[#18181B] focus:outline-none focus:ring-2 focus:ring-[#0F766E]/20 focus:border-[#0F766E]"
          />
        </div>

        <div>
          <label htmlFor="orderAmountInput" className="block text-xs font-medium text-[#3F3F46] mb-1.5">
            Order amount <span className="text-rose-600">*</span>
          </label>
          <input
            id="orderAmountInput"
            type="text"
            value={form.amount || ''}
            onChange={(e) => onChange('amount', e.target.value)}
            placeholder="e.g., 49.00"
            className={`w-full px-3 py-2 rounded-lg text-xs font-mono bg-white border ${
              errors.amount ? 'border-rose-400 ring-2 ring-rose-100' : 'border-[#E6E4DD]'
            } text-[#18181B] focus:outline-none focus:ring-2 focus:ring-[#0F766E]/20 focus:border-[#0F766E]`}
          />
          {errors.amount && <p className="mt-1 text-xs text-rose-700">{errors.amount}</p>}
        </div>

        <div>
          <label htmlFor="orderCurrencySelect" className="block text-xs font-medium text-[#3F3F46] mb-1.5">
            Currency
          </label>
          <select
            id="orderCurrencySelect"
            value={form.currency || 'USD'}
            onChange={(e) => onChange('currency', e.target.value)}
            className="w-full px-3 py-2 rounded-lg text-xs bg-white border border-[#E6E4DD] text-[#18181B] focus:outline-none focus:ring-2 focus:ring-[#0F766E]/20 focus:border-[#0F766E]"
          >
            {CURRENCIES.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label htmlFor="orderDateInput" className="block text-xs font-medium text-[#3F3F46] mb-1.5">
            Order date
          </label>
          <input
            id="orderDateInput"
            type="date"
            value={form.orderDate || ''}
            onChange={(e) => onChange('orderDate', e.target.value)}
            className="w-full px-3 py-2 rounded-lg text-xs bg-white border border-[#E6E4DD] text-[#18181B] focus:outline-none focus:ring-2 focus:ring-[#0F766E]/20 focus:border-[#0F766E]"
          />
        </div>

        <div>
          <label htmlFor="parcelCountInput" className="block text-xs font-medium text-[#3F3F46] mb-1.5">
            Quantity / number of parcels
          </label>
          <input
            id="parcelCountInput"
            type="number"
            min="1"
            value={form.parcelCount || ''}
            onChange={(e) => onChange('parcelCount', e.target.value)}
            placeholder="Optional (e.g., 1)"
            className="w-full px-3 py-2 rounded-lg text-xs bg-white border border-[#E6E4DD] text-[#18181B] focus:outline-none focus:ring-2 focus:ring-[#0F766E]/20 focus:border-[#0F766E]"
          />
        </div>

        <div className="md:col-span-2">
          <label htmlFor="productDescInput" className="block text-xs font-medium text-[#3F3F46] mb-1.5">
            Product or service description
          </label>
          <input
            id="productDescInput"
            type="text"
            value={form.productDescription || ''}
            onChange={(e) => onChange('productDescription', e.target.value)}
            placeholder="e.g., Mechanical Keyboard Kit or SaaS Developer Seat"
            className="w-full px-3 py-2 rounded-lg text-xs bg-white border border-[#E6E4DD] text-[#18181B] focus:outline-none focus:ring-2 focus:ring-[#0F766E]/20 focus:border-[#0F766E]"
          />
        </div>

        <div>
          <label htmlFor="buyerEmailInput" className="block text-xs font-medium text-[#3F3F46] mb-1.5">
            Buyer email (if known)
          </label>
          <input
            id="buyerEmailInput"
            type="email"
            value={form.buyerEmail || ''}
            onChange={(e) => onChange('buyerEmail', e.target.value)}
            placeholder="Optional (e.g., buyer@example.com)"
            className="w-full px-3 py-2 rounded-lg text-xs bg-white border border-[#E6E4DD] text-[#18181B] focus:outline-none focus:ring-2 focus:ring-[#0F766E]/20 focus:border-[#0F766E]"
          />
        </div>
      </div>
    </section>
  );
}

