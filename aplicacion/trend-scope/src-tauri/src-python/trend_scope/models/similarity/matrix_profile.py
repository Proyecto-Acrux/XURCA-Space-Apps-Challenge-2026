"""Exact bounded self-join matrix profile, shared by similarity/change detection.

Direct distances are used as a transparent small-data reference, not advertised
as STOMP or SCRIMP++. O(n_windows^2 * window); no approximate nearest neighbors.
"""
import numpy as np
from ..numeric import finite, integer, temporal


def matrix_profile(times, values, *, window: int, exclusion=None, max_pairs: int = 100_000) -> dict:
    _,y=temporal(times,values,regular=True)
    m=integer(window,'window',2)
    radius=int(np.ceil(m/4)) if exclusion is None else integer(exclusion,'exclusion',0)
    n=len(y)-m+1
    if n<2 or n*(n-1)//2>integer(max_pairs,'max_pairs'):
        raise ValueError('Insufficient windows or matrix-profile pair budget exceeded')
    windows=np.lib.stride_tricks.sliding_window_view(y,m).copy()
    # Scale each window before centering, preserving z-normalized distances.
    scale=np.max(abs(windows),axis=1)
    if np.any(scale==0):
        raise ValueError('Constant windows have undefined z-normalization')
    windows/=scale[:,None]
    windows-=windows.mean(axis=1,keepdims=True)
    sd=windows.std(axis=1)
    if np.any(sd==0):
        raise ValueError('Constant windows have undefined z-normalization')
    windows/=sd[:,None]
    profile=np.full(n,np.inf)
    neighbors=np.full(n,-1,dtype=int)
    for i in range(n):
        for j in range(i+radius+1,n):
            distance=float(np.linalg.norm(windows[i]-windows[j]))
            if distance<profile[i]:
                profile[i],neighbors[i]=distance,j
            if distance<profile[j]:
                profile[j],neighbors[j]=distance,i
    if np.any(neighbors<0):
        raise ValueError('Exclusion leaves a window without an admissible neighbor')
    return {'profile':finite(profile),'neighbor_indices':neighbors,'window':m,'exclusion':radius,
            'normalization':'per-window population standard deviation',
            'warnings':['Large distances indicate unusual shapes, not emergency events; constant windows are rejected explicitly.']}
