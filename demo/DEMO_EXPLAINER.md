![ValiChord Demo](../Images/Demo%20description.png)

# What ValiChord Does — Plain English

## The problem

A scientist publishes a result. Another scientist tries to reproduce it and gets a different answer. Who do you believe?

The problem isn't dishonesty — it's that there's no structural way to tell whether the validators coordinated their answers, looked at each other's work, or changed their verdict after seeing the researcher's numbers. Honest science has no mechanism to prove it was honest.

ValiChord adds that mechanism.

---

## What the demo does

The demo runs a miniature version of ValiChord end-to-end, using an actual piece of mathematics as the "study":

- A researcher runs a linear regression on climate data and gets three numbers: slope, intercept, and R².
- Three independent validators each run the same code and check whether they get the same numbers.
- Everyone writes down their answer and seals it before anyone else opens theirs.
- When all four sealed answers exist, they're all opened at once.
- The result is written permanently to a public network where anyone can read it.

---

## The sealed envelope analogy

Imagine four scientists in four separate rooms. They cannot talk to each other.

The researcher writes their answer on a piece of paper, folds it, and puts it in an envelope sealed with wax. They push the envelope through a slot in the wall into a shared hallway. **They cannot reach back and change it.**

Each of the three validators runs the experiment themselves, writes their verdict, and does the same — without having seen the researcher's envelope or each other's.

Only once all four envelopes are in the hallway does anyone open them. They're all opened simultaneously. The answers are compared. The outcome is stamped on a public noticeboard that nobody can erase.

That's the commit-reveal protocol. ValiChord enforces it cryptographically — not by trusting that the scientists behaved honestly, but by making it mathematically impossible to change a sealed answer.

---

## Why four separate conductors?

In this demo, each participant runs on a completely separate Holochain conductor — its own process, its own cryptographic keypair, its own database. The only way they communicate is through a peer-to-peer network called the DHT (think of it like a shared noticeboard that no single person owns).

There is no central server that could be bribed or hacked to change a verdict. There is no administrator. The phase gate — the moment at which all envelopes are opened — triggers automatically when the network confirms that all commitments exist. No human pushes the button.

---

## What the output means

At the end of the demo you'll see a shareable URL like:

```
http://132.145.34.27:3001/record?hash=uhC8k…
```

That URL returns a permanent record — a **HarmonyRecord** — containing:

- The outcome (e.g. "Reproduced")
- The agreement level (e.g. "ExactMatch" — all three validators got identical results)
- Each validator's individual verdict and their reasoning
- Cryptographic links back to every commitment made during the process

Anyone in the world can read it. Nobody can edit it. The researcher cannot retroactively claim they meant different numbers. The validators cannot retroactively claim they agreed when they didn't.

---

## What "Reproduced" means

"Reproduced" means the validators got the **same result as the researcher** — not that the result is correct.

A study can be reproducible and scientifically wrong. A study can be correct but not reproducible. ValiChord only answers the reproducibility question: *can an independent party arrive at the same result?*

---

## Image generation prompt

For an illustration of this demo suitable for a general audience:

> Four scientists sit in separate rooms with no windows between them. Each room contains a simple desk and a sealed envelope. Above each scientist, a thought bubble shows the same mathematical graph — a line through a scatter plot. In the centre of the image, the four envelopes travel along glowing threads toward a shared floating crystal or orb that represents the permanent public record. The envelopes all open at the same moment, revealing identical answers. A soft teal and white colour palette. Clean editorial illustration style, no cryptocurrency or blockchain imagery, no servers or data centres — emphasise the human scientists and the sealed-envelope metaphor.

Alternative, more abstract:

> A circular arrangement of four glowing nodes connected by lines of light representing a peer-to-peer network. One node is labelled "Researcher" and three are labelled "Validator". Each node holds a sealed glowing capsule containing its verdict. The capsules travel simultaneously toward a central floating record book that emits soft light. The record book is open and permanent — no locks, no keys, just a visible, readable result. Teal, white, and pale gold palette. Scientific but accessible, infographic style.
