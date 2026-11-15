"""Classical RK4 on an explicit grid; numerical core, independent of sources/UI."""
import math

import numpy as np
from numba import njit

METHOD_VERSION = "1.0.0-candidate"


@njit(cache=True)
def _product(a, b, c):
    """Multiply three finite floats without avoidable intermediate overflow."""
    if a == 0.0 or b == 0.0 or c == 0.0:
        return 0.0
    ma, ea = math.frexp(a)
    mb, eb = math.frexp(b)
    mc, ec = math.frexp(c)
    value = math.ldexp(ma*mb*mc, ea+eb+ec)
    if not np.isfinite(value) or value == 0.0:
        raise ValueError("RK4 increment is not representable; rescale state/time")
    return value


@njit(cache=True)
def _stage(rhs, time, state, args):
    """Isolate saved states from callbacks and reject bad derivative arrays."""
    if not np.isfinite(state).all():
        raise ValueError("RK4 intermediate state is nonfinite")
    derivative = rhs(time, state.copy(), *args)
    if derivative.shape != state.shape:
        raise ValueError("RHS derivative shape must match state shape")
    if not np.isfinite(derivative).all():
        raise ValueError("RHS returned a nonfinite derivative")
    # An RHS may return its input or reuse a buffer: stages must not alias.
    return derivative.copy()


@njit(cache=True)
def _advance(state, h, slope):
    value = state.copy()
    for j in range(state.size):
        value.flat[j] = state.flat[j] + _product(h, slope.flat[j], 1.0)
    if not np.isfinite(value).all():
        raise ValueError("RK4 intermediate state overflow")
    return value


@njit(cache=True, nogil=True)
def rk4(rhs, y0: np.ndarray, t: np.ndarray, args=(),
        max_output_bytes=256*1024*1024, max_steps=1_000_000) -> np.ndarray:
    """Integrate y'=rhs(t,y,*args); retains the existing rk4(rhs,y0,t) API.

    y0: nonempty real ndarray; t: finite strictly increasing 1D ndarray.
    Returns float64 states with shape (len(t), *y0.shape), in the same order.
    Each grid interval is one RK4 step, including nonuniform grids. Midpoints
    must be representable. No interpolation, error estimate or adaptivity.
    RHS must be Numba-compatible, deterministic, and return a same-shaped array.
    Python/Numba type errors from invalid callbacks are not hidden.
    """
    if t.ndim != 1 or t.size < 2:
        raise ValueError("t must be a 1D array with at least two points")
    if y0.size == 0:
        raise ValueError("Initial state must be nonempty")
    if y0.dtype == np.dtype(np.bool_) or t.dtype == np.dtype(np.bool_):
        raise ValueError("Boolean states/times are not supported")
    if y0.dtype == np.dtype(np.int64) or y0.dtype == np.dtype(np.uint64):
        if np.any(y0 > 2**53) or np.any(y0 < -(2**53)):
            raise ValueError("Integer state exceeds exact float64 range")
    if t.dtype == np.dtype(np.int64) or t.dtype == np.dtype(np.uint64):
        if np.any(t > 2**53) or np.any(t < -(2**53)):
            raise ValueError("Integer time exceeds exact float64 range; normalize first")
    if max_output_bytes <= 0 or max_steps < 1:
        raise ValueError("Resource limits must be positive")
    if t.size-1 > max_steps or t.size > max_output_bytes // 8 // y0.size:
        raise ValueError("RK4 output/step resource budget exceeded")
    times = np.asarray(t, dtype=np.float64)
    y = np.asarray(y0, dtype=np.float64).copy()
    if not np.isfinite(times).all() or not np.isfinite(y).all():
        raise ValueError("RK4 states and times must be finite")
    # Validate the entire grid before allocating output or invoking user code.
    for i in range(times.size-1):
        h = times[i+1]-times[i]
        midpoint = times[i]+h/2.0
        if not np.isfinite(h) or h <= 0:
            raise ValueError("t must strictly increase with finite steps")
        if not times[i] < midpoint < times[i+1]:
            raise ValueError("RK4 midpoint is not representable; rebase/rescale time")
    result = np.empty((times.size,) + y.shape, dtype=np.float64)
    result[0] = y
    for i in range(times.size-1):
        ti, next_time = times[i], times[i+1]
        h = next_time-ti
        midpoint = ti+h/2.0
        k1 = _stage(rhs, ti, y, args)
        k2 = _stage(rhs, midpoint, _advance(y,h/2.0,k1), args)
        k3 = _stage(rhs, midpoint, _advance(y,h/2.0,k2), args)
        k4 = _stage(rhs, next_time, _advance(y,h,k3), args)
        for j in range(y.size):
            scale = max(abs(k1.flat[j]),abs(k2.flat[j]),abs(k3.flat[j]),abs(k4.flat[j]))
            if scale != 0.0:
                weighted = (k1.flat[j]/scale)/6.0 + (k2.flat[j]/scale)/3.0 + (k3.flat[j]/scale)/3.0 + (k4.flat[j]/scale)/6.0
                y.flat[j] += _product(h,scale,weighted)
        if not np.isfinite(y).all():
            raise ValueError("RK4 state overflow; reduce step or rescale the problem")
        result[i+1] = y
    return result
