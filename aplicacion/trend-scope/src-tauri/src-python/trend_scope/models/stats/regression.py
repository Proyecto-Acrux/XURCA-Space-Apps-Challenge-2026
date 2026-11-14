import numpy as np
from numba import njit
from trend_scope.models.stats.schemas import FitOutput

# =====================================================================
# 1. NÚCLEO COMPILADO CON NUMBA (@njit)
# =====================================================================

@njit(cache=True)
def _jit_linear_fit(x: np.ndarray, y: np.ndarray) -> tuple[float, float]:
    """Mínimos cuadrados ordinarios en un solo recorrido: y = slope * x + intercept."""
    n = x.shape[0]
    sum_x = 0.0
    sum_y = 0.0
    sum_xy = 0.0
    sum_xx = 0.0

    for i in range(n):
        xi = x[i]
        yi = y[i]
        sum_x += xi
        sum_y += yi
        sum_xy += xi * yi
        sum_xx += xi * xi

    denom = n * sum_xx - sum_x * sum_x
    if denom == 0.0:
        return 0.0, sum_y / n

    slope = (n * sum_xy - sum_x * sum_y) / denom
    intercept = (sum_y - slope * sum_x) / n
    return slope, intercept


@njit(cache=True)
def _jit_vandermonde(x: np.ndarray, degree: int) -> np.ndarray:
    """Construye la matriz de Vandermonde [x^d, ..., x^1, 1]."""
    n = x.shape[0]
    cols = degree + 1
    V = np.empty((n, cols), dtype=np.float64)

    for i in range(n):
        val = 1.0
        for j in range(cols - 1, -1, -1):
            V[i, j] = val
            val *= x[i]

    return V


@njit(cache=True)
def _jit_poly_fit(x: np.ndarray, y: np.ndarray, degree: int) -> np.ndarray:
    """Ajuste polinómico estándar mediante mínimos cuadrados."""
    V = _jit_vandermonde(x, degree)
    coeffs, _, _, _ = np.linalg.lstsq(V, y)
    return coeffs


@njit(cache=True)
def _jit_ridge_poly_fit(
    x: np.ndarray, y: np.ndarray, degree: int, alpha: float
) -> np.ndarray:
    """
    Ajuste polinómico con regularización Ridge (L2): (V^T V + alpha * I) c = V^T y.
    No penaliza el término independiente (intercepto).
    """
    V = _jit_vandermonde(x, degree)
    cols = degree + 1
    VtV = V.T @ V
    Vty = V.T @ y

    # Penalización L2 en todos los coeficientes excepto el intercepto (última columna)
    for j in range(cols - 1):
        VtV[j, j] += alpha

    coeffs = np.linalg.solve(VtV, Vty)
    return coeffs


@njit(cache=True)
def _jit_eval_poly(x: np.ndarray, coeffs: np.ndarray) -> np.ndarray:
    """Evalúa un polinomio mediante el algoritmo de Horner."""
    n = x.shape[0]
    m = coeffs.shape[0]
    y_pred = np.empty(n, dtype=np.float64)

    for i in range(n):
        acc = 0.0
        xi = x[i]
        for j in range(m):
            acc = acc * xi + coeffs[j]
        y_pred[i] = acc

    return y_pred


@njit(cache=True)
def _jit_harmonic_fit(
    x: np.ndarray, y: np.ndarray, period: float, harmonics: int, trend_degree: int
) -> tuple[np.ndarray, np.ndarray]:
    """Ajusta tendencia polinómica + series de Fourier (estacionalidad)."""
    n = x.shape[0]
    num_cols = (trend_degree + 1) + (2 * harmonics)
    X_mat = np.empty((n, num_cols), dtype=np.float64)
    two_pi_over_p = 2.0 * np.pi / period

    for i in range(n):
        xi = x[i]
        val = 1.0
        for d in range(trend_degree + 1):
            X_mat[i, d] = val
            val *= xi

        col_idx = trend_degree + 1
        for k in range(1, harmonics + 1):
            angle = k * two_pi_over_p * xi
            X_mat[i, col_idx] = np.cos(angle)
            X_mat[i, col_idx + 1] = np.sin(angle)
            col_idx += 2

    coeffs, _, _, _ = np.linalg.lstsq(X_mat, y)
    y_pred = X_mat @ coeffs
    return coeffs, y_pred


@njit(cache=True)
def _jit_compute_metrics(
    y_true: np.ndarray, y_pred: np.ndarray, num_params: int
) -> tuple[np.ndarray, float, float, float, float, float]:
    """
    Calcula residuales y métricas de bondad de ajuste en un recorrido:
    - R² (coeficiente de determinación)
    - R² ajustado
    - RMSE (raíz del error cuadrático medio)
    - MAE (error absoluto medio)
    - AIC (criterio de información de Akaike, útil para comparar modelos)
    """
    n = y_true.shape[0]
    residuals = np.empty(n, dtype=np.float64)

    mean_y = 0.0
    for i in range(n):
        mean_y += y_true[i]
    mean_y /= n

    ss_res = 0.0
    ss_tot = 0.0
    abs_err = 0.0

    for i in range(n):
        res = y_true[i] - y_pred[i]
        residuals[i] = res
        ss_res += res * res
        abs_err += np.abs(res)

        diff = y_true[i] - mean_y
        ss_tot += diff * diff

    r2 = 1.0 - (ss_res / ss_tot) if ss_tot != 0.0 else 0.0

    if n > num_params + 1 and ss_tot != 0.0:
        adj_r2 = 1.0 - ((1.0 - r2) * (n - 1) / (n - num_params - 1))
    else:
        adj_r2 = r2

    mse = ss_res / n
    rmse = np.sqrt(mse)
    mae = abs_err / n
    aic = n * np.log(mse) + 2.0 * num_params if mse > 0.0 else -np.inf

    return residuals, r2, adj_r2, rmse, mae, aic


# =====================================================================
# 2. FUNCIONES PÚBLICAS (Para llamar desde los Handlers)
# =====================================================================

def linear_regression(x: list[float], y: list[float]) -> FitOutput:
    """Ajuste lineal: y = slope * x + intercept."""
    x_arr, y_arr = _validate_inputs(x, y)
    slope, intercept = _jit_linear_fit(x_arr, y_arr)
    y_pred = _jit_eval_poly(x_arr, np.array([slope, intercept], dtype=np.float64))

    params = {"slope": float(slope), "intercept": float(intercept)}
    return _build_output("linear_regression", x_arr, y_arr, y_pred, params)


def polynomial_regression(
    x: list[float], y: list[float], degree: int = 2
) -> FitOutput:
    """Ajuste polinómico: y = c_n*x^n + ... + c_1*x + c_0."""
    if degree < 1:
        raise ValueError("El grado del polinomio debe ser >= 1.")

    x_arr, y_arr = _validate_inputs(x, y)
    if x_arr.shape[0] <= degree:
        raise ValueError("Se necesitan más puntos de datos que el grado del polinomio.")

    coeffs = _jit_poly_fit(x_arr, y_arr, degree)
    y_pred = _jit_eval_poly(x_arr, coeffs)

    params = {f"c_{degree - i}": float(c) for i, c in enumerate(coeffs)}
    return _build_output("polynomial_regression", x_arr, y_arr, y_pred, params)


def ridge_regression(
    x: list[float], y: list[float], degree: int = 3, alpha: float = 1.0
) -> FitOutput:
    """Ajuste polinómico con regularización L2 (Ridge) para evitar sobreajuste."""
    if degree < 1:
        raise ValueError("El grado del polinomio debe ser >= 1.")
    if alpha < 0.0:
        raise ValueError("El parámetro de regularización 'alpha' debe ser >= 0.")

    x_arr, y_arr = _validate_inputs(x, y)
    coeffs = _jit_ridge_poly_fit(x_arr, y_arr, degree, alpha)
    y_pred = _jit_eval_poly(x_arr, coeffs)

    params = {f"c_{degree - i}": float(c) for i, c in enumerate(coeffs)}
    return _build_output("ridge_regression", x_arr, y_arr, y_pred, params)


def exponential_regression(x: list[float], y: list[float]) -> FitOutput:
    """Ajuste exponencial: y = a * exp(b * x). Requiere y > 0."""
    x_arr, y_arr = _validate_inputs(x, y)
    if np.any(y_arr <= 0.0):
        raise ValueError("Todos los valores de 'y' deben ser estrictamente mayores a 0.")

    b, log_a = _jit_linear_fit(x_arr, np.log(y_arr))
    a = float(np.exp(log_a))
    y_pred = a * np.exp(b * x_arr)

    params = {"a": a, "b": float(b)}
    return _build_output("exponential_regression", x_arr, y_arr, y_pred, params)


def logarithmic_regression(x: list[float], y: list[float]) -> FitOutput:
    """Ajuste logarítmico: y = a + b * ln(x). Requiere x > 0."""
    x_arr, y_arr = _validate_inputs(x, y)
    if np.any(x_arr <= 0.0):
        raise ValueError("Todos los valores de 'x' deben ser estrictamente mayores a 0.")

    b, a = _jit_linear_fit(np.log(x_arr), y_arr)
    y_pred = a + b * np.log(x_arr)

    params = {"a": float(a), "b": float(b)}
    return _build_output("logarithmic_regression", x_arr, y_arr, y_pred, params)


def power_regression(x: list[float], y: list[float]) -> FitOutput:
    """Ajuste potencial (ley de potencias): y = a * x^b. Requiere x > 0 e y > 0."""
    x_arr, y_arr = _validate_inputs(x, y)
    if np.any(x_arr <= 0.0) or np.any(y_arr <= 0.0):
        raise ValueError("Todos los valores de 'x' e 'y' deben ser mayores a 0.")

    b, log_a = _jit_linear_fit(np.log(x_arr), np.log(y_arr))
    a = float(np.exp(log_a))
    y_pred = a * np.power(x_arr, b)

    params = {"a": a, "b": float(b)}
    return _build_output("power_regression", x_arr, y_arr, y_pred, params)


def harmonic_regression(
    x: list[float],
    y: list[float],
    period: float,
    harmonics: int = 2,
    trend_degree: int = 1,
) -> FitOutput:
    """Ajuste de tendencia polinómica + estacionalidad mediante series de Fourier."""
    if period <= 0.0:
        raise ValueError("El periodo debe ser mayor que 0.")
    if harmonics < 1:
        raise ValueError("Debe haber al menos 1 armónico.")
    if trend_degree < 0:
        raise ValueError("El grado de tendencia debe ser >= 0.")

    x_arr, y_arr = _validate_inputs(x, y)
    min_points = (trend_degree + 1) + (2 * harmonics)
    if x_arr.shape[0] <= min_points:
        raise ValueError(f"Se necesitan más de {min_points} puntos para este ajuste.")

    coeffs, y_pred = _jit_harmonic_fit(x_arr, y_arr, period, harmonics, trend_degree)

    params: dict[str, float] = {}
    for d in range(trend_degree + 1):
        params[f"trend_c{d}"] = float(coeffs[d])

    idx = trend_degree + 1
    for k in range(1, harmonics + 1):
        params[f"cos_{k}"] = float(coeffs[idx])
        params[f"sin_{k}"] = float(coeffs[idx + 1])
        idx += 2

    return _build_output("harmonic_regression", x_arr, y_arr, y_pred, params)


# =====================================================================
# 3. UTILIDADES DE VALIDACIÓN Y FORMATEO
# =====================================================================

def _validate_inputs(x: list[float], y: list[float]) -> tuple[np.ndarray, np.ndarray]:
    if len(x) != len(y):
        raise ValueError("Las listas 'x' e 'y' deben tener la misma longitud.")
    if len(x) < 2:
        raise ValueError("Se necesitan al menos 2 puntos para ajustar un modelo.")

    x_arr = np.asarray(x, dtype=np.float64)
    y_arr = np.asarray(y, dtype=np.float64)

    if np.isnan(x_arr).any() or np.isnan(y_arr).any():
        raise ValueError("Los datos contienen valores NaN. Límpialos antes de modelar.")
    if np.isinf(x_arr).any() or np.isinf(y_arr).any():
        raise ValueError("Los datos contienen valores infinitos.")

    return x_arr, y_arr


def _build_output(
    algorithm: str,
    x_arr: np.ndarray,
    y_true: np.ndarray,
    y_pred: np.ndarray,
    parameters: dict[str, float],
) -> FitOutput:
    residuals, r2, adj_r2, rmse, mae, aic = _jit_compute_metrics(
        y_true, y_pred, len(parameters)
    )
    return {
        "algorithm": algorithm,
        "x": x_arr.tolist(),
        "y_pred": y_pred.tolist(),
        "residuals": residuals.tolist(),
        "parameters": parameters,
        "metrics": {
            "r2": float(r2),
            "adj_r2": float(adj_r2),
            "rmse": float(rmse),
            "mae": float(mae),
            "aic": float(aic),
        },
    }
