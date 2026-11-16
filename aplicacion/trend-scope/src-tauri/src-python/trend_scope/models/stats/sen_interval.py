"""W02: Theil-Sen slope with a Kendall rank confidence interval."""
import numpy as np
from scipy.special import ndtri

from ..numeric import finite, integer, scalar, temporal


def sen_interval(times, values, *, confidence: float = 0.95,
                 max_pairs: int = 2_000_000) -> dict:
    """Estimate a slope and its two-sided asymptotic rank interval.

    Reference: Sen (1968), Estimates of the regression coefficient based on
    Kendall's tau, JASA 63, 1379-1389, equation 2.6. For n observations and
    N=n*(n-1)/2 slopes, Var(S)=[n*(n-1)*(2*n+5)-sum(k*(k-1)*(2*k+5))]/18,
    where k are value-tie counts (time ties are rejected). Sorted slope ranks
    use the normal quantile and nearest-integer rounding, clipped to [0,N-1],
    following scipy.stats.theilslopes. confidence is a coverage in (0,1),
    including below 0.5; it is never reinterpreted as a significance level.

    Requires finite real observations at strictly increasing numeric times;
    irregular spacing is allowed. slope/lower/upper have value/time units.
    Assumes a common linear slope and independent errors; no seasonal or
    autocorrelation adjustment, causal claim, or prediction interval. Small
    samples and constant data can give degenerate bounds, not proof of certainty.
    Cost: O(N log N) time, O(N+n) memory; max_pairs bounds N before allocation.
    Version: 1.0.0-candidate. Example: sen_interval([0,1,2], [1,3,5])
    returns slope=lower=upper=2.
    """
    level = scalar(confidence, 'confidence')
    if not 0 < level < 1:
        raise ValueError('confidence must be strictly between 0 and 1')
    limit = integer(max_pairs, 'max_pairs')
    try:
        t, y = temporal(times, values, minimum=2)
        n = len(y)
        pairs = n*(n-1)//2
        if pairs > limit:
            raise ValueError('Sen interval pair budget exceeded; increase max_pairs explicitly')
        slopes = np.empty(pairs)
        offset = 0
        with np.errstate(over='raise', invalid='raise', divide='raise'):
            for i in range(n-1):
                count = n-i-1
                slopes[offset:offset+count] = (y[i+1:]-y[i])/(t[i+1:]-t[i])
                offset += count
            finite(slopes, 'pairwise slopes')
            slopes.sort()
            middle = pairs//2
            # Halve before adding to avoid overflowing a representable median.
            slope = (slopes[middle] if pairs % 2 else
                     slopes[middle-1]/2 + slopes[middle]/2)
            _, counts = np.unique(y, return_counts=True)
            ties = sum(int(k)*(int(k)-1)*(2*int(k)+5) for k in counts)
            variance = (n*(n-1)*(2*n+5)-ties)/18.
            z = -ndtri((1-level)/2)
            spread = z*np.sqrt(variance)
            lower_rank = max(int(np.round((pairs-spread)/2))-1, 0)
            upper_rank = min(int(np.round((pairs+spread)/2)), pairs-1)
            lower, upper = slopes[lower_rank], slopes[upper_rank]
            finite([slope, lower, upper])
    except FloatingPointError as error:
        raise ValueError('Sen interval arithmetic overflow; rescale times or values') from error
    return {'slope': float(slope), 'lower': float(lower), 'upper': float(upper),
            'confidence': level, 'n_pairs': pairs, 'method': 'kendall_rank_tie_corrected',
            'uncertainty': 'asymptotic_confidence_interval',
            'warnings': [
                'The interval assumes serial independence; with autocorrelation it is too narrow.',
                'Normal rank approximation; small samples or ties can give degenerate bounds and inaccurate coverage.',
                'Seasonality is not removed; this is not a prediction interval.']}


def analyze_sen_interval(data, request):
    """Adapt W02 to the existing scientific result contract without changing it."""
    from ..contracts import AnalysisResult

    variable = data.variables[request.variable]
    if data.time is None or (variable.invalid is not None and variable.invalid.any()):
        raise ValueError('Explicit time coordinates and unmasked observations are required')
    payload = sen_interval(data.time.values, variable.values, **dict(request.parameters))
    slope_unit = f'({variable.unit})/({data.time.unit})'
    return AnalysisResult(
        request.analysis_id, 'sen_interval', '1.0.0-candidate', data.dataset_id,
        request.variable, 'completed', 'estimate', dict(request.parameters), payload,
        {'slope': slope_unit, 'lower': slope_unit, 'upper': slope_unit,
         'confidence': '1', 'n_pairs': '1'}, tuple(payload['warnings']), data.provenance,
        {'n_observations': len(data.time.values), 'time_start': data.time.values[0],
         'time_end': data.time.values[-1], 'time_origin': data.time.origin,
         'time_unit': data.time.unit, 'calendar': data.time.calendar,
         'value_unit': variable.unit, 'quality': data.quality},
        data.transformations, uncertainty=payload['uncertainty'])
