"""Analytical, convergence, adversarial and contract tests for stage 1C."""
from dataclasses import replace
import json

import numpy as np
import pytest
from numba import njit

from trend_scope.models.dynamical.rk4 import rk4, METHOD_VERSION
from trend_scope.models.dynamical.multi_ode import rk4_multi
from trend_scope.models.dynamical.rk4_service import ODEModel, ODEModelRegistry, RK4_SPEC, simulate_rk4
from trend_scope.models.contracts import ODEProblem, Provenance
from trend_scope.models.execution import AnalysisCancelled, ExecutionContext
from trend_scope.models.serialization import dumps
from trend_scope.models.tests.rk4_fixtures import (
    decay,growth,zero,cubic_time,oscillator,coupled,bad_shape,nonfinite,
    huge_constant,tiny_constant,mutates_input,parameter_decay,
)


def setup_problem():
    registry=ODEModelRegistry()
    registry.register(ODEModel("decay","test-1",parameter_decay,("rate",),("K",),"s",("1/s",)))
    problem=ODEProblem("decay",np.array([2.]),("K",),{"rate":.5},(0.,2.),"s",np.linspace(0.,2.,201))
    provenance=Provenance("analytic-model","simulation",True,("synthetic decay",))
    return registry,problem,provenance


@pytest.mark.parametrize("rhs,sign",[(decay,-1),(growth,1)])
def test_exponential_solution_and_input_preservation(rhs,sign):
    t=np.linspace(0,2,201)
    initial=np.array([1.,2.])
    result=rk4(rhs,initial,t)
    np.testing.assert_allclose(result,np.exp(sign*t[:,None])*initial,rtol=2e-10,atol=1e-12)
    np.testing.assert_array_equal(initial,[1.,2.])
    assert result.shape == (201,2)
    assert rk4.nopython_signatures


def test_fourth_order_convergence():
    errors=[]
    for steps in (10,20,40):
        calculated=rk4(decay,np.array([1.]),np.linspace(0.,1.,steps+1))[-1,0]
        errors.append(abs(calculated-np.exp(-1.)))
    ratios=np.array(errors[:-1])/errors[1:]
    assert np.all((ratios>15.) & (ratios<18.))


def test_constant_and_nonuniform_nonautonomous_solution():
    t=np.array([0.,.01,.04,.1,.21,.5,1.])
    initial=np.array([2.,-3.])
    np.testing.assert_array_equal(rk4(zero,initial,t),np.tile(initial,(len(t),1)))
    result=rk4(cubic_time,initial,t)
    # RK4 integrates cubic forcing exactly up to rounding (Simpson weights).
    np.testing.assert_allclose(result,initial+t[:,None]**4/4,rtol=1e-14,atol=1e-14)


def test_coupled_system_and_oscillator():
    t=np.linspace(0.,2.,401)
    result=rk4(coupled,np.array([0.,1.]),t)
    np.testing.assert_allclose(result[:,0],np.exp(-t)-np.exp(-2*t),rtol=2e-8,atol=2e-11)
    np.testing.assert_allclose(result[:,1],np.exp(-2*t),rtol=4e-10,atol=1e-12)
    states=rk4(oscillator,np.array([1.,0.]),t)
    np.testing.assert_allclose(states[:,0],np.cos(t),atol=2e-11)
    np.testing.assert_allclose(states[:,1],-np.sin(t),atol=2e-11)
    assert np.max(np.abs(np.sum(states**2,axis=1)-1))<1e-10


def test_against_independent_scipy_solution():
    from scipy.integrate import solve_ivp
    t=np.linspace(0.,1.,101)
    expected=solve_ivp(lambda time,y: np.array([-y[0]+y[1],-2*y[1]]),(0.,1.),[0.,1.],
                       t_eval=t,method="DOP853",rtol=1e-12,atol=1e-14)
    assert expected.success
    np.testing.assert_allclose(rk4(coupled,np.array([0.,1.]),t),expected.y.T,rtol=1e-7,atol=2e-10)


def test_matrix_state_float32_and_readonly_strides():
    t=np.linspace(0,1,201)[::2]
    t.flags.writeable=False
    initial=np.ones((2,3),dtype=np.float32)
    initial.flags.writeable=False
    output=rk4(decay,initial,t)
    assert output.shape==(101,2,3)
    np.testing.assert_allclose(output,np.exp(-t[:,None,None])*np.ones((2,3)),rtol=1e-9)
    assert not initial.flags.writeable


def test_existing_vector_wrapper_and_compiled_call_compatibility():
    t=np.linspace(0.,1.,101)
    initial=np.array([1.,0.])
    expected=rk4(oscillator,initial,t)
    np.testing.assert_array_equal(rk4_multi(oscillator,initial,t),expected)
    @njit
    def caller(y,times):
        return rk4(oscillator,y,times)
    np.testing.assert_array_equal(caller(initial,t),expected)


@pytest.mark.parametrize("times",[
    np.array([0.]),np.array([0.,0.]),np.array([1.,0.]),np.array([0.,np.nan]),
    np.array([0.,np.inf]),np.array([-1e308,1e308]),np.array([1e16,np.nextafter(1e16,np.inf)]),
])
def test_bad_time_grids(times):
    with pytest.raises(ValueError):
        rk4(decay,np.array([1.]),times)


@pytest.mark.parametrize("initial",[np.array([]),np.array([np.nan]),np.array([np.inf])])
def test_bad_initial_states(initial):
    with pytest.raises(ValueError):
        rk4(decay,initial,np.array([0.,1.]))


def test_rhs_shape_finiteness_and_overflow_failures():
    for rhs in (bad_shape,nonfinite):
        with pytest.raises(ValueError):
            rk4(rhs,np.array([1.]),np.array([0.,1.]))
    with pytest.raises(ValueError):
        rk4(growth,np.array([1e308]),np.array([0.,10.]))


def test_weighted_stages_avoid_spurious_overflow_and_underflow():
    result=rk4(huge_constant,np.array([0.]),np.array([0.,1e-308]))
    assert result[-1,0]==pytest.approx(1.,rel=1e-14)
    tiny=rk4(tiny_constant,np.array([0.]),np.array([0.,1e308]))
    assert tiny[-1,0]==pytest.approx(5e-324*1e308,rel=1e-14,abs=0.)


def test_rhs_cannot_mutate_stored_states():
    result=rk4(mutates_input,np.array([2.]),np.array([0.,1.,2.]))
    np.testing.assert_array_equal(result,[[2.],[2.],[2.]])


def test_low_level_resource_limits():
    with pytest.raises(ValueError,match="budget"):
        rk4(decay,np.ones(2),np.linspace(0,1,10),(),16,100)
    with pytest.raises(ValueError,match="budget"):
        rk4(decay,np.ones(2),np.linspace(0,1,10),(),10000,3)


def test_simulation_contract_units_parameters_and_block_equivalence():
    registry,problem,provenance=setup_problem()
    output=simulate_rk4(problem,registry,"simulation-1",provenance,block_steps=7)
    one_block=simulate_rk4(problem,registry,"simulation-1",provenance,block_steps=1000)
    np.testing.assert_array_equal(output.payload["states"],one_block.payload["states"])
    np.testing.assert_allclose(output.payload["states"][:,0],2*np.exp(-.5*problem.output_times),rtol=1e-11)
    assert output.method_version==RK4_SPEC.version==METHOD_VERSION
    assert output.output_kind=="simulation"
    assert output.provenance==provenance
    assert output.payload["rhs_evaluations"]==800
    assert output.parameters["physical_parameter_units"]=={"rate":"1/s"}
    assert output.uncertainty=="not_estimated"
    assert json.loads(dumps(output))["payload"]["state_units"]==["K"]
    np.testing.assert_array_equal(problem.initial_state,[2.])


def test_simulation_registry_and_contract_errors():
    registry,problem,provenance=setup_problem()
    with pytest.raises(ValueError,match="Duplicate"):
        registry.register(registry.resolve("decay"))
    with pytest.raises(ValueError):
        registry.register(ODEModel("python","1",lambda t,y,p:y,(),("K",),"s"))
    for bad in (
        replace(problem,model_id="unknown"),replace(problem,state_units=("degC",)),
        replace(problem,time_unit="day"),replace(problem,physical_parameters={}),
        replace(problem,physical_parameters={"rate":float("nan")}),replace(problem,output_times=None),
        replace(problem,output_times=np.array([.1,2.])),
        replace(problem,initial_state=np.ma.array([2.],mask=[True])),
        replace(problem,initial_state=np.array([True])),
    ):
        with pytest.raises(ValueError):
            simulate_rk4(bad,registry,"a",provenance)
    with pytest.raises(ValueError,match="provenance"):
        simulate_rk4(problem,registry,"a",replace(provenance,kind="observation"))


def test_cancellation_and_budget_before_allocating_trajectory():
    registry,problem,provenance=setup_problem()
    events=[]
    context=ExecutionContext(cancelled=lambda: any(event.startswith("integrating:") for event in events),progress=events.append)
    with pytest.raises(AnalysisCancelled):
        simulate_rk4(problem,registry,"a",provenance,context,block_steps=10)
    assert "completed" not in events
    for options in ({"max_output_bytes":64},{"block_steps":True},{"context":ExecutionContext(max_observations=10)}):
        with pytest.raises(ValueError):
            simulate_rk4(problem,registry,"a",provenance,**options)


def test_physical_parameters_are_runtime_values_not_cached_closures():
    registry,problem,provenance=setup_problem()
    first=simulate_rk4(problem,registry,"a",provenance)
    second=simulate_rk4(replace(problem,physical_parameters={"rate":1.}),registry,"b",provenance)
    assert first.payload["states"][-1,0] == pytest.approx(2*np.exp(-1),rel=1e-10)
    assert second.payload["states"][-1,0] == pytest.approx(2*np.exp(-2),rel=2e-10)


@pytest.mark.parametrize("initial,times",[
    (np.array([True]),np.array([0.,1.])),
    (np.array([1.]),np.array([False,True])),
    (np.array([2**53+1],dtype=np.int64),np.array([0.,1.])),
    (np.array([1.]),np.array([2**53,2**53+3],dtype=np.int64)),
])
def test_bool_and_lossy_integer_inputs(initial,times):
    with pytest.raises(ValueError):
        rk4(decay,initial,times)


def test_model_metadata_and_parameter_rejection():
    registry,problem,provenance=setup_problem()
    for model in (
        ODEModel("missing-units","1",parameter_decay,("rate",),("K",),"s"),
        ODEModel("duplicates","1",parameter_decay,("rate","rate"),("K",),"s",("1/s","1/s")),
    ):
        with pytest.raises(ValueError):
            registry.register(model)
    with pytest.raises(ValueError,match="float64"):
        simulate_rk4(replace(problem,physical_parameters={"rate":10**500}),registry,"a",provenance)


def test_simulation_outputs_do_not_alias_input_time_or_state():
    registry,problem,provenance=setup_problem()
    result=simulate_rk4(problem,registry,"a",provenance)
    problem.output_times[:]=99.
    problem.initial_state[:]=99.
    assert result.payload["times"][0]==0.
    assert result.payload["states"][0,0]==2.
    assert result.input_summary["initial_state"][0]==2.


def test_time_span_must_not_lose_integer_precision():
    registry,problem,provenance=setup_problem()
    invalid=replace(problem,time_span=(2**53+1,2**53+9),output_times=np.array([float(2**53),float(2**53+8)]))
    with pytest.raises(ValueError,match="float64"):
        simulate_rk4(invalid,registry,"a",provenance)
