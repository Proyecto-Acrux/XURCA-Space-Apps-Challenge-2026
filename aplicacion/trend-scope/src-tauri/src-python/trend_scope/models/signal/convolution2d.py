"""W19: 2D convolution / FIR on (y, x) grids with an explicit boundary rule."""
import numpy as np
from scipy.signal import convolve2d as _convolve2d

from ..numeric import array, finite, integer

VERSION = '1.0.0-candidate'
BOUNDARIES = ('reflect', 'constant_zero', 'valid_only')


def convolve2d(grid, kernel, *, boundary, max_cells: int = 5_000_000) -> dict:
    """True 2D convolution (kernel flipped), same shape as `grid`.

    `boundary` is mandatory: 'reflect' mirrors the grid at its edges,
    'constant_zero' pads with zeros, 'valid_only' also pads with zeros but the
    border cells are meaningless and reported invalid. `valid` marks the cells
    whose full kernel footprint lies inside the grid; values elsewhere depend
    on the boundary assumption. The kernel needs odd sides and is NOT
    normalized: a smoothing kernel should sum to 1 (a warning is issued
    otherwise). It smooths cell values only: no area weighting, no
    projection correction, no handling of missing cells (inputs must be
    finite). Cost O(cells * kernel cells), bounded by `max_cells`.
    Version 1.0.0-candidate.
    """
    if boundary not in BOUNDARIES:
        raise ValueError('boundary must be reflect, constant_zero or valid_only')
    g = array(grid, 'grid', ndim=2)
    k = array(kernel, 'kernel', ndim=2)
    if k.shape[0] % 2 == 0 or k.shape[1] % 2 == 0:
        raise ValueError('kernel sides must be odd')
    if g.size * k.size > integer(max_cells, 'max_cells'):
        raise ValueError('Convolution work budget exceeded')
    with np.errstate(over='raise', invalid='raise'):
        values = _convolve2d(g, k, mode='same', boundary='symm' if boundary == 'reflect' else 'fill', fillvalue=0.0)
    finite(values, 'convolution')
    valid = np.zeros(g.shape, dtype=bool)
    ry, rx = k.shape[0] // 2, k.shape[1] // 2
    if g.shape[0] > 2 * ry and g.shape[1] > 2 * rx:
        valid[ry:g.shape[0] - ry, rx:g.shape[1] - rx] = True
    if boundary == 'valid_only':
        values = np.where(valid, values, 0.0)
    warnings = ['Smooths cell values only: no area weighting or projection correction.']
    if abs(float(k.sum()) - 1.0) > 1e-9:
        warnings.append('The kernel does not sum to 1: the output is rescaled relative to the input.')
    return {'values': values, 'valid': valid, 'boundary': boundary, 'uncertainty': 'not_estimated',
            'warnings': warnings}
