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
protocol_hash          cc5588a4…
dataset_hash           26f4b6f4…
lambda_rule            LassoCV(cv=5, alphas=100, eps=1e-3) grid; alpha = largest alpha
                       whose mean CV MSE <= (min mean CV MSE + 1 SE at the minimiser)
lambda_rule_impl_hash  b6ee675e…
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
researcher      6   800c0ca1898ccd7366…  2bd8d344d00e1d6cc1…
validator_1     4   7af8dd2154f4066370…  5d8da569339e5e64b5…
validator_2     6   577c6081b88ff106d0…  20e1601d28736892cc…
validator_3     8   de60c132da8fa03a27…  887971d29d3b2eff4c…
validator_4     6   edb4431272ec8ec4db…  30d0dc4cd843b90560…
validator_5    33   3dfc0d91164a421742…  c51f409bb6c65d8b0e…

distinct content_hashes: 6 of 6
```

These hashes are downstream of the pre-registration: `task_id` is the
`protocol_hash`, so amending so much as the wording of `lambda_rule` re-hashes
every bundle. That happened once during the build — the rule text still named
sklearn's removed `n_alphas` parameter — and every `content_hash` on this page
moved while every selected feature and every derived α stayed identical. That is
the binding doing its job, and a useful thing to have seen.

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

## Does any of this generalise? (`sweep.py`, 1050 rounds)

Everything above comes from one draw of one dataset. The sweep repeats the whole
round over 150 independent datasets at each of seven signal strengths for the
attacked block, at 3 / 5 / 7 / 11 validators.

```
DETECTION / FALSE ALARM at threshold 0.8
  beta    recovery     k=3 (3/3)     k=5 (4/5)     k=7 (6/7)   k=11 (9/11)
  1.00       100%      100% / 0%     100% / 0%     100% / 0%     100% / 0%
  0.40       100%      100% / 0%     100% / 0%     100% / 0%     100% / 0%
  0.20        86%       68% / 5%      85% / 5%      77% / 5%      75% / 4%
  0.12        47%       19% / 4%      27% / 3%      19% / 3%      20% / 2%
  0.08        27%        6% / 2%      10% / 2%       7% / 1%       5% / 1%
  0.05        17%        2% / 1%       2% / 1%       1% / 0%       1% / 0%
  0.00        11%        0% / 0%       0% / 0%       0% / 0%       0% / 0%
```

**The single round's headline holds.** Pooled over 150 datasets the true signal
wins its block 100% of the time while the partners land at 24–33%. Not luck of
the seed.

**Detection tracks validator consensus, and dies with it.** The honest claim is
narrow: *this catches you when you remove something independent parties would
reliably have found, and not otherwise.* Detection is perfect while recovery is
perfect, ~85% when recovery is 86%, and ~20% once recovery falls to half. The
false-alarm rate stays between 0% and 5% throughout, and relaxing the threshold
from 0.8 to 0.5 at the transition lifts detection from ~20% to ~50% for a rise in
false alarms from 3% to 9%. **β = 0.2 / k = 5 — 85% detection at 5% false alarm —
is the operating point worth quoting.** The 100% rows are the easy case.

Of the 7 false alarms at β = 0.2, only 2 trace to the researcher's own fit being
over-sparse; the other 5 are ordinary sampling variation. The 1-SE instability
cannot be blamed for most of them.

**Do not read the k columns as "more validators help".** The bracketed figure is
the threshold in validators, and rounding makes it uneven — k=3 must be unanimous
while k=5 needs only 4 of 5. Any wobble across k is that rounding. Comparing
validator counts fairly needs a count-based rule, which this sweep does not
implement, so **the Bronze/Silver/Gold question remains open.** The one clean
trend is false alarms falling as k rises.

The β = 0.00 row reads in reverse: there the attacked block carries no signal, so
removing it is legitimate and a flag would be a false accusation. It sits at 0%.

## Can any rule pick the right member? (`arbitration.py`)

Since the data is synthetic, ground truth is known, so "closer to the answer" is
a number. Three rules for choosing a block's representative, scored against
truth, at k=5 with 20 random orderings per block. Chance is 25%.

```
STRONG BLOCKS (beta 3.0 and 2.0), n=1000
  naive 100%   mass 100%   polite 100%   order-dependent 0%

ATTACKED BLOCK
  beta       n    naive     mass   polite   order-dep
  1.00     100    100%      98%      97%         8%
  0.40     100     84%      83%      73%        60%
  0.20     100     67%      58%      51%        73%
  0.12      90     60%      48%      46%        60%
```

**Plain vote-counting wins.** Weighting by coefficient mass loses at every level,
and the polite rule — polite-shrink's first-claimant-wins ordering, the
Gauss–Seidel sweep manufactured without a coordinator — loses by more. Two
predictions were made in advance and one was wrong: mass was expected to beat
naive on the reasoning that a block's total weight is determined while its split
is not. It does not. The uniqueness result says the split is *undetermined*; it
never promised the split was *informative*, and that was an over-reading.

**Why the polite rule loses is not a defect in it.** It works by privileging
whoever moves first, which in storage is exactly right — any valid allocation is
as good as any other, and the task is to reach one without collisions. Applied to
inference it discards the other four validators entirely, turning a five-witness
measurement into a one-witness measurement plus an arbitrary ordering. Same
mathematical shape, opposite objective. It is also only testable here as
*post-hoc* aggregation: a validator who defers to another's announced choice has
stopped being an independent witness, and that independence is the entire
evidentiary value of the round.

**The failure is reusable.** Order-dependence tracks signal strength almost
exactly — 8% → 60% → 73% → 60%. When the answer is determined, ordering is
irrelevant; when it is not, ordering decides. So the polite rule is a poor
arbitrator but a serviceable *diagnostic*: run it under permuted orderings and it
measures how underdetermined the answer is, putting a number on the uniqueness
result rather than citing it.

All three rules stay above chance even at β = 0.12, so the independent-witness
evidence is real even where it is weak — and the simplest aggregation of it,
which is what this demonstration already does, is the best of the three.

*Caveat: one formulation of the mass rule was tested (sum of |coefficient| across
validators). A median-based or count-then-tiebreak variant might fare better. The
direction is consistent across all four rows, so the conclusion is not marginal,
but it is not the last word on weighting either.*

## Why the block is the right unit

Counting at block level was introduced above for a practical reason — per-feature
counting cannot separate honest disagreement from concealment. There is a
stronger justification. With exactly interchangeable columns the lasso *fit* is
unique while the *coefficients* are not (R. J. Tibshirani, *The Lasso Problem and
Uniqueness*, EJS 7, 2013): what is determined is the block, not which member
carries it. Our blocks correlate at 0.95 rather than being identical, so this is
the finite-sample shadow of that result rather than an instance of it — unique
but unstable, not formally non-unique.

The same reading, reached independently from the distributed-storage side, is set
out in [`polite-shrink/RELATED_regularisation.md`](https://github.com/ValiChord/polite-shrink),
where coverage is determined but the holder set is not. The measurements above —
block recovered 100%, members scattered at 24–33%, and an arbitrator whose answer
moves with the ordering precisely when the signal is weak — are what that
prediction looks like in data.

The guardrail from that document applies here in mirror image: the instability
has a well-studied cause, and **this does not solve a known problem in
statistics.**

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
