from collections import Counter
import numpy as np
import pytest
from trend_scope.models.similarity.matrix_profile import matrix_profile
from trend_scope.models.text_events.streaming import CountMinSketch, MisraGries, SpaceSaving
from trend_scope.models.serialization import dumps


def test_profile_repeated_shapes_and_neighbor_distances():
    y=np.tile([0.,1.,0.,-1.],4)
    result=matrix_profile(np.arange(len(y)),y,window=4)
    np.testing.assert_allclose(result['profile'],0,atol=1e-14)
    windows=np.lib.stride_tricks.sliding_window_view(y,4)
    for i,j in enumerate(result['neighbor_indices']):
        assert abs(i-j)>result['exclusion']
        a=(windows[i]-windows[i].mean())/windows[i].std()
        b=(windows[j]-windows[j].mean())/windows[j].std()
        assert result['profile'][i] == pytest.approx(np.linalg.norm(a-b))
    dumps(result)
    with pytest.raises(ValueError):
        matrix_profile(np.arange(10),np.ones(10),window=3)


def test_stream_summaries_bounds_and_determinism():
    events=list('aaaaabbacdddaeabaaaaa')
    truth=Counter(events)
    cms,cms2=CountMinSketch(),CountMinSketch()
    mg,ss=MisraGries(2),SpaceSaving(2)
    for event in events:
        for method in (cms,cms2,mg,ss):
            method.update(event)
    for key,count in truth.items():
        assert cms.estimate(key)>=count
        assert cms.estimate(key)==cms2.estimate(key)
        assert mg.counts.get(key,0)<=count<=mg.counts.get(key,0)+len(events)//3
    for key,count in ss.counts.items():
        assert count-ss.errors[key]<=truth[key]<=count
    assert len(mg.counts)<=2 and len(ss.counts)<=2
    assert 'a' in mg.counts and 'a' in ss.counts
    dumps(mg.summary()); dumps(ss.summary())
    with pytest.raises(ValueError):
        cms.update(1.2)
