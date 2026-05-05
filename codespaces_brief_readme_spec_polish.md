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

## Five edits to make

(The original three documentation edits below, plus two added after a second external review — see Edits 4 and 5.)

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

### Edit 4 — Add a "Threat model" section to the spec, including the metric ↔ sample linkage

This is the most substantive addition. Add a "Threat model" section to `attestation_format_v1.md` (immediately before "Limitations and trust boundaries"), spelling out attacker capabilities and what the protocol guarantees against each.

Suggested content:

> ## Threat model
>
> ### Attacker capabilities assumed
>
> An adversary constructing a bundle is assumed to control:
> - The harness execution environment (so they can fabricate per-sample outputs)
> - The adapter that translates harness output into a bundle (so they can omit, reorder, or alter samples before commitment)
> - The reported metric values in `raw_metrics`
>
> An adversary is **not** assumed to control:
> - The verifier's randomness (the verifier supplies a fresh nonce for each challenge)
> - The cryptographic hash function (SHA-256 collision resistance is assumed)
> - Out-of-band knowledge such as the expected total sample count for a known benchmark
>
> ### Attack surfaces and what the protocol catches
>
> **(a) Misreporting of committed sample contents.** If the adversary commits to a Merkle root and later, when challenged, reveals samples whose hashes do not reconstruct the root — the verifier detects the inconsistency directly via Merkle proof verification. *Always caught when challenged.*
>
> **(b) Fabrication of sample outputs.** If the adversary fabricates a fraction `f` of per-sample outputs (committing to fake samples consistent with their fake Merkle root), a verifier requesting `k` random samples catches at least one fake with probability `1 - (1-f)^k`. The verifier tunes `k` to the cheating fraction they want to detect (see sensitivity table in Section 6). *Catches with bounded probability that grows with k.*
>
> **(c) Metric misreporting (metric ↔ sample linkage).** The bundle separately commits to `raw_metrics` (the reported numbers) and `outputs_merkle_root` (the Merkle commitment over samples). An adversary could compute honest metrics from genuine samples and then attach those metrics to a different Merkle root, OR commit to honest samples and report different metrics. To detect this, **a verifier must recompute the metric from the disclosed samples and confirm it matches the reported metric in `raw_metrics`.** This recomputation is a verifier-side responsibility in v1.1; future versions may bundle the metric-derivation function into the bundle itself so the recomputation is automatic. *Caught only if the verifier performs metric recomputation on disclosed samples.*
>
> **(d) Sample omission.** If the adversary drops failed or inconvenient samples wholesale before constructing the bundle, the resulting Merkle root is honest about a smaller-than-real run. The bundle commits `samples_total` (the declared count); a verifier with out-of-band knowledge of the benchmark's true size can detect a discrepancy. In Valichord's federated protocol, multiple independent validators running the same eval should converge on the same `samples_total`, and divergence is itself a flag. *Caught only with external knowledge of expected sample count, or via federation.*
>
> ### Composition with the protocol layer
>
> The format alone provides (a), (b), and (c) — given an honest verifier and an honest log holder. It cannot fully address (d) without external context. Valichord's broader protocol — federation across independent validators, on-chain commit-reveal, warrants — addresses (d) by making divergent `samples_total` claims detectable across the validator pool.
>
> ### What the protocol does not claim
>
> - It does **not** provide zero-disclosure verification (verifying without any log access). The log holder must be available to respond to challenges; selective disclosure of challenged samples is required.
> - It does **not** provide absolute (rather than probabilistic) faithfulness verification under (b) and (c) without full sample disclosure.
> - It does **not** prevent collusion between adversaries who control both the bundle producer and the log holder of the same bundle.

This section is the substantive answer to *"what does this protocol actually guarantee?"* — written precisely enough that a careful reader can decide whether the guarantees are sufficient for their use case.

### Edit 5 — Add one concrete "why this matters" vignette to the README

After the strong-claim opening and the "verifiable statement vs attested claim" section, add a short concrete example so the abstract claims become tangible. Suggested text:

> ## Concrete example
>
> A lab publishes a benchmark result for a frontier model — say, *"87.2% on SWE-bench Verified"* — and constructs a bundle with the canonical metric, the harness configuration, and a Merkle commitment over the per-sample outputs. The lab does not need to share the underlying 4 GB of log files publicly.
>
> A third-party verifier (a journalist, a regulator, a competing lab) reads the bundle and wants to confirm the score is faithful. They generate a fresh challenge — *"reveal samples 17, 142, 391, 894, 1,205, ..."* — and the lab responds with those 50 samples plus their Merkle paths. The verifier checks each path against the bundle's commitment, and recomputes the headline metric from the disclosed samples to confirm it matches what the lab reported.
>
> If the lab fabricated even 5% of their results, the verifier's 50-sample challenge catches the fabrication with probability ≈92%. The verifier has confirmed faithfulness without ever downloading the full log; the lab has demonstrated their result without exposing per-sample data their privacy or competitive position requires they not publish wholesale.
>
> That tradeoff — *probabilistic faithfulness verification with selective disclosure* — is what the protocol is for.

This makes the protocol concrete in a way the abstract framing alone cannot.

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
- [ ] `valichord_attestation/README.md` includes the "Concrete example" vignette (Edit 5)
- [ ] `valichord_attestation/spec/attestation_format_v1.md` includes the new "Threat model" section (Edit 4) covering attacker capabilities, four attack surfaces (a)-(d), composition with the protocol layer, and explicit non-claims
- [ ] `valichord_attestation/spec/attestation_format_v1.md` includes the new "Limitations and trust boundaries" section covering adapter trust, metric semantics vs faithfulness, and floating-point determinism
- [ ] The Threat model and Limitations sections sit adjacent in the spec (Threat model first, Limitations second) so a reader sees them as a coherent pair
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
