import test from 'node:test';
import assert from 'node:assert/strict';
import {
  validateEvidenceFile,
  detectChronologicalAnomalies,
  isLocalDemoIdentifier,
  MAX_EVIDENCE_BYTES,
} from '../src/utils/evidenceRules.js';

test('validateEvidenceFile accepts valid PDF/JPG/PNG under 10 MB', () => {
  assert.equal(validateEvidenceFile({ name: 'pod.pdf', type: 'application/pdf', size: 1024 }).valid, true);
  assert.equal(validateEvidenceFile({ name: 'scan.jpg', type: 'image/jpeg', size: 50000 }).valid, true);
  assert.equal(validateEvidenceFile({ name: 'receipt.PNG', type: 'image/png', size: 2048 }).valid, true);
});

test('validateEvidenceFile rejects unsupported extensions, empty files, and >10MB files', () => {
  const badExt = validateEvidenceFile({ name: 'payload.exe', type: 'application/x-msdownload', size: 500 });
  assert.equal(badExt.valid, false);
  assert.match(badExt.reason, /Unsupported file format/);

  const badMime = validateEvidenceFile({ name: 'fake.pdf', type: 'text/plain', size: 500 });
  assert.equal(badMime.valid, false);

  const empty = validateEvidenceFile({ name: 'empty.pdf', type: 'application/pdf', size: 0 });
  assert.equal(empty.valid, false);

  const huge = validateEvidenceFile({ name: 'huge.pdf', type: 'application/pdf', size: MAX_EVIDENCE_BYTES + 1 });
  assert.equal(huge.valid, false);
});

test('detectChronologicalAnomalies catches out-of-order dates accurately', () => {
  assert.deepEqual(
    detectChronologicalAnomalies({
      orderDate: '2026-10-10',
      shipmentDate: '2026-10-11',
      deliveryDate: '2026-10-14',
    }),
    []
  );

  const inv = detectChronologicalAnomalies({
    orderDate: '2026-10-15',
    shipmentDate: '2026-10-12',
    deliveryDate: '2026-10-10',
  });
  assert.equal(inv.length, 3);
});

test('isLocalDemoIdentifier strictly prevents local IDs from pretending to be live PayPal disputes', () => {
  assert.equal(isLocalDemoIdentifier('DSP-3EU95140-01'), true);
  assert.equal(isLocalDemoIdentifier('PP-D-EXAMPLE'), true);
  assert.equal(isLocalDemoIdentifier('PP-D-98123456'), false);
});

