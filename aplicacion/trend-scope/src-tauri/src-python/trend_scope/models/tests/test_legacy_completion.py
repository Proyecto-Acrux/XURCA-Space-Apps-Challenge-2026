import numpy as np
import pytest
from trend_scope.models.stats import regression as r
from trend_scope.models.serialization import dumps


def test_transformed_fits_known_solutions_and_json():
    x=np.linspace(1,3,12)
    for function,y,expected in (
        (r.exponential_regression,2*np.exp(.3*x),{'a':2,'b':.3}),
        (r.power_regression,3*x**1.5,{'a':3,'b':1.5}),
        (r.logarithmic_regression,4-2*np.log(x),{'a':4,'b':-2}),
    ):
        output=function(x,y)
        for name,value in expected.items():
            assert output['parameters'][name]==pytest.approx(value,rel=1e-12)
        np.testing.assert_allclose(output['y_pred'],y,rtol=1e-12)
        assert output['metrics']['aic'] is None
        dumps(output)


def test_shared_transformed_helper_large_offset():
    x=1e12+np.arange(6.)
    y=2*np.arange(6.)+1
    slope,intercept=r._jit_linear_fit(x,y)
    assert slope==pytest.approx(2)
    assert intercept==pytest.approx(1-2e12)


def test_ridge_reference_augmented_objective_and_unpenalized_intercept():
    x=np.linspace(-1,1,20)
    y=3*x*x+2*x+7
    output=r.ridge_regression(x,y,degree=2,alpha=.2)
    v=np.vander(x,3)
    expected=np.linalg.solve(v.T@v+np.diag([.2,.2,0]),v.T@y)
    np.testing.assert_allclose([output['parameters'][f'c_{k}'] for k in [2,1,0]],expected,rtol=1e-12)
    constant=r.ridge_regression(x,np.ones(20)*7,degree=2,alpha=100)
    np.testing.assert_allclose(constant['y_pred'],7,atol=1e-12)
    assert constant['metrics']['r2'] is None
    dumps(constant)


def test_harmonic_known_coefficients_and_rank_error():
    x=np.linspace(0,4,81)
    y=2+.3*x+4*np.cos(2*np.pi*x)-2*np.sin(2*np.pi*x)
    result=r.harmonic_regression(x,y,period=1,harmonics=1,trend_degree=1)
    np.testing.assert_allclose(result['y_pred'],y,atol=1e-12)
    assert result['parameters']['cos_1']==pytest.approx(4)
    assert result['parameters']['sin_1']==pytest.approx(-2)
    with pytest.raises(ValueError,match='rank'):
        r.harmonic_regression(np.arange(10.),np.arange(10.),period=1,harmonics=1)


def test_legacy_invalid_inputs_and_unrepresentable_amplitude():
    for method in (r.exponential_regression,r.logarithmic_regression,r.power_regression,r.ridge_regression):
        with pytest.raises(ValueError):
            method([1,1],[2,3])
        with pytest.raises(ValueError):
            method([1,2],[np.nan,3])
    with pytest.raises(ValueError):
        r.ridge_regression([0,1],[1,2],degree=True)
    with pytest.raises(ValueError):
        r.exponential_regression(1e12+np.arange(6),np.exp(.01*np.arange(6)))
