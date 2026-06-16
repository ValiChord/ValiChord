# ValiChord × Nondominium — Reviewer Sourcing (Scoping Note)

**Status:** Scoping / pre-design. Written 2026-06-16 ahead of Tiberius's integration build.
**Scope:** The first of the two open design questions from the 2026-06-14/15 Discord agreement
(ValiChord as a capability slot the Nondominium Governance zome calls to gate a
`Prototype → Stable/Distributed` lifecycle transition for medical-device resources).
The companion question — *what specifically gets committed and reproduced at the gate*
(mapping designer/reviewer roles onto commit-reveal) — is a separate note.

---

## The question, framed precisely

"Where do the independent reviewers come from, and how is independence guaranteed?"
splits into two halves that land on opposite sides of the system boundary:

- **Sourcing / admission** — *who is allowed into the reviewer pool, and who decides.*
  This is the subject of this note. It is a governance/onboarding choice, and in the
  integration it is naturally **Nondominium's** to own ("Nondominium owns *who validates*").
- **Independence guarantee** — *that whoever validates did so blind and could not copy.*
  This is **ValiChord's** structural job (commit-reveal: seal before seeing, simultaneous
  reveal, tamper-evident `HarmonyRecord`) and is **out of scope here** — it holds regardless
  of how the pool is sourced.

**Important:** admission does *not* establish independence. A perfectly credentialed pool can
still collude out-of-band, and one actor can still run two device keys (Sybil). Those residual
risks are mitigated by *pool diversity* (sourcing) and by cross-system person identity
(`person_key` / Flowsta `IsSamePerson` — currently `None` everywhere), **not** by either option
below. Neither option should be sold as solving them.

---

## Option A — ValiChord-native credential membrane (issuer-signed certificates)

ValiChord's attestation DNA already has this built. Admission is enforced **at network join**,
structurally, by a membrane proof:

- DNA property `authorized_joining_certificate_issuer` (base58 `AgentPubKey`) names a
  credentialing authority, baked into the DNA hash.
- Two-stage check: `genesis_self_check` (format only — rejects proofs < 64 bytes, runs before
  join) then coordinator `init()` (full Ed25519 verify — the issuer's signature must be over the
  joining agent's pubkey).
- An empty issuer string is the dev/test bypass (what the demo and `valichord-ui` use today).
- Reference onboarding service: Holo-Host / Unyt `joining-service` (REST membrane-proof issuer +
  `joining-cli`).

**Character:** a validator literally cannot enter the attestation network without a certificate
from the issuer. Strong, structural, credential-authority-rooted.

## Option B — In-DHT moderated membership (administration/Status pattern)

The pattern used by `happenings-community/requests-and-offers` (same HC 0.6 / hREA orbit as
Nondominium). There is **no membrane proof**; anyone can
join the DHT, and participation is gated **in application logic** by a moderation status entry:

- An `administration` zome holds a `Status` per agent: `Pending → Accepted / Rejected /
  Archived / SuspendedIndefinitely / SuspendedTemporarily` (stored as a string for upgrade
  stability; `reason` required for suspensions; `suspended_until` for temporary ones).
- New agents start `Pending`; an admin role `Accepts`. Coordinator logic checks status before
  letting an agent take a protocol action.

**Character:** admission is in-DHT, visible, reversible (flip to `Suspended` with a reason), and
the admin set can be plural (capture-resistant). This is also **how Nondominium itself already
works** — no DNA properties (`properties: ~`), in-DHT role hierarchy
(`RoleType`: SimpleAgent / AccountableAgent / PrimaryAccountableAgent / …) plus an administration
layer. So Option B is the more *native* fit for the integration substrate.

---

## Comparison

| Dimension | A — Credential membrane | B — In-DHT moderation |
|---|---|---|
| Enforcement point | Network join (structural — can't get in) | Application logic (after join) |
| Trust root | The issuer key (single, unless delegated) | The admin role(s) (can be plural) |
| Revocation | Hard — needs warrant/conductor block | Easy — flip `Status` to Suspended, with reason |
| Visibility of decisions | Off-DHT (issuer's process) | On-DHT, auditable, reason-bearing |
| Capture resistance | Weaker (single issuer = single gate) | Stronger (distributed admins, transparent) |
| Onboarding UX | Async cert issuance (joining-service) | Self-register, then await acceptance |
| DNA-hash coupling | Issuer baked into DNA properties (change = new network) | None — admins are in-DHT data |
| Native to Nondominium? | No — adds ValiChord-side config | Yes — mirrors its existing model |
| Already built in ValiChord? | **Yes** (membrane proof + issuer property) | No — would be new application logic |

Neither changes badge tiers or `minimum_validators`, and **neither is a statistical claim** —
the 3/5/7 counts remain illustrative placeholders; the right N per domain is a separate,
unresolved question.

---

## The cross-cutting decision: who *operates* the gate?

Independent of mechanism, admission can be owned in three ways. This is the decision that
actually matters for the integration, given the agreed split:

1. **ValiChord owns it** — ValiChord runs Option A with a real issuer; Nondominium just consumes
   the resulting `HarmonyRecord`. Cleanest cryptographically, but puts a ValiChord-side authority
   in the trust path and is *not* how Nondominium gates anything else.
2. **Nondominium owns it (delegation)** — ValiChord runs an **open** membrane (empty issuer), and
   Nondominium's governance/role system is the sole gate on who is invited to a validation round.
   This matches "Nondominium owns *who validates*" exactly, keeps ValiChord a pure verifier, and
   reuses Nondominium's existing administration/role machinery (Option B, on their side).
3. **Hybrid** — ValiChord's issuer is set to a *Nondominium* authority key, so Nondominium's
   admission decision is what mints the membrane certificate. Structural enforcement (A) driven by
   Nondominium's governance (B). Most robust, most plumbing.

---

## Recommendation (for discussion with Tiberius)

**Lead with framing #2 (delegation), implemented as Option B on the Nondominium side.** Rationale:
- It honours the agreed boundary — Nondominium owns admission, ValiChord owns independence.
- It's native to how Nondominium already works (in-DHT roles + administration, no DNA properties).
- It keeps ValiChord a clean, reusable verifier rather than embedding a domain-specific authority.
- Option A stays available as a hardening step (framing #3) if/when a medical-device deployment
  needs structural, certificate-backed admission — but that's a later, regulatory-grade concern,
  not the MVP gate.

This preserves the "leaderless convergence" property at the *verdict* layer (commit-reveal has no
privileged first mover) while being honest that *admission* always has an operator — and locating
that operator in Nondominium's existing governance rather than inventing a new ValiChord authority.

---

## Open questions to put to Tiberius

1. Does Nondominium want admission to a validation round to flow from its existing role hierarchy
   (`AccountableAgent`+) and/or administration `Status`, or a new reviewer-specific credential?
2. How is *conflict-of-interest* expressed? ValiChord's `StudyClaim` `validate()` already rejects a
   validator from the same institution as the researcher (institution is a `String`) — does that map
   onto a Nondominium organization/affiliation field?
3. For the medical-device case, is structural enforcement (Option A / hybrid) a requirement for any
   regulator, or is transparent in-DHT moderation (Option B) sufficient at this stage?
4. Cross-system reviewer identity: do we need Flowsta `IsSamePerson` in place to dedupe a reviewer
   across ValiChord and Nondominium keys before this gate is trustworthy, or is that deferred?

---

*Companion note (to follow): "What gets committed and reproduced at the gate" — mapping the
reference-fingerprint claim and Nondominium designer/reviewer roles onto the commit-reveal
data model (`data_hash`, `metrics`, `ResearcherResultCommitment` → `ValidationAttestation`).*
