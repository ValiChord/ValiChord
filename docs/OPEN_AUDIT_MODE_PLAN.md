# Open Audit Mode — Implementation Plan

**Status:** Deferred — implement before any live network is deployed  
**Estimated effort:** 1 week (16 MB limit, no chunking); 2 weeks (with chunking)  
**Last updated:** 2026-05-27

---

## 1. What This Is

By default, ValiChord's dataset stays in the researcher's private DNA 1 and never enters the shared DHT. Third parties can audit the process (hash chain, phase transitions, attestations, Harmony Record) but cannot independently re-verify the underlying data.

Open audit mode changes only the data locality. At submission, the researcher encrypts their dataset and posts the ciphertext to the DNA 3 DHT. After reveal, the decryption key is published in `ResearcherReveal`. Any third party can then decrypt, hash, and compare against the original commitment — the Harmony Record is fully self-verifying without trusting ValiChord or the researcher's private system.

The blind commit-reveal protocol, phase transitions, CommitmentAnchors, and HarmonyRecord are **identical in both modes**. This is a strictly additive change.

---

## 2. Encryption Approach

Do **not** use Holochain's lair-based `x_salsa20_poly1305_shared_secret_export` for this. Lair exports keys encrypted to a target keypair, not as raw bytes suitable for public decryption.

Use pure-Rust WASM-compatible crypto instead:

```toml
# valichord/Cargo.toml additions
chacha20poly1305 = { version = "0.10", default-features = false, features = ["alloc"] }
rand = { version = "0.8", default-features = false, features = ["getrandom"] }
getrandom = { version = "0.2", features = ["js"] }  # wasm32 entropy
```

```rust
use chacha20poly1305::{
    aead::{Aead, KeyInit, OsRng},
    ChaCha20Poly1305, Key, Nonce,
};

// At submission: generate key + encrypt
let key = ChaCha20Poly1305::generate_key(&mut OsRng);
let cipher = ChaCha20Poly1305::new(&key);
let nonce = ChaCha20Poly1305::generate_nonce(&mut OsRng);  // 96-bit nonce
let ciphertext = cipher.encrypt(&nonce, dataset_bytes.as_ref())?;

// Stored in DNA 1: key.to_vec() + nonce.to_vec()
// Posted to DNA 3 DHT: ciphertext (+ nonce prepended for self-contained decryption)
// Published at reveal: key.to_vec() (32 bytes)

// Anyone decrypting after reveal:
let key = Key::from_slice(&published_key_bytes);
let cipher = ChaCha20Poly1305::new(key);
let (nonce_bytes, ciphertext) = stored_blob.split_at(12);
let plaintext = cipher.decrypt(Nonce::from_slice(nonce_bytes), ciphertext)?;
// SHA-256(plaintext) must equal ValidationRequest.data_hash
```

ChaCha20-Poly1305 is `no_std` / `alloc`-only, IETF-standard, and compiles cleanly to `wasm32-unknown-unknown`. No lair dependency, no special key management beyond storing 32 bytes.

---

## 3. Changes Required

### 3.1 DNA 1 — Researcher Repository

**New shared type** (in `shared_types/`):
```rust
pub struct DatasetEncryptionKey {
    pub request_ref: ExternalHash,
    pub key_bytes:   Vec<u8>,   // 32-byte ChaCha20 key
    pub nonce_bytes: Vec<u8>,   // 12-byte nonce
}
```

**New private entry** in DNA 1 integrity zome:
```rust
DatasetEncryptionKey(DatasetEncryptionKey)  // visibility = "private"
```

**New link type** in DNA 1:
```rust
RequestToEncryptionKey   // ExternalHash (request_ref) → DatasetEncryptionKey ActionHash
```

**New coordinator function** in DNA 1:
```rust
pub fn submit_encrypted_dataset(input: EncryptedDatasetInput) -> ExternResult<ActionHash>
// input: { request_ref, dataset_bytes, mode: DataLocalityMode }
// - if mode == OpenAudit: encrypt, write DatasetEncryptionKey (private), call DNA 3
//   post_encrypted_dataset(ciphertext + nonce), return ciphertext ActionHash
// - if mode == Gdpr: no-op, return unit (GDPR path unchanged)
```

**New coordinator function** in DNA 1 (called at reveal):
```rust
pub fn get_decryption_key(request_ref: ExternalHash) -> ExternResult<Option<Vec<u8>>>
// queries local chain for DatasetEncryptionKey, returns key_bytes
// called by DNA 3 reveal flow to include key in ResearcherReveal
```

### 3.2 DNA 3 — Attestation

**New entry type** in integrity zome:
```rust
// IMMUTABLE — open audit mode only
EncryptedDataset {
    request_ref:   ExternalHash,
    ciphertext:    Vec<u8>,    // nonce (12 bytes) prepended to ciphertext
    size_bytes:    u64,        // plaintext size for pre-download size checks
    mode_version:  String,     // "chacha20poly1305-v1" — algorithm tag for future-proofing
}
```

**Modified entry types** (optional fields — backwards compatible):
```rust
// Add to ValidationRequest:
pub audit_mode: Option<AuditMode>,   // None = GDPR (default), Some(OpenAudit) = encrypted DHT

// Add to ResearcherReveal:
pub decryption_key: Option<Vec<u8>>,  // None = GDPR mode; 32 bytes = open audit mode
```

**New shared type**:
```rust
#[derive(Serialize, Deserialize, Debug, Clone)]
pub enum AuditMode {
    Gdpr,
    OpenAudit,
}
```

**New link type** in DNA 3:
```rust
RequestToEncryptedDataset   // ExternalHash (request_ref) → EncryptedDataset ActionHash
```

**New coordinator functions** in DNA 3:
```rust
pub fn post_encrypted_dataset(input: PostEncryptedDatasetInput) -> ExternResult<ActionHash>
// Creates EncryptedDataset entry, creates RequestToEncryptedDataset link
// Called from DNA 1 via call(OtherRole("attestation"), ...)

pub fn get_encrypted_dataset(request_ref: ExternalHash) -> ExternResult<Option<Record>>
// Retrieves EncryptedDataset for a given request — used by third-party verifiers via HTTP Gateway
```

**Modified coordinator function**:
```rust
// publish_researcher_reveal — extend to accept optional decryption_key
// if present, include in ResearcherReveal entry
```

### 3.3 No Changes Required

- DNA 2 (Validator Workspace) — untouched
- DNA 4 (Governance) — untouched
- Commit-reveal phase logic — untouched
- CommitmentAnchor, PhaseMarker, ValidationAttestation — untouched
- HarmonyRecord — untouched (decryption key is in ResearcherReveal, not HarmonyRecord)
- All existing tests — pass unchanged (new fields are `Option` with `#[serde(default)]`)

---

## 4. Dataset Size Limit

DHT entries have a practical ceiling of ~16 MB before conductor memory pressure. For Phase 1:

- Impose a hard limit at submission: `dataset_bytes.len() > 16_000_000 → Err(WasmError)`
- Document this as a Phase 1 constraint; chunking is the Phase 2 upgrade path
- Most computational eval datasets (scripts + small data) fit within 16 MB
- Large datasets (ML training sets, genomics data) would use GDPR mode regardless

**Chunking (Phase 2, if needed):** Follow the file-system-zome pattern — fixed 1 MB chunks, each a separate `EncryptedChunk` entry, `EncryptedDataset` holds `Vec<ExternalHash>` of chunk entry hashes. ~3 additional days of engineering.

---

## 5. Validation Rules (integrity zome)

```rust
// EncryptedDataset: immutable, author must match ValidationRequest author
FlatOp::RegisterUpdate(OpUpdate::Entry {
    app_entry: EntryTypes::EncryptedDataset(_), ..
}) => Invalid("immutable")

FlatOp::RegisterDelete(OpDelete::Entry {
    original_app_entry: EntryTypes::EncryptedDataset(_), ..
}) => Invalid("immutable")

// Verify audit_mode consistency: if ValidationRequest.audit_mode == Some(OpenAudit),
// a corresponding EncryptedDataset link must exist before RevealOpen phase
// (enforced in coordinator, not integrity — DHT order not guaranteed at validation time)
```

---

## 6. HTTP Gateway Exposure

The existing `Unrestricted` capability grants in DNA 3 `init()` cover read functions. Add `get_encrypted_dataset` to the unrestricted list so journal editors and third-party verifiers can retrieve the ciphertext via HTTP Gateway without a capability token — the same way they query HarmonyRecords today.

---

## 7. Test Plan

### New unit/integration tests needed:

1. `open_audit_mode_dataset_posted_to_dht` — submit with `OpenAudit` mode, verify `EncryptedDataset` entry exists on DNA 3 DHT
2. `open_audit_mode_decryption_key_in_reveal` — complete a full round in open audit mode, verify `ResearcherReveal.decryption_key` is present
3. `open_audit_mode_decrypt_and_verify` — retrieve ciphertext, decrypt with published key, verify SHA-256 matches `ValidationRequest.data_hash`
4. `gdpr_mode_no_ciphertext_on_dht` — submit with default (GDPR) mode, verify no `EncryptedDataset` entry exists
5. `oversized_dataset_rejected` — dataset > 16 MB returns `WasmError`
6. `backwards_compat_existing_entries` — entries created before open audit mode (no `audit_mode` field) deserialise correctly with `#[serde(default)]`

### Existing tests: no changes expected. All new fields are `Option` + `#[serde(default)]`.

---

## 8. Time Estimate

| Phase | Work | Days |
|---|---|---|
| Crypto + shared types | `chacha20poly1305` dep, `DatasetEncryptionKey`, `AuditMode` types | 1 |
| DNA 1 integrity + coordinator | New entry type, key generation, encrypt, `get_decryption_key` | 2 |
| DNA 3 integrity + coordinator | `EncryptedDataset` entry, optional fields, `post_encrypted_dataset`, `get_encrypted_dataset` | 2 |
| Validation rules + capability grants | Immutability guards, HTTP Gateway exposure | 0.5 |
| Tests | 6 new tests + repack | 1.5 |
| **Total** | | **~7 days** |

Adding chunking: +3 days.

---

## 9. Go Criteria

Implement this **before any live network is deployed**. Adding a new entry type to the DNA 3 integrity zome changes the DNA hash, which is a hard network break for any existing participants. In development this costs a repack and test fixture update. Post-launch it means migrating a live network. Do it now.

---

## 10. Related Files

- `valichord/dnas/attestation/` — DNA 3 integrity + coordinator zomes
- `valichord/dnas/researcher_repository/` — DNA 1 integrity + coordinator zomes
- `valichord/shared_types/src/lib.rs` — shared type definitions
- `docs/7_ValiChord_4-DNA_architecture_technical.md` — architecture reference (Data Locality Modes section)
- `docs/1_ValiChord_Vision&Architecture.md` — vision reference (Layer 0 two-modes paragraph)
