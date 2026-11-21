"""Verify the antisymmetric fixed-fixed half-column through the public modal API.

The pinned guide is rigid in bending and flexible axially. It constrains
transverse midpoint translation without taking the column's dead compression.
The massless column has unit midpoint bending inertia in both planes.
This analytical supplement is not a native ISAE/ASWING comparison.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import resource
import shutil
import sys
import time
import traceback

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT/'scripts')]
from antisymmetric_column_reference import L, INERTIA, critical, stiffness, shapes

MODEL = ROOT/'examples/fixed-fixed-column-antisymmetric.asw'
RIGIDITIES = {0: 100., 2: 200.}
GATES = dict(pole=2e-6, shape=2e-7, residual=1e-9, backward=1e-8,
             balance=1e-7, straight=1e-8, mass=1e-12, preload=1e-10)


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False)+'\n')


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def run(args):
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=False)
    load = args.ratio*critical(count=args.intervals if args.grid_critical else None)
    paths = [*sorted((ROOT/'openswing').glob('*.py')), MODEL, Path(__file__),
        ROOT/'scripts/antisymmetric_column_reference.py', ROOT/'.reference/asw_theory.pdf',
        ROOT/'.reference/asw_uns_theory.pdf', ROOT/'.reference/aswing_doc.txt']
    pins = {str(p.relative_to(ROOT)): sha(p) for p in paths}
    source = MODEL.read_text().replace('0 0 0 1000 0 0 0', f'0 0 0 {args.guide_ea:.17g} 0 0 0')
    request = dict(action='modes', mode='modes', source=source, condition=None,
        panels=dict(default=args.intervals, beams={
            '1': dict(count=args.intervals, spacing='uniform'),
            '2': dict(count=4, spacing='uniform')}),
        numerics=dict(beam_interpolation='drela-segspl-v1', structural_operator='drela-fixed-vacuum-v1'),
        modes=dict(frame='fixed', vacuum=True, count=4, shift=[-.02, 0.], method=args.method,
            step=1e-5, rank_tolerance=1e-9, matrices=False,
            position=[0., 0., 0.], attitude=[-90., 0., 0.], gravity_magnitude=load))
    write(out/'request.json', request)
    write(out/'plan.json', dict(arguments=vars(args), source_pins=pins, gates=GATES,
        load=load, continuous_critical_load=critical(), discrete_critical_load=critical(count=args.intervals),
        native_ASWING_validation=False, scope=__doc__, expected_cold_solves=0 if args.saved_case else 1,
        expected_fresh_restores=1))
    started = time.monotonic()
    report = dict(status='RUNNING', native_ASWING_validation=False, goal_complete=False)
    try:
        import numpy as np
        from scipy.sparse import issparse, save_npz, csr_matrix, load_npz
        from scipy.sparse.linalg import norm as sparse_norm
        import openswing.linear_dynamics as dynamics
        from openswing.bridge import dispatch
        from openswing.asw import parse_asw
        from openswing.source_dynamics import SourceDynamicNetwork
        from openswing.equilibrium_state import warm_start_recipe, restore
        from openswing.network import network_snapshot
        original = dynamics.linearize
        captured = []

        def retain(system, *a, **kw):
            assert not captured
            aa, mm = original(system, *a, **kw)
            save_npz(out/'A.npz', aa if issparse(aa) else csr_matrix(aa))
            save_npz(out/'M.npz', mm if issparse(mm) else csr_matrix(mm))
            captured.append(True)
            return aa, mm

        print(f'BEGIN antisymmetric column n={args.intervals} P/Pcr={load/critical():.9g}', flush=True)
        tick = time.monotonic()
        if args.saved_case:
            saved_case = Path(args.saved_case)
            assert json.loads((saved_case/'request.json').read_text()) == request
            old_plan = json.loads((saved_case/'plan.json').read_text())
            for path, value in old_plan['source_pins'].items():
                actual = saved_case/'runner-at-failure.py' if path == str(Path(__file__).relative_to(ROOT)) else ROOT/path
                assert sha(actual) == value, actual
            replay_pins = {}
            for name in ('request.json', 'result.json', 'plan.json', 'runner-at-failure.py', 'A.npz', 'M.npz'):
                replay_pins[str(saved_case/name)] = sha(saved_case/name)
            write(out/'replay-pins.json', replay_pins)
            result = json.loads((saved_case/'result.json').read_text())
            for name in ('A.npz', 'M.npz'):
                shutil.copyfile(saved_case/name, out/name)
            report['saved_case'] = str(saved_case)
        else:
            dynamics.linearize = retain
            try:
                result = dispatch(request)
            finally:
                dynamics.linearize = original
        report['solve_seconds'] = time.monotonic()-tick
        write(out/'result.json', result)
        assert result['converged'] and result['base']['converged'] and len(result['modes']) == 4
        if args.method == 'dense':
            assert result['diagnostics']['finite_dimension'] == 4
        base = result['base']
        model = parse_asw(request['source'], beam_interpolation='drela-segspl-v1')
        saved = base['equilibrium_state']
        net = SourceDynamicNetwork(model, request['panels'], None, base['gravity_body'], [],
            mesh_recipe=warm_start_recipe(model, request['panels'], saved))
        state = restore(net, saved)
        assert net.nfev == 0
        zero = np.zeros_like(net.rj)
        residual, data = net.residual(state, detail=True, elastic_motion=(zero, zero, zero, zero),
            circulation_rate=np.zeros(net.circulation_basis.panels))
        assert net.nfev == 1
        fresh = network_snapshot(net, residual, data)
        write(out/'fresh-base.json', fresh)
        assert fresh['converged'] and net.nn == args.intervals+6 and net.ne == args.intervals+4
        main = net.beam_nodes[1]
        tip = main[-1]
        forces = data['source_discrete']['force_local']
        expected_force = np.zeros_like(forces)
        expected_force[net.beam_elements[1], 1] = -load
        checks = dict(residual=float(np.max(abs(residual))),
            balance=max(float(np.linalg.norm(fresh[k])) for k in ('force_balance', 'moment_balance')),
            straight=float(np.max(abs(data['r']-net.rj))),
            mass=abs(fresh['mass_properties']['mass']-1.),
            preload=float(np.max(abs(forces-expected_force)))/max(1., load),
            pole=0., shape=0., backward=0.)
        aa, mm = load_npz(out/'A.npz'), load_npz(out/'M.npz')
        norms = [(sparse_norm(a, np.inf), sparse_norm(m, np.inf)) for a, m in ((aa, mm), (aa.T, mm.T))]
        modes = []
        for mode in result['modes']:
            pole = complex(*mode['eigenvalue'])
            for side, (an, mn) in zip(('right', 'left'), norms):
                v = np.asarray(mode[side]['real'])+1j*np.asarray(mode[side]['imag'])
                diff = aa@v-pole*(mm@v) if side == 'right' else aa.T@v-pole.conjugate()*(mm.T@v)
                err = float(np.linalg.norm(diff, np.inf)/((an+abs(pole)*mn)*np.linalg.norm(v, np.inf)))
                checks['backward'] = max(checks['backward'], err)
            nodes = mode['output']['nodes']
            displacement = np.array([np.asarray(n['displacement']['real'])+1j*np.asarray(n['displacement']['imag']) for n in nodes])
            rotation = np.array([np.asarray(n['rotation']['real'])+1j*np.asarray(n['rotation']['imag']) for n in nodes])
            axis = int(np.argmax(abs(rotation[tip])))
            assert axis in RIGIDITIES
            scale = rotation[tip, axis]
            assert abs(scale) > 1e-15
            ei = RIGIDITIES[axis]
            k = stiffness(load, ei, args.intervals)
            target = complex(-k/INERTIA)**.5
            error = min(abs(pole-target), abs(pole+target))/max(1., abs(target))
            checks['pole'] = max(checks['pole'], error)
            w, theta = shapes(load, ei, args.intervals)
            expected_d = np.zeros((net.nn, 3))
            expected_r = np.zeros_like(expected_d)
            expected_r[main, axis] = theta
            expected_d[main, 2 if axis == 0 else 0] = w*(1 if axis == 0 else -1)
            shape_error = max(float(np.max(abs(displacement/scale-expected_d))),
                              float(np.max(abs(rotation/scale-expected_r))))
            checks['shape'] = max(checks['shape'], shape_error)
            continuous = abs(complex(-stiffness(load, ei)/INERTIA)**.5)
            modes.append(dict(rotation_axis=axis, eigenvalue=mode['eigenvalue'], stability=mode['stability'],
                continuum_magnitude=continuous, continuum_relative_error=abs(abs(pole)-continuous)/continuous,
                discrete_pole_error=error, discrete_shape_error=shape_error))
        assert sorted(m['rotation_axis'] for m in modes) == [0, 0, 2, 2]
        for axis in RIGIDITIES:
            poles = [complex(*m['eigenvalue']) for m in modes if m['rotation_axis'] == axis]
            assert abs(sum(poles)) <= GATES['pole']*max(1., abs(poles[0]))
        assert any(m['stability'] == 'unstable' for m in modes) == (load > critical(count=args.intervals))
        for name, value in checks.items():
            assert math.isfinite(value) and value <= GATES[name], (name, value, GATES[name])
        assert all(sha(ROOT/p) == value for p, value in pins.items())
        if args.saved_case:
            assert all(sha(p) == value for p, value in replay_pins.items())
        report.update(status='PASS_DISCRETE_ANALYTICAL_CHECK', checks=checks, modes=modes,
            independent_pencil_checks=8, shape_components=4*6*net.nn,
            source_pins_unchanged=True, finite_dimension=result['diagnostics'].get('finite_dimension'))
    except BaseException as error:
        report.update(status='FAILURE_RETAINED', error=repr(error), traceback=traceback.format_exc())
        raise
    finally:
        report.update(seconds=time.monotonic()-started,
            peak_RSS_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
        write(out/'report.json', report)
        print(json.dumps({k:v for k,v in report.items() if k not in ('traceback', 'modes')}), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output')
    parser.add_argument('--intervals', type=int, required=True)
    parser.add_argument('--ratio', type=float, required=True)
    parser.add_argument('--grid-critical', action='store_true')
    parser.add_argument('--guide-ea', type=float, default=1000.)
    parser.add_argument('--saved-case', help='Verify an already completed solve with a retained failed verifier.')
    parser.add_argument('--method', choices=('dense', 'full_shift_invert'), default='full_shift_invert')
    args = parser.parse_args()
    if args.intervals < 4 or not math.isfinite(args.ratio) or args.ratio < 0 or not math.isfinite(args.guide_ea) or args.guide_ea <= 0:
        parser.error('Need at least four intervals, nonnegative load ratio and positive guide EA.')
    run(args)
