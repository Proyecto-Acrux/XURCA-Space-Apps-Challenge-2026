"""Scientific contracts v1. Arrays are borrowed: callers must not mutate during execution."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Optional, Tuple

import numpy as np


@dataclass(frozen=True)
class Coordinate:
    values: np.ndarray
    dimensions: Tuple[str, ...]
    unit: str


@dataclass(frozen=True)
class TimeCoordinate:
    """Elapsed numeric time; origin/calendar supplied by the normalizer, never inferred."""
    values: np.ndarray
    unit: str
    origin: str
    calendar: str
    frequency: Optional[str] = None
    bounds: Optional[np.ndarray] = None
    timezone: Optional[str] = None


@dataclass(frozen=True)
class VariableData:
    values: np.ndarray
    dimensions: Tuple[str, ...]
    unit: str
    invalid: Optional[np.ndarray] = None  # True means invalid; exact shape, no broadcasting.
    feature_units: Tuple[str, ...] = ()


@dataclass(frozen=True)
class Provenance:
    source_id: str
    kind: str  # observation, satellite, reanalysis, model, simulation, demo
    demo: bool
    references: Tuple[str, ...] = ()
    product: Optional[str] = None
    version: Optional[str] = None
    acquired_at: Optional[str] = None


@dataclass(frozen=True)
class Transformation:
    operation: str
    version: str
    parameters: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ScientificDataset:
    dataset_id: str
    variables: Mapping[str, VariableData]
    coordinates: Mapping[str, Coordinate]
    provenance: Provenance
    time: Optional[TimeCoordinate] = None
    crs: Optional[str] = None
    quality: Mapping[str, Any] = field(default_factory=dict)
    transformations: Tuple[Transformation, ...] = ()
    schema_version: int = 1
    spatial_resolution: Mapping[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class AnalysisRequest:
    analysis_id: str
    method_id: str
    variable: str
    parameters: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AnalysisResult:
    analysis_id: str
    method_id: str
    method_version: str
    dataset_id: str
    variable: str
    status: str
    output_kind: str
    parameters: Mapping[str, Any]
    payload: Mapping[str, Any]
    metric_units: Mapping[str, str]
    warnings: Tuple[str, ...]
    provenance: Provenance
    input_summary: Mapping[str, Any]
    transformations: Tuple[Transformation, ...] = ()
    uncertainty: str = "not_estimated"
    schema_version: int = 1


@dataclass(frozen=True)
class ODEProblem:
    """Reserved contract; model_id must resolve to trusted registered code, not user code."""
    model_id: str
    initial_state: np.ndarray
    state_units: Tuple[str, ...]
    physical_parameters: Mapping[str, float]
    time_span: Tuple[float, float]
    time_unit: str
    output_times: Optional[np.ndarray] = None
