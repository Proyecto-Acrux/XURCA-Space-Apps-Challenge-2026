import numpy as np
from trend_scope.models.contracts import ScientificDataset, VariableData, TimeCoordinate, Coordinate, Provenance, AnalysisRequest
from trend_scope.models.adapters.grid import analyze_grid
from trend_scope.models.extended_registry import scientific_registry
from trend_scope.models.serialization import dumps


def test_explicit_grid_slopes_and_coordinates():
    times=np.arange(4.)
    values=times[:,None,None]*np.array([[2.,-3.]])[None,:,:]+5
    source=ScientificDataset('grid',{'v':VariableData(values,('time','y','x'),'K')},
        {'x':Coordinate(np.array([1.,2.]),('x',),'m'),'y':Coordinate(np.array([0.]),('y',),'m')},
        Provenance('synthetic','simulation',True),TimeCoordinate(times,'day','2020-01-01','gregorian'),crs='local')
    result=analyze_grid(source,AnalysisRequest('a','sen','v'),scientific_registry())
    slopes=[cell['analysis'].payload['slope'] for cell in result.payload['cells']]
    assert slopes==[2.,-3.]
    assert result.payload['coordinates']==source.coordinates
    assert result.provenance==source.provenance
    dumps(result)
