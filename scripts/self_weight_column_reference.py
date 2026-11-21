"""Continuous self-weight column: EI theta'' + mu*g*(L-s)*theta = 0.

Root theta(0)=0 and free-tip theta'(L)=0 give an Airy-function determinant.
This is static divergence of a clamped/free uniform line-mass column,
independent of its time-dependent inertia formulation.
"""
import numpy as np
from scipy.integrate import quad
from scipy.optimize import brentq
from scipy.special import airy


def root():
    a0, ap0, b0, bp0 = airy(0.)
    def determinant(a):
        ai, _, bi, _ = airy(-a)
        return ai*bp0-bi*ap0
    return brentq(determinant, 1., 3., xtol=1e-14)


def critical(*, ei=100., mass_per_length=1., length=1.):
    return root()**3*ei/(mass_per_length*length**3)


def shapes(stations, *, length=1.):
    """Normalize the critical displacement to one at the free tip."""
    c = root()/length
    _, ap0, _, bp0 = airy(0.)
    def angle(s):
        ai, _, bi, _ = airy(-c*(length-s))
        return ai*bp0-bi*ap0
    scale = quad(angle, 0., length, epsabs=1e-13, epsrel=1e-13)[0]
    positions = np.asarray(stations, dtype=float)
    w = np.array([quad(angle, 0., float(s), epsabs=1e-13, epsrel=1e-13)[0]/scale for s in positions])
    return w, np.array([angle(s)/scale for s in positions])
