"""W20: callables for rolling-origin backtesting.

Each factory returns `(train_times, train_values, horizon) -> predictions`.
Model orders and periods are explicit arguments: there is no automatic order
search. Models wrap `optional_methods.forecast` without modifying it.
"""
import numpy as np

from ..numeric import integer
from .baselines import climatology_forecast, persistence_forecast

VERSION = '1.0.0-candidate'


def _future_labels(labels: np.ndarray, n: int, horizon: int) -> np.ndarray:
    """Calendar-month labels (1..12) of the steps after the first n observations."""
    last = int(labels[n - 1])
    return ((last - 1 + np.arange(1, horizon + 1)) % 12) + 1


def climatology_baseline(groups, *, min_count):
    """Baseline callable: calendar-month means of the training window only."""
    labels = np.asarray(groups)
    needed = integer(min_count, 'min_count')

    def run(train_times, train_values, horizon):
        n = len(train_values)
        return climatology_forecast(train_values, labels[:n], _future_labels(labels, n, horizon),
                                    min_count=needed)['values']
    return run


def persistence_baseline():
    def run(train_times, train_values, horizon):
        return persistence_forecast(train_values, horizon=horizon)['values']
    return run


def model_forecaster(method, *, period=None, order=(1, 0, 0), seasonal_order=(0, 0, 0, 0)):
    """Wrap one method of `optional_methods.forecast` (seasonal_naive, holt_winters, sarima, ...)."""
    from ..optional_methods import forecast

    def run(train_times, train_values, horizon):
        output = forecast(train_times, train_values, horizon=horizon, method=method, period=period,
                          order=order, seasonal_order=seasonal_order, validation_size=1)
        return output['values']
    return run
