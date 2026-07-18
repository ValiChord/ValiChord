# Sharding: impact on ValiChord & migration plan

> **STATUS — FORWARD-LOOKING / CONDITIONAL. NOT A CURRENT CAPABILITY.**
> This is an internal design note, not a description of what ValiChord does today. It
> depends on *safe* dynamic storage-arc sizing landing in Holochain/kitsune2 — the
> redundancy target-arc controller tracked in **kitsune2 #160**, which is open and unbuilt
> as of this writing. Nothing here is committed or scheduled. Do not cite it as a roadmap
> promise. Revisit when safe shrink is demonstrable (see *Trigger*).

## Background: what "sharding" means here (one paragraph)

Today every Holochain node holds a copy of the **whole** DHT for a hApp ("full-arc"). That
caps a network's shared data at what the smallest node can store. *Sharding* lets each node
hold a **slice** of the keyspace (a "storage arc"), sized to its capacity, while the network
maintains a guaranteed **redundancy R** for every piece of data. Total capacity becomes
`∑(arcs)/R` instead of "what one node holds." The hard part — and the reason it isn't on by
default — is shrinking an arc **without ever dropping any part of the keyspace below R
replicas**. That safe-shrink controller is the open piece (#160); see the `polite-shrink`
research repo for the controller + proof harness.

## Thesis: what changes for ValiChord

Today ValiChord commits **hashes** to the public DHT and stores the large artifacts —
eval logs, datasets, CodeOcean-style capsules, model outputs — **off-DHT**, because a
full-arc DHT can't hold them. Safe sharding changes one thing with large consequences:

> **The evidence itself can live on the validating DHT, sharded, with provable redundancy R
> — instead of being anchored by hash and stored elsewhere.**

ValiChord goes from "anchor a fingerprint of the evidence" to "the reproducibility corpus
lives in the commons," where each shard is validated by the nodes holding it and no single
node (or host) is load-bearing.

## What changes — and what deliberately does not

**Affected (public DHT DNAs):**
- **`attestation`** and **`governance`** are public DHTs. These are where sharding applies:
  the shared corpus (requests, commitments, phase markers, HarmonyRecords, badges — and
  *potentially the evidence artifacts themselves*) could scale beyond any one node with a
  guaranteed R.

**Unchanged — and this must stay true:**
- **`researcher_repository`** and **`validator_workspace`** are **private, single-agent**
  DNAs. They do not enter the DHT and are not sharded. The GDPR boundary (private research
  data never leaves the researcher's cell) is **not** touched by any of this.
- The commit-reveal protocol, blinding, and HarmonyRecord semantics are unaffected —
  sharding is a storage/durability property, not a protocol change.

## Migration sketch (when the capability exists)

1. **Nothing moves first.** ValiChord keeps working full-arc; sharding is opt-in per network.
2. **Evidence artifacts on-DHT** — decide which currently-off-DHT artifacts (eval logs,
   datasets, capsules) become DHT entries, with a redundancy target R appropriate to the
   evidence class (routine benchmark vs. regulatory submission — R is a parameter, like the
   validator count).
3. **Arc-sizing policy for the corpus** — small/mobile/browser validators run small (or zero)
   arcs and still participate; storage-capable nodes carry larger arcs. R is the invariant.
4. **Keep the hash anchor** — content-hash anchoring stays as the integrity check even when the
   bytes are on-DHT; the two are complementary, not either/or.

## Open questions (unresolved — do not pre-decide)

- **Open resolvability vs. membrane.** A public evidence commons wants broad readability; the
  attestation DNA is credential-gated. How much of the corpus is open-join vs. permissioned?
- **Redundancy target per evidence class.** What R for what kind of claim? (Empirical, like
  statistical power analysis — see the CORE-Bench integration notes.)
- **Large-object handling** — chunking/streaming big artifacts as DHT entries vs. a
  content-addressed side-channel with DHT-anchored provenance.
- **Validation cost** — integrity-zome validation of large evidence at every holding node.

## Trigger

Revisit this note when **safe arc-shrink is demonstrably working** — whether shipped upstream
in Holochain/kitsune2 or robustly demonstrated by the `polite-shrink` harness on real
transport. Until then it is design thinking, not a plan of record.

## References

- `polite-shrink` repo — the safe-shrink controller, TLA+ safety proof, adversary + Wind-Tunnel
  harness; `PROVENANCE.md` there tracks upstream #160 state.
- kitsune2 #160 — the open redundancy target-arc controller issue.
- `docs/7_ValiChord_4-DNA_architecture_technical.md` — the DNA/membrane boundaries referenced above.
- `docs/CORE_BENCH_FOR_INSPECT_EVALS.md` — "validator count / R is a parameter" reasoning.
