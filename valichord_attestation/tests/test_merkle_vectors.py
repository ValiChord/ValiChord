"""Conformance vectors for the v1.2 Merkle construction as shipped.

The vectors are language-neutral JSON so a re-implementation — the Rust side
included — can check itself against the same expected roots this package
produces today. They pin v1.2 behaviour, not desired behaviour: when the
construction changes, replace these vectors rather than extending them.

Contributed from falsify-cookbook#4.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from valichord_attestation.merkle import merkle_root

VECTOR_DIR = Path(__file__).parent / "vectors"
V12 = json.loads((VECTOR_DIR / "merkle_v1_2.json").read_text())
V2 = json.loads((VECTOR_DIR / "merkle_v2.json").read_text())
ODD_NODE = json.loads((VECTOR_DIR / "merkle_v1_2_odd_node.json").read_text())

#: These files pin v1.2 and must always be checked under v1.2. Passing this
#: explicitly rather than inheriting the library default is the whole point of a
#: conformance vector: it records what that version does, not what the current
#: version does. Without it these tests silently retarget when the default moves.
VERSION = "v1.2"


@pytest.mark.parametrize("case", V12["cases"], ids=lambda c: c["name"])
def test_v1_2_vector(case: dict) -> None:
    assert (
        merkle_root(case["samples"], format_version=VERSION) == case["expected_root"]
    ), case["description"]


@pytest.mark.parametrize("case", V2["cases"], ids=lambda c: c["name"])
def test_v2_vector(case: dict) -> None:
    assert (
        merkle_root(case["samples"], format_version="v2") == case["expected_root"]
    ), case["description"]


def test_the_two_vector_files_cover_the_same_cases() -> None:
    """v2 mirrors the v1.2 case list, plus the empty case v1.2 cannot express.

    Keeping the names aligned is what makes the two files comparable case by
    case, which is how someone porting an implementation checks their work.
    """
    v12_names = [c["name"] for c in V12["cases"]]
    v2_names = [c["name"] for c in V2["cases"]]
    assert v2_names == v12_names + ["empty"]


@pytest.mark.parametrize("name", [c["name"] for c in V12["cases"]])
def test_no_case_has_the_same_root_under_both_versions(name: str) -> None:
    """If any shared case agreed, one of the two files would be mislabelled."""
    a = next(c for c in V12["cases"] if c["name"] == name)["expected_root"]
    b = next(c for c in V2["cases"] if c["name"] == name)["expected_root"]
    assert a != b


def test_v1_2_vectors_are_distinct_where_they_should_be() -> None:
    """The order, content and extra-field cases must not collide with the base case."""
    roots = {c["name"]: c["expected_root"] for c in V12["cases"]}
    base = roots["four_samples"]
    for name in ("order_reversed", "content_changed", "extra_field"):
        assert roots[name] != base, f"{name} must not share a root with four_samples"


def test_odd_node_padding_collision_is_still_present() -> None:
    """Documents a known v1.2 limitation rather than asserting it is desirable.

    Odd levels are padded by duplicating the last node, so [A,B,C] and [A,B,C,C]
    hash to one root and the root alone no longer identifies the leaf list. When
    the construction moves to RFC 6962-style promotion this test should be
    inverted to assert the two inputs differ.
    """
    a = merkle_root(ODD_NODE["input_a"]["samples"], format_version=VERSION)
    b = merkle_root(ODD_NODE["input_b"]["samples"], format_version=VERSION)
    assert a == ODD_NODE["input_a"]["root"]
    assert b == ODD_NODE["input_b"]["root"]
    assert a == b, "vector claims a collision that no longer reproduces"


def test_odd_node_collision_is_gone_under_v2() -> None:
    """The inversion the contributed docstring asked for, as a separate test.

    The collision test above stays as-is — it documents v1.2 and must keep
    passing for as long as v1.2 bundles exist. This is its counterpart: the same
    two inputs, under the construction that fixed them.
    """
    a = merkle_root(ODD_NODE["input_a"]["samples"], format_version="v2")
    b = merkle_root(ODD_NODE["input_b"]["samples"], format_version="v2")
    assert a != b, "v2 must distinguish [A,B,C] from [A,B,C,C]"
