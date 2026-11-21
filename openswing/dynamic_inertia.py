"""Distributed elastic inertia with virtual-power-consistent nodal transfer.

Material densities/offsets are midpoint data, as in the steady discretization.
Eight Gauss points resolve the centerline and SO(3) section interpolation. No
finite-segment inertia is added: its translational contribution is integrated.
"""
import numpy as np
from .vector_ops import cross3
from .inertia import inertial_wrench

_X,_W=np.polynomial.legendre.leggauss(8)
_FRACTIONS=(_X+1)/2
_WEIGHTS=_W/2


def moving_mass_loads(network, local, meshes, motion, gravity, point_positions, point_rotations, *, with_end_forces=False, _loads_only=False):
    """Return nodal inertial/gravity loads, integration records, end couples."""
    force=np.zeros_like(local.r);moment=np.zeros_like(local.r)
    ends=np.zeros((network.ne,2,3));end_forces=np.zeros_like(ends);records=[]
    # At a stationary elastic state with no frame rotation, translational
    # acceleration is uniform and centroidal inertia contributes no couple.
    # Keep the original Gauss positions/transfer, but omit unused inertia and
    # velocity reports during steady residual perturbations.
    uniform = (_loads_only and not np.any(motion.rates) and not np.any(motion.angular_acceleration)
               and not any(np.any(value) for value in local.values))
    acceleration = np.asarray(gravity)-motion.acceleration if uniform else None
    for mesh in meshes:
        beam=mesh.beam.index;sl=network.beam_elements[beam]
        a=network.a[sl]
        fractions=np.broadcast_to(_FRACTIONS,(len(a),len(_FRACTIONS)))
        field,rotation,_=local.sample(beam,fractions,material=True)
        for mass,c,n,icc,inn in network.inertia_model.data[beam]:
            if _loads_only and not any(np.any(value) for value in (mass,icc,inn)):
                continue
            mass=mass[:,None]*_WEIGHTS
            position=field.origin+c[:,None,None]*rotation[...,0]+n[:,None,None]*rotation[...,2]
            if uniform:
                f=mass[...,None]*acceleration
                m=np.zeros_like(position)
            else:
                diagonal=np.stack([icc,icc+inn,inn],axis=-1)[:,None,:]*_WEIGHTS[None,:,None]
                inertia=(rotation*diagonal[...,None,:])@rotation.swapaxes(-1,-2)
                spin=np.zeros_like(position)
                f,m=inertial_wrench(mass,position,inertia,spin,motion,gravity,network.model.reference[2],local_motion=field)
            couple=m+cross3(position-field.origin,f)
            for end,(ids,nodal_force,nodal_moment) in enumerate(local.nodal_wrenches(beam,fractions,f,couple,material=True)):
                np.add.at(force,ids,nodal_force);np.add.at(moment,ids,nodal_moment)
                ends[sl,end]+=nodal_moment
                end_forces[sl,end]+=nodal_force
            if not _loads_only:
                records.append(dict(beam=beam,point=None,mass=mass.ravel(),position=position.reshape(-1,3),
                    inertia=inertia.reshape(-1,3,3),spin=spin.reshape(-1,3),
                    relative_velocity=field.velocity_at(position).reshape(-1,3),relative_rates=field.rates.reshape(-1,3)))
    for record in network.inertia_model.point_elements(point_positions,point_rotations):
        index=record['point'];field=local.point('weight',index)
        f,m=inertial_wrench(*(record[k] for k in ('mass','position','inertia','spin')),
            motion,gravity,network.model.reference[2],local_motion=field)
        i=network.node(*network.weights[index][:2])
        force[i]+=f[0];moment[i]+=m[0]+cross3(record['position'][0]-local.r[i],f[0])
        if not _loads_only:
            record.update(relative_velocity=field.velocity_at(record['position']),relative_rates=field.rates[None,:])
            records.append(record)
    return (force,moment,records,ends,end_forces) if with_end_forces else (force,moment,records,ends)
