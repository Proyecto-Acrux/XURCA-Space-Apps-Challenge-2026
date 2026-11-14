import pytest
from trend_scope.main import execute_regression, RegressionPayload

def test_execute_regression_success():
    # Armamos el payload simulando lo que mandaría la UI
    payload = RegressionPayload(
        algorithm="linear",
        x=[1.0, 2.0, 3.0, 4.0],
        y=[2.0, 4.0, 6.0, 8.0]
    )

    response = execute_regression(payload)

    assert response["success"] is True
    assert response["data"]["algorithm"] == "linear_regression"
    assert response["data"]["parameters"]["slope"] == 2.0

def test_execute_regression_error():
    # Probamos manejo de errores (ej: algoritmo inexistente)
    payload = RegressionPayload(
        algorithm="inventado",
        x=[1.0, 2.0],
        y=[2.0, 4.0]
    )

    response = execute_regression(payload)

    assert response["success"] is False
    assert "error" in response
