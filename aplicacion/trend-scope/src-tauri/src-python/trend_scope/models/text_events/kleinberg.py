"""Kleinberg exponential-gap automaton (KDD 2002), exact finite-state Viterbi."""
import math
import numpy as np
from ..numeric import array, finite, scalar


def kleinberg(event_times, *, rate_multiplier: float = 2., gamma: float = 1.) -> dict:
    """Infer hierarchical burst levels from explicitly selected event arrival times.

    Rates alpha_i=s^i/mean_gap; upward transition penalty (i-j)*gamma*log(n).
    No text extraction, duplicate aggregation or binning occurs here.
    """
    t=array(event_times,'event_times',minimum=3)
    s=scalar(rate_multiplier,'rate_multiplier',True)
    gamma=scalar(gamma,'gamma',True)
    if s<=1:
        raise ValueError('rate_multiplier must exceed one')
    with np.errstate(over='raise',invalid='raise',divide='raise'):
        gaps=np.diff(t)
        if np.any(gaps<=0):
            raise ValueError('Event arrivals must strictly increase')
        mean=float(gaps.mean())
        levels=int(math.ceil(math.log(mean/float(gaps.min()))/math.log(s)))+1
        if levels>64 or len(gaps)*levels*levels>2_000_000:
            raise ValueError('Kleinberg state/work budget exceeded')
        rates=finite(np.exp(np.arange(levels)*math.log(s))/mean)
        emission=finite(gaps[:,None]*rates[None,:]-np.log(rates)[None,:])
    penalty=gamma*math.log(len(gaps))
    previous=np.full(levels,np.inf); previous[0]=0.
    back=np.empty((len(gaps),levels),dtype=int)
    for i in range(len(gaps)):
        current=np.empty(levels)
        for target in range(levels):
            costs=previous+penalty*np.maximum(0,target-np.arange(levels))
            back[i,target]=np.argmin(costs)
            current[target]=costs[back[i,target]]+emission[i,target]
        previous=current
    state=int(np.argmin(previous))
    objective=float(finite(previous[state]))
    states=np.empty(len(gaps),dtype=int)
    for i in range(len(gaps)-1,-1,-1):
        states[i]=state
        state=back[i,state]
    bursts=[]
    for level in range(1,levels):
        active=np.r_[False,states>=level,False]
        starts=np.flatnonzero(~active[:-1]&active[1:])
        ends=np.flatnonzero(active[:-1]&~active[1:])
        bursts.extend({'level':level,'start':float(t[a]),'end':float(t[b])} for a,b in zip(starts,ends))
    return {'gap_states':states,'state_rates':rates,'bursts':bursts,'objective':objective,
            'warnings':['Exponential waiting-time model for event arrivals; not applicable directly to continuous environmental measurements.']}
