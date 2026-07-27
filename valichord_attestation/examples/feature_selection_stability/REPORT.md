# Independent Stability Attestation for L1 Feature Selection

**Run date:** 2026-07-27 · **scikit-learn:** 1.9.0 · **Plan:** `docs/FEATURE_SELECTION_STABILITY_PLAN.md`

Reproduce everything here with `./run_all.sh`. No API key, no GPU, no network, no Holochain conductor.

---

## The claim

> When a model's feature selection is published, no record of the publisher's own runs — however
> immutable, however complete — can establish that an independent party would have selected the
> same features. That requires parties who resample separately and cannot see each other's answer
> before committing to their own.

## What was run

`n = 500`, `p = 40`. Three correlated blocks of four features (ρ ≈ 0.95 within block, realised
0.950 / 0.953 / 0.949) plus 28 independent noise features. True signal is carried by **one** feature
per block — `blk0_f0`, `blk1_f0`, `blk2_f0` — with coefficients 3.0 / 2.0 / 1.0. The correct answer
is therefore genuinely ambiguous by construction: nothing distinguishes `blk2_f0` from `blk2_f2`
except which one the data happened to favour.

The protocol was fixed and hashed before any party ran anything:

```
protocol_hash          6df77610…
dataset_hash           26f4b6f4…
lambda_rule            LassoCV(cv=5) grid; alpha = largest alpha whose mean CV MSE
                       <= (min mean CV MSE + 1 SE at the minimiser)
lambda_rule_impl_hash  6b1a7909…
resample_scheme        bootstrap, n=500, with replacement
support_definition     coef != 0
```

`lambda_rule` is a **rule**, not a value — each party derives their own λ from their own resample.
`lambda_rule_impl_hash` is what stops that being prose: it pins `lambda_rule.py` in full, so a
change to `CV_FOLDS` invalidates the pre-registration exactly as a change to the function body does.

One researcher and five validators each drew their own bootstrap resample, ran the pre-registered
procedure, and sealed the resulting support set. Every commitment was published before any reveal
was accepted — enforced in `round.py` by a guard that refuses a reveal while any commitment is
outstanding, and the guard is exercised in the output so the claim is seen failing, not asserted.

## Result 1 — the exact-match verdict fails, as designed

**5 distinct supports across 5 validators.** Under ρ = 0.95 blocks this was always going to happen,
and it is why exact match is not the verdict: it cannot distinguish honest parties picking different
members of the same block from parties genuinely disagreeing about what matters.

## Result 2 — the selection profile

| Feature | Selected by | |
|---|---|---|
| `blk0_f0` | 5/5 | true signal (β = 3.0) |
| `blk1_f0` | 5/5 | true signal (β = 2.0) |
| `blk2_f0` | 5/5 | true signal (β = 1.0) |
| `blk2_f2` | 3/5 | correlated partner — no signal of its own |
| `noise_26` | 3/5 | pure noise |
| `blk0_f1`, `blk1_f3` | 2/5 | correlated partners |
| 24 noise features | 1–2/5 | pure noise |

**All three true signals were recovered unanimously.** This is a cleaner recovery than the plan
anticipated, and it is reported as it came out rather than tuned. Raising ρ or shrinking the
coefficients would have produced a more dramatic split; doing so to obtain a more persuasive figure
would be the exact behaviour this demonstration exists to expose.

The block-partner split is real but secondary: `blk2_f2` at 3/5 and `blk0_f1` at 2/5 are the data
saying it cannot cleanly separate those features from their partners. **That split is the finding.**
A single party's own bootstrap can assert it; only independent parties can evidence it.

The noise tail is mostly one party's doing — see the honest wrinkle below.

## Result 3 — per-block frequency, the discriminating statistic

```
blk0: 5/5 of validators   [blk0_f0=5/5, blk0_f1=2/5, blk0_f2=1/5]
blk1: 5/5 of validators   [blk1_f0=5/5, blk1_f1=1/5, blk1_f2=1/5, blk1_f3=2/5]
blk2: 5/5 of validators   [blk2_f0=5/5, blk2_f2=3/5, blk2_f3=1/5]
```

Without this, honest disagreement and the attack below are indistinguishable — both read as "the
parties disagreed". With it they separate: a block at 5/5 whose *members* split is ambiguity; a
block at 5/5 that the researcher dropped **entirely** is something else.

## Result 4 — λ-shopping, and what catches it

The attacker does not fabricate anything. They search the penalty until the coefficients they want
gone hit exactly zero, then publish the model. Targeting `blk2` (the weakest true signal, and so the
cheapest to remove):

| | Honest | Shopped |
|---|---|---|
| Estimator | `sklearn.linear_model.Lasso` | `sklearn.linear_model.Lasso` |
| Penalty α | 0.138306 | 0.996366 |
| Features selected | 6 | 2 |
| Block-2 feature used | yes | **no** |

Both are true. Neither records how many α values were tried. 0.996 is an unremarkable number;
nothing marks it as the smallest one that removed `blk2`.

**The protocol flags it — `blk2` at 100% validator consensus, absent from the researcher's support.**
The validators derived their own λ from their own resamples and never saw the researcher's, so the
attacker could not know what they would say, and could not reach them.

### The honest limit, stated plainly

Shopping *within* a block is **not** flagged, and cannot be. Dropping `blk2_f2` at α = 0.1905 while
retaining `blk2_f0` passes clean — correctly, because honest parties substitute within a correlated
block constantly. The protocol detects a dropped **block**, not a dropped **feature**.

It is also weaker on real data than it looks here: the block structure is known by construction in
this synthetic design. On real data blocks are estimated, and a shopper who drops a feature the
validators were going to drop anyway is indistinguishable from an honest party. **Detectable, not
undeniable.**

There is one structural constraint on the attacker worth noting: raising the penalty removes
features in order of weakness, so only a comparatively weak member can be shopped away while its
block survives. Targeting the *strongest* member exhausts the search — by the time α is high enough
to remove it, the whole block has already gone, which is the case that gets flagged.

## Result 5 — the two hashes

One `valichord_attestation` bundle per party, via `build_bundle` directly. No adapter.

```
party           n   content_hash        bundle_hash
researcher      6   19c948f46cf559fef5…  dca6dce4ef0cf8491c…
validator_1     4   f5017ff8eef587b585…  7aa50c6b8dfc702244…
validator_2     6   af0e2523abc4732f91…  71cf064fc5b65fc8a6…
validator_3     8   a6fde5f0e8490cdfbd…  08a11d629df55364f7…
validator_4     6   6e2e841e55e5857de3…  1ba68be1662931b3b6…
validator_5    33   df6b9721657f6f06e5…  4c7e55afb10894d5a6…

distinct content_hashes: 6 of 6
```

`content_hash` excludes `meta`; `bundle_hash` includes it. So `content_hash` asks *"same features
selected?"* and `bundle_hash` asks *"same features **and** same conditions?"* — "preserve the
regularisation settings, evaluate stability separately", as two hashes. Six distinct
`content_hash`es is the stability finding restated: no two independent parties selected the same set.

This property is **verified, not assumed**. `bundles.py` constructs a controlled pair — identical
support, different seeds and λ — and asserts that they share a `content_hash` and differ in
`bundle_hash`. Both hold.

Getting there required care that is worth recording, because the obvious implementation is wrong.
`content_hash` excludes `meta` and **nothing else**: `generated_at`, `outputs_merkle_root`,
`model_id` and `task_id` are all inside the digest. Built naively — party name in `model_id`,
wall-clock `generated_at`, resample rows as `samples` — five parties with byte-identical results
would produce five different `content_hash`es, and this section would be claiming a property the
library does not have. So `model_id`, `task_id` and `generated_at` are pinned across parties in the
pre-registration, `samples` holds per-feature selection records rather than resample rows, and all
provenance lives in `meta`. Note that `build_bundle`'s top-level `repo_commit` / `harness_version` /
`command` parameters are *not* `meta` — they are inside `content_hash` too.

## An honest wrinkle: the 1-SE rule is itself unstable

`validator_5` derived α = 0.0126 where every other party landed between 0.103 and 0.142, and
consequently selected 33 of 40 features. That single party accounts for most of the noise tail in
Result 2.

This is not a bug and has not been removed. It is the 1-SE rule behaving as it does under
resampling: when the CV curve is flat and the fold-to-fold standard error at the minimiser is small,
the one-SE threshold is tight and the rule returns something close to the minimiser — a much denser
model. It is a genuine instability in the *pre-registered procedure*, surfaced by exactly the
mechanism this demonstration is about, and it would have been invisible to a single party reporting
a single fit.

It also sharpens why the per-block statistic matters: `validator_5` is an outlier on *density* while
agreeing completely on *blocks*.

## What was real and what was not

| Element | Status |
|---|---|
| Correlated-block instability | **Real** — genuine sklearn output |
| λ-shopping attack | **Real** — genuine search, genuinely invisible in the published artefact |
| Commitment hashes and reveal verification | **Real** — actual SHA-256 commit-reveal, actually verified |
| Attestation bundles | **Real** — the shipping `valichord_attestation` library |
| Independent parties | **Simulated** — six processes in one script, not six agents on a DHT |
| The Holochain round | **Not present** — no conductor, no DNA, no HarmonyRecord |
| Dataset | **Synthetic** — proves the mechanism, not its practical incidence |
| Nonces | **Derived from seeds**, not from the OS CSPRNG, so the run is reproducible |

The blinding is enforced by a Python guard in `round.py`, not by a network. Nothing here has run on
Holochain. Wiring this to the live protocol is future work and **must not be implied to have
happened**.

Two smaller substitutions, recorded so they are decisions rather than omissions. The plan called for
plots; the profile is rendered as text bars instead, to keep the "runnable with nothing" promise
rather than pull in a plotting dependency for one chart. And nonces are seed-derived, as above — in
production the nonce must be unpredictable, since the support space is small enough to brute-force
against a guessable one.

## What this does not settle

- **What "reproduced" should mean for a selection.** This takes a position — per-feature frequency,
  not exact match — and argues for it. It does not settle it. The threshold π is left explicitly
  unset, for the same reason polite-shrink refuses to pick R.
- **Whether λ-shopping happens in practice.** Demonstrated as *possible and invisible*, not as
  prevalent. No claim about real-world incidence.
- **How far the per-block signature generalises.** It works here because the blocks are known. See
  the honest limit above.
- **Whether five validators is enough.** Arbitrary, chosen for legibility.

## The conceptual step, sized precisely

Stability selection (Meinshausen & Bühlmann, 2010) is one party resampling their own data — the
party with the incentive is also the only witness. Here the resamples are independent parties who
cannot see each other.

State the size of that claim before someone else sizes it: five parties bootstrapping the same
dataset under the same rule is the *same estimator* as one party drawing five bootstraps. Same
distribution, no new statistics. What differs is entirely who witnesses the draw, and the fact that
no party can condition their answer on another's. **Statistically identical; epistemically
different.** That difference is the novel part, and the only part worth calling novel.

---

*Built by Ceri John with AI assistance (Claude, Anthropic).*
