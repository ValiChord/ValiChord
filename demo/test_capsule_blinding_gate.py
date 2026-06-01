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


_CLAIM = {"AUC": {"value": 0.9157952669235003, "lower": 0.9148, "upper": 0.9167, "basis": "explicit_tolerance"}}


def test_rounded_form_leak_any_extension():
    files = {"code/train.py": "# expected final auc 0.916 on the test split\n"}
    leaks = gate.find_answer_leaks(files, _CLAIM)
    assert any(lk.signal == "rounded_form" and lk.file == "code/train.py" for lk in leaks)


def test_notebook_output_cell_leak():
    nb = '{"cells":[{"outputs":[{"text":["AUC: 0.9158\\n"]}]}]}'
    leaks = gate.find_answer_leaks({"analysis.ipynb": nb}, _CLAIM)
    assert any(lk.signal == "rounded_form" for lk in leaks)


def test_interval_signal_only_doc_files():
    # 0.9155 is inside [lower-h, upper+h]; flagged in .md, ignored in .csv/.py
    assert gate.find_answer_leaks({"README.md": "approx 0.9155\n"}, _CLAIM)
    assert gate.find_answer_leaks({"data.csv": "x,0.9155,y\n"}, _CLAIM) == []
    assert gate.find_answer_leaks({"m.py": "lr = 0.9155\n"}, _CLAIM) == []


def test_clean_capsule_no_leak():
    files = {"code/README.md": "conda install pytorch; prepare covid/ then run.",
             "data.csv": "id,label\n1,0\n2,1\n"}
    assert gate.find_answer_leaks(files, _CLAIM) == []


def test_assert_raises_and_names_file():
    with pytest.raises(gate.CapsuleLeakError) as exc:
        gate.assert_capsule_blind({"REPORTME.md": "AUC = 0.9158"}, _CLAIM)
    assert "REPORTME.md" in str(exc.value)
