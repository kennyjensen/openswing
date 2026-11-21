"""Production inputs/probes for the separately declared UA-1 stall supplement."""
import math
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def model_text(section):
    from isae_suite_unsteady import model_text as attached_model
    text = attached_model()
    old = '6.283185307179586 10 -10'
    assert text.count(old) == 2 and section.chord == 1.
    return text.replace(old, f'6.283185307179586 {section.clmax:.17g} {section.clmin:.17g}')


def request(section, steps):
    if not isinstance(steps, int) or steps < 8:
        raise ValueError('At least eight time steps required')
    table = []
    for i in range(steps+1):
        t = section.period*i/steps
        acceleration = section.motion(t)[2]*section.heave
        table.append(f'{t:.17g} {acceleration[0]:.17g} {acceleration[2]:.17g}')
    return dict(action='time', mode='time', source=model_text(section), panels=4,
        numerics=dict(beam_interpolation='drela-segspl-v1', structural_operator='drela-moving-airflow-v1'),
        condition=dict(speed=section.speed, alpha=section.alpha_deg, mach=0., stall=True,
            stall_factor=section.stall_factor, stall_width=section.stall_width, aero_lag=True,
            gravity_magnitude=0., position_earth=(section.amplitude_ratio/2*section.heave).tolist()),
        time=dict(frame='prescribed', duration=section.period, dt=section.period/steps,
            order=2, tolerance=1e-10, max_steps=4*steps, forcing='time Ax Az\n'+'\n'.join(table)+'\n'))


def evaluate_point(section, gamma, gamma_dot, velocity, acceleration, *, panels=4, representation='body'):
    from openswing.asw import parse_asw
    from openswing.aero import FlightCondition, evaluate_aerodynamics
    from openswing.network import StaticNetwork
    ca, sa = math.cos(section.alpha), math.sin(section.alpha)
    to_wind = np.array([[ca, 0., sa], [0., 1., 0.], [-sa, 0., ca]])
    if representation == 'body':
        vx, vz, _ = section.flow(velocity)
        air, acc, rotation = np.array([vx, 0., vz]), acceleration*section.heave, np.eye(3)
    elif representation == 'wind':
        air, acc, rotation = np.array([section.speed, 0., -velocity]), np.array([0., 0., acceleration]), to_wind
    else:
        raise ValueError('Unknown coordinate representation')
    condition = FlightCondition(speed=float(np.linalg.norm(air)), alpha=math.degrees(math.atan2(air[2], air[0])),
        mach=0., acceleration=tuple(acc), stall=True, stall_factor=section.stall_factor,
        stall_width=section.stall_width, aero_lag=True)
    net = StaticNetwork(parse_asw(model_text(section)), panels, condition, [0, 0, 0], [])
    rotations = np.broadcast_to(rotation, (net.nn, 3, 3))
    meshes = net.deformed_meshes(net.rj, rotations, net.geometry(net.rj, rotations))
    output = evaluate_aerodynamics(net.model, condition, meshes,
        point_positions=net.point_positions(net.rj, rotations),
        circulation=np.full(net.ng, gamma), circulation_rate=np.full(net.ng, gamma_dot))
    qs = .5*1.225*section.speed**2*200000.
    forces = {key: np.asarray(output[value])/qs for key, value in
              [('CF', 'force'), ('CF_rate', 'circulation_rate_force'), ('CF_apparent', 'apparent_force')]}
    if representation == 'wind':
        forces = {key: value@to_wind for key, value in forces.items()}
    return dict(**{key: value.tolist() for key, value in forces.items()},
        CL_instantaneous=output['CL'], CDp_fixed=output['CDp']*condition.speed**2/section.speed**2,
        section_cl=[r['cl'] for r in output['strips'] if r['lifting']],
        circulation_residual=output['circulation_residual'])
