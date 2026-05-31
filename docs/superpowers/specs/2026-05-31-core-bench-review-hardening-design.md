# CORE-Bench demo — review-hardening design (3 findings)

**Date:** 2026-05-31
**Branch:** `core-bench-demo` (already merged to `main`)
**Status:** design approved (pending written-spec review)

Addresses three findings from an external review of the CORE-Bench × ValiChord
demo. Three independent units; **none touch an integrity zome or change a DNA
hash.** The only main-crate change is a dev-dependency + test in `shared_types`.

Canonical conventions pinned once here, used everywhere:

- **Interval match is inclusive: `lower <= value <= upper`.** Matches the existing
  `report_to_verdict.match_value` (`demo/report_to_verdict.py:61`). The JS helper
  and all prose use the same boundary. (Fixes the README contradiction at
  `demo/CORE_BENCH_DEMO.md:181`, which currently says "`<` and `>`".)
- **On-chain outcome vocabulary** (`AttestationOutcome`): `Reproduced`,
  `PartiallyReproduced`, `FailedToReproduce`, `UnableToAssess`. The demo-only
  claim-path synonym `NotReproduced` is normalised in Python only and is **not**
  part of the cross-language golden fixture.

---

## Unit 1 — Capsule blinding gate (`demo/capsule_blinding_gate.py`)

**Purpose:** before a round, prove the target answer is not readable from any file
the agent retains in hard mode — so "independent execution" can't be reduced to
"read the number." (Empirically `capsule-0851068` is clean today; this makes it a
gate, not an assumption, and covers future/stochastic capsules.)

**Retained set:** files **not** under
`inspect_evals.core_bench.dataset.CAPSULE_PATHS_TO_REMOVE["hard"]` (imported, so it
tracks what hard mode actually deletes). Scanned extensions:
`.md .txt .rst .py .json .ipynb .csv .yaml .yml`. **`.ipynb` is scanned as raw
text** — output cells are JSON strings, so a whole-file text scan catches
`"AUC: 0.9158"` in cell output without notebook parsing.

**Two non-fuzzy signals** (the fuzzy keyword-near-number heuristic is dropped):

1. **Rounded point forms** — for each committed metric `value`, generate
   `repr(value)` and rounds to 2/3/4 sig-decimals plus the `value*100`
   percentage form; flag if any appears as a token in retained text.
2. **Interval membership** — extract numeric tokens from retained text; flag any
   token inside `[lower - h, upper + h]` where `h = (upper - lower)/2` (i.e.
   within 2× the committed half-width of the centre). Pure numeric comparison —
   the exact case the gate guards for a *stochastic* capsule whose README states
   an approximate result.

**API (pure):**
```python
def find_answer_leaks(retained_files: dict[str, str], committed_claim: dict) -> list[Leak]
class Leak(NamedTuple): file: str; token: str; signal: str  # "rounded_form" | "interval"
class CapsuleLeakError(RuntimeError): ...
def assert_capsule_blind(retained_files, committed_claim) -> None  # raises CapsuleLeakError on any leak
```
**Capsule loader (impure, separate):**
`load_retained_capsule_text(capsule_id) -> dict[str, str]` — reads the cached
tarball, returns `{path: text}` for retained text-extension files (utf-8,
`errors="ignore"`).

**Integration:** in `core_bench_runner.run_core_bench_protocol`, after
`run_researcher_claim` (which yields the committed claim with value+interval) and
**before** the validator loop: `assert_capsule_blind(load_retained_capsule_text(capsule_id), claim)`.
A leak hard-aborts the round with the offending files. Also surfaced by
`core_bench_spike.py` (print a leak report for a candidate capsule, non-fatal).

**Tests** (`demo/test_capsule_blinding_gate.py`, pure, no network): point-form
leak in `.md`; output-cell leak in `.ipynb`; interval-membership leak; clean
capsule → no leak; rounded-form (`0.916` for `0.9157…`) leak; `assert_*` raises
and names files.

---

## Unit 2 — `/record` numeric panel (`demo/researcher-node.mjs` + `demo/node-lib.mjs`)

**Purpose:** carry the CLI's execution-vs-numeric distinction onto the
screenshotted record surface, so `agreement_level` can't be misread as "the
numbers matched."

**Pure helpers in `node-lib.mjs`** (unit-tested):
- `parseCommittedInterval(expectedValueStr) -> {lower, upper} | null` — parses the
  researcher's `"[l, u] (basis)"` encoding (from `claim_to_metrics`).
- `numericMatch(value, lower, upper) -> bool` — inclusive `<=` both sides; non-numeric → false.
- `buildNumericConvergence(researcherMetrics, attestationEntries) -> [{validator, metric, value, lower, upper, match}]`
  — per validator × metric: `value` = that validator's
  `outcome_summary.key_metrics[metric].produced_value`; interval parsed from the
  researcher metric's `expected_value`; `match` via `numericMatch`.
- `executionAgreementNote(level) -> string` — e.g. "all N validators independently
  produced a result; this is NOT a claim that the numbers agree — see numeric_convergence".

**`/record` handler — enrich, with explicit degradation (never 500):**
- Base (unchanged): fetch `HarmonyRecord`; 404 if absent. Always return
  `harmony_record_hash, outcome, agreement_level, discipline, validator_count`
  (back-compat for `ai_validator.py`).
- Then, in a **guarded** block calling `get_researcher_reveal` +
  `get_attestations_for_request`:
  - **revealed** (reveal present AND attestations non-empty) → add
    `execution_agreement: {level, means}`, `numeric_convergence: [...]` (headline),
    `committed_claim: [{metric, value, lower, upper}]`.
  - **pre-reveal** (reveal `None` or no attestations) → `numeric_convergence: "pending"`,
    still include `execution_agreement`.
  - **error on the extra calls** → log, return base fields only. A failed
    `get_attestations_for_request` must never take down the record view.

**Tests** (`demo/test_record_helpers.mjs`, `node --test`): interval parse incl.
malformed → null; `numericMatch` incl. value exactly on each bound (true);
`buildNumericConvergence` match + outside + empty (pre-reveal) cases. The handler
stays thin over these tested helpers (full handler needs a conductor).

**Caveat:** the public `record_url` points at the Oracle; this only changes the
shareable URL after the Oracle node is redeployed (user's server access).

---

## Unit 3 — Agreement parity (Python runner + shared Rust/Python golden fixture)

**Purpose:** make the doc's "display can never diverge from the HarmonyRecord"
literally true.

**Echo (runner):** after `create-harmony-record`, `_node_get(record_url)` and use
the record's own `outcome` / `agreement_level` for the authoritative display.
Fall back to Python `derive_majority_outcome` / `derive_agreement_level(outcomes)`
only if the fetch fails or the fields are missing. (The locally-built
`numeric_panel` is unchanged — it's the recomputable headline; Unit 2 is its
on-chain counterpart.)

**Shared golden fixture:** `valichord/shared_types/tests/agreement_golden.json`:
```json
[ { "outcomes": ["Reproduced","Reproduced","Reproduced"],
    "agreement_level": "ExactMatch", "majority_outcome": "Reproduced" }, ... ]
```
Uses **canonical** outcome strings only (no `NotReproduced`).

- **Python** (`test_agreement.py`): resolve the path via a `repo_root()` walk-up
  helper (find the dir containing `valichord/`, override with
  `VALICHORD_REPO_ROOT`), **raising loudly if not found** — never a bare relative
  literal, never a silent skip. Assert `derive_agreement_level` /
  `derive_majority_outcome` match each vector. A separate Python-only test keeps
  the `NotReproduced` normalisation case.
- **Rust** (new `#[test]` **inside the existing `#[cfg(test)] mod tests`** in
  `shared_types/src/lib.rs`, so it can reuse the private `att()` helper at
  `:559`): `include_str!(concat!(env!("CARGO_MANIFEST_DIR"), "/tests/agreement_golden.json"))`,
  parse with `serde_json`, map each outcome string → `AttestationOutcome` (struct
  variants get empty `details`/`reason`) → `att()` → `derive_*`, assert.
- `serde_json` added to `[dev-dependencies]` of `shared_types/Cargo.toml` —
  **dev-only, not inherited by dependent zomes, zero DNA-hash impact.**

A threshold change in either language now breaks both tests or neither.

---

## Out of scope
- Oracle redeployment (Unit 2 only affects the public URL after the user deploys).
- The stochastic follow-up capsule itself (Unit 1's interval signal is built now so
  it's ready; selecting/adding the capsule is separate work).
- Any integrity-zome / DNA / production change.

## Test summary
- Python: `test_capsule_blinding_gate.py` (new) + `test_agreement.py` (golden) +
  existing 31 core_bench tests stay green.
- JS: `test_record_helpers.mjs` (new, `node --test`).
- Rust: one new `#[test]` in `shared_types` consuming the shared fixture.
