"""Production probes for a prescribed, nonuniform inclined-wing circulation."""
import math
from pathlib import Path
import sys
import numpy as np

ROOT=Path(__file__).resolve().parents[1]


def evaluate(gamma,rate,velocity,acceleration,*,alpha_deg,representation='body',span=10.,speed=10.):
    sys.path.insert(0,str(ROOT))
    from openswing.aero import FlightCondition,evaluate_aerodynamics
    from openswing.asw import parse_asw
    from openswing.network import StaticNetwork
    from isae_suite_unsteady import model_text
    a=math.radians(alpha_deg);ca,sa=math.cos(a),math.sin(a)
    to_wind=np.array([[ca,0.,sa],[0.,1.,0.],[-sa,0.,ca]])
    if representation=='body':
        air=np.array([speed*ca+velocity*sa,0.,speed*sa-velocity*ca])
        acc=acceleration*np.array([-sa,0.,ca]);rotation=np.eye(3)
    elif representation=='wind':
        air=np.array([speed,0.,-velocity]);acc=np.array([0.,0.,acceleration]);rotation=to_wind
    else:raise ValueError('Use body or wind coordinates')
    condition=FlightCondition(speed=float(np.linalg.norm(air)),alpha=math.degrees(math.atan2(air[2],air[0])),
        mach=0.,stall=False,aero_lag=True,acceleration=tuple(acc))
    net=StaticNetwork(parse_asw(model_text(span)),len(gamma),condition,[0,0,0],[])
    rotations=np.broadcast_to(rotation,(net.nn,3,3))
    meshes=net.deformed_meshes(net.rj,rotations,net.geometry(net.rj,rotations))
    actual=evaluate_aerodynamics(net.model,condition,meshes,
        point_positions=net.point_positions(net.rj,rotations),circulation=gamma,circulation_rate=rate)
    qs=.5*1.225*speed**2*span
    forces={key:np.array(actual[value])/qs for key,value in
        (('CF','force'),('CF_rate','circulation_rate_force'),('CF_apparent','apparent_force'))}
    forces['CF_circulation_and_profile']=forces['CF']-forces['CF_rate']-forces['CF_apparent']
    if representation=='wind':forces={k:v@to_wind for k,v in forces.items()}
    return dict(**forces,residual=np.array(actual['circulation_residual']),
        stations=np.array(meshes[0].rm)[:,1],nodes=np.r_[meshes[0].r0[:,1],meshes[0].r1[-1,1]])
