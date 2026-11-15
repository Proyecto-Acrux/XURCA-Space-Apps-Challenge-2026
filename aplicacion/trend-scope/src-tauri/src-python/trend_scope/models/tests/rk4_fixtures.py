"""Synthetic RHS fixtures, not registered physical products."""
import numpy as np
from numba import njit


@njit(cache=True)
def decay(t,y):
    return -y


@njit(cache=True)
def growth(t,y):
    return y


@njit(cache=True)
def zero(t,y):
    return np.zeros_like(y)


@njit(cache=True)
def cubic_time(t,y):
    return np.full_like(y,t**3)


@njit(cache=True)
def oscillator(t,y):
    return np.array([y[1],-y[0]])


@njit(cache=True)
def coupled(t,y):
    return np.array([-y[0]+y[1],-2*y[1]])


@njit(cache=True)
def bad_shape(t,y):
    return np.ones(y.size+1)


@njit(cache=True)
def nonfinite(t,y):
    return np.full_like(y,np.nan if t>=.5 else 1.)


@njit(cache=True)
def huge_constant(t,y):
    return np.full_like(y,1e308)


@njit(cache=True)
def tiny_constant(t,y):
    return np.full_like(y,5e-324)


@njit(cache=True)
def mutates_input(t,y):
    for i in range(y.size):
        y.flat[i]=999.
    return np.zeros_like(y)


@njit(cache=True)
def parameter_decay(t,y,parameters):
    return -parameters[0]*y
