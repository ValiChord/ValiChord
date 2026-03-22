<div align="center">
<img src="https://github.com/topeuph-ai/ValiChord/blob/main/Images/4%20DNA%20technical.png" alt="ValiChord 4-DNA Technical Architecture Diagram" width="900">
</div>

# ValiChord: Technical Architecture — Four-DNA Membrane Design

**Version:** 1.0 — March 2026
**Author:** Ceri John
**Status:** Infrastructure built and integration-tested

---

## Overview

ValiChord is implemented as four Holochain DNAs. Each DNA defines a distinct peer-to-peer network with its own entry types, link types, validation rules, and membrane boundary. The four DNAs run simultaneously on each participant's conductor, communicating via same-agent `call(OtherRole(...))` calls rather than cross-network messaging.

The architectural separation is not a design preference — it is the privacy and security model. Sensitive data is confined to single-agent private DNAs by structural impossibility of DHT propagation, not by policy. Only cryptographic hashes cross membrane boundaries.

---

## DNA 1 — Researcher Repository

**Membrane:** Private. Single-agent. No DHT. No membrane proof required.

**Purpose:** Local storage of all research artefacts. Nothing exits this DNA except a SHA-256 `ExternalHash` passed manually by the researcher when submitting a validation request to DNA 3.

### Entry Types

```rust
// Private — never enters DHT
ResearchStudy {
    title:             String,
    discipline:        Discipline,
    institution:       String,
    abstract_text:     String,
    pre_registration_ref: Option<ExternalHash>,
}

// IMMUTABLE after creation — enforced in validate()
PreRegisteredProtocol {
    analysis_plan:        String,
    hypotheses:           String,
    statistical_methods:  String,
    registered_at_secs:   u64,
}

// SHA-256 fingerprint of dataset at validation time
VerifiedDataSnapshot {
    data_hash:            ExternalHash,   // [u8; 32] SHA-256
    snapshot_taken_at_secs: u64,
    file_count:           u32,
    total_size_bytes:     u64,
}

// Wraps shared UndeclaredDeviation type as a private entry
DeclaredDeviation {
    study_ref:   ActionHash,
    deviation:   UndeclaredDeviation,
}
```

### Link Types
```rust
StudyToProtocol
StudyToSnapshot
StudyToDeviation
```

### Validation Rules
- `PreRegisteredProtocol`: all updates and deletes rejected — immutable after registration
- All other entries: only original author may update or delete
- No membrane proof check — single-agent DNA, no joining credential required

### Key Coordinator Functions
- `register_study`, `register_protocol`, `take_data_snapshot`, `declare_deviation`
- `compute_data_hash(data: Vec<u8>) → ExternalHash` — SHA-256 via `sha2` crate, returns `ExternalHash::from_raw_32()`

### Engineering Notes
- All entry types declared `visibility = "private"` in `EntryTypes` enum
- No `init()` capability grants needed — single-agent, all calls run under author grant automatically
- `compute_data_hash` is the only outward-facing function in the sense that its output (an `ExternalHash`) is what travels to DNA 3

---

## DNA 2 — Validator Workspace

**Membrane:** Private. Single-agent. No DHT. No membrane proof required.

**Purpose:** The commit phase of the blind commit-reveal protocol. Each validator runs one instance of this DNA. The private assessment is sealed here and never leaves. The only outward communication is a `call(OtherRole("attestation"))` fired from `post_commit` to notify DNA 3 that a commitment has been made.

### Entry Types

```rust
ValidationTask {
    request_ref:       ExternalHash,
    assigned_at_secs:  u64,
    discipline:        Discipline,
    deadline_secs:     u64,
    validation_focus:  String,
    time_cap_secs:     u64,
    compensation_tier: CompensationTier,
}

// THE COMMIT — private, immutable after creation
ValidatorPrivateAttestation {
    request_ref:             ExternalHash,
    outcome:                 AttestationOutcome,
    outcome_summary:         OutcomeSummary,
    time_invested_secs:      u64,
    time_breakdown:          TimeBreakdown,
    deviation_flags:         Vec<UndeclaredDeviation>,
    computational_resources: ComputationalResources,
    confidence:              AttestationConfidence,
    sealed_at_secs:          u64,
}
```

### Link Types
```rust
TaskToPrivateAttestation
```

### Validation Rules
- `ValidatorPrivateAttestation`: all updates and deletes rejected — immutable after sealing
- All other entries: only original author may update or delete

### post_commit — Critical Path

```rust
#[hdk_extern(infallible)]
pub fn post_commit(committed_actions: Vec<SignedActionHashed>) {
    // Detects ValidatorPrivateAttestation creation
    // Calls DNA 3 via call(OtherRole("attestation"),
    //   "attestation_coordinator",
    //   "notify_commitment_sealed",
    //   attestation.request_ref)
}
```

**Important constraint:** The target attestation cell must be initialised (i.e. `init()` must have run) before `post_commit` fires. If `post_commit` triggers `init()` in the target cell for the first time, the conductor serialises cell operations and deadlocks. In production, the UI layer initialises all cells on startup. In tests, a warm-up read call is required before `seal_private_attestation`.

---

## DNA 3 — Attestation

**Membrane:** Shared DHT. Credentialed joining. Membrane proof required.

**Purpose:** All inter-validator coordination. Manages the full commit-reveal protocol. The credentialed membrane ensures only institutionally verified validators participate. This is the most complex DNA — it contains the phase transition logic, the commitment detection mechanism, and the public attestation record.

### DNA Properties

```rust
#[dna_properties]
pub struct DnaProperties {
    pub authorized_joining_certificate_issuer: String, // base58 AgentPubKey
    pub discipline:          String,
    pub minimum_validators:  u32,
}
```

Properties are baked into the DNA hash at deployment — immutable per network instance.

### Entry Types

```rust
ValidationRequest {
    protocol_ref:            Option<ExternalHash>,
    data_hash:               ExternalHash,
    num_validators_required: u8,
    validation_tier:         ValidationTier,
    discipline:              Discipline,
}

// Public commitment proof — zero content, IMMUTABLE
// Proves a validator acted; does not reveal outcome
CommitmentAnchor {
    request_ref: ExternalHash,
    validator:   AgentPubKey,
}

// DHT-persistent phase state — IMMUTABLE, append-only
PhaseMarker {
    request_ref: ExternalHash,
    phase:       ValidationPhase,  // RevealOpen | Closed
}

// THE REVEAL — public attestation, IMMUTABLE, required_validations = 7
ValidationAttestation {
    request_ref:             ExternalHash,
    outcome:                 AttestationOutcome,
    outcome_summary:         OutcomeSummary,
    time_invested_secs:      u64,
    time_breakdown:          TimeBreakdown,
    confidence:              AttestationConfidence,
    deviation_flags:         Vec<UndeclaredDeviation>,
    computational_resources: ComputationalResources,
    discipline:              Discipline,
}

ValidatorProfile { ... }
DifficultyAssessment { ... }
```

### Link Types

```rust
StudyToValidation
ValidatorToAttestation
AgentToProfile
StatusPath              // path anchor → ValidationRequest (by status/discipline)
InstitutionPath
DisciplinePath
RequestToCommitment     // ValidationRequest → CommitmentAnchor
RequestToPhaseMarker    // ValidationRequest → PhaseMarker
```

### Commit-Reveal Protocol Flow

```
DNA 2 post_commit
    → call(OtherRole("attestation"), "notify_commitment_sealed", request_ref)
        → write CommitmentAnchor to DHT
        → create_link(commit_path, anchor_hash, RequestToCommitment)
        → count CommitmentAnchors via get_links(commit_path)
        → if count >= minimum_validators:
            → write PhaseMarker(RevealOpen)
            → create_link(phase_path, marker_hash, RequestToPhaseMarker)
            → emit_signal(PhaseSignal) — UI notification only, NOT a protocol gate

Validator polls get_current_phase(request_ref)
    → get_links(phase_path, RequestToPhaseMarker)
    → returns Option<ValidationPhase>
    → None = commit phase still open
    → Some(RevealOpen) = reveal window open

Validator calls submit_attestation(attestation)
    → create_entry(ValidationAttestation) — required_validations = 7
    → create_link(agent, hash, ValidatorToAttestation)
    → post_commit detects ValidationAttestation
    → call(OtherRole("governance"), "check_and_create_harmony_record", request_ref)
```

**Phase transition is DHT-poll-driven, not signal-driven.** Signals are send-and-forget and cannot be relied upon for protocol state transitions. `get_current_phase()` is the authoritative source of phase state.

### Validation Rules (validate callback)

Immutability guards **must** precede the generic update arm — Rust match ordering is the enforcement mechanism:

```rust
// GUARDED ARMS FIRST
FlatOp::RegisterUpdate(OpUpdate::Entry {
    app_entry: EntryTypes::ValidationAttestation(_), ..
}) => Invalid("immutable")

FlatOp::RegisterUpdate(OpUpdate::Entry {
    app_entry: EntryTypes::CommitmentAnchor(_), ..
}) => Invalid("immutable")

FlatOp::RegisterUpdate(OpUpdate::Entry {
    app_entry: EntryTypes::PhaseMarker(_), ..
}) => Invalid("immutable")

// GENERIC ARM AFTER
FlatOp::RegisterUpdate(OpUpdate::Entry { action, .. }) => {
    // author check only
}
```

### Membrane Proof

Two-stage validation:
1. `genesis_self_check` — format check only (runs before network join, no DHT access). Rejects proofs shorter than 64 bytes.
2. `coordinator init()` — full Ed25519 signature verification after join (runs lazily on first zome call, after `AgentValidationPkg` is on the source chain). Queries the source chain for `AgentValidationPkg`, extracts the 64-byte signature from the proof, and calls `verify_signature(issuer_key, sig, Vec<u8> of joining agent's 39-byte pubkey)`. Empty `authorized_joining_certificate_issuer` bypasses verification for dev/test mode.

### Capability Grants (init)

Read functions only are `Unrestricted` — accessible via HTTP Gateway without a capability token. Write functions (`notify_commitment_sealed`, `submit_attestation`) are **not** listed — they run under author grant via `call(OtherRole(...))`.

---

## DNA 4 — Governance & Harmony Records

**Membrane:** Public DHT. Open read. No membrane proof required for joining. Write access gated by DNA properties keys enforced in `validate()`.

**Purpose:** The public face of ValiChord. Permanent, tamper-evident validation outcomes. HTTP Gateway target — queryable by journals, funders, and the public without running a Holochain node.

### DNA Properties

```rust
#[dna_properties]
pub struct DnaProperties {
    pub system_coordinator_key:     String, // may write ValidatorReputation
    pub harmony_record_creator_key: String, // may write HarmonyRecord / Badge / GovernanceDecision
}
```

In test/dev mode, empty strings bypass the key check. In production, real `AgentPubKey` base58 strings are baked in at deployment.

### Entry Types

```rust
// IMMUTABLE — harmony_record_creator_key gated
HarmonyRecord {
    request_ref:              ExternalHash,
    outcome:                  AttestationOutcome,
    agreement_level:          AgreementLevel,
    participating_validators: Vec<AgentPubKey>,
    validation_duration_secs: u64,
    discipline:               Discipline,
    created_at_secs:          u64,
}

// Updateable — system_coordinator_key gated
ValidatorReputation {
    validator:           AgentPubKey,   // NOTE: keyed by device key, not person — see Known Gaps
    discipline:          Discipline,
    total_validations:   u32,
    agreement_rate:      f64,
    avg_time_secs:       u64,
    tier:                CertificationTier,
    last_updated_secs:   u64,
}

// IMMUTABLE — harmony_record_creator_key gated
ReproducibilityBadge {
    study_ref:          ExternalHash,
    issued_to:          AgentPubKey,
    badge_type:         BadgeType,  // Gold | Silver | Bronze | Failed
    issued_at_secs:     u64,
    harmony_record_ref: ActionHash,
}

// IMMUTABLE — harmony_record_creator_key gated
GovernanceDecision {
    proposal:        String,
    decision:        String,
    decided_at_secs: u64,
    votes_for:       u32,
    votes_against:   u32,
}
```

### Badge Thresholds

| Badge | Validator Count | Agreement Requirement |
|---|---|---|
| GoldReproducible | ≥ 7 | ExactMatch or WithinTolerance |
| SilverReproducible | ≥ 5 | ExactMatch or WithinTolerance |
| BronzeReproducible | ≥ 3 | ExactMatch or WithinTolerance |
| FailedReproduction | Any | Majority Divergent or NotReproduced |

### Link Types

```rust
ValidatorToReputation
RequestToHarmonyRecord
DisciplinePath         // path anchor → HarmonyRecord
BadgePath              // path anchor → ReproducibilityBadge
StudyToBadge
```

### Validation Rules

Author checks in `validate()` compare `action.author().to_string()` against DNA property keys:

```rust
// HarmonyRecord, GovernanceDecision, ReproducibilityBadge
if action.author().to_string() != props.harmony_record_creator_key {
    return Invalid("Only harmony_record_creator_key may write")
}

// ValidatorReputation
if action.author().to_string() != props.system_coordinator_key {
    return Invalid("Only system_coordinator_key may write")
}
```

All four protected entry types block deletes. `ValidatorReputation` allows updates (coordinator key enforced). The other three are fully immutable.

### check_and_create_harmony_record

Called from DNA 3's `post_commit`. Idempotent — checks for existing `HarmonyRecord` before creating. Calls back into DNA 3 via `call(OtherRole("attestation"), "get_attestations_for_request")` to retrieve attestations.

**Deadlock warning:** Do not call `check_and_create_harmony_record` from inside DNA 3's `post_commit` directly — this creates a re-entrant deadlock on the attestation cell's operation queue (attestation waits for governance, governance calls back into attestation which is still executing). The correct pattern is: DNA 3 `post_commit` calls governance, governance calls attestation read functions only (not write).

---

## Cross-DNA Communication Pattern

Same-agent `call()` is the only permitted cross-DNA communication. `call_remote()` cannot cross DNA network boundaries.

```
DNA 2 post_commit
    → call(OtherRole("attestation"), notify_commitment_sealed)   // write

DNA 3 post_commit
    → call(OtherRole("governance"), check_and_create_harmony_record)   // write

DNA 4 check_and_create_harmony_record
    → call(OtherRole("attestation"), get_attestations_for_request)   // read only
```

All three arrows run on the same agent's conductor. The governance call from DNA 3 and the attestation read from DNA 4 must not form a cycle with any pending write operation on either cell — see deadlock warning above.

---

## Build and Test

```bash
# Compile all four WASM zomes
cargo build --target wasm32-unknown-unknown --release

# Pack DNAs and hApp — use hc directly, NOT pack_dna.py
hc dna pack dnas/attestation            -o workdir/attestation.dna
hc dna pack dnas/researcher_repository  -o workdir/researcher_repository.dna
hc dna pack dnas/validator_workspace    -o workdir/validator_workspace.dna
hc dna pack dnas/governance             -o workdir/governance.dna
hc app pack . -o workdir/valichord.happ

# Run integration tests
cd tests && npm test
```

**87 integration tests passing, 1 skipped** (GoldReproducible — requires 7 simultaneous conductors, resource-constrained in Codespaces). See `tests/README.md` for full test inventory.

---

## Known Gaps and TODOs

| Item | Location | Notes |
|---|---|---|
| Validator assignment engine | DNA 3 `select_validators()` | Stub returns empty. Needs conflict-of-interest detection, institutional balance, randomisation |
| Gaming detection | DNA 3 `detect_gaming_patterns()` | Stub. Pattern flags defined but not implemented |
| GoldReproducible badge (7 validators) | DNA 4 / test 12.2 | Test logic correct. Skipped in Codespaces — requires 7 simultaneous conductors (≥16 GB RAM). Run on adequately resourced hardware |
| Countersigning for simultaneous reveal | DNA 3 | Deferred to Phase 2. Current design uses DHT-poll-driven sequential reveals. CommitmentAnchor approach already prevents outcome-peeking. True countersigning adds operational constraints (all validators online simultaneously) that are inappropriate for Phase 0 |
| Multi-device identity / agent linking | DNA 3 `ValidatorProfile`, DNA 4 `ValidatorReputation` | Both are keyed by `AgentPubKey` (device key), not a stable person identity. A validator who switches or loses a device accrues reputation on a new orphaned key. The Flowsta `agent_linking` zome (github.com/WeAreFlowsta/flowsta-identity-dna) is an ecosystem drop-in that creates pairwise `IsSamePersonEntry` records with mutual Ed25519 signatures — allowing any lookup to resolve all keys belonging to one person. Not needed for Phase 0 (single-device institutional validators). Design into Phase 1 before reputation scores become operationally meaningful. Will also be partially addressed by Holochain 1.0 Deepkey (key rotation) — coordinate the two designs together |

---

## Shared Types

All cross-DNA types live in `valichord/shared_types/` — a pure `rlib` crate imported by all four DNAs. This avoids the `cdylib` duplicate-symbol error that occurs when types are defined in an integrity zome (compiled as `cdylib`) and re-exported across crates.

Key shared types: `Discipline`, `AttestationOutcome`, `AttestationConfidence`, `ComputationalResources`, `TimeBreakdown`, `UndeclaredDeviation`, `ValidationPhase`, `OutcomeSummary`, `MetricResult`, `AgreementLevel`, `CertificationTier`, `discipline_tag()`.

---

*Technical Reference v16 and Architecture Scaffold v12 provide full field-level detail and engineering narrative.*
