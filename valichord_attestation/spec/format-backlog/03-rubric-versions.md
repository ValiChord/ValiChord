# Backlog: prompt, evaluator and rubric versions

**Status:** Open. Additive.
**Raised by:** independently by the same three people as 02, same week.
**Related:** 02, 04.

## Problem

The text that defines what "correct" means is not in the bundle. Prompt template, evaluator
implementation, grading rubric — all can change between runs while `task_id` stays identical.
A rubric revision that tightens one criterion moves every score, and the bundle records the
movement as though the model changed.

## v2 position

Nothing. `task_id` names the task; nothing names the version of the thing doing the judging.
`repo_commit` and `harness_version` cover the harness but not the rubric, which frequently lives
outside the harness repository.

## Proposed direction

Optional version identifiers for prompt, evaluator and rubric. Hashes rather than semantic
versions would be self-verifying and avoid arguing about numbering, at the cost of being
unreadable to a human comparing two bundles by eye.

## Open questions

1. Hash, semantic version, or both? Both is the honest answer and the more cluttered one.
2. Where does the rubric text itself live? The format binds evidence rather than storing it, so
   probably a hash plus a location, but a rubric that becomes unreachable makes an old bundle
   unverifiable in a new way.
3. Same `content_hash` question as 02. A rubric change alters results, so it belongs inside.
