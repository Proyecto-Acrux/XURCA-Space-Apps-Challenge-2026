import numpy as np
import pytest
from trend_scope.models.dynamical.diffusion import diffusion_1d
from trend_scope.models.serialization import dumps


def test_diffusion_analytic_sine_and_maximum_principle():
    x=np.linspace(0,1,41)
    t=np.linspace(0,.01,41)
    initial=np.sin(np.pi*x); initial[-1]=0
    result=diffusion_1d(initial,x,t,diffusivity=1.)
    exact=np.exp(-np.pi**2*t[:,None])*np.sin(np.pi*x)
    np.testing.assert_allclose(result['values'],exact,atol=8e-5)
    assert result['values'].min() >= 0 and result['values'].max() <= 1
    np.testing.assert_array_equal(result['values'][:,[0,-1]],0)
    dumps(result)


def test_diffusion_stationary_linear_boundary_and_cfl_rejection():
    x=np.linspace(0,1,6)
    result=diffusion_1d(2+3*x,x,[0,.01,.02],diffusivity=1.)
    np.testing.assert_allclose(result['values'],np.tile(2+3*x,(3,1)),atol=1e-14)
    with pytest.raises(ValueError,match='stability'):
        diffusion_1d(x,x,[0,1],diffusivity=1.)
