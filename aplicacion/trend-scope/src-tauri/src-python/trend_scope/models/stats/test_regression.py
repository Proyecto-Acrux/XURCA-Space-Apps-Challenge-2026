import pytest
import numpy as np
from trend_scope.models.stats import regression

def test_linear_regression():
    x = [1.0, 2.0, 3.0, 4.0, 5.0]
    y = [2.0, 4.0, 6.0, 8.0, 10.0]

    result = regression.linear_regression(x, y)

    assert result["algorithm"] == "linear_regression"
    assert pytest.approx(result["parameters"]["slope"], rel=1e-5) == 2.0
    assert pytest.approx(result["parameters"]["intercept"], rel=1e-5) == 0.0
    assert pytest.approx(result["metrics"]["r2"], rel=1e-5) == 1.0

def test_polynomial_regression():
    x = [1.0, 2.0, 3.0, 4.0]
    y = [1.0, 4.0, 9.0, 16.0]  # y = x^2

    result = regression.polynomial_regression(x, y, degree=2)

    assert result["algorithm"] == "polynomial_regression"
    assert pytest.approx(result["metrics"]["r2"], rel=1e-5) == 1.0
