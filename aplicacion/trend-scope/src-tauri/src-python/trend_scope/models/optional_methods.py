"""Explicit optional scientific dependencies, imported only when invoked."""
from importlib import import_module
import warnings
import numpy as np
from .numeric import array, finite, integer, scalar, temporal


def dependency(name):
    try:
        return import_module(name)
    except ModuleNotFoundError as error:
        if error.name == name.split('.')[0]:
            raise ImportError(f'Install the documented optional dependency for {name}') from error
        raise


def modified_mann_kendall(times, values, *, correction: str = 'hamed_rao', lag: int = 1, alpha: float = .05) -> dict:
    """Published variance corrections, explicitly selected, regular nonseasonal data."""
    _,y=temporal(times,values,regular=True,minimum=4)
    lag=integer(lag,'lag')
    alpha=scalar(alpha,'alpha',True)
    if lag>=len(y)-2 or alpha>=1 or len(y)>2000:
        raise ValueError('Invalid lag/alpha or pairwise work budget exceeded')
    functions={'hamed_rao':'hamed_rao_modification_test','yue_wang':'yue_wang_modification_test'}
    if correction not in functions:
        raise ValueError('Choose hamed_rao or yue_wang')
    if np.all(y==y[0]):
        return {'score':0,'variance':0.,'z':0.,'p_value':1.,'correction':correction,
                'warnings':['Constant series has no rank trend; independence correction is degenerate.']}
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always')
        result=getattr(dependency('pymannkendall'),functions[correction])(y,alpha=alpha,lag=lag)
    finite([result.s,result.var_s,result.z,result.p,result.slope])
    if result.var_s<=0:
        raise ValueError('Autocorrelation correction produced nonpositive variance')
    return {'score':float(result.s),'variance':float(result.var_s),'z':float(result.z),'p_value':float(result.p),
            'correction':correction,'lag':lag,'alpha':alpha,
            'warnings':[str(w.message) for w in caught]+['Finite-sample variance correction is model-dependent; not a universal cure for dependence or seasonality.']}


def dtw_kmeans(series, *, clusters: int, seed: int = 2026, max_iter: int = 20) -> dict:
    """Collection shape (series,time,feature); DTW barycenter averaging, no scaling."""
    x=array(series,'series',ndim=3)
    k=integer(clusters,'clusters'); seed=integer(seed,'seed',0); iterations=integer(max_iter,'max_iter')
    if not 1<=k<=len(x) or x.shape[1]<2 or x.shape[2]<1:
        raise ValueError('Invalid collection dimensions or cluster count')
    if iterations>100 or len(x)*k*x.shape[1]**2*iterations>2_000_000:
        raise ValueError('DTW clustering work budget exceeded')
    model=dependency('tslearn.clustering').TimeSeriesKMeans(n_clusters=k,metric='dtw',random_state=seed,
        n_init=1,max_iter=iterations,max_iter_barycenter=20,n_jobs=1)
    labels=model.fit_predict(x)
    centers=finite(model.cluster_centers_)
    if len(np.unique(labels))!=k:
        raise RuntimeError('DTW clustering could not form all requested clusters')
    return {'labels':labels,'centers':centers,'inertia':float(finite(model.inertia_)),
            'iterations':int(model.n_iter_),'seed':seed,
            'warnings':['Local optimum with iterative DTW barycenters; shared feature units and explicit normalization are required.',
                        'Iteration limits do not certify convergence of every barycenter.']}


def stl(times, values, *, period: int, seasonal: int = 7, robust: bool = True) -> dict:
    t, y = temporal(times, values, regular=True)
    p, s = integer(period,'period',2), integer(seasonal,'seasonal',3)
    if s%2 == 0 or len(y) < 2*p or type(robust) is not bool:
        raise ValueError('STL needs >=2 cycles, odd seasonal span and boolean robust')
    model = dependency('statsmodels.tsa.seasonal').STL(y,period=p,seasonal=s,robust=robust).fit()
    return {'times':t.copy(),'trend':finite(model.trend),'seasonal':finite(model.seasonal),
            'residuals':finite(model.resid),'causal':False,
            'warnings':['STL uses future samples in the supplied interval; split before fitting for prediction.']}


def wavelet(times, values, *, wavelet: str = 'db2', level: int = 1) -> dict:
    _, y = temporal(times, values, regular=True)
    pywt = dependency('pywt')
    w = pywt.Wavelet(wavelet)
    level = integer(level,'level')
    if level > pywt.dwt_max_level(len(y),w.dec_len):
        raise ValueError('Wavelet level exceeds useful decomposition depth')
    coefficients = pywt.wavedec(y,w,mode='symmetric',level=level)
    for c in coefficients:
        finite(c)
    reconstruction = finite(pywt.waverec(coefficients,w,mode='symmetric')[:len(y)])
    return {'coefficients':coefficients,'ordering':'approximation_L, detail_L,...,detail_1',
            'wavelet':wavelet,'level':level,'boundary':'symmetric','reconstruction':reconstruction,
            'warnings':['Boundary coefficients depend on symmetric extension; this is a discrete transform, not a forecast.']}


def pelt(times, values, *, penalty: float, min_size: int = 2) -> dict:
    t,y = temporal(times,values,regular=True)
    penalty = scalar(penalty,'penalty',True)
    size = integer(min_size,'min_size')
    if len(y) < size:
        raise ValueError('Series shorter than minimum segment')
    if np.max(abs(y)) > np.sqrt(np.finfo(float).max/len(y))/2:
        raise ValueError('Squared-error cost may overflow; rescale values and penalty explicitly')
    # Ruptures l2 cost is segment sum of squared centered deviations.
    points = dependency('ruptures').Pelt(model='l2',min_size=size,jump=1).fit(y.reshape(-1,1)).predict(pen=penalty)
    indices = np.array(points[:-1],dtype=int)
    return {'change_indices':indices,'change_times':t[indices], 'segment_ends':np.array(points),
            'penalty':penalty,'cost':'sum of within-segment squared deviations',
            'warnings':['Penalty has squared-value units; detections require calibration and may reflect sensor changes.']}


def adwin(times, values, *, delta: float = .002) -> dict:
    t,y = temporal(times,values)
    delta = scalar(delta,'delta',True)
    if delta >= 1 or np.any((y<0)|(y>1)):
        raise ValueError('ADWIN requires 0<delta<1 and explicitly normalized values in [0,1]')
    detector = dependency('river.drift').ADWIN(delta=delta)
    events=[]
    for i,v in enumerate(y):
        detector.update(float(v))
        if detector.drift_detected:
            events.append(i)
    indices=np.asarray(events,dtype=int)
    return {'change_indices':indices,'change_times':t[indices], 'final_window_width':int(detector.width),
            'warnings':['Detection times lag change onset; probabilistic guarantees assume bounded data and appropriate independence.']}


def isolation_forest(features, *, contamination='auto', seed: int = 2026, n_estimators: int = 100) -> dict:
    x = array(features,'features',ndim=2)
    if x.shape[0] < 2 or x.shape[1] < 1:
        raise ValueError('Isolation Forest needs at least two observations and one feature')
    seed=integer(seed,'seed',0)
    n_estimators=integer(n_estimators,'n_estimators')
    if n_estimators > 1000:
        raise ValueError('Tree budget exceeded')
    if contamination != 'auto':
        contamination=scalar(contamination,'contamination',True)
        if contamination > .5:
            raise ValueError('contamination must not exceed 0.5')
    model=dependency('sklearn.ensemble').IsolationForest(n_estimators=n_estimators,contamination=contamination,random_state=seed,n_jobs=1)
    labels=model.fit_predict(x)
    return {'labels':labels,'decision_scores':finite(model.decision_function(x)),
            'anomaly_indices':np.flatnonzero(labels==-1),'seed':seed,
            'warnings':['Exploratory in-sample anomalies, not operational alerts or independently validated predictions.']}


def _predict(y, horizon, method, period, order, seasonal_order):
    if method == 'naive':
        return np.full(horizon,y[-1]), []
    if method == 'seasonal_naive':
        p=integer(period,'period',2)
        if len(y)<p:
            raise ValueError('Seasonal baseline needs one complete cycle')
        return np.resize(y[-p:],horizon), []
    with warnings.catch_warnings(record=True) as captured:
        warnings.simplefilter('always')
        if method == 'holt_winters':
            p=integer(period,'period',2)
            if len(y)<2*p:
                raise ValueError('Holt-Winters needs at least two training cycles')
            fit=dependency('statsmodels.tsa.holtwinters').ExponentialSmoothing(y,trend='add',seasonal='add',seasonal_periods=p,initialization_method='estimated').fit(optimized=True)
        elif method in ('arima','sarima'):
            if len(order)!=3 or len(seasonal_order)!=4:
                raise ValueError('Expected ARIMA (p,d,q), seasonal (P,D,Q,s)')
            order=tuple(integer(v,'order',0) for v in order)
            season=tuple(integer(v,'seasonal_order',0) for v in seasonal_order)
            if method == 'arima' and season != (0,0,0,0):
                raise ValueError('Use sarima for seasonal orders')
            if max(order)>5 or max(season[:3])>2 or season[3]>366:
                raise ValueError('Model order exceeds supported resource limits')
            if any(season[:3]) and season[3]<2:
                raise ValueError('Seasonal dynamics need period >=2')
            effective=len(y)-order[1]-season[1]*season[3]
            if effective <= sum(order[::2])+sum(season[:3:2])+1 or (season[3] and len(y)<2*season[3]):
                raise ValueError('Insufficient training data for selected model order')
            fit=dependency('statsmodels.tsa.statespace.sarimax').SARIMAX(y,order=order,seasonal_order=season,trend='n',enforce_stationarity=True,enforce_invertibility=True).fit(disp=False,maxiter=200)
        else:
            raise ValueError('Unknown forecast method')
        info=getattr(fit,'mle_retvals',None)
        if info is not None and not info.get('converged',info.get('success',True)):
            raise RuntimeError('Forecast optimizer did not converge')
        predicted=finite(np.asarray(fit.forecast(horizon)))
    return predicted, [str(w.message) for w in captured]


def forecast(times, values, *, horizon: int, method: str = 'naive', period=None,
             order=(1,0,0), seasonal_order=(0,0,0,0), validation_size=None) -> dict:
    """Chronological holdout vs naive, then refit; no calibrated uncertainty claim."""
    t,y=temporal(times,values,regular=True,minimum=4)
    h=integer(horizon,'horizon')
    v=h if validation_size is None else integer(validation_size,'validation_size')
    if h>10000 or v>=len(y)-1:
        raise ValueError('Forecast budget or training length is insufficient')
    holdout, notes=_predict(y[:-v],v,method,period,order,seasonal_order)
    predicted, notes2=_predict(y,h,method,period,order,seasonal_order)
    error=finite(y[-v:]-holdout)
    baseline=finite(y[-v:]-y[-v-1])
    def metrics(e):
        scale=max(float(abs(e).max()),1.)
        return {'mae':float(finite(scale*np.mean(abs(e)/scale))), 'rmse':float(finite(scale*np.sqrt(np.mean((e/scale)**2))))}
    future=finite(t[-1]+(t[1]-t[0])*np.arange(1,h+1))
    if np.any(np.diff(np.r_[t[-1],future])<=0):
        raise ValueError('Future times are not representable; rebase time')
    return {'times':future,'values':predicted,'method':method,
            'validation':{'design':'single chronological holdout','training_size':len(y)-v,
                'times':t[-v:].copy(),'predicted':holdout,'metrics':metrics(error),
                'naive_metrics':metrics(baseline),'absolute_error_by_horizon':abs(error)},
            'uncertainty':'not_estimated',
            'warnings':notes+notes2+['One holdout is not proof of future reliability; inspect errors by horizon and use rolling backtests before operational use.']}
