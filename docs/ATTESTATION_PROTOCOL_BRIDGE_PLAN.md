# Attestation → protocol bridge — build plan and decision record

**Branch:** `integration/attestation-protocol-bridge`
**Governed by:** `docs/PROTOCOL_INTEGRATION_BOUNDARY.md`. Every decision below cites the
precondition it satisfies.
**Status:** step 1 of 4 landed. **No Rust, no DNA, no entry types touched, and nothing deployed.**

## Why this is being built the way it is

The bridge is the **first test of the integration boundary**, not primarily a feature for
`valichord_attestation`. If the four preconditions cannot accommodate our own on-ramp — same
author, same repo, no adversarial relationship — they will not accommodate a stranger's system.
So the constraint is the deliverable, and the bridge is the thing being measured.

⚠️ The corollary, restated from the boundary doc because it is easy to forget while enjoying
progress: this is a **flattering** test case, and passing it proves less than it appears to.

## Precondition compliance for step 1

| | Precondition | How step 1 satisfies it |
|---|---|---|
| §3.1 | No new entry types, link types, or integrity-zome changes | **Zero Rust changed.** Uses `ValidationRequest.data_hash` and `ValidationAttestation.reproduction_bundle_hash`, both of which already exist |
| §3.2 | No payload parsed inside an integrity zome | The protocol receives fixed-size digests only. Nothing added to any `validate()` |
| §3.3 | No payload content on a public DHT | `submission_bytes` are handed only to `researcher_repository`, the private single-agent DNA whose own docstring says the data never leaves it |
| §3.4 | Every crossing value declared asserted or observed | Below, and in each function's docstring |

## What crosses the boundary, and on which side of the line

Per `spec/conformance.md` §3.17–3.18.

| Value | Size | Asserted / observed | Enforced by |
|---|---|---|---|
| `data_hash` | 39 bytes (`ExternalHash`) | **Asserted** by the researcher — it is a digest of a document they authored | Nothing, and that is correct. It is an *identifier for a claim*, never evidence the claim is true |
| `reproduction_bundle_hash` | 32 bytes | **Asserted** by the validator, about their own reproduction | Bound into the sealed commitment, so it cannot be changed after seeing others' answers — the protocol's commit-reveal, not the format |
| The verdict | enum | Asserted by the validator | Commit-reveal, plus federation across independent validators |

**Nothing crossing this boundary is observed.** The protocol's guarantee is not that any of these
values is true — it is that **none of them could be changed after their author saw someone else's**.
That is the guarantee, that is the layer providing it, and it is written down here so a later
reader cannot come to believe the format supplies something it does not.

## Step 1 — landed

`valichord_attestation/protocol.py` + `tests/test_protocol.py`.

- HoloHash primitives: `holo_dht_location_bytes`, `external_hash_from_core`,
  `encode_holo_hash` / `decode_holo_hash`.
- Bridge functions: `submission_bytes`, `data_hash`, `data_hash_b64`,
  `reproduction_bundle_hash`.
- `canonical.content_preimage` extracted so `content_hash` and `submission_bytes` share one
  definition of the preimage rather than inlining it twice.

### Decision: `data_hash` derives from `content_hash`, not `bundle_hash`

`data_hash` identifies a **claim**. The same claim submitted from two machines differs in
`generated_at` and in whatever the harness wrote into `meta`; under `bundle_hash` those would be
two unrelated claims. `content_hash` was defined for exactly this question — *"is this the same
science?"*

⚠️ **This promotes the `meta` trap from a library nicety to an on-chain property.** `meta` is
excluded from `content_hash`, so anything placed there that could change a result is invisible to
`data_hash`, and two materially different claims collide as one identifier — **permanently, on an
immutable record**. Backlog items 02–05 (judge configuration, rubric versions, thresholds,
repeatability conditions) stop being tidy-ups the moment this ships. Recorded so the cost is
chosen rather than discovered.

### Verified, and how

The `ExternalHash` construction is **observed**, not asserted. The algorithm was read from
`holo_hash`'s `encode.rs` upstream, and then checked against
`uhC8k4j2xO83gyCFCBMTAtx2Nyy_i_Yr4oDk-X1XJlbOZsI0-bYNT` — a real hash produced by a running
ValiChord conductor and recorded in `demo/bundles_worked_example/`. Its location bytes were not
computed by this library and cannot have been influenced by it.

⚠️ **A negative control ships with it.** A secondary summary of the algorithm described it as
XOR-folding the eight 4-byte groups of the 32-byte core with no BLAKE2b step. That is wrong, and
it produces `e14a8dbd` where the real hash carries `3e6d8353`. Every `data_hash` built that way
would have been rejected by a conductor. `test_the_plausible_wrong_algorithm_does_not_pass` exists
so it cannot be reintroduced quietly.

## Steps 2–4 — not started

2. **Round-trip against a live `compute_data_hash`.** The remaining verification gap: the hash has
   been checked against a conductor-produced value, but not against the zome function that will
   actually produce it. Needs a conductor.
3. **A worked example** carrying a bundle from `build_bundle` through to a submitted
   `ValidationRequest`, so the path is demonstrated rather than described.
4. **The reverse direction** — given a published HarmonyRecord, recover which bundle it concerns
   and check it. This is the half that makes the bridge worth having to anyone who is not us.

## What would make this stop

Recorded in advance, because a precondition is only real if it can halt work already under way.

- Any step requiring a **new entry type or integrity-zome change** (§3.1).
- Any step requiring the protocol to **parse a bundle** (§3.2).
- Any step putting **bundle content, rather than a digest, on DNA 1 or DNA 4** (§3.3).
- Any step where a value's **asserted/observed status cannot be stated**, or where a guarantee
  cannot be attributed to a named layer (§3.4).

None of steps 2–4 currently appears to need any of these. If one turns out to, that is the
finding — the boundary met a real case and held, or it did not — and it matters more than the
bridge does.
