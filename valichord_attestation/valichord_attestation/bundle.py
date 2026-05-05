from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional


class MalformedBundleError(ValueError):
    """Raised when a bundle field is absent, malformed, or contains a non-finite number."""


def _reject_non_finite(v: float, label: str) -> None:
    if not math.isfinite(v):
        raise MalformedBundleError(
            f"{label}: NaN, Infinity, and subnormal values are not permitted in bundles"
        )


@dataclass
class Metric:
    """A single scalar result metric.

    `value` and `stderr` must be finite floats pre-rounded to 6 dp by the caller
    (see `canonical.pre_round`). Validated on construction.
    """

    key: str
    value: float
    stderr: Optional[float] = None

    def __post_init__(self) -> None:
        if not self.key:
            raise MalformedBundleError("Metric.key must not be empty")
        _reject_non_finite(self.value, f"metric '{self.key}' value")
        if self.stderr is not None:
            _reject_non_finite(self.stderr, f"metric '{self.key}' stderr")


@dataclass
class Bundle:
    """Canonical attestation bundle (format v1).

    Required fields raise MalformedBundleError on absence or empty string.
    Optional fields (None) are omitted from canonical encoding — never serialised as null.
    """

    format_version: str
    generated_at: str        # ISO 8601, UTC recommended
    model_id: str
    task_id: str
    metrics: list[Metric]
    samples_total: int
    samples_completed: int
    outputs_merkle_root: str
    repo_commit: Optional[str] = None
    harness_version: Optional[str] = None
    command: Optional[str] = None

    def __post_init__(self) -> None:
        required = {
            "format_version": self.format_version,
            "generated_at": self.generated_at,
            "model_id": self.model_id,
            "task_id": self.task_id,
            "outputs_merkle_root": self.outputs_merkle_root,
        }
        for name, val in required.items():
            if not val:
                raise MalformedBundleError(f"Bundle.{name} must not be empty")
        if not self.metrics:
            raise MalformedBundleError("Bundle.metrics must contain at least one entry")
        if self.samples_total < 0 or self.samples_completed < 0:
            raise MalformedBundleError("Bundle sample counts must be non-negative integers")
