"""Pure Python application services."""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel

from trend_scope.handlers.analysis import run_regression_analysis


class RegressionPayload(BaseModel):
    algorithm: str
    x: List[float]
    y: List[float]
    options: Optional[Dict[str, Any]] = None


def execute_regression(payload: RegressionPayload) -> Dict[str, Any]:
    """Execute a regression and return a UI-friendly response."""

    try:
        result = run_regression_analysis(
            algorithm=payload.algorithm,
            x=payload.x,
            y=payload.y,
            options=payload.options,
        )

        return {
            "success": True,
            "data": result,
        }

    except Exception as error:
        return {
            "success": False,
            "error": str(error),
        }
