"""Explicit simulation API for ODEProblem; no arbitrary code from configuration."""
from dataclasses import dataclass, replace
from typing import Tuple

import numpy as np
from numba.core.registry import CPUDispatcher

from ..contracts import AnalysisResult, ODEProblem, Provenance
from ..execution import ExecutionContext
from ..registry import MethodSpec
from ..serialization import to_jsonable
from ..validation import validate_ode
from .rk4 import METHOD_VERSION, rk4

RK4_SPEC = MethodSpec(
    method_id="rk4", name="Classical Runge-Kutta 4", version=METHOD_VERSION,
    category="dynamical", output_kind="simulation", dimensions=(("state",),),
    min_observations=2, minimum_reason="Two integration times, not two observations",
    regularity="strictly increasing explicit integration grid; nonuniform allowed",
    parameters=("block_steps", "max_output_bytes"), dependencies=("numpy", "numba"),
    complexity="O(steps*(state_size+RHS cost)); O(times*state_size) output",
    acceleration="Numba nopython, cache=True, nogil=True; serial RK4 steps",
    parameter_defaults={"block_steps":1024, "max_output_bytes":256*1024*1024},
)


@dataclass(frozen=True)
class ODEModel:
    """Trusted developer registration; RHS signature rhs(time,state,parameter_array)."""
    model_id: str
    version: str
    rhs: CPUDispatcher
    parameter_names: Tuple[str, ...]
    state_units: Tuple[str, ...]
    time_unit: str
    parameter_units: Tuple[str, ...] = ()


class ODEModelRegistry:
    """Separate from observed-series methods: no fictitious observed input to RK4."""
    def __init__(self):
        self._models = {}

    def register(self, model: ODEModel) -> None:
        if not isinstance(model.rhs, CPUDispatcher) or not model.rhs.targetoptions.get("nopython",False):
            raise ValueError("ODE models require a trusted nopython-compiled RHS")
        for text in (model.model_id, model.version, model.time_unit, *model.state_units, *model.parameter_names, *model.parameter_units):
            if not isinstance(text,str) or not text.strip():
                raise ValueError("Model IDs, version, units and parameter names must be nonempty")
        if not model.state_units or len(set(model.parameter_names)) != len(model.parameter_names):
            raise ValueError("Model requires state units and unique parameter names")
        if len(model.parameter_units) != len(model.parameter_names):
            raise ValueError("Provide a physical unit for every model parameter")
        if model.model_id in self._models:
            raise ValueError("Duplicate ODE model")
        self._models[model.model_id] = model

    def resolve(self, model_id: str) -> ODEModel:
        try:
            return self._models[model_id]
        except KeyError as error:
            raise ValueError(f"Unregistered ODE model: {model_id}") from error


def _float_array(values, name: str) -> np.ndarray:
    if not isinstance(values,np.ndarray) or np.ma.isMaskedArray(values) or values.dtype.kind not in "iuf":
        raise ValueError(f"{name} must be an unmasked real numeric ndarray")
    if values.dtype.kind in "iu" and (np.any(values>2**53) or np.any(values<-(2**53))):
        raise ValueError("Integers exceed exact float64 range; normalize before simulation")
    with np.errstate(over="raise",invalid="raise"):
        try:
            result=np.ascontiguousarray(values,dtype=np.float64)
        except (FloatingPointError,OverflowError) as error:
            raise ValueError(f"{name} is not representable in float64") from error
    if not np.isfinite(result).all():
        raise ValueError(f"{name} must be finite")
    return result


def simulate_rk4(problem: ODEProblem, models: ODEModelRegistry, analysis_id: str,
                 provenance: Provenance, context: ExecutionContext = ExecutionContext(),
                 *, block_steps: int = 1024, max_output_bytes: int = 256*1024*1024) -> AnalysisResult:
    """Simulate on output_times as the step grid; cancellation between bounded blocks.

    Returns arrays in Python; use the existing bounded serializer for small IPC
    payloads. No model is registered by default, and no strings are evaluated.
    """
    for limit in (block_steps,max_output_bytes,context.max_input_bytes,context.max_observations):
        if isinstance(limit,bool) or not isinstance(limit,int) or limit < 1:
            raise ValueError("Resource limits must be positive integers")
    if not isinstance(analysis_id,str) or not analysis_id.strip():
        raise ValueError("analysis_id is required")
    if provenance.kind != "simulation" or type(provenance.demo) is not bool or not isinstance(provenance.source_id,str) or not provenance.source_id.strip():
        raise ValueError("Explicit simulation provenance and demo flag are required")
    to_jsonable(provenance)
    context.checkpoint("validating")
    model=models.resolve(problem.model_id)
    if problem.output_times is None:
        raise ValueError("RK4 requires an explicit integration grid in output_times")
    if not isinstance(problem.initial_state,np.ndarray) or not isinstance(problem.output_times,np.ndarray):
        raise ValueError("Initial state and integration times must be NumPy arrays")
    if problem.output_times.size > context.max_observations or problem.initial_state.nbytes+problem.output_times.nbytes > context.max_input_bytes:
        raise ValueError("RK4 input budget exceeded before conversion")
    y0=_float_array(problem.initial_state,"initial_state")
    times=_float_array(problem.output_times,"output_times")
    for value in problem.physical_parameters.values():
        if isinstance(value,(int,np.integer)) and abs(int(value)) > 2**53:
            raise ValueError("Integer physical parameter exceeds exact float64 range")
    for boundary in problem.time_span:
        if isinstance(boundary,(int,np.integer)) and abs(int(boundary)) > 2**53:
            raise ValueError("Integer time_span exceeds exact float64 range; normalize first")
    validated=replace(problem,initial_state=y0,output_times=times)
    validate_ode(validated)
    if problem.state_units != model.state_units or problem.time_unit != model.time_unit:
        raise ValueError("State/time units must match the registered physical model; convert explicitly")
    if set(problem.physical_parameters) != set(model.parameter_names):
        raise ValueError("Physical parameters must exactly match the registered model")
    parameters=np.array([problem.physical_parameters[name] for name in model.parameter_names],dtype=np.float64)
    if not np.isfinite(parameters).all():
        raise ValueError("Physical parameters must be representable in float64")
    parameters.setflags(write=False)
    n,m=times.size,y0.size
    if n < 2 or times[0] != problem.time_span[0] or times[-1] != problem.time_span[1]:
        raise ValueError("Integration grid must include both time_span endpoints and at least two times")
    if n > context.max_observations or y0.nbytes+times.nbytes+parameters.nbytes > context.max_input_bytes:
        raise ValueError("RK4 input budget exceeded")
    # Bound stored trajectory, copied time, block trajectory and core work arrays.
    required=8*(n*m+3*n+(min(block_steps,n-1)+1)*m+16*m)
    if required > max_output_bytes:
        raise ValueError("RK4 output/work buffer budget exceeded")
    with np.errstate(over="raise",invalid="raise"):
        try:
            steps=np.diff(times)
            midpoint=times[:-1]+steps/2
        except FloatingPointError as error:
            raise ValueError("Integration steps must be finite") from error
    if np.any((midpoint<=times[:-1]) | (midpoint>=times[1:])):
        raise ValueError("RK4 midpoints are not representable; rebase/rescale time")
    context.checkpoint("analysing")
    states=np.empty((n,m),dtype=np.float64)
    states[0]=y0
    for start in range(0,n-1,block_steps):
        context.checkpoint(f"integrating:{start}/{n-1}")
        stop=min(start+block_steps,n-1)
        block=rk4(model.rhs,states[start],times[start:stop+1],(parameters,),max_output_bytes,block_steps)
        states[start+1:stop+1]=block[1:]
        del block
    result=AnalysisResult(
        analysis_id=analysis_id,method_id="rk4",method_version=METHOD_VERSION,
        dataset_id=f"simulation:{analysis_id}",variable="state",status="completed",output_kind="simulation",
        parameters={"model_id":model.model_id,"model_version":model.version,
                    "physical_parameters":dict(problem.physical_parameters),
                    "physical_parameter_units":dict(zip(model.parameter_names,model.parameter_units)),"block_steps":block_steps},
        payload={"times":times.copy(),"states":states,"n_steps":n-1,"rhs_evaluations":4*(n-1),
                 "state_units":problem.state_units,"time_unit":problem.time_unit},
        metric_units={"time":problem.time_unit,**{f"state_{i}":unit for i,unit in enumerate(problem.state_units)}},
        warnings=("Physical simulation, not an independently validated statistical forecast.",
                  "Explicit RK4 with a user-supplied step grid; truncation error and uncertainty not estimated.",
                  "Stiffness/stability are not diagnosed; finite output does not guarantee accuracy.",
                  "Cancellation is checked between blocks, not during an RHS evaluation."),
        provenance=provenance,input_summary={"initial_state":y0.copy(),"time_span":problem.time_span,
            "min_step":float(steps.min()),"max_step":float(steps.max()),"model_version":model.version},
    )
    context.checkpoint("completed")
    return result
