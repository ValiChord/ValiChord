# ValiChord × EU AI Act Article 12 — Compliance Plan

**Created:** 2026-06-18  
**Status:** Draft — for review before Arcadia Impact conversation  
**Deadline:** 2 December 2027 (high-risk obligations; deferred from August 2026 by EU Digital Omnibus, May 2026)

---

## 1. What Article 12 actually requires

Article 12 mandates that **high-risk AI systems** shall technically allow for the **automatic recording of events (logs)** over the lifetime of the system. Those logs must enable:

- **(a)** Identifying situations that may result in the system presenting a risk (→ Art 79)
- **(b)** Post-market monitoring (→ Art 72)
- **(c)** Monitoring by deployers (→ Art 26(5))

For biometric systems specifically (Annex III §1(a)), enhanced minimums apply: period of use (start/end timestamps), reference database used, input data that produced matches, and identification of natural persons who verified results.

Deployers must retain automatically generated logs for **at least 6 months** (Art 26(6)).  
Providers must retain technical documentation for **10 years** (Art 18).

**Who it applies to:** Providers and deployers of systems listed in Annex III (employment screening, healthcare, biometrics, law enforcement, critical infrastructure, education, migration, justice) plus Annex I systems. General-purpose AI / frontier models are addressed separately under Articles 51–55 (systemic risk — different but adjacent obligations).

---

## 2. ValiChord's position — enabler, not subject

ValiChord is **not** a high-risk AI system. It does not make decisions about people. It verifies claims about AI system performance.

ValiChord's role is as **verification infrastructure** for the evaluation-claim layer of Article 12. Specifically:

- A provider of a high-risk AI system claims "our model achieves X accuracy on benchmark Y"
- Article 12 + Art 72 require that claim to be logged, monitorable over the system's lifetime, and traceable
- ValiChord produces a **HarmonyRecord**: a tamper-evident, multi-party-verified, cryptographically-bound record that the stated claim was independently reproduced under blind conditions

This covers the **post-market monitoring slice** of Article 12 (Art 12(2)(b) → Art 72), not runtime inference logging. Those are complementary layers, not competing ones.

---

## 3. Current coverage — what ValiChord already satisfies

| Article 12 obligation | ValiChord mechanism | Status |
|---|---|---|
| Automatic recording of evaluation events | HarmonyRecord written to DHT automatically at round close, without manual intervention | **Full** |
| Tamper-evidence over lifetime | DHT + commit-reveal; no single party can alter a committed record | **Full** |
| Multi-party independence | Commit-reveal protocol enforces blind validation; COI rules prevent institutional collusion | **Full** |
| Dataset binding | `data_hash` (ExternalHash) on `ValidationRequest` — cryptographic binding to the specific data evaluated | **Full** |
| Validator identity | AgentPubKey + institutional membrane proof (Ed25519 credential from issuer) | **Partial** |
| Input data reference | `data_access_url` + `data_hash` | **Partial** |
| Post-market monitoring records | Individual HarmonyRecords queryable by `request_ref` | **Partial** |
| Lifetime chain across evaluations | Not yet — no link between successive evaluations of the same AI system | **Gap** |
| Evaluation period timestamps | Not yet — no explicit start/end time recorded | **Gap** |
| Natural person identification | Pseudonymous (AgentPubKey); institutional identity via membrane proof | **Gap** for Annex III §1(a) |
| Pre-registration of evaluation bar | Not in Rust protocol — `prml_lock_hash` now in Python bundle layer | **Partial** |

**The honest summary:** ValiChord currently provides the *evidence* layer Article 12 needs for evaluation claims — tamper-evident, multi-party, cryptographically bound. Three structural gaps prevent full compliance coverage, all requiring integrity zome changes (DNA hash bump).

---

## 4. The pre-registration gap — and how Falsify closes it

Article 12 + Article 15 (accuracy/robustness claims) together imply a problem ValiChord alone cannot solve: a provider can run 20 evaluations, find one where their model looks best, and submit only that one. ValiChord would faithfully attest a cherry-picked result.

**PRML pre-registration** (Falsify, `studio-11-co/falsify`) closes this by locking the evaluation bar — metric, threshold, dataset hash, seed — to a SHA-256 *before the run starts*. The `prml_lock_hash` field (added to `valichord_attestation` bundle in v1.3, 2026-06-18) links the ValiChord attestation bundle to the pre-registered manifest.

The combined evidence package:

```
PRML manifest (Falsify)                   valichord_attestation bundle
 ├── metric: accuracy                       ├── model_id: ...
 ├── threshold: 0.90                        ├── task_id: ...  
 ├── dataset.hash: <sha256>                 ├── metrics: [accuracy=0.934]
 ├── seed: 42                               ├── prml_lock_hash: <same SHA-256>
 └── locked_sha256: c30dba8e...             └── meta.attestation_uri: <HarmonyRecord>
          │                                              │
          └─────────────── in-toto Statement ────────────┘
                           subject = run_id
                           predicates = {PRML, ValiChord bundle, HarmonyRecord ref}
```

This gives an auditor three independently verifiable claims:
1. The bar was committed before the run (PRML SHA-256 is time-stamped before evaluation)
2. The run produced a specific output (valichord_attestation bundle hash)
3. Independent validators reproduced that output blind (HarmonyRecord on DHT)

---

## 5. Gaps and protocol additions required

All three gaps require integrity zome changes and should be batched into a single DNA hash bump. Sequence this with any other planned integrity changes (0.7.0 upgrade, `person_key` decision).

### Gap 1 — `system_ref`: Lifetime chain across evaluations

**Article 12 obligation:** Logging "over the lifetime of the system" — not just individual evaluation events but a traceable chain.  
**Missing:** No field in `ValidationRequest` that identifies the AI system being evaluated. Multiple HarmonyRecords for the same model are unlinked.

**Proposed addition** to `ValidationRequest`:

```rust
/// External identifier for the AI system under evaluation.
/// Enables lifetime chain: link all HarmonyRecords for one system across time.
/// Use: the model card URI, provider's system ID, or a content-hash of the model artifact.
/// None = unlinked (valid; lifetime chain simply not claimed).
#[serde(default)]
pub system_ref: Option<String>,

/// Version or release identifier of the AI system being evaluated.
/// Together with system_ref, identifies a specific model version.
#[serde(default)]  
pub system_version: Option<String>,
```

A coordinator-side `get_records_for_system(system_ref)` query (no DNA hash change needed for the query) returns the full audit trail across deployments.

### Gap 2 — Evaluation period timestamps

**Article 12 obligation:** Art 12(3)(a) requires recording of start date/time and end date/time of each use.  
**Missing:** ValiChord records DHT action timestamps implicitly but doesn't surface them as explicit fields. For compliance purposes they need to be unambiguous.

**Proposed addition** to `ValidationRequest` (or a new `EvaluationPeriod` entry written by the researcher):

```rust
/// ISO 8601 timestamp when the researcher began the evaluation run.
/// For Article 12(3)(a) compliance — "start date and time of each use".
#[serde(default)]
pub evaluation_started_at: Option<String>,
```

The `evaluation_completed_at` is the DHT action timestamp of the HarmonyRecord creation — already implicit, just needs surfacing in the API response.

### Gap 3 — Validator identity for Annex III §1(a) systems

**Article 12 obligation:** Art 12(3)(d) requires "identification of the natural persons involved in the verification." For biometric systems, pseudonymous keys are insufficient.  
**Current state:** Validator identity = AgentPubKey + institutional membrane proof. The membrane proof establishes institutional affiliation but not natural-person identity.

**Proposed addition:** A `ValidatorIdentityAttestation` entry (coordinator-only, can use `UpdateCoordinators` — no DNA hash change needed) that links AgentPubKey → institution → named role, signed by the institutional issuer. For most evaluation contexts (non-biometric Annex III), institutional identity is sufficient. For biometric contexts, a separate natural-person disclosure layer is needed.

**Note:** This gap only applies to Annex III §1(a) biometric systems. For the evaluation contexts ValiChord is primarily used in (capability benchmarks, reproducibility), institutional identity via membrane proof is sufficient.

---

## 6. For Arcadia Impact — the specific conversation

**What Arcadia does:** AI safety evaluations using Inspect Evals infrastructure. Their clients are AI providers; the AI systems evaluated may include both Annex III high-risk deployments and frontier/GPAI models under Article 51–55 systemic risk provisions.

**What they need:**

For **Annex III clients** (e.g., a provider deploying an LLM for employment screening under Annex III §4): Article 12-compliant evaluation records proving stated accuracy claims were independently verified. Specifically:
- Tamper-evident, immutable record of the evaluation
- Multi-party blind verification (not just self-attestation)
- Binding to the specific model version and dataset evaluated
- Linkable to the model's post-market monitoring history over time

For **GPAI/frontier model clients** under Article 51–55: Technical documentation of capability evaluations that can withstand regulatory scrutiny. The requirements are different (no explicit Article 12 mandate) but the practical need is the same — credible, verifiable, independent evaluation records that are more trustworthy than the provider's own claims.

**What ValiChord gives them right now** (no waiting for Gap 1/2/3 to close):
- HarmonyRecord: tamper-evident, multi-party verified, publicly queryable, immutable
- `data_hash` binding: the evaluation is cryptographically tied to the specific dataset version
- CORE-Bench demo: end-to-end working demo — three AI validators blind-reproduce a real paper's computational result, commit-reveal simultaneously, produce a public HarmonyRecord at a curl-verifiable Oracle URL
- `prml_lock_hash` in attestation bundle: links the run to a pre-registered evaluation design

**The honest limitation:** ValiChord's HarmonyRecord doesn't yet carry explicit `system_ref`, `system_version`, or `evaluation_started_at`. For full Article 12 compliance coverage, those fields need adding. Timeline: batch with 0.7.0 upgrade (planned, no date set), well inside the December 2027 deadline.

---

## 7. The full evidence package — what a compliant evaluation looks like

A provider preparing Article 12 + Art 72 documentation for an evaluation event:

| Step | Who | Tool | Output | Article 12 coverage |
|---|---|---|---|---|
| 1. Pre-register evaluation design | Provider | `falsify lock` | PRML manifest + SHA-256 | Prevents post-hoc bar-moving |
| 2. Submit validation request | Researcher | ValiChord `create_validation_request` | `ValidationRequest` on DHT, bound to `data_hash` | Art 12(2) automatic recording |
| 3. Blind validation round | 3–7 validators | ValiChord commit-reveal | `ValidationAttestation` per validator, sealed before reveal | Multi-party independence |
| 4. Consensus | Protocol | `check_and_create_harmony_record` | `HarmonyRecord` — immutable, permanent, public | Art 12(2)(b) monitoring record |
| 5. Bundle attestation | Researcher | `valichord_attestation` with `prml_lock_hash` | Signed bundle + `content_hash` | Annex IV technical documentation |
| 6. in-toto Statement | Either | `falsify attest` | ITE-6 Statement wrapping PRML + bundle | Machine-readable compliance artefact |
| 7. CI gate (ongoing) | Provider | `prml-verify-action` | Exit 0/10/3 on each release | Art 72 post-market monitoring |

Steps 1 and 6 require Falsify. Steps 2–5 are ValiChord today. Step 7 is Falsify's GitHub Action.

---

## 8. Timeline

| Milestone | Date | What |
|---|---|---|
| `prml_lock_hash` in attestation bundle | ✅ 2026-06-18 | Python layer, no Rust changes |
| Gap 1+2 (system_ref, timestamps) | Batch with 0.7.0 upgrade | Integrity change — DNA hash bump |
| Gap 3 (natural person identity) | Only if biometric clients emerge | Coordinator-only, no DNA hash change |
| EU AI Act high-risk obligations enforceable | 2 December 2027 | Hard deadline |

Gaps 1 and 2 are well-bounded integrity changes. They should be scoped into the 0.7.0 upgrade plan so they don't require a second DNA hash bump.

---

## 9. What is explicitly out of scope

ValiChord addresses the **evaluation-claim layer** of Article 12 — proof that stated performance metrics were independently verified. It does **not** cover:

- **Runtime inference logging** — logging every prediction a model makes during deployment. That's an operational logging system (separate infrastructure entirely).
- **Risk management system** (Art 9) — process obligation, not a record format.
- **Data governance** (Art 10) — substantive bias and quality obligations.
- **Human oversight** (Art 14) — operational obligation for deployers.
- **Conformity assessment procedures** (Arts 43–49) — notified body process.

ValiChord + Falsify together cover the evaluation-evidence layer. The runtime logging layer needs separate infrastructure that the deployer operates.

---

## 10. References

- Regulation (EU) 2024/1689 of 13 June 2024 (AI Act) — Articles 12, 18, 26, 72, 73, 79; Annex III; Annex IV
- EU Digital Omnibus (May 2026) — deferred high-risk obligation date to 2 December 2027
- Falsify PRML v0.1 compliance mapping: `studio-11-co/falsify/spec/compliance/AI-Act-mapping-v0.1.md`
- NIST AI RMF 1.0 (January 2023) — additional crosswalk in Falsify compliance doc
- ISO/IEC 42001:2023 — additional crosswalk in Falsify compliance doc
