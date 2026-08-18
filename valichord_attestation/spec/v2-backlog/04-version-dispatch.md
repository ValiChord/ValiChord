# v2 backlog item: keeping v1.1/v1.2 bundles verifiable

**Status:** Open design. The only item here that is not "adopt RFC 6962".
**Blocks:** all of `01`–`03`. None of them can ship until this is decided.

## Problem

Changing the Merkle construction changes every root. A bundle written under v1.2 stores a
root computed the old way, and there is currently no code path that can reproduce it once
`merkle_root` implements the new construction.

That matters because bundles are meant to be verifiable indefinitely. A v1.2 bundle
published today, referenced from a Holochain `ValidationRequest.data_hash`, must still
verify in two years against a library that has moved on.

The library is not currently shaped to do this. Three call sites, three different amounts
of trouble:

| Call site | Has the bundle? | Can dispatch on version? |
|---|---|---|
| `verify_response(challenge, response, bundle, …)` | yes | **yes** — reads `bundle.format_version` |
| `build_response(challenge, log_samples)` | no | no — writes new proofs, so v2 is correct by default |
| `verify_faithfulness(root_hex, sample_index, sample, proof)` | **no** | **no** — this is the problem |

`verify_faithfulness` takes a bare root hex and a proof. It has no idea which construction
produced them, and no argument through which to be told. It cannot be made
version-correct without a signature change — which is itself a breaking change, arriving
inside a breaking release, so the cost is at its lowest right now.

`builder.py` hardcodes `format_version="v1.2"` at line 96; that part is a one-line bump.

## Options

**A — thread a version parameter through.** `merkle_root(samples, *, version="v2")`,
`leaf_hash(sample, *, version=…)`, `verify_faithfulness(…, version=…)`. Explicit at every
call, and every caller must be updated. Most churn, least ambiguity.

**B — a module per construction.** `merkle_v1.py` and `merkle_v2.py`, with
`merkle_for(format_version)` returning the right one. `merkle.py` re-exports v2 as the
default. Old vectors then exercise a module that never changes again, which is the
cleanest story for "this bundle from 2026 still verifies".

**C — v2 as the default, v1 retained under an explicit name.** `merkle_root` becomes v2;
`merkle_root_v1_2` stays for verification of old bundles. `verify_faithfulness` gains an
optional `version` argument defaulting to v2. Least churn; slightly worse at signalling
that two constructions coexist.

Leaning **B**. The separation is legible to an outside reimplementation, and it makes the
retention rule structural rather than a convention someone has to remember: `merkle_v1.py`
is frozen, and the existing vectors are its permanent test.

## What makes this tractable now

`tests/vectors/merkle_v1_2.json` pins the old construction with seven cases and a
documented collision, contributed 2026-08-18. Before those vectors existed, changing the
construction meant losing the ability to demonstrate the old one still worked. Now the old
path has a permanent, external, language-neutral regression suite, and the change is safe
to make.

That is the main reason this item moved from "someday" to "decidable".

## Open questions

1. Does `Bundle.format_version` become the single source of truth for construction
   selection, or is there an explicit `merkle_construction` field? A separate field is
   more honest — the construction is not the only thing `format_version` governs — but it
   is another field to get wrong. Suggest deriving from `format_version` and documenting
   the mapping in one table.
2. Should `verify_faithfulness` keep its current signature with a `version` default, or
   take the bundle? Taking the bundle is better typed and closes the question, but changes
   it from a free function over primitives into one coupled to `Bundle`.
3. Migration wording: §12 promises "a v2 spec will document migration from v1". Migration
   here is not rewriting bundles — old bundles stay valid and unmodified — it is telling
   implementers which construction applies to which declared version. State that plainly,
   because "migration" will otherwise be read as "regenerate your bundles".
