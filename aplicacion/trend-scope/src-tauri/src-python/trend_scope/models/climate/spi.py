"""W03: monthly, zero-adjusted gamma SPI (1.0.0-candidate)."""
import warnings

import numpy as np
from scipy.special import gammainc, ndtri
from scipy.stats import gamma

from ..numeric import array, finite, integer, scalar, temporal
from .climatology import _labels


def _window_sums(values: np.ndarray, width: int) -> np.ndarray:
    """O(n) nonnegative window sums using block prefixes/suffixes.

    No subtraction of a whole-series cumulative sum: each returned sum depends
    only on its own window, including in floating-point arithmetic.
    """
    padded = np.pad(values, (0, (-len(values)) % width)).reshape(-1, width)
    prefix = np.cumsum(padded, axis=1).ravel()
    suffix = np.cumsum(padded[:, ::-1], axis=1)[:, ::-1].ravel()
    starts = np.arange(len(values)-width+1)
    ends = starts+width-1
    result = prefix[ends].copy()
    crosses = starts % width != 0
    result[crosses] += suffix[starts[crosses]]
    return result


def spi(totals, groups, calibration, *, scale: int, min_count: int,
        epsilon: float = 1e-6) -> dict:
    """Standardize monthly precipitation totals against an explicit calibration.

    Input is one nonnegative total per consecutive month, never a rate. groups
    are integer calendar months 1..12 cycling consecutively, starting anywhere;
    the caller must establish monthly cadence (this API has no time coordinate).
    scale is a positive number of months. Each trailing sum is labelled by its
    ending month. A calibration window must have ALL constituent months marked
    True, preventing outside-calibration totals from affecting fitted parameters.

    Fit a two-parameter gamma by maximum likelihood (location fixed at zero)
    to positive calibration sums in each month. With q = zero_count/n, use
    H(x) = q + (1-q)*GammaCDF(x), including H(0)=q, then Phi^-1(H).
    Probabilities are clipped strictly inside (epsilon, 1-epsilon). Parameters
    report group_ids, shape, scale (in input depth units), zero_probability,
    n and n_positive. Requires min_count windows AND two distinct positive
    sums in every month; constant/all-zero fits are undefined and rejected.
    Fewer than 20 eligible annual samples in any month emits a warning (Q05),
    not a scientific minimum. No missing-data filling or calendar inference.

    spi is dimensionless. The first scale-1 slots are zero placeholders with
    valid=False: they are NOT neutral SPI observations. calibration_valid records
    the windows actually used. Zero mass makes the SPI distribution discrete;
    exact standard-normal moments are not expected for zero-heavy climates.
    No uncertainty is estimated. Do not sum SPI at different scales. SPI is
    not soil moisture, a forecast, or a test of gamma goodness of fit.

    Reference: WMO (2012), Standardized Precipitation Index User Guide,
    WMO-No. 1090, section 6 (gamma fit and normal transformation).
    https://www.droughtmanagement.info/literature/WMO_standardized_precipitation_index_user_guide_en_2012.pdf
    O(n) aggregation/memory and twelve scalar gamma fits (solver dependent).
    Example: spi(np.arange(1., 49.), np.tile(np.arange(1, 13), 4),
                 np.ones(48, dtype=bool), scale=1, min_count=2).
    """
    width = integer(scale, 'scale')
    minimum = integer(min_count, 'min_count')
    eps = scalar(epsilon, 'epsilon')
    if not 0 < eps < .5 or not 1-eps < 1:
        raise ValueError('epsilon must be between 0 and 0.5 with 1-epsilon representably below 1')
    lo, hi = np.nextafter(eps, 1.), np.nextafter(1-eps, 0.)
    if lo >= hi:
        raise ValueError('epsilon leaves no representable open clipping interval')
    try:
        y = array(totals, 'totals')
        if np.any(y < 0):
            raise ValueError('totals must be nonnegative monthly precipitation depths')
        months = _labels(groups, y.shape)
        if np.any((months < 1) | (months > 12)) or np.any(months[1:] != months[:-1] % 12 + 1):
            raise ValueError('groups must cycle through consecutive calendar months 1..12')
        if np.ma.isMaskedArray(calibration):
            raise ValueError('calibration must not be masked')
        mask = np.asarray(calibration)
        if mask.shape != y.shape or mask.dtype.kind != 'b':
            raise ValueError('calibration must be a boolean mask matching totals')
        if width > len(y):
            raise ValueError('scale exceeds the number of monthly observations')
        with np.errstate(over='raise', invalid='raise', divide='raise'):
            sums = _window_sums(y, width)
            finite(sums, 'precipitation window sums')
            eligible = _window_sums(mask.astype(np.int64), width) == width
            end_months = months[width-1:]
            parameters = {'group_ids': np.arange(1, 13),
                          **{key: np.empty(12) for key in ('shape', 'scale', 'zero_probability')},
                          'n': np.empty(12, dtype=np.int64),
                          'n_positive': np.empty(12, dtype=np.int64)}
            scores = np.empty(len(sums))
            for index, month in enumerate(parameters['group_ids']):
                positions = end_months == month
                sample = sums[positions & eligible]
                if len(sample) < minimum:
                    raise ValueError(f'Group {month} has fewer than min_count={minimum} complete calibration windows')
                positive = sample[sample > 0]
                if len(positive) < 2 or np.all(positive == positive[0]):
                    raise ValueError(f'Group {month} requires at least two distinct positive calibration sums for a gamma fit')
                # Scaling aids the solver without changing the fitted gamma family.
                normalizer = positive.max()
                try:
                    with warnings.catch_warnings():
                        warnings.simplefilter('error', RuntimeWarning)
                        shape, _, normalized_scale = gamma.fit(positive/normalizer, floc=0)
                    gamma_scale = normalized_scale*normalizer
                    finite([shape, gamma_scale], 'gamma parameters')
                    if shape <= 0 or gamma_scale <= 0:
                        raise ValueError('Gamma parameters must be positive')
                except (ValueError, RuntimeError, RuntimeWarning, FloatingPointError) as error:
                    raise ValueError(f'Group {month}: gamma fit failed; check calibration variability and numerical scale') from error
                q = 1-len(positive)/len(sample)
                probability = q+(1-q)*gammainc(shape, sums[positions]/gamma_scale)
                scores[positions] = ndtri(np.clip(probability, lo, hi))
                for key, value in (('shape', shape), ('scale', gamma_scale),
                                   ('zero_probability', q), ('n', len(sample)),
                                   ('n_positive', len(positive))):
                    parameters[key][index] = value
            finite(scores, 'SPI')
    except FloatingPointError as error:
        raise ValueError('SPI arithmetic overflow; rescale precipitation totals') from error
    valid = np.arange(len(y)) >= width-1
    output = np.zeros(len(y))
    output[valid] = scores
    calibration_valid = np.zeros(len(y), dtype=bool)
    calibration_valid[valid] = eligible
    messages = [
        'Calibration suitability and gamma goodness of fit are not established; uncertainty is not estimated.',
        'Do not sum SPI at different scales; SPI is not soil moisture.',
        'Zero placeholders with valid=False are unavailable observations, not neutral SPI.']
    short = parameters['group_ids'][parameters['n'] < 20]
    if short.size:
        messages.append(f'Low robustness: fewer than 20 years of complete calibration windows for months {short.tolist()}.')
    return {'spi': output, 'valid': valid, 'calibration_valid': calibration_valid,
            'scale': width, 'epsilon': eps, 'parameters': parameters,
            'method': 'zero_adjusted_gamma_mle', 'uncertainty': 'not_estimated',
            'warnings': messages}


def analyze_spi(data, request):
    """Registry adapter: month-index time, depth totals, auxiliary variable IDs.

    Time unit must be month/months and step exactly one (within float tolerance).
    Depth units supported without conversion: mm, cm, m. Calendar-month grouping
    and 0/1 calibration variables have unit 1. Numeric encoding is required by
    the existing dataset contract; the direct SPI API uses a boolean mask.
    """
    from ..contracts import AnalysisResult

    variable = data.variables[request.variable]
    if data.time is None or (variable.invalid is not None and variable.invalid.any()):
        raise ValueError('SPI requires explicit time and unmasked monthly totals')
    t, y = temporal(data.time.values, variable.values, regular=True, minimum=24)
    if data.time.unit not in ('month', 'months') or not np.allclose(np.diff(t), 1., rtol=1e-8, atol=0):
        raise ValueError('SPI requires consecutive month-index coordinates in month/months units')
    if variable.unit not in ('mm', 'cm', 'm'):
        raise ValueError('SPI requires monthly precipitation depth totals in mm, cm or m, not rates')
    parameters = dict(request.parameters)
    auxiliary = {}
    for name in ('groups', 'calibration'):
        identifier = parameters.pop(name, None)
        if not isinstance(identifier, str) or identifier not in data.variables:
            raise ValueError(f'Specify {name} as a dataset variable ID')
        value = data.variables[identifier]
        if value.dimensions != ('time',) or value.unit != '1' or (value.invalid is not None and value.invalid.any()):
            raise ValueError(f'{name} must be an unmasked dimensionless time variable')
        auxiliary[name] = value.values
    if not np.isin(auxiliary['calibration'], [0, 1]).all():
        raise ValueError('calibration variable must encode False/True as 0/1')
    if 'scale' not in parameters or 'min_count' not in parameters:
        raise ValueError('Specify scale and min_count explicitly')
    payload = spi(y, auxiliary['groups'], auxiliary['calibration'].astype(bool), **parameters)
    units = {key: '1' for key in ('spi', 'valid', 'calibration_valid', 'epsilon',
             'parameters.group_ids', 'parameters.shape', 'parameters.zero_probability',
             'parameters.n', 'parameters.n_positive')}
    units.update({'scale': data.time.unit, 'parameters.scale': variable.unit})
    return AnalysisResult(request.analysis_id, 'spi', '1.0.0-candidate', data.dataset_id,
        request.variable, 'completed', 'index', dict(request.parameters), payload, units,
        tuple(payload['warnings']), data.provenance,
        {'n_observations': len(t), 'time_start': t[0], 'time_end': t[-1],
         'time_unit': data.time.unit, 'time_origin': data.time.origin, 'calendar': data.time.calendar,
         'value_unit': variable.unit, 'quality': data.quality}, data.transformations)
