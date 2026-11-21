"""Energy diagnostics for the documented componentwise strain-rate law."""
import numpy as np


def damping_diagnostics(compliance, times, lengths):
    """Check dissipation on finite-stiffness strains after unit scaling.

    e + D edot = S load does not guarantee passive damping when S and D
    couple different damping times. Eigenvalues below are in energy coordinates
    and have time units. This diagnostic does not modify the prescribed law.
    """
    elements=[]
    for index,(s,d,length) in enumerate(zip(compliance,times,lengths)):
        scale=np.r_[np.ones(3),np.full(3,length)]
        s=s*scale[:,None]*scale[None,:]
        values,basis=np.linalg.eigh(s)
        active=values>max(float(np.max(values))*1e-12,0.)
        v=basis[:,active];ev=values[active]
        transformed=v.T@(d[:,None]*v)
        if len(ev):
            energy=transformed*np.sqrt(ev[None,:]/ev[:,None])
            minimum=float(np.linalg.eigvalsh((energy+energy.T)/2)[0])
        else:
            minimum=None
        leakage=float(np.linalg.norm(basis[:,~active].T@(d[:,None]*v)))
        tolerance=1e-10*max(float(np.max(abs(d))),1e-30)
        elements.append(dict(element=index,finite_strain_rank=int(active.sum()),
            minimum_energy_damping_time=minimum,rigid_subspace_coupling=leakage,
            passive=(minimum is None or minimum>=-tolerance) and leakage<=tolerance))
    return dict(passive=all(e['passive'] for e in elements),elements=elements,
        rank_relative_tolerance=1e-12,
        note='A constitutive diagnostic only: aeroelastic stability and passivity of the full discretization are not established.')
