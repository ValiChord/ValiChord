### Can anyone else get the same result you did?

Usually there's no answer. A published result comes with a number, a method, and the author's word for it. Even a perfect record of the author's own work only establishes what *they* did — not whether an independent party would have found the same thing.

I build the infrastructure that answers it.

#### The project — [ValiChord](https://github.com/ValiChord/ValiChord)

A researcher seals a hash of their result before anyone examines it. Independent validators then reproduce the work **blind** — unable to see the researcher's answer, or each other's. Each seals their own verdict, and a reveal window opens only once everyone has committed, so every answer is fixed before any becomes visible. No last-mover advantage, because there's no last mover.

The outcome becomes a **Harmony Record** — the verdict, the level of agreement, and who took part — written to a public peer-to-peer network where nobody, including me, can alter it afterwards. Anyone can fetch it by URL without installing anything.

Three decisions I'd defend:

- **"Reproduced" means an independent party got the same result — not that the result is correct.** ValiChord doesn't adjudicate science; it answers a narrower question that can be checked.
- **Disagreement is an output, not a failure.** If validators split, that *is* the finding, and it's recorded as one. A system that can only report success isn't measuring anything.
- **Sensitive data never enters a shared network.** Researchers' data and validators' private assessments live in single-participant stores; only hashes cross the boundary. Structural, not a policy promise.

Built on Holochain: peer-to-peer and agent-centric, each participant holding their own signed record. Not a blockchain — no ledger, no mining, no tokens.

It runs end-to-end today on five independent nodes whose only channel is the network. 183 integration tests, a browser interface for all three roles, Apache-2.0, and a [public demo](https://valichord-demo.onrender.com/demo) you can run yourself.

#### Two things that came out of building it

**[valichord_attestation](https://github.com/ValiChord/ValiChord/tree/main/valichord_attestation)** — the intended client-side on-ramp: a researcher packages an evaluation run into a verifiable bundle, then submits it. So a claimed benchmark score can be checked without publishing the whole log. 537 tests, five adapters including lm-evaluation-harness and Inspect AI. Standalone Python today, not yet wired to the protocol.

**[polite-shrink](https://github.com/ValiChord/polite-shrink)** — ValiChord needs a network that keeps data safe as nodes join and leave, which led me into an open problem in Holochain's networking: how a node safely *reduces* what it stores without dropping the network below its redundancy target, with no coordinator and no consensus. A simulation harness, a TLA+ proof of the safety gate, and zero data loss across 1,248 configurations — flat even at 90% message loss. Independently reproduced by another developer. Offered against kitsune2's open [sharding issue](https://github.com/holochain/kitsune2/issues/160); the harness also surfaced a real liveness bug there, now an [open PR](https://github.com/holochain/kitsune2/pull/572) upstream.

#### Where this honestly stands

Phase 0. The protocol runs, the tests pass, the demo is live, the records are real. It also has no research users yet, validator assignment is manual, and reputation tracking is off in production. I'd rather you sponsored that than something dressed up.

#### What sponsorship changes

- **Keeping published records readable.** A record that can disappear was never tamper-evident. The live network is one machine on one provider, and its predecessor was reclaimed when a free trial expired — taking every record published before June with it, as I found when grant-application links died. Sponsorship puts it on a paid, redundant footing.
- **Keeping it independent.** A verification protocol funded by the institutions whose results it checks is compromised at the root. Many small sponsors is the only funding shape that avoids it, which makes sponsorship part of the design.
- **Letting validators run their own nodes.** Independence isn't real while every validator depends on infrastructure I run. Bootstrap and relay servers, then a desktop app, move the network onto theirs.
- **A demo anyone can run.** Seeing it work currently needs your own API key. Removing that step is the difference between reading about it and watching it happen.
- **Time.** No grant, no company. Everything above is Apache-2.0 and stays that way.
