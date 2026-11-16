"""W17: descriptive series diagnostics used to choose among trend tests.

Both functions are diagnostics, not hypothesis tests. Inputs follow the engine
convention: finite real arrays, strictly increasing numeric times, no masks.
"""
import numpy as np

from ..numeric import finite, temporal

VERSION = '1.0.0-candidate'


def _group_labels(groups, shape) -> np.ndarray:
    labels = np.asarray(groups)
    if labels.shape != shape or labels.dtype.kind not in 'iu':
        raise ValueError('groups must be one integer label per observation')
    return labels


def lag1_autocorrelation(times, values, *, groups=None) -> dict:
    """Lag-1 autocorrelation of a regular series, optionally without group means.

    r1 = sum(c[t]*c[t+1]) / sum(c[t]^2), with c the values minus the overall
    mean, or minus the mean of each group when `groups` (integer labels, e.g.
    calendar month) is given. `threshold` = 1.96/sqrt(n) is the usual
    large-sample band for white noise; `exceeds_threshold` only says that |r1|
    is outside that band. It is not a test of serial independence, and it is
    unreliable for short series. Requires n >= 4 and a regular time grid.
    A constant series (after removing group means) raises ValueError.
    O(n) time and memory. Version 1.0.0-candidate.
    """
    _, y = temporal(times, values, regular=True, minimum=4)
    n = len(y)
    if groups is None:
        centered = y - y.mean()
    else:
        labels = _group_labels(groups, y.shape)
        centered = y.copy()
        for label in np.unique(labels):
            selected = labels == label
            centered[selected] = y[selected] - y[selected].mean()
    denominator = float(np.dot(centered, centered))
    if denominator == 0:
        raise ValueError('Constant series has undefined autocorrelation')
    r1 = float(np.dot(centered[:-1], centered[1:]) / denominator)
    threshold = float(1.96 / np.sqrt(n))
    finite([r1, threshold])
    return {'r1': r1, 'n': n, 'threshold': threshold,
            'exceeds_threshold': bool(abs(r1) > threshold),
            'deseasonalized': groups is not None, 'uncertainty': 'not_estimated',
            'warnings': ['Descriptive diagnostic, not a test of serial independence.']}


def seasonal_strength(times, values, groups) -> dict:
    """Fraction of variance explained by the group means (0 = none, 1 = all).

    strength = 1 - SSW/SST, where SSW is the within-group sum of squares and
    SST the total sum of squares. `groups` are integer labels (e.g. calendar
    month). It measures how much of the sample variance a repeating cycle
    accounts for; it does not establish that the cycle is statistically
    significant. A constant series raises ValueError. O(n). Version 1.0.0-candidate.
    """
    _, y = temporal(times, values, minimum=2)
    labels = _group_labels(groups, y.shape)
    total = float(np.sum((y - y.mean()) ** 2))
    if total == 0:
        raise ValueError('Constant series has undefined seasonal strength')
    within = 0.0
    unique = np.unique(labels)
    for label in unique:
        sample = y[labels == label]
        within += float(np.sum((sample - sample.mean()) ** 2))
    strength = 1.0 - within / total
    finite([strength])
    return {'strength': float(strength), 'n': len(y), 'n_groups': int(len(unique)),
            'uncertainty': 'not_estimated',
            'warnings': ['Share of sample variance explained by group means; not a significance test.']}
