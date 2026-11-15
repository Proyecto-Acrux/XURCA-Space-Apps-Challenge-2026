
import numpy as np
from numba import njit, prange
from .rk4 import rk4


@njit(cache=True)
def rk4_multi(rhs, y0, t):
    """
    Multivariable RK4 integrator.

    Integrates a coupled system of ODEs:

        dy_i/dt = f_i(t, y_1, y_2, ..., y_n)

    Parameters
    ----------
    rhs : Numba-compatible function
        Receives (t, y) and returns the derivatives vector.
    y0 : ndarray, shape (n_variables,)
        Initial state.
    t : ndarray, shape (n_times,)
        Strictly increasing time coordinates.

    Returns
    -------
    ndarray, shape (n_times, n_variables)
        State evolution.
    """
    if y0.ndim != 1:
        raise ValueError("y0 must be a 1D array")
    return rk4(rhs, y0, t)

@njit(cache=True)
def rk4_multi_independent(rhs, y0, t):
    """
    Integrates independent ODE systems in parallel.

    rhs receives (t, y_variable, variable_index).

    Parameters
    ----------
    rhs : Numba-compatible function
    y0 : ndarray, shape (n_systems,)
        Initial state of each independent system.
    t : ndarray
        Time coordinates.

    Returns
    -------
    ndarray, shape (n_times, n_systems)
    """
    if y0.ndim != 1:
        raise ValueError("y0 must be a 1D array")

    if t.ndim != 1 or t.size < 2:
        raise ValueError("Invalid time array")

    if np.any(np.diff(t) <= 0):
        raise ValueError("t must be strictly increasing")

    n_times = t.size
    n_systems = y0.size

    result = np.empty((n_times, n_systems), dtype=np.float64)
    result[0] = y0

    for i in range(n_times - 1):
        ti = t[i]
        h = t[i + 1] - ti

        for j in prange(n_systems):
            y = result[i, j]

            k1 = rhs(ti, y, j)
            k2 = rhs(ti + h / 2.0, y + h * k1 / 2.0, j)
            k3 = rhs(ti + h / 2.0, y + h * k2 / 2.0, j)
            k4 = rhs(ti + h, y + h * k3, j)

            result[i + 1, j] = y + (h / 6.0) * (
                k1 + 2.0 * k2 + 2.0 * k3 + k4
            )

    return result
