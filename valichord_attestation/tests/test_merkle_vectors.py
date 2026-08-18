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
ODD_NODE = json.loads((VECTOR_DIR / "merkle_v1_2_odd_node.json").read_text())


@pytest.mark.parametrize("case", V12["cases"], ids=lambda c: c["name"])
def test_v1_2_vector(case: dict) -> None:
    assert merkle_root(case["samples"]) == case["expected_root"], case["description"]


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
    a = merkle_root(ODD_NODE["input_a"]["samples"])
    b = merkle_root(ODD_NODE["input_b"]["samples"])
    assert a == ODD_NODE["input_a"]["root"]
    assert b == ODD_NODE["input_b"]["root"]
    assert a == b, "vector claims a collision that no longer reproduces"
