import math
import numpy as np
import pytest
from trend_scope.models.optional_methods import modified_mann_kendall, dtw_kmeans
from trend_scope.models.stats.trends import mann_kendall
from trend_scope.models.serialization import dumps


@pytest.mark.parametrize('correction',['hamed_rao','yue_wang'])
def test_modified_mk_score_and_probability(correction):
    t=np.arange(40.)
    y=np.random.default_rng(2026).normal(size=40)+t*.1
    result=modified_mann_kendall(t,y,correction=correction,lag=2)
    assert result['score']==mann_kendall(t,y)['score']
    assert result['z']==pytest.approx((result['score']-np.sign(result['score']))/math.sqrt(result['variance']))
    assert result['p_value']==pytest.approx(math.erfc(abs(result['z'])/math.sqrt(2)))
    assert modified_mann_kendall(t,np.ones(40),correction=correction)['p_value']==1
    dumps(result)


def test_dtw_clustering_distinct_constant_groups():
    x=np.array([[0,0,0],[.1,.1,.1],[10,10,10],[10.1,10.1,10.1]])[:,:,None]
    result=dtw_kmeans(x,clusters=2,max_iter=5)
    labels=result['labels']
    assert labels[0]==labels[1] and labels[2]==labels[3] and labels[0]!=labels[2]
    means=sorted(result['centers'].mean(axis=(1,2)))
    np.testing.assert_allclose(means,[.05,10.05],atol=1e-12)
    dumps(result)


def test_optional_trend_constraints():
    with pytest.raises(ValueError):
        modified_mann_kendall([0,1,3,4],[0,1,2,3])
    with pytest.raises(ValueError):
        dtw_kmeans(np.ones((2,3,1)),clusters=3)
