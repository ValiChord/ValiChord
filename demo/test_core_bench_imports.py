"""Guards the exact inspect_evals import surface the demo depends on.
If inspect_evals reorganises these, this test fails loudly and the pins
in requirements.txt must be revisited."""
import pytest

pytest.importorskip("inspect_ai")
pytest.importorskip("inspect_evals")


def test_inspect_evals_surface_importable():
    from inspect_evals.core_bench.dataset import (  # noqa: F401
        read_core_bench_dataset,
        CAPSULE_CHECKSUMS,
    )
    from inspect_evals.core_bench.core_bench import default_solver  # noqa: F401
    from inspect_evals.core_bench.utils import (  # noqa: F401
        calculate_prediction_intervals,
        categorize_keys,
    )


def test_inspect_ai_scorer_surface_importable():
    from inspect_ai.scorer import (  # noqa: F401
        scorer, Scorer, Score, Target, accuracy, CORRECT, INCORRECT,
    )
    from inspect_ai.solver import TaskState  # noqa: F401
    from inspect_ai.util import sandbox  # noqa: F401
