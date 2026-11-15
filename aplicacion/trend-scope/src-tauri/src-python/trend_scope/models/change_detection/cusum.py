"""Two-sided tabular CUSUM with explicit physical baseline and thresholds."""
import numpy as np
from numba import njit
from ..numeric import array, finite, scalar


@njit(cache=True)
def _cusum(y, baseline, allowance, threshold):
    high = np.zeros(len(y))
    low = np.zeros(len(y))
    events = np.zeros(len(y), dtype=np.int8)
    upper = lower = 0.
    for i in range(len(y)):
        delta = y[i]-baseline
        upper = max(0., upper+delta-allowance)
        lower = max(0., lower-delta-allowance)
        high[i], low[i] = upper, lower
        if upper > threshold:
            events[i] = 1
            upper = lower = 0.
        elif lower > threshold:
            events[i] = -1
            upper = lower = 0.
    return high, low, events


def cusum(values, *, baseline: float, allowance: float, threshold: float) -> dict:
    """Reset both accumulators after a crossing; detection time is not onset time."""
    y = array(values, 'values')
    baseline = scalar(baseline, 'baseline')
    allowance = scalar(allowance, 'allowance')
    threshold = scalar(threshold, 'threshold', positive=True)
    if allowance < 0:
        raise ValueError('allowance must be nonnegative')
    high, low, events = _cusum(y, baseline, allowance, threshold)
    finite(high); finite(low)
    return {'upper': high, 'lower': low, 'event_indices': np.flatnonzero(events),
            'event_directions': events[events != 0],
            'warnings': ['Thresholds require domain calibration; crossings are not certified emergency alerts.',
                         'Baseline must be specified without using future evaluation data.']}
