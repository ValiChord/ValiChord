"""pi coding agent session JSONL → Valichord Bundle adapter.

Reads a pi session v3 JSONL file (or accepts a pre-parsed list of entry dicts)
and converts the session data into a canonical Valichord Bundle.

Field mapping (pi session → Valichord Bundle):

    AssistantMessage.provider + "/" + .model (last seen) → Bundle.model_id
    SessionInfoEntry.name (last non-empty)               → Bundle.task_id
    SessionHeader.timestamp                              → Bundle.generated_at
    git rev-parse HEAD (in session cwd, best-effort)    → Bundle.repo_commit
    Derived from branch entries (8 metrics)             → Bundle.metrics
    All active-branch entries as leaf dicts             → Bundle.outputs_merkle_root

task_id fallback (when no session_info name is set):
    Path(header.cwd).name + "/" + header.id[:8]

Branch traversal (v2/v3 sessions):
    Pi sessions are append-only trees.  The active branch is the path from the
    last entry in the file (the leaf) to the root, followed via parentId links.
    This mirrors SessionManager._buildIndex() which sets leafId = last entry.id.

    v1 sessions (header.version < 2 or no id field on entries): treated as
    linear — all entries used in insertion order.

    Compaction: entries before firstKeptEntryId of the last compaction on the
    path are excluded, matching buildSessionContext() behaviour.

Merkle leaf format (each branch entry becomes one leaf dict):
    {"id": str, "type": str, "timestamp": str, "content": dict}
    where content = entry dict minus id / parentId / timestamp.

Metrics (aggregated from the active branch):
    total_turns         — AssistantMessage count
    total_tool_calls    — toolCall content blocks across assistant messages
    tool_error_rate     — isError ToolResult count / total ToolResult count
    total_input_tokens  — sum of AssistantMessage.usage.input
    total_output_tokens — sum of AssistantMessage.usage.output
    total_cost_usd      — sum of AssistantMessage.usage.cost.total
    compaction_count    — CompactionEntry count on branch
    final_stop_reason   — last AssistantMessage.stopReason, float-encoded:
                          stop=0.0  toolUse=1.0  length=2.0
                          error=3.0  aborted=4.0  unknown=-1.0

meta block (excluded from content_hash):
    session_id, cwd, harness_version="pi", final_stop_reason_str (if set)
    session_file (only when a file path is passed)
    Any meta_extras merged last.

Source reference: https://github.com/earendil-works/pi/blob/main/packages/coding-agent/docs/session-format.md
Implementation plan: docs/PISESSION_ADAPTER_PLAN.md
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Optional, Union

from ..adapters.base import AdapterBase
from ..builder import build_bundle
from ..bundle import Bundle

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_STOP_REASON_ENCODING: dict[str, float] = {
    "stop": 0.0,
    "toolUse": 1.0,
    "length": 2.0,
    "error": 3.0,
    "aborted": 4.0,
}

# Fields stripped from each entry when building the Merkle leaf content dict.
# These are tree-structure fields; all semantic payload is kept.
_TREE_FIELDS = frozenset(("id", "parentId", "timestamp"))


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _parse_session(
    session: Union[str, "Path", list],
) -> tuple[dict, list[dict]]:
    """Parse a pi session input into (header, entries).

    Accepts a file path (str/Path) or a pre-parsed list of entry dicts.
    The first element must be the session header (type == "session").

    Returns:
        header:  session header dict
        entries: all non-header entry dicts, in file order

    Raises:
        ValueError: if the input is empty or the first entry is not a session header.
    """
    if isinstance(session, (str, Path)):
        text = Path(session).read_text(encoding="utf-8")
        raw: list[dict] = []
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                raw.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    else:
        raw = list(session)

    if not raw:
        raise ValueError("Session is empty — no entries found.")

    header = raw[0]
    if not isinstance(header, dict) or header.get("type") != "session":
        raise ValueError(
            f"First entry must be a session header (type: 'session'), "
            f"got type={header.get('type')!r}"
        )

    entries = [e for e in raw[1:] if isinstance(e, dict)]
    return header, entries


def _resolve_branch(header: dict, entries: list[dict]) -> list[dict]:
    """Return active-branch entries in root→leaf order, with compaction filtering.

    v1 sessions (header.version < 2, or first entry lacks 'id'): all entries
    in insertion order (pi auto-migrates files, but pre-parsed lists may be v1).

    v2/v3 sessions: walk parentId links from the last entry (leaf) back to the
    root.  This mirrors SessionManager._buildIndex() which sets leafId to the
    last non-header entry id.

    Compaction: if any compaction entry appears on the path, entries before
    firstKeptEntryId of the *last* such compaction are excluded, matching
    buildSessionContext() behaviour.
    """
    if not entries:
        return []

    # Detect v1: format version < 2, or first entry has no 'id' field.
    version = header.get("version", 1)
    if version < 2 or "id" not in entries[0]:
        return list(entries)

    # Build id → entry index for O(1) parentId traversal.
    by_id: dict[str, dict] = {
        e["id"]: e for e in entries if isinstance(e.get("id"), str)
    }

    # Leaf = last entry in file (matches _buildIndex() behaviour).
    leaf = entries[-1]
    leaf_id: Optional[str] = leaf.get("id")
    if not leaf_id:
        return list(entries)  # defensive: fall back to linear

    # Walk parentId from leaf to root; build path in root→leaf order.
    path: list[dict] = []
    current_id: Optional[str] = leaf_id
    visited: set[str] = set()
    while current_id and current_id not in visited:
        visited.add(current_id)
        entry = by_id.get(current_id)
        if entry is None:
            break
        path.insert(0, entry)
        current_id = entry.get("parentId") or None

    # Find the last compaction entry on the path (matches buildSessionContext).
    compaction: Optional[dict] = None
    for e in path:
        if e.get("type") == "compaction":
            compaction = e

    if compaction is None:
        return path

    # Apply compaction filtering: exclude entries before firstKeptEntryId.
    first_kept_id: Optional[str] = compaction.get("firstKeptEntryId")
    compaction_id: str = compaction["id"]
    compaction_idx = next(
        (i for i, e in enumerate(path) if e.get("id") == compaction_id), -1
    )
    if compaction_idx < 0:
        return path  # defensive fallback

    # Entries before compaction: only from firstKeptEntryId onwards.
    kept: list[dict] = []
    found_first_kept = False
    for i in range(compaction_idx):
        e = path[i]
        if e.get("id") == first_kept_id:
            found_first_kept = True
        if found_first_kept:
            kept.append(e)

    # Compaction entry itself, then all entries after it.
    kept.append(compaction)
    kept.extend(path[compaction_idx + 1 :])
    return kept


def _entry_to_leaf_dict(entry: dict) -> dict:
    """Convert a session entry to the canonical Merkle leaf dict.

    Format:
        {
            "id":        str   — entry id (8-char hex)
            "type":      str   — entry type
            "timestamp": str   — ISO timestamp
            "content":   dict  — entry dict minus id / parentId / timestamp
        }

    content retains all semantic fields (including "type") so that each entry
    type's payload is fully committed without duplication of tree-structure
    metadata.
    """
    content = {k: v for k, v in entry.items() if k not in _TREE_FIELDS}
    return {
        "id": str(entry.get("id", "")),
        "type": str(entry.get("type", "")),
        "timestamp": str(entry.get("timestamp", "")),
        "content": content,
    }


def _extract_model_id(branch: list[dict]) -> Optional[str]:
    """Return the last model seen on the branch as "provider/model".

    Checks both model_change entries and assistant message entries; the last
    one encountered (closest to the leaf) wins, matching buildSessionContext().
    """
    model_id: Optional[str] = None
    for entry in branch:
        t = entry.get("type")
        if t == "model_change":
            provider = entry.get("provider", "")
            model = entry.get("modelId", "")
            if provider and model:
                model_id = f"{provider}/{model}"
        elif t == "message":
            msg = entry.get("message")
            if isinstance(msg, dict) and msg.get("role") == "assistant":
                provider = msg.get("provider", "")
                model = msg.get("model", "")
                if provider and model:
                    model_id = f"{provider}/{model}"
    return model_id


def _extract_task_id(header: dict, branch: list[dict]) -> str:
    """Infer task_id from the last session_info name, or cwd+uuid fallback."""
    name: Optional[str] = None
    for entry in branch:
        if entry.get("type") == "session_info":
            n = (entry.get("name") or "").strip()
            if n:
                name = n
    if name:
        return name

    cwd: str = header.get("cwd", "")
    session_id: str = header.get("id", "")
    cwd_base = Path(cwd).name or "session"
    uuid_prefix = session_id[:8] if len(session_id) >= 8 else session_id
    return f"{cwd_base}/{uuid_prefix}"


def _collect_metrics(
    branch: list[dict],
) -> tuple[list[dict], Optional[str]]:
    """Aggregate performance metrics from all entries on the active branch.

    Returns:
        (raw_metrics, final_stop_reason_str)
        raw_metrics: list of {"key": str, "value": float} dicts for build_bundle()
        final_stop_reason_str: the raw stopReason string from the last assistant
            message (None if no assistant messages have a stopReason set).
    """
    total_turns = 0
    total_tool_calls = 0
    total_tool_results = 0
    error_tool_results = 0
    total_input_tokens = 0.0
    total_output_tokens = 0.0
    total_cost_usd = 0.0
    compaction_count = 0
    final_stop_reason: Optional[str] = None

    for entry in branch:
        t = entry.get("type")
        if t == "compaction":
            compaction_count += 1
        elif t == "message":
            msg = entry.get("message")
            if not isinstance(msg, dict):
                continue
            role = msg.get("role")
            if role == "assistant":
                total_turns += 1
                content = msg.get("content", [])
                if isinstance(content, list):
                    for block in content:
                        if isinstance(block, dict) and block.get("type") == "toolCall":
                            total_tool_calls += 1
                usage = msg.get("usage") or {}
                total_input_tokens += float(usage.get("input") or 0)
                total_output_tokens += float(usage.get("output") or 0)
                cost = usage.get("cost") or {}
                total_cost_usd += float(cost.get("total") or 0)
                sr = msg.get("stopReason")
                if sr:
                    final_stop_reason = str(sr)
            elif role == "toolResult":
                total_tool_results += 1
                if msg.get("isError"):
                    error_tool_results += 1

    tool_error_rate = (
        error_tool_results / total_tool_results if total_tool_results > 0 else 0.0
    )
    stop_float = (
        _STOP_REASON_ENCODING.get(final_stop_reason, -1.0)
        if final_stop_reason is not None
        else -1.0
    )

    raw_metrics: list[dict] = [
        {"key": "total_turns", "value": float(total_turns)},
        {"key": "total_tool_calls", "value": float(total_tool_calls)},
        {"key": "tool_error_rate", "value": tool_error_rate},
        {"key": "total_input_tokens", "value": float(total_input_tokens)},
        {"key": "total_output_tokens", "value": float(total_output_tokens)},
        {"key": "total_cost_usd", "value": float(total_cost_usd)},
        {"key": "compaction_count", "value": float(compaction_count)},
        {"key": "final_stop_reason", "value": stop_float},
    ]
    return raw_metrics, final_stop_reason


def _git_head(cwd: str) -> Optional[str]:
    """Best-effort `git rev-parse HEAD` in cwd. Returns None on any failure."""
    if not cwd:
        return None
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            sha = result.stdout.strip()
            return sha or None
    except Exception:
        pass
    return None


# ---------------------------------------------------------------------------
# Adapter
# ---------------------------------------------------------------------------

class PiSessionAdapter(AdapterBase):
    """Adapter: pi coding agent session JSONL → Valichord attestation Bundle.

    Reads a pi session v3 JSONL file (or accepts a pre-parsed list of entry
    dicts) and produces a Bundle that commits to the model, task, performance
    metrics, and full per-entry content of the session.

    The bundle is intended to travel alongside the session file when published
    (e.g. via pi-share-hf), giving any consumer a way to verify the published
    session is byte-for-byte unmodified via Merkle proof.

    See module docstring and docs/PISESSION_ADAPTER_PLAN.md for field mapping.

    Example::

        from valichord_attestation.adapters import PiSessionAdapter
        from valichord_attestation import hash_bundle, content_hash

        adapter = PiSessionAdapter()
        bundle = adapter.to_bundle(
            "~/.pi/agent/sessions/--home-me-myproject--/2026-05-19T10:00:00_abc123.jsonl",
            task_id_override="myproject/fix-auth-bug",
        )
        print(bundle.bundle_hash)   # publish alongside session on HF
        print(bundle.content_hash)  # scientific equivalence (excludes meta)
    """

    def to_bundle(
        self,
        session: "Union[str, Path, list[dict]]",
        *,
        task_id_override: Optional[str] = None,
        repo_commit: Optional[str] = None,
        meta_extras: Optional[dict] = None,
    ) -> Bundle:
        """Convert a pi session to a Valichord attestation Bundle.

        Args:
            session: Path to a .jsonl session file (str or Path), or a
                     pre-parsed list of entry dicts (for testing without
                     file I/O).  When a list is passed, the first element
                     must be the session header dict.
            task_id_override: Override the inferred task_id.  When absent,
                              task_id is taken from the last session_info name,
                              or falls back to cwd-basename/uuid-prefix.
            repo_commit: Git commit SHA of the project working directory at
                         session time.  When absent, auto-extracted via
                         `git rev-parse HEAD` in the session's cwd (best-effort;
                         silently None if not a git repo or git unavailable).
            meta_extras: Extra key/value pairs merged last into Bundle.meta.

        Returns:
            A Valichord Bundle ready for canonicalisation and hashing.

        Raises:
            ValueError: if the session is empty, contains no assistant messages,
                        or model_id cannot be determined.
            MalformedBundleError: propagated from build_bundle() on bad metric
                                  values.
        """
        header, entries = _parse_session(session)

        branch = _resolve_branch(header, entries)
        if not branch:
            raise ValueError(
                "Session has no non-header entries — cannot build Bundle."
            )

        # model_id: last assistant provider/model on branch
        model_id = _extract_model_id(branch)
        if not model_id:
            raise ValueError(
                "No assistant messages found in session — cannot determine model_id."
            )

        # task_id: override > session_info name > cwd+uuid fallback
        task_id = task_id_override or _extract_task_id(header, branch)

        # generated_at: session header timestamp (ISO 8601)
        generated_at: Optional[str] = header.get("timestamp") or None

        # repo_commit: explicit > auto-extract from session cwd
        if repo_commit is None:
            cwd: str = header.get("cwd", "")
            repo_commit = _git_head(cwd)

        # metrics + stop reason string for meta
        raw_metrics, final_stop_reason_str = _collect_metrics(branch)

        # Merkle over all active-branch entries
        leaf_dicts = [_entry_to_leaf_dict(e) for e in branch]

        # meta: provenance block (excluded from content_hash)
        meta: dict = {
            "harness_version": "pi",
            "session_id": header.get("id", ""),
            "cwd": header.get("cwd", ""),
        }
        if isinstance(session, (str, Path)):
            meta["session_file"] = str(session)
        if final_stop_reason_str is not None:
            meta["final_stop_reason_str"] = final_stop_reason_str
        if meta_extras:
            meta.update(meta_extras)

        return build_bundle(
            model_id=model_id,
            task_id=task_id,
            raw_metrics=raw_metrics,
            samples=leaf_dicts,
            samples_total=len(leaf_dicts),
            repo_commit=repo_commit,
            generated_at=generated_at,
            meta=meta,
        )
