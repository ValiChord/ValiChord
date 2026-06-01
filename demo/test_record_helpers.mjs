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
