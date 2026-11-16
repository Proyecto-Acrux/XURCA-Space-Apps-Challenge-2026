"""W01 descriptive baseline statistics and anomalies, version 1.0.0-candidate."""
from collections.abc import Mapping

import numpy as np

from ..numeric import array, finite, integer

# Normal-consistency factor: MAD * 1.4826 estimates the standard deviation.
ROBUST_Z_CONSISTENCY = 1.4826


def _labels(groups, shape) -> np.ndarray:
    if np.ma.isMaskedArray(groups):
        raise ValueError('groups must not be masked')
    labels = np.asarray(groups)
    if labels.shape != shape or labels.dtype.kind not in 'iu':
        raise ValueError('groups must contain one integer label per observation')
    return labels


def climatology(values, groups, baseline, *, min_count) -> dict:
    """Summarize only baseline observations within each supplied integer group.

    Equal observation weights; std = sqrt(mean((x-mean)**2)) (ddof=0),
    MAD = median(abs(x-median)), without normal-consistency scaling.
    These are descriptive population moments, not uncertainty estimates.
    Statistics retain the input unit; counts and labels are dimensionless.
    The caller supplies the baseline: this does not decide its validity or
    infer calendar groups. Formula reference: models/AGENTS.md, W01.
    O(n log n) grouping time, O(n) memory; no pairwise allocation.

    Example: climatology([1, 3], [0, 0], [True, True], min_count=2)
    has mean=2, std=1, median=2, mad=1 and count=2.
    """
    y = array(values, 'values')
    labels = _labels(groups, y.shape)
    minimum = integer(min_count, 'min_count')
    if np.ma.isMaskedArray(baseline):
        raise ValueError('baseline must not be masked')
    mask = np.asarray(baseline)
    if mask.shape != y.shape or mask.dtype.kind != 'b':
        raise ValueError('baseline must be a boolean mask matching values')
    ids, inverse = np.unique(labels, return_inverse=True)
    order = np.argsort(inverse[mask], kind='stable')
    selected = y[mask][order]
    counts = np.bincount(inverse[mask], minlength=len(ids))
    if np.any(counts < minimum):
        group = ids[np.flatnonzero(counts < minimum)[0]]
        raise ValueError(f'Group {group} has fewer than min_count={minimum} baseline observations')
    result = {key: np.empty(len(ids)) for key in ('mean', 'std', 'median', 'mad')}
    offset = 0
    try:
        with np.errstate(over='raise', invalid='raise', divide='raise'):
            for i, count in enumerate(counts):
                sample = selected[offset:offset + count]
                offset += count
                result['mean'][i] = sample.mean()
                result['std'][i] = sample.std(ddof=0)
                result['median'][i] = np.median(sample)
                result['mad'][i] = np.median(abs(sample - result['median'][i]))
            for key in result:
                finite(result[key], key)
    except FloatingPointError as error:
        raise ValueError('Baseline statistics overflow; rescale values') from error
    return dict(result, group_ids=ids, count=counts, uncertainty='not_estimated',
                warnings=['Baseline suitability is caller-defined; uncertainty is not estimated.'])


def anomalies(values, groups, reference, *, kind) -> dict:
    """Compare observations to an explicit climatology reference (W01).

    absolute = x-mean; percent = 100*(x-mean)/mean;
    standardized = (x-mean)/std; robust_z = (x-median)/(1.4826*MAD).
    The reference MAD stays unscaled (descriptive, in variable units); the
    normal-consistency factor 1.4826 is applied only here, so robust_z is
    comparable with a standard z for normally distributed data.
    Units are input units, percent, or dimensionless respectively. Percent
    requires a meaningful ratio-scale variable; no unit conversion is inferred.
    This does not select a valid baseline, infer trends or estimate uncertainty.
    O(g log g + n log g) time and O(n+g) memory for g reference groups.
    """
    y = array(values, 'values')
    labels = _labels(groups, y.shape)
    if not isinstance(kind, str) or kind not in ('absolute', 'percent', 'standardized', 'robust_z'):
        raise ValueError('kind must be absolute, percent, standardized or robust_z')
    if not isinstance(reference, Mapping) or 'group_ids' not in reference:
        raise ValueError('reference must be a climatology result')
    raw_ids = np.asarray(reference['group_ids'])
    ids = _labels(reference['group_ids'], raw_ids.shape)
    if ids.ndim != 1 or not ids.size or len(np.unique(ids)) != len(ids):
        raise ValueError('reference group_ids must be nonempty, one-dimensional and unique')
    stats = {}
    for key in ('mean', 'std', 'median', 'mad', 'count'):
        if key not in reference:
            raise ValueError(f'reference requires {key}')
        stats[key] = array(reference[key], f'reference {key}')
        if stats[key].shape != ids.shape:
            raise ValueError(f'reference {key} must match group_ids')
    if np.any(stats['std'] < 0) or np.any(stats['mad'] < 0):
        raise ValueError('reference std and mad must be nonnegative')
    if np.any(stats['count'] < 1) or np.any(stats['count'] != np.floor(stats['count'])):
        raise ValueError('reference count must contain positive integers')
    lookup = {int(label): i for i, label in enumerate(ids)}
    try:
        indices = np.array([lookup[int(label)] for label in labels])
    except KeyError as error:
        raise ValueError(f'Group {error.args[0]} is missing from reference') from error
    center = stats['median' if kind == 'robust_z' else 'mean'][indices]
    denominator = {'percent': 'mean', 'standardized': 'std', 'robust_z': 'mad'}.get(kind)
    if denominator and np.any(stats[denominator][indices] == 0):
        raise ValueError(f'{kind} requires nonzero reference {denominator} for every requested group')
    try:
        with np.errstate(over='raise', invalid='raise', divide='raise'):
            output = y - center
            if denominator:
                scale = stats[denominator][indices]
                if kind == 'robust_z':
                    scale = scale * ROBUST_Z_CONSISTENCY
                output = output / scale
            if kind == 'percent':
                output = output * 100
            finite(output)
    except FloatingPointError as error:
        raise ValueError('Anomalies overflow; rescale values') from error
    return {'values': output, 'kind': kind, 'uncertainty': 'not_estimated',
            'warnings': ['Descriptive anomalies; baseline suitability and physical interpretation require review.']}
