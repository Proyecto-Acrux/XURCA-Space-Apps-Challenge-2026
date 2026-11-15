"""Float64 OLS kernel; no metadata, Python objects, fastmath or parallel reductions."""
import math

import numpy as np
from numba import njit


@njit(cache=True)
def _add(total: float, correction: float, value: float) -> tuple[float, float]:
    adjusted = value - correction
    updated = total + adjusted
    return updated, (updated - total) - adjusted


@njit(cache=True, nogil=True)
def linear_kernel(x: np.ndarray, y: np.ndarray) -> tuple[
    float, float, np.ndarray, np.ndarray, float, float, float, bool, bool, bool, bool
]:
    """Validated 1D finite float64 arrays -> coefficients, arrays, metrics, flags.

    Shift, scale, and center before compensated reductions. Two output arrays
    and constant auxiliary storage. Raises ValueError for unrepresentable ranges.
    Equal weights; O(n), deterministic serial summation. Private numeric API.
    """
    n = x.size
    if n < 2 or y.size != n:
        raise ValueError("At least two equally sized arrays required")
    sx = 0.0
    sy = 0.0
    descending = False
    duplicate = False
    for i in range(n):
        dx, dy = x[i] - x[0], y[i] - y[0]
        if not np.isfinite(dx) or not np.isfinite(dy):
            raise ValueError("Unrepresentable numeric span; recenter/rescale inputs")
        sx = max(sx, abs(dx))
        sy = max(sy, abs(dy))
        if i > 0:
            descending = descending or x[i] < x[i-1]
            duplicate = duplicate or x[i] == x[i-1]
    if sx == 0.0:
        raise ValueError("Slope is not identifiable for constant x")
    mx = my = cx = cy = 0.0
    for i in range(n):
        mx, cx = _add(mx, cx, (x[i]-x[0])/sx)
        if sy != 0.0:
            my, cy = _add(my, cy, (y[i]-y[0])/sy)
    mx /= n
    my /= n
    xx = xy = yy = cxx = cxy = cyy = 0.0
    for i in range(n):
        u = (x[i]-x[0])/sx - mx
        v = 0.0 if sy == 0.0 else (y[i]-y[0])/sy - my
        xx, cxx = _add(xx, cxx, u*u)
        xy, cxy = _add(xy, cxy, u*v)
        yy, cyy = _add(yy, cyy, v*v)
    if xx == 0.0:
        raise ValueError("Numerically degenerate predictor")
    beta = xy/xx
    # Exponent arithmetic avoids overflow/underflow in beta*sy before division.
    ma, ea = math.frexp(beta)
    mb, eb = math.frexp(sy)
    mc, ec = math.frexp(sx)
    slope = math.ldexp(ma*mb/mc, ea+eb-ec)
    if not np.isfinite(slope) or (slope == 0.0 and beta != 0.0 and sy != 0.0):
        raise ValueError("Slope is not representable in float64")
    intercept = (y[0] + sy*my) - slope*(x[0] + sx*mx)
    if not np.isfinite(intercept):
        raise ValueError("Intercept is not representable in float64")
    fitted = np.empty(n, dtype=np.float64)
    residuals = np.empty(n, dtype=np.float64)
    rs = 0.0
    irregular = False
    first_step = (x[1]-x[0])/sx
    for i in range(n):
        fitted[i] = y[0] + sy*(my + beta*((x[i]-x[0])/sx-mx))
        residuals[i] = y[i]-fitted[i]
        if not np.isfinite(fitted[i]) or not np.isfinite(residuals[i]):
            raise ValueError("Fit/residuals are not representable in float64")
        rs = max(rs, abs(residuals[i]))
        if i > 1:
            step = (x[i]-x[i-1])/sx
            irregular = irregular or abs(step-first_step) > 1e-7*abs(first_step)
    squares = absolute = cs = ca = 0.0
    if rs != 0.0:
        for i in range(n):
            r = residuals[i]/rs
            squares, cs = _add(squares, cs, r*r)
            absolute, ca = _add(absolute, ca, abs(r))
    rmse = rs*math.sqrt(squares/n)
    mae = rs*(absolute/n)
    if rs != 0.0 and (rmse == 0.0 or mae == 0.0):
        raise ValueError("Error metrics underflow float64; rescale the response")
    r2 = 0.0 if sy == 0.0 else 1.0 - ((rs/sy)**2)*(squares/yy)
    return slope, intercept, fitted, residuals, r2, rmse, mae, sy == 0.0, descending, duplicate, irregular
