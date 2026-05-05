# Codespaces Brief — Canonical Attestation Format for Valichord

**Trigger:** Architectural feedback from Scott Simmons on inspect_evals PR (UKGovernmentBEIS/inspect_evals#1610).
**Status:** PR being closed; this brief is the follow-up work.
**Target completion:** First-pass spec + reference impl + tests in a single sustained Codespaces session.

---

## Context — what changed

The inspect_evals PR proposed an attestation exporter inside the harness repo. A collaborator (Scott Simmons) responded with substantive architectural feedback:

1. **The canonical format belongs in Valichord, not in each harness.** Adapters per harness come later.
2. **The current `eval_file_sha256` is weak attestation.** Hashing the log proves you have a file, not that the *report* is faithful to the *run*. The format must let a verifier confirm faithfulness without access to the full log.
3. **Hardcoded `accuracy` / `stderr` won't generalise.** Different evals have different metric shapes (agentdojo multi-dim, SWE-bench pass@k, etc.). The encoding must be metric-agnostic.
4. **Don't couple to upstream schemas that are still evolving** (specifically inspect_evals PR #1575 `evaluation_report`). Design Valichord-side independently; write the adapter when upstream stabilises.

He's effectively given Valichord a roadmap. This brief implements step one: build the canonical format properly, in Valichord, designed harness-agnostic from day one.

---

## Upstream context — what's already in inspect_evals

**Important update (verified after Scott's review):** PR #1575 was merged on 2026-04-30 — the `evaluation_report` schema is now stable in main. PR #1593 added a worked example (hangman-bench). Read both before designing the Valichord bundle so we mirror their field shapes where they overlap rather than inventing new ones.

The merged schema, in `src/inspect_evals/metadata.py`:

```python
class EvaluationReportMetric:
    key: str           # metric name (e.g. "accuracy")
    value: numeric     # value

class EvaluationReportResult:
    model: str                              # required
    metrics: list[EvaluationReportMetric]   # required, ≥1
    task: str | None
    provider: str | None
    stderr: str | None
    time: str | None
    date: str | None
    # ConfigDict(extra="allow") — eval-specific fields permitted

class EvaluationReport:
    results: list[EvaluationReportResult]   # required, ≥1
    commit: str                             # required — upstream SHA
    version: str | None
    command: str | None
    timestamp: ... | None
    notes: list | None
    # ConfigDict(extra="allow")
```

Submitters declare these in `register/<eval-name>/eval.yaml`. A worked example is now in `register/hangman-bench/README.md`.

Two takeaways for our design:

1. **Where field names overlap, copy them verbatim.** `commit`, `command`, `model`, `metrics: [{key, value}]`, `task`, `stderr`, `time` are all already there. The Valichord bundle should use the same names — the inspect_evals adapter then becomes a near-trivial mapping rather than a re-translation.
2. **`extra="allow"` is the right flexibility model.** Downstream consumers can add fields without schema bumps. We should adopt the same posture in Valichord's bundle.

What Valichord adds on top of this schema is the **faithfulness layer** — per-sample Merkle commitments — which the inspect_evals report deliberately does not include. That's our value-add, not a re-do of work that's already merged upstream.

---

## The work

Design and ship a **versioned canonical attestation format** in Valichord. This is:

1. A spec document
2. A reference Python implementation
3. A test suite
4. Two worked example bundles
5. An adapter interface (no concrete adapters yet)

Nothing else. No signature schemes, no DNA integration, no actual harness adapters. Those are deliberately deferred.

---

## Design requirements (translated from Scott's feedback)

### R1 — Metric-agnostic, mirroring the upstream shape

The bundle must accommodate any metric shape — single value with stderr, multi-dimensional like agentdojo, pass@k like SWE-bench, custom metrics. **Adopt the same `{key, value}` list pattern as the merged inspect_evals `EvaluationReportMetric`** so the adapter is a one-to-one mapping:

```json
"metrics": [
  {"key": "accuracy", "value": 0.847, "stderr": 0.025},
  {"key": "benign_utility", "value": 0.71},
  {"key": "targeted_asr", "value": 0.04}
]
```

`stderr` and any per-metric metadata are optional fields on each metric object (matching the upstream `extra="allow"` posture). The canonical encoding must produce identical bytes regardless of which optional fields are present (deterministic key ordering, no optional-field-induced variance).

### R2 — Bind report to underlying run (the Valichord-specific value-add)

The merged inspect_evals `EvaluationReport` lives at the metadata layer — it carries scores, commit, command, timing — but it does **not** bind the *report* to the *run* in a verifiable way. That's exactly the gap Scott named, and it's what Valichord's bundle adds on top of the upstream shape.

The bundle must let a verifier confirm "this reported result is faithful to the underlying log" without access to the full log. Minimum viable design:

- Include a Merkle root of per-sample outputs in the bundle (`outputs_merkle_root`).
- Holder of the log can selectively reveal `(sample_index, sample_content, merkle_path)` to prove faithfulness for any sample.
- Verifier checks the path against the root.

This replaces the weak "hash the whole log file" approach with a mechanism that supports selective disclosure. **This is the load-bearing reason a Valichord bundle exists at all on top of an `EvaluationReport`** — without R2, the Valichord bundle is just a re-encoding of upstream metadata.

### R3 — Self-describing

The bundle must carry enough metadata to be interpretable in isolation: model id, task ids, results, format version, harness identifier (if known). No floating hashes.

### R4 — Versioned

Spec and bundle both carry `format_version: "v1"`. Versioning policy in the spec doc says how a future `v2` would relate to `v1` (e.g. v2 adds fields without breaking v1 readers; breaking changes increment major version).

### R5 — Stdlib-friendly

Reference implementation should lean on stdlib for hashing, JSON, encoding. Pydantic is acceptable as a single dependency. Resist heavyweight crypto libraries unless strictly necessary.

---

## Concrete deliverables

### 1. Spec document — `valichord/spec/attestation_format_v1.md`

Sections:
- Overview and goals
- Bundle JSON schema (with examples inline)
- Canonical encoding rules (sorted keys, no whitespace, UTF-8, number representation rules — fixed-precision floats or strings)
- Hashing rules (SHA-256 over canonical encoding)
- Faithfulness-verification protocol (Merkle tree construction, proof format, verifier algorithm)
- Versioning policy
- Non-goals (what v1 deliberately doesn't cover)

### 2. Reference implementation — `valichord/attestation/`

Python module with:
- `Bundle` dataclass / Pydantic model
- `canonicalise(bundle: Bundle) -> bytes` — deterministic JSON encoding
- `hash_bundle(bundle: Bundle) -> str` — SHA-256 hex digest
- `build_bundle(...)` — construction helper
- `merkle_root(samples: list[bytes]) -> str` — outputs Merkle tree root
- `merkle_proof(samples, index) -> list[bytes]` — generate proof
- `verify_faithfulness(bundle, sample_index, sample_content, merkle_path) -> bool`
- `AdapterBase` — abstract class defining the interface a future harness adapter implements (input: harness-native output; output: `Bundle`)

### 3. Tests — `valichord/attestation/tests/`

Coverage:
- **Round-trip:** build → canonicalise → reconstruct from bytes → re-canonicalise → byte-identical
- **Metric-agnostic:** bundles with single-metric, multi-metric, agentdojo-shaped, pass@k metrics all canonicalise consistently
- **Determinism:** same input produces byte-identical canonical encoding across runs and Python versions
- **Faithfulness:** Merkle-tree round-trip, valid proof verifies, tampered sample fails verification, wrong path fails verification
- **Schema validation:** malformed bundles rejected with informative errors
- **Negative cases:** missing required fields, version mismatches, invalid hashes

Aim for ≥90% line coverage on the implementation module.

### 4. Examples — `valichord/attestation/examples/`

Two end-to-end example bundles in JSON, each with the corresponding synthetic source data so a reader can verify the bundle was correctly derived:

- `examples/simple_eval.json` — single metric (accuracy + stderr), single task (e.g. GSM8K-shaped)
- `examples/complex_eval.json` — multi-metric, multi-task, agentdojo-shaped (utility + safety scores per task)

Include a small `examples/verify_examples.py` script that loads each bundle and confirms it canonicalises, hashes, and round-trips correctly.

### 5. README — `valichord/attestation/README.md`

Brief, scoped to:
- What the format is and why it exists (link to Scott's review comment as the architectural rationale)
- Quickstart: build a bundle, hash it, verify a sample
- How a future harness adapter would be written (sketch, not full implementation)
- Pointer to the spec doc for the formal definition

### 6. Adapter sketch — `valichord/attestation/adapters/inspect_evals_stub.py`

A single stub file showing the shape of an inspect_evals adapter, raising `NotImplementedError`. The stub should make the mapping concrete in comments so a future implementer (or Scott, if he reviews it) can see the intent:

```python
class InspectEvalsAdapter(AdapterBase):
    """
    Maps inspect_evals output to a Valichord attestation bundle.

    Inputs:
      - register/<eval>/eval.yaml's `evaluation_report` block
        (see UKGovernmentBEIS/inspect_evals#1575, src/inspect_evals/metadata.py)
      - the corresponding .eval log file (per-sample outputs)

    Mapping:
      EvaluationReport.commit         -> Bundle.harness_commit
      EvaluationReport.command        -> Bundle.command
      EvaluationReportResult.model    -> Bundle.model_id
      EvaluationReportResult.task     -> Bundle.task_id
      EvaluationReportResult.metrics  -> Bundle.metrics  (verbatim)

    Valichord-specific additions (no upstream equivalent):
      Bundle.outputs_merkle_root      <- merkle_root over .eval per-sample outputs
      Bundle.format_version            <- "v1"
    """
    def to_bundle(self, eval_yaml_block, eval_log_file) -> Bundle:
        raise NotImplementedError(
            "inspect_evals adapter deferred until the v1 spec ships and "
            "the inspect_evals API for reading .eval files stabilises"
        )
```

This stub is documentation as much as code — it tells a future contributor exactly what an adapter does without committing us to maintaining it now.

---

## Out of scope — do not implement in this work

- **Concrete harness adapters.** No `InspectEvalsAdapter`, no `LMEvalHarnessAdapter`, no METR adapter. Define `AdapterBase` interface only, with one or two stubs raising `NotImplementedError` with a comment pointing at the upstream schema to wait for.
- **Signature schemes.** The spec should leave room for a future `signatures` field, but signing is explicitly v2+.
- **Integration with existing Valichord DNAs.** The on-chain commit-reveal flow stays untouched. Bundles becoming on-chain attestations is a separate piece of work that comes after the spec is stable.
- **Importing from `inspect_evals` directly.** Mirror the field names where they overlap (free, no dependency); do not import their Pydantic models. The adapter handshake is a future job, and we shouldn't take a runtime dep on a sibling project.
- **UI changes** in `valichord-ui`.
- **Changes to `demo/ai_validator.py`** in this PR. The validator client integration with the new format comes later.

---

## Acceptance criteria

Work is complete when all of the following are true:

- [ ] `valichord/spec/attestation_format_v1.md` exists and is internally complete (someone with no prior context can read it and implement an adapter)
- [ ] `valichord/attestation/` reference implementation passes all tests
- [ ] Test coverage ≥90% on the implementation module
- [ ] Two example bundles exist, round-trip cleanly, and `verify_examples.py` exits 0
- [ ] `AdapterBase` is defined with at least one stub demonstrating the shape
- [ ] `valichord/attestation/README.md` explains the format and adapter pattern
- [ ] No unrelated changes (don't touch DNAs, UI, or `demo/ai_validator.py`)
- [ ] Apache 2.0 license headers on new files matching the rest of the repo

---

## Strategic note

This is the architectural foundation that turns every future Valichord ↔ harness conversation into a thin adapter PR rather than a feature PR. Done right, the next round of harness contact (lm-evaluation-harness, METR task-standard, HELM) becomes much faster, much smaller in scope, and much more likely to merge — because the maintainer will be reviewing "10 lines mapping our output to a stable external spec" rather than "200 lines of unfamiliar abstractions."

The single most common way this work goes wrong is scope creep: adding a signature scheme "while we're here," wiring the bundle into the DNA layer, or building a real adapter against an unstable upstream schema. Resist all three. Spec first; integrations later, separately, when their preconditions are stable.

---

## If anything is ambiguous

Raise the question before guessing. Particular things worth checking with the founder before committing:

- **Number representation in canonical encoding.** Fixed-precision string (e.g. `"0.84700000"`) is reproducible across languages but ugly; IEEE 754 round-trip via shortest-roundtrip representation is cleaner but Python-flavoured. Recommend: shortest-roundtrip with explicit precision rules in the spec, or stringify all numeric values. Decide before writing canonicaliser.
- **Merkle tree leaf format.** Three options: (a) raw per-sample-output bytes, (b) sha256 of structured per-sample dict, (c) sha256 of canonicalised per-sample JSON. Recommend (c) — most robust to representation drift in the harness. Confirm before implementing.
- **Whether to mirror upstream `commit` semantics or use a separate `harness_commit`.** The merged `EvaluationReport.commit` is the upstream-eval-repo commit. Valichord might want both that and the harness-implementation commit (e.g., `inspect_ai` framework version). Recommend two fields: `repo_commit` and `harness_version`. Confirm.

These are real design choices; don't bury them in implementation details.
