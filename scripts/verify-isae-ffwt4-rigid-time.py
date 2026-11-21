"""Integrate a synthetic folding-tip oscillator in at most ten-step jobs.

The two point masses use literal FFWT-4 right-tip locations. All other model
choices are declared synthetic. The independent vacuum solution is a linear
torsional oscillator despite its finite rotations: I theta'' + k theta = 0.
No archived model is rewritten and no native reference pass is claimed.
"""
import argparse
from datetime import datetime, timezone
from decimal import Decimal
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from isae_ffwt4_evidence import pin, read, require, write

MASS = .0102
HINGE = .364
POINTS = ((-.0139, .3521, 0.), (-.0139, .4965, 0.))
INERTIA = MASS*sum((p[1]-HINGE)**2+p[2]**2 for p in POINTS)
FREQUENCY = 5.  # rad/s; a declared synthetic spring, not a fitted parameter
ANGLE = .4
STIFFNESS = INERTIA*FREQUENCY**2
TOLERANCE = 1e-10


def source(extended):
    import math
    torque = STIFFNESS*math.pi/2
    attachment = '3 .3521' if extended else '2 .364'
    text = (f'Name\nSynthetic rigid tip oscillator: {"extension" if extended else "pylon"}\nEnd\n'
        'Unit\nL 1 m\nT 1 s\nF 1 N\nEnd\nConstant\n9.81 1.2 340\nEnd\n'
        'Reference\n.1 .1 1\nEnd\nGround\n1 1 0\nEnd\n'
        'Joint\n1 2 2 .364 3\nEnd\nJangle\n1 1 0 0\n'
        f'{-torque:.17g} -90\n{torque:.17g} 90\nEnd\n'
        f'Weight\n{attachment} -.0139 .3521 0 {MASS*9.81:.17g}\n'
        f'2 .4965 -.0139 .4965 0 {MASS*9.81:.17g}\nEnd\n'
        'Beam 1\nFixed parent\nt x y z chord\n1 0 .2 0 .078\n2 0 .364 0 .078\nEnd\n'
        'Beam 2\nRigid lifting tip in vacuum\nt x y z chord\n.364 0 .364 0 .078\n.5 0 .5 0 .078\nEnd\n')
    if extended:
        text += ('Joint\n2 3 .364 .364 0\nEnd\nBeam 3\nMassless rigid auxiliary anchor\n'
                 't x y z\n.3521 0 .3521 0\n.364 0 .364 0\nEnd\n')
    return text


def samples(result, extended):
    import numpy as np
    rows = []
    for snapshot in result['snapshots']:
        nodes = snapshot['nodes']
        def node(beam, t):
            candidates = [(i, n) for i, n in enumerate(nodes)
                          if n['beam'] == beam and abs(n['t']-t) < 1e-12]
            require(len(candidates) == 1, 'Missing or ambiguous anchor')
            return candidates[0]
        root, _ = node(2, HINGE)
        hinge, = snapshot['hinges']
        points = []
        anchors = ((3, .3521) if extended else (2, .364), (2, .4965))
        for p, (beam, t) in zip(POINTS, anchors):
            i, n = node(beam, t)
            offset = np.asarray(n['rotation'])@(np.asarray(p)-[0., t, 0.])
            omega = np.asarray(snapshot['local_rates'][i])
            alpha = np.asarray(snapshot['local_rate_derivative'][i])
            points.append(dict(position=(np.asarray(n['position'])+offset).tolist(),
                velocity=(np.asarray(snapshot['local_velocity'][i])+np.cross(omega, offset)).tolist(),
                acceleration=(np.asarray(snapshot['local_acceleration'][i])+np.cross(alpha, offset)
                              +np.cross(omega, np.cross(omega, offset))).tolist()))
        rows.append(dict(time=snapshot['time'], angle=np.deg2rad(hinge['angle_deg']),
            rate=snapshot['local_rates'][root][0],
            angular_acceleration=snapshot['local_rate_derivative'][root][0], points=points,
            residual=snapshot['residual'], order=snapshot['order'],
            effective_order=snapshot['restart']['accepted_method'].get('effective_order')))
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--representation', choices=('extension', 'pylon'), required=True)
    parser.add_argument('--dt', choices=('.02', '.01', '.005'), required=True)
    parser.add_argument('--steps', type=int, default=10)
    parser.add_argument('--resume-from', type=Path)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    require(1 <= args.steps <= 10, 'At most ten steps per job')
    dt = Decimal(args.dt)
    extended = args.representation == 'extension'
    folder = args.output_dir.resolve()
    folder.mkdir(parents=True, exist_ok=False)
    kernels = [pin(p) for p in sorted((ROOT/'openswing').glob('*.py'))]
    helpers = [pin(__file__), pin(ROOT/'scripts/isae_ffwt4_evidence.py')]
    model_path = folder/'model.asw'
    model_path.write_text(source(extended))
    from openswing.asw import parse_asw
    from openswing.source_dynamics import MOVING_POLICY, SourceMovingNetwork
    from openswing.time_integration import solve_time
    from openswing.time_state import checkpoint, resume_time
    model = parse_asw(model_path.read_text(), beam_interpolation='drela-segspl-v1')
    panels = {'default': 4, 'beams': {'1': {'nodes': [1, 1.25, 1.5, 1.75, 2]},
        '2': {'nodes': [.364, .4, .44, .47, .4965, .5]}}}
    if extended:
        panels['beams']['3'] = {'nodes': [.3521, .355075, .35805, .361025, .364]}
    network = SourceMovingNetwork(model, panels, None, [0, 0, 0], [])
    require(not network.ng and not network.source_material_compliance.any()
            and not network.source_weights.any(), 'Fixture must be massless rigid beams in vacuum')
    start, parent = 0, None
    if args.resume_from:
        parent = read(args.resume_from/'report.json')
        plan = read(args.resume_from/'plan.json')
        require(parent['status'] == 'SEGMENT_COMPUTED' and plan['dt'] == args.dt
                and plan['representation'] == args.representation, 'Incompatible history')
        require(plan['kernel_pins'] == kernels and plan['helper_pins'] == helpers, 'Changed kernel or helper')
        for key in ('result', 'checkpoint', 'plan'):
            require(pin(parent[key]['path']) == parent[key], 'Changed parent '+key)
        start = plan['end_step']
    require(dt*(start+args.steps) <= Decimal('.2'), 'Do not exceed the declared study duration')
    plan = dict(schema='isae-ffwt4-rigid-time-v1', representation=args.representation,
        dt=args.dt, start_step=start, end_step=start+args.steps, duration=.2,
        kernel_pins=kernels, helper_pins=helpers, model=pin(model_path), panels=panels,
        parent_report=pin(args.resume_from/'report.json') if parent else None,
        mass_each=MASS, points=POINTS, hinge_y=HINGE, inertia_about_hinge=INERTIA,
        stiffness=STIFFNESS, frequency_rad_s=FREQUENCY, initial_angle_rad=ANGLE,
        tolerance=TOLERANCE, structural_operator=MOVING_POLICY,
        original_ISAE_sources_modified=False, native_predictions_added=0)
    write(folder/'plan.json', plan)
    started = time.monotonic()
    with (folder/'progress.jsonl').open('w') as log:
        def progress(*event):
            log.write(json.dumps(dict(seconds=time.monotonic()-started, event=event))+'\n'); log.flush()
        if parent:
            result = resume_time(model, read(parent['checkpoint']['path']), duration=float(dt*args.steps),
                dt=float(dt), order=2, tolerance=TOLERANCE, max_steps=args.steps, progress=progress)
        else:
            result = solve_time(model, panels=panels, duration=float(dt*args.steps), dt=float(dt),
                order=2, frame='prescribed', gravity=[0., 0., 0.], gravity_magnitude=0.,
                initial_loads=[dict(beam=2, t=.5, moment=[STIFFNESS*ANGLE, 0., 0.])], loads=[],
                tolerance=TOLERANCE, continuation_steps=4, max_steps=args.steps,
                structural_operator=MOVING_POLICY, progress=progress)
    write(folder/'result.json.gz', result)
    require(result['converged'] and result['accepted_steps'] == args.steps
            and result['rejected_steps'] == 0, 'Unexpected rejection or incomplete history')
    require(result['temporal_policy'] == 'drela-euler-bdf-v1', 'Wrong time equations')
    if parent:
        require(result['checkpoint_validation']['discrete_replayed'], 'Checkpoint not replayed')
    rows = samples(result, extended)
    for i, row in enumerate(rows):
        tick = start+i
        require(abs(row['time']-float(tick*dt)) < 1e-12 and row['residual'] <= TOLERANCE,
                'Invalid time or unconverged residual')
        if i:
            require(row['effective_order'] == (1 if tick == 1 else 2), 'BDF history restarted')
    write(folder/'checkpoint.json.gz', checkpoint(result, -1))
    require(kernels == [pin(p['path']) for p in kernels] and helpers == [pin(p['path']) for p in helpers],
            'Sources changed during solve')
    report = dict(status='SEGMENT_COMPUTED', observed_at=datetime.now(timezone.utc).isoformat(),
        seconds=time.monotonic()-started, accepted_steps=result['accepted_steps'],
        rejected_steps=result['rejected_steps'], nodes=network.nn, samples=rows,
        plan=pin(folder/'plan.json'), result=pin(folder/'result.json.gz'),
        checkpoint=pin(folder/'checkpoint.json.gz'), native_predictions_added=0)
    write(folder/'report.json', report)
    print(json.dumps({k: v for k, v in report.items() if k not in ('samples', 'plan', 'result', 'checkpoint')}), flush=True)


if __name__ == '__main__':
    main()
