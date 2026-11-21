"""Stationary-base linearization of Drela unsteady Eqs.23, 43--44.

No OpenSwing imports. Loaded geometry/materials and the BASE relative fluid
velocity are input data. This independently reconstructs section kinematics
and apparent loads, not circulation, the base airflow, or aircraft dynamics.
"""
import numpy as np
from scipy.spatial.transform import Rotation


PARTS = ['rotation_rate', 'frame_velocity_derivative', 'frame_convective_acceleration',
         'frame_angular_acceleration', 'elastic_translation_acceleration',
         'elastic_rotation_acceleration', 'angular_inertia_couple']


def skew(v):
    x,y,z=v
    return np.array([[0.,-z,y],[z,0.,-x],[-y,x,0.]])


def jacobian(v):
    x=float(v@v);k=skew(v)
    if x<1e-6:
        a=.5-x/24+x*x/720;b=1/6-x/120+x*x/5040
    else:
        theta=np.sqrt(x);a=(1-np.cos(theta))/x;b=(theta-np.sin(theta))/(x*theta)
    return np.eye(3)+a*k+b*k@k


def evaluate(data, velocity, rates, frame_velocity, frame_rates, omega):
    """Physical complex amplitudes, exp(i omega t); return seven load parts."""
    a,b=data['a'],data['b'];fraction=data['fraction'];q=data['node_frames']
    local_velocity=(1-fraction[:,None])*velocity[a]+fraction[:,None]*velocity[b]
    local_rate=np.empty_like(local_velocity)
    for i,(lo,hi,f) in enumerate(zip(a,b,fraction)):
        k=Rotation.from_matrix(q[lo].T@q[hi]).as_rotvec()
        wb=q[lo]@(f*jacobian(f*k))@np.linalg.solve(jacobian(k),q[lo].T)
        local_rate[i]=rates[lo]+wb@(rates[hi]-rates[lo])
    chord=data['chord'];frame=data['frames'];c,s,n=frame[:,:,0],frame[:,:,1],frame[:,:,2]
    arm=((.5-data['xax'])*chord)[:,None]*c
    mass=float(data['density'])*np.pi/4*chord**2*data['length']
    omega_total=frame_rates+local_rate
    alpha_frame=1j*omega*frame_rates;alpha_local=1j*omega*local_rate
    rate_scalar=np.sum(np.cross(data['axis_air_velocity'],omega_total)*n,axis=1)
    forces=np.zeros((len(PARTS),len(a),3),complex);moments=np.zeros_like(forces)
    forces[0]=mass[:,None]*rate_scalar[:,None]*n
    moments[0]=-(mass*chord/4*rate_scalar)[:,None]*s
    accelerations=[np.broadcast_to(1j*omega*frame_velocity,local_velocity.shape),
        np.broadcast_to(np.cross(frame_rates,data['base_frame_velocity']),local_velocity.shape),
        np.cross(alpha_frame,data['positions']+arm),1j*omega*local_velocity,np.cross(alpha_local,arm)]
    for index,acceleration in enumerate(accelerations,1):
        forces[index]=-(mass*np.sum(acceleration*n,axis=1))[:,None]*n
    moments[6]=-(mass*chord**2/32*np.sum((alpha_frame+alpha_local)*s,axis=1))[:,None]*s
    moments+=np.cross(arm[None,:,:],forces)
    nodal_force=np.zeros((len(PARTS),len(velocity),3),complex);nodal_moment=np.zeros_like(nodal_force)
    midpoint=(data['node_positions'][a]+data['node_positions'][b])/2
    # The declared source operator transfers each completed strip wrench
    # symmetrically about its arithmetic structural midpoint.
    couple=moments+np.cross((data['positions']-midpoint)[None,:,:],forces)
    for part in range(len(PARTS)):
        for ids in (a,b):
            np.add.at(nodal_force[part],ids,forces[part]/2)
            np.add.at(nodal_moment[part],ids,couple[part]/2)
    wrench=np.concatenate([forces.sum(axis=1),
        (moments+np.cross((data['positions']-data['moment_reference'])[None,:,:],forces)).sum(axis=1)],axis=1)
    return dict(forces=forces,moments=moments,nodal_force=nodal_force,nodal_moment=nodal_moment,
        wrench=wrench,local_velocity=local_velocity,local_rate=local_rate)
