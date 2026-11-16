"""W10: ETCCDI-style indices from regular daily series.

Inputs: a regular daily series in chronological order and `groups`, one
integer label per day (the year). Each index is reported separately and per
group; they are not combined. Daily precipitation in mm, no missing values.
Definitions follow the ETCCDI index descriptions (Zhang et al., 2011); the
wet-day threshold is an explicit argument (the standard value is 1 mm).
"""
import numpy as np

from ..numeric import array, finite, integer, scalar

VERSION = '1.0.0-candidate'


def _prepare(values, groups, *, precipitation=True):
    y = array(values, 'values')
    labels = np.asarray(groups)
    if labels.shape != y.shape or labels.dtype.kind not in 'iu':
        raise ValueError('groups must be one integer year label per day')
    if precipitation and np.any(y < 0):
        raise ValueError('precipitation must be nonnegative')
    return y, labels, np.unique(labels)


def _result(ids, output, valid=None, **extra):
    finite(output[~np.isnan(output)])
    return {'group_ids': ids, 'values': output,
            'valid': np.ones(len(ids), dtype=bool) if valid is None else valid,
            'uncertainty': 'not_estimated',
            'warnings': ['Index computed per group from daily data; no missing days are tolerated.'], **extra}


def rx1day(values, groups) -> dict:
    """Maximum 1-day precipitation per year (mm)."""
    y, labels, ids = _prepare(values, groups)
    return _result(ids, np.array([y[labels == g].max() for g in ids]))


def rx5day(values, groups) -> dict:
    """Maximum 5-consecutive-day precipitation total per year (mm), windows inside the year."""
    y, labels, ids = _prepare(values, groups)
    output = np.full(len(ids), np.nan)
    for position, g in enumerate(ids):
        sample = y[labels == g]
        if sample.size >= 5:
            output[position] = np.convolve(sample, np.ones(5), mode='valid').max()
    valid = ~np.isnan(output)
    return _result(ids, output, valid)


def sdii(values, groups, *, wet_threshold) -> dict:
    """Simple daily intensity index: mean precipitation on wet days (>= threshold), mm/day."""
    y, labels, ids = _prepare(values, groups)
    limit = scalar(wet_threshold, 'wet_threshold', True)
    output = np.full(len(ids), np.nan)
    for position, g in enumerate(ids):
        wet = y[(labels == g) & (y >= limit)]
        if wet.size:
            output[position] = wet.mean()
    return _result(ids, output, ~np.isnan(output))


def cdd(values, groups, *, wet_threshold) -> dict:
    """Maximum number of consecutive dry days (< threshold) per year."""
    y, labels, ids = _prepare(values, groups)
    limit = scalar(wet_threshold, 'wet_threshold', True)
    output = np.zeros(len(ids))
    for position, g in enumerate(ids):
        best = run = 0
        for dry in (y[labels == g] < limit):
            run = run + 1 if dry else 0
            best = max(best, run)
        output[position] = best
    return _result(ids, output)


def r95ptot(values, groups, baseline, *, wet_threshold, percentile=95.0) -> dict:
    """Total precipitation on days above the base-period percentile of wet days (mm).

    The threshold is the `percentile` of wet-day amounts (>= wet_threshold)
    computed ONLY on days where the boolean `baseline` mask is true.
    """
    y, labels, ids = _prepare(values, groups)
    limit = scalar(wet_threshold, 'wet_threshold', True)
    q = scalar(percentile, 'percentile', True)
    mask = np.asarray(baseline)
    if mask.shape != y.shape or mask.dtype != np.bool_:
        raise ValueError('baseline must be a boolean mask with one entry per day')
    reference = y[mask & (y >= limit)]
    if reference.size < 2:
        raise ValueError('The baseline has too few wet days to estimate the percentile')
    threshold = float(np.percentile(reference, q))
    output = np.array([y[(labels == g) & (y > threshold)].sum() for g in ids])
    return _result(ids, output, threshold=threshold, n_reference_wet_days=int(reference.size))


def warm_spell_days(values, thresholds, groups, *, min_duration) -> dict:
    """Days per year inside spells of >= min_duration consecutive days above `thresholds`.

    `thresholds` is an array with one (e.g. calendar-day percentile) threshold
    per day, calculated by the caller on a base period.
    """
    y, labels, ids = _prepare(values, groups, precipitation=False)
    limit = array(thresholds, 'thresholds')
    if limit.shape != y.shape:
        raise ValueError('thresholds must have one entry per day')
    needed = integer(min_duration, 'min_duration')
    output = np.zeros(len(ids))
    for position, g in enumerate(ids):
        hot = y[labels == g] > limit[labels == g]
        run = 0
        for flag in np.append(hot, False):
            if flag:
                run += 1
            else:
                if run >= needed:
                    output[position] += run
                run = 0
    return _result(ids, output)
