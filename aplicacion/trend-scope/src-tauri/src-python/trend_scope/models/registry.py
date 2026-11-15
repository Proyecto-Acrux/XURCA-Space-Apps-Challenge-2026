"""Explicit registry of installed methods. No dynamic imports from user configuration."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Mapping, Tuple

from .contracts import AnalysisRequest, AnalysisResult, ScientificDataset


@dataclass(frozen=True)
class MethodSpec:
    method_id: str
    name: str
    version: str
    category: str
    output_kind: str
    dimensions: Tuple[Tuple[str, ...], ...]
    min_observations: int
    minimum_reason: str
    regularity: str
    parameters: Tuple[str, ...]
    dependencies: Tuple[str, ...]
    complexity: str
    acceleration: str
    status: str = "candidate"
    parameter_defaults: Mapping[str, object] = field(default_factory=dict)


Runner = Callable[[ScientificDataset, AnalysisRequest], AnalysisResult]


class MethodRegistry:
    def __init__(self) -> None:
        self._methods: dict[str, tuple[MethodSpec, Runner]] = {}

    def register(self, spec: MethodSpec, runner: Runner) -> None:
        if not spec.method_id or spec.min_observations < 1 or not callable(runner):
            raise ValueError("Invalid method registration")
        if spec.method_id in self._methods:
            raise ValueError(f"Duplicate method: {spec.method_id}")
        self._methods[spec.method_id] = (spec, runner)

    def resolve(self, method_id: str) -> tuple[MethodSpec, Runner]:
        try:
            return self._methods[method_id]
        except KeyError as error:
            raise ValueError(f"Unknown method: {method_id}") from error

    def describe(self) -> tuple[MethodSpec, ...]:
        return tuple(spec for spec, _ in self._methods.values())


def default_registry() -> MethodRegistry:
    """Expose only implemented candidates, with explicit capabilities and defaults."""
    from .adapters.linear import analyze_linear
    from .adapters.polynomial import analyze_polynomial
    registry = MethodRegistry()
    registry.register(MethodSpec(
        method_id="linear", name="Linear regression", version="1.1.0-candidate",
        category="stats", output_kind="fit", dimensions=(("time",),),
        min_observations=2, minimum_reason="Two distinct times identify slope and intercept; not uncertainty",
        regularity="strictly_increasing; irregular allowed; no missing values",
        parameters=(), dependencies=("numpy", "numba"),
        complexity="O(n) ordered input; O(n log n) unordered duplicate check; O(n) output memory",
        acceleration="Numba nopython float64, cache=True, nogil=True, serial compensated reductions",
    ), analyze_linear)
    registry.register(MethodSpec(
        method_id="polynomial", name="Polynomial regression", version="1.0.0-candidate",
        category="stats", output_kind="fit", dimensions=(("time",),),
        min_observations=2, minimum_reason="degree+1 observations and full rank; degree-specific check in executor",
        regularity="strictly_increasing; irregular allowed; no missing values",
        parameters=("degree",), dependencies=("numpy",),
        complexity="O(n*(degree+1)^2) solver; O(n*(degree+1)) design memory; explicit resource guards",
        acceleration="Native NumPy LAPACK least squares on a scaled Vandermonde matrix",
        parameter_defaults={"degree": 2},
    ), analyze_polynomial)
    return registry
