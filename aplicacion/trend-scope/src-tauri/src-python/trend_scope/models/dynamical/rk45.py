
import numpy as np
from numba import njit


@njit(cache=True)
def rk45(
    rhs,
    y0,
    t_span,
    rtol=1e-6,
    atol=1e-9,
    initial_step=0.0,
    max_step=np.inf,
    min_step=1e-12,
    max_steps=100000,
):
    """
    Dormand-Prince RK45 (5th/4th order).

    Parameters
    ----------
    rhs : Numba-compatible function
        rhs(t, y) -> dy/dt
    y0 : ndarray
        Initial state.
    t_span : tuple
        (t_initial, t_final).
    rtol, atol : float
        Relative and absolute tolerances.
    initial_step : float
        Initial step. Zero selects an automatic initial step.
    max_step, min_step : float
        Step limits.
    max_steps : int
        Maximum number of iterations.

    Returns
    -------
    times : ndarray
        Accepted time coordinates.
    states : ndarray
        Corresponding state values.
    """

    t0, tf = t_span

    if tf <= t0:
        raise ValueError("Invalid time interval")

    y = np.asarray(y0, dtype=np.float64).copy()

    if rtol <= 0.0 or atol <= 0.0:
        raise ValueError("Tolerances must be positive")

    if min_step <= 0.0 or max_step < min_step:
        raise ValueError("Invalid step limits")

    t = t0

    h = initial_step
    if h <= 0.0:
        h = (tf - t0) / 100.0

    h = min(max(h, min_step), max_step, tf - t0)

    times_buffer = np.empty(max_steps + 1, dtype=np.float64)
    states_buffer = np.empty(
        (max_steps + 1,) + y.shape,
        dtype=np.float64
    )

    times_buffer[0] = t
    states_buffer[0] = y

    accepted = 1

    for _ in range(max_steps):

        if t >= tf:
            break

        h = min(h, max_step, tf - t)

        k1 = rhs(t, y)

        k2 = rhs(
            t + h / 5.0,
            y + h * (k1 / 5.0)
        )

        k3 = rhs(
            t + 3.0 * h / 10.0,
            y + h * (
                3.0 * k1 / 40.0
                + 9.0 * k2 / 40.0
            )
        )

        k4 = rhs(
            t + 4.0 * h / 5.0,
            y + h * (
                44.0 * k1 / 45.0
                - 56.0 * k2 / 15.0
                + 32.0 * k3 / 9.0
            )
        )

        k5 = rhs(
            t + 8.0 * h / 9.0,
            y + h * (
                19372.0 * k1 / 6561.0
                - 25360.0 * k2 / 2187.0
                + 64448.0 * k3 / 6561.0
                - 212.0 * k4 / 729.0
            )
        )

        k6 = rhs(
            t + h,
            y + h * (
                9017.0 * k1 / 3168.0
                - 355.0 * k2 / 33.0
                + 46732.0 * k3 / 5247.0
                + 49.0 * k4 / 176.0
                - 5103.0 * k5 / 18656.0
            )
        )

        y5 = y + h * (
            35.0 * k1 / 384.0
            + 500.0 * k3 / 1113.0
            + 125.0 * k4 / 192.0
            - 2187.0 * k5 / 6784.0
            + 11.0 * k6 / 84.0
        )

        k7 = rhs(t + h, y5)

        y4 = y + h * (
            5179.0 * k1 / 57600.0
            + 7571.0 * k3 / 16695.0
            + 393.0 * k4 / 640.0
            - 92097.0 * k5 / 339200.0
            + 187.0 * k6 / 2100.0
            + k7 / 40.0
        )

        error_sum = 0.0
        size = y.size

        for j in range(size):
            scale = atol + rtol * max(abs(y.flat[j]), abs(y5.flat[j]))
            error = (y5.flat[j] - y4.flat[j]) / scale
            error_sum += error * error

        error_norm = np.sqrt(error_sum / size)

        if not np.isfinite(error_norm):
            raise FloatingPointError("Non-finite integration error")

        if error_norm <= 1.0:
            t += h
            y = y5

            times_buffer[accepted] = t
            states_buffer[accepted] = y
            accepted += 1

        if error_norm == 0.0:
            factor = 5.0
        else:
            factor = min(
                5.0,
                max(0.2, 0.9 * error_norm ** (-0.2))
            )

        h *= factor

        if h < min_step:
            raise RuntimeError("RK45 reached min_step")

    if t < tf:
        raise RuntimeError("RK45 reached max_steps")

    return (
        times_buffer[:accepted].copy(),
        states_buffer[:accepted].copy()
    )
