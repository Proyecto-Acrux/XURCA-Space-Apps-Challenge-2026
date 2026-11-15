"""Regular-grid signal methods. All boundary policies are explicit."""
import numpy as np
from scipy import signal
from ..numeric import array, finite, integer, scalar, temporal


def moving_average(times, values, *, window: int) -> dict:
    """Trailing mean of complete windows, aligned to their last sample (causal)."""
    t, y = temporal(times, values, regular=True)
    w = integer(window, 'window')
    if w > len(y):
        raise ValueError('window exceeds observations')
    filtered = finite(np.convolve(y, np.ones(w)/w, mode='valid'))
    return {'times': t[w-1:].copy(), 'values': filtered, 'causal': True,
            'edge_policy': 'omit incomplete initial windows', 'window': w}


def fir_filter(times, values, *, coefficients=None, numtaps=None, cutoff=None) -> dict:
    """Causal FIR with zero initial history; explicit coefficients or lowpass design."""
    t, y = temporal(times, values, regular=True)
    fs = scalar(1/(t[1]-t[0]), 'sampling frequency', True)
    if coefficients is None:
        taps = integer(numtaps, 'numtaps', 2)
        cut = scalar(cutoff, 'cutoff', True)
        if cut >= fs/2:
            raise ValueError('cutoff must be below Nyquist')
        b = signal.firwin(taps, cut, fs=fs)
    else:
        if numtaps is not None or cutoff is not None:
            raise ValueError('Choose coefficients or filter design, not both')
        b = array(coefficients, 'coefficients')
    frequency, response = signal.freqz(b, fs=fs)
    return {'times': t.copy(), 'values': finite(signal.lfilter(b, [1.], y)),
            'coefficients': b, 'causal': True, 'sampling_frequency': float(fs),
            'response_frequencies': frequency, 'response_magnitude': finite(abs(response)),
            'edge_policy': 'zero history; initial len(coefficients)-1 samples are transient'}


def iir_filter(times, values, *, sos, zero_phase: bool = False) -> dict:
    """Stable second-order sections, causal zero history or noncausal odd padding."""
    t, y = temporal(times, values, regular=True)
    sections = array(sos, 'sos', ndim=2)
    if sections.shape[1] != 6 or np.any(sections[:,3] != 1):
        raise ValueError('sos must have shape (sections,6) and a0=1')
    if type(zero_phase) is not bool:
        raise ValueError('zero_phase must be boolean')
    for row in sections:
        if np.any(abs(np.roots(row[3:])) >= 1):
            raise ValueError('IIR poles must lie strictly inside unit circle')
    result = signal.sosfiltfilt(sections, y) if zero_phase else signal.sosfilt(sections, y)
    return {'times': t.copy(), 'values': finite(result), 'sos': sections.copy(),
            'causal': not zero_phase,
            'edge_policy': 'odd padding; noncausal and uses future data' if zero_phase else 'zero initial history',
            'warnings': ['Do not filter a full dataset noncausally before temporal train/test splitting.'] if zero_phase else []}


def fft_spectrum(times, values, *, detrend: bool = True) -> dict:
    """One-sided amplitude spectrum, rectangular window, no implicit resampling."""
    t, y = temporal(times, values, regular=True)
    if type(detrend) is not bool:
        raise ValueError('detrend must be boolean (mean removal only)')
    centered = y-y.mean() if detrend else y
    spectrum = np.fft.rfft(centered)
    amplitude = abs(spectrum)/len(y)
    amplitude[1:-1 if len(y)%2 == 0 else None] *= 2
    return {'frequencies': finite(np.fft.rfftfreq(len(y), d=t[1]-t[0])),
            'amplitude': finite(amplitude), 'phase': np.angle(spectrum),
            'mean_removed': detrend, 'window': 'rectangular',
            'warnings': ['Spectral leakage and aliasing require domain review; frequencies use inverse time units.']}


def ssa(times, values, *, window: int, components, max_elements: int = 2_000_000) -> dict:
    """Basic SSA: Hankel embedding, SVD, selected eigentriples, diagonal averaging."""
    t, y = temporal(times, values, regular=True, minimum=3)
    w = integer(window, 'window', 2)
    if w >= len(y):
        raise ValueError('SSA window must be shorter than the series')
    k = len(y)-w+1
    if w*k > integer(max_elements, 'max_elements'):
        raise ValueError('SSA trajectory matrix budget exceeded')
    selected = tuple(integer(v, 'component index', 0) for v in components)
    if not selected or len(set(selected)) != len(selected) or max(selected) >= min(w,k):
        raise ValueError('Select distinct zero-based SVD component indices')
    trajectory = np.lib.stride_tricks.sliding_window_view(y, w).T.copy()
    u, singular, vt = np.linalg.svd(trajectory, full_matrices=False)
    finite(singular)
    indices = list(selected)
    reconstructed = (u[:,indices]*singular[indices]) @ vt[indices,:]
    total, count = np.zeros(len(y)), np.zeros(len(y))
    for i in range(w):
        total[i:i+k] += reconstructed[i]
        count[i:i+k] += 1
    fitted = finite(total/count)
    return {'times': t.copy(), 'values': fitted, 'residuals': finite(y-fitted),
            'singular_values': singular, 'components': selected, 'causal': False,
            'warnings': ['SSA reconstruction uses the full supplied series; component selection is explicit, not a forecast.']}
