import pytest
pytest.importorskip("inspect_evals")
import capsule_blinding_gate as gate


def test_is_retained_prefix_aware():
    # Removed in hard mode: results, environment, REPRODUCING.md, code/run, code/run.sh
    assert gate.is_retained("code/README.md") is True
    assert gate.is_retained("data/final_model.pth") is True
    assert gate.is_retained("REPRODUCING.md") is False
    assert gate.is_retained("results") is False
    assert gate.is_retained("results/output") is False        # prefix, not bare name
    assert gate.is_retained("results/sub/output.json") is False
    assert gate.is_retained("code/run") is False
    assert gate.is_retained("code/run.sh") is False
    assert gate.is_retained("code/runner.py") is True         # not "code/run" nor under it
