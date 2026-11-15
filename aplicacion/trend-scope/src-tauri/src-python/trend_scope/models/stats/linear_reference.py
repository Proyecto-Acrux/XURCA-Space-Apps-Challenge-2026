"""Frozen stage-0 NumPy implementation for tests/benchmarks only; never registered."""
import numpy as np
from trend_scope.models.stats.schemas import LinearFitOutput

def linear_regression(x: list[float], y: list[float]) -> LinearFitOutput:
    """OLS descriptivo con intercepto, centrado y escalado (versión 1, candidate).

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
            if any(isinstance(value, (bool, np.bool_)) for value in values):
                raise ValueError(f"'{name}' no admite booleanos.")
            arr = np.asarray(raw, dtype=np.float64)
        except (TypeError, ValueError, OverflowError) as error:
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
    # Shift first to preserve small differences around a large time/value origin.
    # Scaling centered vectors avoids squaring large or tiny physical units.
    try:
        with np.errstate(over="raise", invalid="raise", divide="raise", under="raise"):
            dx = x_arr - x_arr[0]
            dy = y_arr - y_arr[0]
            mx = np.sum(dx / n)
            my = np.sum(dy / n)
            xc, yc = dx - mx, dy - my
            sx, sy = np.max(np.abs(xc)), np.max(np.abs(yc))
            u = xc / sx
            if sy == 0:
                slope = 0.0
                fitted_delta = np.full(n, my)
            else:
                v = yc / sy
                beta = np.dot(u, v) / np.dot(u, u)
                slope = (beta * sy) / sx
                fitted_delta = my + (beta * u) * sy
            intercept = (y_arr[0] + my) - slope * (x_arr[0] + mx)
            y_pred = y_arr[0] + fitted_delta
            residuals = y_arr - y_pred
            scale = np.max(np.abs(residuals))
            rmse = 0.0 if scale == 0 else scale * np.sqrt(np.mean((residuals / scale) ** 2))
            mae = np.sum(np.abs(residuals) / n)
            r2 = None if sy == 0 else 1.0 - np.sum((residuals / sy) ** 2) / np.dot(yc / sy, yc / sy)
            adj_r2 = None if r2 is None or n <= 2 else 1.0 - (1.0 - r2) * (n - 1) / (n - 2)
            # Gaussian maximized likelihood: slope, intercept AND variance (k=3).
            aic = None if rmse == 0 else n * (np.log(2.0 * np.pi) + 1.0 + 2.0 * np.log(rmse)) + 6.0
    except FloatingPointError as error:
        raise ValueError("Rango numérico no representable; recentrá o reescalá las entradas.") from error
    numbers = [slope, intercept, rmse, mae] + [v for v in (r2, adj_r2, aic) if v is not None]
    if not np.isfinite(numbers).all() or not np.isfinite(y_pred).all() or not np.isfinite(residuals).all():
        raise ValueError("El ajuste excede el rango numérico finito.")
    if sy == 0:
        warnings.append("Serie constante: R² y R² ajustado no definidos (null).")
    if n == 2:
        warnings.append("Dos observaciones: sin grados de libertad residuales; R² ajustado null.")
    if aic is None:
        warnings.append("Error residual cero: AIC gaussiano no finito, representado como null.")
    else:
        warnings.append("AIC supone errores gaussianos independientes con varianza constante; supuestos no verificados.")
    if np.unique(x_arr).size != n:
        warnings.append("Hay x duplicados: se conservan como réplicas con igual peso; revisar duplicados temporales.")
    if np.any(x_arr[1:] < x_arr[:-1]):
        warnings.append("x no está ordenado; se conserva el orden de los pares.")
    # Use normalized coordinates to avoid overflow in interval subtraction.
    steps = np.diff(u)
    if n > 2 and not np.allclose(steps, steps[0], rtol=1e-7, atol=0.0):
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
        "method_version": "1.0.0-candidate", "n_observations": int(n),
    }

