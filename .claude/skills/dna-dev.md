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

# Run tests (kill stale conductors first)
pkill -f holochain; pkill -f lair-keystore; sleep 2
cd valichord/tests && npm test
```

**Never use `pack_dna.py`** — it embeds the same DNA bytes for all four roles.

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

## Membrane proof two-stage pattern

**Stage 1 — integrity zome `validate()`**
- Only format check (≥ 64 bytes): `verify_signature` is HDK-only, not available in HDI
- Rejects missing or short proofs

**Stage 2 — coordinator `init()`**
- Full Ed25519 verification: `verify_signature(issuer_key, sig, raw_bytes)`
- Failure → `InitCallbackResult::Fail` (agent becomes read-only observer)
- Empty `authorized_joining_certificate_issuer` = dev/test bypass

**Signed data format** (critical for JS signing tool):
```
msgpack-BIN-encoded Vec<u8> of the joining agent's raw 39-byte pubkey
```
Use `encode(Buffer.from(agentPubKey))` NOT `encode(Array.from(agentPubKey))` — the latter produces a fixarray, not BIN format, and will fail `verify_signature`.

---

## Commit-reveal protocol

### Validator side (DNA 3 → DNA 1)
1. `seal_private_attestation` — generates nonce, serialises attestation to msgpack via `SerializedBytes`, computes `SHA-256(msgpack || nonce)`, stores as private `ValidatorPrivateAttestation`
2. `post_commit` → `notify_commitment_sealed` on DNA 1 — passes only `request_ref` + `commitment_hash` (no content)
3. `submit_attestation` — verifies `SHA-256(SerializedBytes(attestation) || nonce) == CommitmentAnchor.commitment_hash` before writing public `ValidationAttestation`

### Researcher side (DNA 2 → DNA 1)
1. `lock_researcher_result` — generates nonce, computes `SHA-256(rmp_serde::to_vec_named(metrics) || nonce)`, stores as private `LockedResult`
2. Calls `publish_researcher_commitment` on DNA 1 — passes only hash
3. `reveal_researcher_result` — verifies hash match before writing public `ResearcherReveal`

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
// Update arm
FlatOp::RegisterUpdate(OpUpdate::Entry {
    app_entry: EntryTypes::SomeImmutableType(_), ..
}) => Ok(ValidateCallbackResult::Invalid("SomeImmutableType is immutable".into())),

// Delete arm — must use must_get_valid_record + deserialize
FlatOp::RegisterDelete(OpDelete { action }) => {
    let original = must_get_valid_record(action.deletes_address.clone())?;
    if let Some(EntryType::App(app_def)) = original.action().entry_type() {
        // deserialize and match on type...
    }
}
```

Immutable entries in ValiChord: `ValidationAttestation`, `CommitmentAnchor`, `PhaseMarker`, `ResearcherResultCommitment`, `ResearcherReveal`, `ValidationRequest`, `HarmonyRecord`, `ReproducibilityBadge`, `GovernanceDecision`, `PreRegisteredProtocol`, `VerifiedDataSnapshot`, `LockedResult`, `ValidatorPrivateAttestation`, `ValidationTask`.

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

## ExternalHash construction in JS tests

```typescript
import { hashFrom32AndType, HoloHashType } from "@holochain/client";

// Correct — DHT location bytes are valid blake2b checksum
const core = new Uint8Array(32).fill(0xAB);
const externalHash = hashFrom32AndType(core, HoloHashType.External);

// Wrong — produces invalid DHT location bytes
const bad = new Uint8Array(39).fill(0xAB);
```

---

## DNA properties pattern

- Store as `String` (base58/base64), NOT `AgentPubKey` — conductor passes YAML modifiers as msgpack strings, not binary
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
