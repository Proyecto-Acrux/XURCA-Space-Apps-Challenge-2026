"""W18: descriptive statistics of the observations received."""
import numpy as np

from ..numeric import finite, scalar, temporal

VERSION = '1.0.0-candidate'


def describe(times, values, *, quantiles=(0.05, 0.25, 0.5, 0.75, 0.95)) -> dict:
    """Count, mean, sample standard deviation, extremes and quantiles.

    `std` uses ddof=1 and is None for a single observation. Quantiles use
    numpy's linear interpolation. All values except `n` are in the unit of the
    variable. The statistics describe the observations received: they are not
    an area average, an annual total or an estimate with uncertainty.
    Times must be strictly increasing; irregular spacing is allowed.
    O(n log n) time, O(n) memory. Version 1.0.0-candidate.
    """
    t, y = temporal(times, values, minimum=1)
    levels = [scalar(q, 'quantile') for q in quantiles]
    if not levels or any(not 0 < q < 1 for q in levels):
        raise ValueError('quantiles must be strictly between 0 and 1')
    with np.errstate(over='raise', invalid='raise'):
        mean = float(np.mean(y))
        std = float(np.std(y, ddof=1)) if len(y) > 1 else None
        values_q = np.quantile(y, levels)
    finite([mean])
    finite(values_q)
    if std is not None:
        finite([std])
    return {'n': int(len(y)), 'mean': mean, 'std': std,
            'minimum': float(y.min()), 'maximum': float(y.max()),
            'quantile_levels': np.asarray(levels), 'quantile_values': values_q,
            'time_start': float(t[0]), 'time_end': float(t[-1]),
            'uncertainty': 'not_estimated',
            'warnings': ['Describes the observations received; not an area average or an annual total.']}


def analyze_describe(data, request):
    """Adapt W18 to the existing scientific result contract without changing it."""
    from ..contracts import AnalysisResult

    variable = data.variables[request.variable]
    if data.time is None or (variable.invalid is not None and variable.invalid.any()):
        raise ValueError('Explicit time coordinates and unmasked observations are required')
    payload = describe(data.time.values, variable.values, **dict(request.parameters))
    unit = variable.unit
    return AnalysisResult(
        request.analysis_id, 'describe', VERSION, data.dataset_id, request.variable,
        'completed', 'summary', dict(request.parameters), payload,
        {'n': '1', 'mean': unit, 'std': unit, 'minimum': unit, 'maximum': unit,
         'quantile_levels': '1', 'quantile_values': unit, 'time_start': data.time.unit,
         'time_end': data.time.unit},
        tuple(payload['warnings']), data.provenance,
        {'n_observations': len(data.time.values), 'time_start': data.time.values[0],
         'time_end': data.time.values[-1], 'time_origin': data.time.origin,
         'time_unit': data.time.unit, 'calendar': data.time.calendar,
         'value_unit': unit, 'quality': data.quality},
        data.transformations, uncertainty=payload['uncertainty'])
