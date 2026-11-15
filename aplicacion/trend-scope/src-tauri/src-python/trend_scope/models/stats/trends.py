"""Sen slope, Mann-Kendall and multivariable OLS. No causal interpretation."""
import math
import numpy as np
from numba import njit
from ..numeric import array, finite, integer, temporal


@njit(cache=True)
def _score(y):
    s = 0
    for i in range(y.size-1):
        for j in range(i+1, y.size):
            s += int(y[j] > y[i]) - int(y[j] < y[i])
    return s


def sen_slope(times, values, *, max_pairs: int = 2_000_000) -> dict:
    """Median of all pairwise temporal slopes; no IID confidence interval."""
    t, y = temporal(times, values)
    limit = integer(max_pairs, 'max_pairs')
    n = len(y)
    if n*(n-1)//2 > limit:
        raise ValueError('Sen pair budget exceeded')
    slopes = np.empty(n*(n-1)//2)
    offset = 0
    with np.errstate(over='raise', invalid='raise', divide='raise'):
        for i in range(n-1):
            count = n-i-1
            slopes[offset:offset+count] = (y[i+1:]-y[i])/(t[i+1:]-t[i])
            offset += count
        slope = float(np.median(slopes))
        # Centered intercept avoids dependence on arbitrary time origin.
        reference = float(t[0])
        intercept = float(np.median(y-slope*(t-reference)))
    finite([slope, intercept])
    return {'slope': slope, 'intercept_at_reference': intercept, 'time_reference': reference,
            'uncertainty': 'not_estimated', 'n_pairs': len(slopes),
            'warnings': ['Descriptive slope; seasonality and autocorrelation are not removed and uncertainty is not estimated.']}


def _mk_components(y):
    n = len(y)
    _, counts = np.unique(y, return_counts=True)
    ties = sum(int(c)*(int(c)-1)*(2*int(c)+5) for c in counts)
    return int(_score(y)), (n*(n-1)*(2*n+5)-ties)/18.


def mann_kendall(times, values, *, seasons=None, max_pairs: int = 2_000_000) -> dict:
    """Two-sided asymptotic MK with tie correction and continuity correction.

    Optional explicit season labels sum within-season scores and variances;
    that variance assumes independent seasons and no serial dependence.
    """
    _, y = temporal(times, values)
    if len(y)*(len(y)-1)//2 > integer(max_pairs, 'max_pairs'):
        raise ValueError('MK pair budget exceeded')
    if seasons is None:
        groups = [y]
    else:
        labels = np.asarray(seasons)
        if labels.shape != y.shape or labels.dtype.kind not in 'iuUS' or labels.dtype.kind == 'b':
            raise ValueError('Provide an integer or string season label for every observation')
        groups = [y[labels == label] for label in np.unique(labels)]
        if not any(len(group) >= 2 for group in groups):
            raise ValueError('At least one season needs repeated observations')
    components = [_mk_components(group) for group in groups]
    s, variance = sum(c[0] for c in components), sum(c[1] for c in components)
    z = (s-np.sign(s))/math.sqrt(variance) if variance > 0 else 0.
    p = math.erfc(abs(z)/math.sqrt(2))
    pairs = sum(len(g)*(len(g)-1)//2 for g in groups)
    return {'score': s, 'variance': variance, 'z': float(z), 'p_value': p,
            'tau_a': s/pairs, 'seasonal': seasons is not None,
            'warnings': ['Asymptotic p-value; small samples may require an exact test.',
                         'Serial/cross-season dependence is not corrected; significance is conditional on independence.',
                         'Significance does not establish causality or physical importance.']}


def multivariable_ols(features, values) -> dict:
    """Full-rank OLS with intercept, centered/scaled design and SVD least squares."""
    x, y = array(features, 'features', ndim=2), array(values, 'values')
    n, p = x.shape
    if len(y) != n or n < p+1 or p == 0:
        raise ValueError('Need matching rows and at least p+1 observations')
    with np.errstate(over='raise', invalid='raise', divide='raise'):
        center = x.mean(axis=0)
        scale = np.max(np.abs(x-center), axis=0)
        if np.any(scale == 0):
            raise ValueError('Constant feature is redundant with intercept')
        design = np.column_stack((np.ones(n), (x-center)/scale))
        yc = y.mean()
        coefficient, _, rank, singular = np.linalg.lstsq(design, y-yc, rcond=None)
        if rank != p+1:
            raise ValueError('Rank-deficient feature matrix')
        fitted = yc + design @ coefficient
        residual = y-fitted
        slopes = coefficient[1:]/scale
        intercept = yc+coefficient[0]-center @ slopes
        rmse = np.linalg.norm(residual)/np.sqrt(n)
        total = finite(np.linalg.norm(y-yc))
        r2 = None if total == 0 else 1-(np.linalg.norm(residual)/total)**2
    for value in (fitted, residual, slopes, intercept, rmse):
        finite(value)
    if r2 is not None:
        finite(r2)
    return {'coefficients': slopes, 'intercept': float(intercept), 'fitted': fitted,
            'residuals': residual, 'rmse': float(rmse), 'mae': float(np.mean(abs(residual))),
            'r2': r2, 'rank': int(rank), 'scaled_condition_number': float(singular[0]/singular[-1]),
            'uncertainty': 'not_estimated',
            'warnings': ['Descriptive in-sample fit; no causal inference, confidence intervals or validated forecast.']}
