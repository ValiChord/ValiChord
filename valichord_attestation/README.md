# Moved: valichord-attestation now has its own repository

**→ [github.com/ValiChord/valichord-attestation](https://github.com/ValiChord/valichord-attestation)**

On 2026-10-19 the attestation library and format moved out of this repository, with its full
history, so that this one is only about ValiChord itself.

- **ValiChord** (this repository) is a commit-reveal reproducibility protocol on Holochain:
  independent validators seal their results before anyone reveals.
- **valichord-attestation** is a separate project: an open format and Python library for attesting
  AI evaluation runs. It is meant to become one way to bring AI evaluation results into ValiChord,
  and is not yet connected to it.

Install it with `pip install valichord-attestation`.

Old links into this folder map one-to-one onto the new repository: `valichord_attestation/X` here
is `X` there.
