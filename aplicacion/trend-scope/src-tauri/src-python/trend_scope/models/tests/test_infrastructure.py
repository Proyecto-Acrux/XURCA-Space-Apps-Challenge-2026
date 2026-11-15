"""Contract/integration tests with synthetic data, no NASA or native UI."""
from dataclasses import replace
import json

import numpy as np
import pytest

from trend_scope.models.contracts import (
    AnalysisRequest, Coordinate, ODEProblem, Provenance, ScientificDataset,
    TimeCoordinate, Transformation, VariableData,
)
from trend_scope.models.execution import AnalysisCancelled, ExecutionContext, analyze
from trend_scope.models.registry import default_registry
from trend_scope.models.serialization import dumps, to_jsonable
from trend_scope.models.validation import validate_dataset, validate_ode


def sample():
    return ScientificDataset(
        "synthetic", {"temperature": VariableData(np.array([10., 12., 16.]), ("time",), "degC")}, {},
        Provenance("analytic", "simulation", True, ("synthetic fixture",)),
        time=TimeCoordinate(np.array([0., 1., 3.]), "day", "2020-01-01T00:00:00Z", "gregorian"),
        transformations=(Transformation("fixture", "1"),),
    )


def request():
    return AnalysisRequest("analysis-1", "linear", "temperature")


def test_vertical_path_preserves_contract_units_provenance_and_inputs():
    data = sample()
    before = data.variables["temperature"].values.copy()
    states = []
    result = analyze(data, request(), default_registry(), ExecutionContext(progress=states.append))
    assert result.payload["parameters"]["slope"] == pytest.approx(2., abs=1e-12)
    assert result.metric_units["slope"] == "(degC)/(day)"
    assert result.provenance == data.provenance
    assert result.transformations == data.transformations
    assert result.input_summary["time_end"] == 3.
    assert result.uncertainty == "not_estimated"
    assert states == ["validating", "analysing", "completed"]
    np.testing.assert_array_equal(before, data.variables["temperature"].values)
    assert json.loads(dumps(result))["payload"]["algorithm"] == "linear_regression"


@pytest.mark.parametrize("dims,shape", [
    (("time",), (3,)), (("y", "x"), (2, 4)), (("time", "y", "x"), (3, 2, 4)),
    (("time", "feature"), (3, 2)), (("time", "y", "x", "feature"), (3, 2, 4, 2)),
])
def test_supported_shapes(dims, shape):
    coordinates = {}
    if "y" in dims:
        coordinates.update(y=Coordinate(np.arange(2.), ("y",), "m"), x=Coordinate(np.arange(4.), ("x",), "m"))
    if "feature" in dims:
        coordinates["feature"] = Coordinate(np.array(["temperature", "rain"]), ("feature",), "1")
    data = replace(sample(), variables={"v": VariableData(np.ones(shape), dims, "K", feature_units=("K", "mm") if "feature" in dims else ())},
                   coordinates=coordinates, crs="EPSG:3857" if "y" in dims else None,
                   time=sample().time if "time" in dims else None)
    validate_dataset(data)
    if dims != ("time",):
        with pytest.raises(ValueError, match="dimensions"):
            analyze(data, replace(request(), variable="v"), default_registry())


def test_curvilinear_coordinates():
    data = replace(sample(), time=None, crs="EPSG:4326",
                   variables={"v": VariableData(np.ones((2, 3)), ("y", "x"), "K")},
                   coordinates={"latitude": Coordinate(np.ones((2, 3)), ("y", "x"), "degree_north"),
                                "longitude": Coordinate(np.ones((2, 3)), ("y", "x"), "degree_east")})
    validate_dataset(data)
    with pytest.raises(ValueError, match="Spatial"):
        validate_dataset(replace(data, coordinates={}))


@pytest.mark.parametrize("times", [[0., 0., 3.], [0., 3., 1.]])
def test_temporal_adapter_rejects_duplicates_or_disorder(times):
    data = replace(sample(), time=replace(sample().time, values=np.array(times)))
    validate_dataset(data)  # Container does not silently sort or discard duplicates.
    with pytest.raises(ValueError, match="increasing"):
        analyze(data, request(), default_registry())


def test_masks_are_explicit_and_algorithm_specific():
    variable = VariableData(np.array([10., np.nan, 16.]), ("time",), "degC", np.array([False, True, False]))
    data = replace(sample(), variables={"temperature": variable})
    validate_dataset(data)
    with pytest.raises(ValueError, match="Missing"):
        analyze(data, request(), default_registry())
    with pytest.raises(ValueError, match="Unmasked"):
        validate_dataset(replace(data, variables={"temperature": replace(variable, invalid=None)}))
    with pytest.raises(ValueError, match="mask"):
        validate_dataset(replace(data, variables={"temperature": replace(variable, invalid=np.array([True]))}))


@pytest.mark.parametrize("change", [
    {"dataset_id": ""}, {"schema_version": 2}, {"time": None},
    {"quality": {"bad": float("nan")}},
    {"time": TimeCoordinate(np.array([0., np.inf, 3.]), "day", "origin", "gregorian")},
    {"time": TimeCoordinate(np.array([0., 1.]), "day", "origin", "gregorian")},
])
def test_invalid_datasets(change):
    with pytest.raises(ValueError):
        validate_dataset(replace(sample(), **change))


def test_registry_errors_and_unknown_parameters():
    registry = default_registry()
    spec, runner = registry.resolve("linear")
    with pytest.raises(ValueError, match="Duplicate"):
        registry.register(spec, runner)
    for req in (replace(request(), method_id="arima"), replace(request(), variable="missing"),
                replace(request(), parameters={"degree": 2})):
        with pytest.raises(ValueError):
            analyze(sample(), req, registry)


def test_limits_and_cancel_before_or_after_calculation():
    for context in (ExecutionContext(max_input_bytes=1), ExecutionContext(max_observations=2)):
        with pytest.raises(ValueError, match="budget"):
            analyze(sample(), request(), default_registry(), context)
    states = []
    with pytest.raises(AnalysisCancelled):
        analyze(sample(), request(), default_registry(), ExecutionContext(cancelled=lambda: True, progress=states.append))
    assert states == []
    with pytest.raises(AnalysisCancelled):
        analyze(sample(), request(), default_registry(), ExecutionContext(cancelled=lambda: "analysing" in states, progress=states.append))
    assert "completed" not in states


def test_insufficient_observations():
    data = replace(sample(), variables={"temperature": VariableData(np.array([1.]), ("time",), "K")},
                   time=replace(sample().time, values=np.array([0.])))
    with pytest.raises(ValueError, match="Insufficient"):
        analyze(data, request(), default_registry())


@pytest.mark.parametrize("value", [float("nan"), float("inf"), {1: "bad"}, object()])
def test_json_rejects_invalid_values(value):
    with pytest.raises(ValueError):
        dumps(value)


def test_json_budgets_and_numpy():
    assert json.loads(dumps({"a": np.array([1., 2.]), "b": np.int64(3), "c": None})) == {"a": [1., 2.], "b": 3, "c": None}
    with pytest.raises(ValueError, match="item"):
        to_jsonable(np.ones(100), max_items=10)
    with pytest.raises(ValueError, match="byte"):
        dumps("long text", max_bytes=2)
    with pytest.raises(ValueError):
        dumps({"x": np.array([np.nan])})


def test_ode_contract_is_not_an_observed_series():
    problem = ODEProblem("decay", np.array([1.]), ("K",), {"rate": .1}, (0., 10.), "s", np.array([0., 5., 10.]))
    validate_ode(problem)
    for invalid in (replace(problem, initial_state=np.array([])), replace(problem, time_span=(1., 0.)),
                    replace(problem, output_times=np.array([0., 0.])), replace(problem, state_units=()),
                    replace(problem, physical_parameters={"rate": float("nan")})):
        with pytest.raises(ValueError):
            validate_ode(invalid)


def test_adversarial_metadata_and_coordinates():
    data = sample()
    for invalid in (
        replace(data, schema_version=True),
        replace(data, coordinates={"time": Coordinate([0., 1., 3.], ("time",), "day")}),
        replace(data, provenance=replace(data.provenance, references=(3,))),
        replace(data, transformations=(Transformation("", "1"),)),
        replace(data, spatial_resolution={"x": 1.}),
        replace(data, time=replace(data.time, bounds=np.array([[0., 0.], [2., 3.], [3., 3.]]))),
    ):
        with pytest.raises(ValueError):
            validate_dataset(invalid)


def test_constant_series_keeps_undefined_metrics_and_demo_flag():
    data = replace(sample(), variables={"temperature": VariableData(np.array([4., 4., 4.]), ("time",), "K")})
    decoded = json.loads(dumps(analyze(data, request(), default_registry())))
    assert decoded["payload"]["metrics"]["r2"] is None
    assert decoded["provenance"]["demo"] is True
    assert decoded["payload"]["parameters"]["slope"] == 0.


def test_shared_dimension_alignment_and_feature_names():
    data = sample()
    with pytest.raises(ValueError, match="shared"):
        validate_dataset(replace(data, variables={**data.variables, "other": VariableData(np.ones(2), ("time",), "K")}))
    features = replace(data, variables={"v": VariableData(np.ones((3, 2)), ("time", "feature"), "", feature_units=("K", "mm"))},
                       coordinates={"feature": Coordinate(np.array(["same", "same"]), ("feature",), "1")})
    with pytest.raises(ValueError, match="unique"):
        validate_dataset(features)


def test_small_sample_retains_legacy_nullable_metrics():
    data = replace(sample(), variables={"temperature": VariableData(np.array([10., 12.]), ("time",), "K")},
                   time=replace(sample().time, values=np.array([0., 1.])))
    result = analyze(data, request(), default_registry())
    assert result.payload["metrics"]["adj_r2"] is None
    assert result.payload["metrics"]["aic"] is None
