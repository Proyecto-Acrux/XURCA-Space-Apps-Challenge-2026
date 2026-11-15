import numpy as np
import pytest
from scipy.signal import butter
from trend_scope.models.signal.processing import moving_average, fir_filter, iir_filter, fft_spectrum, ssa
from trend_scope.models.data_reduction.reduction import paa, lttb
from trend_scope.models.similarity.dtw import dtw
from trend_scope.models.serialization import dumps


def test_moving_and_fir_impulse():
    t = np.arange(5.)
    result = moving_average(t, t, window=3)
    np.testing.assert_array_equal(result['times'], [2,3,4])
    np.testing.assert_allclose(result['values'], [1,2,3])
    response = fir_filter(t, [1,0,0,0,0], coefficients=[.25,.5,.25])
    np.testing.assert_array_equal(response['values'], [.25,.5,.25,0,0])
    dumps(response)


def test_iir_constant_and_stability():
    t = np.arange(80.)
    sos = butter(2,.2,output='sos')
    result = iir_filter(t, np.ones(80), sos=sos, zero_phase=True)
    np.testing.assert_allclose(result['values'], 1, atol=1e-13)
    assert not result['causal']
    with pytest.raises(ValueError):
        iir_filter(t,np.ones(80),sos=[[1,0,0,1,0,2]])


@pytest.mark.parametrize('n',[63,64])
def test_fft_known_amplitude(n):
    t = np.arange(n)/n
    result = fft_spectrum(t, 3*np.sin(2*np.pi*5*t)+7)
    assert result['frequencies'][np.argmax(result['amplitude'])] == pytest.approx(5)
    assert result['amplitude'][5] == pytest.approx(3)
    dumps(result)


def test_ssa_full_reconstruction_and_rank_one():
    t = np.arange(12.)
    y = np.sin(t)
    result = ssa(t,y,window=4,components=range(4))
    np.testing.assert_allclose(result['values'],y,atol=1e-14)
    result = ssa(t,np.ones(12)*3,window=4,components=[0])
    np.testing.assert_allclose(result['values'],3,atol=1e-14)


def test_reduction_weighted_mean_and_extreme():
    result = paa(np.arange(5),[0,1,2,3,4],segments=2)
    np.testing.assert_allclose(result['values'],[.8,3.2])
    result = lttb(np.arange(9),[0,0,0,0,10,0,0,0,0],samples=5)
    assert 4 in result['indices']
    assert result['indices'][0] == 0 and result['indices'][-1] == 8
    assert len(result['indices']) == 5
    assert np.all(np.diff(result['indices']) > 0)
    dumps(result)


def test_dtw_known_symmetry_and_band():
    assert dtw([1,2,3],[1,2,3])['distance'] == 0
    assert dtw([1,2,3],[1,1,2,3])['distance'] == 0
    assert dtw([1,2],[3,4],radius=0)['distance'] == pytest.approx(np.sqrt(8))
    assert dtw([1,2],[3,4])['distance'] == dtw([3,4],[1,2])['distance']
    with pytest.raises(ValueError):
        dtw([1],[1,2,3],radius=0)


def test_irregular_and_missing_rejected():
    for method, params in ((moving_average,{'window':2}),(fft_spectrum,{}),(ssa,{'window':2,'components':[0]})):
        with pytest.raises(ValueError):
            method([0,1,3],[1,2,3],**params)
        with pytest.raises(ValueError):
            method([0,1,2],[1,np.nan,3],**params)
