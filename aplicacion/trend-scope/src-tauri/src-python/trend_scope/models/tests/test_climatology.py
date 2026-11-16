"""W01: analytic answers, independent formula oracle, properties and integration."""
from dataclasses import replace

import numpy as np
import pytest

from trend_scope.models.climate.climatology import anomalies, climatology
from trend_scope.models.catalog_registry import catalog_registry
from trend_scope.models.contracts import AnalysisRequest, Provenance, ScientificDataset, TimeCoordinate, VariableData
from trend_scope.models.execution import analyze
from trend_scope.models.serialization import dumps


def test_known_statistics_and_anomalies():
    reference = climatology([1, 3, 5, 100], [7]*4, [True]*3+[False], min_count=3)
    for key, expected in dict(mean=3, std=np.sqrt(8/3), median=3, mad=2, count=3).items():
        np.testing.assert_allclose(reference[key], [expected])
    for kind, expected in [('absolute', 2), ('percent', 200/3),
                           ('standardized', 2/np.sqrt(8/3)), ('robust_z', 1/1.4826)]:
        np.testing.assert_allclose(anomalies([5], [7], reference, kind=kind)['values'], [expected])


def test_independent_seasonal_linear_oracle():
    t = np.arange(24)
    groups = t % 4
    cycle = np.array([3, -2, 8, 1])
    values = cycle[groups] + 2*t
    reference = climatology(values, groups, t < 12, min_count=3)
    # Baseline times for group g are g, g+4, g+8: mean time g+4.
    np.testing.assert_allclose(reference['mean'], cycle + 2*(np.arange(4)+4))
    np.testing.assert_allclose(reference['std'], np.full(4, np.sqrt(128/3)))
    np.testing.assert_allclose(reference['median'], cycle + 2*(np.arange(4)+4))
    np.testing.assert_allclose(reference['mad'], np.full(4, 8))
    np.testing.assert_allclose(anomalies(values, groups, reference, kind='absolute')['values'],
                               2*(t-groups-4))


def test_translation_scaling_and_baseline_isolation():
    y = np.array([1., 3., 5., 9.])
    groups, mask = [0]*4, [True]*3+[False]
    original = climatology(y, groups, mask, min_count=3)
    shifted = climatology(y+10, groups, mask, min_count=3)
    scaled = climatology(y*2, groups, mask, min_count=3)
    changed = climatology([1, 3, 5, -1000], groups, mask, min_count=3)
    for key in ('mean', 'std', 'median', 'mad', 'count'):
        np.testing.assert_array_equal(original[key], changed[key])
    for kind in ('absolute', 'standardized', 'robust_z'):
        np.testing.assert_allclose(anomalies(y, groups, original, kind=kind)['values'],
                                   anomalies(y+10, groups, shifted, kind=kind)['values'])
    for kind in ('percent', 'standardized', 'robust_z'):
        np.testing.assert_allclose(anomalies(y, groups, original, kind=kind)['values'],
                                   anomalies(y*2, groups, scaled, kind=kind)['values'])


def test_minimum_constant_ties_and_missing_group():
    reference = climatology([2], [-3], [True], min_count=1)
    assert reference['std'][0] == reference['mad'][0] == 0
    assert anomalies([2], [-3], reference, kind='absolute')['values'][0] == 0
    assert anomalies([2], [-3], reference, kind='percent')['values'][0] == 0
    for kind in ('standardized', 'robust_z'):
        with pytest.raises(ValueError, match='nonzero'):
            anomalies([2], [-3], reference, kind=kind)
    ties = climatology([1, 1, 3], [0]*3, [True]*3, min_count=3)
    assert ties['mad'][0] == 0
    with pytest.raises(ValueError, match='Group 9'):
        climatology([1, 2], [0, 9], [True, False], min_count=1)
    with pytest.raises(ValueError, match='Group 9'):
        anomalies([1], [9], reference, kind='absolute')
    zero = climatology([-1, 1], [0, 0], [True, True], min_count=2)
    with pytest.raises(ValueError, match='nonzero'):
        anomalies([1], [0], zero, kind='percent')


@pytest.mark.parametrize('y,g,b,m', [
    ([], [], [], 1), ([np.nan], [0], [True], 1), ([np.inf], [0], [True], 1),
    ([True], [0], [True], 1), ([1], [0.5], [True], 1), ([1], [True], [True], 1),
    ([1], [0], [1], 1), ([1], [0], [False], 1), ([1], [0], [True], 0),
    ([1], [0], [True], True), ([1], [0], [True], 2), ([1], [], [True], 1),
    (np.ma.array([1], mask=[True]), [0], [True], 1),
])
def test_invalid_climatology(y, g, b, m):
    with pytest.raises(ValueError):
        climatology(y, g, b, min_count=m)


@pytest.mark.parametrize('patch', [{'group_ids': [0, 0]}, {'mean': [np.nan]},
                                  {'std': [-1]}, {'count': [0]}, {'mad': []}])
def test_invalid_reference(patch):
    reference = climatology([1, 3], [0, 0], [True, True], min_count=2)
    with pytest.raises(ValueError):
        anomalies([2], [0], {**reference, **patch}, kind='absolute')


def test_invalid_anomaly_inputs_and_overflow():
    reference = climatology([1, 3], [0, 0], [True, True], min_count=2)
    for y, g, r, kind in [([np.nan], [0], reference, 'absolute'),
                           ([2], [0.1], reference, 'absolute'),
                           ([2], [0], {}, 'absolute'), ([2], [0], reference, 'bad')]:
        with pytest.raises(ValueError):
            anomalies(y, g, r, kind=kind)
    with pytest.raises(ValueError, match='rescale'):
        climatology([1e308, 1e308], [0, 0], [True, True], min_count=2)


def dataset():
    return ScientificDataset('synthetic', {
        'v': VariableData(np.array([1., 3., 5.]), ('time',), 'K'),
        'g': VariableData(np.array([0, 0, 0]), ('time',), '1'),
        'b': VariableData(np.array([1, 1, 0]), ('time',), '1')}, {},
        Provenance('fixture', 'simulation', True),
        TimeCoordinate(np.array([0., 1., 3.]), 'day', '2000-01-01', 'gregorian'))


@pytest.mark.parametrize('method,kind,unit', [('climatology', None, 'K'),
    ('anomalies', 'absolute', 'K'), ('anomalies', 'percent', '%'),
    ('anomalies', 'standardized', '1'), ('anomalies', 'robust_z', '1')])
def test_registry_units_and_serialization(method, kind, unit):
    params = dict(groups='g', baseline='b', min_count=2)
    if kind:
        params['kind'] = kind
    registry = catalog_registry(include_optional=False)
    assert registry.resolve(method)[0].min_observations == 1
    result = analyze(dataset(), AnalysisRequest('test', method, 'v', params), registry)
    assert result.metric_units['values' if kind else 'mean'] == unit
    assert result.provenance == dataset().provenance
    for value in (result, result.payload):
        encoded = dumps(value)
        assert 'NaN' not in encoded and 'Infinity' not in encoded


@pytest.mark.parametrize('params', [{}, dict(groups='missing', baseline='b', min_count=1),
    dict(groups='g', baseline='b'), dict(groups='g', baseline='b', min_count=1)])
def test_registry_required_inputs(params):
    with pytest.raises(ValueError):
        analyze(dataset(), AnalysisRequest('test', 'anomalies', 'v', params),
                catalog_registry(include_optional=False))


def test_registry_rejects_nonbinary_baseline_and_bad_time():
    source = dataset()
    for invalid in (replace(source, variables={**source.variables,
            'b': VariableData(np.array([1, 2, 0]), ('time',), '1')}),
            replace(source, time=replace(source.time, values=np.array([0., 0., 1.])))):
        with pytest.raises(ValueError):
            analyze(invalid, AnalysisRequest('test', 'climatology', 'v',
                    dict(groups='g', baseline='b', min_count=1)), catalog_registry(include_optional=False))
