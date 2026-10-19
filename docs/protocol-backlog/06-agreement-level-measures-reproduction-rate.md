# 06 — `AgreementLevel` measures the reproduction rate, not agreement

**Raised:** docs audit, 2026-10-18 (found while correcting doc 10 against the code).
**Category:** 🔴 — it determines what an immutable HarmonyRecord *says*. Records written before a
fix keep the current meaning forever.
**Needs a network break?** Yes, to rename the field or change its values (it lives in the
governance integrity zome's HarmonyRecord). Documenting it does not.
**Decided (Ceri, 2026-10-19):** do not rename now; document it clearly, and keep this item for a
future break.

## The evidence

`derive_agreement_level` (`valichord/shared_types/src/lib.rs`, `pub fn derive_agreement_level`)
computes two rates over the validators' outcome labels:

- `full_rate` = Reproduced / total
- `any_rate` = (Reproduced + PartiallyReproduced) / total

and maps them to `ExactMatch` (full ≥ 0.90), `WithinTolerance` (any ≥ 0.70), `DirectionalMatch`
(any ≥ 0.50), `Divergent` (any > 0) or `UnableToAssess` (any = 0).

So the level says **how many validators reproduced the result**, not **how much the validators
agreed with each other**. Consequences:

- Three validators who **unanimously** fail to reproduce get `UnableToAssess` — a name that reads
  as "could not tell", when in fact all three agreed it did not reproduce. `evaluate_badge` then
  issues a FailedReproduction badge from it, so the badge is right but the level's name is wrong.
- `Divergent` sounds like "validators disagreed", but it means "some, but under half, reproduced".
- The level never compares numbers: it counts outcome labels only (numeric matching is
  client-side — see `docs/DIAGRAMS.md` §3).

## What is open

1. **Rename** (e.g. `ReproductionLevel`, with values that describe rates), or
2. **Add** a genuine agreement measure alongside it (do the validators' outcomes and numbers agree
   with each other, regardless of whether they reproduced the researcher's result?), or
3. **Leave the field** and rely on documentation.

Options 1 and 2 change the HarmonyRecord, so they cost a DNA-hash break and should ride one that is
happening anyway. The cut-offs (0.90 / 0.70 / 0.50) remain placeholders whatever is chosen.
