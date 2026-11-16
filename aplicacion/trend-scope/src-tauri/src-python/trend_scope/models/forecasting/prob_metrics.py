"""W13: probabilistic forecast metrics."""
import numpy as np

from ..numeric import array, finite, integer

VERSION = '1.0.0-candidate'
MAX_CRPS_CELLS = 20_000_000


def _pair(probabilities, outcomes):
    p = array(probabilities, 'probabilities')
    o = array(outcomes, 'outcomes')
    if p.shape != o.shape:
        raise ValueError('probabilities and outcomes must have the same shape')
    if np.any((p < 0) | (p > 1)):
        raise ValueError('probabilities must lie in [0, 1]')
    if not np.isin(o, (0.0, 1.0)).all():
        raise ValueError('outcomes must be 0 or 1')
    return p, o


def brier_score(probabilities, outcomes) -> dict:
    """Mean squared difference between forecast probability and the 0/1 outcome."""
    p, o = _pair(probabilities, outcomes)
    return {'brier': float(np.mean((p - o) ** 2)), 'n': int(p.size), 'uncertainty': 'not_estimated',
            'warnings': ['Lower is better; compare against a reference such as climatological frequency.']}


def brier_skill_score(probabilities, outcomes, reference_probabilities) -> dict:
    """1 - Brier / Brier_reference. Not computed when the reference Brier is zero."""
    score = brier_score(probabilities, outcomes)['brier']
    reference = brier_score(reference_probabilities, outcomes)['brier']
    skill = None if reference == 0 else float(1 - score / reference)
    return {'skill': skill, 'brier': score, 'brier_reference': reference, 'uncertainty': 'not_estimated',
            'warnings': ['Positive skill means better than the reference.'] if skill is not None
            else ['Reference Brier score is zero: skill is undefined.']}


def reliability_table(probabilities, outcomes, *, bins) -> dict:
    """Mean forecast probability vs observed frequency in equal-width bins of [0, 1]."""
    p, o = _pair(probabilities, outcomes)
    count = integer(bins, 'bins')
    edges = np.linspace(0, 1, count + 1)
    index = np.minimum(np.digitize(p, edges[1:-1]), count - 1)
    n = np.bincount(index, minlength=count)
    forecast = np.full(count, np.nan)
    observed = np.full(count, np.nan)
    for b in np.flatnonzero(n):
        forecast[b], observed[b] = p[index == b].mean(), o[index == b].mean()
    return {'bin_edges': edges, 'count': n, 'mean_forecast': forecast, 'observed_frequency': observed,
            'uncertainty': 'not_estimated',
            'warnings': ['Bins with few cases are noisy; empty bins are NaN.']}


def crps_ensemble(members, observations) -> dict:
    """Continuous ranked probability score of an ensemble (fair-free estimator).

    `members` has shape (n, m): m ensemble members for each of n observations.
    CRPS = mean|X - y| - 0.5 * mean|X - X'| per observation; units are those of
    the variable. Cost O(n*m^2), bounded by an explicit cell limit.
    """
    x = array(members, 'members', ndim=2)
    y = array(observations, 'observations')
    if x.shape[0] != y.size:
        raise ValueError('members needs one row per observation')
    if x.shape[0] * x.shape[1] ** 2 > MAX_CRPS_CELLS:
        raise ValueError('CRPS work budget exceeded; reduce members or observations')
    first = np.mean(np.abs(x - y[:, None]), axis=1)
    second = np.mean(np.abs(x[:, :, None] - x[:, None, :]), axis=(1, 2))
    scores = first - 0.5 * second
    finite(scores)
    return {'crps': float(scores.mean()), 'per_observation': scores, 'n': int(y.size),
            'uncertainty': 'not_estimated', 'warnings': ['Lower is better.']}
