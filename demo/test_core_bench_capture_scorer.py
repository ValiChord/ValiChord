import asyncio
import json
import pytest

pytest.importorskip("inspect_ai")
from core_bench_capture_scorer import read_report_from_sandbox


class _FakeSandbox:
    def __init__(self, content, raise_not_found=False):
        self._content = content
        self._raise = raise_not_found
        self.read_calls = []

    async def read_file(self, path):
        self.read_calls.append(path)
        if self._raise:
            raise FileNotFoundError(path)
        return self._content


def test_reads_and_parses_report():
    sb = _FakeSandbox(json.dumps({"Q": 96.125}))
    report = asyncio.run(read_report_from_sandbox(sb))
    assert report == {"Q": 96.125}
    assert sb.read_calls == ["report.json"]


def test_missing_report_returns_none():
    sb = _FakeSandbox("", raise_not_found=True)
    assert asyncio.run(read_report_from_sandbox(sb)) is None


def test_invalid_json_returns_none():
    sb = _FakeSandbox("not json {")
    assert asyncio.run(read_report_from_sandbox(sb)) is None


def test_blinding_guard_source_never_references_ground_truth():
    """The capture path must not read state.metadata['results'] (the sealed
    ground truth). Enforce structurally by scanning the source."""
    import inspect, core_bench_capture_scorer as mod
    src = inspect.getsource(mod)
    assert "report.json" in src  # sanity: file is about reports
    assert 'metadata["results"]' not in src
    assert "metadata['results']" not in src
