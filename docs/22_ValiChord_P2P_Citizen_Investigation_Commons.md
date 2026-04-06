# ValiChord and the P2P Citizen Investigation Commons

**Context:** Tiberius Brastaviceanu (Sensorica / Nondominium) proposed a commons-based P2P citizen investigation stack and asked whether ValiChord could be relevant. This document records the analysis.

---

## Short answer

Yes — and the fit is more precise than "could be useful." ValiChord is the **validation layer** the proposed stack describes. The blind commit-reveal protocol solves the exact problem independent investigative review requires: reviewers must not be able to see each other's assessments before sealing their own. Without that guarantee, the first validator who posts a conclusion anchors everyone else's reading. With it, the `HarmonyRecord` is a tamper-evident record that N independent investigators, working from the same evidence, reached the same conclusion — without coordinating.

---

## Where ValiChord directly fits

The PDF asks explicitly: *"Can ValiChord be relevant for this?"* — in the section on **Review as first-class labour**:

> Validation work is structurally privileged: Reproducibility checks, Source tracing, Bias detection, Method critique

That is ValiChord's exact purpose.

The PDF's epistemic humility principle — *"no 'final report' fetish, narratives are provisional snapshots"* — also maps cleanly. ValiChord's outcome is explicitly procedural: *"reproduced"* means an independent party arrived at the same result, not that the result is correct. A study can be reproducible and scientifically wrong. A claim can be corroborated and still contestable. ValiChord only answers the corroboration question, never the truth question.

---

## The conceptual extension required

ValiChord is currently built for **code + data reproducibility**: a researcher deposits a ZIP, validators run it, the `HarmonyRecord` records whether the same numbers came out. Investigative evidence is heterogeneous — documents, financial records, OSINT, interview transcripts.

The protocol generalises, but three things need extending:

### 1. What gets hashed into `data_hash`

Currently an IPFS/SHA-256 hash of a dataset ZIP. For investigations this would be a CID of an evidence bundle — IPFS content-addressing already produces a hash of the same form. `ValidationRequest.data_hash` is an `ExternalHash` (a 39-byte Holochain HoloHash wrapping any external hash), so it already accommodates IPFS CIDs without a schema change.

### 2. What `AttestationOutcome` means

Currently: `Reproduced / PartiallyReproduced / FailedToReproduce / UnableToAssess`. For investigative corroboration you would want: `Corroborated / PartiallyCorroborated / Contradicted / UnableToAssess`. The struct is identical — it is a vocabulary change, not a structural one. This could be handled as a new `Discipline::InvestigativeJournalism` variant with domain-specific outcome semantics, without touching the core protocol.

### 3. Membrane proofs vs pseudonymous identity

ValiChord's Attestation DNA currently requires an Ed25519 institutional credential from a designated issuer (`authorized_joining_certificate_issuer` in DNA properties). The P2P investigation stack requires pseudonymous cryptographic identities. These are in tension.

The resolution already exists in the codebase: **empty issuer = dev/test bypass** (the membrane proof check is skipped entirely). For an investigation commons you would either:

- **(a)** Use a pseudonymous credential issuer whose job is only to prevent Sybil attacks without linking to real-world identity, or
- **(b)** Deploy with the bypass and rely on Nondominium's `zome_person` + Flowsta Vault for identity continuity.

This is exactly Decision 2 from `nondominium_integration/README.md` — it applies here too.

---

## How ValiChord fits the full proposed stack

| PDF layer | Proposed component | ValiChord role |
|---|---|---|
| Storage / persistence | IPFS / Arweave | Evidence bundle CID becomes `data_hash` in `ValidationRequest` |
| Identity / reputation | Flowsta Vault | `AgentIdentityAttestation` (implemented) handles within-ValiChord key continuity; Flowsta resolves across systems |
| **Review / validation** | **ValiChord** | **Blind commit-reveal → `HarmonyRecord` as tamper-evident corroboration record** |
| Contribution accounting | Nondominium PPRs | `log_economic_event(VfAction::Work)` per validator after `HarmonyRecord` is produced |
| Economic layer | Nondominium | PPRs feed `derive_reputation_summary()`; validation labour is rewarded, evidence access is not |
| Governance | Nondominium | `ResourceValidation` + `update_resource_state()` — an investigation "claim" transitions from `PendingValidation` to `Active` after the round |
| Social / discovery | Nostr / ActivityPub / Farcaster | Out of scope for ValiChord; these handle distribution, not integrity |

The investigation commons stack is structurally the same as the biosensor calibration walkthrough in `nondominium_integration/INTEGRATION_VISION.md`, except the resource being validated is an investigative claim rather than a calibration protocol. The plumbing is identical.

---

## What neither system does alone — and what they do together

**Nondominium** manages the resource lifecycle, contributor identity, role hierarchy, and economic accounting (ValueFlows / hREA). It does not provide a blind validation protocol.

**ValiChord** provides the blind commit-reveal protocol and tamper-evident consensus record. It does not provide contribution tracking or resource lifecycle management.

Together they produce a commons where investigative claims earn their `Active` status through cryptographically rigorous peer corroboration — with no platform, no editorial board, and no single point of trust at any stage.

The full audit trail a commons participant can follow:

```
Claim / evidence bundle
  → ResourceValidation (Nondominium) — approved, N validators
    → ReproducibilityBadge — SilverReproducible
      → HarmonyRecord — Corroborated, agreement_level: ExactMatch, N validators
        → each ValidationAttestation — individual findings, confidence, deviation flags
          → each CommitmentAnchor — proof findings were sealed before unblinding
            → each ValidatorReputation — Certified tier, 78% agreement rate, 12 prior validations
```

No central authority to trust. The chain is the proof.

---

## What needs to be agreed before integration work starts

The four open decisions from `nondominium_integration/README.md` apply directly to the investigation commons context:

| # | Question | Stakes |
|---|---|---|
| 1 | Who owns validation state — ValiChord feeds Nondominium's `ResourceValidation`, or `HarmonyRecord` is canonical? | Data architecture |
| 2 | Membrane proofs vs pseudonymous identity — does a valid ValiChord credential auto-trigger `promote_agent_to_accountable()` in Nondominium? | Trust architecture |
| 3 | Who creates the Nondominium resource — researcher first, or ValiChord fires the cross-app call? | UX and coupling |
| 4 | Flowsta as shared identity layer — required for cross-system validators, or optional with manual key-mapping fallback? | Identity and attribution |

The required implementation work once those decisions are made:

1. A vocabulary extension to `AttestationOutcome` for the investigative domain (low effort — `shared_types` change only)
2. A governance decision on pseudonymous credentials vs institutional membrane proofs (design decision, no code until resolved)
3. The Nondominium integration work already scoped in `nondominium_integration/README.md`

---

## Further reading

- [Nondominium Integration Vision](../nondominium_integration/INTEGRATION_VISION.md) — end-to-end walkthrough including the biosensor calibration example that maps structurally to this use case
- [Nondominium Integration Notes](../nondominium_integration/README.md) — the four open design decisions
- [Nondominium Architecture Reference](../nondominium_integration/NONDOMINIUM_ARCHITECTURE.md) — zome structure, entry types, function signatures
- [ValiChord and Open Cooperativism](21_ValiChord_and_Open_Cooperativism.md) — philosophical alignment with commons-based peer production
- [How a Validation Round Works](15_How_a_Validation_Round_Works.md) — step-by-step commit-reveal walkthrough
- [4-DNA Architecture](7_ValiChord_4-DNA_architecture_technical.md) — ValiChord's four-DNA sovereignty model
- [Nondominium repository](https://github.com/Sensorica/nondominium)
- [Flowsta Vault](https://github.com/WeAreFlowsta/flowsta-vault-app) — cross-system identity resolution

---

*Written April 2026 in response to Tiberius Brastaviceanu's P2P citizen investigation commons proposal.*
