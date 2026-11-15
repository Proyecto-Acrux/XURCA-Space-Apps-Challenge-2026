"""Scaled polynomial OLS using native NumPy LAPACK; no normal equations."""
import math
from decimal import Decimal, localcontext

import numpy as np

from .schemas import PolynomialFitOutput

# Deployment resource guards, not scientific sufficiency thresholds.
MAX_DESIGN_BYTES = 64 * 1024 * 1024
MAX_WORK_UNITS = 100_000_000  # n * (degree+1)**2; rough least-squares work proxy


def _original_coefficients(coeffs: np.ndarray, offset: float, scale: float,
                           y_offset: float, y_scale: float) -> np.ndarray:
    """Transform the small coefficient vector without silent float64 underflow.

    Decimal (standard library C implementation) is used ONLY at the output
    boundary, O(degree**2), not for the n-observation solve or evaluation.
    It does not recover precision lost in the fitted coefficients.
    """
    with localcontext() as context:
        context.prec = 80
        a = -Decimal.from_float(offset)/Decimal.from_float(scale)
        b = Decimal(1)/Decimal.from_float(scale)
        converted = [Decimal.from_float(float(coeffs[-1]))]
        for coefficient in coeffs[-2::-1]:
            expanded = [Decimal(0)]*(len(converted)+1)
            for index, value in enumerate(converted):
                expanded[index] += a*value
                expanded[index+1] += b*value
            expanded[0] += Decimal.from_float(float(coefficient))
            converted = expanded
        converted = [value*Decimal.from_float(y_scale) for value in converted]
        converted[0] += Decimal.from_float(y_offset)
        result = np.array([float(value) for value in converted])
        if not np.isfinite(result).all() or any(value != 0 and number == 0 for value, number in zip(converted,result)):
            raise ValueError("Original-coordinate coefficients are not representable; rescale x/y explicitly")
        return result


def _vector(values: list[float], name: str) -> np.ndarray:
    if np.ma.isMaskedArray(values):
        raise ValueError("MaskedArray requires an explicit mask/preprocessing policy")
    try:
        raw = np.asarray(values)
    except (TypeError, ValueError, OverflowError) as error:
        raise ValueError(f"{name} must be a numeric vector") from error
    if raw.ndim != 1 or raw.dtype.kind not in "iuf":
        raise ValueError(f"{name} must be a one-dimensional real numeric vector")
    if not isinstance(values, np.ndarray) and any(isinstance(v, (bool, np.bool_)) for v in values):
        raise ValueError(f"{name} must not contain booleans")
    if raw.dtype.kind in "iu" and (np.any(raw > 2**53) or np.any(raw < -(2**53))):
        raise ValueError("Integers exceed exact float64 range; normalize before conversion")
    with np.errstate(over="raise", invalid="raise"):
        try:
            array = np.ascontiguousarray(raw, dtype=np.float64)
        except (FloatingPointError, OverflowError) as error:
            raise ValueError("Input exceeds finite float64 range") from error
    if not np.isfinite(array).all():
        raise ValueError("Nonfinite/missing data require explicit preprocessing")
    return array


def fit_polynomial(x: list[float], y: list[float], degree: int = 2) -> PolynomialFitOutput:
    """Equal-weight polynomial fit, retaining legacy original-coordinate coefficients.

    Require integer degree>=1, n>=degree+1 and full numerical column rank.
    Arrays/coordinates are not sorted, filtered or interpolated. Use stable_basis
    to evaluate around large origins; raw c_k can suffer catastrophic cancellation.
    No uncertainty, significance or forecast validation is inferred.
    """
    if isinstance(degree, (bool, np.bool_)) or not isinstance(degree, (int, np.integer)) or degree < 1:
        raise ValueError("degree must be an integer >= 1")
    degree = int(degree)
    x_arr, y_arr = _vector(x, "x"), _vector(y, "y")
    n, p = x_arr.size, degree + 1
    if y_arr.size != n or n < p:
        raise ValueError("Equal-length inputs and at least degree+1 observations required")
    if n*p*8 > MAX_DESIGN_BYTES or n*p*p > MAX_WORK_UNITS:
        raise ValueError("Polynomial design exceeds resource budget; reduce degree or input size explicitly")
    if np.all(x_arr == x_arr[0]):
        raise ValueError("Polynomial coefficients are not identifiable for constant x")
    warnings = [
        "Historical polynomial fit; not a validated forecast. Extrapolation can be unstable.",
        "Autocorrelation, seasonality, heteroscedasticity and errors in x are not evaluated.",
        "c_k has unit(y)/unit(x)^k; a polynomial has no single constant slope.",
        "Use stable_basis for evaluation; original-coordinate coefficients may cancel severely.",
    ]
    try:
        with np.errstate(over="raise", invalid="raise", divide="raise"):
            offset = float(np.min(x_arr)/2 + np.max(x_arr)/2)
            scale = float(np.max(np.abs(x_arr-offset)))
            if scale == 0:
                raise ValueError("Predictor cannot be scaled in float64")
            z = (x_arr-offset)/scale
            y_offset = float(y_arr[0])
            delta = y_arr-y_offset
            y_scale = float(np.max(np.abs(delta)))
            target = np.zeros(n) if y_scale == 0 else delta/y_scale
            design = np.polynomial.polynomial.polyvander(z, degree)
            rcond = float(max(n, p)*np.finfo(np.float64).eps)
            coeffs, _, rank, singular = np.linalg.lstsq(design, target, rcond=rcond)
            if rank != p:
                raise ValueError("Rank-deficient polynomial: lower degree or provide distinct, better-spaced x")
            condition = float(singular[0]/singular[-1])
            if y_scale == 0:
                coeffs[:] = 0.
                y_pred = np.full(n, y_offset)
                raw_coeffs = np.zeros(p)
                raw_coeffs[0] = y_offset
            else:
                y_pred = y_offset + y_scale*np.polynomial.polynomial.polyval(z, coeffs)
                # Convert by composition only for legacy output, never to calculate fitted values.
                raw_coeffs = _original_coefficients(coeffs, offset, scale, y_offset, y_scale)
            residuals = y_arr-y_pred
            rs = float(np.max(np.abs(residuals)))
            if rs == 0:
                rmse = mae = 0.
            else:
                residual_scaled = residuals/rs
                rmse = float(rs*np.sqrt(np.mean(residual_scaled**2)))
                mae = float(rs*np.mean(np.abs(residual_scaled)))
                if rmse == 0 or mae == 0:
                    raise ValueError("Error metrics underflow; rescale y explicitly")
            if y_scale == 0:
                r2 = adj_r2 = None
            else:
                centered = target - np.mean(target)
                r2 = float(1.-np.sum((residuals/y_scale)**2)/np.dot(centered, centered))
                adj_r2 = None if n == p else float(1.-(1.-r2)*(n-1)/(n-p))
            aic = None if rs == 0 or n == p else float(n*(math.log(2*math.pi)+1+2*math.log(rmse))+2*(p+1))
    except (FloatingPointError, OverflowError, np.linalg.LinAlgError) as error:
        raise ValueError("Polynomial fit/coefficients not representable or solver failed; rescale or lower degree") from error
    if any(not np.isfinite(array).all() for array in (raw_coeffs, coeffs, y_pred, residuals, singular)):
        raise ValueError("Nonfinite polynomial result; rescale or lower degree")
    if not all(math.isfinite(v) for v in (condition, rmse, mae) + tuple(v for v in (r2, adj_r2, aic) if v is not None)):
        raise ValueError("Nonfinite polynomial metrics")
    if y_scale == 0:
        warnings.append("Constant response: R2 and adjusted R2 are undefined (null).")
    if n == p:
        warnings.append("Saturated interpolation: zero residual degrees of freedom; adjusted R2 and AIC null.")
    if aic is None:
        warnings.append("Gaussian AIC is undefined for a saturated or zero-residual fit (null).")
    else:
        warnings.append("AIC assumes independent Gaussian errors with constant variance; assumptions unchecked.")
    if np.unique(x_arr).size != n:
        warnings.append("Duplicate x retained as equal-weight replicates; check temporal duplicates.")
    if np.any(x_arr[1:] < x_arr[:-1]):
        warnings.append("Unsorted pairs retained in their original order.")
    steps = np.diff(z)
    if n > 2 and not np.allclose(steps, steps[0], rtol=1e-7, atol=0.):
        warnings.append("Irregular x spacing: equal observation weights, not duration weights.")
    return {
        "algorithm": "polynomial_regression", "x": x_arr.tolist(), "y_pred": y_pred.tolist(),
        "residuals": residuals.tolist(), "parameters": {f"c_{k}": float(raw_coeffs[k]) for k in range(degree, -1, -1)},
        "metrics": {"r2": r2, "adj_r2": adj_r2, "rmse": rmse, "mae": mae, "aic": aic},
        "warnings": warnings, "uncertainty": "not_estimated", "method_version": "1.0.0-candidate",
        "n_observations": int(n), "degree": degree, "rank": int(rank),
        "residual_degrees_of_freedom": int(n-p), "condition_number": condition,
        "singular_values": singular.tolist(), "rcond": rcond,
        "stable_basis": {"x_offset": offset, "x_scale": scale, "y_offset": y_offset,
                         "y_scale": y_scale, "coefficients": coeffs.tolist()},
    }
