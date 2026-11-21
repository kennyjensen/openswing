"""Independent nodal interpolation and virtual-work load transfer.

This module has no production imports. It connects continuum node motions to a
declared discrete lifting-line geometry; it does not assert continuous-aero or
original-ASWING discrete parity. All vectors are in the fixed cut gauge.

For one material interval, r(f)=(1-f)ra+f rb and
R(f)=Ra exp(f log(Ra.T Rb)). Differentiating the latter gives
omega(f)=(I-B)omega_a+B omega_b, where
B=Ra f J(f k) J(k)^(-1) Ra.T. Virtual power then gives nodal
couples (I-B).T m and B.T m. Translational forces use (1-f), f.
The full geometry derivative of these weights is retained in complex probes.

Rates/accelerations below are spatial endpoint values. The harmonic tangent is
taken at zero endpoint rates, where the omitted quadratic centrifugal terms
and rate-convective acceleration have exactly zero first derivative. This is
an explicitly linearized response map, not a nonlinear time-domain evaluator.
"""

import math
import numpy as np


def hat(v):
    x, y, z = np.asarray(v)
    return np.array([[0, -z, y], [z, 0, -x], [-y, x, 0]],
                    dtype=np.result_type(v, float))


def analytic_norm(v):
    return np.sqrt(np.sum(np.asarray(v)**2, axis=-1))


def exponential(v):
    v = np.asarray(v)
    z = np.sum(v*v)
    if abs(z) < 1e-6:
        a = sum((-z)**j/math.factorial(2*j+1) for j in range(8))
        b = sum((-z)**j/math.factorial(2*j+2) for j in range(8))
    else:
        angle = np.sqrt(z)
        a, b = np.sin(angle)/angle, (1-np.cos(angle))/z
    K = hat(v)
    return np.eye(3)+a*K+b*(K@K)


def logarithm(R):
    R = np.asarray(R)
    cosine = (np.trace(R)-1)/2
    # Adjacent fixture rotations lie on the unique short arc. Do not clip a
    # complex probe or replace its derivative with a real-valued rotation.
    if cosine.real < -1+1e-8:
        raise ValueError('Relative rotation approaches the principal-arc cut')
    d = 1-cosine
    if abs(d) < 1e-5:
        factor = .5+d/6+d*d/15+d**3/35+4*d**4/315
    else:
        angle = np.arccos(cosine)
        factor = angle/(2*np.sin(angle))
    return factor*np.array([R[2, 1]-R[1, 2], R[0, 2]-R[2, 0], R[1, 0]-R[0, 1]])


def left_jacobian(v):
    z = np.sum(v*v)
    if abs(z) < 1e-6:
        b = sum((-z)**j/math.factorial(2*j+2) for j in range(8))
        c = sum((-z)**j/math.factorial(2*j+3) for j in range(8))
    else:
        angle = np.sqrt(z)
        b, c = (1-np.cos(angle))/z, (angle-np.sin(angle))/(angle*z)
    K = hat(v)
    return np.eye(3)+b*K+c*(K@K)


def inverse_left_jacobian(v):
    z = np.sum(v*v)
    if abs(z) < 1e-6:
        c = 1/12+z/720+z*z/30240+z**3/1209600
    else:
        angle = np.sqrt(z)
        c = (1-angle/(2*np.tan(angle/2)))/z
    K = hat(v)
    return np.eye(3)-K/2+c*(K@K)


class NodalSampler:
    def __init__(self, positions, material_frames, endpoints, fractions):
        self.r0 = np.asarray(positions, dtype=float)
        self.R0 = np.asarray(material_frames, dtype=float)
        self.ends = np.asarray(endpoints, dtype=int)
        self.f = np.asarray(fractions, dtype=float)
        self.nn = len(self.r0)
        self.np = len(self.ends)
        if self.r0.shape != (self.nn, 3) or self.R0.shape != (self.nn, 3, 3):
            raise ValueError('Each node requires a position and material triad')
        if self.ends.shape != (self.np, 2) or self.f.shape != (self.np,):
            raise ValueError('Each panel requires two node indices and one fraction')
        if np.any(self.ends < 0) or np.any(self.ends >= self.nn) or np.any((self.f <= 0)|(self.f >= 1)):
            raise ValueError('Invalid receiver interpolation data')

    def sample(self, displacement=None, velocity=None, acceleration=None):
        values = []
        for x in (displacement, velocity, acceleration):
            x = np.zeros((self.nn, 6)) if x is None else np.asarray(x).reshape(self.nn, 6)
            values.append(x)
        q, qd, qdd = values
        r = self.r0+q[:, :3]
        R = np.array([exponential(v)@base for v, base in zip(q[:, 3:], self.R0)])
        a, b = self.ends.T
        f = self.f[:, None]
        rm = (1-f)*r[a]+f*r[b]
        Rm, Wa, Wb = [], [], []
        for ra, rb, fraction in zip(R[a], R[b], self.f):
            k = logarithm(ra.T@rb)
            rotation = ra@exponential(fraction*k)
            wb = ra@(fraction*left_jacobian(fraction*k))@inverse_left_jacobian(k)@ra.T
            Rm.append(rotation)
            Wa.append(np.eye(3)-wb)
            Wb.append(wb)
        Rm, Wa, Wb = np.array(Rm), np.array(Wa), np.array(Wb)
        def angular(values):
            return np.einsum('nij,nj->ni', Wa, values[a, 3:])+np.einsum('nij,nj->ni', Wb, values[b, 3:])
        return dict(r0=r[a], r1=r[b], rm=rm,
                    R0=R[a], R1=R[b], Rm=Rm,
                    velocity=(1-f)*qd[a, :3]+f*qd[b, :3],
                    omega=angular(qd), acceleration=(1-f)*qdd[a, :3]+f*qdd[b, :3],
                    alpha=angular(qdd), ds=analytic_norm(r[b]-r[a]),
                    node_positions=r, node_frames=R, Wa=Wa, Wb=Wb)

    def transfer(self, sampled, force, moment):
        """Return node [force,couple] arrays; couples are about each node axis.

        Section moments are about rm. No extra r_m-r_node cross F term belongs
        here: r_m is interpolated from independent node positions, so its force
        has no rotational generalized-work component. Global angular momentum
        follows from the translational weights and Wa+Wb=I.
        """
        force, moment = np.asarray(force), np.asarray(moment)
        if force.shape != (self.np, 3) or moment.shape != force.shape:
            raise ValueError('Strip force and moment must have shape (panels,3)')
        out = np.zeros((self.nn, 6), dtype=np.result_type(force, moment, sampled['Wa']))
        for indices, fraction, angular in ((self.ends[:, 0], 1-self.f, sampled['Wa']),
                                          (self.ends[:, 1], self.f, sampled['Wb'])):
            np.add.at(out[:, :3], indices, fraction[:, None]*force)
            np.add.at(out[:, 3:], indices, np.einsum('nji,nj->ni', angular, moment))
        return out

    def virtual_power_residual(self, sampled, velocity, force, moment):
        nodal = self.transfer(sampled, force, moment)
        velocity = np.asarray(velocity).reshape(self.nn, 6)
        return (np.sum(nodal*velocity)-np.sum(force*sampled['velocity'])
                - np.sum(moment*sampled['omega']))
