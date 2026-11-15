"""Explicit lossy representations: PAA by samples, LTTB for visualization only."""
import numpy as np
from ..numeric import finite, integer, temporal


def paa(times, values, *, segments: int) -> dict:
    """Fractional sample-overlap PAA; equal bin widths in sample index, regular time."""
    t, y = temporal(times, values, regular=True)
    m = integer(segments, 'segments')
    if m > len(y):
        raise ValueError('Cannot have more segments than samples')
    edges = np.linspace(0., len(y), m+1)
    means, centers = np.empty(m), np.empty(m)
    for k, (left,right) in enumerate(zip(edges[:-1], edges[1:])):
        indices = np.arange(int(np.floor(left)), int(np.ceil(right)))
        weights = np.minimum(indices+1,right)-np.maximum(indices,left)
        weights /= right-left
        means[k], centers[k] = np.dot(weights,y[indices]), np.dot(weights,t[indices])
    return {'times': finite(centers), 'values': finite(means), 'sample_edges': edges,
            'warnings': ['PAA loses within-bin variability; original observations remain authoritative.']}


def lttb(times, values, *, samples: int) -> dict:
    """Largest Triangle Three Buckets; returns original selected samples, no fitting."""
    t, y = temporal(times, values)
    m = integer(samples, 'samples', 3)
    n = len(y)
    if m >= n:
        selected = np.arange(n)
    else:
        # Affine normalization preserves triangle ordering and limits overflow.
        xscale, yscale = max(abs(t).max(),1.), max(abs(y).max(),1.)
        x, z = t/xscale, y/yscale
        every = (n-2)/(m-2)
        selected = [0]
        a = 0
        for i in range(m-2):
            average_start = int(np.floor((i+1)*every))+1
            average_end = min(int(np.floor((i+2)*every))+1,n)
            avgx, avgy = x[average_start:average_end].mean(), z[average_start:average_end].mean()
            start = int(np.floor(i*every))+1
            end = min(int(np.floor((i+1)*every))+1,n-1)
            area = abs((x[a]-avgx)*(z[start:end]-z[a])-(x[a]-x[start:end])*(avgy-z[a]))
            a = start+int(np.argmax(area))
            selected.append(a)
        selected.append(n-1)
        selected = np.asarray(selected)
    return {'indices': selected, 'times': t[selected], 'values': y[selected],
            'warnings': ['Visualization only: do not infer trends or anomalies from decimated data.']}
