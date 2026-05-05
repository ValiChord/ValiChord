# Valichord Pilot Spec — First 10 Studies

**Domain:** AI safety & capability eval reproduction
**Author:** Drafted by Claude Opus 4.7, 2026-05-04
**Status:** Founder-approved domain pick; awaiting operational decisions flagged in §9

---

## 1. Mission of the pilot

Prove that Valichord can take a published AI eval claim — *"Model M scores X% on benchmark B"* — and produce an independently verified, public, tamper-evident judgment on whether that claim is reproducible, in under seven days, using AI validators operating without coordination.

The pilot succeeds when ten such studies are on chain with HarmonyRecords, at least one of which is a contested or failed reproduction. The pilot fails if it produces ten green ticks on uncontroversial claims — that proves nothing about the protocol's adversarial value.

## 2. Why this domain

Eval numbers are the load-bearing currency of the AI industry in 2026 — labs publish them, regulators cite them, customers procure on them, and almost nobody reproduces them. Every major model release ships with benchmark scores that other labs quietly fail to replicate; the gap between "claimed X% on SWE-bench" and "actually X% on SWE-bench" routinely runs five to fifteen points. The causes are mundane (prompt formatting, decoding parameters, harness bugs, contamination, API drift) but the result is that the most-cited numbers in AI are also the least audited.

Three properties make this domain a near-perfect fit for Valichord:

- **Computational.** Reproducing an eval is a deterministic-ish process you run on a machine, not a wet-lab experiment. AI validators (`demo/ai_validator.py`) can execute the work end-to-end.
- **Inherently independent.** Two validator instances on different cloud accounts running the same harness against the same model are genuinely independent in the sense the protocol cares about — there is no institutional affiliation to launder.
- **Commercial pull.** Labs, funders, regulators, and procurement teams will pay attention to a service that produces audited eval scores. There is no equivalent service today.

The strategic risk is that this is a politically charged space where Apollo, METR, MLCommons, and HELM already operate. Valichord's differentiator is *protocol-level independence with public attestation* — none of those orgs offers that today; they offer expert-org judgment, which is a different product.

## 3. What counts as a study

A study in this pilot is a claim of the form:

> *Model M, accessed via method A, achieves score S ± σ on benchmark B (version v) under conditions C.*

Concretely, a researcher submits an **eval bundle** containing:

| Field | Type | Notes |
|---|---|---|
| `model_id` | string | Canonical name + version (e.g. `claude-opus-4-7`, `gpt-5-2026-04`, `llama-4-405b-base`) |
| `model_access` | enum | `api` / `weights` / `hosted_endpoint` |
| `model_access_spec` | string | API endpoint URL or weight checksum (sha256 of safetensors) |
| `benchmark_id` | string | Canonical name (e.g. `swe-bench-verified`) |
| `benchmark_version` | string | Git commit or release tag of the benchmark repo |
| `harness_id` | string | `inspect_ai` / `lm-eval-harness` / `metr-task-standard` / custom |
| `harness_version` | string | Pinned version |
| `params` | object | temperature, top_p, max_tokens, sampling N, system prompt, scaffold |
| `claimed_score` | float | The headline number |
| `claimed_ci` | [float, float] | 95% confidence interval, if reported |
| `output_artefacts_hash` | sha256 | Hash of researcher's raw eval outputs (tamper-evidence) |
| `discipline` | enum | `AISafetyEval` (new discipline; see §10) |
| `notes` | string | Free text for known caveats |

The eval bundle is the `ResearcherResult` payload. Whatever the researcher signs off on at reveal time, this is the structure. Anything missing from this list either has to be reproducible to a known default or the bundle is rejected at submission.

**What is *not* a study:**
- A subjective judgment ("this model is safer")
- An ablation requiring custom training infrastructure validators don't have
- Anything that requires the validator to access proprietary weights they have no licence for
- Anything where the benchmark is private or paywalled — the benchmark must be runnable by an independent party

## 4. Validator selection

Per the existing protocol, AI validators are granted `CertificationTier` at join time by the issuer. For this pilot:

- **Pool size:** minimum 12 active validator nodes at pilot start. Below this, random selection plus per-study quorum (≥5) becomes brittle.
- **Tier mix:** start with all validators at `Standard` tier. Reserve `Advanced` and `Certified` for validators that complete five and fifteen studies respectively without disputes.
- **Capability filter:** each validator declares which `(harness_id, model_access)` pairs it can execute. Random selection draws only from validators capable of the study's bundle. This is a new field — see §10 implementation notes.
- **Compute provider diversity:** target at least three distinct compute providers across the pool (e.g. AWS, GCP, RunPod, Modal, bare-metal). Two validators on the same provider count as one for independence purposes during selection. (This is operational, not protocol-enforced — Phase 2 work to formalise.)
- **Quorum per study:** `num_validators_required = 5`. `min_attestations_for_finalization = 3` (allows a study to finalise even if two validators time out).

Issuers can warrant a validator that produces clearly broken reproductions (wrong harness invocation, output tampering). The existing warrant gating handles exclusion.

## 5. Reproduction protocol

For each claimed study, an assigned validator:

1. **Pulls the eval bundle.** Verifies the harness version, benchmark version, and model access method are accessible.
2. **Provisions environment.** Pinned harness, pinned benchmark commit, declared params. The reproduction script lives in `demo/ai_validator.py` (extension required — see §10).
3. **Executes.** Runs the benchmark against the declared model with declared params. Records:
   - Score achieved (`reproduced_score`)
   - 95% CI on the score
   - Wall-clock runtime
   - Total cost (USD, where applicable)
   - Hash of the validator's raw outputs (`reproduced_artefacts_hash`)
4. **Compares.** Computes agreement using the rule below.
5. **Commits.** Submits a `ValidationAttestation` with outcome, score, CI, and a structured `MethodologicalNote` on any deviations encountered (API timeouts, OOM, version drift).
6. **Reveals.** After phase gate, validator's commitment is opened.

**Agreement rule (initial):**

A validator's reproduction is in agreement with the claimed score if either:
- `|reproduced_score - claimed_score| ≤ 2 percentage points absolute`, OR
- The 95% CIs overlap.

Disagreement is recorded as one of:
- `Below` — reproduced score materially lower than claimed (most interesting case)
- `Above` — reproduced score materially higher than claimed (suggests claimed score under-reports the model's capability — also interesting)
- `Inconclusive` — reproduction failed for non-claim reasons (harness bug, API outage, OOM). Does not count toward Below/Above.

These are encoded as a new enum in shared_types — see §10.

## 6. Outcome taxonomy (badge meaning in this domain)

A HarmonyRecord in the AI-Safety-Eval discipline carries one of:

| Badge | Trigger | Public meaning |
|---|---|---|
| **Reproduced (Gold)** | ≥7 validators agree, 0 disagreements (Below or Above) | "Independent reproduction confirms this score" |
| **Reproduced (Silver)** | ≥5 validators agree, ≤1 disagreement | "Reproduction confirmed by majority" |
| **Reproduced (Bronze)** | ≥3 validators agree, no quorum for stronger badge | "Reproduction tentatively confirmed" |
| **PartialAgreement** | 3–4 agree, 2+ disagree, no `Inconclusive` majority | "Validators split on whether this score reproduces" |
| **FailedReproduction** | ≥3 validators report `Below` or `Above`, fewer than 3 in agreement | "Independent validators could not reproduce this score" |
| **InsufficientData** | Quorum mostly `Inconclusive` (harness/access failures) | "Reproduction was not technically possible — claim neither confirmed nor refuted" |

`InsufficientData` is the badge that prevents the protocol from punishing claims that legitimately can't be reproduced (e.g. closed-weight model that became inaccessible). It exists to keep the system honest about what it can and can't say.

## 7. The first 10 studies — concrete slate

The pilot is *not* "ten studies show up at random." It is a curated slate designed to stress the protocol and produce visible signal. Suggested distribution:

**Tier A — High-trust reproduction (4 studies).**
Claims by reputable labs on standard benchmarks where reproduction is expected to succeed. Purpose: prove the happy path works at scale.

- 1 × frontier API model on SWE-bench Verified
- 1 × frontier API model on GPQA-Diamond
- 1 × frontier API model on MATH-500
- 1 × open-weights model on MMLU-Pro

**Tier B — Likely-contested (3 studies).**
Claims known or suspected to be marginal — early-version benchmark numbers, vendor-published scores that other labs quietly disagree with, or scores where the harness is known to be sensitive. Purpose: prove the protocol catches errors and produces non-Gold badges.

- 2 × vendor-published headline scores you have reason to suspect
- 1 × an older claim that was already informally challenged

**Tier C — Methodological stress (2 studies).**
Studies designed to test specific protocol behaviours.

- 1 × a study deliberately seeded with a researcher mistake (wrong temperature in bundle vs published) — does the protocol catch it?
- 1 × a study where you expect `InsufficientData` (closed-weight model with limited access) — does the protocol degrade gracefully?

**Tier D — Anchor study (1 study).**
One high-profile study run with full operational support, intended for public communication. Pick a benchmark + model where the result is genuinely interesting regardless of which way it lands. This is your launch story.

Total: 10. The slate is designed so that if all ten land Reproduced (Gold), the pilot has *failed* — that would mean it only ran on softballs.

## 8. Success metrics

The pilot is judged on six numbers, set in advance to prevent post-hoc rationalisation:

| Metric | Target | Stretch |
|---|---|---|
| Studies reaching a HarmonyRecord (not timed out) | ≥7 of 10 | 10 of 10 |
| Median time from `submit_request` to HarmonyRecord | ≤7 days | ≤4 days |
| Studies producing a non-Gold outcome | ≥2 | ≥3 |
| Validator participation rate (claims completed / claims taken) | ≥80% | ≥95% |
| Protocol-level incidents (double commitment, sealed-but-unrevealed >24h, warrant disputes) | 0 critical, ≤3 minor | 0 minor |
| External engagement (citations, press mentions, lab inquiries) | ≥1 substantive contact | ≥3 |

A pilot that hits the targets but no stretch goals is a pass. A pilot that misses two or more targets is a learning, not a launch — fix and re-run before public communication.

## 9. Operational asks of you (founder)

These are the decisions and recruitment that only you can drive. Codespaces Claude can implement around them, but cannot make them.

**Decisions needed before pilot start:**

1. **Pick the four Tier A benchmarks.** I've suggested SWE-bench Verified, GPQA-Diamond, MATH-500, MMLU-Pro. Confirm or override.
2. **Pick the anchor study (Tier D).** This is the one external story. It needs to be a benchmark+model combination where Valichord saying "reproduced" or "not reproduced" is genuinely newsworthy.
3. **Pick the two Tier B "likely-contested" claims.** This is research work — reading recent eval discussions, finding scores that other labs have quietly disputed. I can help draft a shortlist if you want; you make the call.
4. **Decide who pays for compute.** Reproducing SWE-bench against a frontier API model costs in the low-thousands USD per validator per benchmark. Five validators × ten studies × variable cost = real money. Options: (a) Valichord-funded grant pool to validators, (b) submitter pays validator costs as part of submission fee, (c) validator volunteers cover their own costs (only viable if validators are funded labs). Option (a) is cleanest for the pilot; option (b) is the long-term model.
5. **Set the timeline.** Recommend: 6 weeks from "infrastructure ready" to "10 studies complete." Tighter than that and validators will rush; longer and momentum dies.

**Recruitment needed before pilot start:**

- 12 AI validator nodes (operators willing to run the validator stack on their compute).
- 3-5 anchor researcher-submitters — the people who will put forward the first studies. Mix of internal (you/team submitting on behalf of public claims) and external (a lab willing to put their own claim through).
- 1 advisory voice from the eval community (METR, Apollo, MLCommons, an academic eval lab) who will publicly say "this is interesting, we're watching." Not an endorsement — just a signal.

**Communication decisions:**

- When do you go public? Recommend: silent for first 3 studies, soft public on study 5 (one blog post, no press push), hard public on study 10 with the anchor study as the headline.
- What do public reports look like? A Valichord study page should show the eval bundle, every validator's score and methodological notes, the agreement matrix, and the badge. This is the artefact you're selling.

## 10. Implementation handoff to Codespaces Claude

This section is a brief for Sonnet 4.6 (or whoever picks this up). The pilot needs the following to ship.

**Protocol additions (shared_types + DNAs):**

- New `Discipline::AISafetyEval` variant. Inductive chain check in `attestation_integrity` extends naturally.
- New `EvalBundle` payload type for `ResearcherResult` content. Fields per §3 table. Validation: required fields present, hashes well-formed, params object schema-checked.
- New `EvalAgreement` enum on `ValidationAttestation`: `Agree | Below | Above | Inconclusive`.
- New `BadgeType::Reproduced { tier: BadgeTier }`, `BadgeType::PartialAgreement`, `BadgeType::FailedReproduction`, `BadgeType::InsufficientData`. Update `evaluate_badge_type()` in governance integrity to match the table in §6.
- New validator capability declaration: `validator_capabilities: Vec<(HarnessId, ModelAccessType)>` on `ValidatorProfile`. Selection in `get_validators_for_discipline` filters on capability.

**`demo/ai_validator.py` extensions:**

- Pluggable harness adapter: a trait/protocol with `prepare(bundle) -> env`, `run(env) -> RawOutputs`, `score(outputs) -> Score`. Implement adapters for `inspect_ai`, `lm-eval-harness`, `metr-task-standard`. Anything else is rejected at the capability filter.
- Agreement computation per §5 rule.
- Methodological note structuring — free text plus structured fields for known issues (`api_timeout_count`, `oom_count`, `version_drift_detected`).
- Cost reporting — validator records USD spent. Out-of-band aggregation; not on chain.

**UI additions (valichord-ui):**

- Public study page (`/study/<HarmonyRecord-hash>`) showing eval bundle, validator outcomes, agreement matrix, badge.
- Researcher submission form for `EvalBundle` with field-level validation.
- Validator dashboard surfaces capability declarations and per-study eligibility.

**Observability:**

- Per-study log of every state transition (submitted → claimed → committed → revealed → finalised) with timestamps. This is the data behind the "median time-to-finalisation" metric.
- Cost tracker per validator per study.

**Test coverage:**

- sweettest_integration test for AISafetyEval discipline end-to-end with a mocked harness.
- Test for each badge outcome (Reproduced Gold/Silver/Bronze, PartialAgreement, FailedReproduction, InsufficientData).
- Test that capability filter excludes validators who haven't declared the required harness.

## 11. Risks and open questions to flag during pilot

These are things to watch, not things to solve up front.

- **API model drift.** A claim that reproduces today may not reproduce in three months because the API model changed silently. Decide: do studies expire? Do they get re-validated periodically? Recommend: studies are timestamped; reproduction badge is "as of date X." No expiry in pilot.
- **Closed-weight access.** If a researcher claims a score on a model only they have access to, validators can't reproduce. Pilot policy: such claims get `InsufficientData` and the protocol does not pretend to validate them. Future work: cryptographic remote-attestation of inference runs.
- **Eval contamination.** If the benchmark is in the model's training data, reproduction confirms a *contaminated* score. The protocol cannot detect this; methodological notes can flag suspected contamination, but it is fundamentally a domain limitation. Document this prominently.
- **Validator collusion under low quorum.** With 5 validators required and 3 minimum, three colluding validators can fabricate a Reproduced (Bronze) badge. This is the documented Phase 2 cross-DNA validation gap. Pilot mitigates via random selection and provider diversity; don't claim cryptographic protection that doesn't exist yet.
- **Cost externality.** If validators pay their own compute, the pool will skew toward validators with budget — reducing independence. Resolve in §9 decision 4.

---

**End of spec.**

Codespaces Claude: implement against this. If anything is ambiguous, raise it as a question to the founder before guessing — this spec is meant to be precise where it matters and silent where founder judgment is needed.

---

## Appendix A — Funding-Constrained Variant ($0 Pilot)

**Added:** 2026-05-04
**Status:** Founder-approved revision. Supersedes the §7 study slate and §9 decision 4 (compute funding). All other sections of the spec remain in force.

### A.1 What changed and why

The original spec assumed a Valichord-funded validator grant pool and implicitly scoped the Tier A slate to frontier API models. Both assumptions require budget that doesn't exist at pilot start. This appendix replaces those assumptions with a zero-budget configuration that:

- Exercises the protocol end-to-end identically to the expensive version
- Produces independently citable output (HuggingFace Open LLM Leaderboard scores are real claims that genuinely don't get audited)
- Costs under $50 if validators bring their own hardware, under $200 if a few RunPod hours are needed
- Generates the credibility needed to pursue the funding paths in §A.4

The $0 pilot is not a downgrade. "Ten studies verified for under $50" is a stronger story for grant applications than "we spent $30k of someone else's money."

### A.2 Three constraints that define this variant

1. **Open-weights models only.** Llama 3.1 8B, Mistral 7B, Qwen 2.5 7B, Phi-3, Gemma 2 9B, and equivalents. These run on a consumer GPU (or slowly on CPU). No API key required; no per-token cost.
2. **Cheap benchmarks.** GSM8K, MMLU subsets, ARC-Challenge, HellaSwag, BBH subsets, WinoGrande. A full eval run on a 7B model takes minutes and pennies of electricity.
3. **Volunteer validators with own hardware.** AI safety students, hobbyists with home GPUs, academic groups with idle compute. Incentive is the validator badge and public attestation record. No payment. 12 such operators are reachable on Discord today.

### A.3 Revised study slate (replaces §7)

| Slot | Type | Suggested study | Expected outcome |
|---|---|---|---|
| A1 | Tier A — happy path | Mistral-7B-Instruct-v0.3 on GSM8K (HF leaderboard score) | Reproduced |
| A2 | Tier A — happy path | Llama-3.1-8B-Instruct on MMLU (HF leaderboard score) | Reproduced |
| A3 | Tier A — happy path | Qwen-2.5-7B-Instruct on ARC-Challenge | Reproduced |
| A4 | Tier A — happy path | Phi-3-mini-4k-instruct on HellaSwag | Reproduced |
| B1 | Tier B — contested | Open LLM Leaderboard score with known community dispute | Non-Gold expected |
| B2 | Tier B — contested | Older score suspected to be harness-sensitive | Non-Gold expected |
| C1 | Tier C — stress | Deliberate bundle error (wrong temperature param) | Protocol catches deviation |
| C2 | Tier C — stress | Model with limited access or deprecated checkpoint | InsufficientData |
| D  | Tier D — anchor | Most interesting open-weights discrepancy you can find | Either direction is newsworthy |
| X  | Spare | Held for opportunistic addition during pilot | — |

**Founder still selects:** B1, B2, and D. Sourcing strategy: scan the HuggingFace Open LLM Leaderboard discussions tab and the EleutherAI Discord for publicly-flagged score disputes. These exist and are easy to find.

### A.4 Validator model for this variant

No payment. No formal employment. Validators opt in by:

1. Joining the ValiChord validator Discord channel
2. Declaring their hardware capability (`harness_id` + GPU type + available VRAM)
3. Receiving a membrane proof (CertificationTier: Standard) from the issuer
4. Running the validator node software against assigned studies

The existing `ValidatorProfile.validator_capabilities` field (§10) handles capability-based routing. The only change from the funded model: `CompensationTier` is set to `Volunteer` (a new enum value — add to shared_types alongside the §10 changes).

Validator motivations in this pool: badge on a public attestation record, citation in any publications arising from the pilot, early contributor status if ValiChord raises funding later.

### A.5 Revised success metrics (replaces §8)

Same structure; compute cost target added; external engagement target adjusted.

| Metric | Target | Stretch |
|---|---|---|
| Studies reaching a HarmonyRecord | ≥7 of 10 | 10 of 10 |
| Median time to HarmonyRecord | ≤7 days | ≤4 days |
| Studies producing non-Gold outcome | ≥2 | ≥3 |
| Validator participation rate | ≥80% | ≥95% |
| Protocol-level incidents | 0 critical, ≤3 minor | 0 minor |
| Total compute cost (all validators combined) | <$200 | <$50 |
| External engagement | ≥1 HF / eval community citation | ≥1 academic/org inquiry |

### A.6 Funding pursuit checklist (run in parallel with pilot)

Pursue exactly two tracks simultaneously. Do not pursue all six — that is how applications become generic and fail.

**Recommended primary track: Anthropic Startup Credits**
- Application is light (a few paragraphs + link to repo)
- $5k–$25k in API credits; unlocks frontier-model Tier A studies immediately
- Profile match is near-perfect: open-source AI safety infrastructure, Holochain not crypto, reproducibility verification
- Apply now. Does not conflict with any other funding. No exclusivity.

**Recommended secondary track: one EA-aligned foundation grant**
- Open Philanthropy, Survival and Flourishing Fund, or Long Term Future Fund
- All three list "AI safety infrastructure" and "eval verification" as in-scope
- Typical range $20k–$200k; slower process (2–4 months)
- Apply once the $0 pilot has at least 3 completed HarmonyRecords — concrete results dramatically improve success rate
- SFF has the lightest application; start there

**Other paths (defer until after pilot):**

| Funder | Notes | When to approach |
|---|---|---|
| OpenAI / Google API credits | Same play as Anthropic credits, lower profile match | After Anthropic result |
| Protocol Labs Research | Decentralised infrastructure angle; Holochain is in scope | After pilot complete |
| Mozilla Builders / Open Source Program | Trust and verification framing | After pilot complete |
| Eval org sponsorship (METR, MLCommons) | Requires something to show; data from pilot is the pitch | Post-pilot, pre-frontier upgrade |

### A.7 Upgrade path to the funded pilot

The $0 pilot and the original spec are the same protocol. Once any of the §A.6 tracks produces funding:

1. Add frontier API model benchmarks to the slate without changing any protocol code
2. Move validators from Volunteer to compensated (update `CompensationTier`)
3. Raise `num_validators_required` from 5 toward 7 as the pool grows
4. The HarmonyRecords from the $0 pilot remain valid and publicly citable — the record of what the protocol did does not get superseded

The $0 pilot is not a prototype. It is the first ten entries in the permanent public record.
