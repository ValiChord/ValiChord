# Valichord — Issues Backlog (Draft)

This file collects 20 GitHub Issue drafts for the Valichord repo, organised in three sections:

- **Section A: Protocol & architecture** (8 issues) — Valichord's own unanswered architectural questions: identity, governance, deployment, cryptographic gaps. The deeper engagement surface; expects expertise from distributed-systems, cryptography, governance reviewers.
- **Section B: Integration & extensions** (9 issues) — adapter work, v1.2 protocol additions, future-direction research. The lower-bar engagement surface; concrete code work plus design questions tied to specific external systems.
- **Section C: Honourable mentions** (4 issues) — real questions worth raising eventually, but not in the first wave.

Each issue is ready to paste into GitHub. Body text is in a code block so the markdown is preserved verbatim.

## How to use this file

- Don't open all 20 at once. Stagger them — three or four this week, the rest over two to three weeks. Opening a Wishlist Dump on day one signals "scattered" rather than "considered."
- **Suggested staging order:** open Section B issues 1, 2, 3 first (concrete, lower bar). Then a wave from Section A (the architectural questions, which benefit from being opened against an active Issues tab rather than landing in an empty one). Then the Section A and B remainders. Honourable mentions are a second-month consideration, not first-week.
- Configure GitHub labels in the repo before opening any issues. Suggested labels appear in each issue body. Most useful: `expert-input-welcome`, `help-wanted`, `design`, `architecture`, `governance`, `cryptography`, `known-gap`, `v1.2`, `v2`, `good-first-issue`.
- Cross-link from the README's Roadmap section once issues are open. Discoverability compounds.
- Don't tag specific people (especially not Scott Simmons). Let readers self-select.
- Reply within 24-48 hours to any engagement. The signal value of issues collapses if they look unattended.

---

# Section A — Protocol & architecture

Eight issues about Valichord's own unresolved architectural questions. These attract the deeper kind of expert engagement.

## A1. Validator Ed25519 key rotation

**Title:** `Design: validator Ed25519 key rotation — handling past attestations after a rotation event`

**Body:**

```markdown
## Context

Each validator on the Valichord network operates with an Ed25519 keypair tied to their Holochain agent identity. Keys may need to rotate for legitimate reasons:

- Suspected compromise (machine breach, key leak)
- Operator handover (one team takes over a validator from another)
- Hardware lifecycle (HSM replaced, machine retired)
- Periodic rotation as security hygiene

The current protocol has no documented rotation procedure. This is fine while the network is small and pre-deployment, but once validators are operating real audits, an unplanned key rotation event is a serious incident with no playbook.

## Open questions

- **Past attestations after rotation.** When a validator rotates their key, do their pre-rotation attestations remain valid? They were signed with a key that is no longer authoritative. Cryptographically the signatures still verify against the old public key, but a verifier reading a HarmonyRecord may not know whether to trust an attestation signed by a now-rotated key.
- **Identity continuity.** Holochain agent identity is the public key. A new key = a new agent. Does a "rotated" validator effectively become a fresh validator that has to re-earn their CertificationTier? Or is there an identity-binding mechanism (cross-signed transition record) that lets the new key inherit the old one's standing?
- **Grace periods.** During a rotation, both old and new keys may need to be valid for a window. How is this represented in the protocol?
- **Detection of unsanctioned rotation.** A compromised key in adversary hands could "rotate" to a key the attacker controls. How does the network distinguish a legitimate rotation from a hostile one?

## Out of scope

- Holochain framework-level key rotation. This issue is about the application-layer semantics for Valichord's protocol; lower-level Holochain key handling is upstream concern.
- Key rotation for the issuer / system coordinator. That's a separate (also open) question — see [issuer rotation issue].

## What would help

Input from anyone who has designed or operated long-running validator networks (Tor relays, Certificate Authorities, blockchain validators, federated identity systems). Real-world rotation procedures from those communities are likely directly applicable.

Labels: `design`, `cryptography`, `governance`, `help-wanted`, `expert-input-welcome`
```

---

## A2. Validator key loss and recovery

**Title:** `Design: validator key loss and recovery — what happens when a private key is unrecoverable?`

**Body:**

```markdown
## Context

A validator may permanently lose their private key — disk failure, lost passphrase, deceased operator, etc. In Holochain's model, an agent's identity is their key; lose the key and you lose the identity. Past attestations remain on the DHT, signed by the lost key, valid forever — but the operator can no longer participate as that agent.

For a one-validator-per-operator model, this is mostly a personal inconvenience. For Valichord, where validators may have accumulated CertificationTier standing, reputation history, and ongoing study commitments, key loss is operationally significant.

## Open questions

- **No native recovery in Holochain.** There is no standard "I lost my key, please re-issue me a new one tied to my old identity" mechanism in Holochain. Recovery has to be an application-layer construction.
- **Social-recovery mechanisms.** Does the protocol need something like a guardian set (M-of-N other validators attest "this person was the key-holder behind that agent identity, here is their new key")? This is well-precedented in account-recovery designs but introduces governance complexity.
- **Identity continuity vs fresh start.** Is it acceptable to require a key-loss validator to re-onboard as a fresh agent, sacrificing accumulated standing? For low-friction operators this may be fine; for institutional validators it may be unacceptable.
- **Abuse vector.** Any recovery mechanism creates an abuse vector — an adversary claiming to be a legitimate operator who lost their key. How does the protocol resist this?

## Out of scope

- Hardware-security-module-level key escrow. Out of band; orthogonal to protocol design.
- Recovery of *researcher* identities (separate concern, see [researcher identity issue]).

## What would help

Account-recovery and social-recovery design experience — areas where this has been studied seriously include cryptocurrency wallet recovery (e.g., Argent's social recovery, Safe's threshold recovery), federated identity systems, and decentralised identity (DID method specs).

Labels: `design`, `cryptography`, `governance`, `help-wanted`, `expert-input-welcome`
```

---

## A3. Issuer key rotation and governance transition

**Title:** `Design: how does the CertificationTier issuer rotate, and how does the network handle issuer transitions?`

**Body:**

```markdown
## Context

Valichord's `CertificationTier` (Provisional → Standard → Advanced → Certified) is granted to AI validators by an *issuer* — currently represented in the protocol as the `system_coordinator_key`, baked into the DNA properties at deploy time. The DNA hash includes these properties, so changing the issuer means a new DNA hash, which means a new (incompatible) network.

This works for the demo and early deployment. It does not work long-term:

- The issuer keypair is a single point of failure. Compromise = entire network compromised.
- The issuer cannot rotate their key without forking the network.
- There is no mechanism for transferring issuer authority to a different operator (succession, organisational handover).
- There is no provision for *multiple* issuers, which the protocol may eventually need for jurisdictional or domain-specific specialisation.

## Open questions

- **Decoupling issuer identity from the DNA hash.** Should the issuer be referenced by some form of indirection (a registry, a trust list, a designated record) rather than baked into the DNA properties? This is more flexible but introduces a new trust surface.
- **Multi-issuer architecture.** Different issuers for different disciplines or jurisdictions — does the protocol support this natively, and how do conflicting attestations from different issuers compose?
- **Rotation procedure.** When an issuer rotates their key, what's the transition protocol? How do validators with credentials issued by the old key migrate to the new one?
- **Governance accountability.** Who can act as an issuer? Is this a free-for-all (any agent can issue), a permission list, or a single authority? Currently it's effectively a single authority by virtue of being in DNA properties.

## Out of scope

- Replacing the entire CertificationTier model with something else (e.g., reputation-based, stake-based). That's a much larger conversation.
- Governance of the *protocol* itself (issuance of new DNA versions). Related but distinct from issuer governance.

## What would help

Input from anyone who has worked on PKI design, certificate authority governance (Web PKI, ACME, Let's Encrypt's operational model), or DAO governance design. The trade-off space — flexibility vs trust concentration vs protocol complexity — is the heart of the question.

Labels: `design`, `governance`, `cryptography`, `help-wanted`, `expert-input-welcome`
```

---

## A4. CertificationTier population mechanism for AI validators

**Title:** `Open: the AI-validator CertificationTier progression mechanism is undefined in production`

**Body:**

```markdown
## Context

The protocol has four `CertificationTier` levels: Provisional, Standard, Advanced, Certified. For *human* validators, progression is round-based (placeholder thresholds: 3 rounds → Standard, 10 → Advanced, 25 → Certified).

For *AI* validators, progression was designed differently: the issuer grants tier at join time, and `_update_reputation_internal` exits early for `validator_type == AI`. In practice, however, the issuer logic is gated behind the `system_coordinator_key` check that no-ops in any non-demo deployment. The result:

- AI validators always remain at `Provisional` tier
- Badge thresholds (which count participants not certified validators) can be reached by any seven first-time validators
- A nominally "Gold" HarmonyRecord can be issued by validators with no track record

This is a documented gap in the project memory but has not been resolved.

## Open questions

- **What's the actual trust model?** AI validators were intended to be granted tier at join time by the issuer, presumably based on operator vetting (compute provider diversity, operator identity, deployment hygiene). The mechanism for "the issuer decides who deserves what tier" has not been specified.
- **What does "Standard" mean for an AI validator?** Round-count thresholds are appropriate for humans (skill develops with experience); for AI validators the question is more like "what is the operator's track record running this validator stack honestly?" That's not a round-count.
- **How does an AI validator's tier change over time?** If a validator behaves dishonestly (issues warrants for chain-integrity violations), should their tier degrade? Currently the warrant system excludes them entirely; tier degradation is finer-grained.
- **What's the relationship to economic stake?** Is tier granted partly based on bonded stake (validator puts up something at risk)? This raises a whole economic-model question (see [validator economic model issue]).

## Out of scope

- Changing the four-tier structure itself. Provisional/Standard/Advanced/Certified is fixed for now.
- Reputation-weighted badge thresholds. Project memory documents that this should NOT be added before the population mechanism is live.

## What would help

Input from anyone working on validator-network governance, sybil resistance, or reputation-based access control. Concrete examples from Tor relay tiers, Certificate Authority audit programs, or proof-of-stake validator certification are likely directly applicable.

Labels: `design`, `governance`, `known-gap`, `help-wanted`, `expert-input-welcome`
```

---

## A5. Validator economic model

**Title:** `Design: validator economic model — how does the submitter-pays mechanism actually work?`

**Body:**

```markdown
## Context

Valichord's long-term plan is a submitter-pays economic model: the researcher submitting a claim for verification pays the validators who reproduce it. This is sketched in the pilot spec but not specified at the protocol level.

The economic dimension matters because:

- Validators have real costs (compute, API budgets, operator time). Without compensation, the validator pool either depends on grants (current state) or skews toward funded labs (which compromises independence).
- Submitter-pays is the only path to a self-sustaining network without ongoing grant dependency.
- The mechanism has to be designed to resist gaming (collusion between submitter and a chosen subset of validators, sybil-validator capture, etc.).

## Open questions

- **Pricing.** Per-study? Per-sample? Per-compute-unit? Different evaluations have wildly different costs (full SWE-bench Verified frontier-API run vs Mistral-7B on GSM8K-100). How are prices set, and by whom?
- **Settlement.** Does the protocol settle on-chain (via Holochain primitives or a wrapped payment token), or off-chain (legal agreements between submitter and validator operator)? Each has trade-offs.
- **Validator selection vs payment.** Currently validator selection is random from a pool. With payment in the mix, do submitters get to influence selection (hire favoured validators)? If yes, independence weakens; if no, validators have no signal about which submitters are trustworthy.
- **Failed validations.** If a validator submits a faithful "FailedReproduction" attestation, do they still get paid? If yes, this is a critical incentive (validators must be paid to find errors, or no one finds errors). If no, no validator will ever find errors.
- **Sybil resistance.** A submitter who creates fake validators to "verify" their own claim cheaply must be made unprofitable.

## Out of scope

- Tokenomics in the cryptocurrency sense. Valichord is not a DeFi project; the economic model is about real money paying real operators.
- Detailed pricing for the pilot. The pilot is grant-funded; this issue is about the post-pilot sustainability mechanism.

## What would help

Input from mechanism designers, economists who have worked on decentralised marketplaces (Filecoin, The Graph, Helium, Arweave), and anyone who has operated audit/inspection businesses where the audited party pays the auditor (ISO certification, financial audit, PCI-DSS). Each of those has wrestled with the "auditee pays auditor" incentive problem.

Labels: `design`, `governance`, `economics`, `help-wanted`, `expert-input-welcome`
```

---

## A6. Validator pool diversity and sock-puppet detection

**Title:** `Design: protocol-level mitigations for sock-puppet validators and pool diversity gaming`

**Body:**

```markdown
## Context

The protocol's independence guarantee depends on validator pool diversity — the assumption that random selection of `n` validators from a pool of `N` returns `n` genuinely independent operators. This holds if `N` validators correspond to `N` distinct operators with diverse infrastructure. It breaks if:

- One operator runs multiple "validator" instances under different keys (sock-puppets)
- Many validators run on the same compute provider (low operational diversity even if keys are distinct)
- Operators collude to bias the selection by inflating the pool with their own nodes

The pilot spec mitigates this *operationally* (target 3+ distinct compute providers, hand-screened pool) but has no protocol-level enforcement. For long-term deployment, operational vetting doesn't scale.

## Open questions

- **Proof-of-distinct-infrastructure.** Can validators cryptographically prove they're running on infrastructure distinct from other validators? TEE-attested deployment plus public infrastructure-fingerprinting is one direction. Network-level diversity proofs (TCP/IP layer, AS path) are another.
- **Stake-based sybil resistance.** Requires bonded stake per validator, raising the cost of running N sock-puppets. Introduces an economic-model dependency (see [validator economic model issue]).
- **Behavioural sybil detection.** Validators that respond at suspiciously correlated times, with suspiciously similar internals, may be detectable as sock-puppets. Statistical detection rather than cryptographic prevention.
- **Issuer-level vetting.** The issuer (see [issuer governance issue]) could simply refuse to credential validators that fail diversity checks. Pushes the problem back to the issuer rather than solving it at the protocol level.

## Out of scope

- Replacing random selection with non-random selection. The randomness is a load-bearing security property.
- Solving sybil resistance entirely. No system has fully solved this; the question is making it expensive enough to be impractical.

## What would help

Input from sybil resistance research (proof-of-personhood, proof-of-stake, web-of-trust), distributed systems engineers who have operated validator networks, and security researchers familiar with TEE-based remote attestation.

Labels: `design`, `security`, `governance`, `help-wanted`, `expert-input-welcome`
```

---

## A7. Cross-DNA validation gap (Phase 2)

**Title:** `Open: cross-DNA validation gap — `validate()` cannot verify content across DNAs`

**Body:**

```markdown
## Context

In Holochain, `validate()` is deterministic and runs locally; it cannot make calls into other DNAs to verify content. This means a HarmonyRecord written in the `governance` DNA cannot have its `validate()` callback inspect the actual `ValidationAttestation` records in the `attestation` DNA that justify it.

The practical consequence: a colluding group of `≥ min_attestations_for_finalization` validators can fabricate a HarmonyRecord with arbitrary outcome and `agreement_level`, because no other peer running `validate()` on the HarmonyRecord can cross-verify it against the attestation DNA's contents.

This is acknowledged as a Phase 2 gap in the current architecture. Federation across independent validators is the operational backstop but is not cryptographic.

## Open questions

- **Inductive proof carrying.** Could the HarmonyRecord carry signed proof artefacts from the underlying attestations (e.g., a Merkle proof over the attestation set), such that `validate()` on the HarmonyRecord verifies the proof without cross-DNA calls? This is design-feasible but adds complexity to the attestation pipeline.
- **Bridging via deterministic relay.** Could a single deterministic-relay zome (or a constrained API) provide cross-DNA reads in `validate()` without breaking determinism? This pushes against Holochain's framework constraints; possibly a Holochain-upstream conversation.
- **Federation thresholds as a protocol-level claim.** Could the protocol explicitly cap how much trust a single HarmonyRecord can carry without cross-DNA validation, and require multi-HarmonyRecord aggregation for higher-trust claims?
- **Off-chain audit trails.** Independent third parties run scrapers that cross-check HarmonyRecords against their underlying attestations and publish discrepancy reports. Operational rather than protocol-level, but provides a real check.

## Out of scope

- Reimplementing the protocol on a non-Holochain substrate. The architecture is Holochain-native; this issue is about working within that frame.
- Replacing `validate()` with non-deterministic logic. That breaks core Holochain guarantees.

## What would help

Input from Holochain core developers (especially anyone who has thought about cross-DNA verification patterns), and from cryptographers familiar with proof-carrying data, recursive zk-SNARKs, or aggregate signature schemes.

Labels: `design`, `cryptography`, `architecture`, `known-gap`, `help-wanted`, `expert-input-welcome`
```

---

## A8. Production deployment: bootstrap and onboarding

**Title:** `Design: production deployment — bootstrap server architecture and validator onboarding flow`

**Body:**

```markdown
## Context

The current Valichord deployment model is the decentralised demo: five Docker containers (researcher, three validators, kitsune2 bootstrap server) running locally. Production deployment looks materially different.

Two unresolved questions:

**Bootstrap servers.** New nodes joining the network discover peers via a kitsune2 bootstrap server. The demo runs one. Production needs:
- Multiple bootstrap servers (single bootstrap = single point of failure)
- A trust model for bootstrap servers (a malicious bootstrap server can partition the network)
- A discovery mechanism (DNS records, well-known endpoints, hardcoded fallbacks?)

**Validator onboarding.** Today, becoming a validator requires manual Docker config, key generation, hAPP install, etc. For a real validator pool of dozens or hundreds of operators, this is too much friction. Production needs:
- A self-service installer or hosted onboarding service
- Membrane proof issuance flow (currently demo-mode bypasses real membrane proofs)
- Identity binding (proving the operator is who they say they are; ties into [issuer governance issue])
- Configuration validation before the validator joins (lest a misconfigured validator pollute the network)

## Open questions

- **Bootstrap server federation.** Multiple independent bootstrap servers run by independent operators? A formal-protocol way to find them?
- **Self-service onboarding without sacrificing vetting.** How does an automated installer reconcile with the issuer-vets-validators model?
- **Operational documentation expectations.** What level of "production runbook" does Valichord ship vs leaving to operators?
- **Geographic distribution.** Bootstrap servers across multiple regions? DHT propagation latency implications?

## Out of scope

- Hosted SaaS Valichord. The protocol is decentralised by design; a hosted version would defeat the purpose.
- Solving Holochain's general production-deployment story. Many of these are upstream concerns; this issue is specifically about Valichord's deployment patterns.

## What would help

Input from operators of decentralised networks (Tor relays, IPFS, libp2p, Holochain commercial deployments) and from anyone who has built validator-onboarding flows for proof-of-stake networks or federated systems. The trade-off between low onboarding friction and high vetting standards is well-trodden territory.

Labels: `design`, `deployment`, `operations`, `help-wanted`, `expert-input-welcome`
```

---

# Section B — Integration & extensions

Nine issues about adapter work, v1.2 protocol additions, and future-direction research. Lower bar to engagement; concrete code work plus design questions tied to specific external systems.

## B1. Verifier-side metric recomputation helper (v1.2)

**Title:** `v1.2: add verifier-side metric recomputation helper to detect metric ↔ sample linkage fraud`

**Body:**

```markdown
## Context

The current bundle (v1.1) commits separately to:
- `raw_metrics` (the reported numbers, e.g. `{"key": "accuracy", "value": 0.847}`)
- `outputs_merkle_root` (the Merkle commitment over per-sample outputs)

These commitments are not bound together. Threat model §10(c) in `attestation_format_v1.md` notes that an adversary could:
- Compute honest metrics from genuine samples, then attach those metrics to a different Merkle root, OR
- Commit to honest samples and report different metrics

The threat model says a verifier *must recompute the metric from disclosed samples* to detect this — but there's no library helper for it. The verifier currently has to know the metric definition and do the recomputation themselves.

## What the helper would do

A function (rough sketch):

```python
def recompute_metric(samples: list[dict], metric_key: str, derivation: Callable[[list[dict]], float]) -> float:
    ...
```

The verifier passes the disclosed samples (from a `ChallengeResponse`), the metric key they want to verify, and a derivation function appropriate to that metric (e.g. `mean(s["correct"] for s in samples)` for accuracy). The helper returns the recomputed value, which the verifier compares against `bundle.raw_metrics`.

## Open design questions

- Should the bundle itself include a reference to the metric-derivation function (e.g. a hash of the derivation code, or a named-derivation enum)? This would let `verify_response` automatically recompute, but it couples the bundle to a specific computation framework.
- For metrics that aren't simple aggregations (e.g. pass@k with sampling), how should the helper handle the more complex derivation?
- Where does this live — in `valichord_attestation/response.py`, or a new `metrics.py` module?

## Out of scope

- Bundling a full metric-derivation language (zk-style circuit definitions). v1.2 should stay simple: verifier supplies the derivation; library does the recomputation and comparison.

## References

- `valichord_attestation/spec/attestation_format_v1.md` §10 attack surface (c)

Labels: `enhancement`, `v1.2`, `help-wanted`
```

---

## B2. lm-evaluation-harness adapter

**Title:** `Adapter: lm-evaluation-harness output → Valichord attestation bundle`

**Body:**

```markdown
## Context

`valichord_attestation` currently has an `AdapterBase` abstract class plus one stub implementation (`InspectEvalsAdapter`). The next concrete adapter target is [`EleutherAI/lm-evaluation-harness`](https://github.com/EleutherAI/lm-evaluation-harness) — the most widely-used open eval harness.

The harness emits per-task results via `--output_path` and per-sample logs via `--log_samples`. An adapter would:

1. Read the harness output JSON
2. Extract the `results` block (model_id, task, metrics)
3. Read the per-sample output file (typically `<output_path>/samples_<task>_<datetime>.jsonl`)
4. Pass them to `valichord_attestation.builder.build_bundle()`

## Why it matters

lm-evaluation-harness is the dominant harness in academic AI safety / capability evaluation. An adapter unlocks Valichord verification for the largest pool of existing eval claims.

## Open design questions

- The harness output schema has shifted across versions. Pinning to a specific version (e.g., `lm-eval==0.5.0`) is the safe approach for v1; supporting multiple versions cleanly is harder. What's the right scope for the first adapter?
- Per-sample output format varies by task. Some tasks emit `{"doc_id", "target", "resps"}`; others have different shapes. Should the adapter normalise these into a canonical sample shape, or pass through raw?
- Some metrics (`acc_norm`, `exact_match`) are aggregations of per-sample correctness; others (`brier_score`, `pass@k`) require richer per-sample data. The adapter needs to handle both — open question how.
- Multi-task runs produce one harness output covering N tasks. Should the adapter produce one bundle per task or one bundle per harness invocation?

## Out of scope

- Modifications to `lm-evaluation-harness` itself. This is a thin one-way translator that lives in Valichord's repo and consumes harness output without modifying it.
- Coupling to `lm-eval` Python imports at runtime. Adapter should parse output files, not import `lm_eval` modules.

## Reference implementation hint

The synthetic example demo (`examples/mistral_7b_gsm8k_demo/build_bundle.py`) already does a basic version of this for GSM8K. A full adapter generalises that to handle arbitrary `lm-eval` tasks.

Labels: `enhancement`, `adapter`, `help-wanted`, `good-first-issue`
```

---

## B3. inspect_evals adapter (post-May-8 register transition)

**Title:** `Adapter: inspect_evals register entries → Valichord attestation bundle (post-May-8)`

**Body:**

```markdown
## Context

[`UKGovernmentBEIS/inspect_evals`](https://github.com/UKGovernmentBEIS/inspect_evals) is the UK AI Safety Institute's eval registry. As of 8 May 2026, the repo is transitioning from the legacy in-tree model (eval code lives inside inspect_evals) to a register model (eval metadata in `register/<eval>/eval.yaml` pointing at external eval code).

The structured `evaluation_report` block (PR #1575, merged 30 April 2026) defines the per-result metadata fields: `model`, `commit`, `command`, `metrics: list[{key, value}]`, etc. This is the canonical input shape a Valichord adapter would consume.

The `InspectEvalsAdapter` stub in `valichord_attestation/adapters/inspect_evals_stub.py` shows the intended field mapping but raises `NotImplementedError` pending upstream stabilisation.

## What this issue asks for

Once the May 8 register transition has settled (estimated 2-4 weeks of stabilisation), build a working adapter:

1. Read `register/<eval>/eval.yaml` for the `evaluation_report` block
2. Walk the linked external repo for the per-sample `.eval` log files
3. Produce a Valichord bundle via `build_bundle()`

## Open design questions

- The `evaluation_report` schema is marked `extra="allow"` in the upstream Pydantic model — eval-specific fields are permitted. Should the adapter pass these through (e.g., into bundle metadata) or strip them?
- `.eval` log files are ZIP archives. What's the right inclusion strategy: hash the entire archive (low value, per Scott's earlier critique), or unpack and Merkle-commit the per-sample outputs?
- Multiple `result` rows in a single report (different models, different runs) — one bundle per row, or one bundle per report?
- How should the adapter handle reports that lack per-sample logs (older entries, internal evals)? Likely: emit a partial bundle marked appropriately, or refuse.

## Out of scope

- Building this against the pre-May-8 in-tree shape. The transition is happening; build for the destination, not the legacy.
- Modifications to inspect_evals' upstream schema. Mirror field names; do not import their Pydantic models at runtime.

## References

- inspect_evals PR #1575: https://github.com/UKGovernmentBEIS/inspect_evals/pull/1575
- inspect_evals PR #1593 (worked example): https://github.com/UKGovernmentBEIS/inspect_evals/pull/1593
- Architectural feedback that prompted this design: https://github.com/UKGovernmentBEIS/inspect_evals/pull/1610

Labels: `enhancement`, `adapter`, `help-wanted`, `blocked: upstream-stabilisation`
```

---

## B4. TEE-based attestation for closed-weight verification (v2 design)

**Title:** `v2 design: TEE-based remote attestation for closed-weight model verification`

**Body:**

```markdown
## Context

The current protocol returns `InsufficientData` for closed-weight models that no validator can independently access. This is honest but unsatisfying — closed-weight model claims are exactly the case where independent verification matters most, and the protocol can't currently cover them.

A path forward: Trusted Execution Environment (TEE) — run the eval inside a hardware enclave (AWS Nitro Enclaves, Intel SGX, AMD SEV) that produces a remote attestation chain proving "this code ran here and produced this output." A verifier with the attestation knows the result is genuine without trusting the lab.

This shifts the trust assumption from *"trust the lab"* to *"trust the TEE manufacturer (Intel/AMD/AWS) plus the published code."* That's a much better trust model for adversarial settings.

## Design space to explore

- **TEE platform choice:** AWS Nitro Enclaves (mature, broadly accessible), Intel SGX (older, well-studied, narrowing application support), AMD SEV (newer, larger memory ceiling). Trade-offs: ecosystem maturity, attestation chain complexity, enclave size limits, cost.
- **Attestation chain integration with the bundle format:** does the TEE attestation document live inside the bundle (as an extension field), alongside it, or as a separately-published artifact? Versioning implications.
- **What runs inside the enclave:** just the inference, or also the harness scoring? Enclave size constraints may force a split.
- **Compatibility with existing federation:** does a TEE-attested study still need 7 validators, or does the TEE attestation reduce the required federation size?
- **Trust assumption documentation:** the spec needs to be honest about what "trust Intel" actually means as a security claim.

## Out of scope (for v2)

- Zero-knowledge proofs over inference. That's v3+ research; not what this issue is about.
- A fully-managed TEE service offering. v2 is a reference implementation pattern, not a SaaS.
- Replacing the existing federated multi-validator protocol. TEE is an additional path for the closed-weight case, not a replacement for the open-weight federated path.

## What would help

Engineers with TEE / Confidential Computing experience commenting on platform choice, attestation chain design, and the trust-model framing. Even rough notes on "AWS Nitro is probably easiest for v2" or "SGX is dying, don't use it" are valuable signal at this stage.

Labels: `design`, `v2`, `help-wanted`, `expert-input-welcome`
```

---

## B5. Eval contamination: protocol-level handling

**Title:** `How should the protocol handle suspected/known training-data contamination?`

**Body:**

```markdown
## Context

If a benchmark's data is in the model's training corpus, both the original lab and any independent validator will reproduce inflated scores. The protocol confirms a *contaminated* number — every validator agrees, the HarmonyRecord lands at Reproduced (Gold), and the verification machinery is technically working as designed while producing a misleading result.

This is a known hard problem in eval research. Detection of contamination is currently out-of-band (analysis of training data, perplexity tests on benchmark items, etc.) and is itself an active research area.

The protocol cannot fix contamination — but it could reasonably *flag* it. The question is how.

## Open design questions

- **Where does the flag live?** Options:
  - Bundle metadata field (`suspected_contamination: bool` with optional notes)
  - Separate "advisory" entry alongside HarmonyRecord (independent of validator agreement)
  - HarmonyRecord-level field (the protocol layer flags it, not the bundle)
- **Who flags it?**
  - The submitter (self-attested, weak)
  - Validators (during reproduction, may have different evidence than the submitter)
  - Third parties (after publication, retroactively)
- **What's the threshold?** "Known" contamination (benchmark data appears verbatim in training corpus) is unambiguous. "Suspected" contamination (statistical signals, perplexity anomalies) is fuzzier. How should the protocol distinguish?
- **What does it change?** Should contamination flags downgrade badge tiers, or just appear as advisory metadata? Different choices have different governance implications.

## Out of scope

- Building a contamination detection pipeline. That's a separate research project; this issue is purely about how Valichord *represents* contamination signals when they exist.
- Mandatory contamination checking. v1 is voluntary metadata; mandatory checks are a v2+ governance question.

## What would help

Input from anyone working on eval contamination (training-data analysis, perplexity-based detection, benchmark hygiene) on what flags would be most useful to surface in the protocol.

Labels: `design`, `governance`, `help-wanted`
```

---

## B6. Adapter trust boundary: protocol-level mitigations beyond federation

**Title:** `Strengthening the adapter trust boundary — protocol-level mitigations`

**Body:**

```markdown
## Context

The protocol commits to per-sample outputs that the *adapter* chooses to include. The challenge-response protocol catches misreporting of *committed* samples, but cannot catch:

- An adapter that drops failed samples wholesale before constructing the bundle
- An adapter that fabricates samples that never came from a real run
- An adapter that systematically biases its harness inputs

The current mitigations:
- The bundle commits `samples_total` (declared sample count); a verifier with out-of-band knowledge of the benchmark size detects discrepancy
- In the federated protocol, multiple independent validators running the same eval should converge on the same `samples_total`; divergence is itself a flag

Threat model §10 names this as the strongest remaining weakness. The federation backstop is real but operational, not cryptographic.

## Open question

Are there protocol-level (or adapter-level) mitigations that would strengthen this without requiring federation as the only line of defence?

## Possible directions

- **Adapter-side commitment registers.** Adapter logs every sample it considered (including ones it dropped) to a separate Merkle commitment, distinct from the included-samples Merkle root. Verifier can see "1000 considered, 950 included" with cryptographic auditability of which 50 were dropped and why.
- **Adapter signing keys.** A specific adapter implementation (e.g., a verified `lm-eval-harness adapter v0.1.0`) is signed by a known key; bundles that don't carry the adapter signature are flagged as "informal." Doesn't prevent all attacks but raises the bar.
- **Reproducibility receipts.** The adapter emits a deterministic transcript of its operation that can be re-executed against the same harness output to confirm bit-for-bit reproduction. Catches non-deterministic adapter behaviour.
- **Federated adapter consensus.** Multiple adapter implementations (different authors, different languages) consume the same harness output and produce bundles; verifier checks all bundles agree on `samples_total` and `outputs_merkle_root`.

None of these fully close the gap. All have implementation cost and trust-model trade-offs.

## What would help

Cryptographers and protocol designers commenting on which directions are worth pursuing, which are dead-ends, and whether there are options we haven't considered.

Labels: `design`, `security`, `help-wanted`, `expert-input-welcome`
```

---

## B7. Adaptive challenges: improving catch rate at lower k

**Title:** `Adaptive challenges — improving fraud catch rate without raising k`

**Body:**

```markdown
## Context

The current challenge-response protocol (`spec §6`) uses uniform random sample selection. The verifier picks `k` samples uniformly at random from `[0, samples_total)`. Catch probability for fabrication fraction `f` is `1 - (1-f)^k`.

This is a strong baseline but treats all samples symmetrically. In some settings, **adaptive challenges** — verifier chooses challenged samples based on prior responses or external signals — could improve catch rate significantly without raising `k`.

## Examples of adaptive strategies

- **Hot-spot challenging.** External signals (samples where the lab's claimed output differs from a baseline's expected output, samples on which other validators disagree) inform which indices to challenge.
- **Multi-round challenges.** Verifier issues `k₁` initial challenges, observes responses, then issues `k₂` follow-up challenges concentrated on patterns that look suspicious.
- **Stratified sampling.** Verifier challenges samples stratified by some property (difficulty, length, output structure) rather than uniform random.

## Open design questions

- **Game-theoretic analysis.** With adaptive challenges, the holder's optimal strategy might change. If the holder anticipates non-uniform challenges, do they fabricate differently? Does adaptive challenging actually improve catch rate against an adaptive adversary, or does it just shift the adversary's strategy?
- **Reproducibility of challenges.** Uniform random with verifier-supplied nonce is deterministic and auditable. Adaptive challenges depend on signals that may not be reproducible — does this weaken the protocol's "verifier-controlled randomness" property?
- **Composition with selective disclosure.** Selective disclosure (§5) lets the holder prove samples on demand. Adaptive challenges introduce a verifier-led mode that the protocol doesn't currently support cleanly.
- **Spec implications.** Does this need a new protocol section, or does it slot into §6 as a variant?

## Why this matters

For high-stakes audits (regulatory verification, large procurement decisions), even modest improvements in catch rate at lower `k` could materially reduce the cost of audit. `k=20` adaptive might catch fraud that `k=60` uniform misses.

## What would help

Cryptographers, game theorists, statisticians weighing in on whether adaptive challenges are worth the protocol complexity, and if so, which strategies are most defensible.

Labels: `design`, `research-direction`, `help-wanted`, `expert-input-welcome`
```

---

## B8. API drift in HarmonyRecords: time-of-test references

**Title:** `How should HarmonyRecords reference time-of-test API state for closed-weight models?`

**Body:**

```markdown
## Context

A HarmonyRecord might say *"Claude Sonnet 4.5 scored 87.2% on SWE-bench Verified, May 2026."* But what does this mean if:

- The lab silently updates the API model in June 2026 with the same `model_id`?
- A future researcher tries to reproduce the score via the API and gets a different result?
- The original API is deprecated entirely?

The protocol can pin `harness_version`, `repo_commit`, and `command` — but for closed-weight API models, the underlying model state is not directly hashable or pinnable. There's no canonical "model commit" for a closed API.

This is a real reproducibility limit. It's not unique to Valichord; it's a fundamental issue in eval research. But the protocol's HarmonyRecords are time-stamped artefacts, and someone reading one in 2027 needs to understand what the score actually meant.

## Open design questions

- **Time-of-test fields.** Should bundles include a `tested_at: timestamp` field? An `api_endpoint_url`? An optional `provider_attestation` (a screenshot, a signed receipt, etc.)?
- **API-state proxies.** Are there proxies that approximate "the model state at time-of-test"? E.g., a bundle of test prompts run against the API at the time, whose responses fingerprint the model? This is a known technique.
- **HarmonyRecord lifecycle.** Does the HarmonyRecord remain "valid" forever, or does it have an implicit decay ("verified May 2026; reproducibility against the live API not guaranteed after June 2026")?
- **Re-validation.** Should the protocol support re-running a study against the current API state and producing a "currency check" output?

## Out of scope

- Pinning closed-weight model state cryptographically. This requires lab cooperation (signed model checkpoints) that doesn't exist today.
- Reproducing the model behind an API without API access. Out of scope for any verification protocol that doesn't have model weights.

## What would help

Anyone working on eval reproducibility commenting on what's actually tractable here, and how existing eval communities handle this. Specific input from MLCommons, METR, HELM teams welcome.

Labels: `design`, `governance`, `help-wanted`, `expert-input-welcome`
```

---

## B9. Native multi-dimensional metric representation in the bundle schema

**Title:** `Design: should Metric carry an optional dimension field for hierarchical scoring structures?`

**Body:**

```markdown
## Context
inspect_ai's scorer system supports multi-dimensional scoring via nested metric structures. From `inspect_evals/agentdojo/scorer.py`:
```python
@scorer(metrics=[{"utility": [accuracy(), stderr()], "security": [accuracy(), stderr()]}])
```
A single run produces four headline numbers (utility-accuracy, utility-stderr, security-accuracy, security-stderr). Per-sample scores are themselves dicts: {"utility": "C" or "I", "security": "C" or "I"}.

Valichord's v1.2 raw_metrics schema is flat: list[{key, value, stderr, filter, metadata}]. Multi-dimensional outputs can be represented via naming convention — utility_accuracy, security_accuracy, etc. — but the dimension structure is encoded in the key string rather than as native schema.

This issue documents the open question of whether the bundle schema should add an optional dimension field to Metric to natively represent the inspect_ai structure 1:1.

What v1.2 supports today (works, via convention)
"raw_metrics": [
  {"key": "utility_accuracy", "value": 0.75, "stderr": 0.04},
  {"key": "security_accuracy", "value": 0.30, "stderr": 0.05}
]
The flat representation works. Cryptographic verification is unaffected. Adapters from inspect_ai output can produce this shape today.

What a native representation might look like (v1.3 candidate)
"raw_metrics": [
  {"key": "accuracy", "dimension": "utility", "value": 0.75, "stderr": 0.04},
  {"key": "accuracy", "dimension": "security", "value": 0.30, "stderr": 0.05}
```

---

# Section C — Honourable mentions

Four issues worth raising eventually but not in the first wave. Hold these until the first 16 have had time to attract engagement.

## C1. Long-term DHT growth and pruning policy

**Title:** `Design: long-term DHT growth — retention, archival, and pruning policies`

**Body:**

```markdown
## Context

Holochain's DHT replicates data across peers. Over time, Valichord's network accumulates HarmonyRecords, ValidationAttestations, study claim records, agent activity, and link metadata. With sustained operation, storage grows monotonically.

For a small demo this is fine. For a network handling thousands of studies per year over multiple years, retention policy matters — both for individual node operators (who pay for the storage) and for network health (very old data may be needed rarely but must remain accessible).

## Open questions

- **What's worth keeping forever?** HarmonyRecords are public attestations of historical claims; arguably they should be permanent. ValidationAttestations may be reasonable to keep; intermediate study-claim metadata less so.
- **Pruning vs archival.** Are old records pruned (deleted) or archived (moved to cold storage with on-demand retrieval)? The latter requires designing a cold-storage protocol that doesn't exist in stock Holochain.
- **Per-node retention.** Holochain peers replicate based on their proximity in the address space. Operators of small nodes may want to opt out of replicating very old records; how does this compose with the protocol's availability guarantees?
- **Operator economics.** Storage cost compounds. Does the validator economic model (see [Issue A5]) need to account for long-term storage?

## Out of scope

- Modifying Holochain's storage layer itself. This is application-layer policy.
- Replacing the DHT with a different storage substrate.

Labels: `design`, `operations`, `architecture`, `help-wanted`
```

---

## C2. Researcher identity continuity

**Title:** `Design: researcher identity continuity across institutional or operational changes`

**Body:**

```markdown
## Context

Researchers submit eval claims under a Holochain agent identity (Ed25519 keypair). In real-world settings, researchers move institutions, retire, or hand projects to successors. The current protocol has no mechanism for binding a new agent identity to a previous researcher's submission history.

Concrete scenarios:

- A researcher at Lab A submits a claim, then moves to Lab B. New work at Lab B uses a new agent identity. Their previous submissions are orphaned from their current activity.
- A research group's principal investigator changes; the new PI inherits ongoing claims but cannot sign as the previous PI.
- A researcher account is decommissioned (retirement, departure); claims it submitted remain on the DHT but cannot be amended or contextualised.

## Open questions

- **Identity continuity proofs.** Can a researcher cryptographically attest "I am the new identity behind the previous identity X"? This is similar to validator key recovery (see [Issue A2]) but for researchers, with different abuse-vector considerations.
- **Institutional vs individual identity.** Should claims be associated with an institution (which can outlast individuals) or with individuals (which is what currently happens)? Or both?
- **Verifier-side context.** A verifier reading a 2026 claim in 2030 may want to know "is the researcher still at this institution? are they still verifying the claim?" The protocol currently provides no mechanism for this.

## Out of scope

- Building a researcher reputation system (separate, larger conversation).
- Replacing the agent-as-public-key model.

Labels: `design`, `governance`, `identity`, `help-wanted`
```

---

## C3. Post-quantum cryptographic agility

**Title:** `Design: post-quantum cryptographic agility — when and how does the protocol upgrade its primitives?`

**Body:**

```markdown
## Context

Valichord uses Ed25519 signatures (per Holochain) and SHA-256 hashing (in `valichord_attestation`). Both are vulnerable to large-scale quantum computers; widespread quantum-cryptanalytic capability is not imminent but is on a decade-scale horizon.

The migration story for cryptographic suites is non-trivial: any change to signature or hash algorithms invalidates existing signatures and hashes (or requires backward-compatibility translation). Cryptographic protocols that don't plan for agility tend to face painful forced migrations later.

## Open questions

- **What's the migration path for Ed25519?** Holochain's choice. When Holochain moves to post-quantum signatures, Valichord follows, but the question is whether Valichord should design ahead for cryptographic agility independently.
- **What's the migration path for SHA-256?** The bundle's content-addressing depends on it. If SHA-256 needs replacement, how do existing bundles remain verifiable?
- **Hybrid signatures.** Some post-quantum migrations use hybrid signatures (classical + post-quantum) so verification remains valid against either side. Is this worth designing in now, or premature?
- **Versioning posture.** Should the bundle format version explicitly carry a cryptographic-suite identifier so future versions can be cleanly distinguished?

## Out of scope

- Implementing post-quantum cryptography now. Premature.
- Migration planning for Holochain itself (upstream concern).

Labels: `design`, `cryptography`, `long-term`, `help-wanted`
```

---

## C4. Multi-network federation

**Title:** `Design: federating multiple Valichord networks (e.g., regulatory vs academic deployments)`

**Body:**

```markdown
## Context

Different organisations or jurisdictions may want to operate their own Valichord network — for example, AISI runs a network for regulatory-grade audits, an academic consortium runs one for research reproducibility, a private consortium runs one for commercial procurement.

Each network has its own DNA hash (different membrane proofs, different issuer keys, different validator pools). They cannot directly interoperate today.

If a HarmonyRecord on the academic network attests an eval result, can the AISI network reference it? Should validators on one network ever participate in another? How are claims that bridge multiple networks represented?

## Open questions

- **Bridge protocols.** What does it mean for HarmonyRecord X on Network A to be referenced from Network B? Cross-DHT links are a real Holochain capability but require careful protocol design.
- **Trust composition.** A claim verified on Network A might not satisfy Network B's validator standards. How do networks express their differing trust requirements without requiring a shared global trust authority?
- **Validator participation across networks.** Can a validator be a member of multiple Valichord networks simultaneously? What does that mean for their identity, reputation, and economic model?
- **Discovery.** How does a verifier discover which networks exist, what they verify, and how to query them?

## Out of scope

- A single global Valichord network. The point of federation is precisely that different networks have different governance and standards.
- Cryptographic bridges between Valichord and unrelated systems (other verification protocols, blockchains).

Labels: `design`, `governance`, `architecture`, `long-term`, `help-wanted`
```

---

# Closing notes

**Total: 21 issues.** 8 architectural + 9 integration + 4 honourable mentions.

**Strategic intent:** these issues convert "questions inside the founder's head" into "public artefacts that experts can engage with." Done well, the Issues tab becomes a recruitment surface for advisors, contributors, and (eventually) team members. The framing throughout — *"open questions," "what would help," "input welcome"* — is the recruitment surface, not the issue text itself.

**Don't:**
- Open all 20 in one week (looks like wishlist-dumping)
- Tag specific people, especially Scott Simmons
- Frame issues as ready-made specs awaiting a contractor
- Let issues sit without engagement after opening — reply within 24-48 hours

**Do:**
- Stage over 2-3 weeks
- Configure GitHub labels first
- Cross-link from the README's Roadmap section
- Reply substantively when anyone engages
- Treat each issue as a public commitment to take its question seriously
