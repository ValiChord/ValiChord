"""Pre-round blinding gate: prove the target answer is not readable from any file
the agent retains in CORE-Bench hard mode, so 'independent execution' cannot
reduce to 'read the number'. Pure functions + a tarball loader; no protocol code."""
from typing import NamedTuple

from inspect_evals.core_bench.dataset import CAPSULE_PATHS_TO_REMOVE


def is_retained(rel_path: str, difficulty: str = "hard") -> bool:
    """A capsule-relative path is retained iff hard mode does not delete it.
    Removal entries are path prefixes applied as `rm -rf`, so a file is deleted
    when its path equals an entry or starts with `entry + '/'`. False negatives
    (treating a retained file as deleted) are the dangerous direction — they skip
    scanning — so the rule mirrors inspect's removal semantics exactly."""
    for entry in CAPSULE_PATHS_TO_REMOVE[difficulty]:
        if rel_path == entry or rel_path.startswith(entry + "/"):
            return False
    return True
