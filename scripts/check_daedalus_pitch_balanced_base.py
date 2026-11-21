"""Isolate pitch balance in the conditional zero-incidence Daedalus case.

Exchange just one operating constraint: prescribe zero mean pitch acceleration
and solve F2 from zero net pitch moment. All other settings of the previous
zero-incidence accelerating case remain fixed. Rebuild the full dynamic model
with all six perturbation accelerations free. This is not native setup recovery.
"""
import argparse
from dataclasses import asdict, replace
from pathlib import Path

from check_daedalus_load_sensitivity import ROOT, read, write
from daedalus_bounded_job import run
import check_daedalus_untrimmed_base as previous

STUDY = ROOT/'artifacts/daedalus-pitch-balanced-base-20261114'
BASE = previous.STUDY/'equilibrium-1/state.json'
QUALIFICATION = ('Conditional pitch-balanced zero-incidence snapshot, still '
                 'accelerating in other axes. F2 is solved from pitch balance, '
                 'not fitted to the Bode drawing. Native settings remain unknown.')


def initialize(folder, args):
    from openswing.equilibrium_state import restore_physical_fields
    from openswing.operating import time_load_constraints
    from openswing.time_state import read_condition, condition_data
    packet = read(BASE)
    assert packet['residual'] <= 1e-9
    condition = read_condition(packet['launch']['condition'])
    acceleration = list(condition.angular_acceleration)
    acceleration[1] = 0.
    condition = replace(condition, angular_acceleration=acceleration)
    constraints = [replace(c, variable='control.2')
        if c.variable == 'angular_acceleration.y' else c
        for c in time_load_constraints('free')]
    launch = dict(packet['launch'], condition=condition_data(condition),
        released_constraints=[asdict(c) for c in constraints])
    n = previous.regular.network(dict(packet, launch=launch))
    x = restore_physical_fields(n, packet)
    result = previous.regular.source.save_state(folder, n, x,
        qualification=QUALIFICATION, initial_guess_only=True)
    assert not result['accepted']
    return result


def audit(folder, args):
    import numpy as np
    n, x = previous.regular.setup(args.seed)
    residual = n.residual(x)
    assert max(abs(residual)) <= 1e-9
    condition, motion, _ = n.operating.apply(x[n.operating_start:])
    assert condition.alpha == condition.beta == 0.
    np.testing.assert_array_equal(condition.attitude, [0., 0., 0.])
    assert condition.controls[3] == 0. and all(v == 0. for v in condition.powers.values())
    assert np.linalg.norm(motion.rates) == 0. and motion.angular_acceleration[1] == 0.
    system = previous.regular.previous.dynamic(args)
    zero = np.zeros(system.size)
    error = float(max(abs(system.residual(zero, zero))))
    assert error <= 1e-9
    assert [c.variable for c in system.network.operating.constraints] == [
        'acceleration.x', 'acceleration.y', 'acceleration.z',
        'angular_acceleration.x', 'angular_acceleration.y', 'angular_acceleration.z']
    report = system.base_report()
    assert not report['modal_base']['kinematically_steady']
    write(folder/'base-report.json', report)
    shape = []
    for seed, name in [(previous.response_study.SEED, 'level-flight'),
                       (BASE, 'zero-controls'), (args.seed, 'pitch-balanced')]:
        network, state = previous.regular.setup(seed)
        _, ids = network.station_nodes[1]
        displacement = network.unpack(state)[0][ids] - network.rj[ids]
        shape.append(dict(case=name,
            wing_z_range_ft=[float(min(displacement[:, 2])), float(max(displacement[:, 2]))],
            wing_tip_displacement_ft=displacement[[0, -1]].tolist()))
    return dict(qualification=QUALIFICATION, residual_max=float(max(abs(residual))),
        dynamic_residual=error, dynamic_states=system.size, controls=condition.controls,
        acceleration_ft_s2=motion.acceleration.tolist(),
        angular_acceleration_rad_s2=motion.angular_acceleration.tolist(),
        shape_comparison=shape, dynamic_pitch_acceleration_free=True)


def execute(folder, arguments):
    previous.STUDY = STUDY
    previous.QUALIFICATION = QUALIFICATION
    previous.initialize = initialize
    previous.audit = audit
    return previous.execute(folder, arguments)


if __name__ == '__main__':
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
    pinned = previous.response_study.inputs() + [BASE, ROOT/'reference/aswing_doc.txt',
        ROOT/'scripts/check_daedalus_regular_mesh_response.py',
        ROOT/'scripts/check_daedalus_untrimmed_base.py']
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
