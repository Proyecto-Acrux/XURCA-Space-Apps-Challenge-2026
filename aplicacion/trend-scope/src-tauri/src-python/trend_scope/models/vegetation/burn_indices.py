"""W14: burn indices and recovery time.

dNBR is a SPECTRAL change indicator; it is not ecological burn severity
validated in the field. Inputs are surface reflectances (nonnegative) or, for
dnbr/rdnbr, NBR values already computed.
"""
import numpy as np

from ..numeric import array, finite, integer, scalar, temporal

VERSION = '1.0.0-candidate'
RDNBR_MIN_PRE = 1e-3


def nbr(nir, swir) -> dict:
    """Normalized burn ratio (NIR - SWIR) / (NIR + SWIR), dimensionless in [-1, 1]."""
    a, b = array(nir, 'nir', ndim=1), array(swir, 'swir', ndim=1)
    if a.shape != b.shape or np.any(a < 0) or np.any(b < 0):
        raise ValueError('nir and swir must be nonnegative arrays of the same length')
    total = a + b
    if np.any(total == 0):
        raise ValueError('NIR + SWIR must be nonzero for every pixel')
    values = (a - b) / total
    return {'values': finite(values), 'uncertainty': 'not_estimated',
            'warnings': ['Spectral index; atmospheric and cloud effects are not corrected here.']}


def dnbr(pre, post) -> dict:
    """Differenced NBR = NBR_pre - NBR_post (unscaled; multiply by 1000 for the usual integer scale)."""
    a, b = array(pre, 'pre'), array(post, 'post')
    if a.shape != b.shape:
        raise ValueError('pre and post must have the same length')
    return {'values': finite(a - b), 'uncertainty': 'not_estimated',
            'warnings': ['Spectral change indicator, not validated ecological severity.']}


def rdnbr(pre, post) -> dict:
    """Relative dNBR = dNBR / sqrt(|NBR_pre|), with |NBR_pre| floored at 0.001 (Miller & Thode 2007)."""
    a, b = array(pre, 'pre'), array(post, 'post')
    if a.shape != b.shape:
        raise ValueError('pre and post must have the same length')
    floored = np.maximum(np.abs(a), RDNBR_MIN_PRE)
    warnings = ['Spectral change indicator, not validated ecological severity.']
    if np.any(np.abs(a) < RDNBR_MIN_PRE):
        warnings.append('Some pre-fire NBR values were floored at 0.001 before the square root.')
    return {'values': finite((a - b) / np.sqrt(floored)), 'uncertainty': 'not_estimated', 'warnings': warnings}


def recovery_time(times, values, event_index, reference_low, reference_high, *, sustain=1) -> dict:
    """Time after the event at which the series returns into [reference_low, reference_high].

    The first index after `event_index` such that `sustain` consecutive values
    lie inside the reference band. `recovered` is False if that never happens
    (the series may simply be too short). The band is chosen by the caller.
    """
    t, y = temporal(times, values)
    event = integer(event_index, 'event_index', 0)
    low, high = scalar(reference_low, 'reference_low'), scalar(reference_high, 'reference_high')
    keep = integer(sustain, 'sustain')
    if event >= len(y) - 1 or low > high:
        raise ValueError('event_index must leave later observations and reference_low <= reference_high')
    inside = (y >= low) & (y <= high)
    for i in range(event + 1, len(y) - keep + 1):
        if inside[i:i + keep].all():
            return {'recovered': True, 'recovery_index': i, 'recovery_time': float(t[i] - t[event]),
                    'uncertainty': 'not_estimated',
                    'warnings': ['Recovery depends on the chosen reference band and sustain length.']}
    return {'recovered': False, 'recovery_index': None, 'recovery_time': None, 'uncertainty': 'not_estimated',
            'warnings': ['No recovery within the observed series; it may be too short.']}
