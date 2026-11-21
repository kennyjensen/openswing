"""Same-evaluation production outputs; no additional residual/load calls."""
import numpy as np
from scipy.spatial.transform import Rotation
from openswing.local_motion import left_jacobian


def extract(system,state,data,fixture):
    n=system.network;R=state.orientation;a=np.asarray(fixture['hinge']['axis']);a=a/np.linalg.norm(a)
    fin=n.beam_nodes[2];carrier=n.beam_nodes[1];i,j=carrier[-1],fin[0]
    relative=state.Q[i].T@state.Q[j]
    eta=Rotation.from_matrix(relative).as_rotvec()@a
    phi=Rotation.from_matrix(R).as_rotvec();J=left_jacobian(phi)
    packet=data['aero']
    def wrench(prefix=''):
        return np.r_[packet[prefix+'force'],packet[prefix+'moment']]
    total=wrench();rate=wrench('circulation_rate_');apparent=wrench('apparent_')
    families=np.array([total,rate,apparent,total-rate-apparent])
    aero=np.stack([np.zeros_like(families),families,families],axis=1)
    aeroE=np.concatenate([aero[...,:3]@R.T,aero[...,3:]@R.T],axis=-1)
    # Point weights are the ONLY real masses. Retain their already evaluated
    # cache at the two distinct attachment nodes; no inertial law is repeated.
    mf,mm=n.mass_cached[:2];mass=[]
    for row in n.weights:
        node=n.node(*row[:2]);mass.append(np.r_[mf[node],mm[node]+np.cross(state.r[node],mf[node])])
    mass=np.asarray(mass)
    rawglobal=np.r_[data['force'].sum(axis=0),(data['moment']+np.cross(state.r,data['force'])).sum(axis=0)]
    reaction=next(row for row in data['reactions'] if row['kind']=='joint')
    hinge=np.r_[reaction['other_force'],reaction['other_moment']]
    points=np.array(n.point_positions(state.r,state.Q))@R.T+state.position
    localrate=a@(state.Q[i].T@(state.w[j]-state.w[i]))
    spring=np.zeros(7);spring[6]=-data['hinges'][0]['structural_moment']
    originM=R@total[3:];F=R@total[:3]
    hingeM=R@(total[3:]-np.cross(state.r[j],total[:3]))
    generalized=np.r_[F,J.T@originM,(R@state.Q[i]@a)@hingeM]
    return dict(frame_position_earth=state.position,frame_rotation_vector=phi,
        frame_velocity_body=state.U,frame_rates_body=state.Omega,
        frame_acceleration_body=data['motion'].acceleration,
        frame_angular_acceleration_body=data['motion'].angular_acceleration,
        hinge_angle=np.array([eta]),hinge_rate=np.array([localrate]),gamma=state.gamma,
        fin_node_position_earth=state.r[fin]@R.T+state.position,
        fin_node_velocity_earth=(state.U+state.u[fin]+np.cross(state.Omega,state.r[fin]))@R.T,
        fin_angular_velocity_earth=R@(state.Omega+state.w[j]),
        mass_point_positions_earth=points,aero_wrenches_earth=aeroE,aero_wrenches_body=aero,
        mass_wrenches_body=mass,global_applied_wrench_body=rawglobal,
        hinge_reaction_on_fin_body=hinge,spring_generalized_force=spring,
        generalized_aerodynamic_load=generalized)


def raw_packet(system,state,data,fixture):
    n=system.network
    return dict(output=extract(system,state,data,fixture),state=dict(x=state.x,r=state.r,Q=state.Q,u=state.u,w=state.w,
        U=state.U,Omega=state.Omega,position=state.position,orientation=state.orientation,gamma=state.gamma),
        residual_data={k:data[k] for k in ('r','Q','N','M','aero','force','moment','reactions','hinges','masses',
            'element_forces','element_moments','distributed_mass_force','operating_values','gravity')},
        mass_cache_force=n.mass_cached[0].copy(),mass_cache_moment=n.mass_cached[1].copy())
