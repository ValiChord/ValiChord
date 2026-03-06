
<div align="center">
  <img src="../Valichord logo-standard v2-1.5x.jpeg" width="450px" alt="ValiChord Logo">
</div>

# ValiChord — Technical Reference
## Illustrative Architecture Sketches for Engineering Discussion

**Author:** Ceri John
**Date:** March 2026

**© 2026 Ceri John. All Rights Reserved.**

**Contact:** topeuph@gmail.com

---

## Important Note on Status

**These are design intent documents, not implementation code.**

The Rust structures and functions in this document describe the *shape* of ValiChord's architecture — data models, system flows, and component interactions. They are illustrative sketches developed during twelve months of architectural design, intended to communicate system intent to engineers clearly and precisely.

They have not been compiled, tested, or audited. They are the starting point for a first proper engineering conversation, not the output of one.

**What this document is for:** An engineer reading this should understand what ValiChord needs to do, what data it handles, how components interact, and where the hard problems are. It should save weeks of explanation and allow technical discussion to begin at the right level.

**What this document is not:** Production code, a specification that can be implemented without modification, or evidence of technical progress beyond architectural design.

**Technical feasibility confirmed:** Paul D'Aoust (Documentation and Developer Community Lead, Holochain Foundation) reviewed the architectural approach and confirmed it is implementable with the current Holochain framework (January 2026). Shin Sakamoto, an independent Holochain application developer, also reviewed the architecture. Arthur Brock (co-founder and architect, Holochain) conducted a solution engineering review and provided detailed implementation guidance, including the multi-DNA membrane architecture (February 2026). Joel Marcey (Tech Director, Rust Foundation) reviewed both this document and the MVP Specification and confirmed the approach is sound (February 2026). This confirms the *approach* is sound, not that these specific structs are final.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│ LAYER 8: Access & Presentation (Human Interface)        │
│ Dashboards for researchers, validators, funders, public │
└─────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────┐
│ LAYER 7: Integration & Interface (Ecosystem)            │
│ How external systems query/submit to ValiChord          │
└─────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────┐
│ LAYER 6: Incentive & Reputation (Participation)         │
│ Why validators validate, why researchers participate    │
└─────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────┐
│ LAYER 5: Output & Certification (Trust Signals)         │
│ What the world sees: Harmony Records, badges, reports   │
└─────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────┐
│ LAYER 4: Audit & Provenance (Memory)                    │
│ Tamper-evident record of every action, complete traceability │
└─────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────┐
│ LAYER 3: Governance & Policy (Rules)                    │
│ Who decides standards, how disputes resolve             │
└─────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────┐
│ LAYER 2: Validation Engine (Orchestration)              │
│ Validator selection, gaming detection, agreement analysis │
└─────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────┐
│ LAYER 1: Intake & Pre-Commitment (Claims Entry)         │
│ Protocol registration, pre-commitment, deviation tracking│
└─────────────────────────────────────────────────────────┘
┌═════════════════════════════════════════════════════════┐
║ LAYER 0: Data & Integrity (Foundation)                  ║
║ Content-addressed storage, cryptographic integrity      ║
╚═════════════════════════════════════════════════════════╝
```

### Layer Interactions & Data Flow

The eight layers describe functional responsibilities, not a central stack. In the multi-DNA architecture, these responsibilities are distributed across separate networked organisms — what looks like a vertical stack in the diagram maps onto coordinated, peer-to-peer participants. The flows below describe the logical sequence of events across that distributed system.

**Registration Flow (Layers 1 → 0 → 4):**
1. Researcher submits protocol via Layer 1 (Intake)
2. Data uploaded to Layer 0 (Integrity)
3. Registration recorded in Layer 4 (Audit)

**Validation Flow (Layers 2 → 0 → 4 → 5):**
1. Validators assigned via Layer 2 (Engine)
2. Fetch data from Layer 0 (Integrity)
3. Attestations logged to Layer 4 (Audit)
4. Harmony Record generated in Layer 5 (Output)

**Reputation Flow (Layers 2 → 4 → 6):**
1. Validation behaviour tracked in Layer 2
2. Historical data from Layer 4
3. Scores updated in Layer 6 (Reputation)

**Governance Flow (Layers 3 → 1, 2, 6):**
1. Policy bodies (Layer 3) set standards
2. Enforced in Intake (Layer 1), Engine (Layer 2), Reputation (Layer 6)

**Access Flow (Layers 8 → 7 → 5, 6):**
1. Users access via Layer 8 (Presentation)
2. Integrations via Layer 7 (Interface)
3. Query Output (Layer 5) and Reputation (Layer 6)

---

### Multi-DNA Architecture and Membranes

ValiChord is designed as a set of distinct, composable Holochain applications (DNAs) rather than a single monolithic application. Each DNA creates its own encrypted peer-to-peer network with its own **membrane** — the boundary that governs who can join that network and what data is shared within it.

This is the recommended pattern for Holochain applications where different participants need different data spaces. Multiple small, focused apps communicating through bridges is architecturally cleaner, easier to update, and more stable than a single large application managing access internally. In distributed software, updates require every participant to upgrade simultaneously — keeping each DNA small and stable minimises how often this is necessary.

Each DNA creates a distinct networked organism: even where two DNAs share identical code, small configuration differences — including a **network seed**, a unique property baked into each instance — make them separate organisms that will only synchronise among their own nodes. This is the mechanism that makes the privacy separation absolute: the Researcher Repository DNA and the Attestation DNA are not the same network with different access rules applied; they are genuinely different networks that happen to share some code patterns.

**DNA 1 — Researcher Repository App** *(private membrane)*
Runs locally on the researcher's or institution's machine. Holds code, data, and methods. Only the researcher and their institution can join. Nothing sensitive ever enters the shared network — the researcher publishes only a cryptographic commitment (metadata and hash) outward to the Attestation DNA. GDPR compliance is architecturally enforced, not just policy: data cannot enter the shared DHT because it lives in a separate, private DNA.

**DNA 2 — Validator Workspace App** *(private membrane, per validator)*
Each validator runs this locally — the "Repro Witnessing hApp." Their private reproduction environment: where they run the analysis, where working results are held. Only this validator can join. Because the local app controls exactly how data is serialised before producing a hash, outputs are consistent regardless of database query ordering or other non-deterministic operations. Only a signed attestation — never raw reproduction results — leaves this space.

**DNA 3 — Attestation App** *(shared DHT, credentialed participants)*
The core shared layer. Records the *act* of validation: protocol registered, attestation signed, warrant issued on disagreement. Not the content of the validation — only the signed outcome summary. Agreement detection operates on structured outcome summaries, not raw result hashes. This resolves the fundamental problem that computational reproduction almost never produces bit-identical outputs: two validators can agree without their results being identical to the byte.

**DNA 4 — Governance and Harmony Records App** *(public DHT)*
Harmony Records, badges, and public validation status — what journals, funders, and institutions query. Governance-controlled writing, publicly readable. Anti-domestication mechanics live here: default salience rules, anti-delay constraints, funding concentration tripwires.

The eight-layer framework below remains the correct conceptual description of what ValiChord does. The layers now map across these four DNAs rather than sitting in one application. Where a layer's primary home in the DNA structure is relevant, it is noted.

**Precedent:** This four-DNA membrane pattern is independently validated by the holo-health project, a Holochain-based architecture for person-centric healthcare ecosystems designed by Steve Melville (https://github.com/evomimic/holo-health/blob/master/holo-health-app-architecture.md). The holo-health architecture uses an identical structure for an analogous problem: a private Personal Health Vault (equivalent to ValiChord's Researcher Repository DNA) holds sensitive personal data under the individual's control; a Health Market hApp (equivalent to ValiChord's Attestation DNA) provides the shared public space where parties find each other under agreed terms; and a Health Service Delivery hApp (equivalent to ValiChord's per-validation private channel) creates a private, audited space for each individual transaction, recording the *act* of data sharing without storing the sensitive data itself. Two independent teams reached the same membrane architecture for the same class of problem — sensitive personal data that must remain under individual control while participating in a shared verification ecosystem. Steve Melville is also one of the contacts identified by Arthur Brock as directly relevant to ValiChord's design.

---

### How a Researcher Experiences This

The eight layers below are architectural components, not sequential steps. A researcher doesn't navigate them one by one — they interact with ValiChord through a single submission process, and the layers work together behind the scenes. Here's the chronological experience:

1. **Researcher submits study** (data, code, protocol — one submission). Layer 0 fingerprints and stores the materials. Layer 1 registers the protocol claims. Layer 2 assesses difficulty.
2. **Validators are anonymously assigned** based on expertise matching and conflict-of-interest screening (Layer 3 governance, Layer 2 engine).
3. **Validators download materials** from Layer 0 — the fingerprint guarantees every validator works from identical data.
4. **Validators independently attempt reproduction** and submit their findings (Layer 2).
5. **Results are recorded** as a Harmony Record — preserving agreement, disagreement, and uncertainty (Layer 5), with full provenance (Layer 4).
6. **Gaming detection** runs continuously in the background (Layer 2, Layer 6).
7. **The Harmony Record is published** and accessible to researchers, journals, funders, and the public (Layer 7, Layer 8).

The layers interleave — they don't stack sequentially. What follows is the engineering breakdown of each layer.

The eight layers divide ValiChord's responsibilities as follows. **Layer 0** is the cryptographic foundation: content-addressed storage ensuring every validator works from provably identical materials. Without it, no validation claim can be trusted. **Layer 1** handles protocol intake and pre-commitment: structured pre-registration, deviation tracking, and epistemic impact assessment — the front-end guarantee that research questions were honestly specified before results were known. **Layer 2** is the validation engine: validator selection, blind commitment protocols (private source chain entries sealed before simultaneous countersigned reveal), gaming detection, agreement analysis, and the warrant mechanism that flags and records bad actors without requiring central enforcement. **Layer 3** is governance: the discipline-specific standards, anti-capture mechanics, and accountability structures that define the rules of the system and resist institutional pressure to soften them. **Layer 4** is the audit and provenance layer: a tamper-evident record of every action, distributed across Holochain's participant network, providing the accountability chain that external parties rely on. **Layer 5** produces outputs: Harmony Records, badges, and certification signals that journals, funders, and institutions consume. **Layer 6** handles incentives and reputation: the multi-dimensional scoring and career credit mechanisms that make sustained participation rational for working researchers. **Layers 7 and 8** handle integration and presentation: the HTTP Gateway, REST APIs, and user interfaces that connect ValiChord to the wider ecosystem without requiring institutional partners to replace existing systems. Each layer maps to one or more of the four Holochain DNAs described above — the engineering breakdown notes the primary DNA home where relevant.

---

## LAYER 0: Data & Integrity Foundation

**Purpose:** Ensure all validators work from provably identical materials, and that those materials remain available and verifiable long-term.

**Why this is critical:** ValiChord's core claim is that multiple independent validators assessed the same study. For that claim to be verifiable — not just asserted — every validator must provably have worked from the same data, code, and protocol. Content-addressed verification guarantees this: each participant's local node generates a cryptographic fingerprint of every submitted file. For research files (data, code, protocol documents), SHA-256 is used — the standard for academic repositories and broadly supported by verification tools. Holochain's own internal addressing uses BLAKE2b, a faster algorithm, for its records and attestations. These are separate layers: the SHA-256 fingerprint identifies the research materials; Holochain's BLAKE2b addressing identifies the validation actions performed on them. Change a single bit and the fingerprint changes. Anyone can verify, at any time, that their copy matches every other copy. Arthur Brock describes this property as **intrinsic data integrity**: the data is self-validating — you can tell if it has been tampered with because the tampering breaks the packaging. The data itself can be stored on any reliable provider — academic repositories, cloud storage, or institutional systems. What matters is the fingerprint recorded on Holochain, not where the files live. Redundant storage across multiple providers ensures the materials outlive any single institution.

### Core Data Structure

> **Type conventions:** Throughout this document, the following type aliases are assumed: `Hash` = `[u8; 32]` (SHA-256 digest for research file fingerprints; Holochain internally uses BLAKE2b for its own addressing), `DateTime` = UTC timestamp, `AgentId` = Holochain `AgentPubKey` (unique cryptographic identity per participant), `ValidatorId` = `AgentId` (alias for readability when the agent is acting as a validator), `Discipline` = enum of scientific fields. `Signature` = cryptographic signature from an agent's keypair. These are illustrative — final type definitions depend on Holochain SDK version and engineering decisions.

```rust
/// Content-addressed, tamper-evident data snapshot
pub struct VerifiedDataSnapshot {
    /// Unique content identifier (SHA-256 hash of contents)
    pub content_id: Hash,
    
    /// Redundant storage locations
    pub storage_locations: Vec<StorageLocation>,
    
    /// SHA-256 hash (primary integrity verification)
    pub sha256_hash: Hash,
    
    /// Dataset metadata
    pub size_bytes: u64,
    pub created_at: DateTime,
    pub creator_id: AgentId,
}

/// Storage location is deliberately agnostic — the fingerprint matters, not where the data lives.
/// Academic repositories (Zenodo, Figshare, institutional repositories) are the natural first choice
/// for research data. Cloud storage (S3, Azure Blob) is also viable. Decentralised storage (IPFS,
/// Arweave, Filecoin) remains an option but is not required.
pub enum StorageLocation {
    Zenodo { deposit_id: String },
    Figshare { article_id: String },
    InstitutionalRepository { url: String },
    S3 { bucket: String, region: String },
    Other { provider: String, location: String },
}
```

> **Engineering note:** The choice of storage provider is an implementation decision, not an architectural one. The integrity guarantee comes from the content hash recorded on Holochain, not from the storage system itself. Any provider that allows validators to download the original files and verify the hash is sufficient. Academic repositories are preferred for familiarity, trust, and long-term sustainability. Storage costs and provider longevity are operational concerns that need addressing in Phase 1/2 planning.

### Large Dataset Handling

**Problem:** Terabyte datasets are slow to download but validators need the complete dataset to run the code.

**Solution:** Standard SHA-256 hash verification. Validators download the full dataset from the storage provider, hash it locally, and compare against the fingerprint recorded on Holochain. Match means identical data. This works for any file size.

> **Engineering note:** At Phase 3 scale, if bandwidth from source repositories becomes a bottleneck, peer-to-peer chunk distribution between validators could reduce load. This is a future performance optimisation, not a current architectural requirement.

### GDPR Compliance: Data/Proof Separation

**Challenge:** Patient data requires "right to be forgotten" (GDPR Article 17).

**Solution:** In the multi-DNA architecture, GDPR compliance is structurally enforced: sensitive data lives in the private Researcher Repository DNA and cannot enter the shared Attestation DHT by design. The hash approach below provides an additional layer — useful for any data summary properties that do need to travel to the Attestation layer — but the membrane is the primary protection, not a policy overlay on top of a shared system.

```rust
pub fn hash_dataset_with_salt(data: &[u8], salt: &[u8]) -> Hash {
    let salted = [data, salt].concat();
    Hash::digest(&salted)
}

// Validator receives salt from data custodian off-DHT
// DHT stores only salted hash
// Attacker cannot compute same hash without salt
// Re-identification prevented
```

> **Engineering note:** Holochain Actions already contain unique properties that differentiate hashes — explicit random salting of Action/Record hashes is therefore unnecessary, as the Action itself provides equivalent uniqueness. For data hashes specifically (where the content being hashed is research data rather than a Holochain Action), the serialisation approach remains the more fundamental question: the Validator Workspace DNA must ensure data is serialised identically before hashing. The salt distribution mechanism is a secondary concern once the membrane architecture guarantees data locality.

A further privacy property follows from how Holochain records actions: a researcher can share a history of **headers** — each containing a timestamp, sequence number, and hash of the entry below it — without ever sharing the data those headers refer to. This means a researcher can prove to an external party that a particular dataset existed at a particular time, and that it has not been modified since, without the data itself ever leaving the private Researcher Repository DNA. For GDPR-sensitive studies, this header-only provenance path allows the Attestation layer to carry full chronological accountability while the underlying data remains under the researcher's control.

---

## LAYER 1: Intake & Pre-Commitment

**Purpose:** Bring research into ValiChord in structured, machine-legible form with pre-commitment enforcement. This is the front-end protection that complements back-end validation.

### Pre-Registered Protocol

```rust
/// Pre-registered protocol with committed analysis plan
pub struct PreRegisteredProtocol {
    /// Unique protocol identifier
    pub protocol_id: Hash,
    
    /// Time-locked analysis plan (sealed after lock period)
    pub analysis_plan: TimeLocked<AnalysisPlan>,
    
    /// Pre-specified hypotheses
    pub hypotheses: Vec<Hypothesis>,
    
    /// Confirmatory vs exploratory declaration
    pub analysis_type: AnalysisType,
    
    /// Pre-specified outcome measures
    pub primary_outcomes: Vec<OutcomeMeasure>,
    pub secondary_outcomes: Vec<OutcomeMeasure>,
    
    /// Stopping rules (when to end data collection)
    pub stopping_rules: StoppingRules,
    
    /// Sample size justification
    pub sample_size: SampleSizeSpec,
    
    /// Deviation allowances (structured)
    pub allowed_deviation_types: Vec<DeviationType>,
    
    /// Registration timestamp
    pub registered_at: DateTime,
    
    /// Institutional signature
    pub institutional_approval: Signature,
}

/// Analysis plan is frozen at registration
pub struct TimeLocked<T> {
    pub inner: T,
    pub locked_at: DateTime,
    pub locked_hash: Hash,
    pub modification_history: Vec<Modification>,
}

impl<T> TimeLocked<T> {
    /// Modifications require explicit declaration + justification
    pub fn request_modification(
        &mut self,
        modification: Modification,
        justification: String,
        epistemic_impact: EpistemicImpact,
        requested_by: AgentId,
    ) -> Result<(), Error> {
        if epistemic_impact == EpistemicImpact::Substantial {
            return Err(Error::RequiresGovernanceReview);
        }
        
        self.modification_history.push(Modification {
            changed_at: SystemTime::now(),
            justification,
            impact: epistemic_impact,
            approver: requested_by,
        });
        
        Ok(())
    }
}
```

### Deviation Typology

Not all deviations are equal. The system must distinguish between them.

```rust
pub enum DeviationType {
    /// Data access issues (ethical, logistical)
    DataAccess {
        reason: String,
        impact: EpistemicImpact,
    },
    
    /// Ethical concerns requiring protocol change
    EthicalConcern {
        review_board: String,
        decision_date: DateTime,
    },
    
    /// Statistical model didn't converge as planned
    ModelFailure {
        attempted_model: String,
        fallback_model: String,
        justification: String,
    },
    
    /// Computational constraints
    ComputationalLimit {
        planned_method: String,
        actual_method: String,
        reason: String,
    },
    
    /// Sample size adjustment
    SampleSizeAdjustment {
        original_n: usize,
        revised_n: usize,
        power_analysis: String,
    },
}

pub enum EpistemicImpact {
    /// No impact on inference
    Minimal,
    
    /// May affect confidence bounds
    Moderate,
    
    /// Changes interpretation — triggers governance review
    Substantial,
}
```

### Verifiable Claim Structure

```rust
/// Explicit, versioned, testable claim
pub struct VerifiableClaim {
    pub claim_id: Hash,
    
    /// Natural language statement
    pub statement: String,
    
    /// Formal specification
    pub formal_spec: FormalClaim,
    
    /// Dependencies on other claims
    pub depends_on: Vec<Hash>,
    
    /// Evidence requirements
    pub evidence_threshold: EvidenceThreshold,
    
    /// Claim hierarchy position
    pub claim_type: ClaimType,
}

pub enum ClaimType {
    Primary,
    Secondary,
    Exploratory { disclosed: bool },
    Robustness,
}

pub struct FormalClaim {
    pub null_hypothesis: String,
    pub alternative_hypothesis: String,
    pub significance_threshold: f64,
    pub test_statistic: String,
    pub direction: Direction,
}
```

### External Linking

```rust
pub struct ExternalLinks {
    pub osf_project: Option<String>,
    pub github_repo: Option<String>,
    pub preregistration_doi: Option<String>,
    pub trial_registry: Option<String>,
}
```

### Submission Workflow

```
Researcher submits protocol
         ↓
Protocol normalised to ClaimObject
         ↓
Pre-commitment validation rules check:
  • Hypotheses testable?
  • Outcome measures specified?
  • Stopping rules clear?
  • Sample size justified?
         ↓
Time-lock applied (sealed after 24h)
         ↓
Protocol hash posted to DHT
         ↓
Institutional signature required
         ↓
Protocol registered → can begin data collection
```

> **Engineering question:** The "normalised to ClaimObject" step is hand-waved here. In practice, converting free-text research protocols into structured, machine-legible claims is a significant NLP/UX challenge. This likely needs a structured submission form rather than automated parsing. The exact form design is a Phase 1 task.

---

## LAYER 2: Validation Engine

**Purpose:** Coordinate distributed validation with gaming detection and collusion resistance. This is ValiChord's core.

### Validation Request

```rust
pub struct ValidationRequest {
    /// References Layer 1 pre-registered protocol
    pub protocol_ref: Hash,
    
    /// Or external protocol if pre-registration not required
    pub protocol: Option<Protocol>,
    
    /// Data snapshot from Layer 0
    pub data_snapshot: VerifiedDataSnapshot,
    
    /// Validation parameters
    pub num_validators_required: u8,
    pub validation_tier: ValidationTier,
}

pub enum ValidationTier {
    /// Simple computational reproducibility
    Basic,
    
    /// Includes robustness checks
    Enhanced,
    
    /// Full methodological review
    Comprehensive,
}
```

### Automated Difficulty Assessment

**Purpose:** Predict validation difficulty from observable surface features before a validator begins work. This determines compensation bands, triage routing, time estimates, and exclusion recommendations.

**Why this matters:** Without difficulty prediction, every study entering ValiChord is a guess — you can't quote a time to a journal, set fair compensation for a validator, or tell a funder what validation costs per study. The difficulty assessment system is what makes ValiChord operationally viable.

**Phase 0 provides the training data.** By recording surface features alongside actual validation time and difficulty, Phase 0 produces the first empirical link between what a study looks like from the outside and what validation actually involves. This evidence underpins every stage of the assessment system.

#### Stage 1: Rule-Based Scoring (Phase 1, early)

A weighted rubric derived directly from Phase 0 correlations. When a study enters ValiChord, the system scores observable features:

```rust
pub struct DifficultyAssessment {
    /// Surface feature scores (each 1-5)
    pub code_volume: u8,           // Lines of code, number of scripts
    pub dependency_count: u8,       // External packages, libraries, APIs
    pub documentation_quality: u8,  // README presence, inline comments, method description
    pub data_accessibility: u8,     // Public download, request-access, proprietary
    pub environment_complexity: u8,  // Standard languages vs proprietary software, containers
    pub study_age: u8,             // Years since publication (older = more dependency rot)
    
    /// Weighted composite score → predicted difficulty tier
    pub predicted_tier: DifficultyTier,
    pub predicted_time_range: (Duration, Duration),  // min-max estimate
    pub confidence: AssessmentConfidence,
}

pub enum DifficultyTier {
    Standard,     // ~4-8 hours predicted
    Moderate,     // ~8-16 hours predicted
    Complex,      // ~16-30 hours predicted
    Extreme,      // ~30+ hours predicted — flagged for triage review
    Excluded,     // Fails minimum criteria — not accepted into system
}
```

Weights are set from Phase 0 data. If Phase 0 shows documentation quality is the strongest predictor and study age barely matters, the rubric reflects that. A researcher submitting a study or a journal integrating with ValiChord receives an immediate difficulty estimate.

This is straightforward engineering. The scoring rubric could be a simple web form initially, or — better — a script that analyses a code repository automatically.

#### Stage 2: Semi-Automated Analysis (Phase 1, later)

A tool that pulls a study's code repository and automatically generates surface feature scores:

- Count lines of code across all scripts
- Identify and count external dependencies (from requirements.txt, DESCRIPTION, package.json, etc.)
- Check for README, documentation files, inline comment density
- Test whether data URLs resolve and data files are downloadable
- Detect proprietary software requirements
- Check for Docker/container definitions
- Assess age of last commit and dependency versions

Output: automated difficulty estimate with confidence level, flagging studies that need human triage review.

**Precedent:** This type of automated assessment is well-established in adjacent domains:

- **Ripeta / RipetaScore** (Digital Science): Uses NLP and machine learning to automatically score scientific papers on reproducibility trust markers — data availability, code availability, methodology transparency, ethical approvals. Integrated into Dimensions database (33 million papers) and the Editorial Manager submission system. Produces a weighted composite score (0–30) combining professionalism and reproducibility indicators. Published in *Frontiers in Research Metrics and Analytics* (2021). Ripeta assesses *reporting quality* from the manuscript; ValiChord's system would assess *validation difficulty* from the code and data — a complementary but distinct prediction target.

- **SonarQube / Code Climate**: Industry-standard automated code quality platforms used by millions of developers. Score code on cyclomatic complexity, duplication, dependency health, test coverage, and maintainability. These metrics overlap substantially with what predicts validation difficulty — complex, poorly-tested, heavily-dependent code is harder to validate. ValiChord could integrate or adapt these scoring engines rather than building from scratch.

- **CODECHECK** (Cambridge/Münster): An open-science initiative where independent codecheckers attempt to reproduce computational results and issue certificates. 25+ checks completed across multiple journals. CODECHECK demonstrates the manual version of what ValiChord automates — and its experience confirms that documentation quality and environment specification are key determinants of reproducibility success.

- **FAIRER-Aware Reproducibility Assessment**: A government-backed checklist tool scoring data assets and code on findability, accessibility, interoperability, reusability, ethics, and reproducibility. Discipline-agnostic. Demonstrates that structured, automated reproducibility scoring is both feasible and institutionally accepted.

**What none of these tools do** is predict how long validation will actually take, or link surface features to empirical time data. That is the specific gap Phase 0 fills, and the specific capability the ValiChord difficulty assessment system provides.

#### Stage 3: Statistical Model (Phase 2+, with volume)

Once Phase 1 generates 200+ validations with linked surface features and actual time data, a regression model can be trained:

- Input: surface feature scores (automated from Stage 2)
- Output: predicted validation time, difficulty tier, and confidence interval
- Model improves as data accumulates — each completed validation is a new training example
- Can eventually identify non-obvious predictors that rule-based systems miss

This requires volume that Phase 0 and early Phase 1 cannot provide. 16–20 validation events from Phase 0 establish which features matter; 200+ from Phase 1 start making statistical prediction viable; Phase 2's scale makes it reliable.

> **Engineering note:** The three stages are not replacements but layers. Stage 1 provides the initial rubric. Stage 2 automates data collection for the rubric. Stage 3 learns from accumulated evidence to refine predictions beyond what any rubric captures. All three can coexist — the rule-based system provides explainable baseline scores while the statistical model flags cases where its predictions diverge from the rubric, indicating non-obvious difficulty.

#### Improvement Feedback (Phase 1+)

Studies that fail triage or score poorly on the difficulty assessment should not simply be rejected. The assessment system already knows *why* a study scored poorly — the same surface feature scores that determine difficulty can generate actionable improvement recommendations.

```rust
pub struct ImprovementReport {
    pub study_ref: Hash,
    pub overall_assessment: DifficultyTier,
    pub feature_scores: DifficultyAssessment,
    
    /// Specific, actionable recommendations per low-scoring feature
    pub recommendations: Vec<ImprovementRecommendation>,
    
    /// Estimated tier after improvements applied
    pub projected_tier_if_improved: DifficultyTier,
}

pub struct ImprovementRecommendation {
    pub feature: SurfaceFeature,
    pub current_score: u8,
    pub target_score: u8,
    pub action: String,         // e.g., "Pin dependency versions in requirements.txt"
    pub guidance_link: String,   // Link to best-practice documentation
    pub estimated_effort: String, // e.g., "~2 hours"
}
```

**Why this matters beyond ValiChord:** Every study that improves its documentation, pins its dependencies, or makes its data accessible in response to ValiChord feedback becomes more reproducible for *everyone* — not just for ValiChord validators. The feedback system turns ValiChord from a verification service into an active driver of better computational research practices. Over time, studies arriving at ValiChord get cleaner because researchers learn what validatable research looks like.

**Equity dimension:** The researchers who produce the most meticulously documented code repositories tend to be those in well-funded labs with dedicated research software engineers and institutional support. Early-career researchers, those in under-resourced institutions, and interdisciplinary thinkers who learned to code independently may produce groundbreaking science with poorly organised materials. Without feedback, ValiChord's triage filters them out — validating the studies that were already most likely to be reproducible. With feedback, ValiChord ensures that validation accessibility isn't determined by institutional resources.

#### Assisted Correction (Phase 2+)

Beyond diagnostic feedback, ValiChord can generate *proposed corrections* — a drafted README, pinned dependencies, restructured file organisation, clearer method descriptions — that the researcher reviews and approves before resubmission.

```rust
pub struct AssistedCorrection {
    pub study_ref: Hash,
    pub original_materials: MaterialsSnapshot,
    
    /// Proposed corrected versions of low-scoring materials
    pub proposed_corrections: Vec<CorrectionProposal>,
    
    /// Status: always requires explicit author approval
    pub status: CorrectionStatus,
}

pub enum CorrectionStatus {
    /// Corrections generated, awaiting author review
    PendingAuthorReview,
    
    /// Author has reviewed and approved all corrections
    AuthorApproved { approved_at: Timestamp, author_id: AuthorId },
    
    /// Author has edited corrections before approving
    AuthorModified { modified_at: Timestamp, author_id: AuthorId },
    
    /// Author has rejected corrections (with reason)
    AuthorRejected { reason: String },
}
```

**Critical constraint: ValiChord never modifies or submits research materials without explicit author approval.** Automated corrections might pin wrong dependency versions, mischaracterise methods, or restructure code in ways that subtly change its behaviour. Only the author knows whether the corrected version faithfully represents their work. A clean-looking README that misrepresents the analysis is worse than a messy one that's honest. The author's name is on the research; the author retains control.

**Workflow:** Submit study → triage scores it → study doesn't meet threshold → ValiChord generates proposed corrections → author reviews → author approves, edits, or rejects → approved version enters validation pipeline.

**Precedent:** Ripeta already does this for manuscript reporting quality — it scores papers and tells authors what's missing before peer review. SonarQube does it for code quality in software engineering. ValiChord would do it for *validatability* — a dimension nobody currently assesses or provides feedback on. The assisted correction step goes further than any existing tool by proposing fixes rather than just identifying problems.

#### Self-Service Pre-Vetting Tool (Phase 2+)

The feedback and assisted correction systems are reactive — they operate after submission. The self-service tool moves assessment upstream: researchers run ValiChord's scoring rubric locally, on their own machine, before ever interacting with ValiChord's infrastructure.

```rust
pub struct PreVetReport {
    /// Generated locally — never transmitted unless researcher opts in
    pub repository_path: String,
    pub scan_timestamp: Timestamp,
    
    /// Same scoring rubric as ValiChord triage
    pub feature_scores: DifficultyAssessment,
    pub predicted_tier: DifficultyTier,
    
    /// Actionable feedback per low-scoring feature
    pub recommendations: Vec<ImprovementRecommendation>,
    
    /// Overall readiness signal
    pub triage_prediction: TriagePrediction,
}

pub enum TriagePrediction {
    /// Likely to pass ValiChord triage as-is
    Ready,
    
    /// Likely to pass after addressing listed recommendations
    NearReady { blocking_issues: Vec<SurfaceFeature> },
    
    /// Significant work needed before submission
    NotReady { major_gaps: Vec<SurfaceFeature> },
}
```

**What the tool does:**

- Scans the local repository for documentation (README, method descriptions)
- Checks whether dependencies are pinned (requirements.txt, environment.yml, Dockerfile)
- Tests whether data URLs resolve (HTTP HEAD requests only — no downloads)
- Counts code volume, identifies languages and frameworks
- Checks for containerisation (Docker, Singularity)
- Assesses repository age and commit recency
- Produces a `PreVetReport` with scores, recommendations, and predicted triage outcome

**What the tool does NOT do:**

- Execute any research code (static analysis only — prevents malicious repository exploitation)
- Transmit any data without explicit opt-in (works fully offline by default)
- Confer any status within ValiChord's pipeline (pre-vetting carries zero authority; ValiChord runs its own triage regardless)
- Hide its scoring logic (the rubric is public by design — transparency about standards is the feature, not a vulnerability)

**Security model:**

| Concern | Mitigation |
|---|---|
| Malicious repository exploits scanning | Static analysis only; no code execution; sandboxed file reads |
| Gaming the rubric to pass triage | Tool checks form, not substance; ValiChord triage includes human review above complexity threshold |
| Spoofed pre-vetting certificates | Tool output has zero authority in ValiChord pipeline; no fast-track for pre-vetted submissions |
| Analytics data exfiltration | Opt-in only; anonymised before transmission; tool fully functional offline |
| Reverse-engineering scoring algorithm | Rubric is intentionally public; understanding what ValiChord expects is the point |

**Anonymous analytics (opt-in only):**

If researchers consent to anonymous usage reporting, ValiChord aggregates data on:

- Most common failure points across disciplines (e.g., "73% of psychology submissions lack pinned dependencies")
- Distribution of readiness scores by field
- Which recommendations are most acted on
- Improvement trajectories (do researchers who use the tool repeatedly produce cleaner repositories?)

This generates a dataset on computational research practices that nobody else has — covering the full ecosystem, not just the studies that reach formal validation.

**Strategic value:** The tool extends ValiChord's impact beyond the studies it formally validates. Every researcher who uses the tool produces more reproducible work, whether or not they submit to ValiChord. This positions ValiChord not just as verification infrastructure but as an active driver of better research practices across the entire ecosystem. It also functions as a natural adoption pipeline: researchers who use the free tool become familiar with ValiChord's standards and are more likely to submit studies for formal validation.

**Timeline:** This is the Stage B tool — Phase 2, once Phase 0's evidence has established which surface features predict difficulty and Phase 1's operational data has calibrated the scoring weights. The rubric must be empirically grounded before the tool can be built — otherwise it would be enforcing assumptions rather than evidence-based standards. A simpler Stage A version — *ValiChord at Home* (working name), a best-practice checklist that doesn't predict difficulty or estimate time — can be released alongside Phase 0 results as ValiChord's first public-facing product (see Phase 0 Deliverable 8). *ValiChord at Home* builds the community and generates ecosystem data. Stage B replaces it with empirically calibrated precision.

### Pre-Commitment Integration

```rust
impl ValidationEngine {
    /// When validating pre-registered protocol
    pub fn validate_with_precommitment(
        &self,
        protocol_ref: Hash,
        actual_execution: ExecutionReport,
    ) -> Result<ValidationTask, Error> {
        // Fetch pre-registered protocol from Layer 1
        let preregistered = self.fetch_preregistration(protocol_ref)?;
        
        // Compare planned vs actual
        let deviations = self.detect_deviations(
            &preregistered,
            &actual_execution,
        );
        
        // Assign validators with deviation context
        let validators = self.select_validators(
            &preregistered,
            deviations.epistemic_impact_level(),
        )?;
        
        // Validators receive:
        // 1. What should have happened (pre-registration)
        // 2. What actually happened (execution report)
        // 3. Declared deviations and justifications
        
        Ok(ValidationTask {
            protocol_ref,
            preregistered_plan: preregistered,
            actual_execution,
            declared_deviations: deviations,
            assigned_validators: validators,
            validation_focus: ValidationFocus::PreCommitmentAdherence,
        })
    }
}

pub enum ValidationFocus {
    /// Just check if code reproduces
    ComputationalReproducibility,
    
    /// Check adherence to pre-registered plan
    PreCommitmentAdherence,
    
    /// Check methodological soundness
    MethodologicalReview,
}
```

### Validator Assignment

Reputation-weighted constrained randomness with safeguards:
- Institutional caps (max 40% from one institution)
- Inverse size weighting (smaller institutions get proportionally more slots)
- **Double-blind by default.** Validators do not see author names, institutional affiliations, or funding sources. They receive the study protocol, code, data, and methodology — nothing that identifies who produced it. This prevents career deference: a junior validator who sees a Nobel laureate's name on a protocol may unconsciously look for reasons to confirm rather than critically assess. The commit-reveal protocol prevents validators from adjusting results after seeing others' findings, but only double-blinding prevents the subtler bias of knowing whose work you are assessing. Author identity is revealed only in the published Harmony Record, after all validators have submitted their final attestations.
- Blind commitment protocol prevents coordination between validators: findings are sealed as private source chain entries before any simultaneous reveal
- Validators do not know who else is validating the same study

> **Engineering question:** How much domain expertise do validators actually need? ValiChord validates computation, not scientific methodology. A chemist who can set up a Python environment and run a script can check whether a climate model produces the claimed outputs just as well as a climate scientist — the numbers either match or they don't. This suggests the validator pool could be much larger than domain-matched selection implies. However, a domain expert might notice that code ran successfully but produced intermediate values that are physically impossible (e.g. negative absolute temperature, impossible protein structure) — something a non-expert would miss. A possible model: "find three computationally competent researchers, at least one with domain familiarity" rather than "find three domain specialists." This would significantly ease panel assembly and reduce queue times, but the trade-off between computational-only and domain-informed validation needs empirical evidence. This is a question for the PI and should be explored in Phase 0 study design.

### Validator Attestation with Deviation Flagging

```rust
pub struct ValidationAttestation {
    pub validator_id: ValidatorId,
    pub validation_id: Hash,
    pub outcome: AttestationOutcome,
    pub detailed_report: String,
    pub time_invested: Duration,
    pub confidence: ConfidenceLevel,
    
    /// Deviation assessment — validators can flag undeclared deviations
    pub deviation_flags: Vec<UndeclaredDeviation>,
    
    /// Agreement with epistemic impact assessment
    pub impact_agreement: Option<ImpactAssessment>,
}

pub struct UndeclaredDeviation {
    pub deviation_type: DeviationType,
    pub severity: Severity,
    pub evidence: String,
    pub flagged_by: ValidatorId,
}
```

### Gaming & Collusion Detection Mechanisms

**Blind commitment via private source chain entries, followed by simultaneous countersigned reveal (commit-reveal):** Each validator records their findings as a *private entry* on their own Holochain source chain — visible only to them, cryptographically sealed by their signing key, and immutable from the moment of recording. This is the commitment: it cannot be changed after the fact, and its existence is verifiable on-chain even before its contents are shared. Once all assigned validators have recorded private entries, a *countersigning session* is initiated: all validators simultaneously contribute their findings to construct the shared Harmony Record entry, with each validator's chain locked during the session to prevent any party from adjusting their position after seeing others' results. All parties countersign the single Harmony Record entry atomically — no validator's findings are visible to the others until all findings are simultaneously committed to the shared Attestation DNA. This prevents last-mover advantage: a validator cannot see others' conclusions and adjust their own, because the private source chain entry is already sealed before the countersigning session begins.

> **In plain terms:** Each validator privately records their findings in a sealed, tamper-proof log before anyone else can see them. Only once every validator has sealed their own record does a joint session open — at which point all findings become visible simultaneously, and all validators sign the shared Harmony Record together. No validator can see what others found and adjust their own position. This is the standard cryptographic pattern known as commit-reveal, implemented here using Holochain's native private entries and countersigning mechanism rather than the hash-based approach common in blockchain systems.

**Result comparison and agreement detection:** Validators submit structured outcome summaries from their private Workspace DNA to the shared Attestation DNA. Agreement detection operates on these summaries — not by comparing raw result hashes. This is architecturally necessary: computational reproduction almost never produces bit-identical outputs due to floating point differences, non-deterministic operations, and hardware variation. Requiring exact hash matches would flag every validation as a disagreement. Instead, the Attestation DNA compares structured outcome summaries (key metrics, direction of effect, confidence intervals) and assesses whether results are within acceptable margins. What constitutes agreement is defined by discipline-specific standards in the Governance DNA.

**Detection patterns:**
- Collusion pattern detection (cross-institutional agreement >90% over 20+ validations)
- Access pattern clustering (validators accessing data at suspiciously similar times)
- Statistical outlier detection (MAD — Median Absolute Deviation)
- Time analysis (unrealistically fast or slow validations)
- Social distance mapping (co-authorship graph analysis)

**Warrants — Holochain's native enforcement mechanism:** When a participant publishes data that violates the DNA's validation rules, any peer that detects the violation creates and signs a **warrant** — a cryptographic proof of the bad action — and publishes it to the network. Warrants propagate automatically to the agent activity authorities responsible for tracking that participant's history. Once received, a warrant is permanent and discoverable by any node via `get_agent_activity`. Any node can check a validator's warrant status before interacting with them — for example, before accepting a commitment in the commit-reveal protocol. Automatic network-level blocking of warranted agents is on Holochain's roadmap; the current behaviour is that warrants are created, persisted, and queryable, with network block enforcement following. For ValiChord, this means a validator who submits fraudulent attestations can be warranted by peers and their status checked by any participant, without a governance committee needing to investigate and act first. Warrants were stabilised as a core feature in Holochain 0.7 (previously behind an experimental flag) — this enforcement mechanism is production-ready, not experimental.

> **Engineering question:** The specific thresholds for gaming detection (e.g., >90% agreement triggering investigation) need empirical calibration. Phase 0 data on natural agreement rates would inform these. Setting thresholds too low creates false positives; too high misses real collusion.

---

## LAYER 3: Governance & Policy

**Purpose:** Transparent, auditable rule-setting that resists institutional capture.

**Precedent for governance-enforced principles:** The holo-health project demonstrates that marketplace principles can be enforced at the membrane level — the conditions for joining the shared DHT can include commitment to specific principles, making them structurally binding rather than merely stated policy. ValiChord's Governance DNA applies the same pattern: disciplinary standards, anti-capture commitments, and epistemic integrity rules are enforced by the membrane function governing participation in the Attestation and Governance DNAs, not merely written into governance documents that can be quietly ignored.

The governance layer is specified in detail in the companion *Governance Framework* document. The technical implementation involves:

```rust
pub struct PreCommitmentGovernance {
    /// Standards for what requires pre-registration
    pub pre_registration_requirements: RequirementMatrix,
    
    /// Deviation approval authority
    pub deviation_review_board: ReviewBoard,
    
    /// Epistemic impact assessment guidelines
    pub impact_guidelines: ImpactGuidelines,
    
    /// Disciplinary standards
    pub discipline_standards: HashMap<Discipline, Standards>,
}

pub enum PreRegRequirement {
    Mandatory,
    Recommended,
    Optional,
    NotApplicable,
}
```

### Deviation Review Process

```
Researcher declares deviation with justification
         ↓
Automated impact assessment
         ↓
If Substantial impact → Review Board
         ↓
Board decision:
  - Approve with note
  - Require additional validation
  - Require re-registration
         ↓
Decision logged to tamper-evident record (Layer 4)
```

### Disciplinary Standards

Each discipline defines its own pre-registration standards. Example:

```yaml
discipline: computational_biology
pre_commitment_standards:
  hypotheses:
    - must_specify_model_architecture: true
    - must_specify_hyperparameters: true
    - must_specify_training_stopping_criteria: true
  
  acceptable_deviations:
    - model_convergence_issues: moderate_impact
    - hardware_constraints: minimal_impact
    - dataset_quality_issues: substantial_impact
  
  outcome_measures:
    - prediction_accuracy: required
    - confidence_intervals: required
    - cross_validation_method: required
```

> **Engineering question:** Who writes these disciplinary standards initially? They require genuine domain expertise. The current plan assumes Disciplinary Standards Committees (7–10 members per field), but recruiting these before the system has credibility is a chicken-and-egg problem. Phase 1 might need to start with 2–3 disciplines where advisory relationships already exist.

---

## LAYER 4: Audit & Provenance

**Purpose:** Tamper-evident record of every significant action — the system's memory.

### Audit Event Types

```rust
/// Every action creates a tamper-evident, append-only log entry
pub enum AuditEvent {
    /// Layer 1 events
    ProtocolRegistered {
        protocol_id: Hash,
        registered_by: AgentId,
        registered_at: DateTime,
        protocol_hash: Hash,
    },
    ProtocolModificationRequested {
        protocol_id: Hash,
        modification: Modification,
        justification: String,
        impact: EpistemicImpact,
    },
    DeviationDeclared {
        protocol_id: Hash,
        deviation: DeviationType,
        declared_at: DateTime,
        declared_by: AgentId,
    },
    
    /// Layer 2 events
    ValidationRequested {
        protocol_id: Hash,
        requester: AgentId,
    },
    ValidatorAssigned {
        validation_id: Hash,
        validator_id: ValidatorId,
        assigned_at: DateTime,
    },
    AttestationSubmitted {
        validation_id: Hash,
        validator_id: ValidatorId,
        outcome: AttestationOutcome,
        submitted_at: DateTime,
    },
    
    /// Layer 5 events
    HarmonyRecordGenerated {
        protocol_id: Hash,
        harmony_record_hash: Hash,
        generated_at: DateTime,
    },
    
    /// Layer 6 events
    ReputationUpdated {
        validator_id: ValidatorId,
        old_score: f64,
        new_score: f64,
        reason: String,
    },
    
    /// Layer 3 events
    GovernanceDecision {
        decision_type: DecisionType,
        made_by: GovernanceBody,
        rationale: String,
        made_at: DateTime,
    },
}
```

### Provenance Graph

```rust
/// Complete lineage from hypothesis → validation
pub struct ProvenanceGraph {
    /// Root: Pre-registered protocol
    pub root: Hash,
    
    /// Nodes: All related entities
    pub nodes: Vec<ProvenanceNode>,
    
    /// Edges: Relationships
    pub edges: Vec<ProvenanceEdge>,
}

pub enum ProvenanceNode {
    PreRegistration(Hash),
    Modification(Hash),
    Deviation(Hash),
    DataSnapshot(Hash),
    ValidationRequest(Hash),
    Attestation(Hash),
    HarmonyRecord(Hash),
    Publication(Hash),
}

pub enum ProvenanceEdge {
    ModifiedFrom,
    DeviatedFrom,
    ValidatedUsing,
    GeneratedFrom,
    PublishedAs,
    CitedBy,
}
```

### Provenance Queries

```rust
impl ProvenanceGraph {
    /// "Show me everything that happened to this protocol"
    pub fn full_history(&self, protocol_id: Hash) -> FullHistory;
    
    /// "Did this protocol have substantial deviations?"
    pub fn check_deviations(&self, protocol_id: Hash) -> DeviationReport;
    
    /// "What validators worked on this?"
    pub fn validator_history(&self, protocol_id: Hash) -> Vec<ValidatorId>;
    
    /// "Has anyone cited this validation?"
    pub fn citation_network(&self, protocol_id: Hash) -> CitationGraph;
}
```

### Holochain Implementation

In the multi-DNA architecture, audit events are distributed across DNAs according to where they originate: registration events live on the Researcher Repository and Attestation DNAs; validation events on the Validator Workspace and Attestation DNAs; governance decisions on the Governance DNA. Every action is recorded within its respective DNA on Holochain. The provenance graph is built from queries across DNAs via bridges. Tamper-evidence is guaranteed by Holochain's architecture — every participant's record is append-only and any modification is detectable by peers. No central audit database exists or is required.

Crucially, Holochain's header structure creates a provenance path that does not require data disclosure. A researcher or validator can present the chain of headers — each containing a timestamp, sequence number, author signature, and hash of the entry it covers — to demonstrate when data was first committed and that it has remained unchanged, without ever sharing the data below those headers. External parties (journals, funders, regulators) can verify the chain's integrity from the headers alone. Note that Holochain Actions already contain author key, signature, and timestamp natively — these fields do not need to be duplicated inside entry structs.

**Precedent for audit trail value:** The holo-health project identifies an identical problem in healthcare: physicians are reluctant to trust health records held in patient custody because they cannot verify the records are complete and unaltered. The holo-health solution — an immutable, non-forgeable, non-repudiable audit trail in the shared DHT — gives practitioners confidence that records are unchanged. ValiChord's Attestation DNA provides the same guarantee to journals and funders: a validation attestation recorded on the DHT cannot have been altered after submission, which is exactly the assurance needed to make Harmony Records trustworthy to external parties.

### Public vs Private Views

```rust
pub struct AuditRecord {
    /// Public (always visible)
    pub public_summary: PublicSummary,
    
    /// Internal (Research Integrity Office only)
    pub internal_details: Option<InternalDetails>,
    
    /// Validator-visible (can see own details)
    pub validator_view: Option<ValidatorDetails>,
}
```

---

## LAYER 5: Output & Certification

**Purpose:** Transform internal processes into externally usable trust signals. This is what journals, funders, and institutions consume.

### Harmony Record

The canonical output of ValiChord. Preserves the full texture of agreement and disagreement rather than producing a single verdict.

```rust
pub struct HarmonyRecord {
    pub record_id: Hash,
    pub protocol_id: Hash,
    
    /// Validation summary
    pub validation_summary: ValidationSummary,
    
    /// Validator details (respecting attribution rules)
    pub validators: Vec<ValidatorSummary>,
    
    /// Disagreement visibility (forced, per Governance commitments)
    pub disagreements: Vec<Disagreement>,
    
    /// Epistemic confidence
    pub confidence_level: ConfidenceLevel,
    
    /// Reproducibility status
    pub status: ReproducibilityStatus,
    
    /// Issue date and validity
    pub issued_at: DateTime,
    pub valid_until: DateTime,  // 24 months minimum per Governance
    
    /// Link to full provenance
    pub provenance_link: String,
}

pub struct ValidationSummary {
    pub total_validators: u8,
    pub successful_validations: u8,
    pub partial_validations: u8,
    pub failed_validations: u8,
    pub inconclusive_validations: u8,
    
    pub agreement_level: f64,
    pub outlier_count: u8,
    pub variance_explained: Option<VarianceReport>,
}

pub enum ConfidenceLevel {
    High {
        agreement: f64,
        reasoning: String,
    },
    Medium {
        concerns: Vec<String>,
        reasoning: String,
    },
    Low {
        substantial_disagreement: bool,
        reasoning: String,
    },
}

pub enum ReproducibilityStatus {
    ExactMatch { validator_count: u8 },
    DirectionalMatch { 
        validator_count: u8,
        variance_explanation: String,
    },
    PartialMatch {
        successful_aspects: Vec<String>,
        failed_aspects: Vec<String>,
    },
    Failed {
        failure_reasons: Vec<String>,
        validator_count: u8,
    },
    Inconclusive {
        reasons: Vec<String>,
    },
    /// The system refuses to force a verdict where evidence doesn't support one
    PersistentlyIndeterminate {
        time_elapsed: Duration,
        validator_count: u8,
        disagreement_summary: String,
    },
}
```

### Reproducibility Badges

Domain-specific, not gamified. Cannot be reduced to a single numerical score.

```rust
pub enum ReproducibilityBadge {
    ComputationalReproducible {
        level: BadgeLevel,
        discipline: Discipline,
    },
    PreRegisteredAndValidated {
        adherence_score: f64,
    },
    OpenDataValidated {
        data_availability: DataAvailability,
    },
    MultiLabValidated {
        lab_count: u8,
        geographic_diversity: f64,
    },
}

pub enum BadgeLevel {
    Bronze,  // Basic validation passed (≥3 validators, ≥60% success)
    Silver,  // Enhanced + good practices (≥5 validators, ≥70%, pre-registered)
    Gold,    // Comprehensive + exemplary (≥7 validators, ≥80%, multi-institutional)
}
```

### Narrative Reports

Human-readable summaries tailored for different audiences.

```rust
pub struct NarrativeReport {
    pub executive_summary: String,
    pub protocol_description: String,
    pub validation_process: String,
    pub findings: String,
    pub limitations: Vec<String>,  // Always included
    pub recommendations: Vec<String>,
    pub generated_at: DateTime,
}

impl NarrativeReport {
    /// Auto-generate from Harmony Record
    pub fn from_harmony_record(record: &HarmonyRecord) -> Self {
        // Template-based generation with discipline-specific language
        // Explicitly flags disagreements (per Governance commitments)
        // Avoids overconfident language
        // Includes appropriate caveats
    }
}
```

### External API

```rust
pub trait ValiChordAPI {
    async fn get_validation_status(
        &self, protocol_id: Hash,
    ) -> Result<HarmonyRecord, Error>;
    
    async fn check_funder_requirements(
        &self, protocol_id: Hash, funder_id: String,
    ) -> Result<ComplianceReport, Error>;
    
    async fn get_researcher_portfolio(
        &self, researcher_id: String,
    ) -> Result<ResearcherPortfolio, Error>;
    
    async fn get_institutional_metrics(
        &self, institution_id: String,
    ) -> Result<InstitutionalMetrics, Error>;
    
    async fn query_by_external_id(
        &self, external_id: String,
    ) -> Result<Vec<HarmonyRecord>, Error>;
}
```

---

## LAYER 6: Incentive & Reputation

**Purpose:** Align behaviour with system goals — make doing the right thing the easiest thing.

### Reputation System

Multi-dimensional scoring. No single number that can be gamed.

```rust
pub struct UnifiedReputation {
    /// Validation track record
    pub validation_score: ReputationScore,
    
    /// Pre-registration quality
    pub preregistration_score: ReputationScore,
    
    /// Deviation handling quality
    pub deviation_score: ReputationScore,
    
    /// Time invested (quality signal)
    pub time_investment: TimeMetrics,
    
    /// Peer ratings
    pub peer_endorsements: u32,
    
    /// Disciplinary expertise
    pub expertise_areas: HashMap<Discipline, ExpertiseLevel>,
    
    /// Institutional affiliation
    pub institution: InstitutionId,
    
    /// Overall reputation (weighted)
    pub total_score: f64,
}
```

### Incentive Structure

```rust
pub enum ValidatorIncentive {
    /// CRediT taxonomy recognition
    CoAuthorshipCredit {
        credit_type: CreditType,
        weight: f64,
    },
    
    /// Career advancement
    CVRecognition {
        validation_count: u32,
        quality_score: f64,
    },
    
    /// Direct compensation (amount in minor currency units, e.g. pence)
    DirectPayment {
        amount_minor_units: u64,
        currency: String,
    },
    
    /// Reputation building
    ReputationGain {
        reputation_increase: f64,
        visibility_boost: f64,
    },
}

pub enum CreditType {
    ValidationExecution,
    MethodologyReview,
    FormalAnalysis,
    Software,
    WritingOriginalDraft,
}
```

### Tiered Credit

```rust
pub enum ValidationCreditTier {
    /// Quick check (1-2 hours): £50-100
    Tier1 { credit: f64, compensation_pence: u64 },
    
    /// Standard validation (4-8 hours): £200-400
    Tier2 { credit: f64, compensation_pence: u64 },
    
    /// Comprehensive review (16+ hours): £800-1600
    Tier3 { credit: f64, compensation_pence: u64 },
}
```

> **Engineering question:** These compensation tiers are illustrative. Phase 0 exists specifically to generate empirical data on what validation actually costs in time, which then determines what fair compensation looks like. The tiers above are placeholders pending Phase 0 evidence. Note: compensation is stored as integer pence rather than floating-point pounds — a standard practice to avoid rounding errors in financial calculations.

### Time Tracking & Audit Sampling

```rust
pub struct TimeTracking {
    pub reported_hours: f64,
    pub system_tracked_time: Duration,
    pub expected_time_range: (f64, f64),
    pub audit_flags: Vec<AuditFlag>,
}

pub enum AuditFlag {
    TooFast { expected_min: f64, actual: f64 },
    TooSlow { expected_max: f64, actual: f64 },
    InactivityPeriods { gaps: Vec<Duration> },
}

/// 10% random audit sampling (stratified)
impl AuditSystem {
    pub fn sample_for_audit(&self) -> Vec<ValidationId> {
        // 40% from new validators (< 10 validations)
        // 60% random from all validators
        // Flags take priority
    }
}
```

### Anti-Gaming Measures

```rust
pub struct IncentiveConstraints {
    /// No "validation count" races
    no_quantity_incentives: bool,
    
    /// Quality over speed — no bonuses for finishing fast
    quality_multiplier: f64,
    
    /// Diversity bonuses (not volume)
    diversity_bonus: DiversityBonus,
    
    /// Penalise homophily (>90% agreement with single institution)
    homophily_penalty: f64,
}

/// Diversity is an architectural requirement, not a policy preference. Credible validation
/// requires genuinely independent validators — different institutions, different geographies,
/// no co-authorship networks. This creates structural demand for distributed capability:
/// ValiChord needs qualified validators across regions to produce epistemically valid results.
/// Participation provides under-resourced labs with funded opportunities to build credibility
/// and methodological skills. Both sides need each other — this is mutual, not charitable.
pub struct DiversityBonus {
    /// Bonus for validating across disciplines
    cross_discipline: f64,
    
    /// Bonus for validating novel methods
    novel_methods: f64,
    
    /// Bonus for finding legitimate disagreement
    disagreement_discovery: f64,
    
    /// Bonus for geographic and institutional diversity in validator panels
    geographic_institutional: f64,
}
```

---

## LAYER 7: Integration & Interface

**Purpose:** How external systems plug into ValiChord. Journals, funders, and institutions query ValiChord; ValiChord is infrastructure, not a silo.

**Design rationale:** Most journals, funders, and universities already have existing editorial, grant management, and research information systems. Requiring them to adopt native Holochain applications as a condition of participation would be a significant barrier to entry. An API-first approach is therefore correct: institutions participate via standard REST APIs and webhooks, with Holochain handling the integrity guarantees behind the interface. This reasoning is directly validated by the holo-health project (Melville), which reached the same conclusion for healthcare providers: *"To require them to adopt a pure holochain-native application architecture for their internal systems would pose a significant barrier to entry... an API-based approach will be followed initially."* The parallel is exact.

**The HTTP Gateway — this is built:** Holochain released an HTTP Gateway in March 2025 (version 0.2 in July 2025) that provides exactly this bridge — standard HTTP requests routed to a running Holochain application. External systems can query ValiChord's Governance and Harmony Records DNA via ordinary HTTP without running a Holochain node. This means the core integration challenge for Layer 7 is largely solved infrastructure rather than custom development work. The REST API endpoints below represent the interface surface; the HTTP Gateway handles the translation to Holochain behind it.

### Integration Traits

```rust
pub trait JournalIntegration {
    async fn check_validation_status(
        &self, manuscript_id: String,
    ) -> Result<ValidationStatus, Error>;
    
    async fn require_validation(
        &self, article_type: ArticleType, minimum_tier: ValidationTier,
    ) -> Result<ValidationRequirement, Error>;
    
    async fn get_reproducibility_badge(
        &self, doi: String,
    ) -> Result<BadgeDisplay, Error>;
}

pub trait FunderIntegration {
    async fn check_grant_compliance(
        &self, grant_id: String,
    ) -> Result<ComplianceReport, Error>;
    
    async fn portfolio_risk_dashboard(
        &self, funder_id: String,
    ) -> Result<PortfolioDashboard, Error>;
}

pub trait RepositoryIntegration {
    async fn link_osf_project(
        &self, osf_id: String, protocol_id: Hash,
    ) -> Result<(), Error>;
    
    async fn link_github_commits(
        &self, repo: String, commits: Vec<String>, protocol_id: Hash,
    ) -> Result<(), Error>;
    
    async fn get_repo_validation_badge(
        &self, repo: String,
    ) -> Result<BadgeMarkup, Error>;
}
```

### REST API Endpoints

```text
// Core endpoints
POST   /api/v1/protocols                    // Submit new protocol
GET    /api/v1/protocols/{id}               // Get protocol details
PUT    /api/v1/protocols/{id}/deviations    // Declare deviation

POST   /api/v1/validations                  // Request validation
GET    /api/v1/validations/{id}             // Get validation status
GET    /api/v1/validations/{id}/harmony     // Get Harmony Record

GET    /api/v1/researchers/{orcid}          // Researcher portfolio
GET    /api/v1/institutions/{id}/metrics    // Institutional metrics
GET    /api/v1/funders/{id}/portfolio       // Funder portfolio

// Query by external identifier
GET    /api/v1/query/doi/{doi}
GET    /api/v1/query/osf/{osf_id}
GET    /api/v1/query/github/{repo}

// Webhook support
POST   /api/v1/webhooks/register
POST   /webhooks/{subscriber}
```

### Integration Flows

**Journal submission:**
```
Author submits manuscript
→ Journal system queries ValiChord: GET /api/v1/validation/{doi}
→ If validated: Display badge, proceed
→ If not validated: Prompt author, offer validation
→ Editor sees validation status in review interface
→ Reviewers see Harmony Record, can query details
```

**Funder review:**
```
PI submits grant application
→ Funder system queries: GET /api/v1/portfolio/{pi_orcid}
→ Displays PI's validation track record
→ Reviewer sees reproducibility history
→ Funding decision informed by validation quality
```

---

## LAYER 8: Access & Presentation

**Purpose:** Make the system legible to different audiences with appropriate views.

### Researcher Dashboard

```rust
pub struct ResearcherDashboard {
    active_protocols: Vec<ProtocolCard>,
    validation_queue: Vec<ValidationStatus>,
    completed_validations: Vec<HarmonyRecordSummary>,
    researcher_reputation: ReputationDisplay,
    portfolio_summary: PortfolioSummary,
    notifications: Vec<Notification>,
}

pub enum ProtocolStatus {
    PreRegistration { locked: bool },
    DataCollection { completion: f64 },
    ValidationRequested { queue_position: u32 },
    ValidationInProgress { 
        validators_assigned: u8,
        attestations_received: u8,
    },
    Validated { harmony_record: Hash },
    DeviationReview { pending_count: u8 },
}
```

### Validator Console

```rust
pub struct ValidatorConsole {
    assigned_validations: Vec<ValidationTask>,
    validation_tools: ValidationToolkit,
    upcoming_deadlines: Vec<Deadline>,
    researcher_communication: Vec<Message>,
    validator_reputation: ReputationDisplay,
    completed_validations: Vec<CompletedValidation>,
}

pub struct ValidationTask {
    pub task_id: Hash,
    pub protocol_summary: ProtocolSummary,
    pub pre_commitment: Option<PreRegisteredProtocol>,
    pub data_access_instructions: DataAccessInstructions,
    pub validation_tier: ValidationTier,
    pub deadline: DateTime,
    pub estimated_time: Duration,
    pub compensation: Compensation,
}

pub struct ValidationToolkit {
    pub data_fetcher: DataFetchTool,
    pub execution_environment: ExecutionEnv,
    pub attestation_form: AttestationForm,
    pub issue_reporter: IssueReporter,
    pub researcher_contact: ContactTool,
}
```

### Funder Dashboard

```rust
pub struct FunderDashboard {
    portfolio_summary: PortfolioSummary,
    risk_dashboard: RiskDashboard,
    compliance_status: ComplianceTracker,
    reproducibility_trends: TrendAnalysis,
    institutional_performance: HashMap<InstitutionId, Performance>,
}

pub struct PortfolioSummary {
    pub total_grants: u32,
    pub validated_outputs: u32,
    pub validation_in_progress: u32,
    pub pending_validation: u32,
    pub validation_rate: f64,
    pub average_confidence: f64,
}
```

> **Engineering question:** The UX design for these dashboards is entirely unspecified. The structs above describe what data each audience needs, but the actual interface design — information hierarchy, interaction patterns, accessibility — is a significant piece of work requiring UX expertise. This is a Phase 1–2 concern.

---

## Holochain Architecture Notes

### Why Holochain, Not Blockchain

Holochain is agent-centric rather than data-centric. Each participant maintains their own source chain of actions; only cryptographic proofs are shared to a Distributed Hash Table (DHT). This solves the three problems that killed blockchain-based reproducibility systems:

**GDPR compliance:** Sensitive data stays local, deletable on request. Only one-way hashes go to the DHT. Article 17 compliance maintained.

**Cost:** No mining, no proof-of-work, no transaction fees. Universities run lightweight nodes. Estimated implementation cost: £50–100K vs. £500K–2M for blockchain equivalents.

**Performance:** No global consensus requirement. Validation happens locally; proofs are shared globally. Scales with participants rather than bottlenecking on consensus.

### Holochain DNA Structure and Update Strategy

ValiChord is implemented as four Holochain DNAs (see Multi-DNA Architecture section above). Within each DNA, Holochain distinguishes two kinds of code modules with critically different update properties:

**Integrity zomes** define data types and validation rules. Any change to an integrity zome changes the DNA's identity — creating a new, separate network. Every participant must migrate to the new DNA to continue participating. These should be kept small and stable, changed as rarely as possible.

**Coordinator zomes** implement application logic and the DNA's public API. They can be swapped out on a running network without forcing migration. Participants do not need to re-join.

For ValiChord, this distinction shapes the phase strategy directly. The core data structures and membrane rules belong in integrity zomes — they define the ground rules and should not change frequently. But governance standards, disciplinary thresholds, anti-domestication rules, and the application logic for agreement detection belong in coordinator zomes where possible, so that governance decisions in Phase 2 and beyond can update the system's behaviour without requiring every researcher and validator to re-install from scratch. Getting this split right during MVP and Phase 1 design is important: moving logic from coordinator to integrity zomes later is disruptive; moving it the other way is straightforward.

Holochain 0.8 (currently in planning) includes "Coordinator Updates: a new feature to allow updates of an application's business logic" as an explicit roadmap item, further strengthening this separation.

### Why Holochain, Not Blockchain

Holochain is agent-centric rather than data-centric. Each participant maintains their own personal record of actions on Holochain; only cryptographic proofs are shared to a distributed network. This solves the three problems that killed blockchain-based reproducibility systems:

**GDPR compliance:** Sensitive data stays local, deletable on request. Only one-way hashes reach the shared network. Article 17 compliance maintained.

**Cost:** No mining, no proof-of-work, no transaction fees. Universities run lightweight nodes. Estimated implementation cost: £50–100K vs. £500K–2M for blockchain equivalents.

**Performance:** No global consensus requirement. Validation happens locally; proofs are shared globally. Scales with participants rather than bottlenecking on consensus.

### Phase 0 Pragmatism

Phase 0 uses PostgreSQL, not Holochain. This isolates the critical test (will validators participate?) from distributed systems complexity. Holochain migration happens in Phase 1, only after participation is proven and performance requirements are specified from actual usage data.

---

## Known Risks and Scope Limitations

The following risks have been identified through adversarial review and are documented here for transparency. Some have mitigations; others are honest boundaries.

### Computation, Not Provenance

ValiChord validates computation — it verifies that provided code, run on provided data, produces the claimed results. It does not validate data provenance. If raw data is fabricated but internally consistent, validators would successfully reproduce the computational results and the study could receive a high confidence rating for science built on false foundations.

This is not a design flaw. It is a boundary. No computational validation system can verify that a researcher actually observed what they claim to have observed in the laboratory, the field, or the clinic. ValiChord catches coding errors, analytical mistakes, undocumented dependencies, statistical misapplication, and post-hoc data manipulation. It does not catch well-executed fraud at the data generation stage.

**Mitigation:** Harmony Records and all ValiChord communications must be explicit about this boundary. A validated study is one whose computation reproduces — not one whose underlying data is guaranteed to be truthful. Complementary systems (data provenance tools, laboratory audit trails, statistical anomaly detection for fabrication patterns) address the data generation stage. ValiChord should integrate with these where possible but must not claim to replace them.

### Career Deference Bias

Even with commit-reveal protocols (which prevent validators from adjusting results after seeing others' findings), a subtler bias exists: a junior validator who knows they are assessing work by a senior figure at a prestigious institution may unconsciously look for reasons to confirm rather than critically assess.

**Mitigation:** Double-blind validation by default. Validators do not see author names, institutional affiliations, or funding sources. They receive the study protocol, code, data, and methodology — nothing that identifies who produced it. Author identity is revealed only in the published Harmony Record, after all validators have submitted final attestations. This does not eliminate all deference bias (a validator might recognise a distinctive methodology or dataset) but it removes the most direct trigger.

### Early-Phase Fragility

In the early months of Phase 1, a single high-profile failure — where a ValiChord "Gold" study is later found to be based on fabricated data — could be reputationally fatal before the system has established credibility.

**Mitigation:** Manual audit of the first 100 studies receiving Gold-level certification. Higher scrutiny thresholds during Phase 1, including additional validators and extended review periods. Explicit public messaging that "validated" means "computation reproduces" and not "data is guaranteed truthful" — set expectations before a failure forces the conversation.

### Gold Badge Misrepresentation

Related to the computation/provenance boundary: a ValiChord Gold badge could be used — deliberately or through misunderstanding — as a general-purpose quality stamp, obscuring the fact that it certifies only computational reproducibility. A university press office writing "ValiChord-verified study shows..." without qualification, or a fraudster pointing to their Gold badge as evidence of data integrity, would misrepresent what ValiChord actually assessed. In the worst case, ValiChord could inadvertently "launder" fabricated data by giving it a stamp of computational success.

However, even when this happens, the validation record has forensic value. Without ValiChord, a retracted paper could have failed at any point — bad data, bad code, bad analysis, undocumented dependencies, post-hoc manipulation. With a Gold badge on a later-retracted study, investigators know the fraud was at data generation, not computation. That narrows the search considerably.

**Mitigation:** The badge format itself must make the boundary visible. Gold means "computation verified by independent validators" — never "study confirmed" or "data verified." Harmony Records should include a standard statement: "This record certifies computational reproducibility. Data provenance was not assessed." Public communications guidelines in the Governance Framework should provide explicit language for press offices, funders, and journals to prevent scope creep in how the badge is described. When misrepresentation occurs — and it will — rapid, public correction is a governance obligation, not an option.

### Functional De-Anonymisation in Niche Fields

Double-blind validation works well in large fields where many labs use similar methods. In niche computational fields — where only three labs worldwide work on a specific climate model, or a particular genomic pipeline has a single originating group — the data, code, or methodology itself is the researcher's signature. A validator working in that field will likely recognise whose work they are assessing regardless of whether names are removed from the submission. Double-blind is functionally impossible when the methods are the identity.

**Mitigation:** Double-blind remains the default because it works in most fields and removes the most direct trigger for deference bias. In niche fields where blinding fails, the other protective layers carry the weight. The blind commitment mechanism still prevents result adjustment — even if a validator recognises the Zurich lab's climate model, they have already sealed their findings as a private source chain entry before the countersigning reveal session begins. That seal is immutable. Validator-to-validator blinding still holds — validators do not know who else is assessing the same study, preventing coordination. Statistical detection mechanisms identify patterns of systematic leniency toward identifiable work across many validations, even when individual cases cannot be blinded. The system degrades gracefully rather than failing completely: full double-blind in large fields, commit-reveal and statistical detection in niche ones. The honest position is that de-anonymisation is a limitation in specialised domains, not that ValiChord has solved it.

### Semantic Gaming of AI Triage (Phase 2+ Risk)

If ValiChord introduces AI-assisted triage or difficulty assessment in later phases, adversarial techniques (paraphrasing documentation to manipulate automated scoring) could game difficulty ratings or confidence assessments.

**Mitigation:** Human-in-the-loop review for all AI-assisted triage decisions during initial deployment. Red-team testing of any AI triage tools before operational use. AI assistance as recommendation, never as final decision.

### DHT Growth at Scale (Phase 3 Risk)

As the network scales globally, the cumulative data burden of Harmony Records, Living Documents, and provenance chains grows. While Holochain's architecture distributes DHT storage across nodes (each node stores a neighbourhood, not the full dataset), sustained global growth requires monitoring to ensure that participation costs don't gradually favour well-resourced institutions — recreating centralisation pressure.

**Mitigation:** Monitor node participation costs as the network grows. Implement data archiving strategies for older records (moving completed, stable Harmony Records to cheaper storage while maintaining integrity verification). Design participation requirements so that lightweight nodes remain viable.

### Geopolitical Fragmentation (Phase 3+ Risk)

Different regions have varying regulatory obligations for data integrity and software validation. Governments could block ValiChord's DHT at the firewall level, creating epistemic silos where science is validated in some regions but inaccessible in others.

**Mitigation:** This is a political problem, not a technical one, and ValiChord cannot solve it unilaterally. The architecture should support federation — regional instances that can interoperate when political conditions permit — rather than assuming a single unified global network. Acknowledged as an open challenge for Phase 3 design.

### Validator Burnout and Dropout

The documents assume that if compensation is calibrated correctly, validators will participate sustainably. This may not hold. Postdocs face grant deadlines. Faculty have teaching commitments. Research software engineers have project cycles. Even well-compensated validation work competes with career-advancing activities (publishing, grant writing, supervising students). Validation may be treated as "service work" — valued in principle, deprioritised in practice — leading to high attrition after a small number of assignments.

**Mitigation:** Phase 0 should explicitly gather data on sustainable participation: not just "how long did this take?" but "would you do this regularly? How often? What would make you stop?" Longitudinal retention modelling should inform Phase 1 design. If sustainable individual participation is low (e.g. 2–3 validations per year per person), the validator pool must be sized accordingly. Longer-term, dedicated professional validator roles (paid full-time or part-time positions, not per-task freelancing) may be necessary for system reliability.

### Proprietary Tooling Dependencies

Many computational fields rely on licensed software (MATLAB, SAS, proprietary sequencing pipelines, commercial cloud configurations). If a study's workflow depends on software a validator cannot legally or practically access, reproduction is impossible regardless of data quality or documentation.

**Mitigation:** Proprietary dependencies must be captured as a specific dimension of the difficulty assessment in Phase 0. Some studies may be classified as unvalidatable specifically because of licensing barriers — that is an honest finding, not a system failure. For Phase 1+, options include: institutional licence-sharing agreements for validation purposes, containerised environments that include licensed software under institutional agreements, or explicit categorisation in Harmony Records noting that validation was conducted under specific tooling constraints. The long-term trajectory favours open-source scientific computing, but ValiChord must deal with the field as it is, not as it should be.

### Reproducibility Theatre

A researcher could invest heavily in making their repository look clean for ValiChord at Home assessment and triage while the actual scientific workflow involved undocumented manual steps, private scripts, one-off tweaks, or unreported decisions. The polished artifact passes triage; the real process remains irreproducible in practice. This is the validation equivalent of teaching to the test.

The Researcher Support auto-generate feature could inadvertently worsen this: if the system drafts a clean README, a researcher might accept it even though it doesn't accurately reflect what they actually did. A clean-looking README that misrepresents the analysis is worse than a messy one that's honest.

**Mitigation:** Validators should be trained to look for signs of over-polished submissions that lack the normal rough edges of genuine research workflows. Phase 0 qualitative data should capture instances where validators suspect undocumented steps. Longer-term, requiring computation environment snapshots (containerised environments capturing the full state at time of analysis) rather than reconstructed repositories would reduce the gap between the submitted artifact and the actual workflow. The Researcher Support document already warns that auto-generated content must be reviewed carefully by the author — but the risk of rubber-stamping remains and should be monitored.

### Adverse Selection in Early Adopters

The first wave of submissions will come disproportionately from reproducibility enthusiasts, open-science advocates, and labs already producing high-quality computational work. Early Harmony Records will therefore look unrealistically positive — high success rates, clean reproductions, few disagreements. This creates a honeymoon effect: inflated expectations of what "normal" validation looks like, followed by disappointment when ordinary messy science enters the pipeline and failure rates increase.

**Mitigation:** Explicit messaging from Phase 1 launch that early results reflect self-selected, high-quality submissions and are not representative of the broader scientific landscape. Phase 0 should deliberately recruit across a difficulty spectrum, including studies the researchers themselves suspect may not reproduce cleanly. Tracking and publishing submission demographics (career stage, institution type, field, self-reported confidence) from day one allows the community to contextualise early results honestly rather than treating them as baselines.

---

## What This Document Does and Doesn't Claim

**It does claim:**
- The architectural approach is sound and confirmed feasible by Holochain Foundation engineers
- The individual technical patterns (content-addressed storage, blind commitment via private source chain entries and countersigned reveal, DHT, collusion detection) are established and proven
- The combination of these patterns for reproducibility validation is novel and well-reasoned
- The data models capture the essential information the system needs to handle

**It does not claim:**
- That this code compiles, runs, or has been tested
- That these specific struct definitions are final
- That implementation timelines are reliable (they are rough estimates)
- That all engineering problems are solved (several are flagged above)
- That the system can be built by one person (it requires a team)
- That ValiChord validates data provenance — it validates computation (see Known Risks and Scope Limitations)

---

**Companion Documents:**
- *ValiChord Vision & Architecture* — What ValiChord is and why it matters
- *ValiChord Governance Framework* — How the system resists corruption
- *ValiChord Phase 0 Proposal* — Workload Discovery Pilot (£69K, 6 months)
- *ValiChord Researcher Support* — Feedback pipeline and pre-validation tools

**Contact:** Ceri John — topeuph@gmail.com

**© 2026 Ceri John. All Rights Reserved.**
