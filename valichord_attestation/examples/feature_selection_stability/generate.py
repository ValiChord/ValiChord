"""Step 1 — synthetic data with deliberately correlated blocks.

Ground truth is known, there is no licensing question, and anyone can reproduce
the matrix from this script alone. See FEATURE_SELECTION_STABILITY_PLAN.md §3.1.

Design:
  n = 500, p = 40
  three correlated blocks of 4 features each (rho ~ 0.95 within block)
  28 independent noise features
  true signal carried by ONE feature from each block

The single-signal-per-block choice is the point: the correct answer is genuinely
ambiguous by construction. An honest party has no principled basis for preferring
feature 0 of a block over feature 1 when the two correlate at 0.95, so honest
parties will disagree. That disagreement is the finding, not a failure.

The three signal coefficients deliberately span strong/medium/weak (3.0 / 2.0 /
1.0) so the stability profile shows a gradient rather than a single cliff.

Determinism: uses numpy.random.default_rng (PCG64), whose stream is covered by
NumPy's backwards-compatibility policy. Legacy RandomState is not used.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, asdict
from pathlib import Path

import numpy as np

SEED = 20260727

N_SAMPLES = 500
N_FEATURES = 40
BLOCK_SIZE = 4
N_BLOCKS = 3
WITHIN_BLOCK_RHO = 0.95
NOISE_SD = 1.0

# One signal feature per block, at the block's first index. Coefficients span
# strong/medium/weak so the stability profile shows a gradient.
SIGNAL_COEFFICIENTS = (3.0, 2.0, 1.0)


@dataclass(frozen=True)
class DatasetSpec:
    """The generating parameters, recorded alongside the data."""

    seed: int
    n_samples: int
    n_features: int
    block_size: int
    n_blocks: int
    within_block_rho: float
    noise_sd: float
    signal_coefficients: tuple[float, ...]

    def to_dict(self) -> dict:
        d = asdict(self)
        d["signal_coefficients"] = list(self.signal_coefficients)
        return d


SPEC = DatasetSpec(
    seed=SEED,
    n_samples=N_SAMPLES,
    n_features=N_FEATURES,
    block_size=BLOCK_SIZE,
    n_blocks=N_BLOCKS,
    within_block_rho=WITHIN_BLOCK_RHO,
    noise_sd=NOISE_SD,
    signal_coefficients=SIGNAL_COEFFICIENTS,
)


def feature_names(spec: DatasetSpec = SPEC) -> list[str]:
    """Stable feature names: block members then noise.

    Names are part of the pre-registered protocol — they appear as metric keys
    in every attestation bundle, so they must not depend on run order.
    """
    names = []
    for b in range(spec.n_blocks):
        for m in range(spec.block_size):
            names.append(f"blk{b}_f{m}")
    n_noise = spec.n_features - spec.n_blocks * spec.block_size
    names.extend(f"noise_{i:02d}" for i in range(n_noise))
    return names


def block_of(name: str) -> str | None:
    """Return the block label for a feature name, or None if it is noise.

    This is the map that makes the per-block frequency profile possible (§3.4).
    It is known here only because the data is synthetic — on real data the
    blocks would have to be estimated. See plan §6.
    """
    return name.split("_")[0] if name.startswith("blk") else None


def signal_indices(spec: DatasetSpec = SPEC) -> list[int]:
    """Indices of the truly predictive features — one per block, at index 0."""
    return [b * spec.block_size for b in range(spec.n_blocks)]


def generate(spec: DatasetSpec = SPEC) -> tuple[np.ndarray, np.ndarray]:
    """Generate (X, y) deterministically from the spec.

    Within a block, each member is built as
        x_j = sqrt(rho) * z + sqrt(1 - rho) * e_j
    with a shared latent z, which gives exactly `rho` pairwise correlation
    between distinct members of that block.
    """
    rng = np.random.default_rng(spec.seed)

    columns = []
    root_rho = np.sqrt(spec.within_block_rho)
    root_residual = np.sqrt(1.0 - spec.within_block_rho)

    for _ in range(spec.n_blocks):
        latent = rng.standard_normal(spec.n_samples)
        for _ in range(spec.block_size):
            noise = rng.standard_normal(spec.n_samples)
            columns.append(root_rho * latent + root_residual * noise)

    n_noise = spec.n_features - spec.n_blocks * spec.block_size
    for _ in range(n_noise):
        columns.append(rng.standard_normal(spec.n_samples))

    X = np.column_stack(columns)

    beta = np.zeros(spec.n_features)
    for coefficient, index in zip(spec.signal_coefficients, signal_indices(spec)):
        beta[index] = coefficient

    y = X @ beta + spec.noise_sd * rng.standard_normal(spec.n_samples)
    return X, y


def dataset_hash(X: np.ndarray, y: np.ndarray) -> str:
    """SHA-256 over the exact bytes of the matrix, with a shape/dtype header.

    The header is included so that two arrays with identical bytes but different
    shapes cannot collide. Arrays are forced to C-contiguous float64 first, so
    the digest does not depend on how the caller happened to build them.
    """
    Xc = np.ascontiguousarray(X, dtype=np.float64)
    yc = np.ascontiguousarray(y, dtype=np.float64)

    header = json.dumps(
        {
            "X_shape": list(Xc.shape),
            "y_shape": list(yc.shape),
            "dtype": "float64",
            "order": "C",
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")

    h = hashlib.sha256()
    h.update(header)
    h.update(Xc.tobytes(order="C"))
    h.update(yc.tobytes(order="C"))
    return h.hexdigest()


def write_dataset(out_dir: Path, spec: DatasetSpec = SPEC) -> dict:
    """Generate, hash, and persist the dataset. Returns the manifest."""
    X, y = generate(spec)
    digest = dataset_hash(X, y)

    out_dir.mkdir(parents=True, exist_ok=True)
    np.savez(out_dir / "dataset.npz", X=X, y=y)

    manifest = {
        "dataset_hash": digest,
        "spec": spec.to_dict(),
        "feature_names": feature_names(spec),
        "signal_features": [feature_names(spec)[i] for i in signal_indices(spec)],
    }
    (out_dir / "dataset_manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    )
    return manifest


def main() -> None:
    out_dir = Path(__file__).parent / "artifacts"
    manifest = write_dataset(out_dir)

    X, y = generate()
    print(f"X: {X.shape}   y: {y.shape}")
    print(f"dataset_hash: {manifest['dataset_hash']}")
    print(f"signal features (ground truth): {', '.join(manifest['signal_features'])}")

    # Report the realised within-block correlation as a sanity check on the
    # construction — it should sit very close to WITHIN_BLOCK_RHO.
    corr = np.corrcoef(X, rowvar=False)
    within = [corr[0, 1], corr[4, 5], corr[8, 9]]
    print("realised within-block corr (blk0, blk1, blk2): " + ", ".join(f"{c:.3f}" for c in within))
    print(f"realised signal-to-noise corr (blk0_f0 vs noise_00): {corr[0, 12]:+.3f}")


if __name__ == "__main__":
    main()
