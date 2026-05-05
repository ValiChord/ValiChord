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
| `samples.total` | `integer` | Total number of samples the run was intended to produce. Non-negative. When the caller passes an explicit `samples_total` to `build_bundle`, that value is recorded here and may exceed `samples.completed`, making silent sample omission detectable. Defaults to `samples.completed` when no explicit total is declared. |
| `samples.completed` | `integer` | Number of samples actually included in the bundle (and committed to `outputs_merkle_root`). Non-negative. |
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

## 6. Probabilistic Challenge-Response

### Goal and trust model

Section 5 delivers *selective disclosure* — the log holder proves individual samples on request, choosing which ones to reveal. A stronger property is verifier-controlled randomness: the verifier picks which samples to inspect, the holder must reveal those specific ones, and the verifier gains high-confidence evidence of faithfulness without the log holder being able to cherry-pick favourable samples.

This protocol achieves that. The verifier supplies a random nonce; the challenged indices are derived deterministically from `(bundle_hash, nonce, k)`, so the holder cannot predict them before committing to the bundle, and cannot choose which samples to reveal.

### Probabilistic guarantee

If a fraction `f` of the log is fabricated and the verifier requests `k` random samples, the probability of catching at least one fabricated sample is `1 - (1-f)^k`.

| f \ k | k=10 | k=30 | k=60 | k=100 | k=300 |
|---|---|---|---|---|---|
| f = 1% | 10% | 26% | 45% | 63% | 95% |
| f = 5% | 40% | 79% | 95% | 99% | >99% |
| f = 10% | 65% | 96% | 99.8% | >99% | >99% |

This guarantee is probabilistic, not deterministic. A verifier must choose `k` based on the cheating fraction they want to detect and the confidence level they require. A response that passes verification does not mean the log is 100% faithful — it means the verifier found no fabrication in the `k` challenged samples.

### `Challenge` schema

```json
{
  "bundle_hash":     "<64 hex chars>",
  "verifier_nonce":  "<hex string, min 32 chars = 16 bytes>",
  "k":               20
}
```

| Field | Type | Description |
|---|---|---|
| `bundle_hash` | `string` | SHA-256 hex digest of the target bundle (from Section 4). |
| `verifier_nonce` | `bytes` | Verifier-chosen random bytes, minimum 16 bytes. Serialised as a lowercase hex string when encoding. |
| `k` | `integer` | Number of samples to challenge. Must be > 0 and ≤ `samples.total`. |

### `ChallengeResponse` schema

```json
{
  "challenge_hash": "<64 hex chars>",
  "samples": [
    {
      "sample_index":        42,
      "sample_content_hash": "<64 hex chars>",
      "merkle_path": [
        {"position": "right", "sibling": "<64 hex chars>"},
        {"position": "left",  "sibling": "<64 hex chars>"}
      ]
    }
  ]
}
```

| Field | Type | Description |
|---|---|---|
| `challenge_hash` | `string` | `compute_challenge_hash(challenge)` — binds this response to a specific challenge. |
| `samples` | `array` | One entry per challenged index, in the order returned by `generate_indices`. |
| `samples[i].sample_index` | `integer` | Position of this sample in the original log. |
| `samples[i].sample_content_hash` | `string` | `SHA-256(JCS(sample_dict))` — the same leaf hash used in the Merkle tree (see `leaf_hash` in the reference implementation). |
| `samples[i].merkle_path` | `array` | Inclusion proof in the same format as Section 5 (`{"position", "sibling"}` steps). |

The response contains only hashes and proof paths — no raw sample content. The verifier learns that the holder has a sample whose hash chains to the bundle's Merkle root, without receiving the sample content itself.

### Seed derivation

```
seed = HMAC-SHA256(key=verifier_nonce_bytes, msg=bundle_hash_ascii_bytes)
```

`bundle_hash` is the 64-character ASCII hex string encoded as UTF-8 bytes. Using `verifier_nonce` as the HMAC key and `bundle_hash` as the message binds the seed to both: changing either produces a completely different seed.

### Index derivation — SHA-256 counter-mode

```
seed = derive_seed(challenge)
indices = []
seen = {}
counter = 0
while len(indices) < k:
    digest = SHA-256(seed || counter.to_bytes(8, big-endian))
    candidate = int.from_bytes(digest, big-endian) mod total_samples
    if candidate not in seen:
        seen.add(candidate)
        indices.append(candidate)
    counter += 1
```

The counter is an 8-byte big-endian unsigned integer. Any conforming implementation produces identical `indices` given the same `(bundle_hash, verifier_nonce, k, total_samples)`.

**Test vector** (for cross-implementation validation):
- `bundle_hash`: `"aaaa...aaaa"` (64 `a` characters)
- `verifier_nonce`: bytes `[0x00, 0x01, ..., 0x0f]` (16 bytes)
- `k = 5`, `total_samples = 100`
- Expected `seed` (hex): `4b763d6f418f14dd085e3458c666fd9a00b6cd0132da3a049c07f96a1d9582f7`
- Expected `indices`: `[9, 69, 33, 74, 38]`

### `challenge_hash` computation

```
canonical = JCS({"bundle_hash": <str>, "k": <int>, "verifier_nonce_hex": <hex str>})
challenge_hash = SHA-256(canonical).hex()
```

Keys are sorted lexicographically by JCS. The nonce is hex-encoded so the dict is JSON-serialisable. The `challenge_hash` appears in the `ChallengeResponse` to bind it to a specific challenge; a response verified against the wrong challenge will fail immediately.

### Response verification algorithm

```python
def verify_response(challenge, response, bundle):
    if response.challenge_hash != compute_challenge_hash(challenge):
        return False
    expected_indices = set(generate_indices(challenge, bundle.samples_total))
    if {s.sample_index for s in response.samples} != expected_indices:
        return False
    for sample in response.samples:
        current = bytes.fromhex(sample.sample_content_hash)
        for step in sample.merkle_path:
            sibling = bytes.fromhex(step["sibling"])
            if step["position"] == "right":
                current = SHA-256(current + sibling)
            else:
                current = SHA-256(sibling + current)
        if current.hex() != bundle.outputs_merkle_root:
            return False
    return True
```

Missing or `None` required fields MUST raise an error rather than produce a hash of `0` or an empty value — see Section 8 (hash-collision safety).

---

## 7. Versioning policy

- The `format_version` field is `"v1"` for all bundles conforming to this spec.
- **Additive changes** (new optional fields, new optional Metric fields) MAY be made without incrementing the version, under the `extra="allow"` posture. v1 readers MUST ignore unrecognised fields.
- **Breaking changes** (removing required fields, changing canonical encoding rules, changing Merkle construction) MUST increment to `"v2"`. A v2 spec will document migration from v1.
- The `bundle_sha256` of a v1 bundle remains stable across additive changes because the canonical encoding omits `None`-valued optional fields.

---

## 8. Adapter interface

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

## 9. Security considerations

- **NaN/Infinity in metrics** — rejected with a `MalformedBundleError`. Including non-finite values in the canonical encoding produces implementation-defined bytes, breaking cross-implementation hash compatibility.
- **Absent fields defaulting** — `build_bundle` raises `MalformedBundleError` if a required metric field is missing. Never silently default to `0.0` — two logs that both fail extraction would produce the same hash, falsely claiming the runs matched.
- **Proof forgery** — an adversary who controls both the bundle and the proof could construct a false inclusion proof. The Merkle root in the bundle and the proof are only meaningful together with a trustworthy bundle provenance (e.g. a git commit, a signed statement, or a Valichord DHT entry).

---

## 10. Threat model

### Attacker capabilities assumed

An adversary constructing a bundle is assumed to control:
- The harness execution environment (so they can fabricate per-sample outputs)
- The adapter that translates harness output into a bundle (so they can omit, reorder, or alter samples before commitment)
- The reported metric values in `raw_metrics`

An adversary is **not** assumed to control:
- The verifier's randomness (the verifier supplies a fresh nonce for each challenge)
- The cryptographic hash function (SHA-256 collision resistance is assumed)
- Out-of-band knowledge such as the expected total sample count for a known benchmark

### Attack surfaces and what the protocol catches

**(a) Misreporting of committed sample contents.** If the adversary commits to a Merkle root and later, when challenged, reveals samples whose hashes do not reconstruct the root — the verifier detects the inconsistency directly via Merkle proof verification. *Always caught when challenged.*

**(b) Fabrication of sample outputs.** If the adversary fabricates a fraction `f` of per-sample outputs (committing to fake samples consistent with their fake Merkle root), a verifier requesting `k` random samples catches at least one fake with probability `1 - (1-f)^k`. The verifier tunes `k` to the cheating fraction they want to detect (see sensitivity table in Section 6). *Catches with bounded probability that grows with k.*

**(c) Metric misreporting (metric ↔ sample linkage).** The bundle separately commits to `raw_metrics` (the reported numbers) and `outputs_merkle_root` (the Merkle commitment over samples). An adversary could compute honest metrics from genuine samples and then attach those metrics to a different Merkle root, OR commit to honest samples and report different metrics. To detect this, **a verifier must recompute the metric from the disclosed samples and confirm it matches the reported metric in `raw_metrics`.** This recomputation is a verifier-side responsibility in v1.1; future versions may bundle the metric-derivation function into the bundle itself so the recomputation is automatic. *Caught only if the verifier performs metric recomputation on disclosed samples.*

**(d) Sample omission.** If the adversary drops failed or inconvenient samples wholesale before constructing the bundle, the resulting Merkle root is honest about a smaller-than-real run. The bundle commits `samples.total` (the declared intended total) and `samples.completed` (the count actually committed to the Merkle root). As of v1.1, `build_bundle` accepts an explicit `samples_total` parameter: when the caller passes the true intended run size, a silent adapter that drops samples will produce a bundle where `samples.total > samples.completed`, which is directly visible in the bundle. A verifier with out-of-band knowledge of the benchmark's true size can detect a discrepancy in either field. In Valichord's federated protocol, multiple independent validators running the same eval should converge on the same `samples.total`, and divergence is itself a flag. *Caught only with external knowledge of expected sample count, or via federation; explicit `samples_total` declaration shifts the detection point from out-of-band comparison to in-bundle inspection.*

### Composition with the protocol layer

The format provides defences against (a) and (b) directly, and against (c) given an honest verifier who performs metric recomputation. It cannot fully address (d) without external context. Valichord's broader protocol — federation across independent validators, on-chain commit-reveal, warrants — addresses (d) by making divergent `samples.total` claims detectable across the validator pool.

### What the protocol does not claim

- It does **not** provide zero-disclosure verification (verifying without any log access). The log holder must be available to respond to challenges; selective disclosure of challenged samples is required.
- It does **not** provide absolute (rather than probabilistic) faithfulness verification under (b) and (c) without full sample disclosure.
- It does **not** prevent collusion between adversaries who control both the bundle producer and the log holder of the same bundle.

---

## 11. Limitations and trust boundaries

### Adapter trust boundary

The protocol commits to per-sample outputs that the adapter chooses to include. If a malicious adapter drops failed samples wholesale before constructing the bundle, the resulting Merkle root is internally honest about a smaller-than-real run. The challenge-response catches misreporting of committed samples, not omission of samples that should have been committed.

Mitigations available at the protocol layer (outside the format itself):
- The bundle commits `samples.total` (the declared sample count), which a verifier can check against external expectations of the benchmark size.
- In Valichord's federated protocol, multiple independent validators running the same eval should converge on the same `samples.total`; an adapter that systematically drops samples would diverge from honest validators.
- On-chain warrants can be issued against validators whose attestations are demonstrably inconsistent with peers'.

The format alone cannot solve this; the protocol layer mitigates it.

### Metric semantics vs metric faithfulness

The bundle proves that the reported numerical metrics are faithful to the underlying run — not that two runs producing the same numbers are methodologically equivalent. Two evaluations producing `{"accuracy": 0.847}` may differ in prompt formatting, scaffold, decoding parameters, or system message, while still both being honest about their respective runs. The bundle's `harness_version` and `command` fields capture some of this context, but semantic equivalence across runs is a methodology problem, not a cryptographic one. Verifiers comparing bundles should treat numerical match as necessary but not sufficient evidence of methodological equivalence.

### Floating-point determinism

RFC 8785 canonical encoding does not by itself guarantee cross-language determinism for floating-point numbers, since IEEE 754 representations and shortest-roundtrip serialisations can vary subtly across implementations. The format addresses this with mandatory pre-rounding rules: accuracy / probability / score-style metrics are pre-rounded to six decimal places before encoding; counts and sample totals are stored as integers; time durations are stored as integer milliseconds; `NaN`, `Infinity`, and subnormal values are explicitly rejected. Pre-rounding happens before the canonical encoder runs, not as part of it. Implementations that follow these rules produce byte-identical encodings across Python, JavaScript, Rust, and other JCS-compliant runtimes.
