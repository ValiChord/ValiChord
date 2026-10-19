
<div align="center">
  <img src="https://github.com/ValiChord/ValiChord/blob/main/Images/Valichord%20logo-standard%20v2-1.5x.jpeg" width="550px" alt="ValiChord Logo">
</div>

# ValiChord Production Deployment Checklist

**For:** Institutional operators deploying ValiChord to a live network
**Author:** Ceri John
**Date:** April 2026

---

## Before You Start

ValiChord is composed of four Holochain DNAs. Each DNA has a set of `DnaProperties` values baked into `happ.yaml` at pack time. These values control security gates, quorum sizes, and claim timeout floors. Getting them wrong can silently disable security checks or make a network impossible to use.

DNA properties are set under the `modifiers` key in each role in `happ.yaml`. They are compiled into the DNA hash — changing any property produces a new DNA hash, which is a network reset.

---

## DNA 3 — Attestation (`attestation_integrity`)

### `authorized_joining_certificate_issuer`

| Property | Value |
|---|---|
| Type | `String` (base64url-encoded `AgentPubKey`, `uhCAk...` format) |
| Dev/test bypass | **Empty string `""`** — membrane proof is not verified; anyone can join |
| Production requirement | The `AgentPubKey` of your institutional credential-issuing agent |
| What breaks if wrong | Empty string in production: any agent can join the network without credentials. Wrong key: no agent can join (all membrane proofs fail). |
| Shipped default | ⚠️ **A placeholder key, not empty** — `dnas/attestation/dna.yaml` and `happ.yaml` each carry one. So an unconfigured install has credentials **switched on** against a key nobody holds: nobody can join. That is deliberate (a forgotten setting fails closed, not open). **You must replace it** with your issuer's key; the demo and tests instead override it to `""`. |

**How to set:** Generate a keypair for your credential-issuing authority. Export the `AgentPubKey` as a `uhCAk...` string. Set it in `happ.yaml` under the `attestation` role `modifiers.authorized_joining_certificate_issuer`.

**Who checks it:** since PR #47 (2026-10-18) the joining certificate is checked by **every peer** in `validate()` (`attestation_integrity::check_joining_certificate`), not only by the joining agent — so a wrong key here is enforced network-wide. A validator's `certification_tier` must also equal what its certificate grants.

**Coordinated update required:** Any change to this key requires simultaneous updates to: (1) `happ.yaml` modifiers, (2) the membrane-proof issuer in all test fixtures, (3) any onboarding tooling that signs joining credentials.

---

### `ai_validator_issuer`

| Property | Value |
|---|---|
| Type | `String` (base64url-encoded `AgentPubKey`, `uhCAk...` format) |
| Dev/test bypass | **Empty string `""`** — AI certificates fall back to `authorized_joining_certificate_issuer`; if that is also empty, the whole credential system is bypassed |
| Production requirement | The `AgentPubKey` of the operator agent who signs AI-validator joining certificates. Leave empty to reuse the same issuer key for both human and AI validators (single-key mode). |
| What breaks if wrong | Empty string with a non-empty `authorized_joining_certificate_issuer`: AI validators must present a certificate signed by the human issuer key — functionally correct but semantically wrong (operators are the trust anchor for AI validators, not institutions). Wrong key: AI validators cannot join. |

**How to set:** Generate or reuse a keypair for your operator authority. Export the `AgentPubKey` as a `uhCAk...` string. Set it in `happ.yaml` under the `attestation` role `modifiers.ai_validator_issuer`. To use a single issuer key for both humans and AI validators, leave this field empty.

**Trust model:** Human validators are vouched for by their institution (`authorized_joining_certificate_issuer`). AI validators are approved directly by the ValiChord operator (`ai_validator_issuer`). Keeping the keys separate lets you rotate them independently and audit which agent type a joining certificate covers.

> **Decentralisation caveat:** A single operator holding `ai_validator_issuer` is a centralisation point in an otherwise peer-to-peer network. Any operator with the key can admit or deny AI validators unilaterally, and there is no on-DHT mechanism to challenge that decision. This is acceptable for Phase 0 / institutional deployments with a known operator, but is architecturally at odds with a fully decentralised network. Future directions worth considering: a multi-sig threshold over the key (M-of-N operators must co-sign a certificate), on-DHT vouching (existing high-tier human validators collectively endorse an AI agent), or DAO-style governance over the approved AI validator registry. None of these are implemented; the note is here so the tension is not forgotten.

---

### `discipline`

| Property | Value |
|---|---|
| Type | `String` — the discipline slug this network instance covers |
| Dev/test value | `"computational_biology"` (or any non-empty string) |
| Production requirement | The canonical discipline identifier for this network (e.g. `"computational_biology"`, `"psychology"`) |
| What breaks if wrong | Missing: the DNA cannot read its properties (the field has no default). Otherwise, as of 2026-10-18 **no code reads this property's value** — the discipline check at `attestation_integrity/src/lib.rs:887` compares an attestation's `discipline` with its `ValidationRequest`'s, not with this property. Changing it still changes the DNA hash. |

---

### `minimum_validators`

| Property | Value |
|---|---|
| Type | `u32` |
| Dev/test bypass | `0` — skips the quorum minimum check in `validate()` |
| Production recommendation | `3` (minimum for meaningful disagreement detection), `5` or `7` for higher-stakes studies |
| What breaks if wrong | `0` in production: a researcher can submit `num_validators_required = 1` and bypass the multi-party protocol entirely. Any value greater than your typical panel size: no round can ever complete. |

**Note:** `num_validators_required` on each `ValidationRequest` must be `≥ minimum_validators`. The integrity zome enforces this at the DHT layer.

---

### `min_claim_timeout_secs`

| Property | Value |
|---|---|
| Type | `u64` (seconds) |
| Dev/test bypass | `0` — no minimum; `reclaim_abandoned_claim` can free a slot immediately |
| Production recommendation | `259200` (72 hours) minimum; `604800` (7 days) for slow-moving disciplines |
| What breaks if wrong | `0` in production: a malicious agent can claim a study, immediately call `reclaim_abandoned_claim`, and repeat — cycling through the validator slot to observe timing patterns. Any value larger than your expected validation time: legitimate claim reclamation is blocked and abandoned slots never free up. |

---

## DNA 4 — Governance (`governance_integrity`)

### `system_coordinator_key`

| Property | Value |
|---|---|
| Type | `String` (base64url-encoded `AgentPubKey`, `uhCAk...` format) |
| Dev/test bypass | **Empty string `""`** — the authorship check is off: **any** agent may write `ValidatorReputation` and `GovernanceDecision` entries, and whoever writes a HarmonyRecord also updates each participant's reputation as a side effect (`governance_integrity/src/lib.rs:376,462`; `governance_coordinator/src/lib.rs:634`) |
| Production requirement | The `AgentPubKey` of your trusted reputation-update agent |
| What breaks if wrong | Empty string in production: any agent can write any validator's reputation, or a governance decision. Set to a key: only that agent may write them; the automatic update runs only when that agent itself writes the HarmonyRecord, so otherwise something must call `update_validator_reputation` — and **who does that in production is not yet decided**. Until it is, human validators stay `Provisional`; an AI validator's first record takes the tier its joining certificate grants. Wrong key: those writes are rejected by validation, and the automatic update's failure is ignored (fire-and-forget). Badges reflect agreement level and participant count only, whatever this is set to. |

> **Phase 0 note:** _(Corrected 2026-10-18 — this table used to say an empty key makes reputation writes a no-op. The code does the opposite: it removes the authorship check.)_ ValiChord Phase 0 ships with this key intentionally empty. Badge tiers in Phase 0 reflect agreement level and participant count only. See the Phase 0 caveat in the Architecture doc and the Technical Reference changelog.

---

### `min_attestations_for_finalization`

| Property | Value |
|---|---|
| Type | `u32` |
| Default | `0` (at-least-one default applied internally) |
| Dev/test value | `0` or `2` |
| Production recommendation | Set equal to `minimum_validators` (attestation DNA) to disallow any dropout; set lower (e.g. `minimum_validators - 1`) to permit reduced-quorum finalisation after the reveal timeout |
| What breaks if wrong | `0` with a high `minimum_validators`: `force_finalize_round` can close a round with a single attestation. Too high: `force_finalize_round` can never complete a round even after the timeout. |

---

### `round_timeout_secs`

| Property | Value |
|---|---|
| Type | `u64` (seconds) |
| Default | `604800` (7 days) — applied by `#[serde(default)]` if omitted |
| Dev/test bypass | `0` — bypasses the clock constraint entirely |
| Production recommendation | `604800` (7 days) for most disciplines; shorter for fast-turnaround computational studies |
| What breaks if wrong | `0` in production: `force_finalize_round` can close a round at any time, before validators have completed their work. Overly long: abandoned rounds are never cleaned up. |

---

## DNA 1 — Researcher Repository

No security-sensitive DNA properties. This DNA is single-agent private (no DHT, no membrane proof). No deployment configuration required beyond including it in the happ bundle.

---

## DNA 2 — Validator Workspace

No security-sensitive DNA properties. This DNA is single-agent private (no DHT, no membrane proof). No deployment configuration required beyond including it in the happ bundle.

---

## Summary Table

| DNA | Property | Dev/Test Value | Production Requirement |
|---|---|---|---|
| 3 — Attestation | `authorized_joining_certificate_issuer` | `""` (anyone joins) | Issuer `AgentPubKey` in `uhCAk...` format |
| 3 — Attestation | `ai_validator_issuer` | `""` (falls back to human issuer) | Operator `AgentPubKey` for AI-validator certs; leave empty to reuse human issuer |
| 3 — Attestation | `discipline` | any string | Canonical discipline slug (value not currently checked) |
| 3 — Attestation | `minimum_validators` | `0` (no quorum floor) | `≥ 3` |
| 3 — Attestation | `min_claim_timeout_secs` | `0` (no floor) | `≥ 259200` (72 h) |
| 4 — Governance | `system_coordinator_key` | `""` (anyone may write reputation) | Reputation oracle `AgentPubKey` (Phase 1) |
| 4 — Governance | `min_attestations_for_finalization` | `0` | Equal to or just below `minimum_validators` |
| 4 — Governance | `round_timeout_secs` | `0` (no floor) | `604800` (7 days) |

---

## Build and Pack Reminder

Always use `hc dna pack` + `hc app pack` — **never** `pack_dna.py` (it embeds the same DNA bytes for all four roles):

```bash
cargo build --target wasm32-unknown-unknown --release
hc dna pack dnas/attestation            -o workdir/attestation.dna
hc dna pack dnas/researcher_repository  -o workdir/researcher_repository.dna
hc dna pack dnas/validator_workspace    -o workdir/validator_workspace.dna
hc dna pack dnas/governance             -o workdir/governance.dna
hc app pack . -o workdir/valichord.happ
```

After changing any DNA property in `happ.yaml`, rebuild and repack — the DNA hash changes and any existing network is incompatible with the new bundle.
