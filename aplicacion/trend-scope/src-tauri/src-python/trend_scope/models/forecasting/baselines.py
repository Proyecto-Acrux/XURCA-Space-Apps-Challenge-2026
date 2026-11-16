"""W07: forecast baselines. They use only the data they receive (the past)."""
import numpy as np

from ..numeric import array, finite, integer

VERSION = '1.0.0-candidate'


def climatology_forecast(values, groups, future_groups, *, min_count) -> dict:
    """Forecast each future step with the mean of past observations of its group.

    `groups` are integer labels (e.g. calendar month) of the observations;
    `future_groups` the labels of the steps to forecast. Every requested group
    needs at least `min_count` past observations or ValueError is raised.
    This is the reference any model must beat: it ignores trends and recent
    anomalies. O(n + horizon). Version 1.0.0-candidate.
    """
    y = array(values, 'values')
    labels = np.asarray(groups)
    future = np.asarray(future_groups)
    if labels.shape != y.shape or labels.dtype.kind not in 'iu':
        raise ValueError('groups must be one integer label per observation')
    if future.ndim != 1 or not future.size or future.dtype.kind not in 'iu':
        raise ValueError('future_groups must be a nonempty 1D integer array')
    needed = integer(min_count, 'min_count')
    means = {}
    for label in np.unique(future):
        sample = y[labels == label]
        if sample.size < needed:
            raise ValueError(f'Group {int(label)} has {sample.size} observations; min_count={needed}')
        means[int(label)] = float(sample.mean())
    output = np.array([means[int(label)] for label in future])
    finite(output)
    return {'values': output, 'group_ids': np.array(sorted(means)), 'uncertainty': 'not_estimated',
            'warnings': ['Climatological reference: ignores trends and recent anomalies.']}


def persistence_forecast(values, *, horizon) -> dict:
    """Repeat the last observed value for every step of the horizon."""
    y = array(values, 'values')
    steps = integer(horizon, 'horizon')
    return {'values': np.full(steps, y[-1]), 'uncertainty': 'not_estimated',
            'warnings': ['Persistence reference: assumes no change from the last observation.']}
