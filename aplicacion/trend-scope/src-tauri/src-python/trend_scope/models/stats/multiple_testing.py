"""W06: Benjamini-Hochberg false discovery rate control."""
import numpy as np

from ..numeric import array, scalar

VERSION = '1.0.0-candidate'


def fdr_bh(p_values, *, alpha=0.05) -> dict:
    """Benjamini-Hochberg q-values and rejections.

    q_(i) = min over j >= i of p_(j) * m / j (p sorted ascending), capped at 1;
    `rejected` marks q <= alpha. Controls the expected share of false
    discoveries among the rejected tests under independence or positive
    dependence; it does not make individual p-values causal evidence.
    """
    p = array(p_values, 'p_values')
    level = scalar(alpha, 'alpha')
    if np.any((p < 0) | (p > 1)):
        raise ValueError('p_values must lie in [0, 1]')
    if not 0 < level < 1:
        raise ValueError('alpha must be strictly between 0 and 1')
    m = p.size
    order = np.argsort(p, kind='stable')
    ranked = p[order] * m / np.arange(1, m + 1)
    adjusted = np.minimum.accumulate(ranked[::-1])[::-1]
    q = np.empty(m)
    q[order] = np.minimum(adjusted, 1.0)
    return {'q_values': q, 'rejected': q <= level, 'n_tests': int(m), 'alpha': level,
            'uncertainty': 'not_estimated',
            'warnings': ['Valid under independence or positive dependence of the tests.']}
