# CORE-Bench Review-Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the three review-hardening units from the spec — a capsule blinding gate, an honest `/record` numeric panel, and cross-language agreement parity.

**Architecture:** Three independent units. Unit 1 is pure Python + a tarball loader, gated into the runner. Unit 2 adds pure JS helpers tested with `node --test`, consumed by the `/record` handler with explicit degradation. Unit 3 echoes the authoring node's record fields and locks Python↔Rust agreement logic to a shared JSON fixture. No integrity-zome or DNA-hash change.

**Tech Stack:** Python (pytest), Node ESM (`node:test`), Rust (`cargo test`, `serde_json` dev-dep), inspect_evals.

**Canonical conventions (from spec):**
- Interval match is **inclusive** `lower <= value <= upper`.
- On-chain outcome vocab: `Reproduced | PartiallyReproduced | FailedToReproduce | UnableToAssess`. Demo-only `NotReproduced` stays Python-side, not in the shared fixture.

**Run all demo Python tests with:** `cd /workspaces/ValiChord/demo && python3 -m pytest <file> -q`

---

## Unit 1 — Capsule blinding gate

### Task 1: `is_retained` — prefix-aware retained/deleted classification

**Files:**
- Create: `demo/capsule_blinding_gate.py`
- Test: `demo/test_capsule_blinding_gate.py`

- [ ] **Step 1: Write the failing test**

```python
# demo/test_capsule_blinding_gate.py
import pytest
pytest.importorskip("inspect_evals")
import capsule_blinding_gate as gate


def test_is_retained_prefix_aware():
    # Removed in hard mode: results, environment, REPRODUCING.md, code/run, code/run.sh
    assert gate.is_retained("code/README.md") is True
    assert gate.is_retained("data/final_model.pth") is True
    assert gate.is_retained("REPRODUCING.md") is False
    assert gate.is_retained("results") is False
    assert gate.is_retained("results/output") is False        # prefix, not bare name
    assert gate.is_retained("results/sub/output.json") is False
    assert gate.is_retained("code/run") is False
    assert gate.is_retained("code/run.sh") is False
    assert gate.is_retained("code/runner.py") is True         # not "code/run" nor under it
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest test_capsule_blinding_gate.py::test_is_retained_prefix_aware -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'capsule_blinding_gate'`

- [ ] **Step 3: Write minimal implementation**

```python
# demo/capsule_blinding_gate.py
"""Pre-round blinding gate: prove the target answer is not readable from any file
the agent retains in CORE-Bench hard mode, so 'independent execution' cannot
reduce to 'read the number'. Pure functions + a tarball loader; no protocol code."""
from typing import NamedTuple

from inspect_evals.core_bench.dataset import CAPSULE_PATHS_TO_REMOVE


def is_retained(rel_path: str, difficulty: str = "hard") -> bool:
    """A capsule-relative path is retained iff hard mode does not delete it.
    Removal entries are path prefixes applied as `rm -rf`, so a file is deleted
    when its path equals an entry or starts with `entry + '/'`. False negatives
    (treating a retained file as deleted) are the dangerous direction — they skip
    scanning — so the rule mirrors inspect's removal semantics exactly."""
    for entry in CAPSULE_PATHS_TO_REMOVE[difficulty]:
        if rel_path == entry or rel_path.startswith(entry + "/"):
            return False
    return True
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest test_capsule_blinding_gate.py::test_is_retained_prefix_aware -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add demo/capsule_blinding_gate.py demo/test_capsule_blinding_gate.py
git commit -m "feat(core-bench): blinding-gate retained/deleted classifier (prefix-aware)"
```

---

### Task 2: `find_answer_leaks` + `assert_capsule_blind` — the two signals

**Files:**
- Modify: `demo/capsule_blinding_gate.py`
- Test: `demo/test_capsule_blinding_gate.py`

- [ ] **Step 1: Write the failing tests**

```python
# append to demo/test_capsule_blinding_gate.py
_CLAIM = {"AUC": {"value": 0.9157952669235003, "lower": 0.9148, "upper": 0.9167, "basis": "explicit_tolerance"}}


def test_rounded_form_leak_any_extension():
    files = {"code/train.py": "# expected final auc 0.916 on the test split\n"}
    leaks = gate.find_answer_leaks(files, _CLAIM)
    assert any(lk.signal == "rounded_form" and lk.file == "code/train.py" for lk in leaks)


def test_notebook_output_cell_leak():
    nb = '{"cells":[{"outputs":[{"text":["AUC: 0.9158\\n"]}]}]}'
    leaks = gate.find_answer_leaks({"analysis.ipynb": nb}, _CLAIM)
    assert any(lk.signal == "rounded_form" for lk in leaks)


def test_interval_signal_only_doc_files():
    # 0.9155 is inside [lower-h, upper+h]; flagged in .md, ignored in .csv/.py
    assert gate.find_answer_leaks({"README.md": "approx 0.9155\n"}, _CLAIM)
    assert gate.find_answer_leaks({"data.csv": "x,0.9155,y\n"}, _CLAIM) == []
    assert gate.find_answer_leaks({"m.py": "lr = 0.9155\n"}, _CLAIM) == []


def test_clean_capsule_no_leak():
    files = {"code/README.md": "conda install pytorch; prepare covid/ then run.",
             "data.csv": "id,label\n1,0\n2,1\n"}
    assert gate.find_answer_leaks(files, _CLAIM) == []


def test_assert_raises_and_names_file():
    with pytest.raises(gate.CapsuleLeakError) as exc:
        gate.assert_capsule_blind({"REPORTME.md": "AUC = 0.9158"}, _CLAIM)
    assert "REPORTME.md" in str(exc.value)
```

- [ ] **Step 2: Run to verify they fail**

Run: `python3 -m pytest test_capsule_blinding_gate.py -q -k "leak or clean or assert"`
Expected: FAIL — `AttributeError: module 'capsule_blinding_gate' has no attribute 'find_answer_leaks'`

- [ ] **Step 3: Write the implementation**

```python
# add to demo/capsule_blinding_gate.py
import re

_DOC_EXTS = (".md", ".txt", ".rst", ".ipynb")  # interval signal only here
_NUM_TOKEN = re.compile(r"-?\d+\.\d+|-?\d+")


class Leak(NamedTuple):
    file: str
    token: str
    signal: str  # "rounded_form" | "interval"


class CapsuleLeakError(RuntimeError):
    pass


def _rounded_forms(value: float) -> set[str]:
    """Specific-enough textual forms of a point value: exact repr, 3/4 dp, and the
    percentage form to 1/2 dp. 2 dp is deliberately excluded — too coarse, it would
    false-positive on unrelated constants in code/data."""
    forms = {repr(value), str(value), f"{value:.3f}", f"{value:.4f}",
             f"{value * 100:.1f}", f"{value * 100:.2f}"}
    return {f for f in forms if f}


def find_answer_leaks(retained_files: dict, committed_claim: dict) -> list:
    """Scan retained file text for the committed answer. Signal 1 (rounded point
    forms) runs on all files; signal 2 (interval membership) only on doc-like
    files, where an approximate *stated* result lives — on raw data/code it is
    noise. Returns at most one leak per (file, metric, signal)."""
    leaks = []
    for spec in committed_claim.values():
        value, lower, upper = spec["value"], spec["lower"], spec["upper"]
        forms = _rounded_forms(value)
        half = (upper - lower) / 2 if upper > lower else 0.0
        lo, hi = lower - half, upper + half
        for fname, text in retained_files.items():
            if any(form in text for form in forms):
                hit = next(form for form in forms if form in text)
                leaks.append(Leak(fname, hit, "rounded_form"))
            if fname.lower().endswith(_DOC_EXTS):
                for m in _NUM_TOKEN.finditer(text):
                    try:
                        num = float(m.group())
                    except ValueError:
                        continue
                    if lo <= num <= hi:
                        leaks.append(Leak(fname, m.group(), "interval"))
                        break
    return leaks


def assert_capsule_blind(retained_files: dict, committed_claim: dict) -> None:
    leaks = find_answer_leaks(retained_files, committed_claim)
    if leaks:
        detail = "\n  - ".join(f"{lk.file}: '{lk.token}' ({lk.signal})" for lk in leaks)
        raise CapsuleLeakError(
            "Capsule answer leaks into retained agent inputs — blinding is broken:\n  - " + detail
        )
```

- [ ] **Step 4: Run to verify they pass**

Run: `python3 -m pytest test_capsule_blinding_gate.py -q`
Expected: PASS (all gate tests)

- [ ] **Step 5: Commit**

```bash
git add demo/capsule_blinding_gate.py demo/test_capsule_blinding_gate.py
git commit -m "feat(core-bench): blinding-gate leak detection (rounded-form + doc interval)"
```

---

### Task 3: `load_retained_capsule_text` — read retained text from the cached tarball

**Files:**
- Modify: `demo/capsule_blinding_gate.py`
- Test: `demo/test_capsule_blinding_gate.py`

- [ ] **Step 1: Write the failing test** (builds a tiny in-memory tarball, no network)

```python
# append to demo/test_capsule_blinding_gate.py
import io, tarfile


def _make_capsule_tar(path, members: dict):
    with tarfile.open(path, "w:gz") as tar:
        for name, data in members.items():
            b = data.encode()
            info = tarfile.TarInfo(name=name)
            info.size = len(b)
            tar.addfile(info, io.BytesIO(b))


def test_load_retained_capsule_text(tmp_path, monkeypatch):
    cap = "capsule-test123"
    tar_path = tmp_path / f"{cap}.tar.gz"
    _make_capsule_tar(tar_path, {
        f"{cap}/code/README.md": "hello",
        f"{cap}/REPRODUCING.md": "auc 0.9158",      # deleted in hard mode -> excluded
        f"{cap}/results/output": "auc 0.9158",      # deleted -> excluded
        f"{cap}/data/final_model.pth": "BINARY",    # non-text ext -> excluded
        f"{cap}/code/train.py": "print('hi')",
    })
    monkeypatch.setattr(gate, "CAPSULE_TAR_PATH", str(tmp_path / "{capsule_id}.tar.gz"))
    files = gate.load_retained_capsule_text(cap)
    assert set(files) == {"code/README.md", "code/train.py"}
    assert files["code/README.md"] == "hello"
```

- [ ] **Step 2: Run to verify it fails**

Run: `python3 -m pytest test_capsule_blinding_gate.py::test_load_retained_capsule_text -q`
Expected: FAIL — `AttributeError: ... has no attribute 'load_retained_capsule_text'` (and `CAPSULE_TAR_PATH` not yet imported)

- [ ] **Step 3: Write the implementation**

```python
# add near the imports of demo/capsule_blinding_gate.py
import tarfile as _tarfile
from inspect_evals.core_bench.dataset import CAPSULE_TAR_PATH

_TEXT_EXTS = (".md", ".txt", ".rst", ".py", ".json", ".ipynb", ".csv", ".yaml", ".yml")


def load_retained_capsule_text(capsule_id: str) -> dict:
    """Return {capsule_relative_path: text} for retained, text-extension files in
    the cached capsule tarball. utf-8 with errors='ignore' (so .ipynb output cells
    are scanned as raw JSON text)."""
    tar_path = CAPSULE_TAR_PATH.format(capsule_id=capsule_id)
    prefix = capsule_id + "/"
    out = {}
    with _tarfile.open(tar_path, "r:gz") as tar:
        for member in tar.getmembers():
            if not member.isfile():
                continue
            rel = member.name[len(prefix):] if member.name.startswith(prefix) else member.name
            if not rel or not is_retained(rel):
                continue
            if not rel.lower().endswith(_TEXT_EXTS):
                continue
            f = tar.extractfile(member)
            if f is None:
                continue
            out[rel] = f.read().decode("utf-8", errors="ignore")
    return out
```

- [ ] **Step 4: Run to verify it passes**

Run: `python3 -m pytest test_capsule_blinding_gate.py -q`
Expected: PASS (all gate tests)

- [ ] **Step 5: Commit**

```bash
git add demo/capsule_blinding_gate.py demo/test_capsule_blinding_gate.py
git commit -m "feat(core-bench): load retained capsule text from cached tarball"
```

---

### Task 4: Gate the runner + expose in the spike

**Files:**
- Modify: `demo/core_bench_runner.py` (after `run_researcher_claim`, before the validator loop)
- Modify: `demo/core_bench_spike.py` (print a leak report)
- Test: `demo/test_core_bench_runner.py`

- [ ] **Step 1: Write the failing test** — the runner aborts when the capsule leaks

```python
# append to demo/test_core_bench_runner.py
def test_run_protocol_aborts_on_capsule_leak(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "x")
    monkeypatch.setenv("OPENAI_API_KEY", "x")
    monkeypatch.setenv("GOOGLE_API_KEY", "x")
    monkeypatch.setattr(cbr, "_node_post", lambda url, payload, timeout=600: {"external_hash_b64": "uhC8kEXT"})
    monkeypatch.setattr(cbr, "_node_get", lambda url, timeout=30: {"phase": "RevealOpen"})
    monkeypatch.setattr(cbr, "run_researcher_claim",
                        lambda cid, model, n_runs, rel_tolerance:
                        {"AUC": {"value": 0.9157952669235003, "lower": 0.9148, "upper": 0.9167, "basis": "explicit_tolerance"}})
    monkeypatch.setattr(cbr, "_sleep", lambda s: None)
    # capsule text leaks the answer in a retained README
    monkeypatch.setattr(cbr, "load_retained_capsule_text", lambda cid: {"code/README.md": "final AUC 0.9158"})

    def fail_if_called(*a, **k):
        raise AssertionError("validators must not run when the capsule leaks")
    monkeypatch.setattr(cbr, "run_validator_eval", fail_if_called)

    with pytest.raises(cbr.CapsuleLeakError):
        cbr.run_core_bench_protocol(
            capsule_id="capsule-0851068",
            researcher_model="anthropic/claude-opus-4-8",
            validator_models=["anthropic/claude-opus-4-8", "openai/gpt-4o", "google/gemini-2.5-pro"],
        )
```

- [ ] **Step 2: Run to verify it fails**

Run: `python3 -m pytest test_core_bench_runner.py::test_run_protocol_aborts_on_capsule_leak -q`
Expected: FAIL — `AttributeError: module 'core_bench_runner' has no attribute 'load_retained_capsule_text'`

- [ ] **Step 3: Implement — wire the gate into the runner**

In `demo/core_bench_runner.py`, add to the imports near line 16:
```python
from capsule_blinding_gate import (
    assert_capsule_blind, load_retained_capsule_text, CapsuleLeakError,
)
```
Then in `run_core_bench_protocol`, immediately after the `claim = run_researcher_claim(...)` line and before `required_keys = ...`, insert:
```python
    # Blinding gate: the answer must not be readable from any retained agent
    # input, or "independent execution" reduces to "read the number". Runs after
    # the claim (we need the value+interval) and before any validator starts.
    assert_capsule_blind(load_retained_capsule_text(capsule_id), claim)
```

- [ ] **Step 4: Run to verify it passes (and the full suite stays green)**

Run: `python3 -m pytest test_core_bench_runner.py -q`
Expected: PASS — including the existing `test_run_protocol_drives_full_sequence` (its mocked `load_retained_capsule_text`? add a no-op). If `test_run_protocol_drives_full_sequence` now fails because it lacks the loader mock, add to that test:
```python
    monkeypatch.setattr(cbr, "load_retained_capsule_text", lambda cid: {})
```
(do the same in `test_run_protocol_aborts_when_a_validator_fails` and `test_validators_run_sequentially_not_concurrently`).

- [ ] **Step 5: Expose in the spike (manual capsule selection)**

In `demo/core_bench_spike.py`, after the value+timing print, add a non-fatal leak report. Find where the spike prints the reproduced value and append:
```python
    from capsule_blinding_gate import load_retained_capsule_text, find_answer_leaks
    # spike claim is a single deterministic value with a zero-width band; widen for the report
    claim = {"value": {"value": value, "lower": value, "upper": value, "basis": "spike"}}
    leaks = find_answer_leaks(load_retained_capsule_text(args.capsule), claim)
    if leaks:
        print("  ⚠ BLINDING LEAK — answer readable from retained inputs:")
        for lk in leaks:
            print(f"      {lk.file}: '{lk.token}' ({lk.signal})")
    else:
        print("  ✓ blinding: target not found in retained inputs")
```

- [ ] **Step 6: Run the full demo Python suite**

Run: `python3 -m pytest test_capsule_blinding_gate.py test_core_bench_runner.py test_core_bench_validator.py test_report_to_verdict.py -q`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add demo/core_bench_runner.py demo/core_bench_spike.py demo/test_core_bench_runner.py
git commit -m "feat(core-bench): gate the round on capsule blinding; leak report in spike"
```

---

## Unit 2 — `/record` numeric panel

### Task 5: Pure JS helpers in `node-lib.mjs`

**Files:**
- Modify: `demo/node-lib.mjs` (append exports)
- Test: `demo/test_record_helpers.mjs` (new, `node --test`)

- [ ] **Step 1: Write the failing test**

```js
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
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd /workspaces/ValiChord/demo && node --test test_record_helpers.mjs`
Expected: FAIL — `SyntaxError: The requested module './node-lib.mjs' does not provide an export named 'numericMatch'`

- [ ] **Step 3: Implement — append to `demo/node-lib.mjs`**

```js
// ── /record numeric-convergence helpers (Unit 2) ────────────────────────────
// numericMatch is a direct port of Python report_to_verdict.match_value:
// produced_value/expected_value are String on-chain, so coerce before comparing.
// Inclusive bounds, NaN => false. A raw-string compare would render every row
// OUTSIDE on the trustworthy surface.
export function numericMatch(value, lower, upper) {
  const v = Number(String(value).replace('%', '').trim());
  if (Number.isNaN(v)) return false;
  return lower <= v && v <= upper;
}

export function parseCommittedInterval(expectedValueStr) {
  const m = String(expectedValueStr).match(/\[\s*([-\d.eE+]+)\s*,\s*([-\d.eE+]+)\s*\]/);
  if (!m) return null;
  const lower = Number(m[1]);
  const upper = Number(m[2]);
  if (Number.isNaN(lower) || Number.isNaN(upper)) return null;
  return { lower, upper };
}

export function executionAgreementNote(level) {
  return `agreement_level='${level}' is independent EXECUTION agreement: all participating `
       + `validators independently produced a result. It is NOT a claim that their numbers `
       + `agree — see numeric_convergence.`;
}

export function buildNumericConvergence(researcherMetrics, attestationEntries) {
  const intervals = new Map();
  for (const rm of researcherMetrics || []) {
    const iv = parseCommittedInterval(rm.expected_value);
    if (iv) intervals.set(rm.metric_name, iv);
  }
  const rows = [];
  (attestationEntries || []).forEach((att, i) => {
    const km = att?.outcome_summary?.key_metrics ?? [];
    for (const m of km) {
      const iv = intervals.get(m.metric_name);
      if (!iv) continue;
      rows.push({
        validator: i + 1,
        metric: m.metric_name,
        value: m.produced_value,
        lower: iv.lower,
        upper: iv.upper,
        match: numericMatch(m.produced_value, iv.lower, iv.upper),
      });
    }
  });
  return rows;
}
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd /workspaces/ValiChord/demo && node --test test_record_helpers.mjs`
Expected: PASS — `# pass 5`

- [ ] **Step 5: Commit**

```bash
git add demo/node-lib.mjs demo/test_record_helpers.mjs
git commit -m "feat(core-bench): /record numeric-convergence pure helpers (node-lib)"
```

---

### Task 6: Enrich the `/record` handler with degradation states

**Files:**
- Modify: `demo/researcher-node.mjs` (the `GET /record` block, ~lines 245-291)

This handler needs a live conductor, so it is verified manually (no unit test); the logic lives in the Task-5 helpers. Keep base fields for back-compat with `ai_validator.py`.

- [ ] **Step 1: Add the imports** — extend the `node-lib.mjs` import in `researcher-node.mjs` to include the new helpers:

```js
import {
  withSession, readBody, loadHcClient, externalHashFromB64,
  buildNumericConvergence, executionAgreementNote,
} from './node-lib.mjs';
```
(Add the two names to the existing import list; keep whatever is already imported.)

- [ ] **Step 2: Replace the response-building section** of the `GET /record` block. After `const hr = ...` is decoded, replace the single `res.end(JSON.stringify({ ... }))` with:

```js
      const base = {
        harmony_record_hash: hashB64,
        outcome:         hr.outcome         ?? null,
        agreement_level: hr.agreement_level ?? null,
        discipline:      hr.discipline      ?? null,
        validator_count: Array.isArray(hr.participating_validators)
                           ? hr.participating_validators.length : 0,
      };

      // Enrich with the numeric-convergence headline. Degrade, never 500:
      //  - revealed (reveal + attestations present) -> full panel
      //  - pre-reveal (no reveal / no attestations)  -> numeric_convergence: "pending"
      //  - any error on the extra calls              -> base fields only
      let enrichment = {};
      try {
        const [reveal, attRecords] = await withSession(async ({ call }) => {
          const rv = await call('attestation', 'attestation_coordinator', 'get_researcher_reveal', hashBytes);
          const at = await call('attestation', 'attestation_coordinator', 'get_attestations_for_request', hashBytes);
          return [rv, at];
        });

        const decodeEntry = (rec) => {
          const b64 = rec?.entry?.Present?.entry?.__bytes ?? null;
          return b64 ? (msgpackDecode(Buffer.from(b64, 'base64')) ?? {}) : null;
        };

        const revealEntry = reveal ? decodeEntry(reveal) : null;
        const attEntries  = Array.isArray(attRecords) ? attRecords.map(decodeEntry).filter(Boolean) : [];

        enrichment.execution_agreement = {
          level: hr.agreement_level ?? null,
          means: executionAgreementNote(hr.agreement_level ?? 'unknown'),
        };
        if (revealEntry && attEntries.length > 0) {
          const researcherMetrics = revealEntry.metrics ?? [];
          enrichment.numeric_convergence = buildNumericConvergence(researcherMetrics, attEntries);
          enrichment.committed_claim = researcherMetrics.map(m => ({
            metric: m.metric_name, value: m.produced_value, interval: m.expected_value,
          }));
        } else {
          enrichment.numeric_convergence = 'pending';
        }
      } catch (e) {
        console.error('[/record] enrichment skipped:', e.message);
        // base fields only
      }

      res.writeHead(200, { 'Cache-Control': 'public, max-age=3600' });
      res.end(JSON.stringify({ ...base, ...enrichment }, null, 2));
```
Note: `msgpackDecode` is already imported in this block (`const { decode: msgpackDecode } = await import('@msgpack/msgpack');`) and `hashBytes` is already in scope. Keep them.

- [ ] **Step 3: Syntax-check (no conductor needed)**

Run: `cd /workspaces/ValiChord/demo && node --check researcher-node.mjs`
Expected: no output (exit 0)

- [ ] **Step 4: Manual verification note (record in plan; run when a stack is up)**

With a stack up and a completed round, `curl ".../record?hash=<ext>"` should show `execution_agreement.means`, a `numeric_convergence` array (or `"pending"` pre-reveal), and still the base `outcome`/`agreement_level`/`validator_count`. Killing the attestation calls (e.g. wrong ext) must still return the base object, not a 502.

- [ ] **Step 5: Commit**

```bash
git add demo/researcher-node.mjs
git commit -m "feat(core-bench): /record numeric-convergence headline with degradation states"
```

---

## Unit 3 — Agreement parity

### Task 7: Shared golden fixture + Python golden test (`repo_root`)

**Files:**
- Create: `valichord/shared_types/tests/agreement_golden.json`
- Modify: `demo/test_agreement.py` (add `repo_root` + golden test)

- [ ] **Step 1: Create the fixture with the boundary vectors**

```json
[
  {"outcomes": ["Reproduced", "Reproduced", "Reproduced"], "agreement_level": "ExactMatch", "majority_outcome": "Reproduced"},
  {"outcomes": ["Reproduced", "Reproduced", "Reproduced", "Reproduced", "Reproduced", "Reproduced", "Reproduced", "Reproduced", "Reproduced", "FailedToReproduce"], "agreement_level": "ExactMatch", "majority_outcome": "Reproduced"},
  {"outcomes": ["Reproduced", "Reproduced", "Reproduced", "Reproduced", "Reproduced", "Reproduced", "Reproduced", "FailedToReproduce", "FailedToReproduce", "FailedToReproduce"], "agreement_level": "WithinTolerance", "majority_outcome": "Reproduced"},
  {"outcomes": ["Reproduced", "FailedToReproduce"], "agreement_level": "DirectionalMatch", "majority_outcome": "Reproduced"},
  {"outcomes": ["Reproduced", "FailedToReproduce", "FailedToReproduce"], "agreement_level": "Divergent", "majority_outcome": "FailedToReproduce"},
  {"outcomes": ["FailedToReproduce", "FailedToReproduce", "FailedToReproduce"], "agreement_level": "UnableToAssess", "majority_outcome": "FailedToReproduce"},
  {"outcomes": ["PartiallyReproduced", "PartiallyReproduced", "PartiallyReproduced"], "agreement_level": "WithinTolerance", "majority_outcome": "PartiallyReproduced"}
]
```

- [ ] **Step 2: Write the failing Python golden test**

```python
# append to demo/test_agreement.py
import json
import os
from pathlib import Path


def repo_root() -> Path:
    """Locate the repo root (the dir containing valichord/shared_types) so the
    shared golden fixture resolves from any layout. Fails loudly — never a silent
    skip. Override with VALICHORD_REPO_ROOT."""
    env = os.environ.get("VALICHORD_REPO_ROOT")
    if env:
        return Path(env)
    here = Path(__file__).resolve()
    for parent in [here, *here.parents]:
        if (parent / "valichord" / "shared_types").is_dir():
            return parent
    raise RuntimeError(
        "repo root not found above test_agreement.py (no valichord/shared_types); "
        "set VALICHORD_REPO_ROOT"
    )


def test_golden_vectors_match_python_derivation():
    fixture = repo_root() / "valichord" / "shared_types" / "tests" / "agreement_golden.json"
    vectors = json.loads(fixture.read_text())
    assert len(vectors) >= 7
    for v in vectors:
        assert derive_agreement_level(v["outcomes"]) == v["agreement_level"], v
        assert derive_majority_outcome(v["outcomes"]) == v["majority_outcome"], v
```

- [ ] **Step 3: Run to verify it passes immediately** (Python logic already matches; this just binds it to the fixture)

Run: `cd /workspaces/ValiChord/demo && python3 -m pytest test_agreement.py -q`
Expected: PASS. If `test_golden_vectors_match_python_derivation` FAILS, the fixture has a wrong expected value — fix the JSON to match `agreement.py` (the Rust test in Task 8 is the cross-check, not this).

- [ ] **Step 4: Commit**

```bash
git add valichord/shared_types/tests/agreement_golden.json demo/test_agreement.py
git commit -m "feat(core-bench): shared agreement golden fixture + Python parity test"
```

---

### Task 8: Rust golden test consuming the same fixture

**Files:**
- Modify: `valichord/shared_types/Cargo.toml` (add `[dev-dependencies]` `serde_json`)
- Modify: `valichord/shared_types/src/lib.rs` (new `#[test]` inside the existing `mod tests`)

- [ ] **Step 1: Add the dev-dependency** — append to `valichord/shared_types/Cargo.toml`:

```toml
[dev-dependencies]
serde_json = "1"
```
(Dev-only: not inherited by zomes depending on `shared_types`, no DNA-hash impact.)

- [ ] **Step 2: Write the failing Rust test** — add inside the `#[cfg(test)] mod tests { ... }` block in `src/lib.rs`, reusing the existing `att()` helper:

```rust
    fn outcome_from_str(s: &str) -> AttestationOutcome {
        match s {
            "Reproduced" => AttestationOutcome::Reproduced,
            "PartiallyReproduced" => AttestationOutcome::PartiallyReproduced { details: String::new() },
            "FailedToReproduce" => AttestationOutcome::FailedToReproduce { details: String::new() },
            "UnableToAssess" => AttestationOutcome::UnableToAssess { reason: String::new() },
            other => panic!("unknown outcome in golden fixture: {other}"),
        }
    }

    fn outcome_to_str(o: &AttestationOutcome) -> &'static str {
        match o {
            AttestationOutcome::Reproduced => "Reproduced",
            AttestationOutcome::PartiallyReproduced { .. } => "PartiallyReproduced",
            AttestationOutcome::FailedToReproduce { .. } => "FailedToReproduce",
            AttestationOutcome::UnableToAssess { .. } => "UnableToAssess",
        }
    }

    #[test]
    fn golden_vectors_match_rust_derivation() {
        let raw = include_str!(concat!(env!("CARGO_MANIFEST_DIR"), "/tests/agreement_golden.json"));
        let vectors: Vec<serde_json::Value> = serde_json::from_str(raw).unwrap();
        assert!(vectors.len() >= 7);
        for v in &vectors {
            let atts: Vec<ValidationAttestation> = v["outcomes"].as_array().unwrap()
                .iter()
                .map(|o| att(outcome_from_str(o.as_str().unwrap())))
                .collect();
            let level = format!("{:?}", derive_agreement_level(&atts));
            assert_eq!(level, v["agreement_level"].as_str().unwrap(), "agreement_level for {:?}", v["outcomes"]);
            let major = outcome_to_str(&derive_majority_outcome(&atts));
            assert_eq!(major, v["majority_outcome"].as_str().unwrap(), "majority for {:?}", v["outcomes"]);
        }
    }
```
Note: `AgreementLevel` derives `Debug` with unit-variant names, so `format!("{:?}", ...)` yields `"ExactMatch"` etc., matching the fixture.

- [ ] **Step 3: Run to verify it passes**

Run: `export PATH="/home/codespace/.cargo/bin:$PATH" && cd /workspaces/ValiChord/valichord && cargo test -p shared_types golden_vectors_match_rust_derivation -- --nocapture`
Expected: PASS. If it FAILS, Python and Rust genuinely disagree on a threshold — that is the bug this test exists to catch; reconcile the logic, do not edit the fixture to paper over it.

- [ ] **Step 4: Run the whole shared_types suite (no regressions)**

Run: `export PATH="/home/codespace/.cargo/bin:$PATH" && cd /workspaces/ValiChord/valichord && cargo test -p shared_types`
Expected: PASS (all existing agreement tests + the new golden test)

- [ ] **Step 5: Commit**

```bash
git add valichord/shared_types/Cargo.toml valichord/shared_types/src/lib.rs
git commit -m "test(shared_types): Rust agreement parity against shared golden fixture"
```

---

### Task 9: Gossip-free echo + boundary-convention prose fix

**Files:**
- Modify: `demo/validator-node.mjs` (`/create-harmony-record` returns `outcome`/`agreement_level`)
- Modify: `demo/core_bench_runner.py` (echo record fields; label recompute fallback)
- Modify: `demo/CORE_BENCH_DEMO.md:181` (boundary contradiction)
- Test: `demo/test_core_bench_runner.py`

- [ ] **Step 1: Enrich `/create-harmony-record`** in `demo/validator-node.mjs`. After `harmonyRecordHash` is resolved (the authoring node has the record locally — gossip-free), and before the `res.end`, replace the success response:

```js
      // Read the just-authored record locally (gossip-free on the authoring node)
      // so the runner can display the AUTHORITATIVE outcome/agreement_level
      // instead of recomputing them.
      let recOutcome = null, recAgreement = null;
      if (harmonyRecordHash) {
        try {
          const rec = await withSession(async ({ call }) =>
            call('governance', 'governance_coordinator', 'get_harmony_record', hashBytes));
          const { decode: msgpackDecode } = await import('@msgpack/msgpack');
          const b64 = rec?.entry?.Present?.entry?.__bytes ?? null;
          const hr = b64 ? (msgpackDecode(Buffer.from(b64, 'base64')) ?? {}) : {};
          recOutcome = hr.outcome ?? null;
          recAgreement = hr.agreement_level ?? null;
        } catch (e) {
          console.error('[/create-harmony-record] local record read failed:', e.message);
        }
      }
      res.writeHead(200);
      res.end(JSON.stringify({
        harmony_record_hash: harmonyRecordHash,
        outcome: recOutcome,
        agreement_level: recAgreement,
      }));
```
(Replace the existing `res.writeHead(200); res.end(JSON.stringify({ harmony_record_hash: harmonyRecordHash }));`.)

- [ ] **Step 2: Write the failing runner test** — echo the record fields; label the recompute fallback

```python
# append to demo/test_core_bench_runner.py
def _full_run(monkeypatch, harmony_response):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "x")
    monkeypatch.setenv("OPENAI_API_KEY", "x")
    monkeypatch.setenv("GOOGLE_API_KEY", "x")
    monkeypatch.setattr(cbr, "load_retained_capsule_text", lambda cid: {})
    monkeypatch.setattr(cbr, "run_researcher_claim",
                        lambda cid, model, n_runs, rel_tolerance:
                        {"AUC": {"value": 96.0, "lower": 95.9, "upper": 96.1, "basis": "x"}})
    monkeypatch.setattr(cbr, "run_validator_eval", lambda cid, model: {"AUC": 96.0})
    monkeypatch.setattr(cbr, "_node_get", lambda url, timeout=30: {"phase": "RevealOpen"})
    monkeypatch.setattr(cbr, "_sleep", lambda s: None)

    def fake_post(url, payload, timeout=600):
        if url.endswith("/lock-result"): return {"external_hash_b64": "uhC8kEXT"}
        if url.endswith("/reveal"): return {"researcher_reveal_hash": "uhCkkREV"}
        if url.endswith("/create-harmony-record"): return harmony_response
        return {}
    monkeypatch.setattr(cbr, "_node_post", fake_post)
    return cbr.run_core_bench_protocol(
        capsule_id="capsule-0851068",
        researcher_model="anthropic/claude-opus-4-8",
        validator_models=["anthropic/claude-opus-4-8", "openai/gpt-4o", "google/gemini-2.5-pro"],
    )


def test_echoes_record_fields_when_present(monkeypatch):
    res = _full_run(monkeypatch, {"harmony_record_hash": "uhC8kHARM",
                                  "outcome": "Reproduced", "agreement_level": "ExactMatch"})
    assert res["outcome"] == "Reproduced"
    assert res["agreement_level"] == "ExactMatch"
    assert res["agreement_recomputed"] is False


def test_labels_recompute_when_record_fields_absent(monkeypatch):
    res = _full_run(monkeypatch, {"harmony_record_hash": "uhC8kHARM"})  # no outcome/agreement
    assert res["agreement_level"] == "ExactMatch"     # recomputed from 3x Reproduced
    assert res["agreement_recomputed"] is True
```

- [ ] **Step 3: Run to verify they fail**

Run: `python3 -m pytest test_core_bench_runner.py -q -k "echoes or labels"`
Expected: FAIL — `KeyError: 'agreement_recomputed'`

- [ ] **Step 4: Implement the echo in `demo/core_bench_runner.py`** — replace the block around `harmony = _node_post(... "/create-harmony-record" ...)` (currently lines ~152-164) with:

```python
    harmony = _node_post(f"{VALIDATOR_URLS[0]}/create-harmony-record", {"external_hash_b64": ext})
    harmony_hash = harmony.get("harmony_record_hash")
    if not harmony_hash:
        raise RuntimeError(f"HarmonyRecord not written after gossip retries (ext={ext[:20]}...)")

    # Echo the AUTHORITATIVE record fields (read gossip-free on the authoring node).
    # Fall back to local recompute only if absent, and flag it so the display is
    # never silently on the recomputed path.
    outcomes = [v["outcome"] for v in verdicts]
    rec_outcome = harmony.get("outcome")
    rec_agreement = harmony.get("agreement_level")
    if rec_outcome and rec_agreement:
        display_outcome, display_agreement, recomputed = rec_outcome, rec_agreement, False
    else:
        display_outcome = derive_majority_outcome(outcomes)
        display_agreement = derive_agreement_level(outcomes)
        recomputed = True
```
Then update the return dict (replace the `"outcome"`/`"agreement_level"` lines and add the flag):
```python
        "outcome": display_outcome,
        "agreement_level": display_agreement,
        "agreement_recomputed": recomputed,
```
(Remove the now-duplicated `outcomes = [...]` line that previously sat just before the return.)

- [ ] **Step 5: Label the fallback in `format_result`** — change the agreement line (~line 187) to:

```python
    suffix = " — RECOMPUTED, record fields unavailable" if result.get("agreement_recomputed") else ""
    a(f"  Agreement level:  {result['agreement_level']}  (independent execution agreement){suffix}")
```

- [ ] **Step 6: Fix the README boundary contradiction** — in `demo/CORE_BENCH_DEMO.md` change the line that reads ``Redo `lower ≤ value ≤ upper` by hand — it's `<` and `>`, not a model call.`` to:

```markdown
Redo `lower ≤ value ≤ upper` by hand (inclusive bounds) — it's `≤` comparisons, not a model call.
```

- [ ] **Step 7: Run to verify pass + full suite + node syntax**

Run: `python3 -m pytest test_core_bench_runner.py -q && node --check validator-node.mjs`
Expected: PASS, node exit 0

- [ ] **Step 8: Commit**

```bash
git add demo/validator-node.mjs demo/core_bench_runner.py demo/CORE_BENCH_DEMO.md demo/test_core_bench_runner.py
git commit -m "feat(core-bench): echo authoritative record fields gossip-free; pin inclusive boundary"
```

---

## Final verification (run after all tasks)

- [ ] **Python:** `cd /workspaces/ValiChord/demo && python3 -m pytest test_capsule_blinding_gate.py test_agreement.py test_core_bench_runner.py test_core_bench_validator.py test_report_to_verdict.py test_core_bench_capture_scorer.py test_core_bench_imports.py -q` → all pass
- [ ] **JS:** `cd /workspaces/ValiChord/demo && node --test test_record_helpers.mjs` → pass; `node --check researcher-node.mjs validator-node.mjs` → exit 0
- [ ] **Rust:** `export PATH="/home/codespace/.cargo/bin:$PATH" && cd /workspaces/ValiChord/valichord && cargo test -p shared_types` → pass
- [ ] **Docs:** spec findings all have a task; `CORE_BENCH_DEMO.md` boundary prose now consistent (`≤` everywhere)
```
