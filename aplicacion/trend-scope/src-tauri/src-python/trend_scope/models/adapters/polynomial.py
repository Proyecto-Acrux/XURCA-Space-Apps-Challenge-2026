"""Temporal adapter for scaled polynomial regression; no implicit preprocessing."""
import numpy as np

from ..contracts import AnalysisRequest, AnalysisResult, ScientificDataset
from ..stats.regression import polynomial_regression


def analyze_polynomial(data: ScientificDataset, request: AnalysisRequest) -> AnalysisResult:
    """Run after structural validation by execution.analyze; degree defaults to two."""
    variable = data.variables[request.variable]
    if variable.dimensions != ("time",) or data.time is None:
        raise ValueError("Polynomial temporal analysis requires one selected time series")
    if set(request.parameters)-{"degree"}:
        raise ValueError("Unsupported polynomial parameters")
    if variable.invalid is not None and variable.invalid.any():
        raise ValueError("Missing values require an explicit upstream transformation")
    time = data.time
    if np.any(time.values[1:] <= time.values[:-1]):
        raise ValueError("Temporal coordinates must be strictly increasing without duplicates")
    result = polynomial_regression(time.values, variable.values, request.parameters.get("degree", 2))
    degree = result["degree"]
    units = {f"c_{k}": variable.unit if k == 0 else f"({variable.unit})/({time.unit})^{k}" for k in range(degree+1)}
    units.update(rmse=variable.unit, mae=variable.unit, r2="1", adj_r2="1", aic="1; likelihood depends on response unit")
    return AnalysisResult(
        analysis_id=request.analysis_id, method_id="polynomial", method_version=result["method_version"],
        dataset_id=data.dataset_id, variable=request.variable, status="completed", output_kind="fit",
        parameters={"degree": degree}, payload=result, metric_units=units,
        warnings=tuple(result["warnings"]), provenance=data.provenance,
        input_summary={"n_observations": len(time.values), "time_start": time.values[0], "time_end": time.values[-1],
                       "time_origin": time.origin, "time_unit": time.unit, "calendar": time.calendar,
                       "timezone": time.timezone, "declared_frequency": time.frequency,
                       "value_unit": variable.unit, "quality": data.quality},
        transformations=data.transformations,
    )
