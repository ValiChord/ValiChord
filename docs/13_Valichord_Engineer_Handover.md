# ValiChord: Engineer Handover Document

**Version:** 2.5 — May 2026
**Author:** Ceri John
**Status:** Current — reflects codebase as of last commit

---

## Overview

This document is for any engineer picking up the ValiChord codebase. It covers what is built and tested, what is stubbed and why, known constraints and hard-won lessons, the build sequence, and decisions that have been deferred to Phase 1.

Read this before touching the code.

---

## What Is Built

ValiChord is a four-DNA Holochain hApp — four independent peer-to-peer networks running simultaneously on each participant's conductor, communicating via same-agent `call(OtherRole(...))` calls.

The infrastructure is complete in the sense that matters: it compiles, the four DNAs pack into a single `.happ` bundle, and 166 integration tests pass across two suites (97 Tryorama, 69 Rust sweettest native), with 1 Tryorama test.skip (GoldReproducible — hardware-constrained; sweettest equivalent passes). As of 2026-04-23, all four DNAs have been reviewed and optimised (including an efficiency pass eliminating O(N) DHT round-trips and a second security pass adding self-claim prevention, researcher reveal authorisation, and PhaseMarker idempotency), and the cryptographic commit-reveal protocol is fully implemented — see the constraint list below for the key decisions made.

### DNA 1 — Researcher Repository
**Status: Complete**

Private, single-agent DNA. Stores all research artefacts locally — code, data, protocols, snapshots. Nothing leaves except a SHA-256 `ExternalHash` passed manually by the researcher when submitting a validation request.

All entry types are `visibility = "private"`. No DHT. No membrane proof required.

`PreRegisteredProtocol` is immutable after creation — updates and deletes are rejected in `validate()`. This is enforced and tested.

`compute_data_hash` uses `sha2::Sha256` and returns a 39-byte `ExternalHash` via `ExternalHash::from_raw_32()`.

`get_all_studies()` returns all `ResearchStudy` records from the local source chain using `query()` + deserialization filter. Same pattern as `get_all_tasks` in DNA 2.

---

### DNA 2 — Validator Workspace
**Status: Complete**

Private, single-agent DNA. The commit phase of the blind commit-reveal protocol lives here. Each validator runs one instance. The private assessment is sealed here as `ValidatorPrivateAttestation` and never leaves.

`ValidatorPrivateAttestation` is immutable after creation — tested.

**`seal_private_attestation` now generates and stores the cryptographic commitment** (2026-03-18). The function accepts `SealAttestationInput { task_hash, attestation: ValidationAttestation }` — the exact public attestation the validator intends to reveal. It:
1. Generates a 32-byte nonce via `random_bytes(32)` (HDK host function).
2. Serialises the `ValidationAttestation` to MessagePack via `SerializedBytes::try_from`.
3. Computes `commitment_hash = SHA-256(msgpack_bytes || nonce)` using the `sha2` crate.
4. Writes the private entry with all attestation fields plus `discipline`, `nonce`, and `commitment_hash`.

`ValidatorPrivateAttestation` now carries five generated/derived fields: `nonce: Vec<u8>`, `commitment_hash: Vec<u8>`, and `discipline: Discipline`. The caller must NOT supply these — they are computed by `seal_private_attestation`. The `discipline` field mirrors the public attestation's discipline so the full `ValidationAttestation` can be reconstructed at reveal time without a separate task lookup.

**Critical:** `post_commit` fires `call(OtherRole("attestation"), "notify_commitment_sealed")` after a `ValidatorPrivateAttestation` is created. The payload is now `CommitmentSealedInput { request_ref, commitment_hash }` — the commitment hash is forwarded to DNA 3 so the `CommitmentAnchor` on the shared DHT carries the cryptographic proof. The target attestation cell must be initialised before `post_commit` fires — see the deadlock section below.

`get_all_private_attestations()` returns all `ValidatorPrivateAttestation` records from the local source chain using `query()` + deserialization filter. Parallel to `get_all_tasks`.

**`get_private_attestation_for_task` uses `query()` for retrieval (2026-03-20).** The function follows a `TaskToPrivateAttestation` link to the target ActionHash, then uses `query(ChainQueryFilter::new().include_entries(true))` to find the matching record in the calling agent's source chain — `find(|r| r.action_address() == &target)`. This replaces the previous `get(target, GetOptions::local())` call. Reason: `query()` is strictly source-chain-local and cannot cross cell boundaries even when cells share the same conductor process (singleFork/test mode). `get()` with local options would find Alice's private entry from Bob's cell in a shared-conductor test, violating the privacy guarantee. In production the distinction is moot (private entries never leave the device), but the test suite verifies the structural privacy property.

---

### DNA 3 — Attestation
**Status: Complete**

Shared DHT, credentialed membrane. The most complex DNA. Manages the full commit-reveal protocol, phase transitions, and public attestation records.

**Membrane proof:** Real Ed25519 verification is implemented in the **coordinator** `init()`, not the integrity zome. The integrity zome does format-only checks (≥64 bytes). The coordinator queries the source chain for `AgentValidationPkg`, reads `authorized_joining_certificate_issuer` from DNA properties, and calls `verify_signature()`. Empty string in DNA properties = dev/test bypass.

**Phase transitions** are DHT-poll-driven. `get_current_phase()` is always the authoritative source of phase state — signals are best-effort and can be lost if an agent is offline. When the last commitment arrives, `notify_commitment_sealed` emits a typed `Signal::RevealOpen { request_ref }` locally via `emit_signal` AND fire-and-forget pushes it to all other committed validators via `send_remote_signal`. The receiving end is `recv_remote_signal(signal: Signal)` — it re-emits locally so the agent's `AppWebsocket` subscriber sees the same payload. Serde encoding: `{ type: "RevealOpen", content: { request_ref: "uhCEk..." } }` (adjacent tag, matching ValiChord's enum convention). Do not gate protocol logic on signals — always verify state via DHT.

`CommitmentAnchor`, `PhaseMarker`, `ValidationAttestation`, and `ResearcherResultCommitment` are all immutable after creation — enforced in `validate()` and tested.

**`CommitmentAnchor` now carries `commitment_hash: Vec<u8>`** (2026-03-18) — the SHA-256 of the validator's serialised `ValidationAttestation` concatenated with a private nonce. Written by `notify_commitment_sealed(input: CommitmentSealedInput)`. At reveal time, verifying `SHA-256(msgpack(attestation) || nonce) == commitment_hash` proves the revealed content matches what was committed without any honesty assumptions.

**`publish_researcher_commitment(input: ResearcherCommitmentInput)` is a new write function** (2026-03-18). The researcher calls this before the validation round opens to publish `ResearcherResultCommitment { request_ref, result_commitment_hash }` to the shared DHT. The actual result stays in the researcher's local DNA 1. This closes the other side of the blinding: validators cannot claim the researcher adjusted their result after seeing validator findings. The entry is indexed under `researcher_commitment.{request_ref}` via `RequestToResearcherCommitment` link type. **`get_researcher_commitment(request_ref)` is the companion read** — added to the unrestricted cap grant so any participant can verify the researcher committed before validators begin.

`notify_commitment_sealed` is intentionally NOT in the unrestricted cap grant — it is called under the author grant from DNA 2's `post_commit`.

`get_validation_request_for_data_hash(data_hash: ExternalHash)` is a public extern registered in `init()`. It resolves a `ValidationRequest` record from the `study.{data_hash}` path. Used by DNA 4 to identify the researcher (record author) when issuing a `ReproducibilityBadge`.

**`ValidationRequest` carries two new pointer fields** added 2026-03-14: `data_access_url: String` (URL where validators download the dataset — OSF, Zenodo, institutional repo, etc.) and `protocol_access_url: Option<String>` (DOI or URL of the pre-registered analysis plan). The actual data never touches the DHT — these are pointers only. The researcher fills these from their private DNA before calling `submit_validation_request`.

**`ValidationRequest` deposit access mechanism** — added April 2026. Two new optional fields (both `#[serde(default)]`, backwards-compatible with existing entries):

- `deposit_access_type: DepositAccessType` — `PublicUrl` (default) or `TokenGated`. Tells validators how to authenticate when fetching the deposit.
- `deposit_token: Option<String>` — a `secrets.token_urlsafe(32)` bearer credential. Only set when `deposit_access_type == TokenGated`.

`DepositAccessType` is defined in `attestation_integrity`. The DHT membrane (credentialed joining, membrane proof required) protects the token — only validators with a valid `authorized_joining_certificate_issuer` signature can read the `ValidationRequest` entry and therefore the token.

**`TokenGated` flow:** the researcher's Flask backend generates the token at job creation time, stores it in `_jobs[job_id]`, and passes `data_access_url = {VALICHORD_BASE_URL}/deposit/{job_id}` + `deposit_token` to `_runValidationRound` in `serve.mjs`, which includes both in the `submit_validation_request` call. Validators read the `ValidationRequest` from the shared DHT, append `?token={deposit_token}` to the URL, and `GET /deposit/<job_id>` serves the ZIP back (token verified with `secrets.compare_digest`).

**`VALICHORD_BASE_URL` env var** — must be set in institutional deployments to the server's public address (e.g. `https://valichord.example.com`). Defaults to `http://localhost:5000` for dev/Codespace.

**Critical Holochain constraint:** `call_remote` cannot cross DNA network boundaries. DNA 1 (Researcher Repository) is a private single-agent DNA in a different network from DNA 3 (Attestation). Validators cannot `call_remote` to the researcher's DNA 1 to fetch the deposit. The token in the `ValidationRequest` entry and the HTTP endpoint in `backend/app.py` are the correct architecture — Holochain carries the credential, HTTP delivers the bytes.

**Governance DNA is now fully decentralised** (2026-03-14): `HarmonyRecord`, `ReproducibilityBadge`, and `ValidatorReputation` are no longer author-gated by a designated coordinator key. Any participant who was part of the round can trigger finalisation by calling `check_and_create_harmony_record`. The function enforces completeness (must have ≥ `num_validators_required` attestations before writing) and idempotency (a second call short-circuits if a record already exists). `submit_attestation` in the Attestation DNA now automatically fires a same-agent cross-DNA call to `check_and_create_harmony_record` — the last validator to submit their attestation triggers the HarmonyRecord write without any central coordinator node.

`GovernanceDecision` remains key-gated by `system_coordinator_key` — governance votes are human deliberation outcomes that require a designated recorder. `harmony_record_creator_key` has been removed from `DnaProperties` entirely.

**Known remaining limitation (Phase 1):** the Governance integrity zome's `validate()` cannot perform cross-DNA lookups to cryptographically verify that a HarmonyRecord's content is correct against the Attestation DHT. Content correctness is currently enforced at the coordinator layer (completeness check + algorithmic derivation) but not at the network validation layer. Making it trustless at the validation layer requires either moving HarmonyRecord creation into the Attestation DNA or embedding sufficient proof in the entry itself. A partial guard IS enforced (2026-03-20): `validate()` requires the HarmonyRecord author to be listed in `record.participating_validators` — prevents non-participants from anonymously forging a record and winning the first-write idempotency race.

**Non-deterministic `links.last()` replaced in DNA 4 (April 2026).** `get_harmony_record` used `links.last()` to pick the single `RequestToHarmonyRecord` link. Replaced with `links.iter().max_by_key(|l| l.timestamp)` for consistency with the DNA 3 fix and to be robust if the idempotency guard ever fails to prevent a duplicate write.

`required_validations = 7` is set on `ValidationAttestation`. This is a Holochain DHT validation parameter — it means 7 peers must validate the entry before it is considered fully integrated.

**Validator self-assignment (`StudyClaim`)** — implemented 2026-03-14. Validators discover studies via `get_pending_requests_for_discipline` and call `claim_study(request_ref: ExternalHash)` to self-assign without any central matchmaker. The coordinator resolves the `ValidationRequest` ActionHash via the `StudyToValidation` path, reads the validator's institution from their `ValidatorProfile`, enforces capacity (no more than `num_validators_required` claims per study) and duplicate (no double-claiming) at the coordinator layer, then writes a `StudyClaim` entry plus two link indexes — `RequestToClaim` (base = request_ref, for `get_claims_for_request`) and `ValidatorToClaim` (base = agent pubkey, for `get_my_claimed_studies`). The integrity zome's `validate()` enforces conflict-of-interest at the network layer: if both `validator_institution` and `researcher_institution` are non-empty and equal, the claim is rejected. `release_claim(request_ref)` deletes both links (freeing the slot for another validator); the `StudyClaim` entry remains permanently as an audit record. Empty institution on either side bypasses the COI check (dev mode / researcher did not declare institution). `ValidationRequest` now also carries `researcher_institution: String` alongside the pointer fields `data_access_url` and `protocol_access_url`.

**Dropout recovery** — implemented 2026-03-14. `reclaim_abandoned_claim(input: { request_ref, claim_hash, timeout_secs })` is callable by any participant. It verifies the claim is older than `timeout_secs` AND the absent validator has not attested, then deletes both link indexes to free the slot. Use `timeout_secs = 604800` (7 days) in production; `0` in tests. The companion function `force_finalize_round(request_ref)` in DNA 4 closes a round still stuck after `round_timeout_secs` seconds (DNA property, default 604 800 s / 7 days; set to `0` in tests so the age check always passes) with whatever attestations are present, subject to `min_attestations_for_finalization` (see governance `DnaProperties`). Neither function requires special keys — both are open to any participant, consistent with the decentralised governance model.

**`check_all_commitments_sealed_inner` fix** — 2026-03-16. Previously used `props.minimum_validators` (network-wide DNA property) to decide when to open the reveal window. Now calls `get_num_validators_required(request_ref)` which reads `num_validators_required` from the actual `ValidationRequest` entry. The phase transition now opens when the correct number of validators *for that specific study* have committed, not the network minimum.

**`ValidatorAgentType` + partial profile update** — 2026-03-24. `ValidatorProfile` now carries an `agent_type: Option<ValidatorAgentType>` field (`#[serde(default)]`) distinguishing `Individual`, `Institution`, and `AutomatedTool`. Existing profiles deserialise with `None` — backwards-compatible. New coordinator functions: `update_validator_profile(UpdateValidatorProfileInput)` accepts partial `Option<T>` fields, fetches the current profile, merges supplied changes, and re-publishes; `get_validator_agent_type(agent: AgentPubKey) → Option<ValidatorAgentType>` is an unrestricted read returning the agent type from the latest profile. Both are in the `init()` cap grant.

**`AgentToProfile` link-tag ordering fix** — 2026-03-25. `publish_validator_profile` now writes an 8-byte big-endian `i64` microsecond timestamp (from `sys_time()`) as the `LinkTag` on every `AgentToProfile` link. All four profile read sites — `get_validator_profile`, `update_validator_profile`, `get_validator_agent_type`, and `claim_study` — now select the latest profile with `.max_by_key(|l| profile_link_ts(l))` instead of `.first()` / `.last()`. `profile_link_ts()` extracts the `i64` from the tag bytes; old links with no tag return `i64::MIN` and always lose — backwards-compatible. **Why this matters:** DHT gossip does not guarantee link delivery order. `.first()` in `get_validator_profile` was returning the *oldest* profile (a correctness bug, not just ordering); `.last()` in the other three was returning an arbitrary link if two DHT messages arrived in the same batch. The fix is consistent with the `ValidatorToReputation` link-tag scheme already in the governance coordinator.

**Native `AgentIdentityAttestation` implemented** — 2026-03-25. Two agents can now assert they share a logical identity (multi-device, key rotation) directly on the ValiChord DHT — no external service. New `attestation_integrity` entry type: `AgentIdentityAttestation { agent_a: AgentPubKey, signature_a: Signature, agent_b: AgentPubKey, signature_b: Signature }` — `agent_a` is always the lexicographically smaller key. New link type: `AgentToIdentityAttestation`. Integrity validation: self-link rejection (`agent_a ≠ agent_b`), update immutability, and authorized-deletion (either named agent may delete; a third party is rejected). New coordinator functions: `sign_for_identity_link(other_agent) → Signature` (signs canonical 78-byte sorted-key payload for ceremony); `link_agent_identity(LinkAgentIdentityInput) → ActionHash` (verifies both Ed25519 signatures, commits entry, writes symmetric links from both pubkeys); `get_linked_agents() → Vec<Record>` (unrestricted, filters deleted entries via `get_details()`); `revoke_agent_identity_link(hash)` (coordinator-level author check + `delete_entry`). `get_linked_agents` added to the `init()` unrestricted cap grant. Five integration tests added (describe block "22. AgentIdentityAttestation"): happy path, self-link rejection, bad signature rejection, revocation + visibility disappears, third-party revocation rejected. **This change modified `attestation_integrity` — the attestation DNA hash changed. Treat as a deliberate network reset.** Phase 1 follow-on: populate `person_key` in `ValidatorProfile` / `ValidatorReputation` from `get_linked_agents` to enable stable-key reputation aggregation across device rotations. Potential future integration: Flowsta's `agent_linking` zome uses the identical two-signature sorted-payload protocol and could replace ValiChord's native version if a shared cross-application identity graph becomes useful.

**N+1 DHT call pattern eliminated from claim functions (April 2026).** `claim_study`, `get_claims_for_request`, and `get_my_claimed_studies` previously iterated over all `StudyClaim` entries and issued one `get_links(ClaimToRelease)` call per claim to check whether it had been released — O(N) DHT round-trips for N claims. Fixed with two new index link types: `RequestToRelease` (base = study path anchor; tag = 39-byte `ActionHash` of the released `StudyClaim`) and `ValidatorToRelease` (base = validator `AgentPubKey`; same tag scheme). `release_claim` and `reclaim_abandoned_claim` now write both index links. All three read functions load all release hashes in a single `get_links` call, then do an O(1) `HashSet::contains` check per claim. DHT round-trips drop from O(N) to O(1) regardless of how many validators are in the round.

**Non-deterministic `links.last()` replaced in DNA 3 (April 2026).** `get_difficulty_assessment`, `get_current_phase`, `get_researcher_commitment`, and `get_researcher_reveal` all previously used `links.last()` — which returns whichever link DHT gossip delivered last, a non-deterministic ordering. All four now use `links.iter().max_by_key(|l| l.timestamp)`, selecting the link with the highest Holochain `Timestamp` value deterministically.

**Self-claim prevention enforced at integrity layer (April 2026).** `StudyClaim validate()` now uses `must_get_valid_record` to fetch the linked `ValidationRequest` and compares `create_action.author` against `req_record.action().author()`. If they match, the claim is rejected with "Researcher cannot claim their own study". This guard has **no dev/test bypass** — `authorized_joining_certificate_issuer = ""` does not affect it. There is no code path through which a researcher can validate their own study.

**Researcher reveal authorisation guard (April 2026).** In production mode (non-empty `authorized_joining_certificate_issuer`), `reveal_researcher_result` now fetches the `ValidationRequest` via the `study.{request_ref}` path and verifies that `action_info().agent_initial_pubkey == validation_request.action().author()`. A third party cannot publish a researcher's structured reveal and falsely claim they got a given result. The dev/test bypass (empty issuer key) skips this check so Tryorama tests work without identity wiring.

**PhaseMarker write idempotency (April 2026).** `notify_commitment_sealed` now checks `existing_phase = get_links(RequestToPhaseMarker)` before writing a new `PhaseMarker`. If a link already exists the write is skipped; cross-agent push signals fire regardless. This closes the TOCTOU gap where two validators simultaneously detecting the quorum threshold would each write a `PhaseMarker`, creating duplicate phase entries that make `get_current_phase` non-deterministic.

**`assess_difficulty` stub replaced with caller-provided input** — 2026-03-25. `assess_difficulty` previously accepted only `request_ref: ExternalHash` and returned an entry with all fields hardcoded (e.g. `code_volume = 3`). The function was a useless scaffold. It now accepts `AssessDifficultyInput { request_ref, code_volume, dependency_count, documentation_quality, data_accessibility, environment_complexity, study_age_years, predicted_tier, predicted_min_secs, predicted_max_secs, confidence }` — all caller-supplied. The coordinator validates that `predicted_min_secs ≤ predicted_max_secs`, stores the entry verbatim, and indexes via `DifficultyPath` (unchanged). A prediction model (ML / heuristic) is Phase 1 work. Phase 0 collects real assessments to determine whether surface features correlate with actual validation workload. The test for this function is updated to pass a meaningful struct and assert the round-tripped values.

---

### DNA 4 — Governance & Harmony Records
**Status: Complete**

Public DHT, HTTP Gateway target. Stores final outcomes — Harmony Records, Reproducibility Badges, validator reputation, governance decisions.

Write access is decentralised: `HarmonyRecord`, `ReproducibilityBadge`, and `ValidatorReputation` are open to any participant — no author key required. `GovernanceDecision` is the sole exception, gated by `system_coordinator_key` in `validate()` (human deliberation outcomes need a designated recorder). Empty string = dev/test bypass. `harmony_record_creator_key` has been removed from `DnaProperties` entirely.

**`DnaProperties`** (governance) contains two fields: `system_coordinator_key: String` (gates GovernanceDecision writes) and `min_attestations_for_finalization: u32` (minimum attestations required before `force_finalize_round` will write a HarmonyRecord). Policy: set equal to `minimum_validators` for panels of ≤4 validators (no dropout tolerated — governance decides); set to `minimum_validators - 1` for larger panels (one dropout tolerated, auto-finalises after timeout). Value `0` falls back to requiring at least one attestation (safe dev/test default).

`HarmonyRecord`, `ReproducibilityBadge`, and `GovernanceDecision` are immutable. `ValidatorReputation` allows updates (no key gate — updated automatically during round finalisation).

**No self-reported timestamps.** `HarmonyRecord`, `ValidatorReputation`, and `ReproducibilityBadge` do not store `created_at_secs`, `last_updated_secs`, or `issued_at_secs` fields. These were removed because Holochain Actions carry an authoritative, tamper-evident timestamp — self-reported timestamps in entry content are falsifiable and redundant. Do not add them back.

**Badge recipient is the researcher, not the first validator.** `ReproducibilityBadge.issued_to` is resolved via a cross-DNA call: `call(OtherRole("attestation"), "get_validation_request_for_data_hash", data_hash)`. The record's `action().author()` is the researcher who submitted the study. Falls back to the first participating validator if the cross-DNA call fails.

`check_and_create_harmony_record` is idempotent and decentralised — any participant may call it. It checks for an existing record first, then verifies that enough attestations exist (`attestation_records.len() >= num_validators_required`) before writing. `submit_attestation` in DNA 3 automatically fires this call on the governance role after writing each attestation — the last validator to reveal triggers HarmonyRecord creation without any central coordinator node. When a badge is issued it is linked twice: via `StudyToBadge` (per-study lookup) and via `BadgePath` (cross-study type-based analytics).

`create_governance_decision(input: GovernanceDecision)` writes a `GovernanceDecision` entry and indexes it under the `decisions.all` path anchor via `AllDecisions` link type. Gated by `system_coordinator_key` in `validate()`.

`get_all_governance_decisions()` reads via `AllDecisions` links from the path anchor. Network-strategy get.

`get_validators_for_institution(institution: String)` reads via `InstitutionPath` links from "institution.{institution}" anchor. `publish_validator_profile` now writes both `ValidatorTierPath` (discipline) and `InstitutionPath` (institution) links.

`get_attestations_for_discipline(discipline: Discipline)` reads via `DisciplinePath` links from "attestations.{discipline_tag}" anchor. Written by `submit_attestation`.

`get_badges_by_type(badge_type: BadgeType)` reads all badges of a given type via the `BadgePath` link index. Accepts a plain string enum variant (e.g. `"BronzeReproducible"`).

---

### Frontend — `valichord-ui`
**Status: Complete (v0.4.2, April 2026)**

Svelte 5 + TypeScript SPA. Connects directly to the running conductor via `AppWebsocket`. No intermediary server.

**Entry points:**
- `src/App.svelte` — app shell, port detection, global `RevealOpen` signal subscription, role detection
- `src/lib/holochain.ts` — singleton `AppWebsocket` wrapper; `callZome<T>(role, fnName, payload)` with role→zome name map
- `src/lib/store.ts` — Svelte stores (`connectState`, `myPubKey`, `activeRole`, `myValidatorProfile`, `pendingReveals`)
- `src/lib/types.ts` — TypeScript mirrors of all Rust types with correct serde encoding

**Three views:**
- `ResearcherView.svelte` — submit request, lock metrics, reveal
- `ValidatorView.svelte` — dashboard, setup profile, browse studies, seal attestation, reveal
- `GovernanceView.svelte` — browse HarmonyRecords, inferred badge display, force-finalize panel

**Commit-reveal flow — validator path (critical: do not deviate):**
1. `claim_study(request_ref)` on `attestation` DNA → `receive_task(ValidationTask)` on `validator_workspace` DNA to get `task_hash`
2. Attestation form → `seal_private_attestation({ task_hash, attestation })` on `validator_workspace` DNA — nonce is generated internally; UI never supplies it
3. `post_commit` in `validator_workspace` automatically fires `notify_commitment_sealed` to `attestation` DNA — **UI must NOT call this manually**
4. `RevealOpen` signal → `get_private_attestation_for_task(task_hash)` on `validator_workspace` → extract `nonce` → `submit_attestation({ attestation, nonce })` on `attestation` DNA

**Commit-reveal flow — researcher path:**
1. `lock_researcher_result({ request_ref, metrics })` on `researcher_repository` DNA + `publish_researcher_commitment(...)` on `attestation` DNA — nonce generated internally
2. `get_locked_result(request_ref)` on `researcher_repository` DNA retrieves the stored nonce → `reveal_researcher_result({ request_ref, metrics, nonce })` on `attestation` DNA

**Port detection** — three-source priority: `window.location.hash` (`#APP_PORT=PORT`, Launcher injection) → `VITE_HC_PORT` env var → Launcher default. `AppWebsocket.connect()` requires `url: new URL(...)` (URL object, not string).

**Signal encoding** — `Signal` enum in `attestation_coordinator` has no `#[serde(tag)]`, so external-tag serialisation applies: `{ RevealOpen: { request_ref: Uint8Array } }`.

**To run:**
```bash
cd valichord-ui
cp .env.example .env   # set VITE_HC_PORT
npm install && npm run dev
```
See `valichord-ui/FRONTEND.md` for the full UX walkthrough with screen-by-screen instructions.

---

### `valichord_attestation` — Canonical AI Evaluation Attestation Format
**Status: v0.1.0 — standalone Python library, 81 tests, 100% line coverage**

`valichord_attestation/` is a harness-agnostic Python library that produces cryptographically verifiable attestation bundles for AI evaluation runs. It applies the same commit-hash-reveal principle that ValiChord uses for scientific reproducibility to AI capability benchmarks: a published accuracy score becomes traceable to the specific run that produced it, and any individual sample can be proven to a third party without disclosing the full log.

**Location:** `valichord_attestation/` (sibling to `valichord/` — a pure-Python package, no Rust dependency)

**Key modules:**

| Module | Purpose |
|---|---|
| `valichord_attestation/builder.py` | `build_bundle(model_id, task_id, raw_metrics, samples, ...)` — constructs and validates a `Bundle`, computes the Merkle root, enforces pre-rounding rules, rejects NaN/Infinity |
| `valichord_attestation/canonical.py` | RFC 8785 (JCS) deterministic encoding; `hash_bundle(bundle)` — SHA-256 hex of the canonical encoding |
| `valichord_attestation/merkle.py` | `merkle_root(samples)`, `merkle_proof(samples, index)`, `verify_faithfulness(root_hex, index, sample, proof)` |
| `valichord_attestation/bundle.py` | `Bundle` Pydantic model — required and optional fields, `extra="allow"` for forwards compatibility |
| `valichord_attestation/adapters/base.py` | `AdapterBase` ABC — subclass and implement `to_bundle(...)` to wrap any harness |
| `valichord_attestation/adapters/inspect_evals_stub.py` | Stub adapter for Inspect AI — maps `EvaluationReport` fields once the upstream API stabilises |

**Format summary:**

A bundle is a JSON document with required fields `format_version`, `generated_at`, `model_id`, `task_id`, `metrics`, `samples`, and `outputs_merkle_root`. Optional fields (`repo_commit`, `harness_version`, `command`) are omitted from the canonical encoding when absent. Metric values are pre-rounded to 6 decimal places before encoding; NaN, Infinity, and missing `value` keys raise `MalformedBundleError`.

The Merkle root is a SHA-256 tree over per-sample output dicts, each leaf computed as `SHA-256(JCS(sample_dict))`. The bundle hash is `SHA-256(JCS(bundle_dict))`. Both are 64-char hex strings.

**What v1 does not do (non-goals):** cryptographic signing (reserved for v2), zero-knowledge disclosure proofs, integration with Holochain DNAs (bundles becoming DHT attestations is post-format-stabilisation work), concrete harness adapters (shipped separately when upstream APIs stabilise).

**Running tests:**
```bash
pip install -e "valichord_attestation[dev]"
pytest valichord_attestation/tests/ --cov=valichord_attestation
```

**Running examples:**
```bash
python valichord_attestation/examples/verify_examples.py
```
Each example JSON contains a synthetic bundle, source samples, and a pre-computed inclusion proof. The script recomputes hash and Merkle root from scratch and confirms they match.

**Full spec:** `valichord_attestation/spec/attestation_format_v1.md` — schema, encoding rules, pre-rounding policy, Merkle tree construction, proof format and verifier algorithm, versioning policy, security considerations.

**Architectural context:** the format was designed in response to Scott Simmons's review of `UKGovernmentBEIS/inspect_evals#1610`. The core feedback was that the canonical attestation spec belongs in ValiChord (the verification infrastructure), not inside each eval harness, and that the meaningful attestation is not "I have the log file" but "this reported result is faithful to the run that produced it."

---

## What Is Stubbed

These functions exist and compile but return placeholder values. They are designed to be filled in during Phase 1 without touching any other part of the system.

| Function | Location | Current behaviour | What it needs |
|---|---|---|---|
| `assess_difficulty` / `get_difficulty_assessment` | DNA 3 coordinator | **Now accepts real caller-provided `AssessDifficultyInput`** (2026-03-25) — all fields are stored verbatim; retrieval works via `DifficultyPath` | Automated prediction model (ML / heuristic) — Phase 1, after Phase 0 workload data collected |
| Cumulative reputation | DNA 4 coordinator | Single-round reputation only | Multi-round cumulative tier progression |
| Real membrane proof issuance | Outside codebase | Not implemented | A credential issuance service that signs joining agents' pubkeys with the issuer keypair |
| Researcher identity blinding | Outside codebase | Partially improved — `TokenGated` deposits use an opaque `/deposit/<job_id>?token=...` URL that does not expose researcher identity. Public URL deposits (`PublicUrl`) still expose the full URL (e.g. `osf.io/jsmith/my-study`). A full blinding proxy would replace any URL with an opaque token before writing the `ValidationRequest` to the DHT. Until built, identity blinding for `PublicUrl` deposits is an operational convention. |

---

## Shared Types

All cross-DNA types live in `valichord/shared_types/` — a pure `rlib` crate imported by all four DNAs.

**Do not move shared types into an integrity zome.** Integrity zomes compile as `cdylib`. If a type is defined in a `cdylib` and re-exported across crates, you get duplicate symbol errors at link time. The `rlib` pattern is the correct solution.

Key shared types: `Discipline`, `AttestationOutcome`, `AttestationConfidence`, `ComputationalResources`, `TimeBreakdown`, `UndeclaredDeviation`, `ValidationPhase`, `OutcomeSummary`, `MetricResult`, `AgreementLevel`, `CertificationTier`, `ValidatorAgentType`, `discipline_tag()`.

**April 2026 additions (ad4m-inspired refactoring):**

- `ValiChordError` / `ValiChordResult<T>` — domain error enum (`thiserror::Error`) with `#[from]` derivations for `WasmError` and `SerializedBytesError`. `impl From<ValiChordError> for WasmError` allows `?` propagation across the extern boundary. Use `ValiChordResult<T>` as the return type for internal helpers; convert to `ExternResult<T>` at the `#[hdk_extern]` boundary.
- `ValidationAttestation::msgpack_bytes(&self) -> ExternResult<Vec<u8>>` — shared serialisation method. Replaces the ad-hoc `SerializedBytes::try_from(&attestation)...map_err(|e| wasm_error!(...))` pattern that was duplicated in DNA 2 (`seal_private_attestation`) and DNA 3 (`submit_attestation`). Both now call `attestation.msgpack_bytes()?` for byte-for-byte consistency between commit and reveal.
- `derive_majority_outcome(attestations: &[ValidationAttestation]) -> Option<AttestationOutcome>` — pure function, moved from `governance_coordinator` to `shared_types` so it can be unit-tested without a conductor.
- `derive_agreement_level(attestations: &[ValidationAttestation]) -> AgreementLevel` — likewise moved.
- 11 conductor-free unit tests in `shared_types/src/lib.rs` (`#[cfg(test)] mod tests`) covering both outcome functions. Run with `cargo test -p valichord_shared_types` — completes in < 1 s with no conductor, WASM, or network setup.

---

## Hard-Won Engineering Constraints

These are things that took significant debugging time to establish. Do not re-learn them.

### 1. post_commit cannot write data directly
`post_commit` is called after the source chain has been committed. Writing new entries from inside `post_commit` causes a re-entrant deadlock on the cell's operation queue. Cross-DNA `call(OtherRole(...))` IS permitted from `post_commit` — but only to write to a **different** cell, never back to the same one.

### 2. Target cell must be initialised before post_commit fires
`post_commit` in DNA 2 calls `notify_commitment_sealed` in DNA 3. If DNA 3's cell has never been initialised (i.e. `init()` has never run), the `call()` triggers `init()`, which the conductor serialises — deadlock. In production, the UI layer should initialise all cells on startup. In tests, always make a warm-up read call to the attestation cell before calling `seal_private_attestation`.

### 3. Add a pause after seal_private_attestation in tests
`post_commit` is asynchronous. If you call `dhtSync` immediately after `seal_private_attestation`, the `CommitmentAnchor` may not yet be written. Add a `pause(500)` between the seal call and the sync.

### 4. DnaProperties fields must be String, not AgentPubKey
The conductor passes DNA properties as msgpack-encoded YAML strings. Declaring a property as `AgentPubKey` in the struct causes a deserialisation error at startup. Always use `String` and parse to `AgentPubKey` inside the coordinator when needed.

### 5. Enum serialisation — two patterns in use
- `Discipline` and `AttestationOutcome` use `#[serde(tag="type", content="content")]` (adjacent tagging) → serialises as `{ type: "ComputationalBiology" }` on the JS side
- All other enums (`ValidationPhase`, `AgreementLevel`, etc.) use no tag → plain strings

Do not mix these up when writing test fixtures.

### 6. ExternalHash construction in TypeScript tests
Always construct `ExternalHash` using `hashFrom32AndType(core32, HoloHashType.External)`. Never use `new Uint8Array(39).fill(byte)` — the DHT location bytes (last 4 bytes) must be a valid blake2b checksum. Using a flat fill produces hashes that fail DHT validation silently.

### 7. do NOT use pack_dna.py
There is a `pack_dna.py` script in the repo. It has a bug that embeds the attestation DNA bytes for all four roles, meaning every cell requires the attestation membrane proof. Always use `hc dna pack` and `hc app pack` directly.

### 8. Deadlock: DNA 4 calling back into DNA 3
`check_and_create_harmony_record` (DNA 4) calls `get_attestations_for_request` (DNA 3) to retrieve attestations. This is safe because it is a read-only call. Do not add any write calls from DNA 4 back into DNA 3 — this creates a cycle with the pending write operation and deadlocks.

### 9. verify_signature is HDK-only — not available in integrity zomes
Integrity zomes run in a restricted WASM environment without host function access to the keystore. `verify_signature` is an HDK function. All cryptographic verification must go in coordinator zomes, not integrity zomes. The validate() callback in an integrity zome cannot call it.

### 10. Do not use hardcoded ZomeIndex or EntryDefIndex
`get_all_tasks` and `post_commit` in DNA 2 previously filtered entries using hardcoded `ZomeIndex(0)` and `EntryDefIndex(0/1)`. These indices break silently if the order of entry type declarations ever changes. The correct pattern is to filter by attempting deserialization: `r.entry().to_app_option::<MyType>().ok().flatten().is_some()`. Any coordinator function that needs to identify a specific entry type from the source chain must use this pattern.

### 11. dhtSync with 7+ conductors exhausts websocket connections in Codespaces
The Tryorama Gold badge test (7 validators) is `test.skip` because spinning up 7 simultaneous Holochain conductors exhausts available websocket connections in resource-constrained environments (Codespaces, CI with <16GB RAM). **The sweettest equivalent (`gold_badge_issued_with_seven_validators` in `sweettest_integration/tests/governance.rs`) passes** — in-process conductors avoid the websocket overhead and are the authoritative coverage for this scenario.

### 12. get_private_attestation_for_task — use query(), not get()
Private entries retrieved by the owning agent must be looked up via `query()`, not `get(target, GetOptions::local())`. In singleFork Tryorama tests, all cells share the same conductor and local DB, so `get()` with local options crosses cell boundaries — Bob's cell can retrieve Alice's private entry. `query()` is strictly bound to the calling agent's source chain and cannot cross this boundary. Pattern: follow the link to get the target ActionHash, then `query(ChainQueryFilter::new().include_entries(true))?.into_iter().find(|r| *r.action_address() == target)`.

### 13. Fire-and-forget cross-DNA calls use a named helper, not inline `call()`
`submit_attestation` in DNA 3 fires a same-agent call to `check_and_create_harmony_record` in DNA 4 after writing each attestation. This pattern is wrapped in `call_governance_fire_and_forget(fn_name, input)` — a private helper that swallows errors with `let _ = call(...)`. Failures are intentionally ignored (the caller still continues); if every validator's reveal silently drops the governance call, the HarmonyRecord simply doesn't appear yet — any participant can re-trigger `check_and_create_harmony_record` later. Do not unwrap the result; do not panic. The one-liner suppresses the `unused Result` warning and makes the intent explicit.

### 15. get() after get_links() can return None — return Ok(None), not Err

DHT gossip propagation is not atomic. When conductor A writes a record and conductor B follows a link to it immediately after, `get(target, GetOptions::network())` can return `None` even though the link itself is visible — the link gossips faster than the record body.

**Rule:** any coordinator function that resolves a link to a record written by another conductor must treat `None` as a retryable miss, not a hard error. Return `Ok(None)` (or the `Option<T>` variant) so the JavaScript caller can retry.

`get_current_phase` follows this pattern: if the `PhaseMarker` link exists but `get(target, GetOptions::network())` returns `None`, the function returns `Ok(None)`. The JavaScript poll loop retries. If it returned `Err`, every gossip-lag window would surface a 502 to the user.

This pattern generalises: any `get()` call that follows a link written by a different agent on a different conductor must be inside a retry loop on the caller side, OR must return `Option<T>` with `None` meaning "not yet propagated".

### 16. Idempotency functions must return the existing value, not None

A function that short-circuits on "already exists" must return the existing entry hash to the caller so the caller can proceed.

`check_and_create_harmony_record` previously returned `Ok(None)` when a `HarmonyRecord` already existed — treating "already done" the same as "couldn't do it". The JavaScript caller saw `null` and reported failure. Fixed: it now returns `Ok(Some(existing_hash))`.

**Rule:** idempotency guards that find an existing entry must return `Ok(Some(existing_hash))`, not `Ok(None)`.

### 17. Trust PhaseMarker for phase gates — do not re-query links

`reveal_researcher_result` previously called `check_all_commitments_sealed_inner` as a safety check, re-querying `RequestToCommitment` links to count how many validators had committed. This races with DHT gossip: even after `PhaseMarker(RevealOpen)` exists, not all `CommitmentAnchor` links may have propagated to the researcher's conductor — the count is falsely low and the function rejects the call.

Fixed: `reveal_researcher_result` now checks `get_current_phase`. If it returns `Some(ValidationPhase::RevealOpen)`, the function proceeds. The `PhaseMarker` is the authoritative quorum record — it was written by a validator only after all required `CommitmentAnchor` entries were visible to that validator. Re-querying links after the fact introduces a race.

**Rule:** once a `PhaseMarker` says `RevealOpen`, trust it. Do not re-verify preconditions by re-querying the links that caused the phase transition. The phase marker IS the proof of completion.

### 18. Cross-DNA decode failures under gossip lag should be soft errors

`call_attestation_zome_opt` in the governance coordinator wraps cross-DNA calls to the Attestation DNA. Under DHT gossip lag, the attestation entries may not yet be deserializable on the governance conductor. A hard decode error propagated as `Err` surfaces a 502 to the caller and aborts the round.

Fixed: `call_attestation_zome_opt` catches `ZomeCallResponse::Ok(io)` where `io.decode::<O>()` fails, logs at `warn!`, and returns `Ok(None)`. The caller (`check_and_create_harmony_record`) retries.

**Rule:** cross-DNA calls that retrieve data published by another conductor should treat decode failures during the gossip propagation window as `Ok(None)` — not hard errors. Always log at `warn!` so the condition is visible in logs, but allow the caller to retry.

### 14. reveal_researcher_result — idempotency guard required before hash check
`reveal_researcher_result` checks for an existing `RequestToResearcherReveal` link **before** the SHA-256 hash verification step. Without this guard, a researcher could call the function multiple times, creating multiple `ResearcherReveal` entries linked from the same deterministic path. `get_researcher_reveal` uses `links.last()`, which is non-deterministic under concurrent DHT propagation, so duplicate entries introduce result ambiguity even though content is forced to match the commitment. Pattern mirrors `publish_researcher_commitment`: query the path's existing links at the top of the function and return an error immediately if any exist. Commitment hash for `metrics=[], nonce=[]` is `SHA256(0x90) = 9e076ceaf246b6003d9c2680a2b4cf0bffd069805902b0b5edeebf49039fe4bd` — used in S6 test fixture.

### 19. validate() deserialization failures must be soft — return Invalid, not wasm_error

Inside a validate() callback, `to_app_option::<T>()` returns a `Result<Option<T>, SerializedBytesError>`. If deserialization fails, the entry under validation is malformed — a protocol-level bad entry, not a system failure. Using `.map_err(|e| wasm_error!(WasmErrorInner::Guest(e.to_string())))?` on that error propagates it as a hard WASM host error — the same error class as an out-of-memory fault. The validation callback crashes non-recoverably. Peers that hold that entry cannot validate it; the entry becomes permanently stuck.

The correct pattern is to return `ValidateCallbackResult::Invalid(...)`, which cleanly rejects the entry and lets the network continue. Use the `handle_error!` macro:

```rust
macro_rules! handle_error {
    ($e:expr) => {
        match $e {
            Ok(v) => v,
            Err(e) => return Ok(ValidateCallbackResult::Invalid(e.to_string())),
        }
    };
}

// Usage:
let maybe_req: Option<ValidationRequest> = handle_error!(record.entry().to_app_option());
let req = match maybe_req {
    Some(r) => r,
    None => return Ok(ValidateCallbackResult::Invalid("entry is not a ValidationRequest".into())),
};
```

Do not use `.ok_or_else(|| wasm_error!(...))` for the `None` arm either — use an explicit match returning `Invalid`. Same rule applies to missing required fields (`Option<ActionHash>` that must be `Some`): use a match, not `ok_or_else(|| wasm_error!(...))`.

Applied to five sites in `governance_integrity` and `attestation_integrity` in commit `985ff20`.

---

## Build Sequence

```bash
# 1. Rust WASM toolchain
rustup target add wasm32-unknown-unknown

# 2. Holochain CLI
cargo install holochain hc --locked

# 3. Node dependencies
cd tests && npm install && cd ..

# 4. Set PATH (Codespaces / CI)
export PATH="/home/codespace/.cargo/bin:$PATH"

# 5. Compile all four WASM zomes
cargo build --target wasm32-unknown-unknown --release

# 6. Pack each DNA — always use hc directly
hc dna pack dnas/attestation            -o workdir/attestation.dna
hc dna pack dnas/researcher_repository  -o workdir/researcher_repository.dna
hc dna pack dnas/validator_workspace    -o workdir/validator_workspace.dna
hc dna pack dnas/governance             -o workdir/governance.dna

# 7. Pack the hApp bundles
hc app pack .            -o workdir/valichord.happ    # full 4-DNA bundle (tests)
hc app pack researcher   -o workdir/researcher.happ   # DNAs 1+3+4 (decentralised demo)
hc app pack validator    -o workdir/validator.happ     # DNAs 2+3+4 (decentralised demo)

# 8. Run targeted tests (preferred)
cd tests && npm test -- -t "Membrane proof"
cd tests && npm test -- -t "governance"

# 9. Full suite (takes ~90 minutes in Codespaces — only when needed)
cd tests && npm test
```

**Role-filtered happs** (`researcher.happ`, `validator.happ`) are committed to `valichord/workdir/` as demo artefacts. They are used by the Docker Compose decentralised demo — each container loads only the DNAs it needs for that run. `valichord.happ` (all four DNAs) is used by the Tryorama integration tests and is the correct bundle for production deployment.

**Production model:** every participant runs the full four-DNA bundle. The same person may submit a study one day and validate a different study another day — DNA 1 holds their research deposits and DNA 2 holds their validation work. The conflict-of-interest check is per-study (`StudyClaim validate()` rejects the same agent as both submitter and claimant of the same `ValidationRequest`), not per-person. Do not use the role-filtered happs as a template for production; they exist purely to save memory and clarify roles in the single-machine demo.

The `.gitignore` tracks all three via explicit `!workdir/*.happ` exceptions. Rebuild them whenever you change any Rust zome code.

---

## Test Inventory Summary

97 Tryorama tests across 5 files, 1 skipped (GoldReproducible — hardware-constrained; sweettest equivalent passes).

| File | Tests | Coverage |
|---|---|---|
| `attestation.test.ts` | 46 (1 Tryorama-skipped) | Membrane proof, commit-reveal, phase poll, immutability, profiles, requests, discipline query, cross-DNA post_commit, real Ed25519 verification, badge thresholds (Bronze/Silver/Gold), `get_validation_request_for_data_hash`, `get_validators_for_institution`, `get_attestations_for_discipline`, validator self-assignment (StudyClaim), dropout recovery (`reclaim_abandoned_claim`) — too-recent guard, eligible reclaim + slot freed, attested validator guard |
| `governance.test.ts` | 24 | Idempotency, author enforcement, end-to-end round, reputation, read queries, Bronze/Silver/Failed badges, mixed outcomes, `GovernanceDecision` CRUD, `get_badges_by_type`, delete-immutability guards, `force_finalize_round` — not-yet-timed-out guard, no-attestations guard |
| `researcher_repository.test.ts` | 14 | All coordinator functions, immutability enforcement, `get_all_studies` |
| `validator_workspace.test.ts` | 7 | All coordinator functions, multi-task retrieval, `get_all_private_attestations` |
| `security.test.ts` | 9 | S1 duplicate attestation, S2 duplicate commitment, S3 researcher commitment idempotency, S4.1 reclaim timeout floor enforced, S4.2 zero floor allows immediate reclaim, S5 force_finalize_round conservative abort on missing VR, S6 reveal_researcher_result idempotency, S7 self-claim prevention (researcher cannot claim own study), S8 capacity-full rejection |

Full test inventory: `valichord/tests/README.md`

### Sweettest (native Rust integration tests)

A separate Rust-native test suite lives in `valichord/sweettest_integration/`. **64 tests across 5 files** covering all four DNAs. These tests use `SweetConductor` / `SweetApp` directly in Rust — no Node.js runtime, no WebSocket overhead. They are the preferred home for new security and protocol tests because they compile alongside the WASM and are checked by `cargo test`.

CI splits the sweettest suite into 5 parallel matrix jobs (`attestation`, `governance`, `researcher_repository`, `validator_workspace`, `security`) to stay under GitHub Actions job time limits. The Tryorama suite (`valichord/tests/`) runs as a single additional job.

Run locally: `cd valichord && cargo test --test '*' -- --nocapture`

---

## Deferred Decisions

These are architectural questions that have been explicitly deferred to Phase 1. They are not oversights — they require Phase 0 empirical data or real operational experience before they can be answered well.

**Countersigning for simultaneous reveal.** The current design uses DHT-poll-driven sequential reveals. CommitmentAnchor already prevents last-mover advantage — a validator cannot see others' outcomes before committing their own. True Holochain countersigning would enforce mathematical simultaneity but requires all validators online at the same moment, which is operationally inappropriate for Phase 0. Revisit in Phase 2.

**Validator assignment.** Validator self-assignment via `claim_study` is now implemented — validators discover studies via `get_pending_requests_for_discipline` and self-select, with COI enforcement (same institution as researcher) and capacity limits enforced at the protocol level. `select_validators()` (central algorithmic assignment with reputation-weighted constrained randomisation, institutional balance caps, and co-authorship detection) remains a stub — the data to calibrate it comes from Phase 0.

**Compensation tiers.** `CompensationTier` is defined in shared_types. The actual tier values are placeholders. Phase 0 empirical workload data determines real compensation rates.

**Difficulty assessment prediction.** `assess_difficulty()` stores a `DifficultyAssessment` entry. The retrieval works. The prediction model — whether surface features (code quality, documentation, dependency count) actually predict validation workload — is Phase 0's primary research question. Do not hard-code a prediction model until Phase 0 data exists.

**Membrane proof issuance service.** The credential verification is implemented and tested. What does not exist yet is the external service that issues credentials — signs a joining agent's pubkey with the authorised issuer keypair and returns the 64-byte proof. This is a Phase 1 infrastructure component. In dev/test mode, set `authorized_joining_certificate_issuer = ""` to bypass.

**HTTP Gateway deployment.** DNA 4 is designed as an HTTP Gateway target — publicly readable without a Holochain node. **Demo deployed 2026-03-28** — `hc-http-gw` v0.3.1 runs on port 8090 in the Codespace alongside the conductor; `demo/start-gateway.sh` starts it. Env vars `HOLOCHAIN_GATEWAY_URL`, `HOLOCHAIN_GOVERNANCE_DNA_HASH`, and `HOLOCHAIN_APP_ID` set on the Flask server populate `harmony_record_url` in every `/result/<job_id>` response. Always-on permanent deployment (outside the Codespace) remains Phase 1.

**Cryptographic commitment verification — FULLY RESOLVED 2026-03-18/20.**

**Researcher side (fully implemented, 2026-03-18):** The full symmetric researcher commit-reveal is complete. The commitment is a two-way blind: it prevents the researcher from adjusting their claimed values after seeing validator outputs, and it prevents validators from seeing the researcher's actual metric values before they commit their own verdicts (only the hash is on the DHT during the commit phase).
- DNA 1 `lock_researcher_result(LockResultInput { request_ref, metrics: Vec<MetricResult> })` — generates nonce, computes `SHA-256(rmp_serde::to_vec_named(metrics) || nonce)`, stores private `LockedResult { request_ref, metrics, nonce, commitment_hash }` (immutable, private, never leaves device), calls `publish_researcher_commitment` in DNA 3.
- DNA 1 `get_locked_result(request_ref)` — retrieves the private entry at reveal time.
- DNA 3 `reveal_researcher_result(ResearcherRevealInput { request_ref, metrics, nonce })` — gates on `check_all_commitments_sealed`, verifies hash on-chain against `ResearcherResultCommitment`, writes immutable `ResearcherReveal { request_ref, metrics }` to DHT.
- DNA 3 `get_researcher_reveal(request_ref)` — unrestricted read.
- `ResearcherReveal` is immutable — update + delete both rejected by `validate()`.

**Validator reveal-side (RESOLVED 2026-03-20):** `submit_attestation` now takes `AttestationRevealInput { attestation: ValidationAttestation, nonce: Vec<u8> }`. It recomputes `SHA-256(msgpack(attestation) || nonce)` and compares against the `CommitmentAnchor.commitment_hash` written during the commit phase. A hash mismatch or missing anchor is rejected with a hard error. This closes the adaptive-reveal attack — a validator cannot reveal a different attestation than they committed to.

**Commit-phase guards (RESOLVED 2026-03-20):** `notify_commitment_sealed` now enforces two guards before writing a `CommitmentAnchor`:
1. The caller must hold a live `StudyClaim` for the study (prevents non-claimants from inflating the commitment quorum).
2. Each validator may only submit one commitment per study (prevents a single agent satisfying the quorum alone).

**Researcher identity blinding proxy.** Double-blind validation (validators cannot see researcher identity) is a design goal but is not architecturally enforced in the current implementation. `ValidationRequest.data_access_url` is visible to validators in full — if it contains researcher-identifying information (e.g. `osf.io/jsmith/my-study`), the blinding is defeated. `researcher_institution` is used server-side only for COI enforcement and is not displayed to validators, but this is a convention not a structural constraint. The fix is a blinding proxy service that replaces the original URL with an opaque token before the `ValidationRequest` is written to the DHT. Until built, double-blinding is an operational convention enforced by the ValiChord team. The commit-reveal blindness (validators cannot see *each other's findings*) is fully implemented and architecturally enforced — these are two distinct properties and only the latter is guaranteed today.

---

## Security Audit Summary (March – April 2026)

Five LLM red-team audits (ChatGPT, Gemini, Grok ×2, Claude) and two systematic self-audits were run against the full codebase. Findings and dispositions are recorded here for future auditors.

### Implemented fixes

| Fix | Finding source | Severity | What was done |
|---|---|---|---|
| `ValidationRequest` immutability | Gemini | High | `validate()` now rejects updates and deletes — researchers cannot silently lower `num_validators_required` after submission |
| `get_num_validators_required` safe default | Gemini | High | `unwrap_or(1)` removed; function now returns `Err` if the ValidationRequest is not found, preventing a single attestation from finalising any study |
| `force_finalize_round` removed from Unrestricted cap grant | Gemini | Medium | Write function was previously callable by anonymous HTTP Gateway clients |
| Conservative quorum fallback in governance | Gemini | Medium | `Err(_) => return Ok(None)` instead of `unwrap_or(1u8)` — a decode failure no longer allows premature finalisation |
| Validator reveal binding (`submit_attestation`) | ChatGPT | Critical | Now takes `AttestationRevealInput { attestation, nonce }`; verifies `SHA-256(msgpack(attestation) \|\| nonce) == CommitmentAnchor.commitment_hash` before writing |
| Commitment uniqueness + claim binding (`notify_commitment_sealed`) | ChatGPT | High | Two new guards: (1) caller must hold a live `StudyClaim`; (2) one commitment per validator per study |
| HarmonyRecord author guard | Grok | High | `validate()` in governance_integrity now requires `action.author ∈ record.participating_validators` — prevents outsider forgery winning the idempotency race |
| `num_validators_required` minimum enforcement | Gemini (second audit) | High | New `validate()` arm for `ValidationRequest` create checks `vr.num_validators_required >= props.minimum_validators`; `minimum_validators = 0` is the dev/test bypass |
| Membrane proof comment corrected | Grok (first) | Low | Comment incorrectly said `rmp_serde` encodes `Vec<u8>` as "msgpack array of unsigned integers" — it encodes as msgpack **bin** format. JS issuer must use `Buffer.from`/`Uint8Array`, not `Array.from` |
| `ValidatorReputation` write gate | Grok (second) | High | `validate()` arms for `ValidatorReputation` create and update were `Valid` unconditionally — anyone could mint or alter reputation scores. Both now check `action.author == system_coordinator_key` (empty = dev/test bypass) |
| `get_harmony_record` uses `.last()` | Grok (second) | Low | Was `.first()` — defensive: idempotency guard should prevent duplicates, but `.last()` is consistent with `get_validator_reputation` and more robust if gossip delivers links out of order |
| Stale `harmony_record_creator_key` removed | Grok (second) | Low | Key was present in `governance/dna.yaml` and `happ.yaml` but absent from `DnaProperties` struct (silently ignored). Removed to eliminate confusion; doc comments updated |
| `reclaim_abandoned_claim` timeout bypass | Self-audit | High | `timeout_secs` was fully caller-controlled — anyone could pass `0` to instantly reclaim any live claim. Added `min_claim_timeout_secs` DNA property (`#[serde(default)]` preserves test behaviour; `0` = bypass). |
| `publish_researcher_commitment` idempotency | Self-audit | High | Researcher could publish multiple commitments, changing their locked prediction after validators started work. Guard now rejects a second commitment for the same `request_ref`. |
| `submit_attestation` double-vote | Self-audit | High | Validator could submit the same attestation+nonce multiple times (one CommitmentAnchor, N identical reveals), gaining N-fold vote weight in the HarmonyRecord plurality tally. Guard prevents duplicate reveals. |
| `force_finalize_round` timeout bypass when VR absent | Self-audit | High | When `get_validation_request_for_data_hash` returned `None`, the `if let` fell through silently and immediately finalised the round without checking the 7-day timeout. Replaced with `match`; `None` → `return Ok(None)` conservatively. |
| `RequestToCommitment` link deletion griefing | Self-audit | High | No validate() guard blocked validators from deleting their own commitment links, dropping the commitment count below the reveal-phase threshold and blocking `reveal_researcher_result` indefinitely. `RegisterDeleteLink` guard added. |
| `ReproducibilityBadge` open create | Self-audit | High | Any credentialed participant could issue a fake badge for any study. `validate()` now requires: (a) `harmony_record_ref` points to a live `HarmonyRecord`, (b) `badge.study_ref == HarmonyRecord.request_ref`, (c) badge author is in `participating_validators`. |
| `RequestToHarmonyRecord` / `StudyToBadge` / `AllDecisions` link deletion | Self-audit | High | A validator who triggered finalisation could delete these index links, hiding outcomes and badges from all future queries (entries themselves are immutable, but their index links were not). `RegisterDeleteLink` guards added in governance_integrity. |
| Badge recipient fallback to wrong agent | Self-audit | Medium | If the researcher's pubkey could not be resolved, `write_harmony_record` issued the badge to the first participating validator. Badge issuance is now skipped entirely if researcher identity is unknown. |
| Automatic reputation update silently fails in production | Self-audit | Medium | `_update_reputation_internal` is called from `write_harmony_record` but always fails if `system_coordinator_key` is set (validate() rejects non-coordinator creates). Wrapped in `system_coordinator_key.is_empty()` guard; production uses `update_validator_reputation` explicitly. |
| `StudyClaim.request_ref` ↔ `ValidationRequest.data_hash` cross-check | Self-audit | Low (defence-in-depth) | validate() now confirms these two fields reference the same study, closing a theoretical COI-bypass where a crafted claim references a benign `ValidationRequest` for the COI check while targeting a different study. |
| `ValidatorToReputation` link-tag ordering | Code review (2026-03-24) | Low — correctness | `_update_reputation_internal` now encodes `total_validations` as 8 big-endian bytes in the `LinkTag`. `get_validator_reputation` selects the record with the highest tag value via `.max_by_key()` instead of `.last()`. Prevents non-deterministic gossip ordering from returning a stale reputation record when two updates arrive in the same DHT batch. Old links (no tag) return count = 0 and always lose to any tagged link — backwards-compatible. |
| Cross-DNA call boilerplate in governance coordinator | Code review (2026-03-24) | Low — maintainability | The repeated `call(CallTargetCell::OtherRole("attestation"), ...) / match ZomeCallResponse::Ok(...) => decode, _ => return Ok(None)` pattern appeared four times in `check_and_create_harmony_record`, `force_finalize_round`, and `write_harmony_record`. Extracted into `call_attestation_zome_opt<I,O>()` typed helper. No behaviour change. |
| `AgentToProfile` link ordering — `.first()` returns oldest profile | Code review (2026-03-25) | Medium — correctness | `get_validator_profile` used `.first()` which returns the *oldest* profile, not the latest. `update_validator_profile`, `get_validator_agent_type`, and `claim_study` used `.last()` which is non-deterministic under DHT gossip. All four fixed: `publish_validator_profile` now tags each `AgentToProfile` link with an 8-byte big-endian `i64` microsecond timestamp; reads use `.max_by_key(\|l\| profile_link_ts(l))`. `profile_link_ts()` returns `i64::MIN` for untagged old links — backwards-compatible. Pattern mirrors `ValidatorToReputation` fix. |
| `assess_difficulty` hardcoded stub unusable | Code review (2026-03-25) | Low — correctness | Function accepted only `request_ref` and returned all fields hardcoded (e.g. `code_volume = 3`). Replaced with `AssessDifficultyInput` struct — assessor supplies all fields; coordinator validates `predicted_min_secs ≤ predicted_max_secs` and stores verbatim. Phase 0 collects real assessments to calibrate whether surface features predict workload. |
| O(n²) DHT reads in `get_attestations_for_request` | Efficiency audit (2026-03-25) | High — runtime | For n committed validators, the function fired n `get_links(ValidatorToAttestation)` calls and then fetched+deserialised every attestation entry per validator to filter by `request_ref` — O(n×m) network calls total. Fixed: `ValidatorToAttestation` links are now tagged with the 39-byte `request_ref`. `get_attestations_for_request` uses a `tag_prefix` query per validator, returning at most 1 link per validator with no entry deserialisation needed. |
| O(n) `get()` calls for duplicate-submission guard in `submit_attestation` | Efficiency audit (2026-03-25) | High — runtime | Guard deserialized every existing `ValidatorToAttestation` entry to check `a.request_ref == request_ref`. Fixed: single `get_links` with `tag_prefix` — returns non-empty iff already attested; zero `get()` calls. |
| `ValidatorToAttestation` link created with `()` tag | Efficiency audit (2026-03-25) | High — enables above fixes | Tag is now the 39-byte `request_ref` bytes. All consumers that previously needed to fetch+deserialise attestation entries to find the right study can now use the tag prefix directly. |
| `get_latest_validator_profile` inline duplication | Efficiency audit (2026-03-25) | Medium — maintainability | The 6-line pattern (get AgentToProfile links → max_by_key timestamp → get() → deserialise) was inlined identically in `update_validator_profile`, `get_validator_agent_type`, and `claim_study`. Extracted into `get_latest_validator_profile(agent)` helper. |
| `zip` misalignment in `write_harmony_record` | Efficiency audit (2026-03-25) | Medium — correctness | `participating_validators` was built from all `attestation_records` (no filter), while `attestations` was built with a filter_map that skips records failing deserialisation. If any record failed, zip silently dropped entries. Fixed: both vecs now derived from the same `(AgentPubKey, ValidationAttestation)` pair collection — always aligned. |
| Four passes over attestation slice in `write_harmony_record` | Efficiency audit (2026-03-25) | Low — runtime | `derive_majority_outcome`, `derive_agreement_level`, `attestations.iter().max()`, and `attestations.first()` were four separate iterations. Discipline+duration are now computed in a single loop. |
| Dead code: `select_validators`, `detect_gaming_patterns`, `AssignmentConstraints`, `GamingFlag` | Efficiency audit (2026-03-25) | Low — WASM size | Phase 1 placeholder stubs that returned empty results and were never called. Removed to reduce WASM binary size. Phase 1 implementations will be added fresh when the data to calibrate them is available. |
| Unnecessary `attestation.clone()` in `submit_attestation` | Efficiency audit (2026-03-25) | Low — allocation | `attestation` was cloned before `create_entry` despite not being used afterwards. Changed to move. |
| Inductive validation gap: `CommitmentAnchor` not linked to `ValidationRequest` | External audit (2026-03-25) | High — protocol integrity | `CommitmentAnchor` had no back-reference to its `ValidationRequest`. A validator with a valid membrane proof could write a `CommitmentAnchor` with a fabricated `request_ref` matching no real study. Fixed: `CommitmentAnchor.validation_request_hash: ActionHash` added; `notify_commitment_sealed` resolves the hash via `study.{request_ref}` path; `validate()` calls `must_get_valid_record` and verifies `vr.data_hash == anchor.request_ref` and `anchor.validator == action.author`. |
| Inductive validation gap: `ValidationAttestation` not linked to `CommitmentAnchor` | External audit (2026-03-25) | High — protocol integrity | `ValidationAttestation` had no back-reference to the `CommitmentAnchor` written during the commit phase. A validator could submit an attestation whose `request_ref` matched no prior commitment. Fixed: `ValidationAttestation.commitment_anchor_hash: Option<ActionHash>` added (optional for backwards compat; always `Some` on new entries); `submit_attestation` finds the anchor first, verifies the hash (production only), then injects `commitment_anchor_hash`; `validate()` calls `must_get_valid_record` and verifies `anchor.validator == action.author` and `anchor.request_ref == att.request_ref`. Hash verification uses the attestation before the anchor hash is injected (consistent with what the validator sealed). |
| `AgentIdentityAttestation` authorship gap | Self-audit (2026-03-25) | High — protocol integrity | `validate()` only checked `agent_a ≠ agent_b` — it did not verify that the entry author was one of the two named agents. Any credentialed validator could write an `AgentIdentityAttestation` linking two other agents' keys and forge their identity relationship. Fixed: `validate()` now requires `action.author ∈ {agent_a, agent_b}`; the coordinator's dual-signature check is the primary guard, but the integrity layer now provides a defence-in-depth backstop. |
| Self-claim prevention | Second self-audit (2026-04-17) | High — protocol integrity | A researcher could call `claim_study` on their own `ValidationRequest` — they would be both poser of the research question and validator, defeating the independence property. Fixed: `StudyClaim validate()` fetches the linked `ValidationRequest` via `must_get_valid_record` and compares `create_action.author` against `vr.action().author()`. Guard has no dev/test bypass. Covered by S7 regression test. |
| N+1 DHT round-trips in claim functions | Efficiency audit (2026-04-17) | High — runtime | `claim_study`, `get_claims_for_request`, and `get_my_claimed_studies` each issued one `get_links(ClaimToRelease)` per claim — O(N) round-trips. Fixed with `RequestToRelease` and `ValidatorToRelease` index link types; all three functions now do a single `get_links` + O(1) set lookup. |
| Non-deterministic `links.last()` at 5 call sites | Efficiency/correctness audit (2026-04-17) | Medium — correctness | `get_difficulty_assessment`, `get_current_phase`, `get_researcher_commitment`, `get_researcher_reveal` (DNA 3) and `get_harmony_record` (DNA 4) used `links.last()` — gossip-order-dependent. All five replaced with `links.iter().max_by_key(\|l\| l.timestamp)`. |
| Researcher reveal impersonation in production mode | Second self-audit (2026-04-17) | High — protocol integrity | `reveal_researcher_result` had no author check — any credentialed agent could publish a structured reveal for a study they did not submit, poisoning the comparison between researcher claim and validator findings. Fixed: in production mode (non-empty issuer key), the function now verifies `caller == ValidationRequest.action().author()`. Dev/test bypass: empty issuer key. |
| PhaseMarker duplicate write (TOCTOU) | Second self-audit (2026-04-17) | Medium — correctness | Two validators simultaneously detecting quorum completion would both pass the `existing_phase.is_empty()` check before either write landed on the DHT. Fixed: `notify_commitment_sealed` checks `get_links(RequestToPhaseMarker)` before writing; the second concurrent writer sees the existing link and skips. Signals fire regardless. |
| `attestation_request_ref` verification in governance finalization | Second self-audit (2026-04-17) | High — protocol integrity | `check_and_create_harmony_record` and `force_finalize_round` in DNA 4 accepted any set of attestation records without verifying all shared the same `request_ref`. An attacker with multiple valid attestations for different studies could blend them into a single `HarmonyRecord`. Fixed: both functions now verify `all(attestation.request_ref == request_ref)` before proceeding; any mismatch returns `Ok(None)`. |
| `HarmonyRecord` TOCTOU deterministic sort | Self-audit (2026-03-25) | Low — correctness | Two governance cells triggering finalization simultaneously both see an empty `RequestToHarmonyRecord` link list and proceed to call `write_harmony_record`. Each builds a `HarmonyRecord` from the same attestation set. If `pairs` were in arbitrary iteration order, the two records could have different content and different entry hashes — the DHT would store two conflicting records for the same round. Fixed: `pairs` is now sorted by `AgentPubKey` raw bytes before building the record, making content deterministic across concurrent writes. Holochain content-addressing then collapses both writes to the same entry hash — the race becomes benign. |
| Duplicate identity link prevention | Self-audit (2026-03-25) | Low — data integrity | `link_agent_identity` did not check whether an attestation between the same pair already existed. Repeated calls created multiple `AgentIdentityAttestation` entries and corresponding link sets for the same agent pair. Fixed: coordinator queries existing `AgentToIdentityAttestation` links (both directions) and rejects the call with `InvalidInput` if a live attestation for the pair already exists. |
| Adaptive-reveal via re-sealing | Red-team audit (2026-04-20) | Critical — protocol integrity | `seal_private_attestation` (DNA 2) had no idempotency guard. A validator could let `post_commit` fail (leaving no `CommitmentAnchor` on DNA 3), observe other validators' public reveals, then re-seal with a favourable verdict and a fresh nonce. Once a `TaskToPrivateAttestation` link exists, the commitment is considered filed regardless of whether `notify_commitment_sealed` succeeded. Guard added at the top of `seal_private_attestation`: queries existing `TaskToPrivateAttestation` links and returns an error immediately if any exist. |
| Late commit after RevealOpen | Red-team audit (2026-04-20) | Medium — protocol integrity | `notify_commitment_sealed` (DNA 3) did not check the current phase before writing a `CommitmentAnchor`. A validator who had not committed before the reveal window opened could slip in a new anchor with knowledge of what other validators found. Phase gate added at function entry: if `get_current_phase` returns `RevealOpen`, the call is rejected before any DHT write. |
| `lock_researcher_result` double-lock | Red-team audit (2026-04-20) | Medium — protocol integrity | `lock_researcher_result` (DNA 1) could be called twice with different nonces. The second call created a new `LockedResult` while the `ResearcherResultCommitment` on DNA 3 was fixed to the first nonce. `get_locked_result` (which uses timestamp-max selection) would return the newer entry at reveal time, causing a permanent hash mismatch and stalling the round. Guard added: checks for an existing `RequestToLockedResult` link before proceeding; fails if one exists. |
| `CommitmentAnchor.commitment_hash` length unvalidated | Red-team audit (2026-04-20) | Medium — protocol integrity | Any credentialed actor could write a `CommitmentAnchor` with a truncated or padded `commitment_hash`. The SHA-256 verification in `submit_attestation` would always fail for such an anchor, blocking the reveal phase permanently for the affected round. `attestation_integrity validate()` now rejects `CommitmentAnchor` creates where `commitment_hash.len() != 32`. |
| `discipline_tag` dot-injection | Red-team audit (2026-04-20) | Low — data integrity | `Discipline::Other("foo.bar")` produced `"other_foo.bar"` via `discipline_tag()` — a string with an embedded dot that Holochain's `Path` treats as a path separator. Attestations for such a discipline would be indexed under `attestations.other_foo.bar` (a two-level path) rather than the intended `attestations.other_foo_bar` bucket. Fixed: `.replace('.', "_")` applied after `.to_lowercase()` in `shared_types/src/lib.rs`. |
| Reputation zip mismatch in `write_harmony_record` | Efficiency/correctness audit (2026-04-20) | Medium — correctness | `write_harmony_record` (DNA 4) zipped `attestation_records` (gossip-delivery order, unsorted) with `attestations` (sorted by validator `AgentPubKey` raw bytes from the deterministic `pairs` sort). When indices diverged, validators were credited for the wrong discipline and outcome in the reputation update loop. Fixed: the `_update_reputation_internal` loop now zips `participating_validators` with `attestations`, both derived from the same sorted `pairs` — ordering is guaranteed consistent. |
| `get_locked_result` non-deterministic link selection | Correctness audit (2026-04-20) | Low — correctness | `get_locked_result` (DNA 1) used `links.last()` to select the `RequestToLockedResult` link — gossip-order-dependent, inconsistent with every other link-selection site in the codebase (all use `max_by_key(timestamp)`). In theory a duplicate lock could have landed out of gossip order. Fixed to `links.iter().max_by_key(|l| l.timestamp)`. |
| `HarmonyRecord` duplicate-validator padding + quorum floor | Claude red-team audit (2026-04-20) | Critical — protocol integrity | `governance_integrity validate()` for `HarmonyRecord` creates now checks: (1) `participating_validators` contains no duplicate `AgentPubKey` entries (HashSet dedup — prevents one colluding validator padding a fabricated record with copied keys to satisfy count-based checks); (2) `len(participating_validators) >= max(1, min_attestations_for_finalization)` — enforces the network quorum floor at the DHT layer, not just at the coordinator. |
| Retroactive oracle attack via late `publish_researcher_commitment` | Claude red-team audit (2026-04-20) | Critical — protocol integrity | `notify_commitment_sealed` (DNA 3) now enforces ordering: in production mode (non-empty `authorized_joining_certificate_issuer`), the `ResearcherResultCommitment` must already exist on the DHT before any validator may write a `CommitmentAnchor`. Without this, a researcher could wait for all validators to publicly reveal their findings, then craft metrics matching the majority and retroactively publish their "pre-registration". Dev/test bypass: empty issuer key (same pattern as all other guards). Guard 2 in the Guard 1→2→3 sequence. |
| `ReproducibilityBadge` type not integrity-enforced | Claude red-team audit (2026-04-20, revised 2026-04-26) | High — protocol integrity | `governance_integrity` now contains a `badge_ceiling()` helper (formerly `evaluate_badge_type()`) that derives the maximum permissible badge tier from raw participant count and agreement level (Gold ≥7 ExactMatch, Silver ≥5, Bronze ≥3, FailedReproduction ≥3 Divergent/UnableToAssess). The `ReproducibilityBadge` validate arm now applies an **upper-bound check**: the issued badge tier must not exceed the ceiling, but may be lower (coordinators are permitted to issue Bronze when the network is small regardless of what the ceiling allows). Direction consistency is also enforced (Reproduced-track badges for positive agreements, FailedReproduction for negative). This replaced an earlier exact-match check that incorrectly rejected valid badges. `evaluate_badge()` in `governance_coordinator` uses the identical raw-count formula — coordinator and integrity are now fully consistent; no Phase 1 divergence. |
| AI validator credential path | Self-audit (2026-04-26) | Medium — integration | Human validators join via a certificate signed by `authorized_joining_certificate_issuer` (institutional credential). AI validators have no institutional affiliation. Added `ai_validator_issuer: String` (default `""`) to attestation `DnaProperties`. `verify_membrane_proof` in the coordinator now parses the `JoiningCertificate.validator_type` first and routes AI certificates to the `ai_validator_issuer` key. Human certificates continue to use `authorized_joining_certificate_issuer`. When `ai_validator_issuer` is empty, AI certificates fall back to the human issuer key (single-key deployments). Empty `authorized_joining_certificate_issuer` = dev/test bypass for both paths (unchanged). |
| `FailedReproduction` minimum validator threshold | Claude red-team audit (2026-04-20) | High — protocol integrity | `evaluate_badge()` in `governance_coordinator` previously issued `FailedReproduction` unconditionally for any `Divergent`/`UnableToAssess` agreement, regardless of validator count. A single validator calling `force_finalize_round` with `UnableToAssess` could permanently brand a study as failed. Fixed: `FailedReproduction` now requires `validator_count >= 3` (matching `BronzeReproducible` threshold). `evaluate_badge_type()` in `governance_integrity` uses the same guard for consistency. |
| `ValidationAttestation.discipline` unvalidated against `ValidationRequest` | Claude red-team audit (2026-04-20) | Medium — data integrity | `attestation_integrity validate()` for `ValidationAttestation` creates already walked the inductive chain to `CommitmentAnchor`. Extended to also fetch the `ValidationRequest` via `anchor.validation_request_hash` and compare `att.discipline != req.discipline` — mismatch is a hard DHT rejection. Previously a validator could self-declare any `Discipline`, polluting the governance discipline indexes. |
| Duplicate `ValidationRequest` per `data_hash` | Claude red-team audit (2026-04-20) | Medium — data integrity | `submit_validation_request` (DNA 3) now checks the `StudyToValidation` path links before calling `create_entry`. If any link exists for the given `data_hash`, the call returns an error: "A ValidationRequest already exists for this data_hash". Prevents non-deterministic behaviour in `get_validation_request_for_data_hash`, COI checks, and badge issuance caused by two requests for the same study deposit. |

### Dismissed findings (with reasoning)

| Finding | Source | Why dismissed |
|---|---|---|
| PhaseMarker forgery / anchor_proof | Grok (first/second) | PhaseMarker is explicitly UI-only; `validate()` cannot gate creates without also blocking the coordinator. Protocol gates on commitment count only. Adding `anchor_proof` would change the DNA hash (breaking change). |
| Phase-marker race condition | Gemini (second) | Multiple simultaneous PhaseMarkers for RevealOpen are harmless — all identical, `get_current_phase` returns last link. Not a protocol gate. |
| Researcher early-reveal breaks blind reveal | Grok (first/second) | Validators already committed their outcomes (bound by SHA-256 hash); researcher revealing first cannot influence committed validators. |
| CommitmentSealedInput accidental leakage | Gemini (second) | Hypothetical future dev error, not a current vulnerability. Addressed with a doc comment on the struct (see `attestation_integrity/src/lib.rs`). |
| Nonce entropy weakness | Gemini (second) | `random_bytes(32)` uses OS RNG — 256-bit entropy. No WASM-specific entropy degradation in Holochain conductors. |
| StudyClaim delete/recreate resets timeout | Gemini (second) | `force_finalize_round` computes age from `ValidationRequest.action().timestamp()` — immutable. StudyClaim timestamps are irrelevant. |
| Assessment spam (`assess_difficulty`) | Gemini (second) | `DifficultyAssessment` is a scaffold stub (all hardcoded values). It does not gate any protocol step. Add per-agent guard when real assessment logic is implemented. |
| post_commit cross-DNA call deadlock | Gemini (second) | Cross-DNA `call(OtherRole(...))` from `post_commit` is the intended Holochain pattern. "Must not write data" means local source chain only. Error is already non-fatal. |
| Empty issuer bypass | Gemini (second) | Already documented as dev/test bypass — same pattern as governance `system_coordinator_key`. Not new. |
| Credential revocation gap | Grok / Gemini (second) | Was: fundamental Holochain DHT architecture limitation — no CRL mechanism possible. **Status changed (2026-03-20):** Holochain roadmap item #5131 ("Validate memproofs on demand") is actively in progress with no milestone (could ship any release). If it lands, post-join credential re-validation becomes possible and a proper revocation mechanism can be built on top. Also watch #5132 / kitsune2 #263–#265 — the Kitsune2 Access module will add network-layer membrane proof enforcement, meaning revoked agents are denied DHT gossip at the transport layer rather than just at the HDI validate() layer. Revisit this gap when these items close. |
| Self-assignment collusion | Grok (first/second) | Acknowledged architectural trade-off. Requires trusted randomness oracle for Phase 1 `select_validators`. |
| HarmonyRecord full content forgery | Grok (second) | Partial fix (author ∈ participants) is in place. Full content verification requires cross-DNA calls in `validate()`, which is architecturally impossible in Holochain HDI. Phase 2. |
| Cross-link deletion by non-author | Grok (second) | Not real in Holochain — only the link author can delete their own links. Any agent who creates a link owns it; non-authors cannot delete it. |

### Known architectural gaps (Phase 1 / Phase 2)

- **Full HarmonyRecord content verification at validate() layer** — cross-DNA calls unavailable in HDI; content correctness is coordinator-layer only. The partial fix (author ∈ participating_validators) is in place.
- **Credential revocation** — once an agent joins the Attestation DHT, they cannot be removed retroactively without governance intervention. **Watch:** Holochain roadmap item #5131 ("Validate memproofs on demand", no milestone — actively in progress as of 2026-03-20) would enable post-join re-validation and is the missing infrastructure for a proper CRL. The Kitsune2 Access module (#5132, kitsune2 #263–265) would additionally enforce membrane proof validity at the network/transport layer, denying gossip to revoked peers before they reach the DHT. When these land, revisit this gap — the Phase 2 revocation design depends on which of these ships first.
- **Multi-device identity / agent linking — implemented (March 2026).** `AgentIdentityAttestation` is live in `attestation_integrity`. `ValidatorReputation` (DNA 4) and `ValidatorProfile` (DNA 3) both carry `person_key: Option<AgentPubKey>` (`#[serde(default)}`). **Phase 1 follow-on (still outstanding):** (1) `update_validator_profile` auto-populates `person_key` from `get_linked_agents` on first call from a new device; (2) `_update_reputation_internal` passes the resolved `person_key` so reputation accumulates under the stable person key; (3) COI checks union all keys linked to an agent. **Async ceremony gap:** `PendingIdentityLink` was not implemented — the current protocol requires both devices to be online simultaneously (device A calls `sign_for_identity_link`, passes the sig out-of-band to device B which also signs, then one calls `link_agent_identity`). A `PendingIdentityLink` stored-entry approach for fully async ceremony is a Phase 1 addition. **Deepkey coordination:** Deepkey handles key rotation (same device, key superseded); `AgentIdentityAttestation` handles the multi-device case (same person, multiple simultaneously active keys). Both are needed for Phase 1. Do not assume device keys are stable when implementing `person_key` propagation.
- **Validator self-assignment collusion** — COI institution check enforced; cartel from distinct institutions is not preventable without random assignment (Phase 1 `select_validators`).
- **`get_current_phase` not authoritative** — clients must not treat `PhaseMarker` as a protocol gate; always verify via `check_all_commitments_sealed`. Any credentialed agent can write a `PhaseMarker` (validate() cannot gate creates without also blocking the coordinator). Protocol itself is unaffected — only UIs that trust `get_current_phase` blindly are at risk.
- **Production reputation is static (Phase 1 gap).** `_update_reputation_internal` is gated behind `system_coordinator_key.is_empty()` (the dev/test bypass) so it never runs in production — the write would fail `validate()` which requires the coordinator key to be the author. All validators therefore remain at `CertificationTier::Provisional` in production until the Phase 1 oracle is live. **Four tiers are defined** — `Provisional` (default) → `Standard` (≥5 rounds) → `Advanced` (≥20 rounds + agreement rate ≥60%) → `Certified` (≥50 rounds + rate ≥80%). These tiers are used for reputation scoring; they do not gate badge issuance. **Badge thresholds use raw participant count** (2026-04-26): Gold ≥7 ExactMatch, Silver ≥5 ExactMatch/WithinTolerance, Bronze ≥3, FailedReproduction ≥3. All tiers of validator contribute equally to badge issuance — an integrator with 5 validators gets Silver regardless of whether those validators are Provisional or Standard. Reputation tier is tracked for future use (governance, assignment priority) but does not change which badge is issued.

---

## Holochain Upgrade Radar (as of 2026-03-21)

Holochain's public roadmap (github.com/orgs/holochain/projects/11) has several upcoming milestones that affect this codebase. Read this before upgrading `holochain` / `hdk` / `hdi` versions in `Cargo.toml`.

**Current ValiChord versions:** `hdk = "0.6"`, `hdi = "0.7"` — these are the current stable versions. See `.claude/skills/check-holochain-updates.md` for a repeatable process to check for newer versions.

---

### 0.6.1 — Almost released (rc.3 dropped March 11, 2026)

`0.6.1-rc.3` is the current latest stable release candidate as of March 11, 2026. This is a Wind Tunnel metrics and infrastructure release — always-online node monitoring, RAM reduction for the summariser, metric interval reporting. **Zero API changes for ValiChord.** Upgrading from 0.6.0 to 0.6.1 when it goes stable is a safe drop-in.

---

### 0.7 — Network transport switch (0.7.0-dev.16 dropped March 16, 2026)

**This is the most imminent change.** 0.7 switches the default kitsune2 transport from QUIC/WebRTC to **iroh** (`Switch default transport to iroh`, kitsune2 #442). This affects network configuration but NOT zome APIs.

When 0.7 stable releases, upgrading ValiChord will require:
1. Bump `hdk` to `0.7.x` and `hdi` to `0.8.x` in workspace `Cargo.toml`
2. Review whether `bootstrapUrl` / `signalUrl` config format changes for iroh (check the 0.7 migration guide — iroh uses a different signalling mechanism)
3. Run `cargo build` — watch for any renamed crates (Holochain crates may be split across repositories for independent versioning in 0.7)

**hdk 0.7.0-dev.10 breaking change already visible in the dev channel:** `get_link_details` is renamed to `get_links_details`. ValiChord does not currently call `get_link_details` directly (uses `get_links` only), so this rename is not expected to affect the build — but verify when upgrading.

---

### 0.8 — **Breaking change expected: validate() API**

**Issue #5010 status (checked 2026-03-21): OPEN, "Ready for refinement", no PR started, no assignee.** This issue was last active December 2025. It is still planned for 0.8 but has not begun implementation. Not an imminent risk — 0.8 is at least two release cycles away.

When it does ship, the signature changes from `validate(op: Op)` to `validate(record: Record, ctx: ValidationContext)`. **This is a breaking compile error** — the build fails immediately, nothing silently breaks. The migration is mechanical but touches all four integrity zomes (~400 lines of match arms).

The membrane proof handler in DNA 3 (`RegisterAgentActivity` arm) will need the most care — check what replaces that variant in the new API before migrating.

Files to update when the time comes:
- `dnas/attestation/zomes/attestation_integrity/src/lib.rs`
- `dnas/governance/zomes/governance_integrity/src/lib.rs`
- `dnas/validator_workspace/zomes/validator_workspace_integrity/src/lib.rs`
- `dnas/researcher_repository/zomes/researcher_repository_integrity/src/lib.rs`

**Issue #4345 — Private entry hash collision bug status (checked 2026-03-21): OPEN, "Ready for refinement", no fix.** This was previously described as "fixed in 0.8" — that is incorrect based on current issue status. It has no linked PR and no assignee. ValiChord uses private entries extensively (all of DNA 1; `ValidatorPrivateAttestation` in DNA 2). The collision probability is negligible but non-zero — if you see spurious validation rejections on private entries, this upstream bug is the likely cause. Watch for a fix to land.

**Issues #4911 + #4912 — Coordinator updates (capability tokens and remote calls) status (checked 2026-03-21): OPEN, "Ready for refinement", both unassigned December 2025.** These describe planned changes to how coordinator zomes are hot-swapped and how capability tokens and remote calls behave during that process. ValiChord's `OtherRole` call pattern is fundamental to the four-DNA architecture and is unlikely to be removed, but grant semantics could change. Review the 0.8 changelog for these issues before upgrading.

---

### Deepkey / key rotation — status corrected (checked 2026-03-21)

**Previous description was inaccurate.** The situation is:

- **Deepkey the hApp is mature and usable today.** The "DeepKey Integration with Holochain" GitHub milestone closed 100% complete in October 2024 (22 issues, all closed). Deepkey has published Rust crates and a standalone hApp. It operates as a foundational service — the first hApp installed on a conductor — and provides key registration, revocation, replacement, and M-of-N authority. Other hApps can query key status via the DPKI service using just a 32-byte key.

- **Conductor-native key migration workflow (#4126, #4128) is still open and unscheduled.** These issues cover adapting the `InstallApp` Admin API to support `MigrateAgent` and `MigrateDna` workflows natively. They have no linked PRs and no milestone. This is not done.

- **Practical implication for ValiChord:** Deepkey can be used for key rotation today, but it requires installing Deepkey as a separate hApp and calling its APIs explicitly. It is not yet transparent conductor infrastructure. `agent_initial_pubkey` vs `agent_latest_pubkey` (#4105) consolidation depends on #4126 and is also unscheduled.

- **Any place ValiChord compares validator identity** (particularly `HarmonyRecord.participating_validators` and the `StudyClaim` COI check) will eventually need to resolve through Deepkey rather than comparing raw pubkeys directly — but this is a Phase 1 task, not urgent now.

**Relationship to agent-linking:** Deepkey handles key rotation (same device, key superseded by a new key). The Flowsta `agent_linking` zome handles the multi-device case (same person, multiple simultaneously active keys). Both are needed for Phase 1. Do not implement agent-linking in a way that assumes keys are stable — the Deepkey migration will change what "canonical key" means.

Flag for the Phase 1 architecture review.

---

### Membrane Proofs epic — status corrected (checked 2026-03-21)

Previously described as "actively in progress, could ship any release." **That was inaccurate based on current issue status.**

- **#5131 — Validate memproofs on demand:** OPEN. Status: "Ready for refinement". Unassigned as of January 2026. No PR. This has stalled — it is not actively in progress. It remains the missing infrastructure for credential revocation, but do not design Phase 2 revocation on an assumption that this will ship soon. Monitor and revisit.

- **#5132 + kitsune2 #263–265 — Kitsune2 Access module:** OPEN. Status: "Ready for refinement". Unassigned as of January 2026. No PR. Same situation — previously described as active, currently stalled. When it eventually lands, ValiChord gets network-layer membrane proof enforcement automatically (no code changes), but that may not be soon. Watch for whether the Access module requires membrane proofs to be registered with Kitsune2 separately in conductor config; if so, ValiChord's join flow would need updating.

- **#1613 — hc sandbox doesn't support membrane proofs:** Dev ergonomics fix. No change in status — still open. Until resolved, the full Tryorama test harness remains required for membrane proof testing.

---

## Integration API and Holochain Bridge (2026-03-28, extended 2026-03-31)

Four phases of work were completed on 2026-03-28 to connect the Python analysis pipeline to the Holochain conductor and expose a clean REST integration surface. The API was extended in March 2026 to support real validator attestations, API key authentication, webhook callbacks, and machine-readable OpenAPI docs.

### REST API surface

All endpoints live in `backend/app.py`. See `backend/openapi.yaml` for the full machine-readable spec, or `GET /docs` for Swagger UI.

**Write endpoints** (require `X-ValiChord-Key` header when `VALICHORD_API_KEYS` env var is set):

- `POST /validate` — multipart/form-data
  - Required: `file` (ZIP, max 100 MB)
  - Optional: `validator_outcome` — `Reproduced | PartiallyReproduced | FailedToReproduce`
  - Optional: `validator_notes` — free text, used as `details` string in non-Reproduced outcomes
  - Optional: `callback_url` — HTTPS URL to POST the result to once complete (one retry after 5 s)
  - Returns: `{ "job_id": "<uuid>" }` (HTTP 202)

- `POST /upload-chunk` — chunked upload for deposits > 100 MB

**Read endpoints** (always open, no key needed):

- `GET /result/<job_id>` → `{ status: running | done | error, ... }`
- `GET /download/<job_id>` → ZIP containing `CLEANING_REPORT.md`, `README_DRAFT.md`, `LICENCE_DRAFT.txt`, `INVENTORY_DRAFT.md`, `ASSESSMENT.md`, `VALICHORD_LOG.json` (job cleaned up after download)
- `GET /deposit/<job_id>?token=<token>` → the original deposit ZIP, served to validators who obtained the token from the `ValidationRequest` entry on the Attestation DHT. Returns 401 if token is missing or wrong, 410 if the file has been cleaned up. Token validated with `secrets.compare_digest` (timing-safe). This endpoint is how `TokenGated` deposit access works — Holochain carries the credential, HTTP delivers the file.
- `GET /health` → `{ status: ok, version, conductor: live | offline }`
- `GET /openapi.yaml` → OpenAPI 3.0.3 YAML spec
- `GET /docs` → Swagger UI HTML (CDN-hosted, no dependencies)

### Two modes: validator-attested vs proxy

**Validator-attested (`validator_attested: true`):** When `validator_outcome` is supplied in `POST /validate`, the `HarmonyRecord` outcome comes directly from the validator's stated verdict — not from deposit quality analysis. This is the genuine replication path. Feynman runs `/replicate`, forms a verdict, then submits it here.

**Proxy (`validator_attested: false`):** When no `validator_outcome` is supplied, the outcome is derived from structural findings:
- No CRITICAL or SIGNIFICANT findings → `Reproduced`
- Only SIGNIFICANT findings → `PartiallyReproduced`
- Any CRITICAL findings → `FailedToReproduce`

The `validator_attested` boolean is always present in `harmony_record_draft`.

### `harmony_record_draft` response shape

```json
{
  "outcome": { "type": "PartiallyReproduced", "content": { "details": "..." } },
  "validator_attested": true,
  "data_hash": "<sha256 hex of the deposit ZIP>",
  "findings_summary": { "critical": 0, "significant": 2, "low_confidence": 3, "total": 5 },
  "harmony_record_hash": "uhCkk7mXy...",
  "harmony_record_url": "https://gateway.valichord.org/..."
}
```

### API authentication

Controlled by the `VALICHORD_API_KEYS` environment variable (comma-separated list of valid keys). When empty, all endpoints are open (dev default). When set, write endpoints (`POST /validate`, `POST /upload-chunk`) require:

```
X-ValiChord-Key: your-api-key
```

Implemented via the `_require_api_key` decorator in `backend/app.py`. Read endpoints are always open.

### Webhooks

When `callback_url` is supplied in `POST /validate`, ValiChord fires a single `POST` to that URL when the job completes:
- `Content-Type: application/json`
- `X-ValiChord-Job-Id: <job_id>` header
- Body: same JSON as `GET /result/<job_id>` when `status == "done"`

One retry after 5 seconds if the first attempt fails. Implemented via `_fire_webhook()` in `backend/app.py` using `threading.Thread(daemon=True)`.

Full request/response shapes are documented in `backend/openapi.yaml` and `docs/INTEGRATION_GUIDE.md`.

### Internal Holochain bridge

**`backend/holochain_bridge.py`** — new file. Python wrapper for `POST /holochain/validate-round` on serve.mjs. Graceful degradation: returns `None` on connection error so analysis always completes even without a live conductor. 120 s timeout for WASM JIT + DHT operations.

**`demo/serve.mjs`** — no longer just a static server + WS proxy. Now also hosts two internal-only POST endpoints (localhost only, HTTP 403 for all other callers):
- `POST /holochain/call` — generic single zome call
- `POST /holochain/validate-round` — full single-agent commit-reveal round → returns `{ harmony_record_hash: "uhCkk...", gateway_payload: "<base64url>" }` or `{ harmony_record_hash: null, gateway_payload: "<base64url>" }` (`gateway_payload` is always present — it is the base64url JSON of the ExternalHash, used to construct `harmony_record_url`)

The commit-reveal sequence in `_runValidationRound` (7 steps): `submit_validation_request` → `claim_study` → `receive_task` → `seal_private_attestation` → poll `get_current_phase` → `submit_attestation` (empty nonce, dev bypass) → `check_and_create_harmony_record` (explicit call to fix DHT timing — post_commit in `submit_attestation` fires before ValidatorToAttestation link is DHT-queryable).

`_runValidationRound` now accepts three additional optional params passed through from `holochain_bridge.py`: `deposit_access_type` (`"PublicUrl"` | `"TokenGated"`), `deposit_token` (string or null), and `data_access_url` (string). All three are forwarded into the `submit_validation_request` zome call. Callers that do not supply them get `PublicUrl` / null / `""` defaults — fully backwards-compatible.

### Two commit-reveal protocol modes

ValiChord's commit-reveal protocol can operate in two modes depending on whether the researcher is a ValiChord participant:

**Validator-only commit-reveal (current demo / plugin path):** The researcher is not on the Holochain network — their deposit is on Zenodo, OSF, or a `TokenGated` endpoint. Only the validator side of the blind commit-reveal runs. Validators seal their verdict independently before seeing what others found. The `CommitmentAnchor` on DNA 3 proves no validator changed their assessment after the consensus became visible. This is what `_runValidationRound` currently executes.

**Full double-blind commit-reveal (native ValiChord path):** The researcher also participates. They call `lock_researcher_result()` in DNA 1 before the round opens, which publishes a `ResearcherResultCommitment` (SHA-256 hash of their metrics + nonce) to DNA 3. After all validators have committed and revealed, the researcher calls `reveal_researcher_result()` — the commitment hash is verified on-chain before the metrics land on the shared DHT. This proves the researcher did not adjust their claimed result after seeing validator findings.

The Rust code for both modes is fully implemented. `_runValidationRound` currently runs the validator-only path. To activate the full double-blind, add `lock_researcher_result` (DNA 1) before `submit_validation_request`, and `reveal_researcher_result` (DNA 3) after `submit_attestation`. These are steps 0 and 7.5 in the sequence — the other 7 steps are unchanged.

**`__bytes` convention:** Uint8Array values crossing Node→Python→Node boundaries serialise as `{ "__bytes": "<base64>" }`. ActionHash results are converted to canonical `uhCkk...` strings via `encodeHashToBase64` before being returned to Python, so Python can embed them in URLs directly.

**`HOLOCHAIN_GATEWAY_URL` + `HOLOCHAIN_GOVERNANCE_DNA_HASH` + `HOLOCHAIN_APP_ID` env vars:** When all three are set, `harmony_record_url` in responses is populated as:
```
${HOLOCHAIN_GATEWAY_URL}/${HOLOCHAIN_GOVERNANCE_DNA_HASH}/${HOLOCHAIN_APP_ID}/governance_coordinator/get_harmony_record?payload=${gateway_payload}
```
`gateway_payload` is returned by `POST /holochain/validate-round` — it is the base64url-encoded JSON of the ExternalHash (`encodeHashToBase64(externalHash)`), which is what `get_harmony_record` expects as input. The governance DNA hash for the current Codespace network is `uhC0kdW4dc3_nWr50fp7PgDT2xR0PSwbaAMUgcp8cUKDDyr8On1lF` (printed by `demo/start-gateway.sh` on startup). **This is now working end-to-end in the Codespace demo** — `harmony_record_url` is fully populated in every validation result when the gateway is running.

---

## Feynman Integration Milestone (2026-03-28, extended 2026-03-31)

Feynman (getcompanion-ai/feynman) is an open-source AI research agent. ValiChord integrated with it as a validator skill:

- **PR #13** in `getcompanion-ai/feynman` — cherry-picked as commit `2dea96f` into Feynman 0.2.15 by @advaitpaliwal.
- **Skill files** (in the Feynman repo, not this one):
  - `skills/valichord-validation/SKILL.md` — skill metadata and entry point description
  - `prompts/valichord.md` — full workflow prompt for Feynman agents

- **PR #14** (open) — migrates to the `POST /validate` + `GET /result/<job_id>` single-shot API; documents `harmony_record_draft` response shape.

- **PR #15** (draft) — adds the full validator flow. The critical architectural change: Feynman runs `/replicate` (actual code execution in Docker/Modal) *before* submitting to ValiChord. The verdict from `/replicate` is passed as `validator_outcome` + `validator_notes` in `POST /validate`, producing `validator_attested: true` in the HarmonyRecord. Prompt lives at `feynman_integration/valichord_prompt_v2.md`.

**Key architectural distinction:** valichord_at_home (static analysis only, no code execution) is for researchers self-checking deposit structure. Feynman's `/replicate` is for validators actually running the code. They are complementary, not competing. ValiChord accepts verdicts from both paths — `validator_attested` tells you which one produced the result.

Feynman and Nondominium are complementary, separate integration layers — Feynman is a REST API client (AI agent), Nondominium is a peer system with direct Holochain zome access. They do not conflict.

---

## Nondominium Integration Status (as of 2026-03-28)

`nondominium_integration/INTEGRATION_VISION.md` is the design document for the ValiChord × Nondominium (Sensorica) integration. It describes a 5-act end-to-end system where Nondominium NRP-CAS (resource tracking) and ValiChord (reproducibility verification) interoperate at the Holochain zome level.

**Status: design phase. No code written for this track.**

Four open design decisions remain pending input from the Sensorica team:
1. Membrane access — how does Nondominium get credentials to call ValiChord's Attestation DNA?
2. Identity bridging — how are Nondominium agent keys mapped to ValiChord validator profiles?
3. Compensation routing — which system owns the `CompensationTier` and when is it written?
4. Governance scope — does Nondominium have write access to ValiChord's Governance DNA, or only read?

Read `nondominium_integration/INTEGRATION_VISION.md` before starting any Nondominium work.

---

## Key Files

| File | Description |
|---|---|
| `valichord/shared_types/src/lib.rs` | All cross-DNA types |
| `valichord/dnas/attestation/zomes/attestation_integrity/src/lib.rs` | DNA 3 entry types, link types, validate() |
| `valichord/dnas/attestation/zomes/attestation_coordinator/src/lib.rs` | DNA 3 coordinator functions including init() membrane verification |
| `valichord/dnas/governance/zomes/governance_integrity/src/lib.rs` | DNA 4 entry types, validate() with author key enforcement |
| `valichord/dnas/governance/zomes/governance_coordinator/src/lib.rs` | DNA 4 including check_and_create_harmony_record |
| `valichord/happ.yaml` | Role definitions, DNA property defaults |
| `valichord/tests/src/attestation.test.ts` | DNA 3 integration tests including membrane proof |
| `valichord/tests/README.md` | Full test inventory, build instructions, architecture notes |
| `backend/app.py` | Flask web entry point — REST API including /validate, /result, /health |
| `backend/holochain_bridge.py` | Python → Holochain bridge wrapper (graceful degradation) |
| `demo/serve.mjs` | Static server + WS proxy + internal Holochain bridge endpoints |
| `valichord-ui/src/App.svelte` | Frontend shell — port detection, role detection, signal subscription |
| `valichord-ui/src/lib/holochain.ts` | AppWebsocket singleton — callZome wrapper, role→zome name map |
| `valichord-ui/src/lib/types.ts` | TypeScript mirrors of all Rust types (serde encoding preserved) |
| `valichord-ui/FRONTEND.md` | UX walkthrough — screen-by-screen instructions for all three roles |
| `docs/3_ValiChord_Technical_Reference.md` | Full architectural narrative — read before modifying architecture |
| `docs/7_ValiChord_4-DNA_architecture_technical.md` | Technical architecture document |
| `nondominium_integration/INTEGRATION_VISION.md` | Nondominium × ValiChord integration design document |

---

## Contact

**Ceri John** — [topeuph@gmail.com](mailto:topeuph@gmail.com)

Technical review: Arthur Brock (Holochain co-founder), Paul D'Aoust (Holochain Foundation)

For Holochain-specific questions, the Holochain developer Discord is the fastest route to answers. Paul D'Aoust is active there and familiar with this codebase.
