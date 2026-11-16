"""W11: moving-block bootstrap confidence intervals and paired differences."""
import numpy as np

from ..numeric import array, finite, integer, scalar

VERSION = '1.0.0-candidate'
MAX_WORK = 50_000_000


def _blocks(n: int, block_length: int, rng) -> np.ndarray:
    count = -(-n // block_length)
    starts = rng.integers(0, n - block_length + 1, size=count)
    return np.concatenate([np.arange(s, s + block_length) for s in starts])[:n]


def block_bootstrap_ci(values, statistic, *, block_length, n_resamples, confidence=0.95, seed) -> dict:
    """Percentile interval of `statistic` under a moving-block bootstrap.

    `statistic` is a callable mapping a 1D array to a finite float (never a
    name). `block_length` and `seed` are mandatory: blocks preserve serial
    dependence only up to their length. Percentile intervals can be inaccurate
    for short series; the interval describes sampling variability of the
    statistic, not predictions. Reproducible for a given seed.
    """
    y = array(values, 'values', minimum=4)
    length = integer(block_length, 'block_length')
    draws = integer(n_resamples, 'n_resamples', 10)
    level = scalar(confidence, 'confidence')
    generator = np.random.default_rng(integer(seed, 'seed', 0))
    if not callable(statistic) or not 0 < level < 1 or length > len(y):
        raise ValueError('statistic must be callable, confidence in (0,1) and block_length <= n')
    if draws * len(y) > MAX_WORK:
        raise ValueError('Bootstrap work budget exceeded')
    estimate = float(statistic(y))
    samples = np.empty(draws)
    for i in range(draws):
        samples[i] = statistic(y[_blocks(len(y), length, generator)])
    finite(np.append(samples, estimate), 'bootstrap statistic')
    tail = (1 - level) / 2
    lower, upper = np.quantile(samples, [tail, 1 - tail])
    return {'estimate': estimate, 'lower': float(lower), 'upper': float(upper), 'confidence': level,
            'n_resamples': draws, 'block_length': length, 'seed': int(seed), 'method': 'moving_block_percentile',
            'uncertainty': 'bootstrap_percentile_interval',
            'warnings': ['Block length controls how much serial dependence is preserved; results depend on it.']}


def paired_difference(first, second, *, block_length, n_resamples, confidence=0.95, seed) -> dict:
    """Mean of first - second with a moving-block bootstrap interval (series paired by position)."""
    a, b = array(first, 'first', minimum=4), array(second, 'second', minimum=4)
    if a.shape != b.shape:
        raise ValueError('first and second must have the same length (paired by position)')
    output = block_bootstrap_ci(a - b, np.mean, block_length=block_length, n_resamples=n_resamples,
                                confidence=confidence, seed=seed)
    output['mean_difference'] = output.pop('estimate')
    return output
