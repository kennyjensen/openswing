"""Owned continuous hinge charts for physical states and local residuals.

Angles are radians, ordered by type-3 constraint. They are never inferred from
rotation matrices without a prior branch. A trial cannot mutate its seed.
"""
import numpy as np
from .aero import AnalysisError
from .local_motion import rotation_matrix as exp, rotation_vector as log

def joints(n):
    return tuple(c for c in n.constraints if c['type']==3)

def checked(n,centers):
    rows=joints(n)
    if not isinstance(centers,(tuple,list)) or len(centers)!=len(rows):
        raise AnalysisError('Hinge history needs one owned angle per hinge.')
    values=[]
    for value in centers:
        if isinstance(value,(bool,np.bool_)) or not isinstance(value,(int,float,np.integer,np.floating)):
            raise AnalysisError('Hinge history angles must be finite numbers.')
        try:value=float(value)
        except OverflowError as exc:raise AnalysisError('Hinge history angle overflows.') from exc
        if not np.isfinite(value):raise AnalysisError('Hinge history angles must be finite numbers.')
        values.append(value)
    return tuple(values)

def current(n):
    return checked(n,tuple(c.get('angle_chart',0.) for c in joints(n)))

def lifted(n,q,centers,previous_q=None):
    centers=checked(n,centers);result=[]
    for c,center in zip(joints(n),centers):
        i,j=c['a'],c['b'];axis=c['law'].axis
        if previous_q is not None:
            travel=sum(float(np.linalg.norm(log(q[k]@previous_q[k].T))) for k in (i,j))
            if travel>=np.pi-.05:
                raise AnalysisError('Relative hinge travel approaches pi; reduce the time step.')
        vector=log(exp(-center*axis)@(q[i].T@q[j]))
        if np.linalg.norm(vector)>=np.pi-.05:
            raise AnalysisError('Hinge history approaches its local chart boundary; reduce the time step.')
        result.append(float(center+axis@vector))
    return tuple(result)

def at_network(n,q):
    return lifted(n,q,current(n))
