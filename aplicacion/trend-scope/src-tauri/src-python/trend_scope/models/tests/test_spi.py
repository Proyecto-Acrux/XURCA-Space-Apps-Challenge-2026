"""W03: analytical oracle, distribution checks, invariants, failures and registry."""
from dataclasses import replace

import numpy as np
import pytest
from scipy.stats import gamma, norm

from trend_scope.models.catalog_registry import catalog_registry
from trend_scope.models.climate.spi import spi
from trend_scope.models.contracts import AnalysisRequest, Provenance, ScientificDataset, TimeCoordinate, VariableData
from trend_scope.models.execution import analyze
from trend_scope.models.serialization import dumps


def months(n):
    return np.arange(n) % 12 + 1


def sample(years=30):
    return np.random.default_rng(7303).gamma(2.5, 8., years*12)


def test_known_exponential_fit_and_zero_mass():
    # For positives [1-d,1+d], mean=1 and mean(log(x))=-EulerGamma.
    # The gamma MLE equation log(a)-digamma(a)=EulerGamma has a=1;
    # beta=mean/a=1. The third calibration value is exactly zero: q=1/3.
    d = np.sqrt(1-np.exp(-2*np.euler_gamma))
    values = np.repeat([0., 1-d, 1+d], 12)
    result = spi(values, months(36), np.ones(36, bool), scale=1, min_count=3)
    params = result['parameters']
    np.testing.assert_allclose(params['shape'], 1., rtol=1e-10)
    np.testing.assert_allclose(params['scale'], 1., rtol=1e-10)
    np.testing.assert_allclose(params['zero_probability'], 1/3)
    np.testing.assert_array_equal(params['n'], np.full(12, 3))
    np.testing.assert_array_equal(params['n_positive'], np.full(12, 2))
    expected = norm.ppf(1/3+(2/3)*(-np.expm1(-values)))
    np.testing.assert_allclose(result['spi'], expected, atol=1e-10)
    assert result['valid'].all()


@pytest.mark.parametrize('scale', [1, 3, 6, 12, 25])
def test_independent_rolling_sum_reference(scale):
    values = sample(8)
    result = spi(values, months(len(values)), np.ones(len(values), bool),
                 scale=scale, min_count=2)
    # Explicit windows independently check block aggregation and month alignment.
    sums = np.array([sum(values[end-scale+1:end+1]) for end in range(scale-1, len(values))])
    expected = np.empty(len(sums))
    for month in range(1, 13):
        selected = months(len(values))[scale-1:] == month
        shape, _, beta = gamma.fit(sums[selected], floc=0)
        assert result['parameters']['shape'][month-1] == pytest.approx(shape, rel=1e-9)
        assert result['parameters']['scale'][month-1] == pytest.approx(beta, rel=1e-9)
        expected[selected] = norm.ppf(gamma.cdf(sums[selected], shape, scale=beta))
    np.testing.assert_allclose(result['spi'][scale-1:], expected, atol=1e-9)
    assert not result['valid'][:scale-1].any()
    assert result['valid'][scale-1:].all()
    np.testing.assert_array_equal(result['spi'][:scale-1], np.zeros(scale-1))


def test_generated_gamma_calibration_is_approximately_standard_normal():
    values = sample(1000)
    result = spi(values, months(len(values)), np.ones(len(values), bool), scale=1, min_count=30)
    assert abs(result['spi'].mean()) < .02
    assert abs(result['spi'].std()-1) < .03
    np.testing.assert_allclose(np.quantile(result['spi'], [.1, .5, .9]), norm.ppf([.1, .5, .9]), atol=.06)
    np.testing.assert_allclose(result['parameters']['shape'], 2.5, rtol=.15)
    np.testing.assert_allclose(result['parameters']['scale'], 8., rtol=.15)


@pytest.mark.parametrize('scale', [1, 3, 6, 12, 25])
def test_no_calibration_leakage_with_boundaries_and_holes(scale):
    values = sample(40)
    mask = np.ones(len(values), bool)
    mask[:17] = mask[-19:] = False
    mask[95:98] = False
    mask[222] = False
    original = spi(values, months(len(values)), mask, scale=scale, min_count=2)
    changed = values.copy()
    changed[~mask] = 1e6
    other = spi(changed, months(len(values)), mask, scale=scale, min_count=2)
    for key in original['parameters']:
        np.testing.assert_array_equal(other['parameters'][key], original['parameters'][key])
    eligible = np.zeros(len(values), bool)
    for end in range(scale-1, len(values)):
        eligible[end] = mask[end-scale+1:end+1].all()
    np.testing.assert_array_equal(original['calibration_valid'], eligible)
    np.testing.assert_array_equal(original['spi'][eligible], other['spi'][eligible])


def test_unit_scaling_invariance_and_input_preservation():
    values = sample()
    groups, mask = months(len(values)), np.ones(len(values), bool)
    before = values.copy(), groups.copy(), mask.copy()
    original = spi(values, groups, mask, scale=3, min_count=10)
    converted = spi(values/10, groups, mask, scale=3, min_count=10)
    np.testing.assert_allclose(original['spi'], converted['spi'], atol=1e-10)
    np.testing.assert_allclose(original['parameters']['shape'], converted['parameters']['shape'])
    np.testing.assert_allclose(original['parameters']['scale']/10, converted['parameters']['scale'])
    for actual, expected in zip((values, groups, mask), before):
        np.testing.assert_array_equal(actual, expected)


def test_minimum_and_twenty_year_warning_boundary():
    for years in (2, 19, 20):
        values = sample(years)
        result = spi(values, months(len(values)), np.ones(len(values), bool), scale=1, min_count=2)
        assert any('fewer than 20 years' in w for w in result['warnings']) == (years < 20)
    values = sample(3)
    mask = np.ones(36, bool)
    mask[months(36) == 7] = False
    with pytest.raises(ValueError, match='Group 7'):
        spi(values, months(36), mask, scale=1, min_count=2)


@pytest.mark.parametrize('values', [np.zeros(36), np.ones(36),
                                  np.repeat([0., 0., 2.], 12), np.repeat([0., 2., 2.], 12)])
def test_undefined_gamma_cases(values):
    with pytest.raises(ValueError, match='Group 1.*distinct positive'):
        spi(values, months(36), np.ones(36, bool), scale=1, min_count=1)


def test_clipping_and_dry_windows_after_large_values():
    calibration = sample(3)
    values = np.concatenate((calibration, np.zeros(12), np.full(12, 1e6)))
    mask = np.arange(len(values)) < len(calibration)
    result = spi(values, months(len(values)), mask, scale=1, min_count=2, epsilon=.001)
    assert np.isfinite(result['spi']).all()
    assert (result['spi'][36:48] < 0).all()
    assert (result['spi'][48:] > 0).all()
    # The inverse/CDF round-trip can round an interior probability to its bound.
    np.testing.assert_allclose(result['spi'][36:48], norm.ppf(np.nextafter(.001, 1.)), atol=1e-14)
    np.testing.assert_allclose(result['spi'][48:], norm.ppf(np.nextafter(.999, 0.)), atol=1e-14)
    assert (norm.cdf(result['spi']) >= .001-1e-15).all()
    assert (norm.cdf(result['spi']) <= .999+1e-15).all()
    # No cumulative subtraction: exact zero windows remain zero after big totals.
    values = np.concatenate((sample(5), np.full(12, 1e12), np.zeros(12)))
    result = spi(values, months(len(values)), np.arange(len(values)) < 60, scale=3, min_count=2)
    np.testing.assert_allclose(result['spi'][-10:], norm.ppf(np.nextafter(1e-6, 1.)), atol=1e-12)


@pytest.mark.parametrize('name,value', [('scale', 0), ('scale', True), ('scale', 1.5),
    ('scale', 1000), ('min_count', 0), ('min_count', True), ('min_count', 2.5),
    ('min_count', 1000), ('epsilon', 0), ('epsilon', -.1), ('epsilon', .5),
    ('epsilon', np.inf), ('epsilon', np.nan), ('epsilon', True), ('epsilon', 1e-30)])
def test_invalid_parameters(name, value):
    parameters = dict(scale=1, min_count=2)
    parameters[name] = value
    with pytest.raises(ValueError):
        spi(sample(3), months(36), np.ones(36, bool), **parameters)


@pytest.mark.parametrize('which,change', [
    ('totals', lambda x: np.full(36, np.nan)), ('totals', lambda x: -x),
    ('totals', lambda x: np.full(36, np.inf)), ('totals', lambda x: x.astype(complex)),
    ('totals', lambda x: np.ones(36, bool)), ('totals', lambda x: x.reshape(3, 12)),
    ('totals', lambda x: np.ma.array(x, mask=False)), ('totals', lambda x: []),
    ('groups', lambda x: x.astype(float)), ('groups', lambda x: x-1),
    ('groups', lambda x: x[::-1]), ('groups', lambda x: np.ones(36, int)),
    ('groups', lambda x: np.ma.array(x)), ('groups', lambda x: x[:-1]),
    ('calibration', lambda x: x.astype(int)), ('calibration', lambda x: x[:-1]),
    ('calibration', lambda x: np.ma.array(x)), ('calibration', lambda x: ~x),
])
def test_invalid_inputs(which, change):
    inputs = dict(totals=sample(3), groups=months(36), calibration=np.ones(36, bool))
    inputs[which] = change(inputs[which])
    with pytest.raises(ValueError):
        spi(**inputs, scale=1, min_count=2)


def test_overflow_and_required_parameters():
    with pytest.raises(ValueError, match='rescale'):
        spi(np.full(36, 1e308), months(36), np.ones(36, bool), scale=3, min_count=2)
    with pytest.raises(TypeError):
        spi(sample(3), months(36), np.ones(36, bool), scale=1)
    with pytest.raises(TypeError):
        spi(sample(3), months(36), np.ones(36, bool), min_count=2)


def dataset():
    values = sample(4)
    return ScientificDataset('spi-fixture', {
        'rain': VariableData(values, ('time',), 'mm'),
        'months': VariableData(months(len(values)), ('time',), '1'),
        'base': VariableData(np.ones(len(values), int), ('time',), '1')}, {},
        Provenance('synthetic', 'simulation', True),
        TimeCoordinate(np.arange(len(values), dtype=float), 'month', '2000-01-01', 'gregorian'))


def request(**overrides):
    return AnalysisRequest('spi-test', 'spi', 'rain',
        dict(groups='months', calibration='base', scale=3, min_count=2, **overrides))


def test_registry_and_serialization():
    registry = catalog_registry(include_optional=False)
    spec, _ = registry.resolve('spi')
    assert spec.min_observations == 24
    assert spec.parameter_defaults == {'epsilon': 1e-6}
    source = dataset()
    result = analyze(source, request(), registry)
    assert result.metric_units['spi'] == '1'
    assert result.metric_units['parameters.scale'] == 'mm'
    assert result.metric_units['parameters.shape'] == '1'
    assert result.metric_units['scale'] == 'month'
    assert result.provenance == source.provenance
    assert result.transformations == source.transformations
    assert result.uncertainty == 'not_estimated'
    for value in (result, result.payload):
        encoded = dumps(value)
        assert 'NaN' not in encoded and 'Infinity' not in encoded


@pytest.mark.parametrize('change', ['daily', 'gaps', 'duplicate', 'rate', 'masked', 'fractional_mask', 'labels_unit'])
def test_registry_rejects_wrong_inputs(change):
    source = dataset()
    if change == 'daily':
        source = replace(source, time=replace(source.time, unit='day'))
    elif change in ('gaps', 'duplicate'):
        times = source.time.values.copy()
        times[-1] += 1 if change == 'gaps' else -1
        source = replace(source, time=replace(source.time, values=times))
    else:
        variables = dict(source.variables)
        if change == 'rate':
            variables['rain'] = replace(variables['rain'], unit='mm/day')
        elif change == 'masked':
            variables['rain'] = replace(variables['rain'], invalid=np.ones(48, bool))
        elif change == 'fractional_mask':
            variables['base'] = replace(variables['base'], values=np.full(48, .5))
        else:
            variables['months'] = replace(variables['months'], unit='month')
        source = replace(source, variables=variables)
    with pytest.raises(ValueError):
        analyze(source, request(), catalog_registry(include_optional=False))


@pytest.mark.parametrize('missing', ['groups', 'calibration', 'scale', 'min_count'])
def test_registry_requires_explicit_parameters(missing):
    params = dict(request().parameters)
    del params[missing]
    with pytest.raises(ValueError):
        analyze(dataset(), replace(request(), parameters=params), catalog_registry(include_optional=False))
