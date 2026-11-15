"""Explicit per-cell temporal adapter; never silently aggregate geographic cells."""
from dataclasses import replace
from ..contracts import AnalysisResult
from ..execution import ExecutionContext, analyze
from ..numeric import integer
from ..validation import validate_dataset


def analyze_grid(data, request, registry, context=ExecutionContext(), *, max_cells: int = 100):
    """Apply one registered (time,) method per cell of (time,y,x), in row order.

    Keeps independent cell results, coordinates and source provenance. No spatial
    inference, area weighting, interpolation or invalid-cell omission is implicit.
    Bound output expansion explicitly; cancellation occurs before each cell.
    """
    validate_dataset(data)
    if request.variable not in data.variables:
        raise ValueError('Unknown selected grid variable')
    variable=data.variables[request.variable]
    if variable.dimensions!=('time','y','x'):
        raise ValueError('Per-cell adapter requires (time,y,x)')
    rows,columns=variable.values.shape[1:]
    if rows*columns>integer(max_cells,'max_cells'):
        raise ValueError('Per-cell result budget exceeded')
    if variable.invalid is not None and variable.invalid.any():
        raise ValueError('Explicitly resolve invalid cells before per-cell analysis')
    cells=[]
    for row in range(rows):
        for col in range(columns):
            context.checkpoint(f'cell:{row}:{col}')
            selected=replace(variable,values=variable.values[:,row,col],dimensions=('time',),invalid=None)
            local=replace(data,variables={request.variable:selected},coordinates={},crs=None,spatial_resolution={})
            local_request=replace(request,analysis_id=f'{request.analysis_id}:{row}:{col}')
            result=analyze(local,local_request,registry,context)
            cells.append({'row':row,'column':col,'analysis':result})
    return AnalysisResult(request.analysis_id,request.method_id,'1.0.0-candidate',data.dataset_id,
        request.variable,'completed','per_cell',dict(request.parameters),
        {'shape':(rows,columns),'cells':cells,'coordinates':data.coordinates,'crs':data.crs},
        {},('Independent per-cell results are not a regionally aggregated trend; multiple testing is not corrected.',),
        data.provenance,{'n_observations':len(data.time.values),'adapter':'explicit_per_cell'},data.transformations)
