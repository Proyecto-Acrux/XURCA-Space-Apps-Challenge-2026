
import numpy as np
from numba import njit


@njit(cache=True)
def rk4(rhs, y0, t):
    """
    Classical fourth-order Runge-Kutta.

    Parameters
    ----------
    rhs : Numba-compatible function
        rhs(t, y) -> dy/dt
    y0 : ndarray
        Initial state.
    t : ndarray
        Time coordinates (strictly increasing).

    Returns
    -------
    ndarray
        State evolution with shape (len(t), *y0.shape).
    """
    if t.ndim != 1 or t.size < 2:
        raise ValueError("t must be a 1D array with at least two points")

    if np.any(np.diff(t) <= 0):
        raise ValueError("t must be strictly increasing")

    y0 = np.asarray(y0, dtype=np.float64)

    result = np.empty((t.size,) + y0.shape, dtype=np.float64)
    result[0] = y0

    for i in range(t.size - 1):
        ti = t[i]
        h = t[i + 1] - ti
        yi = result[i]

        k1 = rhs(ti, yi)
        k2 = rhs(ti + h / 2.0, yi + h * k1 / 2.0)
        k3 = rhs(ti + h / 2.0, yi + h * k2 / 2.0)
        k4 = rhs(ti + h, yi + h * k3)

        result[i + 1] = yi + (h / 6.0) * (
            k1 + 2.0 * k2 + 2.0 * k3 + k4
        )

    return result
