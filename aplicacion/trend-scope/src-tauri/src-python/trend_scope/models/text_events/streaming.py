"""Deterministic insertion-only frequency summaries for explicit string events."""
import hashlib
import math
from ..numeric import integer, scalar


def _key(value):
    if not isinstance(value,str) or not value:
        raise ValueError('Events must be nonempty strings; numeric series need an explicit transformation')
    return value


class CountMinSketch:
    """Nonnegative unit increments; estimate >= true count (no integer overflow)."""
    def __init__(self, epsilon=.01, delta=.01, seed=2026):
        epsilon,delta=scalar(epsilon,'epsilon',True),scalar(delta,'delta',True)
        if epsilon>=1 or delta>=1:
            raise ValueError('epsilon and delta must be below 1')
        self.width=math.ceil(math.e/epsilon)
        self.depth=math.ceil(math.log(1/delta))
        if self.width*self.depth>1_000_000:
            raise ValueError('Sketch counter budget exceeded')
        self.seed=integer(seed,'seed',0)
        self.tables=[[0]*self.width for _ in range(self.depth)]
        self.total=0

    def _indices(self,key):
        encoded=_key(key).encode('utf-8')
        for row in range(self.depth):
            prefix=f'{self.seed}:{row}:'.encode('ascii')
            yield int.from_bytes(hashlib.blake2b(prefix+encoded,digest_size=8).digest(),'big')%self.width

    def update(self,key):
        indices=list(self._indices(key))
        for row,index in enumerate(indices):
            self.tables[row][index]+=1
        self.total+=1

    def estimate(self,key):
        return min(self.tables[row][index] for row,index in enumerate(self._indices(key)))


class MisraGries:
    """At most k candidates; stored counts are lower bounds, error <= N/(k+1)."""
    def __init__(self, capacity=100):
        self.capacity=integer(capacity,'capacity')
        self.counts={}
        self.total=0

    def update(self,key):
        key=_key(key)
        self.total+=1
        if key in self.counts:
            self.counts[key]+=1
        elif len(self.counts)<self.capacity:
            self.counts[key]=1
        else:
            self.counts={k:v-1 for k,v in self.counts.items() if v>1}

    def summary(self):
        return {'counts':dict(self.counts),'total':self.total,'max_underestimate':self.total//(self.capacity+1)}


class SpaceSaving:
    """At most k counters; for retained keys true count lies in [count-error,count]."""
    def __init__(self, capacity=100):
        self.capacity=integer(capacity,'capacity')
        self.counts={}
        self.errors={}
        self.total=0

    def update(self,key):
        key=_key(key)
        self.total+=1
        if key in self.counts:
            self.counts[key]+=1
        elif len(self.counts)<self.capacity:
            self.counts[key],self.errors[key]=1,0
        else:
            smallest=min(self.counts,key=lambda k:(self.counts[k],k))
            count=self.counts.pop(smallest)
            del self.errors[smallest]
            self.counts[key],self.errors[key]=count+1,count

    def summary(self):
        return {'counts':dict(self.counts),'errors':dict(self.errors),'total':self.total}
