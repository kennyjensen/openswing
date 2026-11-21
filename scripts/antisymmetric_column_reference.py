"""Clamped/pinned half-column with unit endpoint rotation and zero translation.

Reflection gives the antisymmetric fixed-fixed full-column subspace. The beam
is massless with endpoint bending inertia J; lambda^2=-k_theta/J. These closed
forms follow from w'=theta, EI theta'=M, M'=-P theta-F, F'=0. No OpenSwing
operator supplies this reference. `count` selects endpoint-average integration;
None selects the continuous boundary-value problem.
"""
import math

import numpy as np
from scipy.optimize import brentq

L = 1.
INERTIA = 1.


def critical(ei=100., count=None):
    if count is not None and count < 2:
        raise ValueError('At least two intervals are required.')
    phase = lambda a: a if count is None else 2*count*math.atan(a/(2*count))
    high = 1.5*math.pi if count is None else 2*count*math.tan(.75*math.pi/count)
    root = brentq(lambda a: math.sin(phase(a))-a*math.cos(phase(a)),
                  math.pi, high, xtol=1e-14)
    return ei*(root/L)**2


def stiffness(load, ei, count=None):
    if load == 0:
        t = 0. if count is None else 1/count**2
        return ei/L*(4-t)/(1-t)
    q = math.sqrt(load/ei)
    a = q*L
    b = a if count is None else 2*count*math.atan(a/(2*count))
    return ei*q*(math.sin(b)-a*math.cos(b))/(2*(1-math.cos(b))-a*math.sin(b))


def shapes(load, ei, count):
    """Discrete w and theta at all nodes, with w(L)=0 and theta(L)=1."""
    s = np.linspace(0., L, count+1)
    h = L/count
    if load == 0:
        w = (s**3-(L+h*h/(2*L))*s*s+h*h*s/2)/(L*L-h*h)
        theta = (3*s*s-(2*L+h*h/L)*s)/(L*L-h*h)
    else:
        q = math.sqrt(load/ei)
        phase = 2*math.atan(q*h/2)*np.arange(count+1)
        b = phase[-1]
        aa, bb = np.linalg.solve([[1-math.cos(b), math.sin(b)-q*L],
            [q*math.sin(b), q*(math.cos(b)-1)]], [0., 1.])
        w = aa*(1-np.cos(phase))+bb*(np.sin(phase)-q*s)
        theta = q*(aa*np.sin(phase)+bb*(np.cos(phase)-1))
    return w, theta
