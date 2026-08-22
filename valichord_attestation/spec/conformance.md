# Valichord attestation — terms, keywords and conformance

**Status:** normative. Applies across **all** format versions.
**Scope:** what an implementation must do to claim conformance, and what the words mean.

This document exists because `attestation_format_v1.md` and `attestation_format_v2.md` are
*version-scoped* — v2 states plainly that its scope of change is "the Merkle construction, and
nothing else". Conformance and vocabulary are not properties of a version, so they cannot live in
a document named after one. `spec/v2-backlog/` closed when its items shipped and left nowhere to
record what outside implementers had found; a version-named container closes, and this one does
not. Same reasoning, stated once in `format-backlog/README.md`.

Nothing here changes any requirement. It states, as numbered requirements, rules the two format
specifications already describe in prose — so that an implementation targeting compatibility has
a definite list to check itself against rather than a document to interpret.

---

## 1. Normative keywords

The key words **MUST**, **MUST NOT**, **REQUIRED**, **SHALL**, **SHALL NOT**, **SHOULD**,
**SHOULD NOT**, **RECOMMENDED**, **MAY** and **OPTIONAL** are to be interpreted as described in
BCP 14 (RFC 2119 and RFC 8174) when, and only when, they appear in all capitals.

Lower-case uses of these words in this and the format specifications carry their ordinary English
meaning and impose no requirement. Prose in the format specifications that describes behaviour
without a capitalised keyword is explanatory; where such prose and a requirement in §4 of this
document appear to conflict, **the requirement in §4 governs** and the conflict is a defect that
should be reported.

## 2. How to cite these specifications

**Cite by Git commit hash, not by a bare version string.**

Three different numbering schemes are in play and they are not interchangeable:

| Scheme | Example | What it names |
|---|---|---|
| `format_version` | `v2` | The bundle format, and the Merkle construction it selects |
| Package version | `2.0.0` | The Python distribution `valichord_attestation` |
| Repository tag | `v0.6.5` | A release of the whole ValiChord repository |

A bundle's `format_version` is the only one of the three that is load-bearing for verification.
Citing "ValiChord attestation 2.0.0" does not identify a format, and citing "v2" does not identify
a document revision. Until a document revision is fixed, cite the commit.

## 3. Terms and definitions

**3.1 bundle** — a JSON document conforming to §2 of `attestation_format_v1.md`, recording the
metrics of one evaluation run together with a commitment to that run's per-sample outputs.

**3.2 sample** — one unit of evaluation work whose output is committed individually. What
constitutes a sample is determined by the harness, not by this format.

**3.3 per-sample output** — the dict recorded for one sample and committed as a leaf.

**3.4 leaf digest** — the hash of one per-sample output under the construction named by the
bundle's `format_version`.

**3.5 construction** — the algorithm mapping an ordered list of per-sample outputs to
`outputs_merkle_root`. Selected by `format_version`; never assumed.

**3.6 `outputs_merkle_root`** — the root of the tree over per-sample outputs. 64 lower-case hex
characters at every format version.

**3.7 `bundle_hash`** — SHA-256 over the canonical encoding of the whole bundle, `meta` included.
Answers *is this the same bytes?*

**3.8 `content_hash`** — the same, computed with `meta` excluded. Answers *is this the same
science?* Two runs differing only in provenance share a `content_hash`; that exclusion is
deliberate and is the reason anything capable of changing a result MUST NOT be recorded only in
`meta` (§4.1.9).

**3.9 canonical encoding** — RFC 8785 (JCS), applied after the pre-rounding of §3.10.

**3.10 pre-rounding** — the normalisation applied to numeric values *before* canonical encoding,
specified in §3 of `attestation_format_v1.md`. It is not part of the canonicaliser.

**3.11 holder** — the party in possession of a bundle's per-sample outputs, able to answer a
challenge. Not necessarily the party that produced the bundle.

**3.12 verifier** — the party checking a bundle. Supplies the nonce in a challenge.

**3.13 faithfulness** — the property that a bundle's committed samples are the samples the run
produced. Faithfulness is **not** correctness, and it is not methodological equivalence: see §5.

**3.14 conformance vector** — a file under `tests/vectors/` pinning expected roots for a
construction. Frozen once published.

**3.15 repeatability** — agreement between results obtained under *the same* conditions: same
operator, same equipment, same method, same location, over a short interval.

**3.16 reproducibility** — agreement between results obtained under *different* conditions:
different operator, different equipment, different location.

> **3.15 and 3.16 follow the distinction drawn in ISO 5725**, paraphrased rather than quoted, and
> are recorded here because the format has been asserting one while the protocol claims the other.
> They are **different quantities**, and conflating them overstates what a record establishes. What
> the protocol demonstrates is reproducibility; what a re-run by the original party demonstrates is
> repeatability. Backlog item 05 proposes a field recording which conditions were varied; **that
> field is not specified here and remains open.** Defining the words is not the same as adding the
> field, and the field is not being designed unilaterally.

**3.17 asserted** — a value supplied by a party with an interest in the result.

**3.18 observed** — a value derived from evidence the asserting party does not control.

> **3.17 and 3.18 are the line the format has to keep visible.** A bundle records both kinds of
> value and, today, marks neither. Any field added to this format should say which side it sits on,
> and where the format cannot tell, it should say so explicitly rather than let absence read as
> agreement. Raised by KeilerHirsch (BRONCO) as a constraint on model identity; it generalises.

---

## 4. Conformance requirements

An implementation MAY conform as a **writer**, a **verifier**, or both. A claim of conformance
MUST name the format version or versions it covers and the roles it claims.

### 4.1 Writers

A conformant writer:

1. **MUST** emit `format_version`, and it **MUST** name the construction actually used to compute
   `outputs_merkle_root`.
2. **MUST** emit every required field of §2 of `attestation_format_v1.md`: `format_version`,
   `generated_at`, `model_id`, `task_id`, `metrics` (non-empty), `samples.total`,
   `samples.completed`, `outputs_merkle_root`.
3. **MUST** omit absent optional fields from the canonical encoding entirely. It **MUST NOT**
   serialise them as `null`.
4. **MUST** apply the pre-rounding rules of §3 of `attestation_format_v1.md` before canonical
   encoding: ratio-style floats and `stderr` to exactly six decimal places; sample counts as JSON
   integers; durations as integer milliseconds or an explicit unit-suffixed string.
5. **MUST** reject `NaN`, `Infinity` and subnormal floats with an error. It **MUST NOT** emit them.
6. **MUST** raise rather than default when a required metric field is missing. It **MUST NOT**
   substitute `0.0`. *Two extractions that both failed would otherwise produce identical hashes and
   falsely report matching runs.*
7. **MUST** encode with RFC 8785 (JCS), UTF-8, no BOM, and **SHOULD** use a maintained JCS library
   rather than a hand-rolled canonicaliser.
8. **MUST NOT** emit a bundle whose sample list is empty. *A root for the empty tree is defined at
   v2 so that implementations agree on the value; that does not make an empty bundle valid.*
9. **MUST NOT** place in `meta` any value capable of changing the result. *`meta` is excluded from
   `content_hash`, so a value recorded only there is invisible to every equivalence comparison.*
10. **SHOULD** set `samples.total` to the run's intended size where the harness knows it, so that
    an adapter dropping samples is visible in the bundle as `total > completed`.

### 4.2 Verifiers

A conformant verifier:

1. **MUST** select the construction from the `format_version` of the bundle under examination.
   It **MUST NOT** use a default, and **MUST NOT** assume the version it writes.
   *A root is 64 hex characters at every version, so checking a v1.2 root under v2 rules returns
   "does not verify" — indistinguishable from genuine tampering.*
2. **MUST** refuse, with an error, any `format_version` it does not recognise. It **MUST NOT**
   guess.
3. **MUST** verify inclusion proofs under that same construction.
4. **MUST NOT** treat a verified inclusion proof as evidence that reported aggregate metrics were
   correctly computed. It proves the sample was committed, and no more (§5).
5. **SHOULD** recompute each reported metric from the samples disclosed to it and compare against
   `metrics`. *Without this step the format's stated coverage of metric misreporting does not
   apply; see §10(c) of `attestation_format_v1.md`.*
6. **SHOULD** compare `samples.total` against out-of-band knowledge of the benchmark's size, and
   **SHOULD** treat `total > completed` as a fact to be explained rather than noise.

### 4.3 Challenge–response

1. A `ChallengeResponse` **MUST** be built under the `format_version` of the bundle it answers.
   *A response built under v2 against a v1.2 bundle fails verification and is indistinguishable
   from a dishonest one.*
2. A verifier **MUST** supply a fresh nonce per challenge and **MUST NOT** accept a response to a
   nonce it did not generate.
3. The number of challenged samples `k` is the verifier's choice. An implementation **MUST NOT**
   cap it below the run's completed sample count.

### 4.4 Vector conformance

1. An implementation claiming **v2** **MUST** reproduce every expected root in
   `tests/vectors/merkle_v2.json`.
2. It **MUST** produce **different** roots for the two inputs in the odd-node vector file. *This is
   the single clearest check that the tree-shape rule was adopted and not merely the domain-
   separation prefixes — `n // 2` as a split rule agrees with RFC 6962 up to exactly n = 4, so a
   broken implementation passes every vector that stops there.*
3. An implementation claiming to verify **v1.x** bundles **MUST** reproduce every expected root in
   `tests/vectors/merkle_v1_2.json` and `merkle_v1_2_odd_node.json`, **including** the documented
   odd-node collision. *Reproducing a known defect is the requirement, not a bug: those files are
   the evidence that already-issued bundles still verify.*
4. Vector files, once published, are **frozen**. A new construction **MUST** add a file. An
   implementation **MUST NOT** retarget an existing vector file to a later construction.

---

## 5. What conformance does not establish

Stated here so that a conformance claim cannot be read as more than it is. Full treatment in §§5,
10 and 12 of `attestation_format_v1.md`.

- **Not correctness.** A bundle can be perfectly faithful about a run that was badly designed.
- **Not equivalence.** Two bundles reporting `accuracy: 0.847` may differ in prompt formatting,
  scaffold, decoding parameters or system message. Numerical match is necessary evidence of
  methodological equivalence, never sufficient.
- **Not aggregate integrity.** The root proves the samples were committed, not that the reported
  numbers were computed from them. Only §4.2.5 recomputation addresses that.
- **Not completeness.** An adapter that drops samples before the tree is built produces a bundle
  that is internally honest about a smaller run. The format cannot detect this alone; declaring
  `samples.total` makes it *inspectable*, and federation across independent parties is what makes
  it *detectable*.
- **Not non-collusion.** A bundle producer and a holder acting together are outside the model.

---

## 6. Reporting a defect in this document

A requirement here that the format specifications do not support is a defect in **this** document
and should be reported as one — these are intended to be a restatement, not a new rule. Open an
issue naming the requirement number and the clause it conflicts with.
