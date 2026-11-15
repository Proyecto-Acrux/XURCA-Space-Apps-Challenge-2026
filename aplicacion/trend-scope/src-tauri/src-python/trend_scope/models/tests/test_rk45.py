import numpy as np
import pytest
from trend_scope.models.dynamical.rk45 import rk45
from trend_scope.models.tests.rk4_fixtures import decay, oscillator, bad_shape, nonfinite, zero


def test_rk45_analytic_vector_and_tolerance():
    t, y = rk45(decay, np.array([1.,2.]), (0., 2.), rtol=1e-9, atol=1e-12, max_steps=1000)
    assert t[0] == 0 and t[-1] == 2 and np.all(np.diff(t)>0)
    np.testing.assert_allclose(y, np.exp(-t[:,None])*[1,2], rtol=2e-9)
    t, y = rk45(oscillator, np.array([1.,0.]), (0., 2.), rtol=1e-9, atol=1e-12, max_steps=1000)
    np.testing.assert_allclose(y[:,0], np.cos(t), atol=2e-9)
    np.testing.assert_allclose(y[:,1], -np.sin(t), atol=2e-9)


def test_completed_last_step_below_minimum_is_success():
    t, y = rk45(zero, np.array([1.]), (0., 1e-14), min_step=1e-12, max_steps=10)
    assert t[-1] == 1e-14
    np.testing.assert_array_equal(y, np.ones_like(y))


@pytest.mark.parametrize('kwargs', [{'rtol':np.nan},{'atol':np.inf},{'initial_step':-1.},{'max_step':np.nan},{'max_steps':0},{'max_output_bytes':1}])
def test_invalid_parameters(kwargs):
    with pytest.raises(ValueError):
        rk45(decay, np.ones(1), (0.,1.), **kwargs)


def test_callback_and_span_errors():
    for rhs in (bad_shape, nonfinite):
        with pytest.raises((ValueError, FloatingPointError)):
            rk45(rhs, np.ones(2), (0.,1.), max_steps=10)
    with pytest.raises(ValueError):
        rk45(decay, np.ones(1), (0., np.inf))
    with pytest.raises(RuntimeError, match='max_steps'):
        rk45(decay, np.ones(1), (0.,10.), max_steps=1)
