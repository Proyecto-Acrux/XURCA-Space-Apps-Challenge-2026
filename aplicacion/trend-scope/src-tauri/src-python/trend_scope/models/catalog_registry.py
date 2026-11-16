"""Additive W01 catalog; numeric baseline variables explicitly encode False/True as 0/1."""
from functools import partial

import numpy as np

from .climate.climatology import anomalies, climatology
from .contracts import AnalysisResult
from .extended_registry import scientific_registry
from .numeric import temporal
from .registry import MethodSpec

VERSION = '1.0.0-candidate'


def _run_climate(method, data, request) -> AnalysisResult:
    variable = data.variables[request.variable]
    if variable.invalid is not None and variable.invalid.any():
        raise ValueError('Resolve masked observations before analysis')
    t, y = temporal(data.time.values, variable.values, minimum=1)
    parameters = dict(request.parameters)
    selected = {}
    for name in ('groups', 'baseline'):
        identifier = parameters.pop(name, None)
        if not isinstance(identifier, str) or identifier not in data.variables:
            raise ValueError(f'Specify {name} as a dataset variable ID')
        auxiliary = data.variables[identifier]
        if auxiliary.dimensions != ('time',) or auxiliary.unit != '1' or (
                auxiliary.invalid is not None and auxiliary.invalid.any()):
            raise ValueError(f'{name} must be an unmasked dimensionless time variable')
        selected[name] = auxiliary.values
    baseline = selected['baseline']
    if not np.isin(baseline, [0, 1]).all():
        raise ValueError('baseline variable must encode False/True as 0/1')
    if 'min_count' not in parameters:
        raise ValueError('Specify min_count explicitly')
    reference = climatology(y, selected['groups'], baseline.astype(bool),
                            min_count=parameters.pop('min_count'))
    units = {key: variable.unit for key in ('mean', 'std', 'median', 'mad')}
    units.update(group_ids='1', count='1')
    payload = reference
    if method == 'anomalies':
        if 'kind' not in parameters:
            raise ValueError('Specify kind explicitly')
        payload = anomalies(y, selected['groups'], reference, kind=parameters['kind'])
        units = {'values': variable.unit if parameters['kind'] == 'absolute' else
                 '%' if parameters['kind'] == 'percent' else '1'}
        payload['reference'] = reference
        units.update({f'reference.{key}': variable.unit for key in ('mean', 'std', 'median', 'mad')})
        units.update({'reference.group_ids': '1', 'reference.count': '1'})
    return AnalysisResult(
        request.analysis_id, method, VERSION, data.dataset_id, request.variable,
        'completed', 'summary' if method == 'climatology' else 'anomalies',
        dict(request.parameters), payload, units, tuple(payload['warnings']), data.provenance,
        {'n_observations': len(t), 'time_start': t[0], 'time_end': t[-1],
         'time_origin': data.time.origin, 'time_unit': data.time.unit,
         'calendar': data.time.calendar, 'value_unit': variable.unit, 'quality': data.quality},
        data.transformations)


def catalog_registry(*, include_optional: bool = True):
    """Extend scientific_registry with W01 only; auxiliary inputs are variable IDs."""
    registry = scientific_registry(include_optional=include_optional)
    for method in ('climatology', 'anomalies'):
        registry.register(MethodSpec(
            method_id=method, name=method.title(), version=VERSION, category='climate',
            output_kind='summary' if method == 'climatology' else 'anomalies',
            dimensions=(('time',),), min_observations=1,
            minimum_reason='At least one observation; each group requires explicit min_count baseline observations',
            regularity='strictly increasing; irregular allowed; no missing values',
            parameters=('groups', 'baseline', 'min_count') + (('kind',) if method == 'anomalies' else ()),
            dependencies=('numpy',), complexity='O(n log n) time; O(n) memory',
            acceleration='NumPy grouped reductions; no performance claim'),
            partial(_run_climate, method))
    from .stats.sen_interval import analyze_sen_interval
    registry.register(MethodSpec(
        method_id='sen_interval', name='Theil-Sen confidence interval',
        version='1.0.0-candidate', category='stats', output_kind='estimate',
        dimensions=(('time',),), min_observations=2,
        minimum_reason='Two distinct times identify a slope; small-sample interval coverage is approximate',
        regularity='strictly increasing; irregular allowed; no missing values',
        parameters=('confidence', 'max_pairs'), dependencies=('numpy', 'scipy'),
        complexity='O(N log N) time; O(N+n) memory, N=n*(n-1)/2 <= max_pairs',
        acceleration='NumPy pairwise slopes and sorting; no performance claim',
        parameter_defaults={'confidence': 0.95, 'max_pairs': 2_000_000}),
        analyze_sen_interval)
    from .climate.spi import analyze_spi
    registry.register(MethodSpec(
        method_id='spi', name='Standardized Precipitation Index', version='1.0.0-candidate',
        category='climate', output_kind='index', dimensions=(('time',),),
        min_observations=24,
        minimum_reason='At least two distinct positive calibration sums per calendar month; scale and min_count impose further requirements',
        regularity='consecutive monthly totals; month-index step 1; no missing values',
        parameters=('groups', 'calibration', 'scale', 'min_count', 'epsilon'),
        dependencies=('numpy', 'scipy'),
        complexity='O(n) aggregation and memory; twelve scalar gamma fits, solver dependent',
        acceleration='NumPy block sums and SciPy gamma MLE; no performance claim',
        parameter_defaults={'epsilon': 1e-6}), analyze_spi)
    from .stats.descriptive import analyze_describe
    registry.register(MethodSpec(
        method_id='describe', name='Descriptive statistics', version='1.0.0-candidate',
        category='stats', output_kind='summary', dimensions=(('time',),), min_observations=1,
        minimum_reason='One observation gives count, mean and extremes; the standard deviation needs two',
        regularity='strictly increasing; irregular allowed; no missing values',
        parameters=('quantiles',), dependencies=('numpy',),
        complexity='O(n log n) time; O(n) memory',
        acceleration='NumPy; no performance claim'), analyze_describe)
    from .forecasting.pipeline import analyze_forecast
    registry.register(MethodSpec(
        method_id='forecast_backtest', name='Backtested monthly forecast', version='1.0.0-candidate',
        category='stats', output_kind='forecast', dimensions=(('time',),), min_observations=48,
        minimum_reason='Needs enough history for a training window plus out-of-sample origins; the handler checks the series length',
        regularity='regular monthly grid; no missing values; groups = calendar month (1-12)',
        parameters=('groups', 'horizon', 'period', 'initial_train', 'max_origins', 'level', 'min_residuals', 'min_count'),
        dependencies=('numpy', 'statsmodels (optional candidates)'),
        complexity='one model fit per origin and candidate; origins capped by max_origins',
        acceleration='statsmodels/NumPy; no performance claim',
        parameter_defaults={'initial_train': 0, 'max_origins': 24, 'level': 0.90, 'min_residuals': 10, 'min_count': 3}),
        analyze_forecast)
    return registry
