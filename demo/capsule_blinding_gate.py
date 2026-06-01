"""Pre-round blinding gate: prove the target answer is not readable from any file
the agent retains in CORE-Bench hard mode, so 'independent execution' cannot
reduce to 'read the number'. Pure functions + a tarball loader; no protocol code."""
import re
import tarfile as _tarfile
from typing import NamedTuple

from inspect_evals.core_bench.dataset import CAPSULE_PATHS_TO_REMOVE, CAPSULE_TAR_PATH

_TEXT_EXTS = (".md", ".txt", ".rst", ".py", ".json", ".ipynb", ".csv", ".yaml", ".yml")


_DOC_EXTS = (".md", ".txt", ".rst", ".ipynb")  # interval signal only here
_NUM_TOKEN = re.compile(r"-?\d+\.\d+|-?\d+")


class Leak(NamedTuple):
    file: str
    token: str
    signal: str  # "rounded_form" | "interval"


class CapsuleLeakError(RuntimeError):
    pass


def _rounded_forms(value: float) -> set[str]:
    """Specific-enough textual forms of a point value: exact repr, 3/4 dp, and the
    percentage form to 1/2 dp. 2 dp is deliberately excluded — too coarse, it would
    false-positive on unrelated constants in code/data."""
    forms = {repr(value), str(value), f"{value:.3f}", f"{value:.4f}",
             f"{value * 100:.1f}", f"{value * 100:.2f}"}
    return {f for f in forms if f}


def find_answer_leaks(retained_files: dict, committed_claim: dict) -> list:
    """Scan retained file text for the committed answer. Signal 1 (rounded point
    forms) runs on all files; signal 2 (interval membership) only on doc-like
    files, where an approximate *stated* result lives — on raw data/code it is
    noise. Returns at most one leak per (file, metric, signal)."""
    leaks = []
    for spec in committed_claim.values():
        value, lower, upper = spec["value"], spec["lower"], spec["upper"]
        forms = _rounded_forms(value)
        half = (upper - lower) / 2 if upper > lower else 0.0
        lo, hi = lower - half, upper + half
        for fname, text in retained_files.items():
            if any(form in text for form in forms):
                hit = next(form for form in forms if form in text)
                leaks.append(Leak(fname, hit, "rounded_form"))
            if fname.lower().endswith(_DOC_EXTS):
                for m in _NUM_TOKEN.finditer(text):
                    try:
                        num = float(m.group())
                    except ValueError:
                        continue
                    if lo <= num <= hi:
                        leaks.append(Leak(fname, m.group(), "interval"))
                        break
    return leaks


def assert_capsule_blind(retained_files: dict, committed_claim: dict) -> None:
    leaks = find_answer_leaks(retained_files, committed_claim)
    if leaks:
        detail = "\n  - ".join(f"{lk.file}: '{lk.token}' ({lk.signal})" for lk in leaks)
        raise CapsuleLeakError(
            "Capsule answer leaks into retained agent inputs — blinding is broken:\n  - " + detail
        )


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


def load_retained_capsule_text(capsule_id: str) -> dict:
    """Return {capsule_relative_path: text} for retained, text-extension files in
    the cached capsule tarball. utf-8 with errors='ignore' (so .ipynb output cells
    are scanned as raw JSON text)."""
    tar_path = CAPSULE_TAR_PATH.format(capsule_id=capsule_id)
    prefix = capsule_id + "/"
    out = {}
    with _tarfile.open(tar_path, "r:gz") as tar:
        for member in tar.getmembers():
            if not member.isfile():
                continue
            rel = member.name[len(prefix):] if member.name.startswith(prefix) else member.name
            if not rel or not is_retained(rel):
                continue
            if not rel.lower().endswith(_TEXT_EXTS):
                continue
            f = tar.extractfile(member)
            if f is None:
                continue
            out[rel] = f.read().decode("utf-8", errors="ignore")
    return out
