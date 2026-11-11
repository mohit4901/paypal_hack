/**
 * Pure validation, provenance taxonomy, and delivery-timeline logic for ProofLedger.
 * Shared across React components and Node automated unit tests.
 */

export const ALLOWED_EVIDENCE_MIME_TYPES = [
  'application/pdf',
  'image/jpeg',
  'image/png',
];
export const ALLOWED_EVIDENCE_EXTENSIONS = ['.pdf', '.jpg', '.jpeg', '.png'];
export const MAX_EVIDENCE_BYTES = 10 * 1024 * 1024;

export function validateEvidenceFile(file) {
  if (!file) {
    return { valid: false, reason: 'No file selected.' };
  }
  const lowerName = (file.name || '').toLowerCase();
  const hasAllowedExt = ALLOWED_EVIDENCE_EXTENSIONS.some((ext) => lowerName.endsWith(ext));
  const hasAllowedMime = !file.type || ALLOWED_EVIDENCE_MIME_TYPES.includes(file.type.toLowerCase());
  if (!hasAllowedExt || !hasAllowedMime) {
    return {
      valid: false,
      reason: `Unsupported file format "${file.name}". Upload a PDF, JPG/JPEG, or PNG document.`,
    };
  }
  if (file.size === 0) {
    return { valid: false, reason: `"${file.name}" is empty (0 bytes).` };
  }
  if (file.size > MAX_EVIDENCE_BYTES) {
    return {
      valid: false,
      reason: `"${file.name}" exceeds the 10 MB upload limit.`,
    };
  }
  return { valid: true, reason: null };
}

export function detectChronologicalAnomalies({ orderDate, shipmentDate, deliveryDate }) {
  const issues = [];
  const orderTs = orderDate ? Date.parse(orderDate) : null;
  const shipTs = shipmentDate ? Date.parse(shipmentDate) : null;
  const delivTs = deliveryDate ? Date.parse(deliveryDate) : null;

  if (orderTs && shipTs && shipTs < orderTs) {
    issues.push(`Shipment date (${shipmentDate}) precedes order date (${orderDate}).`);
  }
  if (shipTs && delivTs && delivTs < shipTs) {
    issues.push(`Delivery date (${deliveryDate}) precedes shipment date (${shipmentDate}).`);
  }
  if (orderTs && delivTs && delivTs < orderTs) {
    issues.push(`Delivery date (${deliveryDate}) precedes order date (${orderDate}).`);
  }
  return issues;
}

export function isLocalDemoIdentifier(id = '') {
  return /^(DSP-|PP-D-EXAMPLE|LOCAL)/i.test(String(id).trim());
}

