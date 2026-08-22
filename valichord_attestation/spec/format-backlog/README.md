# attestation format — open backlog

Candidate additions to the bundle, each raised by someone building against the format from
outside this project. Every item carries who raised it and when, so a claim here can be traced
rather than inherited.

## Why this directory is not called `v3-backlog`

`spec/v2-backlog/` closed on 2026-08-18 when its four items shipped. Nine days later there was
nowhere to record the items below, which is the same failure the v2 backlog existed to fix: a
roadmap that only one person can find. A version-named directory closes; this one does not.

It is also the more accurate name. §7 of `attestation_format_v1.md` — still the versioning policy
for v2 — says **additive changes (new optional fields) MAY be made within a version family**.
Absent optional fields are omitted from the canonical encoding rather than serialised as `null`,
so adding one leaves every existing bundle hashing exactly as before. **Most items here are
therefore v2.x additive, not v3.** Only a change to an existing field's meaning, or to the
canonical encoding or Merkle construction, forces a version bump.

## The items

| | Item | Raised by | Additive? |
|---|---|---|---|
| 01 | Requested vs observed model identity | KeilerHirsch | yes — **field shape proposed, 2026-08-20** |
| 02 | Judge-model configuration | three, independently | yes |
| 03 | Prompt, evaluator and rubric versions | three, independently | yes |
| 04 | Thresholds and aggregation | three, independently | yes |
| 05 | Repeatability vs reproducibility conditions | KeilerHirsch | yes |
| 06 | Uncertainty beyond `stderr` | KeilerHirsch | yes |
| 07 | Comparison validity | KeilerHirsch | probably |

**02, 03 and 04 were named independently by three people in one week**, none of whom had seen
the others' comments: two working on eval platforms and one on a metrology benchmark. That
convergence is the evidence these are real gaps rather than one reviewer's preference — the same
structure of evidence that surfaced the v1 Merkle defects, where two implementations disagreeing
found what neither could find alone.

## The trap that applies to 02–05

There is an obvious-looking home for all of this: `Bundle.meta`, the free-form provenance dict.
**It is the wrong home, and quietly so.**

`meta` is included in `bundle_hash` but *excluded* from `content_hash`. That exclusion exists so
two reruns differing only in provenance — who triggered them, on what machine, at what time —
still compare as scientifically equivalent. Put the judge model in `meta` and two runs scored by
*different judges* also compare as equivalent, because `content_hash` cannot see the difference.

Anything that could change the result belongs in a field `content_hash` covers. `meta` is for
things that cannot. That line is the actual design question behind items 02–05, and it is worth
settling once rather than per-field.

## The principle behind 01, which generalises

KeilerHirsch's constraint on "observed" — *evidence actually exposed by the serving system, not
what the client assumes it received* — is not specific to model identity. It is the same rule as
the ValiChord gate correction (do not decide from the summary the interested party wrote) and as
Nondominium's ADR-012 (re-derive the address rather than trust the anchor naming it). Three
projects, four arrivals, same principle.

Any field added here should say which side of that line it sits on: asserted by the party with an
interest, or observed from something they do not control. Where the format cannot tell, it should
say so explicitly rather than let absence read as agreement.

## Also raised, not yet numbered

- **Dataset snapshot and row identity** (Seekers2001, `future-agi#1368`, 2026-08-16) — which
  rows a run covered, so two runs over "the same" dataset are comparable. Overlaps 01 in spirit;
  may deserve its own item.
- **Leaf-source identity** (Hawthorn, `future-agi#1368`, 2026-08-17) — where per-sample results
  live when they are not in the same store as the aggregate. If the leaf source cannot be
  rebuilt at verification time, the Merkle root stops being checkable and nobody notices for a
  year. Arguably an implementation-guidance item rather than a format one.

  🆕 **Outside convergence, and a proposed answer worth reading before we design ours.**
  The Kantara ANCR working group (`github.com/KantaraInitiative/ancr-wg`, read 2026-08-22) hit the
  same problem in a completely unrelated domain — legally significant privacy notices rather than
  eval runs. Their answer has two parts: the record carries a `notice_event_log_url` naming where
  the supporting log is published, and a companion IETF Internet-Draft, *"Well-Known Location for
  Transparency Records"*, standardises the location so a verifier does not need to be told it
  per-record. Two projects, no contact, same gap: **a commitment whose supporting evidence has no
  stated address stops being checkable, and nothing signals when that happens.**

  That is design input, **not a decision, and not a proposal to adopt their field.** Two things to
  weigh if this is taken up: a URL is *asserted by the party with an interest* (§3.17 of
  `conformance.md`) and points at something they control, so it locates evidence without
  authenticating it; and ANCR's own log requirement is procedural — their spec never says how a
  third party checks the log has not been rewritten, which is the half we would be bringing.
  ⚠️ Their materials are under the Kantara IPR policy, not an open-content licence: read for
  ideas, do not copy text or adopt their field names wholesale.

## Standing offer

KeilerHirsch (BRONCO) has offered to specify the measurement layer and to treat this format as a
compatibility target rather than fork it. If that work lands here as optional fields, the
projects are compatible by construction rather than by negotiation. That is the preferred route
for 01–07 and the reason none of them is being designed unilaterally yet.
