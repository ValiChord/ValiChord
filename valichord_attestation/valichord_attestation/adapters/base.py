from __future__ import annotations

from abc import ABC, abstractmethod

from ..bundle import Bundle


class AdapterBase(ABC):
    """Interface for harness-specific adapters that produce a Valichord Bundle.

    One adapter per eval harness (inspect_ai, lm-evaluation-harness, METR task-standard, …).
    Each adapter maps the harness's native output format to the canonical Bundle fields,
    passing raw per-sample dicts to `build_bundle` (or calling `merkle_root` directly)
    to compute `outputs_merkle_root`.

    The canonical format spec lives at valichord_attestation/spec/attestation_format_v1.md.
    """

    @abstractmethod
    def to_bundle(self, *args, **kwargs) -> Bundle:
        """Convert harness-native output to a Valichord attestation Bundle."""
