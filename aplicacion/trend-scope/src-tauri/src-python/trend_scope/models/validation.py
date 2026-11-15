"""Structural validation without sorting, casting, interpolation or aggregation."""
from __future__ import annotations

import numpy as np

from .contracts import ScientificDataset, ODEProblem
from .serialization import to_jsonable

SUPPORTED_DIMENSIONS = {
    ("time",), ("y", "x"), ("time", "y", "x"),
    ("time", "feature"), ("time", "y", "x", "feature"),
}


def _text(value: str, label: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be nonempty text")


def _array(value: np.ndarray, label: str, *, finite: bool = True) -> None:
    if not isinstance(value, np.ndarray) or value.dtype.kind not in "iuf" or value.size == 0:
        raise ValueError(f"{label} must be a nonempty real numeric ndarray")
    if finite and not np.isfinite(value).all():
        raise ValueError(f"{label} must be finite")


def validate_dataset(data: ScientificDataset) -> None:
    """Allow masked invalid data structurally; each algorithm decides whether it supports it."""
    _text(data.dataset_id, "dataset_id")
    if type(data.schema_version) is not int or data.schema_version != 1 or not data.variables:
        raise ValueError("Expected schema_version=1 and at least one variable")
    _text(data.provenance.source_id, "source_id")
    if data.provenance.kind not in {"observation", "satellite", "reanalysis", "model", "simulation", "demo"}:
        raise ValueError("Unknown provenance kind")
    if type(data.provenance.demo) is not bool or (data.provenance.kind == "demo" and not data.provenance.demo):
        raise ValueError("Invalid demo flag")
    for reference in data.provenance.references:
        _text(reference, "provenance reference")
    sizes = {}
    for name, variable in data.variables.items():
        _text(name, "variable name")
        _array(variable.values, name, finite=False)
        if not isinstance(variable.dimensions, tuple) or variable.dimensions not in SUPPORTED_DIMENSIONS or variable.values.ndim != len(variable.dimensions):
            raise ValueError(f"Unsupported dimensions for {name}")
        for axis, size in zip(variable.dimensions, variable.values.shape):
            if axis in sizes and sizes[axis] != size:
                raise ValueError(f"Inconsistent shared dimension {axis}")
            sizes[axis] = size
        mask = variable.invalid
        if mask is not None and (not isinstance(mask, np.ndarray) or mask.dtype != np.bool_ or mask.shape != variable.values.shape):
            raise ValueError(f"Invalid mask for {name}; broadcasting is prohibited")
        bad = ~np.isfinite(variable.values)
        if np.any(bad if mask is None else bad & ~mask):
            raise ValueError(f"Unmasked nonfinite values in {name}")
        if "feature" in variable.dimensions:
            if len(variable.feature_units) != sizes["feature"]:
                raise ValueError("Provide one unit per feature")
            for unit in variable.feature_units:
                _text(unit, "feature unit")
        else:
            _text(variable.unit, "variable unit")
            if variable.feature_units:
                raise ValueError("feature_units requires a feature axis")
    if "time" in sizes:
        if data.time is None:
            raise ValueError("Missing temporal coordinate")
        _array(data.time.values, "time")
        if data.time.values.shape != (sizes["time"],):
            raise ValueError("Time shape mismatch")
        for label in ("unit", "origin", "calendar"):
            _text(getattr(data.time, label), f"time.{label}")
        bounds = data.time.bounds
        if bounds is not None:
            _array(bounds, "time bounds")
            if bounds.shape != (sizes["time"], 2) or np.any(bounds[:, 0] > bounds[:, 1]):
                raise ValueError("Invalid time bounds")
            if np.any((data.time.values < bounds[:, 0]) | (data.time.values > bounds[:, 1])):
                raise ValueError("Times must lie within their bounds")
    elif data.time is not None:
        raise ValueError("Time coordinate without time dimension")
    for name, coordinate in data.coordinates.items():
        _text(name, "coordinate name")
        _text(coordinate.unit, "coordinate unit")
        if not isinstance(coordinate.values, np.ndarray):
            raise ValueError("Coordinate values must be NumPy arrays")
        if not isinstance(coordinate.dimensions, tuple) or not coordinate.dimensions or len(set(coordinate.dimensions)) != len(coordinate.dimensions):
            raise ValueError("Coordinate axes must be nonempty and unique")
        if any(dim not in sizes for dim in coordinate.dimensions):
            raise ValueError("Coordinate references unknown dimension")
        if coordinate.values.shape != tuple(sizes[dim] for dim in coordinate.dimensions):
            raise ValueError("Coordinate shape mismatch")
        if coordinate.dimensions == ("feature",):
            labels = coordinate.values.tolist()
            if not all(isinstance(v, str) and v.strip() for v in labels) or len(set(labels)) != len(labels):
                raise ValueError("Feature names must be unique nonempty strings")
        else:
            _array(coordinate.values, name)
    if "feature" in sizes:
        if "feature" not in data.coordinates or data.coordinates["feature"].dimensions != ("feature",):
            raise ValueError("Missing feature names")
    if "y" in sizes:
        _text(data.crs, "CRS")
        # Either two 1D grid axes or two 2D geographic/projected coordinates.
        spatial = [c.dimensions for c in data.coordinates.values()]
        if not (("y",) in spatial and ("x",) in spatial) and spatial.count(("y", "x")) < 2:
            raise ValueError("Spatial data require rectilinear or curvilinear coordinates")
    for axis, resolution in data.spatial_resolution.items():
        if axis not in ("x", "y") or axis not in sizes:
            raise ValueError("Resolution must refer to a spatial axis")
        if isinstance(resolution, (bool, np.bool_)) or not isinstance(resolution, (int, float, np.integer, np.floating)) or not np.isfinite(resolution) or resolution <= 0:
            raise ValueError("Spatial resolution must be positive and finite in CRS axis units")
    for transformation in data.transformations:
        _text(transformation.operation, "transformation operation")
        _text(transformation.version, "transformation version")
    to_jsonable(data.provenance)
    to_jsonable(data.quality)
    to_jsonable(data.transformations)


def validate_ode(problem: ODEProblem) -> None:
    """Validate a simulation request without evaluating a derivative."""
    _text(problem.model_id, "model_id")
    _text(problem.time_unit, "time_unit")
    _array(problem.initial_state, "initial_state")
    if problem.initial_state.ndim != 1 or len(problem.state_units) != problem.initial_state.size:
        raise ValueError("Expected vector state and one unit per component")
    for unit in problem.state_units:
        _text(unit, "state unit")
    span = np.asarray(problem.time_span)
    _array(span, "time_span")
    if span.shape != (2,) or span[1] <= span[0]:
        raise ValueError("Invalid time span")
    for key, value in problem.physical_parameters.items():
        _text(key, "physical parameter")
        if isinstance(value, (bool, np.bool_)) or not isinstance(value, (int, float, np.integer, np.floating)) or not np.isfinite(value):
            raise ValueError("Physical parameters must be finite real scalars")
    if problem.output_times is not None:
        times = problem.output_times
        _array(times, "output_times")
        if times.ndim != 1 or np.any(times[1:] <= times[:-1]) or times[0] < span[0] or times[-1] > span[1]:
            raise ValueError("Output times must increase within time_span")
