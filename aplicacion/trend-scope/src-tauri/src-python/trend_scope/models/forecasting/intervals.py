"""W09: predictive intervals from out-of-sample residuals.

These are PREDICTIVE intervals (they describe future observations). They are
not confidence intervals of a parameter; do not mix the two terms.
"""
import numpy as np

from ..numeric import array, finite, integer, scalar

VERSION = '1.0.0-candidate'


def _quantiles(residuals: np.ndarray, level: float):
    tail = (1 - level) / 2
    return np.quantile(residuals, tail, axis=0), np.quantile(residuals, 1 - tail, axis=0)


def residual_intervals(point_forecast, residuals_by_horizon, *, level=0.90, min_residuals) -> dict:
    """Interval = point forecast + empirical residual quantiles, per horizon step.

    `residuals_by_horizon` has shape (n_origins, horizon) with residuals =
    observation - prediction. A horizon step with fewer than `min_residuals`
    residuals gets NaN bounds and is reported in `uncalibrated_horizons`;
    `uncertainty` is 'not_calibrated' when no step could be calibrated.
    `level` is the nominal coverage in (0, 1). Version 1.0.0-candidate.
    """
    point = array(point_forecast, 'point_forecast')
    residuals = array(residuals_by_horizon, 'residuals_by_horizon', ndim=2)
    nominal = scalar(level, 'level')
    needed = integer(min_residuals, 'min_residuals')
    if not 0 < nominal < 1:
        raise ValueError('level must be strictly between 0 and 1')
    if residuals.shape[1] != point.size:
        raise ValueError('residuals_by_horizon needs one column per forecast step')
    lower = np.full(point.size, np.nan)
    upper = np.full(point.size, np.nan)
    if residuals.shape[0] >= needed:
        low, high = _quantiles(residuals, nominal)
        lower, upper = point + low, point + high
        finite(lower), finite(upper)
        uncalibrated = np.array([], dtype=int)
    else:
        uncalibrated = np.arange(point.size)
    return {'lower': lower, 'upper': upper, 'level': nominal, 'n_residuals': int(residuals.shape[0]),
            'uncalibrated_horizons': uncalibrated,
            'uncertainty': 'residual_quantile_intervals' if not uncalibrated.size else 'not_calibrated',
            'warnings': ['Predictive interval from past out-of-sample errors; assumes future errors resemble them.']}


def empirical_coverage(observed, lower, upper) -> dict:
    """Fraction of observations inside [lower, upper] (NaN bounds are ignored)."""
    y, low, high = (np.asarray(item, dtype=np.float64) for item in (observed, lower, upper))
    if not (y.shape == low.shape == high.shape):
        raise ValueError('observed, lower and upper must have the same shape')
    usable = np.isfinite(y) & np.isfinite(low) & np.isfinite(high)
    if not usable.any():
        return {'coverage': None, 'n': 0}
    inside = (y[usable] >= low[usable]) & (y[usable] <= high[usable])
    return {'coverage': float(inside.mean()), 'n': int(usable.sum())}


def split_coverage(predictions, actual, *, level, min_residuals, calibration_fraction=0.6) -> dict:
    """Honest coverage: calibrate on the first origins, score on the later ones.

    `predictions` and `actual` have shape (n_origins, horizon), chronological by
    origin. Returns coverage per horizon step and overall, or None when either
    part is too small (calibration < min_residuals or fewer than 2 test origins).
    """
    p = array(predictions, 'predictions', ndim=2)
    a = array(actual, 'actual', ndim=2)
    if p.shape != a.shape:
        raise ValueError('predictions and actual must have the same shape')
    fraction = scalar(calibration_fraction, 'calibration_fraction')
    if not 0 < fraction < 1:
        raise ValueError('calibration_fraction must be strictly between 0 and 1')
    cut = int(np.ceil(fraction * p.shape[0]))
    needed = integer(min_residuals, 'min_residuals')
    if cut < needed or p.shape[0] - cut < 2:
        return {'coverage': None, 'per_horizon': None, 'n_calibration': cut, 'n_test': p.shape[0] - cut}
    low, high = _quantiles(a[:cut] - p[:cut], scalar(level, 'level'))
    lower, upper = p[cut:] + low, p[cut:] + high
    inside = (a[cut:] >= lower) & (a[cut:] <= upper)
    return {'coverage': float(inside.mean()), 'per_horizon': inside.mean(axis=0),
            'n_calibration': cut, 'n_test': p.shape[0] - cut}
