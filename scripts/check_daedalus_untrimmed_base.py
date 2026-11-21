"""Conditional Daedalus response about an instantaneous accelerating state.

This does not recover Drela's unpublished operating point. At the same speed
and current mesh, prescribe alpha=beta=attitude=controls=power=0 and solve all
six frame accelerations with the full loaded shape. A subsequent descriptor
is a locally frozen linearization, not a periodic trajectory about steady
flight. Each stage is serial, resource limited, and independently recorded.
"""
import argparse
from dataclasses import asdict, replace
from pathlib import Path
from types import SimpleNamespace

from check_daedalus_load_sensitivity import ROOT, read, write
from daedalus_bounded_job import run
import check_daedalus_regular_mesh as regular
import check_daedalus_regular_mesh_response as response_study

STUDY = ROOT/'artifacts/daedalus-untrimmed-base-20261114'
BASE = response_study.SEED
QUALIFICATION = ('Conditional instantaneous accelerating state, not recovered '
                 'native settings or trimmed flight. A frozen local descriptor '
                 'does not establish a periodic response along its trajectory.')


def initialize(folder, args):
    from openswing.equilibrium_state import restore_physical_fields
    from openswing.operating import time_load_constraints
    from openswing.time_state import read_condition, condition_data
    packet = read(BASE)
    condition = replace(read_condition(packet['launch']['condition']),
        alpha=0., beta=0., attitude=[0., 0., 0.],
        rates=[0., 0., 0.], acceleration=[0., 0., 0.],
        angular_acceleration=[0., 0., 0.],
        controls={key: 0. for key in read_condition(packet['launch']['condition']).controls},
        powers={key: 0. for key in read_condition(packet['launch']['condition']).powers})
    launch = dict(packet['launch'], condition=condition_data(condition),
        released_constraints=[asdict(c) for c in time_load_constraints('free')])
    n = regular.network(dict(packet, launch=launch))
    x = restore_physical_fields(n, packet)
    # Retain only physical elastic fields as a Newton guess, not a solution.
    x[n.operating_start:] = 0.
    result = regular.source.save_state(folder, n, x,
        qualification=QUALIFICATION, initial_guess_only=True)
    assert not result['accepted']
    return result


def audit(folder, args):
    import numpy as np
    n, x = regular.setup(args.seed)
    residual, detail = n.residual(x, detail=True)
    assert max(abs(residual)) <= 1e-9
    condition, motion, _ = n.operating.apply(x[n.operating_start:])
    assert condition.alpha == condition.beta == 0.
    assert condition.attitude == [0., 0., 0.]
    assert all(v == 0. for v in [*condition.controls.values(), *condition.powers.values()])
    assert np.linalg.norm(motion.rates) == 0.
    system = regular.previous.dynamic(args)
    zero = np.zeros(system.size)
    error = float(max(abs(system.residual(zero, zero))))
    assert error <= 1e-9
    report = system.base_report()
    assert not report['modal_base']['kinematically_steady']
    write(folder/'base-report.json', report)
    prior, px = regular.setup(BASE)
    shape = []
    for network, state, name in [(prior, px, 'level-flight'), (n, x, 'zero-incidence')]:
        positions = network.unpack(state)[0]
        _, ids = network.station_nodes[1]
        displacement = positions[ids] - network.rj[ids]
        shape.append(dict(case=name, wing_z_range_ft=[float(min(displacement[:, 2])),
            float(max(displacement[:, 2]))],
            wing_tip_displacement_ft=displacement[[0, -1]].tolist()))
    return dict(qualification=QUALIFICATION, residual_max=float(max(abs(residual))),
        dynamic_residual=error, dynamic_states=system.size,
        acceleration_ft_s2=motion.acceleration.tolist(),
        angular_acceleration_rad_s2=motion.angular_acceleration.tolist(),
        shape_comparison=shape)


def execute(folder, arguments):
    args = SimpleNamespace(**arguments)
    args.seed = Path(args.seed) if args.seed else None
    args.matrix = Path(args.matrix) if args.matrix else None
    args.parts = [Path(p) for p in args.parts or []]
    previous = response_study.configure()
    previous.STUDY = STUDY
    previous.stages.STUDY = STUDY
    if args.stage == 'init':
        return initialize(folder, args)
    if args.stage == 'audit':
        return audit(folder, args)
    steady = dict(trim_geometry=previous.stages.geometry,
        trim_other=previous.stages.trim_other, trim_join=previous.stages.join_trim,
        trim_rank=previous.stages.rank_trim, correct=previous.stages.correct)
    if args.stage in steady:
        result = steady[args.stage](folder, args)
    elif args.stage == 'geometry':
        result = previous.stages.geometry(folder, args)
    elif args.stage == 'geometry_join':
        result = previous.stages.join_geometry(folder, args)
    elif args.stage == 'response':
        result = previous.response(folder, args)
    else:
        result = previous.source.staged_linear(folder, args)
    result['qualification'] = QUALIFICATION
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage', choices=['init', 'trim_geometry', 'trim_other',
        'trim_join', 'trim_rank', 'correct', 'audit', 'geometry', 'geometry_join',
        'other', 'mass', 'assemble', 'response'])
    parser.add_argument('--tag', required=True)
    parser.add_argument('--seed')
    parser.add_argument('--matrix')
    parser.add_argument('--parts', nargs='+')
    parser.add_argument('--start', type=int, default=0)
    parser.add_argument('--count', type=int, default=96)
    parser.add_argument('--step', type=float, default=1e-5)
    parser.add_argument('--frequencies', type=float, nargs='+',
                        default=[.1, 1., 1.15737773741517, 1.5])
    args = vars(parser.parse_args())
    args['speed'] = 6.7
    if args['stage'] != 'init' and not args['seed']:
        parser.error('--seed required')
    pinned = response_study.inputs() + [ROOT/'reference/aswing_doc.txt',
        ROOT/'scripts/check_daedalus_regular_mesh_response.py']
    for key in ('seed', 'matrix'):
        if args[key]:
            args[key] = str(Path(args[key]).resolve())
    if args['seed']:
        pinned.append(Path(args['seed']))
    for part in (args['parts'] or []) + ([args['matrix']] if args['matrix'] else []):
        pinned.extend(p for p in Path(part).iterdir() if p.suffix in ('.json', '.npz'))
    if args['stage'] == 'response':
        pinned.append(STUDY/'mass/layout.json')
    run(STUDY, args['tag'], pinned, execute, args, __file__)


if __name__ == '__main__':
    main()
