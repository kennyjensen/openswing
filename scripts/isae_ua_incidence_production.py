"""Production instantaneous-load probes in chord axes and fixed wind axes."""
import math
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]


def evaluate_point(gamma, gamma_dot, velocity, acceleration, *, alpha_deg,
                   panels=4, representation='body', frozen=False, speed=10.):
    sys.path.insert(0, str(ROOT))
    from openswing.asw import parse_asw
    from openswing.aero import FlightCondition, evaluate_aerodynamics
    from openswing.network import StaticNetwork
    from isae_suite_unsteady import model_text
    alpha = math.radians(alpha_deg)
    ca, sa = math.cos(alpha), math.sin(alpha)
    to_wind = np.array([[ca, 0., sa], [0., 1., 0.], [-sa, 0., ca]])
    if representation == 'body':
        air = np.array([speed*ca+velocity*sa, 0., speed*sa-velocity*ca])
        acc = acceleration*np.array([-sa, 0., ca])
        rotation = np.eye(3)
    elif representation == 'wind':
        air = np.array([speed, 0., -velocity])
        acc = np.array([0., 0., acceleration])
        rotation = to_wind
    else:
        raise ValueError('Unknown coordinate representation')
    condition = FlightCondition(speed=float(np.linalg.norm(air)),
        alpha=math.degrees(math.atan2(air[2], air[0])), mach=0.,
        acceleration=tuple(acc), stall=False, aero_lag=True, freeze_influences=frozen)
    net = StaticNetwork(parse_asw(model_text()), panels, condition, [0, 0, 0], [])
    rotations = np.broadcast_to(rotation, (net.nn, 3, 3))
    meshes = net.deformed_meshes(net.rj, rotations, net.geometry(net.rj, rotations))
    output = evaluate_aerodynamics(net.model, condition, meshes,
        point_positions=net.point_positions(net.rj, rotations),
        circulation=np.full(net.ng, gamma), circulation_rate=np.full(net.ng, gamma_dot))
    qs = .5*1.225*speed**2*200000.
    forces = {key: np.asarray(output[value])/qs for key, value in
              [('CF', 'force'), ('CF_rate', 'circulation_rate_force'), ('CF_apparent', 'apparent_force')]}
    forces['CF_circulation_and_profile'] = forces['CF']-forces['CF_rate']-forces['CF_apparent']
    if representation == 'wind':
        forces = {key: value@to_wind for key, value in forces.items()}
    # All reported vectors return to the original chord axes for comparison.
    return dict(**{key: value.tolist() for key, value in forces.items()},
                CL_instantaneous=output['CL'],
                circulation_residual=output['circulation_residual'],
                maximum_residual=float(np.max(abs(np.asarray(output['circulation_residual'])))))
