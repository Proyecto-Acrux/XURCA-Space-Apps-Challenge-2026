import numpy as np
from numba import njit
from trend_scope.models.stats.linear_kernel import linear_kernel
from trend_scope.models.stats.schemas import FitOutput, LinearFitOutput, PolynomialFitOutput
from trend_scope.models.stats.polynomial import fit_polynomial

# =====================================================================
# 1. NÚCLEO COMPILADO CON NUMBA (@njit)
# =====================================================================

@njit(cache=True)
def _jit_linear_fit(x: np.ndarray, y: np.ndarray) -> tuple[float, float]:
    """Reuse the stable linear kernel for legacy transformed-response fits."""
    # Reuse the preserved stable kernel for legacy transformed regressions.
    result = linear_kernel(x, y)
    return result[0], result[1]


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
    # Same raw-monomial penalty, without squaring the condition number.
    augmented = np.zeros((len(y)+cols, cols))
    target = np.zeros(len(y)+cols)
    augmented[:len(y)] = V
    target[:len(y)] = y
    for j in range(cols-1):
        augmented[len(y)+j, j] = np.sqrt(alpha)
    coeffs, _, rank, _ = np.linalg.lstsq(augmented, target)
    if rank != cols:
        raise ValueError('Ridge design is numerically rank deficient; rescale input')
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

    coeffs, _, rank, _ = np.linalg.lstsq(X_mat, y)
    if rank != num_cols:
        raise ValueError('Harmonic design is numerically rank deficient; rescale input')
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

def linear_regression(x: list[float], y: list[float]) -> LinearFitOutput:
    """OLS descriptivo con kernel Numba centrado (versión 1.1, candidate).

    Requiere vectores reales finitos de igual longitud, n >= 2 y x variable.
    No elimina nulos ni convierte fechas. Para tendencias, el llamador debe
    expresar x como tiempo transcurrido y conservar su unidad y origen.
    La pendiente tiene unidad y/x; intercepto, RMSE y MAE tienen unidad y.
    Conserva el orden y permite réplicas e intervalos irregulares con avisos.
    No estima incertidumbre ni valida pronósticos. Ver LINEAR_REGRESSION.md.
    """
    arrays = []
    for name, values in (("x", x), ("y", y)):
        try:
            raw = np.asarray(values)
            if raw.ndim != 1 or raw.dtype.kind not in "iuf":
                raise ValueError(f"'{name}' debe ser un vector numérico real.")
            if raw.dtype.kind in "iu" and (np.any(raw > 2**53) or np.any(raw < -(2**53))):
                raise ValueError("Enteros fuera del rango exacto float64; convertir a tiempo relativo primero.")
            if not isinstance(values, np.ndarray) and any(isinstance(value, (bool, np.bool_)) for value in values):
                raise ValueError(f"'{name}' no admite booleanos.")
            arr = np.ascontiguousarray(raw, dtype=np.float64)
        except (TypeError, OverflowError) as error:
            raise ValueError(f"'{name}' debe ser un vector numérico real finito.") from error
        if not np.isfinite(arr).all():
            raise ValueError(f"'{name}' contiene valores no finitos o faltantes.")
        arrays.append(arr)
    x_arr, y_arr = arrays
    n = x_arr.size
    if n != y_arr.size or n < 2:
        raise ValueError("Se requieren al menos 2 pares y longitudes iguales.")
    if np.all(x_arr == x_arr[0]):
        raise ValueError("La pendiente no es identificable: 'x' es constante.")

    warnings = [
        "Ajuste descriptivo: autocorrelación, estacionalidad y heterocedasticidad no evaluadas.",
        "No estima significancia ni incertidumbre; no es un pronóstico validado.",
        "Pendiente en unidad(y)/unidad(x); el llamador conserva unidades, origen temporal y procedencia.",
    ]
    slope, intercept, y_pred, residuals, r2, rmse, mae, constant, descending, duplicate, irregular = linear_kernel(x_arr, y_arr)
    r2 = None if constant else r2
    adj_r2 = None if r2 is None or n <= 2 else 1.0 - (1.0 - r2) * (n - 1) / (n - 2)
    aic = None if rmse == 0 or n == 2 else n * (np.log(2.0 * np.pi) + 1.0 + 2.0 * np.log(rmse)) + 6.0
    numbers = [slope, intercept, rmse, mae] + [v for v in (r2, adj_r2, aic) if v is not None]
    if not np.isfinite(numbers).all():
        raise ValueError("El ajuste excede el rango numerico finito.")
    if constant:
        warnings.append("Serie constante: R² y R² ajustado no definidos (null).")
    if n == 2:
        warnings.append("Dos observaciones: sin grados de libertad residuales; R² ajustado null.")
    if aic is None:
        warnings.append("Error residual cero o ajuste saturado: AIC gaussiano no definido, representado como null.")
    else:
        warnings.append("AIC supone errores gaussianos independientes con varianza constante; supuestos no verificados.")
    if duplicate or (descending and np.unique(x_arr).size != n):
        warnings.append("Hay x duplicados: se conservan como réplicas con igual peso; revisar duplicados temporales.")
    if descending:
        warnings.append("x no está ordenado; se conserva el orden de los pares.")
    if irregular:
        warnings.append("Espaciado de x no uniforme: ajuste por observación, no ponderado por duración.")
    return {
        "algorithm": "linear_regression", "x": x_arr.tolist(),
        "y_pred": y_pred.tolist(), "residuals": residuals.tolist(),
        "parameters": {"slope": float(slope), "intercept": float(intercept)},
        "metrics": {"r2": None if r2 is None else float(r2),
                    "adj_r2": None if adj_r2 is None else float(adj_r2),
                    "rmse": float(rmse), "mae": float(mae),
                    "aic": None if aic is None else float(aic)},
        "warnings": warnings, "uncertainty": "not_estimated",
        "method_version": "1.1.0-candidate", "n_observations": int(n),
    }


def polynomial_regression(
    x: list[float], y: list[float], degree: int = 2
) -> PolynomialFitOutput:
    """OLS polinómico escalado; conserva c_k originales y añade diagnóstico de rango.

    Ver POLYNOMIAL_REGRESSION.md para unidades, límites y evaluación estable.
    """
    return fit_polynomial(x, y, degree)


def ridge_regression(
    x: list[float], y: list[float], degree: int = 3, alpha: float = 1.0
) -> FitOutput:
    """Ajuste polinómico con regularización L2 (Ridge) para evitar sobreajuste."""
    from ..numeric import integer, scalar
    degree = integer(degree, 'degree')
    alpha = scalar(alpha, 'alpha')
    if degree > 20:
        raise ValueError('Ridge degree exceeds supported resource budget')
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
    if not np.isfinite(a) or a <= 0:
        raise ValueError('Exponential amplitude is not representable; rebase x explicitly')
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
    if not np.isfinite(a) or a <= 0:
        raise ValueError('Power-law amplitude is not representable; rescale inputs')
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
    from ..numeric import integer, scalar
    period = scalar(period, 'period', positive=True)
    harmonics = integer(harmonics, 'harmonics')
    trend_degree = integer(trend_degree, 'trend_degree', 0)
    if harmonics > 100 or trend_degree > 20:
        raise ValueError('Harmonic design resource budget exceeded')
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
    from ..numeric import array
    x, y = array(x, 'x', minimum=2), array(y, 'y', minimum=2)
    if np.all(x == x[0]):
        raise ValueError('Regression requires distinct predictor values')
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
    from ..numeric import finite
    finite(y_pred)
    finite(list(parameters.values()))
    with np.errstate(over='raise', invalid='raise', divide='raise'):
        residuals = finite(y_true-y_pred)
        scale = max(float(np.max(np.abs(residuals))), 1.)
        rmse = finite(scale*np.sqrt(np.mean((residuals/scale)**2)))
        mae = finite(np.mean(np.abs(residuals)))
        centered = y_true-y_true.mean()
        total = finite(np.linalg.norm(centered))
        r2 = None if total == 0 else float(finite(1-(np.linalg.norm(residuals)/total)**2))
    # Transformed and penalized fits need model-specific likelihood/effective df.
    adj_r2 = aic = None
    return {
        "algorithm": algorithm,
        "x": x_arr.tolist(),
        "y_pred": y_pred.tolist(),
        "residuals": residuals.tolist(),
        "parameters": parameters,
        "metrics": {
            "r2": r2,
            "adj_r2": adj_r2,
            "rmse": float(rmse),
            "mae": float(mae),
            "aic": aic,
        },
        "warnings": ["Descriptive fit; uncertainty and predictive reliability are not estimated.",
                     "Adjusted R2 and AIC are not estimated for this transformed/penalized model.",
                     "Exponential and power fits minimize log-response error, not original-scale squared error."],
        "uncertainty": "not_estimated",
        "method_version": "1.1.0-candidate",
    }
