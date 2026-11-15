import math
import numpy as np
import pytest
from scipy.stats import theilslopes
from trend_scope.models.stats.trends import sen_slope, mann_kendall, multivariable_ols
from trend_scope.models.change_detection.cusum import cusum
from trend_scope.models.serialization import dumps


def test_sen_known_and_reference():
    t = np.array([0., .2, 1., 3., 5.])
    for slope in (2., -3., 0.):
        output = sen_slope(t, slope*t+7)
        assert output['slope'] == pytest.approx(slope)
        assert output['intercept_at_reference'] == pytest.approx(7)
        dumps(output)
    y = np.array([1., 3., 2., 8., 9.])
    assert sen_slope(t, y)['slope'] == pytest.approx(theilslopes(y, t).slope)


def test_mk_exact_components_ties_and_seasons():
    t = np.arange(5.)
    result = mann_kendall(t, t)
    assert result['score'] == 10
    assert result['variance'] == pytest.approx(50/3)
    assert result['p_value'] == pytest.approx(math.erfc(9/math.sqrt(100/3)))
    assert mann_kendall(t, -t)['z'] == -result['z']
    assert mann_kendall(t, np.ones(5))['p_value'] == 1
    assert mann_kendall(np.arange(3), [1,1,2])['variance'] == pytest.approx(8/3)
    seasonal = mann_kendall(np.arange(6), [0,100,1,101,2,102], seasons=[0,1,0,1,0,1])
    assert seasonal['score'] == 6
    assert seasonal['variance'] == pytest.approx(22/3)
    dumps(seasonal)


def test_multivariable_known_and_rank():
    x = np.array([[0,0],[1,0],[0,1],[2,3]], dtype=float)
    fit = multivariable_ols(x, 4+2*x[:,0]-3*x[:,1])
    np.testing.assert_allclose(fit['coefficients'], [2,-3], atol=1e-13)
    assert fit['intercept'] == pytest.approx(4)
    assert fit['rmse'] < 1e-13
    dumps(fit)
    with pytest.raises(ValueError):
        multivariable_ols(np.column_stack((np.arange(4), np.arange(4))), np.arange(4))


def test_cusum_crossing_and_no_false_constant():
    result = cusum([0,0,2,2,2], baseline=0, allowance=.5, threshold=3)
    np.testing.assert_array_equal(result['event_indices'], [4])
    np.testing.assert_array_equal(result['event_directions'], [1])
    assert not len(cusum(np.zeros(10), baseline=0, allowance=.5, threshold=3)['event_indices'])
    dumps(result)


@pytest.mark.parametrize('times,values', [([0],[1]),([0,0],[1,2]),([1,0],[1,2]),([0,1],[1,np.nan]),([0,1],[1])])
def test_invalid_trend_inputs(times, values):
    for method in (sen_slope, mann_kendall):
        with pytest.raises(ValueError):
            method(times, values)


def test_resource_limits_and_invalid_cusum():
    with pytest.raises(ValueError):
        sen_slope(np.arange(10), np.arange(10), max_pairs=2)
    with pytest.raises(ValueError):
        cusum([1], baseline=0, allowance=-1, threshold=2)
