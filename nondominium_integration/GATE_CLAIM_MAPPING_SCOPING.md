# ValiChord × Nondominium — What Gets Committed at the Gate (Scoping Note)

**Status:** Scoping / pre-design. Written 2026-06-16. Companion to `REVIEWER_SOURCING_SCOPING.md`.
**Scope:** The second of the two open design questions from the 2026-06-14/15 Discord agreement —
*what specifically gets committed and reproduced at the gate*, mapping the reference-fingerprint
claim and Nondominium's designer/reviewer roles onto ValiChord's commit-reveal data model.
**Reads alongside:** `NONDOMINIUM_ARCHITECTURE.md` (the capability-slot-link handoff this note feeds
into). A separate internal worked-example covers the general *whole-device* reproducibility case
(same sensor family, different claim).

---

## 1. Be precise about *which* claim is at the gate

Tiberius's gate authorises a `Prototype → Stable/Distributed` transition for a medical-device
resource on the basis of **technical (fabrication) validation**. Within that, ValiChord verifies
exactly **one** kind of claim — and it is *not* the whole device:

> **The reference-fingerprint claim:** *"This is the electrical response signature a genuine
> [MP3V5010DP] pressure sensor produces when pinged per the pinned procedure."*

This is the claim Pryderi scoped as ValiChord's real fit. It is what later feeds counterfeit
detection, but ValiChord verifies *establishing the reference*, not the detection method.

**Explicitly out of scope at this gate** (Pryderi's two limits, confirmed):
- **Whether the fingerprint discriminates genuine from counterfeit** — metrology / live R&D, not a
  reproducibility claim. ValiChord's layer doesn't touch it.
- **Firmware verification** — a straight hash check (matches or doesn't). No independent agreement
  needed to confirm a checksum; ValiChord would be overkill. Nondominium does this directly.

So the gate may invoke ValiChord for the *reference-fingerprint* sub-claim while handling the
firmware hash itself and treating the metrology question as separate evidence.

---

## 2. Role mapping (Nondominium → ValiChord)

| Nondominium role | ValiChord role | What they do at the gate |
|---|---|---|
| Resource **designer / originator** (creates the `NondominiumIdentity` / `EconomicResource`) | **Researcher** (claimant) | Deposits the reference-fingerprint claim + pinned ping procedure; commits it. |
| Technical **reviewers** (peer-review the fabrication claim; `AccountableAgent`+ / admitted reviewers) | **Validators** | Independently obtain genuine sensors, run the pinned ping, attest blind whether the signature reproduces. |
| **Governance zome** (governance-as-operator) | *consumer* of the `HarmonyRecord` | Reads the result via the capability slot and authorises the lifecycle transition. |

Two protocol modes fit, and the choice is a real design decision:

- **Claim-relative (as built — recommended for the gate).** The designer commits a reference
  profile as the researcher claim; reviewers reproduce *against it*; `AgreementLevel` is computed
  relative to the designer's revealed claim. Matches "designer proposes the reference, reviewers
  peer-review it." Uses the protocol exactly as it stands.
- **Leaderless convergence (Pryderi's stated natural endpoint).** No privileged first lab; all
  labs symmetric; the record certifies they converged on the same signature. This is closer to how
  a *canonical* reference would ultimately be established — but the protocol as built is
  researcher-claim-relative (it has a `ResearcherReveal` and agreement is claim-relative). True
  leaderless mode needs adaptation (no researcher claim; agreement computed among validators only)
  → Phase 1+, not the MVP gate. **Recommendation: ship claim-relative now, note leaderless as the
  maturity target.**

---

## 3. Data-model mapping (the core of this note)

What each protocol artifact carries, for the reference-fingerprint claim. Hashes and entry names
are ValiChord's as-built (see `NONDOMINIUM_ARCHITECTURE.md` for the entry definitions).

| ValiChord artifact | DNA | Here it holds |
|---|---|---|
| **`data_hash`** (`ExternalHash`, SHA-256) on `ValidationRequest` | 3 | Hash of the **deposited claim bundle**: the part number + lot/provenance of the genuine reference samples, the **pinned ping procedure** (stimulus, measurement points, conditions), the tolerance basis, and the reference signature spec. Pinning this up front is the crux (§4). |
| **`metrics`** (`Vec<MetricResult>`) in researcher `LockedResult` (private) | 1 | The designer's claimed **reference signature**: the characteristic response values (e.g. response at each stimulus point) that define "genuine". |
| **`ResearcherResultCommitment.result_commitment_hash`** = `SHA-256(msgpack(metrics) ‖ nonce)` | 3 | Published **before** any reviewer measures — binds the designer's reference claim without revealing it. |
| **`ResearcherReveal.metrics`** | 3 | The reference signature, revealed **after** all reviewers commit; coordinator verifies the hash. |
| **`ValidatorPrivateAttestation`** (`outcome`, `outcome_summary.key_metrics`, `confidence`, …) | 2 | Each reviewer's **own measured signature** + their `AttestationOutcome`, held private until reveal. |
| **`CommitmentAnchor.commitment_hash`** = `SHA-256(msgpack(ValidationAttestation) ‖ nonce)` | 3 | Each reviewer's sealed verdict — frozen and invisible to others (the blinding). |
| **`ValidationAttestation`** (the reveal) | 3 | `Reproduced` / `PartiallyReproduced` / `FailedToReproduce` / `UnableToAssess`, revealed simultaneously, hash-verified against the commitment. |
| **`HarmonyRecord`** (`outcome`, `agreement_level`, `participating_validators`, …) | 4 | The tamper-evident certificate: *"N independent labs reproduced the reference signature for `<part>` — `ExactMatch`/`WithinTolerance`."* |

**Critical constraint — the `HarmonyRecord` is outcome-level only.** It carries `outcome`,
`AgreementLevel`, the validator set, duration and discipline — **not** each lab's per-metric
numbers. The individual measured signatures live on DNA-3 `ValidationAttestation` reveals (publicly
fetchable), but they are *not* aggregated into the on-chain record. So the gate sees "they agreed,
at this level"; reconstructing the per-lab numeric panel is a separate read across the attestations.
(This matches the PEP Master finding: per-builder numerics don't survive into the `HarmonyRecord`.)

**Reused as-is:** the numeric tolerance + agreement machinery built for CORE-Bench (`match_value`,
tolerance pinned at commit, `derive_agreement_level` / `derive_majority_outcome`). The Holochain
layer is source-agnostic — it doesn't care the number came from an electrical ping rig.

---

## 4. The pinned-procedure crux

Blinding is meaningless unless the *method* is frozen before anyone measures. The deposited bundle
**must** contain a pinned ping procedure (stimulus waveform/levels, measurement points, environmental
conditions, the tolerance basis) hashed into `data_hash`. Otherwise reviewers measure different
things, or the tolerance is retrofitted to the results. This is the same discipline as a pinned
`test_protocol` block — including the unresolved **tolerance-basis** question (of-reading vs
of-full-scale materially changes the pass band; confirm with the device's actual spec before
fixing the bundle).

---

## 5. The gate handoff (after the HarmonyRecord exists)

Per `NONDOMINIUM_ARCHITECTURE.md` (custodian gate stays intact; no new governance-gated pathway):

1. ValiChord produces the `HarmonyRecord` (DNA 4).
2. The designer/custodian writes a **capability-slot link** on Nondominium's DHT: base =
   `EconomicResource` / `NondominiumIdentity` hash, target = `HarmonyRecord` `ActionHash`, tag =
   `{agreement_level, validator_count}` as compact msgpack. (`AgreementLevel` has no serde tag — it
   serialises as a plain string like `"ExactMatch"`, so Nondominium reads it without importing
   ValiChord types.)
3. Nondominium adds a `GovernanceRuleType::ExternalValidation` rule specifying the required slot
   type + consensus threshold for medical-device resources.
4. The custodian calls `update_lifecycle_stage()` (Prototype → Stable) / `update_resource_state()`
   (PendingValidation → Active); the governance rule **verifies the actual `HarmonyRecord`** before
   permitting the transition — it does **not** decide from the slot tag alone (see security note).
5. **The verification must read the real record, not just the researcher-written tag.** Nondominium
   calls `get_harmony_record_by_hash(ActionHash)` via `OtherCell` on a same-conductor ValiChord
   governance cell (both `Unrestricted`), then checks: (a) the record's *own* `agreement_level` +
   validator count meet threshold, and (b) the record's `request_ref` binds to **this** resource's
   deposited data. The slot tag is a fast pre-filter / display hint only.

> **Security note (do not gate on the tag alone — the central call-prep point).** The slot link and
> its tag are written by the **researcher** (the party with incentive to inflate the result), and
> NDO's link `validate()` cannot cross-fetch ValiChord's record at validation time (separate DHT
> networks, no network calls in validation). So a tag-only gate is forgeable two ways: (i) a tag that
> overstates the record it points at, and (ii) a target pointing at a real-but-unrelated good record
> from another study. **Closing this requires step 5's fetch + resource-binding check at decision
> time.** Principle: *sovereignty over **when** (custodian keeps the trigger), never over **what** the
> record says.* This closes the *forged-result* hole; the distinct *captured/fake-reviewer* hole is
> closed upstream by reviewer admission + independence (`REVIEWER_SOURCING_SCOPING.md`), not by this fetch.

The threshold in step 3 is **Nondominium's policy to set**, not a ValiChord constant — consistent
with treating validator-count/badge-tier as a per-domain parameter, not a fixed ladder (the 3/5/7
badge counts are illustrative placeholders, not statistically-derived thresholds).

---

## 6. Honest limits specific to this mapping

- **Schema gap — units / ambient / reference-instrument fields don't exist yet.** `ValidatorPrivateAttestation`
  / `OutcomeSummary` carry `key_metrics` but **no** units, environmental conditions, reference-instrument
  serial, or free-text note. A credible hardware round needs those (to let third parties check for
  correlated-error non-independence post-reveal). Adding them is an **integrity-zome change → changes
  the DNA hash → Phase 1 / Version B**, not a coordinator hot-swap. This is the single biggest
  protocol gap for the hardware gate.
- **Reproduced ≠ correct.** The record proves independent labs converged on the same signature — not
  that the signature is the *right* reference, nor that it discriminates counterfeits. That's the
  metrology question, deliberately out of scope (§1).
- **Reference-instrument / ping-rig trust is not certified by ValiChord.** If every lab's rig is
  miscalibrated the same way, you get agreement on a wrong signature. State the rig as the trust
  anchor ValiChord does not itself certify (a future overlay could require a calibration-cert attestation).
- **Independence is admission-orthogonal and not Sybil-proof.** Covered in the reviewer-sourcing note:
  commit-reveal stops peeking, not out-of-band collusion or one-actor-two-keys; `person_key` / Flowsta
  `IsSamePerson` is the (currently absent) cross-system dedupe.
- **Latency.** A hardware round takes days/weeks (source parts + measure), not seconds. The protocol
  tolerates async rounds (`force_finalize_round` exists) but the gate UX must expect it.
- **Component/lot substitution.** Reviewers measuring different lots of "genuine" parts may legitimately
  diverge. A `DeviationType` exists in the type system; whether a different lot counts as "the same
  reference" is the bundle author's policy call.

---

## 7. Open questions to put to Tiberius

1. **Claim-relative or leaderless?** For the MVP gate, is a designer/originator committing the
   reference profile acceptable (claim-relative, ships now), or does the medical-device case require
   the leaderless/symmetric mode from the outset (Phase 1+ protocol work)?
2. **Does the gate need the per-lab numeric panel, or is the outcome-level `HarmonyRecord` enough?**
   If the panel is required for the governance decision, that's a read-aggregation layer to build
   (the data is on the attestations; the record doesn't carry it).
3. **Which fields must each reviewer record?** If units + ambient + rig-serial are required (likely
   for medical-grade), that's the integrity-zome change in §6 — schedule it as Version B.
4. **What's the pinned tolerance basis** for the actual sensor and ping method (of-reading vs FSS), and
   who authors the pinned procedure — the designer, or Nondominium governance?
5. **Threshold + firmware split:** confirm the gate invokes ValiChord only for the reference-fingerprint
   sub-claim, with Nondominium doing the firmware hash check itself and treating metrology separately.

---

*Together with `REVIEWER_SOURCING_SCOPING.md`, this closes the two open design questions from the
Discord agreement: who validates (sourcing) and what they commit/reproduce (this note). Both are
pre-design scoping for Tiberius's build — neither is a now-action.*
