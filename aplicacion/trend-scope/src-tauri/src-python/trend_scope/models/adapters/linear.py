"""Bridge normalized temporal data to the existing public regression function."""
from __future__ import annotations

import numpy as np

from ..contracts import AnalysisRequest, AnalysisResult, ScientificDataset
from ..stats.regression import linear_regression


def analyze_linear(data: ScientificDataset, request: AnalysisRequest) -> AnalysisResult:
    """Called after structural validation by execution.analyze."""
    variable = data.variables[request.variable]
    if variable.dimensions != ("time",) or data.time is None:
        raise ValueError("Linear temporal analysis requires one selected time series")
    if request.parameters:
        raise ValueError("Linear temporal adapter has no configurable parameters")
    if variable.invalid is not None and variable.invalid.any():
        raise ValueError("Missing values require an explicit upstream transformation")
    times = data.time.values
    if np.any(times[1:] <= times[:-1]):
        raise ValueError("Temporal coordinates must be strictly increasing, without duplicates")
    # Explicit conversion only at the numeric boundary, no intermediate Python lists.
    result = linear_regression(times, variable.values)
    return AnalysisResult(
        analysis_id=request.analysis_id, method_id="linear",
        method_version=result["method_version"], dataset_id=data.dataset_id,
        variable=request.variable, status="completed", output_kind="fit", parameters={},
        payload=result,
        metric_units={"slope": f"({variable.unit})/({data.time.unit})", "intercept": variable.unit,
                      "rmse": variable.unit, "mae": variable.unit, "r2": "1", "adj_r2": "1",
                      "aic": "1; likelihood depends on response unit"},
        warnings=tuple(result["warnings"]), provenance=data.provenance,
        input_summary={"n_observations": len(times), "time_start": times[0], "time_end": times[-1],
                       "time_origin": data.time.origin, "time_unit": data.time.unit,
                       "calendar": data.time.calendar, "timezone": data.time.timezone,
                       "declared_frequency": data.time.frequency, "value_unit": variable.unit,
                       "quality": data.quality}, transformations=data.transformations,
    )
