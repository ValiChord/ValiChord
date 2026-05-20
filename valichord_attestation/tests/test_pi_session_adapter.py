"""Tests for PiSessionAdapter.

All 20 cases from docs/PISESSION_ADAPTER_PLAN.md, plus helpers.
Most tests use pre-parsed list fixtures (no file I/O) for speed and
isolation; file-path and subprocess tests use monkeypatch / tmp_path.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from valichord_attestation.adapters.base import AdapterBase
from valichord_attestation.adapters.pi_session_adapter import (
    PiSessionAdapter,
    _collect_metrics,
    _entry_to_leaf_dict,
    _extract_model_id,
    _extract_task_id,
    _git_head,
    _resolve_branch,
    _STOP_REASON_ENCODING,
)
from valichord_attestation.bundle import Bundle
from valichord_attestation.merkle import merkle_proof, verify_faithfulness

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

HEADER: dict = {
    "type": "session",
    "version": 3,
    "id": "sess-uuid",
    "timestamp": "2026-05-19T10:00:00Z",
    "cwd": "/proj",
}

# Minimal four-entry session: user → assistant (toolUse) → toolResult → assistant (stop)
MINIMAL_SESSION: list[dict] = [
    HEADER,
    {
        "type": "message",
        "id": "aa000001",
        "parentId": None,
        "timestamp": "2026-05-19T10:00:01Z",
        "message": {"role": "user", "content": "fix the bug"},
    },
    {
        "type": "message",
        "id": "aa000002",
        "parentId": "aa000001",
        "timestamp": "2026-05-19T10:00:02Z",
        "message": {
            "role": "assistant",
            "provider": "anthropic",
            "model": "claude-sonnet-4-6",
            "content": [
                {"type": "toolCall", "id": "tc1", "name": "bash", "arguments": {"command": "pytest"}},
            ],
            "usage": {
                "input": 100,
                "output": 50,
                "cacheRead": 0,
                "cacheWrite": 0,
                "totalTokens": 150,
                "cost": {"input": 0.001, "output": 0.002, "cacheRead": 0, "cacheWrite": 0, "total": 0.003},
            },
            "stopReason": "toolUse",
            "timestamp": 1716112800000,
        },
    },
    {
        "type": "message",
        "id": "aa000003",
        "parentId": "aa000002",
        "timestamp": "2026-05-19T10:00:03Z",
        "message": {
            "role": "toolResult",
            "toolCallId": "tc1",
            "toolName": "bash",
            "content": [{"type": "text", "text": "3 passed"}],
            "isError": False,
            "timestamp": 1716112801000,
        },
    },
    {
        "type": "message",
        "id": "aa000004",
        "parentId": "aa000003",
        "timestamp": "2026-05-19T10:00:04Z",
        "message": {
            "role": "assistant",
            "provider": "anthropic",
            "model": "claude-sonnet-4-6",
            "content": [{"type": "text", "text": "All tests pass."}],
            "usage": {
                "input": 200,
                "output": 30,
                "cacheRead": 50,
                "cacheWrite": 0,
                "totalTokens": 280,
                "cost": {"input": 0.002, "output": 0.001, "cacheRead": 0.0005, "cacheWrite": 0, "total": 0.0035},
            },
            "stopReason": "stop",
            "timestamp": 1716112802000,
        },
    },
]

ADAPTER = PiSessionAdapter()


# ---------------------------------------------------------------------------
# 1. Happy path
# ---------------------------------------------------------------------------

def test_happy_path_returns_bundle():
    bundle = ADAPTER.to_bundle(MINIMAL_SESSION)
    assert isinstance(bundle, Bundle)


def test_happy_path_model_id():
    bundle = ADAPTER.to_bundle(MINIMAL_SESSION)
    assert bundle.model_id == "anthropic/claude-sonnet-4-6"


def test_happy_path_task_id_fallback():
    # No session_info → cwd basename + 8-char uuid prefix
    bundle = ADAPTER.to_bundle(MINIMAL_SESSION)
    assert bundle.task_id == "proj/sess-uui"


def test_happy_path_merkle_root_64hex():
    bundle = ADAPTER.to_bundle(MINIMAL_SESSION)
    assert len(bundle.outputs_merkle_root) == 64
    assert all(c in "0123456789abcdef" for c in bundle.outputs_merkle_root)


def test_happy_path_all_eight_metrics_present():
    bundle = ADAPTER.to_bundle(MINIMAL_SESSION)
    keys = {m.key for m in bundle.metrics}
    expected = {
        "total_turns", "total_tool_calls", "tool_error_rate",
        "total_input_tokens", "total_output_tokens", "total_cost_usd",
        "compaction_count", "final_stop_reason",
    }
    assert expected == keys


def test_is_subclass_of_base():
    assert issubclass(PiSessionAdapter, AdapterBase)


# ---------------------------------------------------------------------------
# 2. model_id — last assistant wins; model_change overrides
# ---------------------------------------------------------------------------

def test_model_id_last_assistant_wins():
    session = [
        HEADER,
        {**MINIMAL_SESSION[1]},  # user
        {
            "type": "message", "id": "b1", "parentId": "aa000001",
            "timestamp": "2026-05-19T10:00:02Z",
            "message": {
                "role": "assistant", "provider": "openai", "model": "gpt-4o",
                "content": [], "usage": {"input": 10, "output": 5, "cost": {"total": 0.001}},
                "stopReason": "stop",
            },
        },
        {
            "type": "message", "id": "b2", "parentId": "b1",
            "timestamp": "2026-05-19T10:00:03Z",
            "message": {
                "role": "assistant", "provider": "anthropic", "model": "claude-opus-4-7",
                "content": [], "usage": {"input": 20, "output": 8, "cost": {"total": 0.002}},
                "stopReason": "stop",
            },
        },
    ]
    bundle = ADAPTER.to_bundle(session)
    assert bundle.model_id == "anthropic/claude-opus-4-7"


def test_model_change_entry_overrides_assistant():
    session = [
        HEADER,
        {**MINIMAL_SESSION[1]},  # user
        {
            "type": "message", "id": "c1", "parentId": "aa000001",
            "timestamp": "2026-05-19T10:00:02Z",
            "message": {
                "role": "assistant", "provider": "anthropic", "model": "claude-sonnet-4-6",
                "content": [], "usage": {"input": 10, "output": 5, "cost": {"total": 0.001}},
                "stopReason": "stop",
            },
        },
        {
            "type": "model_change", "id": "c2", "parentId": "c1",
            "timestamp": "2026-05-19T10:00:03Z",
            "provider": "openai", "modelId": "o3",
        },
    ]
    bundle = ADAPTER.to_bundle(session)
    assert bundle.model_id == "openai/o3"


# ---------------------------------------------------------------------------
# 3. task_id inference
# ---------------------------------------------------------------------------

def test_task_id_from_session_info_name():
    session = list(MINIMAL_SESSION) + [
        {
            "type": "session_info", "id": "si1", "parentId": "aa000004",
            "timestamp": "2026-05-19T10:00:05Z",
            "name": "Fix auth bug",
        },
    ]
    bundle = ADAPTER.to_bundle(session)
    assert bundle.task_id == "Fix auth bug"


def test_task_id_last_session_info_wins():
    session = list(MINIMAL_SESSION) + [
        {
            "type": "session_info", "id": "si1", "parentId": "aa000004",
            "timestamp": "2026-05-19T10:00:05Z",
            "name": "First name",
        },
        {
            "type": "session_info", "id": "si2", "parentId": "si1",
            "timestamp": "2026-05-19T10:00:06Z",
            "name": "Final name",
        },
    ]
    bundle = ADAPTER.to_bundle(session)
    assert bundle.task_id == "Final name"


def test_task_id_fallback_cwd_basename_plus_uuid_prefix():
    bundle = ADAPTER.to_bundle(MINIMAL_SESSION)
    assert bundle.task_id == "proj/sess-uui"


def test_task_id_cwd_root_falls_back_to_session():
    header_root = {**HEADER, "cwd": "/", "id": "abcdef12345678"}
    session = [header_root] + MINIMAL_SESSION[1:]
    bundle = ADAPTER.to_bundle(session)
    # Path("/").name == "" → fallback basename "session"
    assert bundle.task_id == "session/abcdef12"


# ---------------------------------------------------------------------------
# 4. task_id_override
# ---------------------------------------------------------------------------

def test_task_id_override_beats_session_info():
    session = list(MINIMAL_SESSION) + [
        {
            "type": "session_info", "id": "si1", "parentId": "aa000004",
            "timestamp": "2026-05-19T10:00:05Z",
            "name": "Some name",
        },
    ]
    bundle = ADAPTER.to_bundle(session, task_id_override="my-override")
    assert bundle.task_id == "my-override"


def test_task_id_override_beats_fallback():
    bundle = ADAPTER.to_bundle(MINIMAL_SESSION, task_id_override="proj/exact-task")
    assert bundle.task_id == "proj/exact-task"


# ---------------------------------------------------------------------------
# 5. Metrics correctness against MINIMAL_SESSION
# ---------------------------------------------------------------------------

def _metric(bundle: Bundle, key: str) -> float:
    return next(m.value for m in bundle.metrics if m.key == key)


def test_metric_total_turns():
    bundle = ADAPTER.to_bundle(MINIMAL_SESSION)
    assert _metric(bundle, "total_turns") == 2.0


def test_metric_total_tool_calls():
    bundle = ADAPTER.to_bundle(MINIMAL_SESSION)
    assert _metric(bundle, "total_tool_calls") == 1.0


def test_metric_tool_error_rate_zero():
    bundle = ADAPTER.to_bundle(MINIMAL_SESSION)
    assert _metric(bundle, "tool_error_rate") == 0.0


def test_metric_total_input_tokens():
    bundle = ADAPTER.to_bundle(MINIMAL_SESSION)
    assert abs(_metric(bundle, "total_input_tokens") - 300.0) < 1e-9


def test_metric_total_output_tokens():
    bundle = ADAPTER.to_bundle(MINIMAL_SESSION)
    assert abs(_metric(bundle, "total_output_tokens") - 80.0) < 1e-9


def test_metric_total_cost_usd():
    bundle = ADAPTER.to_bundle(MINIMAL_SESSION)
    assert abs(_metric(bundle, "total_cost_usd") - 0.0065) < 1e-6


def test_metric_compaction_count_zero():
    bundle = ADAPTER.to_bundle(MINIMAL_SESSION)
    assert _metric(bundle, "compaction_count") == 0.0


# ---------------------------------------------------------------------------
# 6. final_stop_reason encoding
# ---------------------------------------------------------------------------

def test_final_stop_reason_stop():
    bundle = ADAPTER.to_bundle(MINIMAL_SESSION)
    assert _metric(bundle, "final_stop_reason") == 0.0


def test_final_stop_reason_tooluse():
    # Session ending on toolUse (remove last assistant entry, end on aa000002)
    session = MINIMAL_SESSION[:3]  # header + user + assistant(toolUse)
    bundle = ADAPTER.to_bundle(session)
    assert _metric(bundle, "final_stop_reason") == 1.0


def test_final_stop_reason_unknown():
    session = [
        HEADER,
        {**MINIMAL_SESSION[1]},
        {
            "type": "message", "id": "x1", "parentId": "aa000001",
            "timestamp": "2026-05-19T10:00:02Z",
            "message": {
                "role": "assistant", "provider": "anthropic", "model": "claude-haiku-4-5",
                "content": [], "usage": {"input": 5, "output": 2, "cost": {"total": 0.0}},
                "stopReason": "newReasonWeNeverSeen",
            },
        },
    ]
    bundle = ADAPTER.to_bundle(session)
    assert _metric(bundle, "final_stop_reason") == -1.0


def test_final_stop_reason_str_in_meta():
    bundle = ADAPTER.to_bundle(MINIMAL_SESSION)
    assert bundle.meta is not None
    assert bundle.meta.get("final_stop_reason_str") == "stop"


# ---------------------------------------------------------------------------
# 7. tool_error_rate — 1 error out of 3 tool results
# ---------------------------------------------------------------------------

def test_tool_error_rate_one_third():
    session = [
        HEADER,
        {**MINIMAL_SESSION[1]},  # user
        {
            "type": "message", "id": "e1", "parentId": "aa000001",
            "timestamp": "2026-05-19T10:00:02Z",
            "message": {
                "role": "assistant", "provider": "anthropic", "model": "claude-sonnet-4-6",
                "content": [
                    {"type": "toolCall", "id": "tc1", "name": "read", "arguments": {}},
                    {"type": "toolCall", "id": "tc2", "name": "bash", "arguments": {}},
                    {"type": "toolCall", "id": "tc3", "name": "write", "arguments": {}},
                ],
                "usage": {"input": 10, "output": 5, "cost": {"total": 0.001}},
                "stopReason": "toolUse",
            },
        },
        {
            "type": "message", "id": "e2", "parentId": "e1",
            "timestamp": "2026-05-19T10:00:03Z",
            "message": {
                "role": "toolResult", "toolCallId": "tc1", "toolName": "read",
                "content": [], "isError": False,
            },
        },
        {
            "type": "message", "id": "e3", "parentId": "e2",
            "timestamp": "2026-05-19T10:00:04Z",
            "message": {
                "role": "toolResult", "toolCallId": "tc2", "toolName": "bash",
                "content": [], "isError": True,
            },
        },
        {
            "type": "message", "id": "e4", "parentId": "e3",
            "timestamp": "2026-05-19T10:00:05Z",
            "message": {
                "role": "toolResult", "toolCallId": "tc3", "toolName": "write",
                "content": [], "isError": False,
            },
        },
        {
            "type": "message", "id": "e5", "parentId": "e4",
            "timestamp": "2026-05-19T10:00:06Z",
            "message": {
                "role": "assistant", "provider": "anthropic", "model": "claude-sonnet-4-6",
                "content": [], "usage": {"input": 20, "output": 5, "cost": {"total": 0.002}},
                "stopReason": "stop",
            },
        },
    ]
    bundle = ADAPTER.to_bundle(session)
    rate = _metric(bundle, "tool_error_rate")
    # pre_round() stores 6 dp, so compare at that precision
    assert round(rate, 6) == round(1 / 3, 6)


# ---------------------------------------------------------------------------
# 8. Merkle root non-empty
# ---------------------------------------------------------------------------

def test_merkle_root_is_64_hex_chars():
    bundle = ADAPTER.to_bundle(MINIMAL_SESSION)
    root = bundle.outputs_merkle_root
    assert len(root) == 64
    assert all(c in "0123456789abcdef" for c in root)


# ---------------------------------------------------------------------------
# 9. Merkle faithfulness — proof round-trip
# ---------------------------------------------------------------------------

def test_merkle_faithfulness():
    bundle = ADAPTER.to_bundle(MINIMAL_SESSION)
    header = MINIMAL_SESSION[0]
    entries = MINIMAL_SESSION[1:]
    branch = _resolve_branch(header, entries)
    leaf_dicts = [_entry_to_leaf_dict(e) for e in branch]
    # Verify proof for index 0 and the last index
    for idx in (0, len(leaf_dicts) - 1):
        proof = merkle_proof(leaf_dicts, idx)
        assert verify_faithfulness(bundle.outputs_merkle_root, idx, leaf_dicts[idx], proof)


# ---------------------------------------------------------------------------
# 10. samples_total and samples_completed
# ---------------------------------------------------------------------------

def test_samples_total_equals_branch_length():
    bundle = ADAPTER.to_bundle(MINIMAL_SESSION)
    # 4 non-header entries in MINIMAL_SESSION, all on the branch
    assert bundle.samples_total == 4
    assert bundle.samples_completed == 4


def test_samples_total_reflects_full_branch():
    session = [HEADER] + [
        {
            "type": "message",
            "id": f"m{i}",
            "parentId": f"m{i - 1}" if i > 0 else None,
            "timestamp": f"2026-05-19T10:00:0{i}Z",
            "message": (
                {
                    "role": "assistant",
                    "provider": "anthropic",
                    "model": "claude-sonnet-4-6",
                    "content": [],
                    "usage": {"input": 1, "output": 1, "cost": {"total": 0.0}},
                    "stopReason": "stop",
                }
                if i % 2 == 1
                else {"role": "user", "content": "hi"}
            ),
        }
        for i in range(6)
    ]
    bundle = ADAPTER.to_bundle(session)
    assert bundle.samples_total == 6
    assert bundle.samples_completed == 6


# ---------------------------------------------------------------------------
# 11. Compaction — entries before firstKeptEntryId excluded
# ---------------------------------------------------------------------------

def test_compaction_excludes_pre_kept_entries():
    # Branch: e1 → e2 → compaction(firstKeptEntryId=e2) → e3 → e4
    # e1 should be excluded; e2, compaction, e3, e4 kept
    session = [
        HEADER,
        {
            "type": "message", "id": "e1", "parentId": None,
            "timestamp": "2026-05-19T10:00:01Z",
            "message": {"role": "user", "content": "old message (should be excluded)"},
        },
        {
            "type": "message", "id": "e2", "parentId": "e1",
            "timestamp": "2026-05-19T10:00:02Z",
            "message": {"role": "user", "content": "kept message"},
        },
        {
            "type": "compaction", "id": "comp1", "parentId": "e2",
            "timestamp": "2026-05-19T10:00:03Z",
            "summary": "Summary of old conversation",
            "firstKeptEntryId": "e2",
            "tokensBefore": 5000,
        },
        {
            "type": "message", "id": "e3", "parentId": "comp1",
            "timestamp": "2026-05-19T10:00:04Z",
            "message": {
                "role": "assistant", "provider": "anthropic", "model": "claude-sonnet-4-6",
                "content": [], "usage": {"input": 10, "output": 5, "cost": {"total": 0.001}},
                "stopReason": "stop",
            },
        },
    ]
    bundle = ADAPTER.to_bundle(session)
    # Branch should be [e2, comp1, e3] — e1 excluded; 3 entries
    assert bundle.samples_total == 3


def test_compaction_metric_counted():
    session = [
        HEADER,
        {
            "type": "message", "id": "e1", "parentId": None,
            "timestamp": "2026-05-19T10:00:01Z",
            "message": {"role": "user", "content": "hi"},
        },
        {
            "type": "compaction", "id": "comp1", "parentId": "e1",
            "timestamp": "2026-05-19T10:00:02Z",
            "summary": "Summary",
            "firstKeptEntryId": "e1",
            "tokensBefore": 1000,
        },
        {
            "type": "message", "id": "e2", "parentId": "comp1",
            "timestamp": "2026-05-19T10:00:03Z",
            "message": {
                "role": "assistant", "provider": "anthropic", "model": "claude-sonnet-4-6",
                "content": [], "usage": {"input": 5, "output": 2, "cost": {"total": 0.0}},
                "stopReason": "stop",
            },
        },
    ]
    bundle = ADAPTER.to_bundle(session)
    assert _metric(bundle, "compaction_count") == 1.0


# ---------------------------------------------------------------------------
# 12. Branch resolution — only active branch included
# ---------------------------------------------------------------------------

def test_branch_resolution_excludes_dead_branch():
    # Tree: e1 → e2 → e3 (dead branch)
    #              ↘ e4 → e5 (active branch, leaf=e5)
    session = [
        HEADER,
        {
            "type": "message", "id": "e1", "parentId": None,
            "timestamp": "2026-05-19T10:00:01Z",
            "message": {"role": "user", "content": "start"},
        },
        {
            "type": "message", "id": "e2", "parentId": "e1",
            "timestamp": "2026-05-19T10:00:02Z",
            "message": {"role": "user", "content": "branch point"},
        },
        {
            "type": "message", "id": "e3", "parentId": "e2",
            "timestamp": "2026-05-19T10:00:03Z",
            "message": {"role": "user", "content": "dead branch — should NOT appear"},
        },
        # Active branch starts from e2
        {
            "type": "message", "id": "e4", "parentId": "e2",
            "timestamp": "2026-05-19T10:00:04Z",
            "message": {
                "role": "assistant", "provider": "anthropic", "model": "claude-sonnet-4-6",
                "content": [], "usage": {"input": 10, "output": 5, "cost": {"total": 0.001}},
                "stopReason": "stop",
            },
        },
        {
            "type": "message", "id": "e5", "parentId": "e4",
            "timestamp": "2026-05-19T10:00:05Z",
            "message": {"role": "user", "content": "active branch end"},
        },
    ]
    branch = _resolve_branch(HEADER, session[1:])
    branch_ids = {e["id"] for e in branch}
    # e3 is on the dead branch and must not appear
    assert "e3" not in branch_ids
    # e1, e2, e4, e5 are on the active branch
    assert {"e1", "e2", "e4", "e5"} == branch_ids


# ---------------------------------------------------------------------------
# 13. v1 session — linear order
# ---------------------------------------------------------------------------

def test_v1_session_linear_order():
    v1_header = {"type": "session", "cwd": "/old", "id": "old-session-id", "timestamp": "2025-01-01T00:00:00Z"}
    # v1 entries: no id/parentId, no version in header
    v1_entries = [
        {"type": "message", "timestamp": "2025-01-01T00:00:01Z", "message": {"role": "user", "content": "hello"}},
        {
            "type": "message", "timestamp": "2025-01-01T00:00:02Z",
            "message": {
                "role": "assistant", "provider": "anthropic", "model": "claude-3-5-sonnet",
                "content": [], "usage": {"input": 10, "output": 5, "cost": {"total": 0.001}},
                "stopReason": "stop",
            },
        },
    ]
    session = [v1_header] + v1_entries
    bundle = ADAPTER.to_bundle(session)
    assert isinstance(bundle, Bundle)
    assert bundle.samples_total == 2


def test_v1_session_detected_by_missing_version():
    # Explicit version=1
    v1_header = {**HEADER, "version": 1}
    session = [
        v1_header,
        # Entries do have id/parentId but version says v1
        {
            "type": "message", "id": "x1", "parentId": None,
            "timestamp": "2026-05-19T10:00:01Z",
            "message": {
                "role": "assistant", "provider": "anthropic", "model": "claude-sonnet-4-6",
                "content": [], "usage": {"input": 5, "output": 2, "cost": {"total": 0.001}},
                "stopReason": "stop",
            },
        },
    ]
    bundle = ADAPTER.to_bundle(session)
    assert bundle.samples_total == 1


# ---------------------------------------------------------------------------
# 14. No assistant messages → ValueError
# ---------------------------------------------------------------------------

def test_no_assistant_messages_raises():
    session = [
        HEADER,
        {
            "type": "message", "id": "u1", "parentId": None,
            "timestamp": "2026-05-19T10:00:01Z",
            "message": {"role": "user", "content": "hello?"},
        },
    ]
    with pytest.raises(ValueError, match="No assistant messages"):
        ADAPTER.to_bundle(session)


# ---------------------------------------------------------------------------
# 15. Empty session → ValueError
# ---------------------------------------------------------------------------

def test_empty_list_raises():
    with pytest.raises(ValueError, match="empty"):
        ADAPTER.to_bundle([])


def test_header_only_raises():
    with pytest.raises(ValueError, match="no non-header entries"):
        ADAPTER.to_bundle([HEADER])


def test_wrong_first_entry_type_raises():
    with pytest.raises(ValueError, match="session header"):
        ADAPTER.to_bundle([{"type": "message", "id": "x"}])


# ---------------------------------------------------------------------------
# 16. File path — round-trip via tmpfile
# ---------------------------------------------------------------------------

def test_file_path_roundtrip(tmp_path: Path):
    session_file = tmp_path / "test_session.jsonl"
    lines = [json.dumps(entry) for entry in MINIMAL_SESSION]
    session_file.write_text("\n".join(lines), encoding="utf-8")

    bundle_from_file = ADAPTER.to_bundle(session_file)
    bundle_from_list = ADAPTER.to_bundle(MINIMAL_SESSION)

    # content_hash must match (same data, meta differs by session_file path)
    from valichord_attestation.canonical import content_hash
    assert content_hash(bundle_from_file) == content_hash(bundle_from_list)


def test_file_path_str_accepted(tmp_path: Path):
    session_file = tmp_path / "test_session.jsonl"
    session_file.write_text(
        "\n".join(json.dumps(e) for e in MINIMAL_SESSION), encoding="utf-8"
    )
    bundle = ADAPTER.to_bundle(str(session_file))
    assert isinstance(bundle, Bundle)
    assert bundle.meta is not None
    assert "session_file" in bundle.meta


def test_file_path_has_session_file_in_meta(tmp_path: Path):
    session_file = tmp_path / "sess.jsonl"
    session_file.write_text(
        "\n".join(json.dumps(e) for e in MINIMAL_SESSION), encoding="utf-8"
    )
    bundle = ADAPTER.to_bundle(session_file)
    assert bundle.meta is not None
    assert bundle.meta["session_file"] == str(session_file)


def test_list_input_has_no_session_file_in_meta():
    bundle = ADAPTER.to_bundle(MINIMAL_SESSION)
    assert bundle.meta is None or "session_file" not in (bundle.meta or {})


# ---------------------------------------------------------------------------
# 17. repo_commit auto-extract (mocked subprocess)
# ---------------------------------------------------------------------------

def test_repo_commit_auto_extracted(monkeypatch):
    import valichord_attestation.adapters.pi_session_adapter as mod

    fake_sha = "a" * 40
    monkeypatch.setattr(mod, "_git_head", lambda _: fake_sha)
    bundle = ADAPTER.to_bundle(MINIMAL_SESSION)
    assert bundle.repo_commit == fake_sha


def test_repo_commit_explicit_overrides_auto(monkeypatch):
    import valichord_attestation.adapters.pi_session_adapter as mod

    monkeypatch.setattr(mod, "_git_head", lambda _: "auto-extracted-sha")
    explicit = "explicit-sha-0000"
    bundle = ADAPTER.to_bundle(MINIMAL_SESSION, repo_commit=explicit)
    assert bundle.repo_commit == explicit


# ---------------------------------------------------------------------------
# 18. repo_commit — not a git repo → None, no exception
# ---------------------------------------------------------------------------

def test_repo_commit_none_when_not_git_repo(monkeypatch):
    import valichord_attestation.adapters.pi_session_adapter as mod

    monkeypatch.setattr(mod, "_git_head", lambda _: None)
    bundle = ADAPTER.to_bundle(MINIMAL_SESSION)
    assert bundle.repo_commit is None


def test_git_head_returns_none_on_subprocess_error(tmp_path):
    # Actually call _git_head on a directory that is not a git repo
    not_a_repo = str(tmp_path)
    result = _git_head(not_a_repo)
    assert result is None


def test_git_head_returns_none_for_empty_cwd():
    assert _git_head("") is None


# ---------------------------------------------------------------------------
# 19. meta_extras merged last
# ---------------------------------------------------------------------------

def test_meta_extras_merged():
    extras = {"project": "ValiChord", "run_id": "abc123"}
    bundle = ADAPTER.to_bundle(MINIMAL_SESSION, meta_extras=extras)
    assert bundle.meta is not None
    assert bundle.meta["project"] == "ValiChord"
    assert bundle.meta["run_id"] == "abc123"


def test_meta_extras_override_adapter_keys():
    # meta_extras is merged last so it can override adapter-set keys
    extras = {"cwd": "/override-cwd"}
    bundle = ADAPTER.to_bundle(MINIMAL_SESSION, meta_extras=extras)
    assert bundle.meta is not None
    assert bundle.meta["cwd"] == "/override-cwd"


# ---------------------------------------------------------------------------
# 20. bundle_hash vs content_hash
# ---------------------------------------------------------------------------

def test_bundle_hash_differs_from_content_hash():
    from valichord_attestation.canonical import content_hash, hash_bundle
    bundle = ADAPTER.to_bundle(MINIMAL_SESSION)
    # meta is always non-empty (session_id, cwd, etc.) so hashes differ
    assert hash_bundle(bundle) != content_hash(bundle)


def test_same_session_different_meta_same_content_hash():
    from valichord_attestation.canonical import content_hash
    bundle_a = ADAPTER.to_bundle(MINIMAL_SESSION, meta_extras={"run": "1"})
    bundle_b = ADAPTER.to_bundle(MINIMAL_SESSION, meta_extras={"run": "2"})
    assert content_hash(bundle_a) == content_hash(bundle_b)


# ---------------------------------------------------------------------------
# Unit tests for internal helpers
# ---------------------------------------------------------------------------

def test_entry_to_leaf_dict_structure():
    entry = {
        "type": "message",
        "id": "aa000001",
        "parentId": None,
        "timestamp": "2026-05-19T10:00:01Z",
        "message": {"role": "user", "content": "hello"},
    }
    leaf = _entry_to_leaf_dict(entry)
    assert set(leaf.keys()) == {"id", "type", "timestamp", "content"}
    assert leaf["id"] == "aa000001"
    assert leaf["type"] == "message"
    assert leaf["timestamp"] == "2026-05-19T10:00:01Z"
    # content = entry minus id/parentId/timestamp
    assert "id" not in leaf["content"]
    assert "parentId" not in leaf["content"]
    assert "timestamp" not in leaf["content"]
    assert leaf["content"]["message"] == {"role": "user", "content": "hello"}


def test_entry_to_leaf_dict_no_parent_id_in_content():
    entry = {"type": "message", "id": "x", "parentId": "y", "timestamp": "t", "message": {}}
    leaf = _entry_to_leaf_dict(entry)
    assert "parentId" not in leaf["content"]


def test_resolve_branch_empty_returns_empty():
    assert _resolve_branch(HEADER, []) == []


def test_resolve_branch_v1_linear():
    v1_header = {"type": "session", "cwd": "/p", "id": "abc", "timestamp": "t"}
    entries = [
        {"type": "message", "timestamp": "t1", "message": {"role": "user"}},
        {"type": "message", "timestamp": "t2", "message": {"role": "assistant"}},
    ]
    branch = _resolve_branch(v1_header, entries)
    assert branch == entries


def test_collect_metrics_no_tool_results_rate_zero():
    branch = [
        {
            "type": "message", "id": "a1", "parentId": None,
            "timestamp": "t",
            "message": {
                "role": "assistant", "provider": "x", "model": "m",
                "content": [], "usage": {"input": 10, "output": 5, "cost": {"total": 0.1}},
                "stopReason": "stop",
            },
        },
    ]
    metrics, _ = _collect_metrics(branch)
    rate = next(m["value"] for m in metrics if m["key"] == "tool_error_rate")
    assert rate == 0.0


def test_stop_reason_encoding_table_complete():
    for key in ("stop", "toolUse", "length", "error", "aborted"):
        assert key in _STOP_REASON_ENCODING
    assert _STOP_REASON_ENCODING["stop"] == 0.0
    assert _STOP_REASON_ENCODING["toolUse"] == 1.0


def test_extract_model_id_none_when_no_assistant():
    branch = [
        {"type": "message", "id": "u1", "parentId": None, "timestamp": "t",
         "message": {"role": "user", "content": "hi"}},
    ]
    assert _extract_model_id(branch) is None


def test_extract_task_id_empty_session_info_name_ignored():
    header = {**HEADER, "cwd": "/myproj", "id": "12345678abcdef"}
    branch = [
        {"type": "session_info", "id": "si", "parentId": None, "timestamp": "t", "name": "   "},
    ]
    task_id = _extract_task_id(header, branch)
    # Whitespace-only name → fall back to cwd/uuid
    assert task_id == "myproj/12345678"


# ---------------------------------------------------------------------------
# Coverage gap: _parse_session blank lines and malformed JSON (lines 107, 110-111)
# ---------------------------------------------------------------------------

def test_parse_session_skips_blank_lines(tmp_path):
    from valichord_attestation.adapters.pi_session_adapter import _parse_session
    lines = [
        json.dumps(HEADER),
        "",
        "   ",
        json.dumps(MINIMAL_SESSION[1]),
    ]
    f = tmp_path / "session.jsonl"
    f.write_text("\n".join(lines))
    header, entries = _parse_session(f)
    assert header["type"] == "session"
    assert len(entries) == 1


def test_parse_session_skips_malformed_json_lines(tmp_path):
    from valichord_attestation.adapters.pi_session_adapter import _parse_session
    lines = [
        json.dumps(HEADER),
        "not valid json {{{",
        json.dumps(MINIMAL_SESSION[1]),
    ]
    f = tmp_path / "session.jsonl"
    f.write_text("\n".join(lines))
    _, entries = _parse_session(f)
    assert len(entries) == 1


# ---------------------------------------------------------------------------
# Coverage gap: _resolve_branch defensive leaf-id missing (line 160)
# ---------------------------------------------------------------------------

def test_resolve_branch_leaf_missing_id_falls_back_to_linear():
    entries = [
        {"type": "message", "id": "a1", "parentId": None, "timestamp": "t"},
        {"type": "message", "parentId": "a1", "timestamp": "t"},  # no 'id'
    ]
    branch = _resolve_branch(HEADER, entries)
    # Leaf (last entry) has no 'id' → defensive linear fallback
    assert branch == entries


# ---------------------------------------------------------------------------
# Coverage gap: _resolve_branch broken parentId chain (line 170)
# ---------------------------------------------------------------------------

def test_resolve_branch_broken_parent_chain():
    # parentId points to an entry not in the index → walk terminates early
    entries = [
        {"type": "message", "id": "a1", "parentId": "MISSING", "timestamp": "t"},
    ]
    branch = _resolve_branch(HEADER, entries)
    assert branch == [entries[0]]


# ---------------------------------------------------------------------------
# Coverage gap: _resolve_branch compaction_idx < 0 fallback (line 190)
# ---------------------------------------------------------------------------

def test_resolve_branch_compaction_with_firstKeptEntryId():
    # Verify that compaction filtering works end-to-end (firstKeptEntryId honoured).
    # Line 190 (compaction_idx < 0) is unreachable by construction: any compaction
    # found during `for e in path` must already be in path, so compaction_idx >= 0.
    # This test exercises the normal compaction filtering path instead.
    entries = [
        {"type": "message", "id": "a1", "parentId": None, "timestamp": "t"},
        {"type": "message", "id": "a2", "parentId": "a1", "timestamp": "t"},
        {
            "type": "compaction",
            "id": "comp1",
            "parentId": "a2",
            "timestamp": "t",
            "firstKeptEntryId": "a2",
        },
        {"type": "message", "id": "a4", "parentId": "comp1", "timestamp": "t"},
    ]
    branch = _resolve_branch(HEADER, entries)
    ids = [e.get("id") for e in branch]
    # a1 is before firstKeptEntryId (a2) → excluded; a2, comp1, a4 kept
    assert "a1" not in ids
    assert "a2" in ids
    assert "comp1" in ids
    assert "a4" in ids


# ---------------------------------------------------------------------------
# Coverage gap: _collect_metrics non-dict msg (line 302)
# ---------------------------------------------------------------------------

def test_collect_metrics_non_dict_message_skipped():
    branch = [
        {
            "type": "message",
            "id": "a1",
            "parentId": None,
            "timestamp": "t",
            "message": "not-a-dict",  # triggers the 'continue' at line 302
        },
    ]
    metrics, stop = _collect_metrics(branch)
    turns = next(m["value"] for m in metrics if m["key"] == "total_turns")
    assert turns == 0.0
    assert stop is None


# ---------------------------------------------------------------------------
# Coverage gap: _git_head success path (lines 359-360)
# ---------------------------------------------------------------------------

def test_git_head_returns_sha_in_real_git_repo():
    import os
    # Use the repo root (parent of valichord_attestation/)
    repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    sha = _git_head(repo_root)
    # The workspace is a git repo so we should get a 40-char hex string
    assert sha is not None
    assert len(sha) == 40
    assert all(c in "0123456789abcdef" for c in sha)
