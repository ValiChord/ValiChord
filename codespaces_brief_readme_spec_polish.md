# Codespaces Brief — README / Spec Polish (Positioning Only)

**Trigger:** External review (ChatGPT, after seeing the inspect_evals PR + Scott's response + the current README) flagged that the *cryptographic substance is right* but the *positioning undersells what's actually been built*. The README and spec describe v1 + v1.1 in low-claim language ("a bundle of hashes") rather than what the system actually delivers ("verifiable commitment scheme with probabilistic fraud detection").

**Status:** Pure documentation polish. No code changes. No protocol changes. No breaking changes.

**Target completion:** Single focused 30-minute Codespaces session.

---

## Context

The substance of v1 + v1.1 is genuinely strong:
- Canonical, deterministic encoding (RFC 8785) so the same run produces the same bytes
- Merkle commitment over per-sample outputs enabling selective disclosure
- Probabilistic challenge-response with verifier-controlled randomness
- Hard rule against silent defaults (so two failed extractions can't collide hashes)

But a reader landing on the repo cold sees the README opening with *"a bundle is a lightweight JSON document..."* — accurate but small. They miss the load-bearing technical content unless they read the full spec. That's a positioning gap, not a substance gap.

This brief fixes that with three targeted edits. The cryptographic protocol stays exactly as it is; only the framing changes.

---

## Three edits to make

### Edit 1 — README opening: lead with the strong claim

Replace the current `valichord_attestation/README.md` opening with framing that surfaces what the protocol actually delivers. Suggested text (adjust wording to match the existing tone, but the load-bearing content should be present):

> A lightweight verification layer for AI evaluation claims.
>
> The protocol provides a **verifiable commitment over an entire evaluation trace** — its summary metrics, its per-sample outputs, and the harness configuration that produced them — together with a **probabilistic challenge-response protocol** that lets a verifier confirm faithfulness of reported results without transferring the full log.
>
> The system enables:
> - **Selective disclosure** — the holder of the log can prove individual samples on demand without revealing the rest
> - **Bounded-confidence fraud detection** — the verifier picks random samples; the probability of catching a misreport grows with the number of samples requested
> - **Deterministic cross-implementation comparison** — RFC 8785 (JCS) canonical encoding means two implementations in different languages produce byte-identical bundles for the same input
>
> v1 ships the format spec, the Merkle commitment, and selective disclosure. v1.1 (already shipped) adds the probabilistic challenge-response. Future work extends this with hardware-attested execution and zero-knowledge faithfulness proofs.

This stays factually true to what's shipped, surfaces the technical depth, and frames the protocol as what it is rather than what it superficially looks like.

The existing "quickstart," "how a future adapter would be written," and "pointer to spec" sections below this opening can stay unchanged.

### Edit 2 — Add "verifiable statement vs attested claim" distinction

Add a short subsection to the README (after the strong-claim opening, before the quickstart). This addresses a real gap in how the bundle is positioned: in isolation, anyone can produce a valid bundle; the cryptographic non-repudiation comes from the bundle's eventual on-chain commitment via Valichord's Holochain DNAs.

Suggested text:

> ## Verifiable statement vs attested claim
>
> A bundle in isolation is a **verifiable statement**: any reader can confirm the bundle's internal consistency (the Merkle root commits to the per-sample outputs; the canonical encoding is deterministic; the challenge-response succeeds against a holder of the log). But anyone could have produced the bundle — there is no built-in identity layer in the format itself.
>
> When a bundle is committed on-chain through Valichord's Holochain DNAs (`validator_workspace`, `attestation`, `governance`), it becomes an **attested claim**: the commit is signed by the validator's Ed25519 keypair, recorded in their tamper-proof source chain, and witnessed by independent peers. At this point the bundle carries cryptographic non-repudiation: the validator cannot later deny they made the claim.
>
> The two layers are deliberately separable. The format is harness-agnostic and useful in contexts beyond Valichord's protocol. Within Valichord's protocol, the on-chain layer adds the identity and witnessing properties that the format alone deliberately doesn't carry.

This frames the format and the protocol cleanly without conflating them, and pre-empts the "anyone can write a bundle" critique that would otherwise look like a vulnerability.

### Edit 3 — Add "Limitations and trust boundaries" section to the spec

Add a new section to `valichord_attestation/spec/attestation_format_v1.md` (between Security Considerations and the end, or as an extension of Security Considerations). This names limits explicitly so a careful reader sees that they've been considered, not glossed.

Suggested content covering three points:

> ## Limitations and trust boundaries
>
> ### Adapter trust boundary
>
> The protocol commits to per-sample outputs that the adapter chooses to include. If a malicious adapter drops failed samples wholesale before constructing the bundle, the resulting Merkle root is honest about a smaller-than-real run. The challenge-response catches misreporting of committed samples, not omission of samples that should have been committed.
>
> Mitigations available at the protocol layer (outside the format itself):
> - The bundle commits `samples_total` (the declared sample count), which a verifier can check against external expectations of the benchmark size
> - In Valichord's federated protocol, multiple independent validators running the same eval should converge on the same `samples_total`; an adapter that systematically drops samples would diverge from honest validators
> - On-chain warrants can be issued against validators whose attestations are demonstrably inconsistent with peers'
>
> The format alone cannot solve this; the protocol layer mitigates it.
>
> ### Metric semantics vs metric faithfulness
>
> The bundle proves that the reported numerical metrics are faithful to the underlying run — not that two runs producing the same numbers are methodologically equivalent. Two evaluations producing `{"accuracy": 0.847}` may differ in prompt formatting, scaffold, decoding parameters, or system message, while still both being honest about their respective runs. The bundle's `harness_version` and `command` fields capture some of this context, but semantic equivalence across runs is a methodology problem, not a cryptographic one. Verifiers comparing bundles should treat numerical match as necessary but not sufficient evidence of methodological equivalence.
>
> ### Floating-point determinism
>
> RFC 8785 canonical encoding does not by itself guarantee cross-language determinism for floating-point numbers, since IEEE 754 representations and shortest-roundtrip serialisations can vary subtly across implementations. The format addresses this with mandatory pre-rounding rules: accuracy / probability / score-style metrics are pre-rounded to six decimal places before encoding; counts and sample totals are stored as integers; time durations are stored as integer milliseconds; `NaN`, `Infinity`, and subnormal values are explicitly rejected. Pre-rounding happens before the canonical encoder runs, not as part of it. Implementations that follow these rules produce byte-identical encodings across Python, JavaScript, Rust, and other JCS-compliant runtimes.

These are not weaknesses-to-hide; they are honest scope boundaries that demonstrate the design has been thought through.

---

## Out of scope — do not implement in this work

- **Any code changes.** This is documentation only. No new functions, no new modules, no behavioural changes.
- **Any spec changes that alter the protocol.** Field names, schemas, encoding rules, hashing rules — all unchanged.
- **Bumping `format_version`.** Documentation polish does not change the format.
- **Marketing language.** Stay precise. Phrases like "cryptographically guaranteed correctness," "zero-knowledge verification," or "first of its kind" are not warranted by what's shipped. The existing claims in v1 + v1.1 are accurate; surface them, don't inflate them.

---

## Acceptance criteria

- [ ] `valichord_attestation/README.md` opens with the strong-claim paragraph (or equivalent wording that surfaces verifiable commitment, probabilistic challenge-response, selective disclosure, and deterministic encoding)
- [ ] `valichord_attestation/README.md` includes the "verifiable statement vs attested claim" subsection
- [ ] `valichord_attestation/spec/attestation_format_v1.md` includes the new "Limitations and trust boundaries" section covering adapter trust, metric semantics vs faithfulness, and floating-point determinism
- [ ] No changes to any Python files
- [ ] No changes to test files
- [ ] No changes to bundle JSON schema, canonical encoding rules, or any cryptographic protocol detail
- [ ] All 138 existing tests still pass (verifying no accidental code changes)

---

## If anything is ambiguous

Two stylistic choices the founder might want to weigh in on:

- **Tone of the strong-claim opening.** The suggested text leans technical-but-accessible. A more clipped/punchy version is possible, as is a more academic version. Default to the suggested version unless the founder prefers a different register.
- **Where the "verifiable statement vs attested claim" subsection sits.** Could go in the README (suggested) or in the spec doc (alternative). Default to README — that's where readers landing cold will benefit most from the framing.

Both are taste calls, not protocol decisions.

---

## Strategic note

The point of this work is not to convince Scott or any specific reviewer. The point is that the *next* careful reader who lands on the repo — funder, eval-team engineer, AISI staffer, an academic considering an adapter — sees what's actually been built rather than what it superficially looks like. The cryptographic substance was already strong; this just makes it visible at the surface.

When this lands, the README and spec will accurately match what 138 tests at 100% coverage actually verify. That's the whole goal.
