"""W16: hypsometric equation (educational; not a trend method)."""
import numpy as np

from ..numeric import array, finite, scalar

VERSION = '1.0.0-candidate'
GRAVITY = 9.80665          # m s^-2
DRY_AIR_CONSTANT = 287.05  # J kg^-1 K^-1


def pressure_at_height(reference_pressure, reference_height, height, mean_temperature) -> dict:
    """Pressure at `height` from a reference level, p = p0 * exp(-g (h - h0) / (Rd * Tm)).

    Heights in metres, `mean_temperature` in KELVIN (mean of the layer between
    both levels, 150-350 K), pressure in any unit (the result keeps it).
    Assumptions: dry air, hydrostatic balance and a constant layer-mean
    temperature. Educational use: it is not a trend or a measurement.
    """
    p0 = scalar(reference_pressure, 'reference_pressure', True)
    h0 = scalar(reference_height, 'reference_height')
    h = array(height, 'height') if np.ndim(height) else np.array([scalar(height, 'height')])
    tm = scalar(mean_temperature, 'mean_temperature', True)
    if not 150 <= tm <= 350:
        raise ValueError('mean_temperature must be in kelvin, between 150 and 350')
    with np.errstate(over='raise', under='ignore'):
        pressure = p0 * np.exp(-GRAVITY * (h - h0) / (DRY_AIR_CONSTANT * tm))
    finite(pressure, 'pressure')
    return {'pressure': pressure, 'uncertainty': 'not_estimated',
            'assumptions': ['dry air', 'hydrostatic balance', 'constant layer-mean temperature'],
            'warnings': ['Educational formula; real profiles depart from a constant mean temperature and humidity.']}
