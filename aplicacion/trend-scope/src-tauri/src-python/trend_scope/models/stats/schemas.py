from typing import TypedDict


class FitOutput(TypedDict):
    """Contrato estándar de salida para cualquier algoritmo de ajuste o regresión."""
    algorithm: str
    x: list[float]
    y_pred: list[float]
    residuals: list[float]
    parameters: dict[str, float]
    metrics: dict[str, float]
