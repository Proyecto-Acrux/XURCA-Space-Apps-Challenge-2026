import itertools
import numpy as np
import pytest
from trend_scope.models.optional_methods import stl, wavelet, pelt, adwin, isolation_forest, forecast
from trend_scope.models.serialization import dumps


def test_stl_decomposition_identity():
    t=np.arange(48.)
    y=.2*t+np.sin(2*np.pi*t/12)
    result=stl(t,y,period=12,robust=False)
    np.testing.assert_allclose(result['trend']+result['seasonal']+result['residuals'],y,atol=1e-13)
    np.testing.assert_allclose(result['trend'],.2*t,atol=1e-10)
    dumps(result)


def test_wavelet_roundtrip():
    y=np.sin(np.arange(33.))
    result=wavelet(np.arange(33),y,wavelet='db2',level=2)
    np.testing.assert_allclose(result['reconstruction'],y,atol=1e-14)
    with pytest.raises(ValueError):
        wavelet(np.arange(4),np.ones(4),level=5)


def test_pelt_against_exhaustive_objective():
    y=np.array([0.,.1,0.,3.,3.1,3.])
    penalty=.5
    result=pelt(np.arange(6),y,penalty=penalty,min_size=1)
    def objective(ends):
        starts=[0]+list(ends[:-1])
        return sum(np.sum((y[a:b]-y[a:b].mean())**2) for a,b in zip(starts,ends))+penalty*(len(ends)-1)
    best=min(objective(list(cuts)+[6]) for count in range(6) for cuts in itertools.combinations(range(1,6),count))
    assert objective(result['segment_ends']) == pytest.approx(best)
    np.testing.assert_array_equal(result['change_indices'],[3])


def test_adwin_bounded_step_and_constant():
    assert not len(adwin(np.arange(100),np.zeros(100))['change_indices'])
    result=adwin(np.arange(512),np.r_[np.zeros(256),np.ones(256)])
    assert len(result['change_indices']) >= 1
    assert result['change_indices'][0] >= 256
    with pytest.raises(ValueError):
        adwin([0,1],[0,2])


def test_isolation_determinism_and_outlier():
    x=np.r_[np.linspace(-1,1,100),100.][:,None]
    first=isolation_forest(x,n_estimators=20)
    second=isolation_forest(x,n_estimators=20)
    np.testing.assert_array_equal(first['decision_scores'],second['decision_scores'])
    assert np.argmin(first['decision_scores']) == 100
    dumps(first)


def test_baselines_and_no_holdout_leakage():
    t=np.arange(20.)
    y=np.arange(20.)
    first=forecast(t,y,horizon=3)
    changed=y.copy(); changed[-3:]+=100
    second=forecast(t,changed,horizon=3)
    np.testing.assert_array_equal(first['validation']['predicted'],second['validation']['predicted'])
    assert first['validation']['metrics']['mae'] == pytest.approx(2)
    np.testing.assert_array_equal(first['values'],[19,19,19])
    np.testing.assert_array_equal(first['times'],[20,21,22])
    seasonal=forecast(t,np.tile([1,2,3,4],5),horizon=4,method='seasonal_naive',period=4)
    assert seasonal['validation']['metrics']['rmse'] == 0
    dumps(seasonal)


def test_arima_and_sarima_reference_special_cases():
    t=np.arange(48.)
    y=np.cumsum(np.random.default_rng(2026).normal(size=48))
    result=forecast(t,y,horizon=3,method='arima',order=(0,1,0))
    np.testing.assert_allclose(result['values'],y[-1],atol=1e-8)
    seasonal=forecast(t,y,horizon=4,method='sarima',order=(0,0,0),seasonal_order=(0,1,0,4))
    np.testing.assert_allclose(seasonal['values'],y[-4:],atol=1e-8)


def test_holt_winters_known_additive_series():
    t=np.arange(48.)
    y=.1*t+np.tile([1.,-1.,2.,-2.],12)
    result=forecast(t,y,horizon=4,method='holt_winters',period=4)
    np.testing.assert_allclose(result['values'],.1*np.arange(48,52)+[1,-1,2,-2],atol=.03)
    assert result['validation']['metrics']['rmse'] < .03


def test_invalid_library_inputs():
    with pytest.raises(ValueError):
        stl([0,1,2],[1,2,3],period=12)
    with pytest.raises(ValueError):
        forecast(np.arange(10),np.ones(10),horizon=20)
    with pytest.raises(ValueError):
        forecast(np.arange(10),np.ones(10),horizon=2,method='unknown')
