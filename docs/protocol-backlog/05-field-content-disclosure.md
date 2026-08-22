# Backlog: three public fields where what someone *types* can expose a research subject

**Status:** Open. **Category: 🟢 to fix, 🔴 in consequence** — the fix is guidance and coordinator-side
checks, neither of which needs a DNA change. But anything already published cannot be withdrawn.
**Needs the rebuild window: no.**
**Found:** 2026-08-22, checking Ceri's question about people named in medical research.
**Related:** 04, which establishes that the *architecture* keeps subject data off the network. This
item is about the gap that architecture cannot close.

## Why this is a different class of problem

Item 04 concluded that research-subject data never reaches the shared network, and that holds:
the data lives in a private single-agent DNA and the institution controls it.

**But three public fields accept free text or a URL, and nothing checks what goes in them.** The
architecture prevents subject data being *transferred*. It cannot prevent someone *typing it in*.

That distinction matters because it changes who fixes it. Membrane separation is a guarantee.
Field content is a discipline, and disciplines need guidance, defaults and warnings — not walls.

⚠️ **This is the question a hospital ethics committee asks first**, and there is currently no
guidance of any kind to answer it with.

## The three surfaces

### 1. `data_access_url` — permanent, public, unstructured

`ValidationRequest.data_access_url: String`, on the public attestation DNA.

A URL constructed carelessly leaks: a patient identifier in the path, a cohort name that identifies
a rare-disease group, an internal hostname that names a ward or a trial arm. And it is **permanent
even after the data behind it is deleted** — a public pointer to a resource that no longer exists,
still describing what it pointed at.

**This is the most likely way to get it wrong in practice**, because it is the field where a
sensible person pastes whatever their system gave them.

### 2. Revealed metrics — free-text values with a small-cell problem

`ResearcherReveal.metrics: Vec<MetricResult>`, where each carries `metric_name`,
`produced_value` and `expected_value` — **all `String`**, all published permanently.

Two risks:

- **Free text.** Nothing constrains these to numbers. A researcher pasting a per-group breakdown,
  or a note explaining an anomaly, publishes it permanently.
- **Small-cell disclosure.** Even honest aggregate values identify people when the group is small.
  This is why health and census bodies suppress small cells as routine practice. In a three-patient
  study, an aggregate can be a record. **Nothing in ValiChord checks group sizes, and it has no way
  to know them.**

### 3. Institution + discipline + timing

`researcher_institution`, `discipline`, and validation timestamps together narrow a cohort. Weak
alone; real in combination with either of the above.

## What would actually help

None of it needs an integrity-zome change, which is why this is 🟢 to fix.

- **Guidance, written down.** A short "what not to put in a ValidationRequest" for researchers, and
  a line in the submission UI at the point of typing rather than in a document nobody opens.
- **Coordinator-side checks.** Coordinator changes carry **no DNA-hash change** (`CLAUDE.md`,
  "Coordinator-only upgrade"), so cheap heuristics are available: reject or warn on URLs containing
  query strings that look like identifiers, on metric values that are not parseable as numbers, on
  values above a length threshold. ⚠️ **Heuristics catch carelessness, never intent** — say so
  plainly wherever they are added, or they will be mistaken for a guarantee.
- **A structured metric type.** If `produced_value` were numeric rather than `String`, surface 2
  mostly closes. That *is* an integrity change (🟠) and would want to ride the same break as 01/02
  — but it is a real option and should be considered while the window is open rather than after.
- **A declared subject count.** If a submission stated its N, small-cell risk could at least be
  flagged. Also 🟠, also worth considering in the window. ⚠️ And it would itself be **asserted, not
  observed** (`spec/conformance.md` §3.17–18) — the protocol cannot check it.

## The 🔴 part

**Anything already published stays published.** If a live deposit has a leaky URL or a free-text
metric value, no later fix reaches it. Worth one pass over what Oracle currently holds before the
rebuild — and noting that the rebuild itself clears state, which for once helps.

## Not decided

Everything. Filed so that the first ethics committee to ask is not the thing that discovers it.
