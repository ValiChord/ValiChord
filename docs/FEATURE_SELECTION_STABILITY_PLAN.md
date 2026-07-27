# Independent Stability Attestation for L1 Feature Selection — Build Plan

**Created:** 2026-07-27
**Status:** Plan — build starts 2026-07-28
**Scope:** One self-contained demonstration. No protocol changes, no DNA changes, no new library.

---

## 1. The claim being demonstrated

> When a model's feature selection is published, no record of the publisher's own runs — however
> immutable, however complete — can establish that an independent party would have selected the
> same features. That requires parties who resample separately and cannot see each other's answer
> before committing to their own.

This is ValiChord's existing thesis applied to a domain it has never been shown in. Everything
demonstrated is mechanism ValiChord already has; what is new is the **subject matter** and one
genuine conceptual step (§3.4).

## 2. Why this domain, and why it bites

**λ-shopping.** An L1 penalty is tuned by a single scalar. Nudge it and a specific coefficient
goes to exactly zero. Nothing in a published model reveals how many values were tried, or that
the final one was chosen because of which variable it excluded.

In credit, insurance or employment screening this is not academic. *"We did not use postcode"* and
*"L1 dropped postcode at the penalty strength we happened to select"* are materially different
claims that produce an identical model card. The audience for this is model risk management —
SR 11-7, PRA SS1/23, EU AI Act Article 15 (accuracy and robustness).

It is structurally the same problem as evaluation cherry-picking, which `prml_lock_hash` and the
Falsify pre-registration work already address (`docs/EU_AI_ACT_ARTICLE_12_PLAN.md` §4). The
selection case is sharper because the lever is one number.

**The honest boundary.** A complete record of every run *would* expose λ-shopping — if the
recorder recorded everything. That is self-policing, and it answers *"what did I do?"* It cannot
answer *"would anyone else, on their own split, have chosen these features?"* That second question
is what this demonstrates, and it is not a deficiency of record-keeping. It is a different
question.

## 3. Design

### 3.1 Data

**Synthetic, with deliberately correlated blocks.** Ground truth is known, there is no licensing
question, and anyone can reproduce it from the script alone. Design:

- `n = 500`, `p = 40`
- Three correlated blocks of 4 features each (ρ ≈ 0.95 within block), plus 28 independent noise
  features
- True signal carried by **one** feature from each block — so the correct answer is genuinely
  ambiguous by construction, exactly as §2 of `polite-shrink/RELATED_regularisation.md` describes
- Fixed generating seed, published

Real-data replication is a follow-on (§7), not day one.

### 3.2 The pre-registered protocol

Fixed and hashed **before any party runs anything**:

| Field | Example |
|---|---|
| `dataset_hash` | SHA-256 of the generated matrix |
| `estimator` | `sklearn.linear_model.LassoCV` |
| `lambda_rule` | `"LassoCV(cv=5) grid; α = one-standard-error rule over mse_path_"` — a *rule*, not a value |
| `lambda_rule_impl_hash` | SHA-256 of the source of the function implementing that rule |
| `resample_scheme` | `"bootstrap, n=500, with replacement"` |
| `n_validators` | 5 |
| `support_definition` | `"coef != 0"` |

`lambda_rule` is the load-bearing field. Pre-registering a **rule** rather than a **value** is
what forecloses λ-shopping: each party derives their own λ from their own resample by the agreed
procedure.

**scikit-learn has no one-standard-error rule, and no `alpha_1se`.** `LassoCV.alpha_` is the
CV-MSE *minimiser*; the 1-SE rule exists in glmnet (`lambda.1se`) and has never been implemented
in sklearn. The rule must therefore be written out as a computable procedure over the fitted
`mse_path_` (shape `n_alphas × n_folds`) and `alphas_`:

> mean and standard error of MSE across folds at each α; take the **largest** α whose mean MSE is
> ≤ (minimum mean MSE + 1 SE at the minimising α).

Two consequences. First, that helper **is** part of the pre-registered protocol — its source is
hashed into `protocol.json` as `lambda_rule_impl_hash`, not merely described in prose, or the
"rule not value" guarantee is prose only. Second, `LassoCV` derives its α grid *from the data*
(`n_alphas=100`, `eps=1e-3`, α_max from X and y), so each party's grid differs. That is correct
for this design — it is what makes each party's λ genuinely their own — but it makes the rule
sklearn-version-sensitive, so the version is pinned and recorded (in `meta`; see §3.5).

### 3.3 The round

1. **Researcher** runs the protocol on their resample, obtains a support set, seals it
   (commitment = SHA-256 over the canonicalised support plus a nonce), publishes only the hash.
2. **Five validators** each draw their *own* bootstrap resample with their own seed, run the same
   pre-registered protocol, seal their own support, publish only hashes.
3. **Simultaneous reveal.** Any reveal not matching its seal is rejected.
4. **Aggregate** into a per-feature selection profile.

Blinding is the whole point: no party sees another's support before committing.

### 3.4 What counts as agreement — the one real design decision

**Exact support match is the wrong metric and the demonstration should show it failing.** With
correlated blocks, honest independent parties will pick different members of the same block. Under
an exact-match rule every round returns "not reproduced", which is uninformative.

The demonstration reports **both**, deliberately:

- **Exact-match verdict** — expected to fail, shown failing, with the reason
- **Per-feature selection frequency across validators** — the informative result

The output is a stability profile: *feature 7 selected by 5/5, feature 12 by 3/5, feature 13 by
2/5.* Features 12 and 13 are the same correlated block, and the split between them **is the
finding** — it says the data cannot distinguish them, which is precisely what a model-risk
reviewer needs and what a single party's own bootstrap can assert but not evidence.

**Report per-block frequency alongside per-feature.** Without it, honest disagreement and the
§4 step-6 attack are indistinguishable — both surface as "the parties disagreed", and a reader
has no way to tell them apart. With it they separate cleanly:

| Pattern | Reads as |
|---|---|
| Block total ≈ 5/5, split across its members (12 at 3/5, 13 at 2/5) | Correlated-block ambiguity — expected, honest |
| Researcher omits a feature whose **block** validators select at ≈ 5/5 | The λ-shopping signature |

This is the discriminating statistic, and it is what makes step 6 an exhibit rather than an
anecdote. The attack is invisible in the *published artefact*; it is not invisible to *this
protocol*, and the demonstration has to show both halves of that or it shows nothing.

**The conceptual step.** Stability selection (Meinshausen & Bühlmann, 2010) is one party
resampling their own data — the party with the incentive is also the only witness. Here the
resamples are **independent parties who cannot see each other**.

State the size of that claim precisely, because a statistically literate reader will otherwise
size it for us. Five parties bootstrapping the same dataset under the same rule is the *same
estimator* as one party drawing five bootstraps — same distribution, no new statistics. What
differs is entirely who witnesses the draw and the fact that no party can condition their answer
on another's. **Statistically identical; epistemically different.** That difference is the novel
part, and the only part worth calling novel.

**Framing discipline (carried from `memory/feedback_arc_sim_polite_shrink_is_product.md`):**
validator disagreement here is the *expected and correct* behaviour of the method. It must never
be presented, or allowed to read, as ValiChord failing to reproduce. Attribute every divergence to
correlated-block ambiguity explicitly before it appears in any summary.

### 3.5 Attestation bundles

One `valichord_attestation` bundle per party, via `build_bundle` directly — **no new adapter on
day one**.

The intended payoff is a property already built and never demonstrated: **`content_hash` excludes
`meta`, `bundle_hash` includes it** — so `content_hash` answers *"same features selected?"* and
`bundle_hash` answers *"same features **and** same conditions?"* That is literally "preserve the
regularisation settings, evaluate stability separately" as two hashes.

**Getting that requires care, because `content_hash` excludes `meta` and nothing else.**
`canonical.py:93` pops exactly one key; every other field in `bundle_to_dict`
(`canonical.py:41-52`) is inside the hash — including `generated_at`, `outputs_merkle_root`,
`model_id` and `task_id`. Built naively, five parties who select *identical* feature sets still
produce five different `content_hash` values, and the demonstration would assert a property the
library does not have. The bundle layout is therefore fixed as:

| Field | Value | Why |
|---|---|---|
| `model_id` | `"lasso-cv-1se"` — identical for all parties | in `content_hash`; party identity here would defeat the comparison |
| `task_id` | `protocol_hash` — identical for all parties | binds every bundle to the pre-registration; same reason |
| `generated_at` | the protocol's fixed timestamp, passed explicitly | defaults to wall-clock `now()`, which alone would break every match |
| `raw_metrics` | one entry per feature, `{key: "selected__<name>", value: 0.0 \| 1.0}` | **this is the claim** — the thing two parties should agree on |
| `samples` | the per-feature selection records | drives `outputs_merkle_root`, which is in `content_hash` |
| `meta` | party ID, resample seed, **derived** λ, `lambda_rule`, `lambda_rule_impl_hash`, `cv_folds`, `sklearn` version, `dataset_hash`, `protocol_hash` | the conditions — excluded from `content_hash`, included in `bundle_hash` |

Two traps worth naming because both are silent. `samples` **must not** be the per-resample rows:
those differ per party by construction, so the Merkle root — and therefore `content_hash` — would
be party-specific whatever was selected, and the headline claim would be quietly false. And the
top-level `repo_commit` / `harness_version` / `command` parameters of `build_bundle` are *not*
`meta`; they sit in `content_hash` too. All provenance goes in `meta`.

The resample itself is still evidence and still gets committed — as its seed in `meta`, inside
`bundle_hash`, which is exactly where "same conditions?" belongs. Step 7 asserts both hash
behaviours rather than assuming them; if the assertion cannot be made to hold, §3.5 is wrong and
the write-up compares the `metrics` lists directly instead of claiming a property we do not have.

## 4. Build order

| # | Step | Output |
|---|---|---|
| 1 | `generate.py` — correlated-block synthetic data, fixed seed | matrix + `dataset_hash` |
| 2 | `protocol.py` — pre-registration record, canonicalised + hashed; includes `lambda_rule_impl_hash` over the step-3 rule function | `protocol.json` + hash |
| 3 | `party.py` — resample → `LassoCV` → **explicit 1-SE selection over `mse_path_`** (§3.2) → support → seal(support, nonce) | commitment per party |
| 4 | `round.py` — commit all, reveal all, verify each reveal against its seal | round record |
| 5 | `aggregate.py` — exact-match verdict, per-feature frequency, **and per-block frequency** (§3.4) | `results.json` |
| 6 | `lambda_shop.py` — adversarial: search λ until feature *k* drops; show the published artefact looks identical **and that the per-block profile exposes it** | the money exhibit |
| 7 | Bundles — one per party via `build_bundle` on the §3.5 layout; assert two identical-support parties share a `content_hash` and differ in `bundle_hash` | `bundles/*.json` |
| 8 | `REPORT.md` — the argument, the plots, the honesty ledger | write-up |

**Location:** `valichord_attestation/examples/feature_selection_stability/`, mirroring
`examples/mistral_7b_gsm8k_demo/`.

**Dependency:** adds `scikit-learn` — dev/example extra only, never a core dependency.

**Runnable with no key, no GPU, no network, no conductor.** That is a hard requirement; it is what
makes the artefact shareable.

## 5. Honesty ledger — what is real and what is simulated

Written into `REPORT.md`, not buried:

| Element | Status |
|---|---|
| Correlated-block instability | **Real** — genuine sklearn output |
| λ-shopping attack | **Real** — genuine search, genuinely invisible in the published artefact |
| Commitment hashes and reveal verification | **Real** — actual SHA-256 commit-reveal, actually verified |
| Attestation bundles | **Real** — the shipping `valichord_attestation` library |
| Independent parties | **Simulated** — five processes on one machine, not five agents on a DHT |
| The Holochain round | **Not present** — no conductor, no DNA, no HarmonyRecord |
| Dataset | **Synthetic** — proves the mechanism, not its practical incidence |

The blinding is enforced by construction in the script rather than by a network. **Say this
plainly.** Wiring to the live protocol is §7, and the demonstration must not imply it has happened.

## 6. What this does not settle

- **What "reproduced" should mean for a selection.** The demonstration takes a position —
  per-feature frequency, not exact match — and argues for it. It does not settle it. A threshold
  π (as in stability selection) is left explicitly unset, for the same reason polite-shrink
  refuses to pick R.
- **Whether λ-shopping happens in practice.** The attack is demonstrated as *possible and
  invisible*, not as prevalent. No claim about real-world incidence.
- **How far the per-block signature generalises.** §3.4's discriminating statistic works because
  the block structure is known by construction. On real data the blocks are estimated, not given,
  and a shopper who drops a feature the validators were also going to drop is indistinguishable
  from an honest one. The claim is that the attack becomes *detectable*, not that it becomes
  *undeniable*.
- **Whether five parties is enough.** Arbitrary, chosen for legibility.

## 7. Follow-ons — explicitly not day one

1. Real dataset replication (a public credit dataset, licensing checked first)
2. A `SklearnAdapter` for `valichord_attestation` — only if the direct `build_bundle` route proves
   awkward, not on spec
3. Wiring to the live protocol — a real round on the Oracle nodes producing a real HarmonyRecord
4. `prml_lock_hash` linkage, making the pre-registration a Falsify PRML manifest

## 8. Distribution — decided in advance

**Publish it; do not send it.** A public artefact in the repo can be found, used, cited or ignored
with no obligation. A private one addressed to a particular person creates a debt they have to
discharge, and reads as courtship however it is worded — which would undercut the peer footing the
Vericertum thread is currently on (`vericertum_outreach_TEMP.md`).

Once public, referring to it is natural: *"I built the thing we were circling; it's here."*

**Do not send it into silence.** As of 2026-07-27 Bhavesh has not replied to Ceri's second
message. Build regardless — the artefact stands on its own merits — but let him reply before
pointing him at it.

---

*Plan directed by Ceri John; drafted with AI assistance (Claude, Anthropic).*
