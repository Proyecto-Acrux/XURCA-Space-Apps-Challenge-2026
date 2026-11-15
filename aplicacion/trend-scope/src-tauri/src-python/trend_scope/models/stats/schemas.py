from typing import Optional, TypedDict


class FitOutput(TypedDict):
    """Contrato estándar de salida para cualquier algoritmo de ajuste o regresión."""
    algorithm: str
    x: list[float]
    y_pred: list[float]
    residuals: list[float]
    parameters: dict[str, float]
    metrics: dict[str, Optional[float]]


class LinearFitOutput(FitOutput):
    """Extensión lineal: métricas indefinidas como null y límites explícitos."""

    warnings: list[str]
    uncertainty: str
    method_version: str
    n_observations: int


class PolynomialBasis(TypedDict):
    """y = y_offset + y_scale * sum(coefficients[k] * z**k), z=(x-x_offset)/x_scale."""
    x_offset: float
    x_scale: float
    y_offset: float
    y_scale: float
    coefficients: list[float]  # ascending powers of z


class PolynomialFitOutput(FitOutput):
    warnings: list[str]
    uncertainty: str
    method_version: str
    n_observations: int
    degree: int
    rank: int
    residual_degrees_of_freedom: int
    condition_number: float
    singular_values: list[float]
    rcond: float
    stable_basis: PolynomialBasis
