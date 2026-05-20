# PiSessionAdapter — Implementation Plan

**Target:** `valichord_attestation/valichord_attestation/adapters/pi_session_adapter.py`

**Parallel:** `InspectAILogAdapter` for inspect_ai `.eval` files. Same pattern, different source format.

**Source format:** pi session v3 JSONL (`~/.pi/agent/sessions/--<path>--/<timestamp>_<uuid>.jsonl`)
Spec: https://github.com/earendil-works/pi/blob/main/packages/coding-agent/docs/session-format.md

---

## What the adapter does

Reads a pi coding agent session JSONL file and produces a `Bundle` that commits to:
- which model ran the session
- which task/project it was for
- aggregate performance metrics (turns, tokens, cost, tool error rate)
- a Merkle root over every session entry, enabling selective disclosure

The bundle travels alongside the session file when published to Hugging Face via `pi-share-hf`, giving any consumer a way to verify the published session is byte-for-byte unmodified.

---

## Field mapping

| Bundle field | Source | Notes |
|---|---|---|
| `model_id` | Last `AssistantMessage.provider + "/" + AssistantMessage.model` | Walk entries in tree order; use the final model seen. On model-switch entries, use the switched-to model. |
| `task_id` | `session_info.name` if present; else `cwd` basename + `"/"` + session UUID prefix (8 chars) | `session_info` is the last `type: "session_info"` entry. Falls back to cwd so headless sessions still have a stable task_id. |
| `generated_at` | `SessionHeader.timestamp` | ISO 8601; first line of file. |
| `repo_commit` | `subprocess.run(["git", "rev-parse", "HEAD"], cwd=session_cwd)` | Optional, best-effort. Silently `None` if cwd is not a git repo or git is unavailable. |
| `metrics` | See table below | Aggregated from all `type: "message"` entries. |
| `outputs_merkle_root` | Merkle over all non-header entries | Each leaf = one entry dict (see "Merkle leaf format" below). |
| `samples_total` | Total entry count (non-header) | Explicit, for sample-omission detection. |
| `samples_completed` | Entries that are not error tool results | `isError: true` ToolResult entries count as failed; everything else counts as completed. |
| `meta` | `harness_version`, `session_file`, `cwd`, `session_id` | Provenance only; goes in `Bundle.meta` so it's in `bundle_hash` but excluded from `content_hash`. |

---

## Metrics

All extracted from `type: "message"` entries across the active branch (root → leaf path).

| Metric key | Value | Type |
|---|---|---|
| `total_turns` | Count of `AssistantMessage` entries | int as float |
| `total_tool_calls` | Count of `toolCall` content blocks across all assistant messages | int as float |
| `tool_error_rate` | `error_tool_results / total_tool_results` (0.0 if no tool results) | float 0–1 |
| `total_input_tokens` | Sum of `AssistantMessage.usage.input` | int as float |
| `total_output_tokens` | Sum of `AssistantMessage.usage.output` | int as float |
| `total_cost_usd` | Sum of `AssistantMessage.usage.cost.total` | float |
| `compaction_count` | Count of `type: "compaction"` entries | int as float |
| `final_stop_reason` | Encoded value from last `AssistantMessage.stopReason` | See encoding below |

**`final_stop_reason` encoding** (must be float for `Metric.value`):
```
"stop"     → 0.0
"toolUse"  → 1.0
"length"   → 2.0
"error"    → 3.0
"aborted"  → 4.0
unknown    → -1.0
```

Include as a metric with a `filter` field noting the string value in `meta` to allow
human-readable recovery. Alternatively: store as a string in `meta` and omit from
metrics if it creates too much confusion. **Decision needed at implementation time.**

---

## Merkle leaf format

Each non-header entry in the active branch becomes one leaf:

```python
{
    "id":        str,   # entry id (8-char hex)
    "type":      str,   # entry type string
    "timestamp": str,   # ISO timestamp
    "content":   dict,  # the entry dict minus id/parentId/timestamp (role-specific data)
}
```

`content` is the entry stripped of tree-structure fields (`id`, `parentId`, `timestamp`) — only the semantic payload. This makes the leaf stable against tree restructuring (branching) while still committing to the full message content.

For `type: "message"` entries, `content` includes the full `message` object (role, content blocks, provider, model, usage, stopReason). Tool call arguments and results are included — these are the semantically meaningful parts.

**Why all entries, not just assistant messages:**
Selective disclosure of a tool call + its result requires both entries to be in the tree. A verifier challenging "show me what happened at step 7" gets both the call and the result.

---

## Branch resolution

Pi sessions are trees (v2+). The adapter must walk the active branch:
`root → leaf` path, using the same logic as `buildSessionContext()` in the pi source.

**Algorithm:**
1. Parse all lines into a `dict[id → entry]` plus the header.
2. Find the current leaf: last `type: "leaf"` entry's `targetId`; if absent, the entry with no children (only child in a linear session).
3. Walk `parentId` links from leaf to root; collect entries in reverse; reverse to get root→leaf order.
4. If a `compaction` entry is on the path, entries before `firstKeptEntryId` are excluded (same as `buildSessionContext()`).

v1 sessions (no `id`/`parentId`) are linear — treat as a single branch in insertion order.

---

## Adapter interface

```python
class PiSessionAdapter(AdapterBase):
    """Adapter: pi coding agent session JSONL → Valichord attestation Bundle.

    Reads a pi session v3 JSONL file (or accepts a pre-parsed list of entry dicts)
    and produces a Bundle committing to the model, task, metrics, and per-entry
    content of the session.

    Field mapping: see docs/PISESSION_ADAPTER_PLAN.md.
    """

    def to_bundle(
        self,
        session: "str | Path | list[dict]",
        *,
        task_id_override: str | None = None,
        repo_commit: str | None = None,
        meta_extras: dict | None = None,
    ) -> Bundle:
        """Convert a pi session to a Valichord attestation Bundle.

        Args:
            session: Path to a .jsonl session file (str or Path), or a
                     pre-parsed list of entry dicts (for testing without file I/O).
            task_id_override: Override the inferred task_id.
            repo_commit: Git commit SHA of the project cwd at session time.
                         When absent, auto-extracted via `git rev-parse HEAD`
                         in the session's cwd if available.
            meta_extras: Extra key/value pairs merged into Bundle.meta.

        Returns:
            A Valichord Bundle ready for canonicalisation and hashing.

        Raises:
            ValueError: if no assistant messages are found, model_id is empty,
                        or the entry list is empty.
            MalformedBundleError: propagated from build_bundle().
        """
```

No optional dependency — the adapter only uses stdlib (`json`, `pathlib`, `subprocess`).
The pre-parsed list path makes it fully testable without fixture files.

---

## Test strategy

Mirror the `InspectAILogAdapter` test structure at:
`valichord_attestation/tests/test_pi_session_adapter.py`

### Fixture

A minimal synthetic session dict list (no file I/O needed for most tests):

```python
MINIMAL_SESSION = [
    {"type": "session", "version": 3, "id": "sess-uuid", "timestamp": "2026-05-19T10:00:00Z", "cwd": "/proj"},
    {"type": "message", "id": "aa000001", "parentId": None,     "timestamp": "...", "message": {"role": "user",      "content": "fix the bug"}},
    {"type": "message", "id": "aa000002", "parentId": "aa000001", "timestamp": "...", "message": {"role": "assistant", "provider": "anthropic", "model": "claude-sonnet-4-6", "content": [{"type": "toolCall", "id": "tc1", "name": "bash", "arguments": {"command": "pytest"}}], "usage": {"input": 100, "output": 50, "cacheRead": 0, "cacheWrite": 0, "totalTokens": 150, "cost": {"input": 0.001, "output": 0.002, "cacheRead": 0, "cacheWrite": 0, "total": 0.003}}, "stopReason": "toolUse", "timestamp": 1716112800000}},
    {"type": "message", "id": "aa000003", "parentId": "aa000002", "timestamp": "...", "message": {"role": "toolResult", "toolCallId": "tc1", "toolName": "bash", "content": [{"type": "text", "text": "3 passed"}], "isError": False, "timestamp": 1716112801000}},
    {"type": "message", "id": "aa000004", "parentId": "aa000003", "timestamp": "...", "message": {"role": "assistant", "provider": "anthropic", "model": "claude-sonnet-4-6", "content": [{"type": "text", "text": "All tests pass."}], "usage": {"input": 200, "output": 30, "cacheRead": 50, "cacheWrite": 0, "totalTokens": 280, "cost": {"input": 0.002, "output": 0.001, "cacheRead": 0.0005, "cacheWrite": 0, "total": 0.0035}}, "stopReason": "stop", "timestamp": 1716112802000}},
]
```

### Test cases

1. **Happy path** — `to_bundle(MINIMAL_SESSION)` produces a valid Bundle with correct `model_id`, `task_id`, all expected metrics, non-empty `outputs_merkle_root`.
2. **model_id** — last assistant model wins; model_change entry overrides.
3. **task_id inference** — session_info name used when present; cwd basename + uuid prefix used as fallback.
4. **task_id_override** — explicit override wins over both.
5. **metrics correctness** — verify each metric value against hand-calculated expected from fixture.
6. **final_stop_reason** — `"stop"` → `0.0`, `"toolUse"` → `1.0`, unknown → `-1.0`.
7. **tool_error_rate** — fixture with one error and two success tool results → `0.333...`.
8. **Merkle root non-empty** — `outputs_merkle_root` is a 64-char hex string.
9. **Merkle faithfulness** — `verify_faithfulness(bundle)` passes (round-trip check).
10. **samples_total** — equals total non-header entries; `samples_completed` excludes `isError: true` tool results.
11. **compaction excluded entries** — entries before `firstKeptEntryId` are excluded from branch and Merkle.
12. **branch resolution** — session with branching; only active branch entries included.
13. **v1 session** — no id/parentId; linear order used.
14. **no assistant messages** — raises `ValueError`.
15. **empty session** — raises `ValueError`.
16. **file path** — `to_bundle(path_to_tmpfile)` round-trips correctly.
17. **repo_commit auto-extract** — mocked `subprocess.run` returns a commit hash; verified in meta.
18. **repo_commit not a git repo** — `subprocess.run` fails; `repo_commit` is `None`, no exception.
19. **meta_extras** — merged into `Bundle.meta` last.
20. **bundle_hash vs content_hash** — `bundle_hash != content_hash` when meta is non-empty; equal when meta is absent.

Target: 100% line coverage on `pi_session_adapter.py`.

---

## Package wiring

1. Add `PiSessionAdapter` to `valichord_attestation/adapters/__init__.py`.
2. Export from `valichord_attestation/__init__.py` alongside `InspectAILogAdapter`.
3. No new dependencies — stdlib only.
4. No optional dependency group needed.

---

## Example usage (to include in docstring / examples/)

```python
from valichord_attestation.adapters import PiSessionAdapter
from valichord_attestation import hash_bundle, content_hash

adapter = PiSessionAdapter()
bundle = adapter.to_bundle(
    "~/.pi/agent/sessions/--home-me-myproject--/2026-05-19T10:00:00_abc123.jsonl",
    task_id_override="myproject/fix-auth-bug",
)

print(bundle.bundle_hash)   # publish this alongside the session on HF
print(bundle.content_hash)  # scientific equivalence hash (excludes meta)
```

---

## pi-share-hf integration note (out of scope for the adapter itself)

A future `pi-share-hf bundle` step would:
1. Run `PiSessionAdapter().to_bundle(session_path)` on each uploadable session.
2. Write `bundle.json` alongside the session file.
3. Include `bundle_hash` as a HF dataset metadata field per row.

This is a separate tool change that requires the pi-share-hf maintainer to adopt it.
Do not attempt to upstream this until there is a working demo and Discord contact has been made first.

---

## What is NOT in scope

- Parsing pi-chat (Slack bot) sessions — different format, defer.
- Multi-session aggregation (e.g. all sessions for a project) — defer.
- Real-time streaming attestation (attesting a live session as it runs) — Phase 2.
- Verifying that a session's bash commands actually produced the claimed outputs — outside ValiChord's scope (that is what the Holochain commit-reveal protocol is for, applied to the task outcome rather than the transcript).

---

*Written: 2026-05-19. Continue implementation in a fresh session; start from test fixtures, then adapter, then wiring — same sequence as InspectAILogAdapter.*
