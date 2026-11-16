"""W08: rolling-origin backtesting with an expanding window and no shuffling."""
from collections.abc import Mapping

import numpy as np

from ..numeric import integer, temporal

VERSION = '1.0.0-candidate'
MAX_ORIGINS = 500


def _metrics(predictions: np.ndarray, actual: np.ndarray) -> dict:
    error = predictions - actual
    return {'mae': np.mean(np.abs(error), axis=0), 'rmse': np.sqrt(np.mean(error ** 2, axis=0)),
            'bias': np.mean(error, axis=0), 'residuals': actual - predictions, 'predictions': predictions}


def rolling_origin(times, values, *, forecaster, horizon, initial_train, step, baselines) -> dict:
    """Evaluate a forecaster out of sample at expanding origins.

    At each origin `o` the forecaster sees only times[:o] and values[:o]
    (callable `(train_times, train_values, horizon) -> predictions`) and is
    scored on the next `horizon` observations. `baselines` is a mapping
    name -> callable with the same signature, evaluated on the same origins.
    Per horizon step: mae, rmse, bias (mean of prediction - observation) and
    out-of-sample `residuals` (observation - prediction), for the model and for
    every baseline, plus `skill` = 1 - mae_model / mae_baseline (NaN where the
    baseline error is zero). Requires a regular series; any transformation the
    forecaster needs must be fitted inside the callable, on the training part.
    Origins: initial_train, initial_train+step, ... while origin+horizon <= n
    (at most 500). Cost: one forecaster fit per origin. Version 1.0.0-candidate.
    """
    t, y = temporal(times, values, regular=True, minimum=4)
    steps_ahead = integer(horizon, 'horizon')
    first = integer(initial_train, 'initial_train', 2)
    stride = integer(step, 'step')
    if not callable(forecaster) or not isinstance(baselines, Mapping) or not baselines \
            or not all(callable(item) for item in baselines.values()):
        raise ValueError('forecaster and every baseline must be callables')
    n = len(y)
    if first + steps_ahead > n:
        raise ValueError('initial_train + horizon exceeds the series length')
    origins = np.arange(first, n - steps_ahead + 1, stride)
    if len(origins) > MAX_ORIGINS:
        raise ValueError(f'More than {MAX_ORIGINS} origins; increase step')

    def collect(function):
        output = np.empty((len(origins), steps_ahead))
        for row, origin in enumerate(origins):
            prediction = np.asarray(function(t[:origin], y[:origin], steps_ahead), dtype=np.float64)
            if prediction.shape != (steps_ahead,) or not np.isfinite(prediction).all():
                raise ValueError('A forecaster returned a prediction with the wrong shape or nonfinite values')
            output[row] = prediction
        return output

    actual = np.stack([y[origin:origin + steps_ahead] for origin in origins])
    model = _metrics(collect(forecaster), actual)
    base = {name: _metrics(collect(function), actual) for name, function in baselines.items()}
    skill = {}
    with np.errstate(divide='ignore', invalid='ignore'):
        for name, result in base.items():
            skill[name] = np.where(result['mae'] > 0, 1 - model['mae'] / result['mae'], np.nan)
    return {'model': model, 'baselines': base, 'skill': skill, 'actual': actual, 'origins': origins,
            'horizon': steps_ahead, 'n_origins': int(len(origins)), 'design': 'expanding_window_rolling_origin',
            'uncertainty': 'not_estimated',
            'warnings': ['Backtest evidence is conditional on the sampled origins; it does not guarantee future skill.']}
