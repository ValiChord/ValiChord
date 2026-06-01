# CORE-Bench demo — review-hardening design (3 findings)

**Date:** 2026-05-31
**Branch:** `core-bench-demo` (already merged to `main`)
**Status:** ✅ IMPLEMENTED 2026-06-01 — all 3 units built TDD via subagent-driven-development and merged to `main` (fast-forward). Tests green: Python 44 / JS 5 / Rust 27 (incl. cross-language agreement golden). See `docs/superpowers/plans/2026-05-31-core-bench-review-hardening.md`.

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

**Retained set:** files **not** removed by hard mode. The removal list
`inspect_evals.core_bench.dataset.CAPSULE_PATHS_TO_REMOVE["hard"]` holds path
**prefixes**, not bare names (`results`, `environment`, `REPRODUCING.md`,
`code/run`, `code/run.sh`) and is applied as `rm -rf <path>`. Classification must
therefore be **prefix-aware**: a file is *deleted* iff its capsule-relative path
equals a removal entry **or** starts with `entry + "/"` (so `results/output.json`
is correctly deleted). The dangerous direction is the false negative — treating a
deleted file as retained is harmless; failing to recognise a retained file means
never scanning it. A `is_retained(rel_path)` helper encodes exactly this rule
against the imported list.

Scanned extensions: `.md .txt .rst .py .json .ipynb .csv .yaml .yml`. **`.ipynb`
is scanned as raw text** — output cells are JSON strings, so a whole-file text
scan catches `"AUC: 0.9158"` in cell output without notebook parsing.

**Two non-fuzzy signals** (the fuzzy keyword-near-number heuristic is dropped):

1. **Rounded point forms** — for each committed metric `value`, generate
   `repr(value)` and rounds to 2/3/4 decimal places plus the `value*100`
   percentage form; flag if any appears as a token in retained text. **Applies to
   all scanned extensions** (specific enough not to false-positive on data/code).
2. **Interval membership** — extract numeric tokens and flag any inside
   `[lower - h, upper + h]` where `h = (upper - lower)/2` (within 2× the committed
   half-width of the centre). **Restricted to documentation-like files
   (`.md .txt .rst .ipynb`) only** — on raw `.csv/.json/.py` an in-band token
   (a data column, `lr=0.91`, a normalised feature) is noise that would cause a
   false abort and make the gate look broken. Documentation is where an
   *approximate stated result* actually lives, so that is where this signal earns
   its keep.

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
- `numericMatch(value, lower, upper) -> bool` — **a direct port of Python
  `match_value`** (`report_to_verdict.py:55-61`), because `produced_value` /
  `expected_value` are `String` on-chain (`shared_types:309-310`). Coerce
  `Number(String(v).replace('%','').trim())`; `NaN` → false; inclusive `<=` both
  sides. A naive `value <= upper` on the raw string renders **every** row
  `OUTSIDE` on the exact surface meant to be trustworthy. Unit-test against a
  `"%"`-suffixed and a whitespace-padded value, not just clean floats.
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

**Echo (runner) — gossip-free source.** A `_node_get(record_url)` after creation
would race governance gossip: the record is authored on validator-1's node and
must propagate to the researcher node before the GET sees it; under lag the GET
404s → the fallback fires → the display silently shows the **recomputed** value,
i.e. the exact unverified path #3 exists to retire, now invisible.

Instead, enrich `/create-harmony-record` (`validator-node.mjs`) to also return
`outcome` and `agreement_level`, read by the **authoring** node from the record it
just wrote (a local `get_harmony_record(request_ref)` on the author is
gossip-free). The runner displays those authoritative fields. It falls back to
Python `derive_*(outcomes)` **only** if the response omits them, and when it does
it **labels the display** ("recomputed — record fields unavailable") so the
output is never silently on the recompute path. The locally-built `numeric_panel`
is unchanged — it's the recomputable headline; Unit 2 is its on-chain counterpart.

**Shared golden fixture:** `valichord/shared_types/tests/agreement_golden.json`:
```json
[ { "outcomes": ["Reproduced","Reproduced","Reproduced"],
    "agreement_level": "ExactMatch", "majority_outcome": "Reproduced" }, ... ]
```
Uses **canonical** outcome strings only (no `NotReproduced`).

"Breaks both or neither" only holds for vectors that **exercise the thresholds**,
so the fixture must include the exact edges (migrated from the current
`test_agreement.py`), not just the easy `3×Reproduced` case:
- `full_rate == 0.90` → 9×Reproduced + 1×Failed → `ExactMatch`
- `full_rate == 0.70 < 0.90`, `any_rate == 0.70` → 7×Reproduced + 3×Failed → `WithinTolerance`
- `any_rate == 0.50` → 1×Reproduced + 1×Failed → `DirectionalMatch`
- `any_rate` just above 0 → 1×Reproduced + 2×Failed → `Divergent`
- `any_rate == 0` → 3×Failed → `UnableToAssess`
- all-partial → 3×PartiallyReproduced → `WithinTolerance` (full 0, any 1.0)

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
