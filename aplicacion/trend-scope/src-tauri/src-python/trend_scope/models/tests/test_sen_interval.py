"""Seven W02 test categories, including an independent SciPy oracle."""
from dataclasses import replace

import numpy as np
import pytest
from scipy.stats import theilslopes

from trend_scope.models.catalog_registry import catalog_registry
from trend_scope.models.contracts import AnalysisRequest, Provenance, ScientificDataset, TimeCoordinate, VariableData
from trend_scope.models.execution import analyze
from trend_scope.models.serialization import dumps
from trend_scope.models.stats.sen_interval import sen_interval


@pytest.mark.parametrize('slope', [2., -3., 0.])
def test_known_linear_and_constant(slope):
    t = np.array([0., .5, 2., 3., 8.])
    result = sen_interval(t, 7+slope*t)
    for key in ('slope', 'lower', 'upper'):
        assert result[key] == pytest.approx(slope)
    assert result['n_pairs'] == 10


@pytest.mark.parametrize('confidence', [.5, .8, .9, .95, .99])
@pytest.mark.parametrize('ties', [False, True])
def test_scipy_independent_reference(confidence, ties):
    rng = np.random.default_rng(3102)
    t = np.cumsum(rng.uniform(.2, 3, 35))
    y = .3*t + rng.normal(0, 4, len(t))
    if ties:
        y = np.round(y/3)*3
    expected = theilslopes(y, t, alpha=confidence)
    result = sen_interval(t, y, confidence=confidence)
    np.testing.assert_allclose([result[k] for k in ('slope', 'lower', 'upper')],
                               [expected.slope, expected.low_slope, expected.high_slope])


def test_transformations_and_nested_intervals():
    t = np.array([0., 1., 3., 7., 8., 10.])
    y = np.array([2., 8., 3., 12., 8., 14.])
    original = sen_interval(t, y)
    shifted = sen_interval(t+100, y+40)
    scaled = sen_interval(t*2, y*6)
    reflected = sen_interval(t, -y)
    for key in ('slope', 'lower', 'upper'):
        assert shifted[key] == pytest.approx(original[key])
        assert scaled[key] == pytest.approx(original[key]*3)
    assert reflected['lower'] == pytest.approx(-original['upper'])
    assert reflected['upper'] == pytest.approx(-original['lower'])
    assert reflected['slope'] == pytest.approx(-original['slope'])
    intervals = [sen_interval(t, y, confidence=c) for c in (.1, .5, .8, .95, .99)]
    for narrow, wide in zip(intervals, intervals[1:]):
        assert wide['lower'] <= narrow['lower'] <= narrow['slope'] <= narrow['upper'] <= wide['upper']


def test_minimum_ties_and_literal_low_confidence():
    result = sen_interval([0, 2], [4, 10], max_pairs=1)
    assert result['n_pairs'] == 1
    assert result['lower'] == result['slope'] == result['upper'] == 3
    t, y = np.arange(6), [1, 1, 1, 2, 2, 3]
    expected = theilslopes(y, t)
    result = sen_interval(t, y)
    assert result['lower'] == expected.low_slope
    assert result['upper'] == expected.high_slope
    # Six slopes sorted: [1, 3, 13/3, 5, 6, 7]. At 10%, ranks are 2 and 3.
    low = sen_interval([0, 1, 2, 3], [0, 1, 6, 13], confidence=.1)
    assert (low['lower'], low['upper']) == pytest.approx((13/3, 5.))
    assert low['confidence'] == .1


def test_iid_simulation_coverage():
    rng = np.random.default_rng(2048)
    t = np.arange(30.)
    covered = 0
    for _ in range(200):
        result = sen_interval(t, 2*t+rng.normal(size=len(t)))
        covered += result['lower'] <= 2 <= result['upper']
    assert .88 <= covered/200 <= 1.


@pytest.mark.parametrize('t,y', [([], []), ([0], [1]), ([0, 0], [1, 2]),
    ([1, 0], [1, 2]), ([0, 1], [1]), ([0, np.nan], [1, 2]),
    ([0, 1], [1, np.inf]), ([0, 1], [1, np.nan]), ([0, 1], [True, False]),
    ([0, 1], [1+1j, 2]), ([[0, 1]], [1, 2]),
    ([0, 1], np.ma.array([1, 2], mask=[False, True])),
    (np.ma.array([0, 1]), [1, 2]), ([0, 1], [2**54, 2**54+1])])
def test_invalid_inputs(t, y):
    with pytest.raises(ValueError):
        sen_interval(t, y)


@pytest.mark.parametrize('confidence', [0, 1, -1, 2, np.nan, np.inf, True, '0.95'])
def test_invalid_confidence(confidence):
    with pytest.raises(ValueError, match='confidence'):
        sen_interval([0, 1], [1, 2], confidence=confidence)


@pytest.mark.parametrize('budget', [0, -1, 1.5, True, np.inf, 2])
def test_pair_budget(budget):
    with pytest.raises(ValueError):
        sen_interval([0, 1, 2], [0, 1, 2], max_pairs=budget)
    assert sen_interval([0, 1, 2], [0, 1, 2], max_pairs=3)['n_pairs'] == 3


@pytest.mark.parametrize('t,y', [([-1e308, 1e308], [0, 1]),
    ([0, 1], [-1e308, 1e308]), ([0, 1e-300], [0, 1e300])])
def test_overflow_controlled(t, y):
    with pytest.raises(ValueError, match='rescale'):
        sen_interval(t, y)


def test_inputs_unchanged_and_large_finite_median():
    t = np.arange(4.)
    y = np.array([0., 1., 2., 3.])*4e307
    original_t, original_y = t.copy(), y.copy()
    result = sen_interval(t, y)
    assert result['slope'] == pytest.approx(4e307)
    np.testing.assert_array_equal(t, original_t)
    np.testing.assert_array_equal(y, original_y)


def dataset():
    return ScientificDataset('fixture', {'v': VariableData(np.array([1., 4., 3., 8.]),
        ('time',), 'K')}, {}, Provenance('synthetic', 'simulation', True),
        TimeCoordinate(np.array([0., 1., 2., 4.]), 'year', '2000-01-01', 'gregorian'))


def test_registry_units_metadata_and_json():
    data = dataset()
    registry = catalog_registry(include_optional=False)
    spec, _ = registry.resolve('sen_interval')
    assert spec.min_observations == 2 and spec.status == 'candidate'
    assert spec.parameter_defaults == {'confidence': .95, 'max_pairs': 2_000_000}
    result = analyze(data, AnalysisRequest('ci', 'sen_interval', 'v', {'confidence': .9}), registry)
    assert result.metric_units == {'slope': '(K)/(year)', 'lower': '(K)/(year)',
        'upper': '(K)/(year)', 'confidence': '1', 'n_pairs': '1'}
    assert result.payload['confidence'] == .9
    assert result.uncertainty == result.payload['uncertainty'] == 'asymptotic_confidence_interval'
    assert result.provenance == data.provenance
    assert result.transformations == data.transformations
    assert any('serial independence' in warning and 'too narrow' in warning for warning in result.warnings)
    for value in (result, result.payload, sen_interval([0, 1], [0, 0])):
        encoded = dumps(value)
        assert 'NaN' not in encoded and 'Infinity' not in encoded


def test_registry_mask_and_unsupported_parameter():
    data = dataset()
    masked = replace(data, variables={'v': replace(data.variables['v'],
                      invalid=np.array([False, True, False, False]))})
    registry = catalog_registry(include_optional=False)
    with pytest.raises(ValueError, match='unmasked'):
        analyze(masked, AnalysisRequest('ci', 'sen_interval', 'v'), registry)
    with pytest.raises(ValueError, match='Unsupported'):
        analyze(data, AnalysisRequest('ci', 'sen_interval', 'v', {'other': 1}), registry)
