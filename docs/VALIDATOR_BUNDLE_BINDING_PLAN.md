# Binding validator verdicts to their reproduction bundles

**Status:** scoped, not built · **Written:** 2026-07-31 · **Origin:** the open gap documented in
falsify-cookbook Pattern 13 (co-authored with ValiChord)

---

## The gap, in their words

From `studio-11-co/falsify-cookbook`, `patterns/13-commit-reveal-validation.md`:

> Validators are not currently bound to verified reproduction bundles. While they commit to
> verdicts, they do not yet commit to hashes of their own attestation bundles. A validator
> claiming "Reproduced" with different per-sample outputs wouldn't be caught by protocol
> alone — this is marked as a planned extension.

That is accurate. Today a validator commits to an **opinion** (`AttestationOutcome::Reproduced`,
a confidence, a summary) and nothing binds that opinion to the **work** that supposedly produced
it. The commit-reveal machinery faithfully proves they held that opinion before seeing anyone
else's — and says nothing about what they actually ran.

It is the same shape as the correlated-verifier question in the AI Alignment Foundation
proposal: a verdict that is structurally sound but under-bound to its evidence.

---

## 🕐 Why this is time-sensitive, and the main reason to decide now

**The 0.7 migration already changes every DNA hash.** `ValidationAttestation` lives in
`shared_types`, so touching it is normally a hash-breaking change — the expensive kind that
kills every published HarmonyRecord URL. We spent part of 2026-07-31 cleaning up after exactly
that (four files advertising a record dead since the Oracle reclamation).

Right now that cost is **already being paid**. Landing this on the `v0.7.0` branch is
effectively free. Landing it after the merge means a *second* hash break and a second round of
dead URLs.

If it is going to be done at all, it should be done on this branch or deliberately deferred a
long way — not "soon".

---

## Why the change is small

The commitment is computed in `validator_workspace_coordinator/src/lib.rs:89-94`:

```rust
let msgpack_bytes = input.attestation.commitment_msgpack_bytes()?;
let mut hasher = Sha256::new();
hasher.update(&msgpack_bytes);
hasher.update(&nonce);
let commitment_hash: Vec<u8> = hasher.finalize().to_vec();
```

and verified at reveal in `attestation_coordinator/src/lib.rs:276-296` against the same
`commitment_msgpack_bytes()` helper — deliberately shared between the two DNAs so the bytes
cannot drift.

**Consequence: any field added to `ValidationAttestation` is bound into the commitment
automatically.** There is no hashing change, no new verification path, no new protocol message.
The existing machinery does the work.

---

## Proposed change

### 1. `shared_types` — one field

```rust
pub struct ValidationAttestation {
    // ... existing fields unchanged ...
    /// content_hash of the validator's own valichord_attestation bundle for this
    /// reproduction — SHA-256 over the bundle's canonical (JCS) content, excluding
    /// the `meta` provenance block, so two validators who genuinely produced the
    /// same per-sample outputs commit to the same value even if timestamps differ.
    ///
    /// Bound into commitment_hash automatically via commitment_msgpack_bytes().
    #[serde(default)]
    pub reproduction_bundle_hash: Option<Vec<u8>>,
}
```

`Option` + `#[serde(default)]` matches the existing `commitment_anchor_hash` precedent and keeps
deserialisation of older entries working.

**Use `content_hash`, not `bundle_hash`.** `bundle_hash` covers `Bundle.meta` (provenance,
timestamps), so two honest validators would never match. `content_hash` is the "same outputs?"
question, which is the one being asked.

### 2. `validator_workspace` — carry it through

`ValidatorPrivateAttestation` gains the same field, and the destructure at
`validator_workspace_coordinator/src/lib.rs:96-107` gains the binding. Mechanical; the compiler
finds every site.

### 3. Integrity zomes — validate shape only

In the `CreateEntry` arm for `ValidationAttestation`, mirror the existing
`CommitmentAnchor.commitment_hash` check:

```rust
if let Some(h) = &att.reproduction_bundle_hash {
    if h.len() != 32 { return Invalid("reproduction_bundle_hash must be 32 bytes (SHA-256)") }
}
```

⚠️ **Do not attempt to validate the bundle itself in `validate()`.** The bundle is off-DHT; the
integrity zome cannot fetch it and must stay deterministic. Shape only.

### 4. Coordinator surface

`seal_private_attestation` accepts the hash from the caller. The validator computes it from
their own bundle before sealing — the CORE-Bench runner already produces bundles
(`core_bench_runner.py --emit-bundles`), so the value exists at the right moment.

---

## What this buys, stated narrowly

**Buys:** a validator cannot reveal a bundle other than the one they committed to. "Reproduced"
becomes a claim about a *specific set of per-sample outputs* rather than a bare label. Combined
with the existing challenge-response scheme (`challenge.py` / `response.py`), a third party can
then demand Merkle proofs for randomly-chosen samples from *that* bundle, and the validator
cannot substitute a more convenient one.

**Does not buy:**
- Proof the bundle came from a real run. That is the bundle's own faithfulness property, not
  this binding.
- Protection against a validator who genuinely computes a wrong result. Same limit as the rest
  of commit-reveal: it is anti-copying and anti-fabrication, not anti-error.
- Anything about *correlated* validators producing the same wrong bundle — see the AIAF
  proposal; that is a different and open question.

---

## Test plan (write before the code)

The repo's standing rule applies: **prove the check can fail before trusting that it passes.**

1. **Negative control first.** A test where the validator commits bundle hash A and reveals with
   bundle hash B must FAIL the existing commitment verification. Run it against today's code
   first — it will pass wrongly, because nothing is bound yet. That is the baseline that proves
   the test is wired to something real.
2. Same-bundle round still succeeds (no regression to the happy path).
3. `None` (legacy / no bundle) still succeeds — the field is optional by design.
4. Shape rejection: a 31-byte hash is `Invalid`, asserting on the **specific guard message**,
   never a bare `is_err()`.
5. Re-run the immutability tripwires — `ValidationAttestation` is a guarded type and this
   touches its entry definition.

---

## Estimate

Half a day, most of it tests. The protocol change is one field; the leverage comes from
`commitment_msgpack_bytes()` already being the shared seam.

## Open question for Cüneyt

Pattern 13 frames this as ours to build. Worth asking whether he wants the bundle hash surfaced
in the PRML manifest alongside `attestation_uri` — if the pattern's step 7 ("bind to PRML and
re-lock") also carried the per-validator bundle hashes, the whole chain would be checkable from
the manifest alone rather than requiring a DHT read.
