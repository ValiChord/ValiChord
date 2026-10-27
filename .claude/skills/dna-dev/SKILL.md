---
name: dna-dev
description: ValiChord's Holochain DNA reference — build and pack commands, serde tag rules for JS/TS callers, the joining-certificate (membrane proof) pattern, the commit-reveal flow across the four DNAs, private-entry queries, which entries the integrity zomes guard, the cross-DNA call helper and DNA properties. Use when writing, changing or reviewing zome code in valichord/dnas/ or valichord/shared_types/, or JS/TS that calls those zomes.
---

# ValiChord DNA Development Guide

Reference for working on the Holochain DNA layer in `valichord/`.

---

## Build commands

```bash
# Always set PATH first in Codespaces
export PATH="/home/codespace/.cargo/bin:$PATH"

# Full build + pack
cargo build --target wasm32-unknown-unknown --release
hc dna pack dnas/attestation            -o workdir/attestation.dna
hc dna pack dnas/researcher_repository  -o workdir/researcher_repository.dna
hc dna pack dnas/validator_workspace    -o workdir/validator_workspace.dna
hc dna pack dnas/governance             -o workdir/governance.dna
hc app pack .                           -o workdir/valichord.happ
hc app pack researcher                  -o workdir/researcher.happ   # the demo nodes load these two
hc app pack validator                   -o workdir/validator.happ

# Run tests (kill stale conductors first; -x not -f, -f kills your own shell)
pkill -x holochain; pkill -x lair-keystore; sleep 2
./run-sweettest.sh governance        # sweettest; Tryorama (valichord/tests, npm test) was retired 2026-08-03
```

See the `integration-testing` skill (`.claude/skills/integration-testing/SKILL.md`) for the full test workflow.

Pack only with `hc` (`pack_dna.py`, which embedded the same DNA bytes for all four roles, was
deleted on 2026-10-27). **Never commit bundles you packed yourself:** the committed `.happ` files
come from the **Repack bundles** workflow, because the integrity WASM embeds the build machine's
paths, so a local build has a different DNA hash (see `CLAUDE.md`).

---

## Four-DNA architecture

| DNA | Membrane | Purpose |
|-----|----------|---------|
| `attestation` | Public DHT + Ed25519 credential | Shared protocol state: requests, commitments, profiles, phase markers |
| `researcher_repository` | Private, single-agent | GDPR-protected data; never enters DHT |
| `validator_workspace` | Private, single-agent | Private attestations before reveal; commit-reveal state |
| `governance` | Public DHT, open join | HarmonyRecords, badges, reputation, governance decisions |

Cross-DNA calls use `CallTargetCell::OtherRole("role_name")` with the author grant (same-agent only).

---

## Serde tag rules — critical for JS integration

### Adjacent tag `#[serde(tag = "type", content = "content")]`
Used by: `Discipline`, `AttestationOutcome`, `DeviationType`

```
// Unit variant — NO content key
{ type: "ComputationalBiology" }
{ type: "Reproduced" }

// Struct variant — content key present
{ type: "PartiallyReproduced", content: { details: "..." } }
{ type: "FailedToReproduce",   content: { details: "..." } }
{ type: "UnableToAssess",      content: { reason: "..."  } }
```

### External tag (default, no attribute)
Used by: `ValidationTier`, `AttestationConfidence`, `ValidationPhase`,
`AgreementLevel`, `CertificationTier`, `ValidationFocus`, `CompensationTier`

```
// Unit variants → plain strings
"Basic"    "High"    "RevealOpen"    "ExactMatch"    "Provisional"

// Struct variants → { VariantName: { ...fields } }
{ Tier1: { amount_pence: 5000 } }
```

---

## Membrane proof (joining certificate) pattern

One function, `attestation_integrity::check_joining_certificate`
(`valichord/dnas/attestation/zomes/attestation_integrity/src/lib.rs`), is called from three places:

- **`validate()`, `AgentValidationPkg` arm — run by EVERY peer.** This is the security property; a modified hApp cannot skip it.
- `genesis_self_check` — the joining agent only, before joining; fails an honest bad install early.
- coordinator `init()` (`verify_membrane_proof`) — joining agent only; defence in depth.

Do not describe the check as "init() only" or say `verify_signature` is unavailable in integrity zomes (both were in older versions of this doc and are wrong). Empty `authorized_joining_certificate_issuer` = dev/test bypass. A ValidatorProfile's `certification_tier` must equal the tier its certificate grants (`check_profile_certification`).

**Signed data format** (critical for any signing tool): `agent_raw_39 || meta_bytes`, passed to `verify_signature` as a `Vec<u8>`, which msgpack-ENCODES it (BIN format) before verifying. Do not hand-roll it; read the doc comment on `check_joining_certificate` and `sweettest_integration/tests/membrane_proof.rs` first. In JS use `Buffer`/`Uint8Array`, not `Array.from(...)` (a plain array encodes as msgpack fixarray, not BIN, and will fail).

---

## Commit-reveal protocol

DNA numbering as everywhere else in the repo: DNA 1 = `researcher_repository`, DNA 2 =
`validator_workspace`, DNA 3 = `attestation`, DNA 4 = `governance`.

### Validator side (DNA 2 → DNA 3)
1. `seal_private_attestation` (DNA 2) — generates nonce, serialises attestation to msgpack via `SerializedBytes`, computes `SHA-256(msgpack || nonce)`, stores as private `ValidatorPrivateAttestation`
2. `post_commit` (DNA 2) → `notify_commitment_sealed` on DNA 3 — passes only `request_ref` + `commitment_hash` (no content)
3. `submit_attestation` (DNA 3) — on credentialed networks refuses until the phase is RevealOpen, then verifies `SHA-256(SerializedBytes(attestation) || nonce) == CommitmentAnchor.commitment_hash` before writing public `ValidationAttestation`

### Researcher side (DNA 1 → DNA 3)
1. `lock_researcher_result` (DNA 1) — generates nonce, computes `SHA-256(rmp_serde::to_vec_named(metrics) || nonce)`, stores as private `LockedResult`
2. Calls `publish_researcher_commitment` on DNA 3 — passes only hash
3. `reveal_researcher_result` (DNA 3) — verifies hash match before writing public `ResearcherReveal`

**Codec consistency**: both commit and reveal use `SerializedBytes::try_from(&attestation).bytes()` (= `rmp_serde::to_vec_named`). Never mix with `rmp_serde::to_vec` — named uses string keys, compact uses integer keys.

---

## Private entry queries

**Use `query()` not `get()` for private entries in single-agent DNAs.**

`get(hash, GetOptions::local())` in a test conductor can leak across cell boundaries because all cells share the same local database. `query()` is always scoped to the calling agent's source chain.

```rust
// Correct — source-chain-scoped
let records = query(ChainQueryFilter::new()
    .action_type(ActionType::Create)
    .include_entries(true))?;
records.into_iter().find(|r| *r.action_address() == target)

// Risky in tests — may cross cell boundaries
get(target, GetOptions::local())
```

---

## Immutability enforcement pattern

In `validate()`, immutable entries need guards in **both** the Update and Delete arms:

```rust
// Update arm (Holochain 0.7 / hdi 0.8 names — 0.6 called these RegisterUpdate / RegisterDelete)
FlatOp::Update(OpUpdate::Entry {
    app_entry: EntryTypes::SomeImmutableType(_), ..
}) => Ok(ValidateCallbackResult::Invalid("SomeImmutableType is immutable".into())),

// Delete arm — must use must_get_valid_record + deserialize
FlatOp::Delete(OpDelete { ref action }) => {
    let original = must_get_valid_record(action.deletes_address.clone())?;
    if let Some(EntryType::App(app_def)) = original.action().entry_type() {
        // deserialize and match on type...
    }
}
```

Private entries never match `OpUpdate::Entry`, only `OpUpdate::PrivateEntry` — so in the two
all-private DNAs one blanket `OpUpdate::PrivateEntry` arm rejects **every** update, and the
per-type update arms there are dead code.

What the integrity zomes actually guard (checked 2026-10-27 against the `Invalid` messages):

| DNA | No update and no delete | Other rules |
|---|---|---|
| 3 attestation | `ValidationRequest`, `StudyClaim`, `StudyClaimRelease`, `CommitmentAnchor`, `PhaseMarker`, `ValidationAttestation`, `ResearcherResultCommitment`, `ResearcherReveal` | `AgentIdentityAttestation`: no update; either named agent may delete it (revocation) |
| 4 governance | `HarmonyRecord`, `ReproducibilityBadge`, `GovernanceDecision`, `Supersession` | `ValidatorReputation`: created and updated by `system_coordinator_key` only; it has no delete guard, so its author may delete it |
| 1 researcher_repository | `PreRegisteredProtocol` | No entry can be updated. `LockedResult`: delete refused in `OpenAudit` mode, allowed in `Gdpr`. Other entries: author-only delete |
| 2 validator_workspace | `ValidatorPrivateAttestation`, `DeliberateAbstention` | No entry can be updated. Other entries: author-only delete |

---

## Cross-DNA call helper pattern (governance coordinator)

Use `call_attestation_zome_opt<I, O>` for calls that should abort conservatively on failure:

```rust
// Returns Ok(None) on any cross-DNA failure
let records: Vec<Record> = match call_attestation_zome_opt(
    "get_attestations_for_request", request_ref.clone()
)? {
    Some(r) => r,
    None => return Ok(None),
};
```

For calls where the return type is `Option<T>` on the remote side, chain `.flatten()`:
```rust
let maybe_vr: Option<Record> = call_attestation_zome_opt::<_, Option<Record>>(
    "get_validation_request_for_data_hash", request_ref.clone()
)?.flatten();
```

---

## Reputation link-tag ordering

`ValidatorToReputation` links encode `total_validations` as 8 big-endian bytes in the link tag. Use `reputation_link_count(link)` (defined in `governance_coordinator`) to extract the count. Find the correct record with `.max_by_key()`, not `.last()`.

This prevents a race condition where two concurrent DHT writes in the same gossip batch produce non-deterministic `.last()` results.

---

## ExternalHash construction in JS (UI and Playwright e2e)

```typescript
import { hashFrom32AndType, HoloHashType } from "@holochain/client";
// see valichord-ui/src/lib/holochain.ts and valichord-ui/tests/e2e/utils/helpers.ts

// Correct — DHT location bytes are valid blake2b checksum
const core = new Uint8Array(32).fill(0xAB);
const externalHash = hashFrom32AndType(core, HoloHashType.External);

// Wrong — produces invalid DHT location bytes
const bad = new Uint8Array(39).fill(0xAB);
```

---

## DNA properties pattern

- Store as `String` (the base64 `uhCAk…` form), NOT `AgentPubKey` — conductor passes YAML modifiers as msgpack strings, not binary
- Use `#[serde(default)]` on optional properties
- Empty string = dev/test bypass (consistent pattern across all DNAs)

```rust
#[dna_properties]
pub struct DnaProperties {
    pub some_key: String,           // NOT AgentPubKey
    #[serde(default)]
    pub optional_threshold: u64,    // 0 = bypass
}
```

---

## ValidatorProfile — partial update

Use `update_validator_profile(UpdateValidatorProfileInput)` instead of calling `publish_validator_profile` with a full struct when only some fields change. `None` fields copy from the existing profile.

Note: updating disciplines/institution adds new discovery-path links but does not remove old ones. Stale discipline paths resolve to old profile records (harmless for Phase 0).
