"""Backtested monthly forecast: candidates vs baselines, honest delivery, residual intervals.

Registered as method `forecast_backtest`. It composes W07 (baselines), W08
(rolling-origin backtest), W09 (intervals) and W20 (forecasters). Rules:
  * candidates (seasonal naive, Holt-Winters, SARIMA with fixed declared orders)
    are scored out of sample on the same origins as the baselines
    (climatology, persistence);
  * if no candidate beats the best baseline at the first horizon step, the
    BASELINE is delivered and flagged `not_superior_to_baseline`;
  * mode 'validated_forecast' needs a delivered model with positive skill over
    the whole requested horizon and an interval whose coverage was measured on
    held-out origins; otherwise 'exploratory_extrapolation';
  * no interval is produced without enough out-of-sample residuals.
"""
from importlib.util import find_spec

import numpy as np

from ..numeric import integer, scalar, temporal
from .backtest import rolling_origin
from .forecasters import climatology_baseline, model_forecaster, persistence_baseline
from .intervals import residual_intervals, split_coverage

VERSION = '1.0.0-candidate'


def _skill_horizon(skill: np.ndarray) -> int:
    """Largest h such that skill > 0 for steps 1..h."""
    count = 0
    for value in skill:
        if np.isfinite(value) and value > 0:
            count += 1
        else:
            break
    return count


def forecast_with_backtest(times, values, groups, *, horizon, period, initial_train=0, max_origins=24,
                           level=0.90, min_residuals=10, min_count=3) -> dict:
    t, y = temporal(times, values, regular=True, minimum=8)
    labels = np.asarray(groups)
    if labels.shape != y.shape or labels.dtype.kind not in 'iu':
        raise ValueError('groups must be one integer label per observation')
    n = len(y)
    h = integer(horizon, 'horizon')
    p = integer(period, 'period', 2)
    origins_cap = integer(max_origins, 'max_origins', 2)
    needed = integer(min_residuals, 'min_residuals')
    first = integer(initial_train, 'initial_train', 0) or max(3 * p, n // 2)
    nominal = scalar(level, 'level')
    spare = n - h - first
    if spare < 0:
        raise ValueError('Series too short for the requested horizon and training window')
    stride = max(1, int(np.ceil(spare / (origins_cap - 1)))) if spare else 1

    baselines = {'climatology': climatology_baseline(labels, min_count=min_count),
                 'persistence': persistence_baseline()}
    candidates = {'seasonal_naive': model_forecaster('seasonal_naive', period=p)}
    if find_spec('statsmodels') is not None:
        candidates['holt_winters'] = model_forecaster('holt_winters', period=p)
        candidates['sarima'] = model_forecaster('sarima', period=p, order=(1, 0, 0), seasonal_order=(0, 1, 1, p))

    warnings, results, failed = [], {}, {}
    for name, function in candidates.items():
        try:
            results[name] = rolling_origin(t, y, forecaster=function, horizon=h, initial_train=first, step=stride,
                                           baselines=baselines)
        except (ValueError, RuntimeError, ImportError, FloatingPointError) as error:
            failed[name] = str(error)[:160]
    if not results:
        raise ValueError('No candidate model could be evaluated: ' + '; '.join(f'{k}: {v}' for k, v in failed.items()))
    for name, reason in failed.items():
        warnings.append(f'Candidate {name} was skipped: {reason}')

    reference = next(iter(results.values()))
    base_mae = {name: float(np.mean(item['mae'])) for name, item in reference['baselines'].items()}
    best_baseline = min(base_mae, key=base_mae.get)
    best_model = min(results, key=lambda name: float(np.mean(results[name]['model']['mae'])))
    chosen = results[best_model]
    skill = chosen['skill'][best_baseline]
    validated_steps = _skill_horizon(skill)
    superior = validated_steps >= 1

    if superior:
        delivered, label, series, function = 'model', best_model, chosen['model'], candidates[best_model]
    else:
        delivered, label, series, function = 'baseline', best_baseline, reference['baselines'][best_baseline], baselines[best_baseline]
        validated_steps = 0
        warnings.append('No candidate beat the best baseline: the baseline is delivered.')

    central = np.asarray(function(t, y, h), dtype=np.float64)
    step = float(t[1] - t[0])
    future = t[-1] + step * np.arange(1, h + 1)
    bounds = residual_intervals(central, series['residuals'], level=nominal, min_residuals=needed)
    lower, upper = bounds['lower'].copy(), bounds['upper'].copy()
    coverage = split_coverage(series['predictions'], chosen['actual'], level=nominal, min_residuals=needed)
    if delivered == 'model' and validated_steps < h:
        lower[validated_steps:], upper[validated_steps:] = np.nan, np.nan
        warnings.append(f'Skill over the baseline holds only for the first {validated_steps} step(s); '
                        'later steps have no nominal interval.')
    calibrated = bool(np.isfinite(lower).any() and coverage['coverage'] is not None)
    if not calibrated:
        warnings.append('Interval coverage could not be measured on held-out origins: treat any interval as uncalibrated.')
    mode = ('validated_forecast' if delivered == 'model' and validated_steps >= h and calibrated
            else 'exploratory_extrapolation')

    summary = {name: {'mae': item['model']['mae'], 'rmse': item['model']['rmse'], 'bias': item['model']['bias'],
                      'skill_vs_climatology': item['skill']['climatology'],
                      'skill_vs_persistence': item['skill']['persistence']}
               for name, item in results.items()}
    return {
        'times': future, 'central': central, 'lower': lower, 'upper': upper,
        'mode': mode, 'delivered': delivered, 'model': label, 'best_candidate': best_model,
        'best_baseline': best_baseline, 'baseline_values': np.asarray(baselines[best_baseline](t, y, h), dtype=np.float64),
        'not_superior_to_baseline': not superior, 'horizon_requested': h, 'horizon_validated': int(validated_steps),
        'skill_vs_best_baseline': skill,
        'interval': {'level': nominal, 'calibrated': calibrated, 'empirical_coverage': coverage['coverage'],
                     'n_calibration_origins': coverage['n_calibration'], 'n_test_origins': coverage['n_test'],
                     'n_residuals': bounds['n_residuals']},
        'backtest': {'design': reference['design'], 'n_origins': reference['n_origins'], 'initial_train': first,
                     'step': stride, 'models': summary,
                     'baselines': {name: {'mae': item['mae'], 'rmse': item['rmse'], 'bias': item['bias']}
                                   for name, item in reference['baselines'].items()}},
        'uncertainty': bounds['uncertainty'] if calibrated else 'not_calibrated',
        'warnings': warnings + ['Statistical forecast of this single series: no physical predictors or scenario.',
                                'Backtest skill does not guarantee future skill; regime changes are not modeled.']}


def analyze_forecast(data, request):
    """Registry adapter: `groups` is a dataset variable ID of calendar-month labels (unit 1)."""
    from ..contracts import AnalysisResult

    variable = data.variables[request.variable]
    if data.time is None or (variable.invalid is not None and variable.invalid.any()):
        raise ValueError('Explicit time coordinates and unmasked observations are required')
    parameters = dict(request.parameters)
    identifier = parameters.pop('groups', None)
    if not isinstance(identifier, str) or identifier not in data.variables:
        raise ValueError('Specify groups as a dataset variable ID')
    group = data.variables[identifier]
    if group.dimensions != ('time',) or group.unit != '1' or (group.invalid is not None and group.invalid.any()):
        raise ValueError('groups must be an unmasked dimensionless time variable')
    for name in ('horizon', 'period'):
        if name not in parameters:
            raise ValueError(f'Specify {name} explicitly')
    payload = forecast_with_backtest(data.time.values, variable.values, group.values, **parameters)
    unit = variable.unit
    return AnalysisResult(
        request.analysis_id, 'forecast_backtest', VERSION, data.dataset_id, request.variable, 'completed',
        'forecast', dict(request.parameters), payload,
        {'central': unit, 'lower': unit, 'upper': unit, 'baseline_values': unit, 'times': data.time.unit,
         'skill_vs_best_baseline': '1'},
        tuple(payload['warnings']), data.provenance,
        {'n_observations': len(data.time.values), 'time_start': data.time.values[0],
         'time_end': data.time.values[-1], 'time_origin': data.time.origin, 'time_unit': data.time.unit,
         'calendar': data.time.calendar, 'value_unit': unit, 'quality': data.quality},
        data.transformations, uncertainty=payload['uncertainty'])
