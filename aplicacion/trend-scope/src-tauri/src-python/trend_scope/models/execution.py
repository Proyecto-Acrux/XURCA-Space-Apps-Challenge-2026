"""Synchronous scientific orchestration; invoke from a worker, not the UI thread."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from .contracts import AnalysisRequest, AnalysisResult, ScientificDataset
from .registry import MethodRegistry
from .validation import validate_dataset


class AnalysisCancelled(RuntimeError):
    """Cooperative cancellation; no partial output is presented as completed."""


@dataclass(frozen=True)
class ExecutionContext:
    # Conservative input-size limits, not a guarantee about total process memory.
    max_input_bytes: int = 256 * 1024 * 1024
    max_observations: int = 1_000_000
    cancelled: Callable[[], bool] = lambda: False
    progress: Callable[[str], None] = lambda state: None

    def checkpoint(self, state: str) -> None:
        if self.cancelled():
            raise AnalysisCancelled("Analysis cancelled")
        self.progress(state)


def analyze(data: ScientificDataset, request: AnalysisRequest,
            registry: MethodRegistry, context: ExecutionContext = ExecutionContext()) -> AnalysisResult:
    """Validate and dispatch without mutating data or guessing transformations."""
    for limit in (context.max_input_bytes, context.max_observations):
        if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
            raise ValueError("Resource limits must be positive integers")
    if not request.analysis_id or not isinstance(request.analysis_id, str):
        raise ValueError("analysis_id is required")
    context.checkpoint("validating")
    arrays = [v.values for v in data.variables.values()]
    arrays += [v.invalid for v in data.variables.values() if v.invalid is not None]
    arrays += [c.values for c in data.coordinates.values()]
    if data.time is not None:
        arrays.append(data.time.values)
        if data.time.bounds is not None:
            arrays.append(data.time.bounds)
    # Validate types before reading nbytes; count shared arrays conservatively.
    import numpy as np
    if any(not isinstance(a, np.ndarray) for a in arrays):
        raise ValueError("Scientific data require NumPy arrays")
    if sum(a.nbytes for a in arrays) > context.max_input_bytes:
        raise ValueError("Input memory budget exceeded")
    validate_dataset(data)
    spec, runner = registry.resolve(request.method_id)
    if request.variable not in data.variables:
        raise ValueError("Unknown selected variable")
    variable = data.variables[request.variable]
    if variable.dimensions not in spec.dimensions:
        raise ValueError("Incompatible dimensions; select an explicit adapter")
    n = variable.values.shape[0]
    if n < spec.min_observations:
        raise ValueError(f"Insufficient data: {spec.minimum_reason}")
    if n > context.max_observations:
        raise ValueError("Observation budget exceeded")
    if set(request.parameters) - set(spec.parameters):
        raise ValueError("Unsupported method parameters")
    context.checkpoint("analysing")
    result = runner(data, request)
    context.checkpoint("completed")
    return result
