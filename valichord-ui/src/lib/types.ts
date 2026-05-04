// TypeScript mirrors of ValiChord Rust types.
// Serde encoding rules (critical — don't deviate):
//   Adjacent-tagged enums (#[serde(tag="type", content="content")]):
//     Discipline, AttestationOutcome, DeviationType
//     Unit variants → { type: "VariantName" }
//     Struct/tuple variants → { type: "VariantName", content: { ...fields } }
//   Plain-string enums (no serde tag):
//     ValidatorAgentType, CertificationTier, ValidationTier,
//     AttestationConfidence, AgreementLevel, ValidationPhase,
//     EpistemicImpact, Severity, DifficultyTier, AssessmentConfidence,
//     DepositAccessType, ValidationPhase, ValidatorType

import type { AgentPubKey, ActionHash } from "@holochain/client";
import { decode as msgpackDecode } from "@msgpack/msgpack";

export type ExternalHash = Uint8Array; // 39-byte HoloHash (External type)

// ── Discipline ──────────────────────────────────────────────────────────────

export type Discipline =
  | { type: "ComputationalBiology" }
  | { type: "ClimateScience" }
  | { type: "SocialScience" }
  | { type: "Economics" }
  | { type: "Psychology" }
  | { type: "Neuroscience" }
  | { type: "MachineLearning" }
  | { type: "Other"; content: string };

export const DISCIPLINE_LABELS: Record<string, string> = {
  ComputationalBiology: "Computational Biology",
  ClimateScience: "Climate Science",
  SocialScience: "Social Science",
  Economics: "Economics",
  Psychology: "Psychology",
  Neuroscience: "Neuroscience",
  MachineLearning: "Machine Learning",
  Other: "Other",
};

export function disciplineLabel(d: Discipline): string {
  if (d.type === "Other") return `Other: ${d.content}`;
  return DISCIPLINE_LABELS[d.type] ?? d.type;
}

// ── AttestationOutcome ───────────────────────────────────────────────────────

export type AttestationOutcome =
  | { type: "Reproduced" }
  | { type: "PartiallyReproduced"; content: { details: string } }
  | { type: "FailedToReproduce"; content: { details: string } }
  | { type: "UnableToAssess"; content: { reason: string } };

// ── AgreementLevel ───────────────────────────────────────────────────────────

export type AgreementLevel =
  | "ExactMatch"
  | "WithinTolerance"
  | "DirectionalMatch"
  | "Divergent"
  | "UnableToAssess";

// ── ValidationTier ───────────────────────────────────────────────────────────

export type ValidationTier = "Basic" | "Enhanced" | "Comprehensive";

// ── CertificationTier ────────────────────────────────────────────────────────

export type CertificationTier = "Provisional" | "Standard" | "Advanced" | "Certified";

// ── ValidatorAgentType ───────────────────────────────────────────────────────

export type ValidatorAgentType = "Individual" | "Institution" | "AutomatedTool";

// ── AttestationConfidence ────────────────────────────────────────────────────

export type AttestationConfidence = "High" | "Medium" | "Low";

// ── EpistemicImpact / Severity ────────────────────────────────────────────────

export type EpistemicImpact = "Minimal" | "Moderate" | "Substantial";
export type Severity = "Minor" | "Moderate" | "Major" | "Critical";

// ── DeviationType ────────────────────────────────────────────────────────────

export type DeviationType =
  | { type: "DataAccess"; content: { reason: string; impact: EpistemicImpact } }
  | { type: "EthicalConcern"; content: { review_board: string } }
  | {
      type: "ModelFailure";
      content: {
        attempted_model: string;
        fallback_model: string;
        justification: string;
      };
    }
  | {
      type: "ComputationalLimit";
      content: {
        planned_method: string;
        actual_method: string;
        reason: string;
      };
    }
  | {
      type: "SampleSizeAdjustment";
      content: { original_n: number; revised_n: number; power_analysis: string };
    };

export interface UndeclaredDeviation {
  deviation_type: DeviationType;
  severity: Severity;
  evidence: string;
}

// ── TimeBreakdown ─────────────────────────────────────────────────────────────

export interface TimeBreakdown {
  environment_setup_secs: number;
  data_acquisition_secs: number;
  code_execution_secs: number;
  troubleshooting_secs: number;
}

// ── ComputationalResources ────────────────────────────────────────────────────

export interface ComputationalResources {
  personal_hardware_sufficient: boolean;
  hpc_required: boolean;
  gpu_required: boolean;
  cloud_compute_required: boolean;
  estimated_compute_cost_pence: number | null;
}

// ── MetricResult / OutcomeSummary ─────────────────────────────────────────────

export interface MetricResult {
  metric_name: string;
  produced_value: string;
  expected_value: string;
  within_tolerance: boolean;
}

export interface OutcomeSummary {
  key_metrics: MetricResult[];
  effect_direction_matches: boolean | null;
  confidence_interval_overlap: number | null;
  overall_agreement: AgreementLevel;
}

// ── DepositAccessType ─────────────────────────────────────────────────────────

export type DepositAccessType = "PublicUrl" | "TokenGated";

// ── ValidationRequest ─────────────────────────────────────────────────────────

export interface ValidationRequest {
  protocol_ref: ExternalHash | null;
  data_hash: ExternalHash;
  data_access_url: string;
  deposit_access_type: DepositAccessType;
  deposit_token: string | null;
  protocol_access_url: string | null;
  num_validators_required: number;
  validation_tier: ValidationTier;
  discipline: Discipline;
  researcher_institution: string;
}

// ── ValidationAttestation ─────────────────────────────────────────────────────

export interface ValidationAttestation {
  request_ref: ExternalHash;
  outcome: AttestationOutcome;
  outcome_summary: OutcomeSummary;
  time_invested_secs: number;
  time_breakdown: TimeBreakdown;
  confidence: AttestationConfidence;
  deviation_flags: UndeclaredDeviation[];
  computational_resources: ComputationalResources;
  discipline: Discipline;
  commitment_anchor_hash: ActionHash | null;
}

// ── ValidatorProfile ──────────────────────────────────────────────────────────

export interface ValidatorProfile {
  institution: string;
  disciplines: Discipline[];
  certification_tier: CertificationTier;
  available: boolean;
  max_concurrent_tasks: number;
  orcid: string | null;
  agent_type: ValidatorAgentType | null;
  person_key: AgentPubKey | null;
}

// ── HarmonyRecord ─────────────────────────────────────────────────────────────

export interface HarmonyRecord {
  request_ref: ExternalHash;
  outcome: AttestationOutcome;
  agreement_level: AgreementLevel;
  participating_validators: AgentPubKey[];
  validator_types: (ValidatorAgentType | null)[];
  validation_duration_secs: number;
  discipline: Discipline;
}

// ── BadgeType ─────────────────────────────────────────────────────────────────

export type BadgeType = "Gold" | "Silver" | "Bronze" | "Failed";

// ── Researcher repository types ───────────────────────────────────────────────

export interface LockedResult {
  request_ref: ExternalHash;
  metrics: MetricResult[];
  nonce: number[];
  commitment_hash: number[];
}

export interface LockResultInput {
  request_ref: ExternalHash;
  metrics: MetricResult[];
}

export interface ResearcherRevealInput {
  request_ref: ExternalHash;
  metrics: MetricResult[];
  nonce: number[];
}

// ── ValidationFocus / CompensationTier (validator_workspace DNA) ──────────────

export type ValidationFocus =
  | "ComputationalReproducibility"
  | "PreCommitmentAdherence"
  | "MethodologicalReview";

// External-tag serde (default, no #[serde(tag)]) — struct variants use object notation
export type CompensationTier =
  | { Tier1: { amount_pence: number } }
  | { Tier2: { amount_pence: number } }
  | { Tier3: { amount_pence: number } };

export interface ValidationTask {
  request_ref: ExternalHash;
  discipline: Discipline;
  deadline_secs: number;
  validation_focus: ValidationFocus;
  time_cap_secs: number;
  compensation_tier: CompensationTier;
}

export interface SealAttestationInput {
  task_hash: ActionHash;
  attestation: ValidationAttestation;
}

export interface AttestationRevealInput {
  attestation: ValidationAttestation;
  nonce: number[]; // Vec<u8> → number[] over msgpack
}

export interface ValidatorPrivateAttestation {
  request_ref: ExternalHash;
  outcome: AttestationOutcome;
  outcome_summary: OutcomeSummary;
  time_invested_secs: number;
  time_breakdown: TimeBreakdown;
  deviation_flags: UndeclaredDeviation[];
  computational_resources: ComputationalResources;
  confidence: AttestationConfidence;
  discipline: Discipline;
  nonce: number[];
  commitment_hash: number[];
}

// ── App signals ───────────────────────────────────────────────────────────────
// Signal enum in attestation_coordinator uses #[serde(tag = "type", content = "content")]
// (adjacent-tag). The msgpack payload delivered by @holochain/client is:
//   { type: "RevealOpen",          content: { request_ref: Uint8Array } }
//   { type: "FinalizationFailed",  content: { request_ref: Uint8Array } }

export interface RevealOpenSignal {
  type: "RevealOpen";
  content: { request_ref: ExternalHash };
}

export interface FinalizationFailedSignal {
  type: "FinalizationFailed";
  content: { request_ref: ExternalHash };
}

export type AppHcSignal = RevealOpenSignal | FinalizationFailedSignal;

// ── Holochain Record wrapper ──────────────────────────────────────────────────

export interface HolochainRecord<T> {
  signed_action: {
    hashed: {
      hash: ActionHash;
      content: { author: AgentPubKey; timestamp: number };
    };
  };
  entry: { Present: { entry: T } } | { NotApplicable: null } | { Hidden: null };
}

export function entryFromRecord<T>(record: HolochainRecord<T>): T | null {
  if (!("Present" in record.entry)) return null;
  const raw = record.entry.Present.entry;
  // @holochain/client 0.20.x returns the inner entry as raw msgpack bytes
  // (Uint8Array / Buffer). Decode them to get the actual entry struct.
  if (raw instanceof Uint8Array || (raw && typeof (raw as unknown as { data: unknown }).data === "object")) {
    const bytes = raw instanceof Uint8Array ? raw : new Uint8Array((raw as unknown as { data: number[] }).data);
    return msgpackDecode(bytes) as T;
  }
  return raw;
}

export function hashFromRecord<T>(record: HolochainRecord<T>): ActionHash {
  return record.signed_action.hashed.hash;
}

export function authorFromRecord<T>(record: HolochainRecord<T>): AgentPubKey {
  return record.signed_action.hashed.content.author;
}
