from typing import Any, Dict, List
from trend_scope.models.stats import regression
from trend_scope.models.stats.schemas import FitOutput

def run_regression_analysis(
    algorithm: str,
    x: List[float],
    y: List[float],
    options: Dict[str, Any] | None = None
) -> FitOutput:
    """Regression algorithm dispatcher."""
            
    from typing import Any, Dict, Optional
    
    from trend_scope.models.stats import regression
    from trend_scope.models.stats.schemas import FitOutput
    
    
    def run_regression_analysis(
        algorithm: str,
        x: list[float],
        y: list[float],
        options: Optional[Dict[str, Any]] = None,
    ) -> FitOutput:
        """Dispatch a regression request to the selected algorithm."""
    
        options = options or {}
    
        if algorithm == "linear":
            return regression.linear_regression(x, y)
    
        if algorithm == "polynomial":
            degree = options.get("degree", 2)
            return regression.polynomial_regression(x, y, degree=degree)
    
        if algorithm == "ridge":
            degree = options.get("degree", 3)
            alpha = options.get("alpha", 1.0)
            return regression.ridge_regression(
                x, y, degree=degree, alpha=alpha
            )
    
        if algorithm == "exponential":
            return regression.exponential_regression(x, y)
    
        if algorithm == "logarithmic":
            return regression.logarithmic_regression(x, y)
    
        if algorithm == "power":
            return regression.power_regression(x, y)
    
        if algorithm == "harmonic":
            return regression.harmonic_regression(
                x,
                y,
                period=options.get("period", 1.0),
                harmonics=options.get("harmonics", 2),
                trend_degree=options.get("trend_degree", 1),
            )
    
        raise ValueError(f"Algoritmo de regresión desconocido: '{algorithm}'")
