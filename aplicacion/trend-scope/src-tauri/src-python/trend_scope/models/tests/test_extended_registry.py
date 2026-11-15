from dataclasses import replace
import numpy as np
import pytest
from trend_scope.models.contracts import ScientificDataset, VariableData, TimeCoordinate, Provenance, AnalysisRequest, Coordinate
from trend_scope.models.extended_registry import scientific_registry
from trend_scope.models.registry import default_registry
from trend_scope.models.execution import analyze
from trend_scope.models.serialization import dumps


def data():
    t=np.arange(24.)
    return ScientificDataset('fixture',{'v':VariableData(2*t+1,('time',),'K')},{},
        Provenance('synthetic','simulation',True),TimeCoordinate(t,'day','2020-01-01','gregorian'))


@pytest.mark.parametrize('method,params',[
    ('sen',{}),('mann_kendall',{}),('seasonal_mann_kendall',{'seasons':list(np.tile([0,1],12))}),
    ('cusum',{'baseline':1.,'allowance':1.,'threshold':5.}),('moving_average',{'window':3}),
    ('fir',{'coefficients':[.5,.5]}),('fft',{}),('ssa',{'window':4,'components':[0,1]}),
    ('paa',{'segments':6}),('lttb',{'samples':6}),('naive_forecast',{'horizon':3}),
    ('seasonal_naive_forecast',{'horizon':3,'period':4}),
])
def test_added_registry_json_provenance_and_units(method,params):
    source=data()
    result=analyze(source,AnalysisRequest('test',method,'v',params),scientific_registry(include_optional=False))
    assert result.method_id==method and result.provenance==source.provenance
    assert result.uncertainty=='not_estimated'
    dumps(result)
    if method=='sen':
        assert result.metric_units['slope']=='(K)/(day)'


def test_default_registry_preserved_and_multivariable_adapter():
    assert [s.method_id for s in default_registry().describe()]==['linear','polynomial']
    source=data()
    t=source.time.values
    features=np.column_stack((t,np.sin(t)))
    source=replace(source,variables={**source.variables,'x':VariableData(features,('time','feature'),'mixed',feature_units=('day','1'))},
        coordinates={'feature':Coordinate(np.array(['time','wave']),('feature',),'1')})
    result=analyze(source,AnalysisRequest('a','multivariable','v',{'features':'x'}),scientific_registry())
    np.testing.assert_allclose(result.payload['coefficients'],[2,0],atol=1e-13)
    assert result.payload['coefficient_units']==('(K)/(day)','(K)/(1)')
    dumps(result)
