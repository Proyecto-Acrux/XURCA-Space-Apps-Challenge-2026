import pytest
import numpy as np
import json
from trend_scope.models.stats import regression

def test_linear_regression():
    x = [1.0, 2.0, 3.0, 4.0, 5.0]
    y = [2.0, 4.0, 6.0, 8.0, 10.0]

    result = regression.linear_regression(x, y)

    assert result["algorithm"] == "linear_regression"
    assert pytest.approx(result["parameters"]["slope"], rel=1e-5) == 2.0
    assert pytest.approx(result["parameters"]["intercept"], rel=1e-5) == 0.0
    assert pytest.approx(result["metrics"]["r2"], rel=1e-5) == 1.0

def test_polynomial_regression():
    x = [1.0, 2.0, 3.0, 4.0]
    y = [1.0, 4.0, 9.0, 16.0]  # y = x^2

    result = regression.polynomial_regression(x, y, degree=2)

    assert result["algorithm"] == "polynomial_regression"
    assert pytest.approx(result["metrics"]["r2"], rel=1e-5) == 1.0


@pytest.mark.parametrize("slope,intercept", [(2.0, 3.0), (-3.0, 7.0), (0.0, 4.0)])
def test_known_lines(slope, intercept):
    x = np.arange(6, dtype=float)
    y = slope * x + intercept
    result = regression.linear_regression(x.tolist(), y.tolist())
    assert result["parameters"] == pytest.approx({"slope": slope, "intercept": intercept}, abs=1e-12)
    np.testing.assert_allclose(result["y_pred"], y, atol=1e-12, rtol=1e-12)
    np.testing.assert_allclose(result["residuals"], 0, atol=1e-12)
    assert result["metrics"]["r2"] == (None if slope == 0 else 1.0)
    json.dumps(result, allow_nan=False)


def test_analytic_noise_and_metrics():
    # Noise is orthogonal to both the intercept and x: exact OLS solution.
    x = [-2., -1., 0., 1., 2.]
    noise = np.array([1., -2., 2., -2., 1.])
    y = 3 * np.array(x) + 7 + noise
    result = regression.linear_regression(x, y.tolist())
    assert result["parameters"] == pytest.approx({"slope": 3., "intercept": 7.}, abs=1e-12)
    np.testing.assert_allclose(result["residuals"], noise, atol=1e-12)
    metrics = result["metrics"]
    assert metrics["r2"] == pytest.approx(1 - 14 / 104)
    assert metrics["adj_r2"] == pytest.approx(1 - (14 / 104) * 4 / 3)
    assert metrics["rmse"] == pytest.approx(np.sqrt(14 / 5))
    assert metrics["mae"] == pytest.approx(8 / 5)
    assert metrics["aic"] == pytest.approx(5 * (np.log(2 * np.pi) + 1 + np.log(14 / 5)) + 6)
    json.dumps(result, allow_nan=False)


def test_large_origin():
    x = 1e12 + np.arange(10.)
    y = 3 * (x - 1e12) + 7
    result = regression.linear_regression(x.tolist(), y.tolist())
    assert result["parameters"]["slope"] == pytest.approx(3, abs=1e-12)
    assert result["parameters"]["intercept"] == pytest.approx(7 - 3e12, abs=1e-3, rel=0)
    np.testing.assert_allclose(result["y_pred"], y, atol=1e-12)


@pytest.mark.parametrize("scale", [1e-150, 1e150])
def test_scaling(scale):
    x = np.arange(5.) * scale
    y = np.array([1., 2., 4., 4., 6.]) * scale
    result = regression.linear_regression(x.tolist(), y.tolist())
    reference = regression.linear_regression((x / scale).tolist(), (y / scale).tolist())
    assert result["parameters"]["slope"] == pytest.approx(reference["parameters"]["slope"], rel=1e-12)
    assert result["metrics"]["rmse"] / scale == pytest.approx(reference["metrics"]["rmse"], rel=1e-12)
    json.dumps(result, allow_nan=False)


def test_seeded_noise_against_numpy_lstsq():
    rng = np.random.default_rng(2026)
    x = np.linspace(-3, 8, 101)
    y = -1.2 * x + 5 + rng.normal(0, .3, x.size)
    expected, *_ = np.linalg.lstsq(np.column_stack((x, np.ones(x.size))), y, rcond=None)
    result = regression.linear_regression(x.tolist(), y.tolist())
    np.testing.assert_allclose(list(result["parameters"].values()), expected, rtol=1e-12, atol=1e-12)
    residuals = np.array(result["residuals"])
    assert abs(residuals.sum()) < 1e-11
    assert abs(residuals @ x) < 1e-10


def test_two_points():
    result = regression.linear_regression([0., 1.], [2., 4.])
    assert result["metrics"]["adj_r2"] is None
    assert result["metrics"]["aic"] is None
    assert result["uncertainty"] == "not_estimated"
    json.dumps(result, allow_nan=False)


def test_unsorted_duplicate_irregular_pairs_preserved():
    x = [4., 0., 1., 1., 8.]
    y = [2 * v + 3 for v in x]
    result = regression.linear_regression(x, y)
    assert result["x"] == x
    np.testing.assert_allclose(result["y_pred"], y, atol=1e-12)
    assert any("duplicados" in w for w in result["warnings"])
    assert any("ordenado" in w for w in result["warnings"])
    assert any("uniforme" in w for w in result["warnings"])


@pytest.mark.parametrize("x,y", [
    ([], []), ([1.], [2.]), ([1., 2.], [3.]), ([1., 1.], [2., 3.]),
    ([0., np.nan], [1., 2.]), ([0., 1.], [1., np.inf]),
    ([0., 1.], [None, 2.]), ([[0.], [1.]], [1., 2.]),
    (["0", "1"], [1., 2.]), ([False, True], [1., 2.]),
    ([False, 1.], [1., 2.]),
    ([0j, 1j], [1., 2.]), (None, [1., 2.]),
    (["2020-01-01", "2020-01-02"], [1., 2.]),
    ([-1e308, 1e308], [0., 1.]),
])
def test_invalid_linear_input(x, y):
    with pytest.raises(ValueError):
        regression.linear_regression(x, y)


@pytest.mark.parametrize("n", [2, 3, 31, 1000])
@pytest.mark.parametrize("scale,origin", [(1., 0.), (1., 1e12), (1e-150, 0.), (1e150, 0.)])
def test_numba_against_frozen_numpy(n, scale, origin):
    from trend_scope.models.stats.linear_reference import linear_regression as reference
    rng = np.random.default_rng(701)
    x = origin + np.arange(n, dtype=float) * scale
    y = (3 * np.arange(n) + 7 + rng.normal(0, .2, n)) * scale
    actual, expected = regression.linear_regression(x, y), reference(x, y)
    np.testing.assert_allclose(actual["y_pred"], expected["y_pred"], rtol=2e-13, atol=1e-13*scale)
    assert actual["parameters"]["slope"] == pytest.approx(expected["parameters"]["slope"], rel=2e-13)
    # Two-point fits have zero residual degrees of freedom and roundoff-sensitive AIC.
    if n > 2:
        assert actual["metrics"]["rmse"]/scale == pytest.approx(expected["metrics"]["rmse"]/scale, abs=2e-10)
        assert actual["metrics"]["aic"] == pytest.approx(expected["metrics"]["aic"], rel=1e-10, abs=1e-8)
    json.dumps(actual, allow_nan=False)


def test_kernel_nopython_repeatability_and_readonly_strides():
    from trend_scope.models.stats.linear_kernel import linear_kernel
    x = np.arange(20.)[::2]
    y = (3*x + 7)
    x.flags.writeable = False
    y.flags.writeable = False
    first = regression.linear_regression(x, y)
    assert first == regression.linear_regression(x, y)
    assert linear_kernel.nopython_signatures
    assert first["parameters"]["slope"] == pytest.approx(3.)
    assert not x.flags.writeable


def test_exact_decimal_reference_for_adversarial_origin():
    from decimal import Decimal, localcontext
    x = np.array([1e14 + v for v in [0., .125, 1., 4., 10.]])
    y = np.array([2., -1., 4., 8., 7.])
    with localcontext() as ctx:
        ctx.prec = 70
        xd, yd = list(map(Decimal.from_float, x)), list(map(Decimal.from_float, y))
        mx, my = sum(xd)/len(xd), sum(yd)/len(yd)
        slope = sum((a-mx)*(b-my) for a,b in zip(xd,yd))/sum((a-mx)**2 for a in xd)
        fitted = np.array([float(my+slope*(a-mx)) for a in xd])
    result = regression.linear_regression(x,y)
    assert result["parameters"]["slope"] == pytest.approx(float(slope), rel=1e-13)
    np.testing.assert_allclose(result["y_pred"], fitted, atol=1e-13, rtol=1e-13)


def test_tiny_representable_scale_and_unrepresentable_slope():
    result = regression.linear_regression(np.array([0., 1e-300, 2e-300]), np.array([0., 1e-300, 2e-300]))
    assert result["parameters"]["slope"] == 1.
    with pytest.raises(ValueError, match="representable"):
        regression.linear_regression([0., 1e-300], [0., 1e300])


def test_unsorted_nonadjacent_duplicates():
    result = regression.linear_regression([0., 2., 1., 2.], [0., 4., 2., 4.])
    assert any("duplicados" in warning for warning in result["warnings"])


def test_float32_promotes_without_mutating():
    x = np.arange(10, dtype=np.float32)
    y = 3*x+1
    result = regression.linear_regression(x,y)
    assert result["parameters"]["slope"] == pytest.approx(3.)
    assert x.dtype == np.float32


@pytest.mark.parametrize("values", [np.array([2**53, 2**53+1],dtype=np.int64), np.array([2**64-2,2**64-1],dtype=np.uint64)])
def test_lossy_integer_coordinates_are_rejected(values):
    with pytest.raises(ValueError, match="float64"):
        regression.linear_regression(values,[0.,1.])


def test_permutation_and_unit_conversion_invariants():
    x=np.arange(20.)
    y=2*x+np.sin(x)
    result=regression.linear_regression(x,y)
    order=np.random.default_rng(4).permutation(x.size)
    shuffled=regression.linear_regression(x[order],y[order])
    converted=regression.linear_regression(x/365.25,y+273.15)
    np.testing.assert_allclose(np.array(shuffled["y_pred"])[np.argsort(order)],result["y_pred"],rtol=1e-13,atol=1e-13)
    assert converted["parameters"]["slope"] == pytest.approx(result["parameters"]["slope"]*365.25,rel=1e-13)
    assert converted["metrics"]["rmse"] == pytest.approx(result["metrics"]["rmse"],abs=1e-13)


def test_saturated_two_point_aic_is_not_roundoff_likelihood():
    result=regression.linear_regression([1.1,4.7],[3.3,5.9])
    assert result["metrics"]["aic"] is None
    assert result["metrics"]["adj_r2"] is None


def test_registered_version_matches_accelerated_result():
    from trend_scope.models.registry import default_registry
    spec, _ = default_registry().resolve("linear")
    result=regression.linear_regression([0.,1.],[2.,4.])
    assert spec.version == result["method_version"] == "1.1.0-candidate"
    assert "Numba" in spec.acceleration


@pytest.mark.parametrize("coefficients", [[3., -2., .5], [-1., 2., -3., .25], [4., 0., 0.]])
def test_polynomial_known_coefficients(coefficients):
    x = np.linspace(-2., 3., 21)
    y = np.polynomial.polynomial.polyval(x, coefficients)
    result = regression.polynomial_regression(x, y, len(coefficients)-1)
    np.testing.assert_allclose([result["parameters"][f"c_{i}"] for i in range(len(coefficients))], coefficients, atol=2e-12, rtol=2e-12)
    np.testing.assert_allclose(result["y_pred"], y, atol=3e-12, rtol=2e-12)
    assert result["rank"] == len(coefficients)
    if np.ptp(y) == 0:
        assert result["metrics"]["r2"] is None
        assert result["metrics"]["aic"] is None
    json.dumps(result, allow_nan=False)


def test_polynomial_analytic_noise_metrics_and_orthogonality():
    # This noise is orthogonal to 1, x and x**2: finite-difference stencil order 4.
    x = np.arange(-2., 3.)
    noise = np.array([1., -4., 6., -4., 1.])
    y = 2*x*x + 3*x + 5 + noise
    result = regression.polynomial_regression(x, y)
    np.testing.assert_allclose(result["residuals"], noise, atol=1e-12)
    assert result["parameters"] == pytest.approx({"c_2": 2., "c_1": 3., "c_0": 5.}, abs=1e-12)
    sst = np.sum((y-y.mean())**2)
    metrics = result["metrics"]
    assert metrics["rmse"] == pytest.approx(np.sqrt(70/5))
    assert metrics["mae"] == pytest.approx(16/5)
    assert metrics["r2"] == pytest.approx(1-70/sst)
    assert metrics["adj_r2"] == pytest.approx(1-(70/sst)*4/2)
    assert metrics["aic"] == pytest.approx(5*(np.log(2*np.pi)+1+np.log(14))+8)
    assert result["residual_degrees_of_freedom"] == 2


def test_polynomial_large_time_origin_stable_basis():
    x = 1e12+np.arange(11.)
    y = .5*(x-1e12)**2-2*(x-1e12)+7
    result = regression.polynomial_regression(x,y)
    basis = result["stable_basis"]
    reconstructed = basis["y_offset"]+basis["y_scale"]*np.polynomial.polynomial.polyval((x-basis["x_offset"])/basis["x_scale"],basis["coefficients"])
    np.testing.assert_allclose(reconstructed,y,rtol=1e-12,atol=1e-12)
    np.testing.assert_allclose(result["y_pred"],reconstructed,rtol=0,atol=0)
    assert result["condition_number"] < 10
    json.dumps(result,allow_nan=False)


def test_polynomial_seeded_against_numpy_polynomial_fit():
    rng=np.random.default_rng(2026)
    x=np.sort(rng.uniform(-4,9,101))
    y=.25*x**3-2*x+4+rng.normal(0,.2,len(x))
    expected=np.polynomial.Polynomial.fit(x,y,3)
    result=regression.polynomial_regression(x,y,3)
    np.testing.assert_allclose(result["y_pred"],expected(x),rtol=1e-11,atol=1e-11)
    for k in range(4):
        assert abs(np.dot(result["residuals"],x**k)) < 1e-7


@pytest.mark.parametrize("scale", [1e-100, 1e100])
def test_polynomial_response_scaling(scale):
    x=np.linspace(-2,2,11)
    y=(x*x+3*x+5)*scale
    result=regression.polynomial_regression(x,y)
    np.testing.assert_allclose(np.array(result["y_pred"])/scale,y/scale,atol=1e-12,rtol=1e-12)
    json.dumps(result,allow_nan=False)


@pytest.mark.parametrize("degree", [0,-1,2.5,True,"2",None,float("nan")])
def test_polynomial_invalid_degree(degree):
    with pytest.raises(ValueError,match="degree"):
        regression.polynomial_regression([0.,1.,2.],[1.,2.,3.],degree)


@pytest.mark.parametrize("x,y,degree", [
    ([],[],2),([1.,2.],[3.,4.],2),([1.,2.,3.],[1.,2.],2),
    ([1.,1.,1.],[2.,3.,4.],2),([0.,0.,1.,1.],[1.,1.,2.,2.],2),
    ([0.,1.,np.nan],[1.,2.,3.],2),([0.,1.,2.],[1.,np.inf,3.],2),
    ([[0.],[1.],[2.]],[1.,2.,3.],2),([False,1.,2.],[1.,2.,3.],2),
    (["2020","2021","2022"],[1.,2.,3.],2),
    ([0.,1.,2.],[None,2.,3.],2),
    (np.array([2**53,2**53+1,2**53+2]),[1.,2.,3.],2),
])
def test_polynomial_invalid_data(x,y,degree):
    with pytest.raises(ValueError):
        regression.polynomial_regression(x,y,degree)


def test_polynomial_saturated_and_replicate_inputs():
    saturated=regression.polynomial_regression([0.,1.,2.],[1.,3.,9.])
    assert saturated["metrics"]["aic"] is None
    assert saturated["metrics"]["adj_r2"] is None
    x=[3.,0.,1.,1.,2.]
    y=[v*v+1 for v in x]
    result=regression.polynomial_regression(x,y)
    assert result["x"] == x
    np.testing.assert_allclose(result["y_pred"],y,atol=1e-12)
    assert any("Duplicate" in w for w in result["warnings"])


def test_polynomial_rank_and_resource_rejection(monkeypatch):
    from trend_scope.models.stats import polynomial
    with pytest.raises(ValueError,match="Rank"):
        regression.polynomial_regression(np.linspace(0,1,51),np.ones(51),50)
    monkeypatch.setattr(polynomial,"MAX_DESIGN_BYTES",8)
    with pytest.raises(ValueError,match="budget"):
        regression.polynomial_regression([0.,1.,2.],[1.,2.,3.])


def test_polynomial_readonly_float32_and_degree_one():
    x=np.arange(20,dtype=np.float32)[::2]
    y=3*x+2
    x.flags.writeable=False
    result=regression.polynomial_regression(x,y,np.int64(1))
    linear=regression.linear_regression(x,y)
    np.testing.assert_allclose(result["y_pred"],linear["y_pred"],atol=1e-12)
    assert not x.flags.writeable
    assert result["parameters"]["c_1"] == pytest.approx(3.)


def test_polynomial_registry_and_scientific_adapter():
    from trend_scope.models.contracts import ScientificDataset, VariableData, TimeCoordinate, Provenance, AnalysisRequest
    from trend_scope.models.execution import analyze
    from trend_scope.models.registry import default_registry
    from trend_scope.models.serialization import dumps
    data=ScientificDataset("fixture",{"rain":VariableData(np.array([1.,2.,5.,10.]),("time",),"mm")},{},
        Provenance("analytic","simulation",True),time=TimeCoordinate(np.arange(4.),"day","2020-01-01","gregorian"))
    registry=default_registry()
    result=analyze(data,AnalysisRequest("a","polynomial","rain"),registry)
    spec,_=registry.resolve("polynomial")
    assert spec.parameter_defaults == {"degree":2}
    assert spec.version == result.method_version
    assert result.parameters == {"degree":2}
    assert result.metric_units["c_2"] == "(mm)/(day)^2"
    assert result.provenance == data.provenance
    np.testing.assert_allclose(result.payload["y_pred"],data.variables["rain"].values,atol=1e-12)
    json.loads(dumps(result))
    for params in ({"degree":4},{"degree":True},{"unexpected":1}):
        with pytest.raises(ValueError):
            analyze(data,AnalysisRequest("a","polynomial","rain",params),registry)


def test_polynomial_adapter_rejects_duplicate_times_and_mask():
    from dataclasses import replace
    from trend_scope.models.contracts import ScientificDataset, VariableData, TimeCoordinate, Provenance, AnalysisRequest
    from trend_scope.models.execution import analyze
    from trend_scope.models.registry import default_registry
    data=ScientificDataset("fixture",{"v":VariableData(np.array([1.,2.,5.,10.]),("time",),"K")},{},
        Provenance("analytic","simulation",True),time=TimeCoordinate(np.array([0.,1.,1.,3.]),"day","2020-01-01","gregorian"))
    with pytest.raises(ValueError,match="increasing"):
        analyze(data,AnalysisRequest("a","polynomial","v"),default_registry())
    masked=replace(data,variables={"v":replace(data.variables["v"],invalid=np.array([False,True,False,False]))})
    with pytest.raises(ValueError,match="Missing"):
        analyze(masked,AnalysisRequest("a","polynomial","v"),default_registry())


def test_polynomial_does_not_silently_discard_numpy_mask():
    with pytest.raises(ValueError,match="mask"):
        regression.polynomial_regression([0.,1.,2.],np.ma.array([1.,999.,4.],mask=[False,True,False]))


@pytest.mark.parametrize("scale",[1e-200,1e200])
def test_polynomial_unrepresentable_original_coefficients(scale):
    # The normalized polynomial is identifiable, but c_2=1/scale**2 is not representable.
    with pytest.raises(ValueError,match="representable"):
        regression.polynomial_regression(np.array([0.,1.,2.])*scale,[0.,1.,4.])


def test_polynomial_permutation_and_origin_conversion():
    rng=np.random.default_rng(5)
    x=np.arange(15.)
    y=x*x+2*x+7+rng.normal(0,.01,15)
    baseline=regression.polynomial_regression(x,y)
    order=rng.permutation(15)
    shuffled=regression.polynomial_regression(x[order],y[order])
    changed=regression.polynomial_regression(x+1000,y+273.15)
    np.testing.assert_allclose(np.array(shuffled["y_pred"])[np.argsort(order)],baseline["y_pred"],rtol=1e-12,atol=1e-12)
    np.testing.assert_allclose(np.array(changed["y_pred"])-273.15,baseline["y_pred"],rtol=1e-12,atol=1e-12)
    assert changed["metrics"]["rmse"] == pytest.approx(baseline["metrics"]["rmse"],abs=1e-12)


def test_polynomial_linalg_failure_is_actionable(monkeypatch):
    def fail(*args,**kwargs):
        raise np.linalg.LinAlgError("synthetic failure")
    monkeypatch.setattr(np.linalg,"lstsq",fail)
    with pytest.raises(ValueError,match="solver failed"):
        regression.polynomial_regression([0.,1.,2.],[1.,2.,5.])
