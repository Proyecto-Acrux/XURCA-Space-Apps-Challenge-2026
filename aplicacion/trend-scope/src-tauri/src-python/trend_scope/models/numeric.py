"""Strict boundaries for new numerical methods; no implicit missing-data policy."""
from numbers import Integral, Real
import numpy as np


def integer(value, name: str, minimum: int = 1) -> int:
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, Integral) or value < minimum:
        raise ValueError(f"{name} must be an integer >= {minimum}")
    return int(value)


def scalar(value, name: str, positive: bool = False) -> float:
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, Real) or not np.isfinite(value):
        raise ValueError(f"{name} must be finite and real")
    if positive and value <= 0:
        raise ValueError(f"{name} must be positive")
    return float(value)


def array(value, name: str, ndim: int = 1, minimum: int = 1) -> np.ndarray:
    if np.ma.isMaskedArray(value):
        raise ValueError(f"{name}: explicitly resolve masked values first")
    raw = np.asarray(value)
    if raw.dtype.kind not in 'iuf' or raw.ndim != ndim or raw.size < minimum:
        raise ValueError(f"{name}: expected a nonempty real {ndim}D array")
    if raw.dtype.kind in 'iu' and (np.any(raw > 2**53) or np.any(raw < -2**53)):
        raise ValueError(f"{name}: integers exceed exact float64 range")
    with np.errstate(over='raise', invalid='raise'):
        result = np.asarray(raw, dtype=np.float64)
    if not np.isfinite(result).all():
        raise ValueError(f"{name}: missing or nonfinite values are unsupported")
    return result


def temporal(times, values, regular: bool = False, minimum: int = 2):
    t, y = array(times, 'times', minimum=minimum), array(values, 'values', minimum=minimum)
    if t.shape != y.shape:
        raise ValueError('Times and values must have the same shape')
    with np.errstate(over='raise', invalid='raise'):
        steps = np.diff(t)
    if np.any(steps <= 0):
        raise ValueError('Times must strictly increase; no sorting or interpolation is implicit')
    if regular and not np.allclose(steps, steps[0], rtol=1e-8, atol=0):
        raise ValueError('Method requires regularly sampled data')
    return t, y


def finite(values, name='result'):
    if not np.isfinite(values).all():
        raise FloatingPointError(f'{name} is nonfinite; rescale the problem')
    return values
