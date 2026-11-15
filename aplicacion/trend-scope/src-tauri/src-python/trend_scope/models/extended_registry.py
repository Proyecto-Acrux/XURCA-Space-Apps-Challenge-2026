"""Additive registry: protected default registry and existing adapters stay untouched."""
from functools import partial
from importlib.util import find_spec
import numpy as np
from .contracts import AnalysisResult
from .registry import MethodSpec, default_registry
from .numeric import temporal

VERSION='1.0.0-candidate'


def _run(method, function, output_kind, data, request):
    variable=data.variables[request.variable]
    if data.time is None or variable.invalid is not None and variable.invalid.any():
        raise ValueError('Explicit time coordinates and unmasked observations are required')
    parameters=dict(request.parameters)
    t=data.time.values
    if method=='multivariable':
        feature_name=parameters.pop('features',None)
        if feature_name not in data.variables:
            raise ValueError('Specify a feature variable ID')
        features=data.variables[feature_name]
        if features.dimensions!=('time','feature') or features.invalid is not None and features.invalid.any():
            raise ValueError('Features must be an unmasked (time,feature) variable')
        temporal(t,variable.values)
        payload=function(features.values,variable.values,**parameters)
        units={'coefficients': tuple(f'({variable.unit})/({u})' for u in features.feature_units),
               'intercept':variable.unit,'rmse':variable.unit,'mae':variable.unit,'r2':'1'}
    elif method=='dtw':
        second=parameters.pop('second_variable',None)
        if second not in data.variables:
            raise ValueError('Specify second_variable ID')
        other=data.variables[second]
        if other.dimensions!=('time',) or other.unit!=variable.unit or other.invalid is not None and other.invalid.any():
            raise ValueError('DTW requires another unmasked time series with matching physical units')
        temporal(t,variable.values)
        payload=function(variable.values,other.values,**parameters)
        units={'distance':variable.unit}
    elif method=='isolation_forest':
        if np.any(np.diff(t)<=0):
            raise ValueError('Times must strictly increase')
        payload=function(variable.values,**parameters)
        units={'decision_scores':'1'}
    else:
        temporal(t,variable.values)
        if method=='adwin' and variable.unit!='1':
            raise ValueError('ADWIN requires explicit normalization with dimensionless unit 1')
        payload=function(t,variable.values,**parameters)
        units={'times':data.time.unit,'values':variable.unit}
        if method=='sen':
            units={'slope':f'({variable.unit})/({data.time.unit})','intercept_at_reference':variable.unit,'time_reference':data.time.unit}
        elif method in ('mann_kendall','seasonal_mann_kendall','modified_mann_kendall'):
            units={'score':'1','variance':'1','z':'1','p_value':'1','tau_a':'1'}
        elif method=='fft':
            units={'frequencies':f'1/({data.time.unit})','amplitude':variable.unit,'phase':'rad'}
        elif method=='matrix_profile':
            units={'profile':'1'}
        elif method=='cusum':
            units={'upper':variable.unit,'lower':variable.unit}
        elif method in ('pelt','adwin'):
            units={'change_times':data.time.unit}
    # AnalysisResult metric_units maps strings; feature units remain in payload metadata.
    feature_units=units.pop('coefficients',None)
    if feature_units is not None:
        payload['coefficient_units']=feature_units
    return AnalysisResult(request.analysis_id,method,VERSION,data.dataset_id,request.variable,
        'completed',output_kind,dict(request.parameters),payload,units,
        tuple(payload.get('warnings',())),data.provenance,
        {'n_observations':len(t),'time_start':t[0],'time_end':t[-1],
         'time_origin':data.time.origin,'time_unit':data.time.unit,'calendar':data.time.calendar,
         'value_unit':variable.unit,'quality':data.quality},data.transformations)


def _cusum_time(t,y,**kwargs):
    from .change_detection.cusum import cusum
    output=cusum(y,**kwargs)
    output['event_times']=t[output['event_indices']]
    return output


def _seasonal_mk(t,y,*,seasons,**kwargs):
    from .stats.trends import mann_kendall
    return mann_kendall(t,y,seasons=seasons,**kwargs)


def scientific_registry(*, include_optional: bool = True):
    """Register implemented methods only. Optional methods require installed packages."""
    from .stats.trends import sen_slope,mann_kendall,multivariable_ols
    from .signal.processing import moving_average,fir_filter,iir_filter,fft_spectrum,ssa
    from .data_reduction.reduction import paa,lttb
    from .similarity.dtw import dtw
    from .similarity.matrix_profile import matrix_profile
    from .stats import regression
    registry=default_registry()
    def add(identifier,fn,category,kind,params,complexity,regularity='strictly increasing; no missing values',deps=('numpy',),dims=(('time',),)):
        registry.register(MethodSpec(identifier,identifier.replace('_',' ').title(),VERSION,category,kind,dims,
            2,'At least two observations; method-specific dimension/order requirements checked at execution',
            regularity,tuple(params),tuple(deps),complexity,'NumPy/native library or serial Numba; no new performance claim'),
            partial(_run,identifier,fn,kind))
    add('sen',sen_slope,'stats','estimate',('max_pairs',),'O(n^2) time/memory')
    for name,fn,parameters in (
        ('ridge',regression.ridge_regression,('degree','alpha')),
        ('exponential',regression.exponential_regression,()),
        ('logarithmic',regression.logarithmic_regression,()),
        ('power',regression.power_regression,()),
        ('harmonic',regression.harmonic_regression,('period','harmonics','trend_degree')),
    ):
        add(name,fn,'stats','fit',parameters,'O(n*p^2) for design fits; O(n) transformed linear fits',deps=('numpy','numba','scipy'))
    add('mann_kendall',mann_kendall,'stats','test',('max_pairs',),'O(n^2) time, O(n) memory',deps=('numpy','numba'))
    add('seasonal_mann_kendall',_seasonal_mk,'stats','test',('seasons','max_pairs'),'O(n^2) time, O(n) memory',deps=('numpy','numba'))
    add('multivariable',multivariable_ols,'stats','fit',('features',),'O(n*p^2) time; O(n*p) memory')
    add('cusum',_cusum_time,'change_detection','events',('baseline','allowance','threshold'),'O(n) time/memory',deps=('numpy','numba'))
    regular='regular temporal grid; no missing values'
    add('moving_average',moving_average,'signal','smooth',('window',),'O(n*window)',regular)
    add('fir',fir_filter,'signal','filter',('coefficients','numtaps','cutoff'),'O(n*taps)',regular,('numpy','scipy'))
    add('iir',iir_filter,'signal','filter',('sos','zero_phase'),'O(n*sections)',regular,('numpy','scipy'))
    add('fft',fft_spectrum,'signal','spectrum',('detrend',),'O(n log n)',regular)
    add('ssa',ssa,'signal','decomposition',('window','components','max_elements'),'O(min(L,K)^2*max(L,K))',regular)
    add('paa',paa,'data_reduction','reduction',('segments',),'O(n+segments)',regular)
    add('lttb',lttb,'data_reduction','visualization',('samples',),'O(n)')
    add('dtw',dtw,'similarity','distance',('second_variable','radius','max_cells'),'O(n*m) time, O(m) memory',deps=('numpy','numba'))
    add('matrix_profile',matrix_profile,'similarity','profile',('window','exclusion','max_pairs'),'O(n_windows^2*window)',regular)
    from .optional_methods import forecast
    add('naive_forecast',partial(forecast,method='naive'),'stats','forecast',('horizon','validation_size'),'O(n+h)',regular)
    add('seasonal_naive_forecast',partial(forecast,method='seasonal_naive'),'stats','forecast',('horizon','validation_size','period'),'O(n+h)',regular)
    if include_optional:
        from . import optional_methods as library
        if find_spec('statsmodels') is not None:
            for method in ('arima','sarima','holt_winters'):
                add(method,partial(library.forecast,method=method),'stats','forecast',
                    ('horizon','period','order','seasonal_order','validation_size'),
                    'model/order and optimizer dependent',regular,('numpy','statsmodels'))
        for identifier,fn,category,kind,params,package,complexity in (
            ('stl',library.stl,'signal','decomposition',('period','seasonal','robust'),'statsmodels','LOESS iterations and window dependent'),
            ('wavelet',library.wavelet,'signal','decomposition',('wavelet','level'),'pywt','O(n) for fixed wavelet filter'),
            ('pelt',library.pelt,'change_detection','events',('penalty','min_size'),'ruptures','O(n^2) worst case with pruning'),
            ('adwin',library.adwin,'change_detection','events',('delta',),'river','adaptive bucket/window dependent'),
            ('modified_mann_kendall',library.modified_mann_kendall,'stats','test',('correction','lag','alpha'),'pymannkendall','O(n^2) time/memory'),
            ('forecast',library.forecast,'stats','forecast',('horizon','method','period','order','seasonal_order','validation_size'),'statsmodels','model/order and optimizer dependent'),
            ('isolation_forest',library.isolation_forest,'advanced','anomalies',('contamination','seed','n_estimators'),'sklearn','O(trees*samples*log(samples))'),
        ):
            if find_spec(package) is not None:
                dims=(('time','feature'),) if identifier=='isolation_forest' else (('time',),)
                add(identifier,fn,category,kind,params,complexity,regular,('numpy',package),dims)
    return registry
