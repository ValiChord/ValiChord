# GitHub Sponsors — tiers

## STATUS on GitHub (dashboard read 2026-07-30)

The suggestion picker worked as intended. **Two monthly tiers exist, both `Draft`:**

| Tier | ID | Edit URL | Current text (GitHub's boilerplate) |
|---|---|---|---|
| $5/month | `642060` | `/sponsors/topeuph-ai/dashboard/tiers/642060/edit` | "Get a Sponsor badge on your profile" |
| $25/month | `642061` | `/sponsors/topeuph-ai/dashboard/tiers/642061/edit` | "Logo or name goes in my project README" |

A third tier id (`642062`) appears in the page's own event payload but not on the
monthly tab — almost certainly the **$50 one-time** draft, which lives under the
"One-time tiers" tab. Confirm it's there.

**The Twitter shoutout was correctly not created.** Good.

### Three things still to do

1. **Publish them.** The dashboard reads *"You have 0 published tiers and 2 draft
   tiers."* **A draft tier is invisible to sponsors and cannot be sponsored.**
   This is the one step that actually matters.
2. **Replace the boilerplate** with the descriptions below. Right now both tiers
   still say GitHub's text, including the $5 tier advertising the Sponsor badge —
   which GitHub grants automatically to every sponsor at any tier, so as written
   that tier promises nothing.
3. **Fill the two "Custom amounts" fields**, both currently empty:
   - *Recommend a sponsorship amount* → **$5**, matching the entry tier.
   - *Set minimum amount* → **$1**. The whole independence argument is breadth of
     support, so the floor should be as low as GitHub allows.

   Note the dashboard's own warning: *"Sponsors will not be assigned to a tier for
   a custom monthly sponsorship if you don't have a published monthly tier."*
   Another reason step 1 comes first.

### Platform limits (from the dashboard)

- 10 published monthly tiers, 10 published one-time tiers.
- Maximum tier amount **$12,000**.
- One-time sponsors automatically get their badge on your sponsors page and
  receive your email updates **for one month** — no need to promise either.

---


Two monthly + one one-time, at the amounts GitHub's tier-suggestion picker offers
(verified from that page 2026-07-30: monthly 5/10/25/30/100/500/1000, one-time
10/50/200/350/500/1000/2000/5000 — there is no $15/month or $25 one-time option).
Each description is well under GitHub's field limit. Paste one block per tier.

**On the suggestions page, tick exactly these three and untick the rest:**

| Amount | GitHub's checkbox | Becomes |
|---|---|---|
| $5/mo | "Get a Sponsor badge on your profile" *(pre-checked)* | Keep the records alive |
| $25/mo | "Logo or name goes in my project README" | Fund a node |
| $50 one-time | "Earn a mention in our Release notes" | A month of hosting |

⚠️ **Untick "$10 one time — Get a shoutout on Twitter", which is pre-checked.** It
commits you to a tweet per sponsor on a channel you don't use.

⚠️ **The $5 sponsor badge is automatic** — GitHub grants it to every sponsor at any
tier. It is not a reward, which is why the $5 description below pays in something real.

Selections sharing a price **merge into a single tier**, so tick one per price point.

---

## $5 / month — Keep the records alive

**Name:** Keep the records alive

**Description:**

Funds the hosting that keeps published Harmony Records fetchable. Your name in SPONSORS.md if you'd like it there, and a sponsor update whenever a version ships: what shipped, what broke, and what I got wrong.

---

## $25 / month — Fund a node

**Name:** Fund a node

**Description:**

Everything in the previous tier, plus you or your organisation named with a link in the ValiChord README for as long as you sponsor — for labs, journals and companies who'd rather this project's independence were visibly funded than quietly assumed.

What it doesn't buy: any influence over a verdict, a record, or who validates what. That constraint is the product.

---

## $50 one-time — A month of hosting

**Name:** A month of hosting

**Description:**

A single month of the live network, no strings and no ongoing commitment. Your name in SPONSORS.md and in the release notes of the version it funded, if you want them there.

---
---

# What to leave UNCHECKED on the suggestions page, and why

Two entire categories are traps for this project:

**🤖 Access To Code** — "Access to private repositories", "Get access to my
sponsorware repository", "Get a company license for my project". All three
contradict a project whose pitch is that it is open and checkable; sponsorware
worst of all, since gating code undercuts the intro's own argument. The $500/month
company licence is separately premature — a real commercial-licence option exists in
`TRADEMARK.md`, and pre-pricing it as a sponsor perk would undercut any actual
licensing negotiation.

**🙂 Facetime And Consulting** — all five (company chat support at $1,000/mo, pair
programming, consulting/mentorship, a team workshop, a conference talk). Time that
isn't available, and several sit badly with how this project is actually built.

**📓 Community And Education** — a weekly newsletter is a cadence promise the
calendar controls; the community chat space and the videos/screencasts/tutorials
don't exist and shouldn't be sold before they do.

**🛠️ "$100/mo — Have your bug reports prioritized"** — the closest thing on the page
to selling priority, and unstaffable besides.

**🎉 "$100/mo — Logo or name on project website"** — genuinely deliverable and the
natural next tier to add. Hold it until someone asks, so the top of the ladder isn't
conspicuously empty.

# The one rule these tiers follow

**No reward may touch the protocol's outputs.** This is where the standard
sponsorship playbook is actively wrong for ValiChord. Perks that would be
unremarkable elsewhere are disqualifying here:

- priority or expedited validation of a sponsor's claim
- any sponsor mark on a Harmony Record
- influence over agreement thresholds, badge tiers, or what counts as reproduced
- a vote on which studies get validated
- preferential treatment in validator selection

ValiChord's entire proposition is that no party can alter the record and no party
gets a better answer than anyone else. Selling any of the above would destroy more
value than it raised — and a sceptic would find it immediately. Recognition and
information are the only safe currencies, which is why every tier above pays in
those.

# Two delivery cautions

**Cadence is tied to releases, not the calendar.** "A sponsor update whenever a
version ships" is a promise you control. "Monthly updates" is one the calendar
controls, and a missed month is visible to everyone paying.

**Nothing here costs you time you don't have.** No calls, no support hours, no
consulting, no bespoke work at any tier. Those are the perks solo maintainers most
often regret — they convert sponsorship into obligation, and they scale with
success in the wrong direction. A README line costs one commit.

# What to add later, not now

The $100/month website-placement tier, once someone asks. Then an organisation tier
above it if a lab or journal ever wants one.

Sponsor-only technical write-ups are also tempting and I'd avoid them — the project
is Apache-2.0 and open by argument, so gating documentation sits awkwardly with the
pitch. Early access to a write-up is fine; permanent exclusivity is not.

# Prerequisite

Create SPONSORS.md in ValiChord/ValiChord before the first sponsor arrives. Two of
the four tiers reference it, and an unmet perk on day one is a bad first impression.
