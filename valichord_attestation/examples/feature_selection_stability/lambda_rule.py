"""The pre-registered analysis procedure — hashed into protocol.json.

This module is the load-bearing part of the pre-registration. Every party runs
exactly this code on their own resample; nobody chooses a penalty by hand. The
SHA-256 of this file in full is recorded as `lambda_rule_impl_hash`, so the rule
is pinned as *code*, not as prose that code might drift from.

scikit-learn has no one-standard-error rule and no `alpha_1se`. `LassoCV.alpha_`
is the CV-MSE *minimiser*; the 1-SE rule exists in glmnet (`lambda.1se`) and has
never been implemented in sklearn. So it is written out here explicitly.

Why the 1-SE rule rather than the minimiser: the minimiser is noisy under
resampling and tends to a denser support, which would blur the very effect the
demonstration is about. The 1-SE rule takes the sparsest model that is still
statistically indistinguishable from the best one — the standard conservative
choice, and the one a model-risk reviewer would expect to see defended.

Determinism: `cv=KFold(shuffle=False)` and `selection="cyclic"` are both
deterministic, so a given resample always yields the same support. The alpha
grid is derived by sklearn *from the data* (grid size, eps, alpha_max from X, y),
which means each party gets their own grid. That is intended — it is what makes
each party's lambda genuinely their own — but it also makes this procedure
sklearn-version-sensitive, so the version is recorded in every bundle's meta.

That sensitivity is not hypothetical, and it bit on the first run. scikit-learn
folded the old `n_alphas` parameter into `alphas` (an int now means "generate
this many"), and the old spelling is gone by 1.9. A pre-registration that named
only the *estimator* would have silently survived that change with a different
grid; one that hashes this file does not. Requires scikit-learn >= 1.9.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np
from sklearn.linear_model import Lasso, LassoCV
from sklearn.model_selection import KFold

CV_FOLDS = 5
N_ALPHAS = 100
EPS = 1e-3
MAX_ITER = 50_000

# "coef != 0" — the support definition from the pre-registration.
SUPPORT_THRESHOLD = 0.0

LAMBDA_RULE_DESCRIPTION = (
    "LassoCV(cv=5, n_alphas=100, eps=1e-3) grid; "
    "alpha = largest alpha whose mean CV MSE <= (min mean CV MSE + 1 SE at the minimiser)"
)


def select_alpha_1se(alphas: np.ndarray, mse_path: np.ndarray) -> float:
    """Apply the one-standard-error rule to a fitted CV path.

    Args:
        alphas: the alpha grid, shape (n_alphas,).
        mse_path: cross-validated MSE, shape (n_alphas, n_folds).

    Returns:
        The largest alpha (strongest penalty, sparsest model) whose mean CV MSE
        is within one standard error of the minimum.

    The standard error is taken across folds at the minimising alpha, using the
    sample standard deviation (ddof=1) divided by sqrt(n_folds).
    """
    if mse_path.ndim != 2:
        raise ValueError(f"mse_path must be 2-D (n_alphas, n_folds), got {mse_path.shape}")

    mean_mse = mse_path.mean(axis=1)
    n_folds = mse_path.shape[1]
    se = mse_path.std(axis=1, ddof=1) / np.sqrt(n_folds)

    i_min = int(np.argmin(mean_mse))
    threshold = mean_mse[i_min] + se[i_min]

    eligible = alphas[mean_mse <= threshold]
    if eligible.size == 0:
        # Cannot happen — the minimiser is always within one SE of itself — but
        # fail loudly rather than silently returning the minimiser.
        raise RuntimeError("no alpha satisfied the 1-SE threshold")
    return float(np.max(eligible))


def fit_support(X: np.ndarray, y: np.ndarray) -> tuple[list[int], float]:
    """Run the full pre-registered procedure on one resample.

    Returns:
        (support_indices, derived_alpha) — support indices are sorted ascending.

    Features are not standardised: they are unit-variance by construction in
    this synthetic design (see generate.py). On real data this step would have
    to be pre-registered explicitly, since Lasso is scale-sensitive.
    """
    cv = KFold(n_splits=CV_FOLDS, shuffle=False)

    search = LassoCV(
        cv=cv,
        alphas=N_ALPHAS,
        eps=EPS,
        selection="cyclic",
        max_iter=MAX_ITER,
        fit_intercept=True,
    )
    search.fit(X, y)

    alpha = select_alpha_1se(search.alphas_, search.mse_path_)

    # LassoCV.coef_ is fitted at alpha_ (the minimiser), not at our 1-SE alpha,
    # so the final model has to be refitted at the alpha the rule actually chose.
    final = Lasso(alpha=alpha, max_iter=MAX_ITER, fit_intercept=True, selection="cyclic")
    final.fit(X, y)

    support = [int(i) for i in np.flatnonzero(np.abs(final.coef_) > SUPPORT_THRESHOLD)]
    return support, alpha


def fit_support_at_alpha(X: np.ndarray, y: np.ndarray, alpha: float) -> list[int]:
    """Fit at a caller-supplied alpha, bypassing the rule.

    This exists solely for the adversarial exhibit (lambda_shop.py). An honest
    party never calls it — the whole point of pre-registering a rule is that the
    penalty is not a free parameter. It lives here, in the pre-registered
    module, so that the attack is visibly using the same estimator as everyone
    else and differs *only* in how alpha was obtained.
    """
    final = Lasso(alpha=alpha, max_iter=MAX_ITER, fit_intercept=True, selection="cyclic")
    final.fit(X, y)
    return [int(i) for i in np.flatnonzero(np.abs(final.coef_) > SUPPORT_THRESHOLD)]


def impl_hash() -> str:
    """SHA-256 of this file in full.

    Whole-file rather than per-function: a change to CV_FOLDS or SUPPORT_THRESHOLD
    changes the procedure just as surely as a change to the function bodies, and
    a per-function hash would miss it.
    """
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
