// demo/test_record_helpers.mjs
import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  numericMatch, parseCommittedInterval, buildNumericConvergence, executionAgreementNote,
} from './node-lib.mjs';

test('numericMatch ports Python match_value: coercion + inclusive bounds', () => {
  assert.equal(numericMatch('0.9158', 0.9148, 0.9167), true);
  assert.equal(numericMatch('91.58%', 0.9148, 0.9167), false); // % strip => 91.58, out of band
  assert.equal(numericMatch('  0.9148  ', 0.9148, 0.9167), true); // whitespace + exactly on lower bound (inclusive)
  assert.equal(numericMatch('0.9167', 0.9148, 0.9167), true);     // exactly on upper bound (inclusive)
  assert.equal(numericMatch('not-a-number', 0, 1), false);
  assert.equal(numericMatch('', -0.01, 0.01), false); // empty string is not a match even when interval contains 0
  assert.equal(numericMatch('   ', -1, 1), false);     // whitespace-only too
});

test('parseCommittedInterval reads "[l, u] (basis)"; null on malformed', () => {
  assert.deepEqual(parseCommittedInterval('[0.9148, 0.9167] (explicit_tolerance)'), { lower: 0.9148, upper: 0.9167 });
  assert.equal(parseCommittedInterval('no brackets here'), null);
});

test('buildNumericConvergence pairs validator values to researcher interval', () => {
  const researcherMetrics = [{ metric_name: 'AUC', expected_value: '[0.9148, 0.9167] (x)', produced_value: '0.9158' }];
  const atts = [
    { outcome_summary: { key_metrics: [{ metric_name: 'AUC', produced_value: '0.9158' }] } },
    { outcome_summary: { key_metrics: [{ metric_name: 'AUC', produced_value: '0.5000' }] } },
  ];
  const rows = buildNumericConvergence(researcherMetrics, atts);
  assert.equal(rows.length, 2);
  assert.deepEqual(rows[0], { validator: 1, metric: 'AUC', value: '0.9158', lower: 0.9148, upper: 0.9167, match: true });
  assert.equal(rows[1].match, false);
});

test('buildNumericConvergence empty attestations => [] (pre-reveal)', () => {
  assert.deepEqual(buildNumericConvergence([{ metric_name: 'AUC', expected_value: '[0,1] (x)' }], []), []);
});

test('executionAgreementNote names the level and disclaims numeric agreement', () => {
  const note = executionAgreementNote('ExactMatch');
  assert.match(note, /ExactMatch/);
  assert.match(note, /NOT a claim that/i);
});

// The note used to end "see numeric_convergence" on every record, including the
// ones where that field is an empty array. It is empty on every path except
// CORE-Bench, and correctly so, which made a correct record look like a broken
// one. These four pin the note to what the field actually holds.
test('executionAgreementNote points at numeric_convergence only when it has rows', () => {
  const rows = [{ validator: 1, metric: 'AUC', value: '0.9158', lower: 0.9148, upper: 0.9167, match: true }];
  assert.match(executionAgreementNote('ExactMatch', rows), /see numeric_convergence/);
});

test('executionAgreementNote explains an empty numeric_convergence', () => {
  const note = executionAgreementNote('ExactMatch', []);
  assert.doesNotMatch(note, /see numeric_convergence/);
  assert.match(note, /empty by construction, not by failure/);
});

test('executionAgreementNote reports the pending sentinel as pending', () => {
  const note = executionAgreementNote('ExactMatch', 'pending');
  assert.match(note, /pending/);
  assert.doesNotMatch(note, /empty by construction/);
});

test('executionAgreementNote still disclaims numeric agreement in every case', () => {
  for (const c of [undefined, [], 'pending', [{ match: true }]]) {
    assert.match(executionAgreementNote('Divergent', c), /NOT a claim that their numbers/i);
    assert.match(executionAgreementNote('Divergent', c), /Divergent/);
  }
});
