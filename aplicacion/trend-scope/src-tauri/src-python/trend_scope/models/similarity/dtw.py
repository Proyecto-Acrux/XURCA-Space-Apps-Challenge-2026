"""Exact scalar-series DTW distance with an optional Sakoe-Chiba band."""
import numpy as np
from numba import njit
from ..numeric import array, finite, integer


@njit(cache=True)
def _distance(a, b, radius):
    previous = np.full(len(b)+1, np.inf)
    previous[0] = 0.
    for i in range(1,len(a)+1):
        current = np.full(len(b)+1,np.inf)
        for j in range(max(1,i-radius), min(len(b),i+radius)+1):
            current[j] = (a[i-1]-b[j-1])**2 + min(previous[j],current[j-1],previous[j-1])
        previous = current
    return np.sqrt(previous[-1])


def dtw(first, second, *, radius=None, max_cells: int = 2_000_000) -> dict:
    """Square-root accumulated squared cost; no silent normalization or alignment of units."""
    a, b = array(first,'first'), array(second,'second')
    r = max(len(a),len(b)) if radius is None else integer(radius,'radius',0)
    if r < abs(len(a)-len(b)):
        raise ValueError('Band excludes every complete alignment')
    if len(a)*min(len(b),2*r+1) > integer(max_cells,'max_cells'):
        raise ValueError('DTW cell budget exceeded')
    distance = float(finite(_distance(a,b,r)))
    return {'distance': distance, 'radius': r,
            'warnings': ['Inputs must have compatible physical units; warping does not imply causal alignment.']}
