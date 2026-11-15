"""Python handler compatibility after integrating origin/main; not native IPC."""
import numpy as np
import pytest
from trend_scope.handlers.analysis import run_regression_analysis
from trend_scope.models.serialization import dumps


@pytest.mark.parametrize('method,options',[
    ('linear',{}),('polynomial',{'degree':2}),('ridge',{'degree':2,'alpha':1.}),
    ('exponential',{}),('logarithmic',{}),('power',{}),
    ('harmonic',{'period':7.,'harmonics':1,'trend_degree':1}),
])
def test_existing_python_handler_returns_compatible_finite_payload(method,options):
    x=np.arange(1.,21.)
    result=run_regression_analysis(method,x.tolist(),(2*x+3).tolist(),options)
    assert len(result['x'])==len(result['y_pred'])==len(result['residuals'])==20
    assert {'algorithm','parameters','metrics'} <= set(result)
    dumps(result)
