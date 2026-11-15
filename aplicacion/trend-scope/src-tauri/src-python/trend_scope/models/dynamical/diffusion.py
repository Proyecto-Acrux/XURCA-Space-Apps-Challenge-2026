"""Defined PDE only: 1D constant-diffusivity heat equation, fixed Dirichlet ends."""
import numpy as np
from numba import njit
from ..numeric import array, finite, integer, scalar, temporal


@njit(cache=True)
def _ftcs(y,x,t,alpha):
    result=np.empty((len(t),len(x)))
    result[0]=y
    dx=x[1]-x[0]
    for i in range(len(t)-1):
        r=alpha*(t[i+1]-t[i])/dx**2
        result[i+1,0]=y[0]
        result[i+1,-1]=y[-1]
        for j in range(1,len(x)-1):
            result[i+1,j]=(1-2*r)*result[i,j]+r*result[i,j-1]+r*result[i,j+1]
    return result


def diffusion_1d(initial, positions, times, *, diffusivity: float, max_cells: int = 1_000_000) -> dict:
    """u_t=alpha*u_xx, FTCS O(dt+dx^2), alpha*dt/dx^2 <= 1/2.

    Boundary values equal the two supplied initial endpoints for all times.
    Positions must be equally spaced in a declared physical length unit; alpha
    must use that length squared per time unit. No sources or other BC types.
    """
    x,y=temporal(positions,initial,regular=True,minimum=3)
    t=array(times,'times',minimum=2)
    temporal(t,np.zeros(len(t)))
    alpha=scalar(diffusivity,'diffusivity',True)
    if len(t)*len(x)>integer(max_cells,'max_cells'):
        raise ValueError('Diffusion output cell budget exceeded')
    with np.errstate(over='raise',invalid='raise',divide='raise',under='raise'):
        ratios=alpha*np.diff(t)/(x[1]-x[0])**2
    if np.any(ratios>.5):
        raise ValueError('FTCS diffusion stability requires alpha*dt/dx^2 <= 0.5')
    values=finite(_ftcs(y,x,t,alpha))
    return {'times':t.copy(),'positions':x.copy(),'values':values,'diffusivity':alpha,
            'boundary':'fixed Dirichlet at initial endpoints','max_diffusion_number':float(ratios.max()),
            'output_kind':'simulation','uncertainty':'not_estimated',
            'warnings':['One-dimensional constant-coefficient simulation; spatial/temporal convergence must be checked for each physical problem.']}
