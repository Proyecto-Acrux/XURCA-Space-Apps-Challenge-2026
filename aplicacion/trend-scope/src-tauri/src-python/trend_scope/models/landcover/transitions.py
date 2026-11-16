"""W15: land-cover transition matrix (counts and, optionally, areas)."""
import numpy as np

from ..numeric import array, finite

VERSION = '1.0.0-candidate'


def transition_matrix(before, after, *, classes, cell_area=None) -> dict:
    """Cross-tabulate class labels of two dates: rows = before, columns = after.

    `classes` lists every allowed integer label (unique); a label outside it is
    an error, never silently dropped. With `cell_area` (same shape, positive)
    the matrix of areas is also returned and the total area is conserved.
    Labels are compared cell by cell: the grids must be co-registered.
    """
    first, second = np.asarray(before), np.asarray(after)
    if first.shape != second.shape or first.size == 0:
        raise ValueError('before and after must be nonempty and have the same shape')
    if first.dtype.kind not in 'iu' or second.dtype.kind not in 'iu':
        raise ValueError('class labels must be integers')
    labels = np.asarray(classes)
    if labels.ndim != 1 or labels.size < 2 or labels.dtype.kind not in 'iu' or len(np.unique(labels)) != labels.size:
        raise ValueError('classes must be a 1D array of at least two unique integers')
    order = np.argsort(labels)
    ordered = labels[order]

    def index(values):
        position = np.searchsorted(ordered, values)
        position = np.minimum(position, ordered.size - 1)
        if not np.all(ordered[position] == values):
            raise ValueError('A cell has a class label that is not in classes')
        return order[position]

    i, j = index(first.ravel()), index(second.ravel())
    k = labels.size
    flat = i * k + j
    counts = np.bincount(flat, minlength=k * k).reshape(k, k)
    output = {'classes': labels, 'counts': counts, 'total_cells': int(first.size),
              'uncertainty': 'not_estimated',
              'warnings': ['Transitions are cell-by-cell: classification errors appear as spurious change.']}
    if cell_area is not None:
        area = array(cell_area, 'cell_area', ndim=first.ndim if first.ndim else 1, minimum=1)
        if area.shape != first.shape or np.any(area <= 0):
            raise ValueError('cell_area must be positive and have the same shape as the grids')
        areas = np.bincount(flat, weights=area.ravel(), minlength=k * k).reshape(k, k)
        finite(areas)
        output.update({'areas': areas, 'total_area': float(area.sum())})
    return output
