# Valichord Attestation Format v1

**Status:** Draft  
**Format version string:** `"v1"`  
**Reference implementation:** `valichord_attestation/` (this repository)

---

## 1. Overview and goals

An attestation bundle is a lightweight JSON document that binds a published evaluation result claim to the underlying run that produced it. Its purpose is to let a third party — a journal reviewer, a downstream consumer, an independent replication service — verify that the numbers in a report match the actual run without necessarily holding the full log file.

The format is designed to be harness-agnostic. One bundle schema covers any eval harness (Inspect AI, lm-evaluation-harness, METR task-standard, HELM, etc.); harness-specific adapters are thin converters, not part of the core spec.

### What v1 provides

- A canonical, deterministic encoding of the bundle (RFC 8785 / JCS) so the same run always produces the same bytes and therefore the same hash.
- A metric-agnostic result encoding that covers single-metric evals (accuracy + stderr), multi-dimensional evals (agentdojo utility + ASR rates), and ranked-pass evals (SWE-bench pass@k).
- A Merkle root over per-sample outputs so the holder of the full log can selectively prove individual sample faithfulness without disclosing the entire log.

### What v1 does not provide (non-goals)

- **Cryptographic signing.** A `signatures` field is reserved for v2. In v1, trust rests on the same social-attestation chain that git commits and PR reviews already provide.
- **Zero-disclosure verification.** v1 enables *selective disclosure* — the log holder proves individual samples on request. Full zero-disclosure (verify without any log access) requires ZK proofs; that is v2+ scope.
- **Harness-specific adapters.** `AdapterBase` and a stub are included. Concrete adapters are shipped separately when upstream APIs stabilise.
- **Integration with Valichord DNAs.** Bundles becoming on-chain attestations is separate work that follows format stabilisation.

### Relationship to existing attestation mechanisms

Git commit authorship and PR-review endorsement already constitute a *social* attestation chain for eval reports. Valichord bundles add a *cryptographic faithfulness layer* on top: the Merkle root binds the per-sample outputs to the reported aggregates, enabling verification that the report faithfully summarises the run.

---

## 2. Bundle JSON schema

### Required fields

| Field | Type | Description |
|---|---|---|
| `format_version` | `string` | Always `"v1"` for this spec. |
| `generated_at` | `string` | ISO 8601 timestamp, UTC recommended (e.g. `"2026-05-05T12:00:00+00:00"`). |
| `model_id` | `string` | Model identifier (e.g. `"gpt-4o-2024-08-06"`). |
| `task_id` | `string` | Task/eval identifier (e.g. `"gsm8k"`, `"agentdojo/travel"`). |
| `metrics` | `array[Metric]` | One or more result metrics. See Metric schema below. Non-empty. |
| `samples.total` | `integer` | Total sample count. Non-negative. |
| `samples.completed` | `integer` | Completed sample count. Non-negative. |
| `outputs_merkle_root` | `string` | SHA-256 hex Merkle root over per-sample output dicts. 64 hex chars. |

### Optional fields

| Field | Type | Description |
|---|---|---|
| `repo_commit` | `string` | Git commit hash of the eval repository. |
| `harness_version` | `string` | Eval harness version (e.g. `"inspect_ai/0.3.19"`). |
| `command` | `string` | Command used to run the eval. |

Optional fields MUST be omitted from the canonical encoding when absent — never serialised as `null`.

### Metric schema

```json
{"key": "accuracy", "value": 0.847, "stderr": 0.025}
```

| Field | Type | Required | Description |
|---|---|---|---|
| `key` | `string` | Yes | Metric name (e.g. `"accuracy"`, `"pass_at_1"`, `"benign_utility"`). |
| `value` | `number` | Yes | Metric value. Must be a finite float pre-rounded to 6 decimal places. |
| `stderr` | `number` | No | Standard error. Finite float pre-rounded to 6 dp if present; omitted otherwise. |

Additional fields on a Metric object are permitted (`extra="allow"` posture). Unrecognised fields are preserved in the canonical encoding but have no defined semantics in v1.

### Complete example

```json
{
  "format_version": "v1",
  "generated_at": "2026-05-05T12:00:00+00:00",
  "model_id": "gpt-4o-2024-08-06",
  "task_id": "gsm8k",
  "metrics": [
    {"key": "accuracy", "value": 0.847, "stderr": 0.025}
  ],
  "samples": {"total": 1319, "completed": 1319},
  "outputs_merkle_root": "a3f2...64 hex chars...",
  "repo_commit": "abc123",
  "harness_version": "inspect_ai/0.3.19",
  "command": "inspect eval gsm8k --model openai/gpt-4o-2024-08-06"
}
```

Multi-metric (agentdojo-shaped):
```json
{
  "format_version": "v1",
  "generated_at": "2026-05-05T12:00:00+00:00",
  "model_id": "claude-3-5-sonnet-20241022",
  "task_id": "agentdojo/travel",
  "metrics": [
    {"key": "benign_utility",  "value": 0.75},
    {"key": "targeted_asr",   "value": 0.0625},
    {"key": "untargeted_asr", "value": 0.0}
  ],
  "samples": {"total": 16, "completed": 16},
  "outputs_merkle_root": "7f73...64 hex chars..."
}
```

---

## 3. Canonical encoding rules

The canonical encoding is **RFC 8785 (JSON Canonicalization Scheme / JCS)**. Use a maintained JCS library; do not hand-roll.

### Pre-rounding (applied before encoding, not inside the canonicaliser)

| Value type | Rule |
|---|---|
| Accuracy, probability, score-style float | Round to exactly 6 decimal places (`round(v, 6)`) before constructing a `Metric`. |
| `stderr` | Same: round to 6 dp. |
| `samples.total`, `samples.completed` | JSON integers — no rounding. |
| Time durations (if added in future fields) | Integer milliseconds, or an explicit unit-suffix string (e.g. `"3600s"`). |
| NaN, Infinity, subnormal floats | **Raise an error.** Never include in a bundle. |

The 6 dp precision gate is a policy choice: two runs that agree within 6 dp will produce identical hashes; runs that differ beyond 6 dp will not. An attestation system that silently defaults missing fields to `0.0` would produce matching hashes for two broken extractions — this is a correctness failure. Pre-rounding rules ensure that absent fields raise rather than silently match.

### Key ordering

JCS sorts object keys lexicographically. No manual sorting is required — the library handles it. Array order is preserved (metric list order is significant).

### String encoding

UTF-8. No BOM.

---

## 4. Hashing rules

The bundle hash is the SHA-256 hex digest of the JCS canonical encoding:

```
bundle_sha256 = hex(SHA-256(JCS(bundle_dict)))
```

The `bundle_sha256` is not a field inside the bundle JSON — it is computed from the bundle and stored or transmitted separately (e.g. in a report, a commit message, or a Valichord DHT entry). Including it inside the bundle would make it a self-referential hash, which is undefined.

---

## 5. Faithfulness-verification protocol

The Merkle root binds the reported aggregate metrics to the per-sample outputs that produced them.

### Leaf construction

Each sample's leaf hash is:

```
leaf = SHA-256(JCS(sample_dict))
```

where `sample_dict` is the per-sample output dict, JCS-encoded. Using JCS for leaves ensures deterministic bytes regardless of key insertion order in the harness output.

### Tree construction

1. Compute a leaf hash for each sample in order.
2. If the number of leaves at any level is odd, duplicate the last node before pairing.
3. Pair adjacent nodes and hash pairs: `parent = SHA-256(left_bytes || right_bytes)`.
4. Repeat until one node remains. That is the Merkle root.

```
leaves:  [h(s0), h(s1), h(s2), h(s3)]
level 1: [h(h(s0)||h(s1)), h(h(s2)||h(s3))]
root:    [h(level1[0]||level1[1])]
```

Odd-length example (3 leaves):
```
leaves:  [h(s0), h(s1), h(s2)]
padded:  [h(s0), h(s1), h(s2), h(s2)]   <- last node duplicated
level 1: [h(h(s0)||h(s1)), h(h(s2)||h(s2))]
root:    [h(level1[0]||level1[1])]
```

### Proof format

An inclusion proof for sample at index `i` is a list of steps from leaf to root:

```json
[
  {"position": "right", "sibling": "<64 hex chars>"},
  {"position": "left",  "sibling": "<64 hex chars>"}
]
```

- `"position": "right"` — the sibling is the right child; combine as `SHA-256(current || sibling)`.
- `"position": "left"` — the sibling is the left child; combine as `SHA-256(sibling || current)`.

### Verifier algorithm

```python
def verify_faithfulness(root_hex, sample, proof):
    current = SHA-256(JCS(sample))
    for step in proof:
        sibling = bytes.fromhex(step["sibling"])
        if step["position"] == "right":
            current = SHA-256(current + sibling)
        else:
            current = SHA-256(sibling + current)
    return current.hex() == root_hex
```

### What this proves

Given a valid proof, the verifier has confirmed:
- The sample dict produces a leaf that chains to the stored `outputs_merkle_root`.
- The `outputs_merkle_root` in the bundle was derived from a set of samples that included this exact sample at this position.

If the reported aggregate metrics were computed from those same samples, the report is faithful to the run. The verifier can check any individual sample without receiving the entire log.

### What this does not prove

The Merkle root proves the *samples were present*, not that the *aggregate metrics were correctly computed from them*. A dishonest reporter could include real samples but miscompute the aggregate. Catching that requires recomputing the aggregate from the full sample set — which requires the full log. v1 is a foundation for stronger verification, not a complete solution.

---

## 6. Versioning policy

- The `format_version` field is `"v1"` for all bundles conforming to this spec.
- **Additive changes** (new optional fields, new optional Metric fields) MAY be made without incrementing the version, under the `extra="allow"` posture. v1 readers MUST ignore unrecognised fields.
- **Breaking changes** (removing required fields, changing canonical encoding rules, changing Merkle construction) MUST increment to `"v2"`. A v2 spec will document migration from v1.
- The `bundle_sha256` of a v1 bundle remains stable across additive changes because the canonical encoding omits `None`-valued optional fields.

---

## 7. Adapter interface

Adapters map harness-native outputs to `Bundle` objects. The interface:

```python
class AdapterBase(ABC):
    @abstractmethod
    def to_bundle(self, *args, **kwargs) -> Bundle: ...
```

An adapter receives:
1. The harness report metadata (model id, task id, metrics, commit, command).
2. The per-sample output dicts (to compute `outputs_merkle_root`).

It calls `build_bundle(...)` from the reference implementation, passing `raw_metrics` (list of `{"key", "value", "stderr"}` dicts) and `samples` (list of per-sample dicts).

The metric names in `raw_metrics` should match the harness's own names verbatim where possible, so the bundle field names are consistent with what the harness reports. For inspect_evals specifically, `EvaluationReportMetric.key` maps directly to `Metric.key`.

---

## 8. Security considerations

- **NaN/Infinity in metrics** — rejected with a `MalformedBundleError`. Including non-finite values in the canonical encoding produces implementation-defined bytes, breaking cross-implementation hash compatibility.
- **Absent fields defaulting** — `build_bundle` raises `MalformedBundleError` if a required metric field is missing. Never silently default to `0.0` — two logs that both fail extraction would produce the same hash, falsely claiming the runs matched.
- **Proof forgery** — an adversary who controls both the bundle and the proof could construct a false inclusion proof. The Merkle root in the bundle and the proof are only meaningful together with a trustworthy bundle provenance (e.g. a git commit, a signed statement, or a Valichord DHT entry).
