"""W12: Canadian Fire Weather Index system (Van Wagner 1987; Van Wagner & Pickett 1985).

FWI is a relative METEOROLOGICAL fire-danger index. It does not predict
ignition, fire location or burned area. Equations follow Van Wagner (1987),
Forestry Technical Report 35. Day-length factors are the published
northern-hemisphere (about 46N) values; the southern hemisphere uses the same
factors shifted by six months. Latitudes within 30 degrees of the equator are
REJECTED: no tropical factors are implemented and none were invented.
No reference output tables were available to this implementation: it has not
been compared against published values.
"""
import math

import numpy as np

from ..numeric import array, finite, scalar

VERSION = '1.0.0-candidate'
DMC_DAY_LENGTH = (6.5, 7.5, 9.0, 12.8, 13.9, 13.9, 12.4, 10.9, 9.2, 8.0, 7.0, 6.0)
DC_DAY_LENGTH = (-1.6, -1.6, -1.6, 0.9, 3.8, 5.8, 6.4, 5.0, 2.4, 0.4, -1.6, -1.6)


def _factor(table, month: int, latitude: float) -> float:
    return table[(month - 1 + (6 if latitude < 0 else 0)) % 12]


def _ffmc(f0, t, h, w, rain):
    mo = 147.2 * (101 - f0) / (59.5 + f0)
    if rain > 0.5:
        rf = rain - 0.5
        mr = mo + 42.5 * rf * math.exp(-100 / (251 - mo)) * (1 - math.exp(-6.93 / rf))
        if mo > 150:
            mr += 0.0015 * (mo - 150) ** 2 * math.sqrt(rf)
        mo = min(mr, 250.0)
    ed = 0.942 * h ** 0.679 + 11 * math.exp((h - 100) / 10) + 0.18 * (21.1 - t) * (1 - math.exp(-0.115 * h))
    if mo > ed:
        ko = 0.424 * (1 - (h / 100) ** 1.7) + 0.0694 * math.sqrt(w) * (1 - (h / 100) ** 8)
        m = ed + (mo - ed) * 10 ** (-(ko * 0.581 * math.exp(0.0365 * t)))
    else:
        ew = 0.618 * h ** 0.753 + 10 * math.exp((h - 100) / 10) + 0.18 * (21.1 - t) * (1 - math.exp(-0.115 * h))
        if mo < ew:
            k1 = 0.424 * (1 - ((100 - h) / 100) ** 1.7) + 0.0694 * math.sqrt(w) * (1 - ((100 - h) / 100) ** 8)
            m = ew - (ew - mo) * 10 ** (-(k1 * 0.581 * math.exp(0.0365 * t)))
        else:
            m = mo
    return min(max(59.5 * (250 - m) / (147.2 + m), 0.0), 101.0)


def _dmc(p0, t, h, rain, day_length):
    t = max(t, -1.1)
    if rain > 1.5:
        rw = 0.92 * rain - 1.27
        wmi = 20 + 280 / math.exp(0.023 * p0)
        b = 100 / (0.5 + 0.3 * p0) if p0 <= 33 else 14 - 1.3 * math.log(p0) if p0 <= 65 else 6.2 * math.log(p0) - 17.2
        wmr = wmi + 1000 * rw / (48.77 + b * rw)
        pr = max(244.72 - 43.43 * math.log(wmr - 20), 0.0)
    else:
        pr = p0
    return pr + 1.894 * (t + 1.1) * (100 - h) * day_length * 0.0001


def _dc(d0, t, rain, day_length):
    t = max(t, -2.8)
    if rain > 2.8:
        rw = 0.83 * rain - 1.27
        smi = 800 * math.exp(-d0 / 400)
        dr = max(d0 - 400 * math.log(1 + 3.937 * rw / smi), 0.0)
    else:
        dr = d0
    return dr + 0.5 * max(0.36 * (t + 2.8) + day_length, 0.0)


def fire_weather_index(temperature, relative_humidity, wind_speed, precipitation, months, *, latitude,
                       initial_state) -> dict:
    """Daily FFMC, DMC, DC, ISI, BUI and FWI.

    Inputs are DAILY arrays (local-noon temperature in degC, relative humidity
    in %, wind speed in km/h, 24 h precipitation in mm) and the calendar month
    of each day; monthly data must not be passed (the caller is responsible).
    `initial_state` = {'ffmc','dmc','dc'} is mandatory (no start values are
    assumed) and `final_state` is returned to chain runs. Indicates relative
    meteorological danger; it does not predict ignition or its location.
    """
    t = array(temperature, 'temperature')
    h = array(relative_humidity, 'relative_humidity')
    w = array(wind_speed, 'wind_speed')
    rain = array(precipitation, 'precipitation')
    m = np.asarray(months)
    if not (t.shape == h.shape == w.shape == rain.shape == m.shape) or m.dtype.kind not in 'iu':
        raise ValueError('All inputs need the same length and months must be integers')
    if np.any((h < 0) | (h > 100)) or np.any(w < 0) or np.any(rain < 0) or np.any((m < 1) | (m > 12)):
        raise ValueError('Humidity must be 0-100, wind and precipitation nonnegative, months 1-12')
    if np.any(np.abs(t) > 70):
        raise ValueError('Temperature outside the plausible range (degC)')
    lat = scalar(latitude, 'latitude')
    if abs(lat) < 30 or abs(lat) > 90:
        raise ValueError('Day-length factors are implemented only for |latitude| between 30 and 90 degrees')
    if not isinstance(initial_state, dict) or set(initial_state) != {'ffmc', 'dmc', 'dc'}:
        raise ValueError('initial_state must have exactly ffmc, dmc and dc')
    f = scalar(initial_state['ffmc'], 'ffmc')
    p = scalar(initial_state['dmc'], 'dmc')
    d = scalar(initial_state['dc'], 'dc')
    if not 0 <= f <= 101 or p < 0 or d < 0:
        raise ValueError('initial_state out of range (ffmc 0-101, dmc >= 0, dc >= 0)')
    n = t.size
    out = {key: np.empty(n) for key in ('ffmc', 'dmc', 'dc', 'isi', 'bui', 'fwi')}
    for i in range(n):
        month = int(m[i])
        f = _ffmc(f, t[i], h[i], w[i], rain[i])
        p = _dmc(p, t[i], h[i], rain[i], _factor(DMC_DAY_LENGTH, month, lat))
        d = _dc(d, t[i], rain[i], _factor(DC_DAY_LENGTH, month, lat))
        fm = 147.2 * (101 - f) / (59.5 + f)
        isi = 0.208 * w[i] * 91.9 * math.exp(-0.1386 * fm) * (1 + fm ** 5.31 / 4.93e7)
        if p == 0 and d == 0:
            bui = 0.0
        elif p <= 0.4 * d:
            bui = 0.8 * p * d / (p + 0.4 * d)
        else:
            bui = p - (1 - 0.8 * d / (p + 0.4 * d)) * (0.92 + (0.0114 * p) ** 1.7)
        bui = max(bui, 0.0)
        fd = 0.626 * bui ** 0.809 + 2 if bui <= 80 else 1000 / (25 + 108.64 * math.exp(-0.023 * bui))
        b = 0.1 * isi * fd
        fwi = math.exp(2.72 * (0.434 * math.log(b)) ** 0.647) if b > 1 else b
        for key, value in zip(out, (f, p, d, isi, bui, fwi)):
            out[key][i] = value
    for key in out:
        finite(out[key], key)
    return {**out, 'final_state': {'ffmc': float(f), 'dmc': float(p), 'dc': float(d)},
            'uncertainty': 'not_estimated',
            'warnings': ['Relative meteorological danger only; not ignition, location or burned area.',
                         'Not validated against published reference tables in this implementation.']}
