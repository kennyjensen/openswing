"""Independent stationary-base real-mass replay of Drela unsteady Eqs.23/38–40.

No OpenSwing imports. Supplied endpoint material data and loaded geometry use
the declared source endpoint averaging and symmetric nodal wrench transfer.
This checks the equation/kinematic coupling, not historical ASWING quadrature.
"""
import numpy as np


PARTS = ['frame_velocity_derivative', 'frame_convective_acceleration',
         'frame_angular_acceleration', 'elastic_translation_acceleration',
         'elastic_rotation_acceleration', 'section_rotary_inertia',
         'interval_rotary_inertia', 'gravity_orientation',
         'gravity_centroid_arm', 'gravity_reference_arm']


def evaluate(data, displacement, rotation, velocity, rates, frame_velocity,
             frame_rates, omega, reference_displacement):
    """Complex physical amplitudes exp(i omega t), zero mean rotation/accel.

    Endpoint weights contain ds/2. Completed forces/couples are averaged onto
    both structural nodes. The moment reference follows its supplied motion.
    Frame gravity rotation follows Omega = i omega delta_phi, independently of
    the solver's Euler-angle chart and acceleration-state slots.
    """
    a,b,node=data['a'],data['b'],data['node']
    q=data['frames'];r=data['node_positions'];g=data['gravity']
    mass=data['weight_density']*data['ds']/(2*float(data['g_constant']))
    offset=np.einsum('nij,nj->ni',q,data['cg_local'])
    doffset=np.cross(rotation[node],offset)
    position=r[node]+offset
    midpoint=(r[a]+r[b])/2
    dmidpoint=(displacement[a]+displacement[b])/2
    factor=data['ds']/(2*float(data['g_constant']))
    icc=data['icc_weight_density']*factor;inn=data['inn_weight_density']*factor
    diagonal=np.column_stack([icc,icc+inn,inn])
    section=(q*diagonal[:,None,:])@q.transpose(0,2,1)
    segment_diagonal=mass[:,None]*data['ds'][:,None]**2/12*np.array([1.,0.,1.])
    segment=(q*segment_diagonal[:,None,:])@q.transpose(0,2,1)
    alpha=1j*omega*frame_rates
    local_alpha=1j*omega*rates[node]
    acceleration=[np.broadcast_to(1j*omega*frame_velocity,offset.shape),
                  np.broadcast_to(np.cross(frame_rates,data['base_velocity']),offset.shape),
                  np.cross(alpha,position),1j*omega*velocity[node],
                  np.cross(local_alpha,offset)]
    force=np.zeros((len(PARTS),len(node),3),complex)
    couple=np.zeros_like(force)
    for j,value in enumerate(acceleration):force[j]=-mass[:,None]*value
    couple[5]=-np.einsum('nij,nj->ni',section,alpha+local_alpha)
    couple[6]=-np.einsum('nij,nj->ni',segment,alpha+local_alpha)
    dg=-np.cross(frame_rates/(1j*omega),g)
    force[7]=mass[:,None]*dg
    base_force=mass[:,None]*g
    couple+=np.cross(offset[None,:,:],force)
    couple[8]=np.cross(doffset,base_force)
    nf=np.zeros((len(PARTS),len(r),3),complex);nm=np.zeros_like(nf)
    nf0=np.zeros_like(r);nm0=np.zeros_like(r)
    for ids in (a,b):
        np.add.at(nf0,ids,base_force/2)
        np.add.at(nm0,ids,np.cross(offset,base_force)/2)
        for j in range(len(PARTS)):
            np.add.at(nf[j],ids,force[j]/2)
            np.add.at(nm[j],ids,couple[j]/2)
    moments=(couple+np.cross((midpoint-data['moment_reference'])[None,:,:],force)).sum(axis=1)
    moments[9]+=np.cross(dmidpoint-reference_displacement,base_force).sum(axis=0)
    wrench=np.concatenate([force.sum(axis=1),moments],axis=1)
    return dict(nodal_force=nf,nodal_moment=nm,wrenches=wrench,
                base_force=nf0,base_moment=nm0,mass=mass,section_inertia=section,
                interval_inertia=segment,gravity_derivative=dg)
