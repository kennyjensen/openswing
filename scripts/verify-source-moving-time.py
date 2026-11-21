#!/usr/bin/env python3
"""One rigid prescribed-frame source Euler-BDF trajectory and one restart.

Synthetic kinematics/inertia and native/browser parity evidence only; not an
archived ASWING time-history match. No retry, fitting or additional solve.
Usage: .venv/bin/python scripts/verify-source-moving-time.py NEW_OUTPUT_DIR
"""
import hashlib
import json
import math
from pathlib import Path
import signal
import sys
import time
import traceback


ROOT = Path(__file__).resolve().parents[1]
POLICY = {'beam_interpolation': 'drela-segspl-v1', 'structural_operator': 'drela-moving-vacuum-v1'}
SCHEME = 'drela-euler-bdf-v1'


def pin(path):
    value = path.read_bytes()
    return {'path': str(path), 'bytes': len(value), 'sha256': hashlib.sha256(value).hexdigest()}


def main():
    if len(sys.argv) != 2:
        raise SystemExit('Supply one new output directory.')
    out = Path(sys.argv[1]).resolve()
    out.mkdir(exist_ok=False)
    write = lambda name, value: (out/name).write_text(json.dumps(value, indent=2, allow_nan=False)+'\n')
    began = time.monotonic()
    report = {'status': 'PREPARING', 'checks': [], 'planned_cold_calls': 1, 'planned_resume_calls': 1,
              'actual_cold_calls': 0, 'actual_resume_calls': 0, 'timeout_seconds': 120,
              'scope': 'Synthetic rigid prescribed-frame Euler-BDF motion; not archived ASWING agreement.'}
    def check(name, value, **details):
        report['checks'].append({'name': name, 'passed': bool(value), **details})
        if not value:
            raise AssertionError(name)
    def alarm(*_):
        raise TimeoutError('Bounded native time verification exceeded 120 seconds; no retry.')
    signal.signal(signal.SIGALRM, alarm)
    signal.setitimer(signal.ITIMER_REAL, 120.)
    inputs, events = [], []
    try:
        original = ROOT/'examples/source-moving-vacuum-check.asw'
        text = original.read_text()
        replacements = [('1 200 0 0 0 0 0', '1 0 0 0 0 0 0'), ('3 200 0 0 0 0 0', '3 0 0 0 0 0 0')]
        for before, after in replacements:
            check('unique literal EA row '+before, text.splitlines().count(before) == 1)
            text = text.replace(before+'\n', after+'\n')
        # Preserve original bytes apart from the two explicitly declared EA
        # entries. Its leading oscillator comments describe the parent model.
        source = out/'rigid-source.asw'
        source.write_text(text)
        request = dict(action='time', mode='time', source=text, condition=None,
            panels={'default': 4, 'beams': {'1': {'count': 4, 'spacing': 'uniform'}}}, numerics=POLICY,
            time=dict(duration=.08, dt=.02, order=2, frame='prescribed', forcing='', accuracy=None,
                position=[1., 2., 3.], attitude=[11., -7., 179.], velocity=[7., -2., .5], gravity_magnitude=0.,
                motion=dict(rates=[.2, -.15, -.5], acceleration=[.3, -.2, .1], angular_acceleration=[.4, .3, -.2])))
        write('request.json', request)
        modules = sorted((ROOT/'openswing').glob('*.py'))
        pins = {p.name: pin(p)['sha256'] for p in modules}
        inputs = [pin(original), pin(source), pin(Path(__file__).resolve()), pin(out/'request.json'), *[pin(p) for p in modules]]
        plan = dict(kernel_pins=pins, source_file=str(source), source_sha256=pin(source)['sha256'],
            parent_source=pin(original), declared_source_changes=replacements, source_pins=inputs,
            planned_cold_calls=1, planned_resume_calls=1, no_retries=True, timeout_seconds=120,
            full_residual_gate=1e-8, balance_relative_gate=1e-7, numerical_parity={'absolute': 2e-8, 'relative': 2e-8},
            expected_structural_nodes=5, expected_structural_elements=4, temporal_scheme=SCHEME,
            continuation_options=dict(duration=.02, dt=.02, order=2, accuracy=None),
            scope=report['scope'], browser_case=dict(project_name='Source Euler-BDF moving-frame check',
                case_name='Rigid prescribed frame, mixed-axis motion, Euler heading crossing',
                solution_name='Rigid moving-frame trajectory', plot_quantity='frame.attitude.2',
                solve_timeout_ms=120000, total_timeout_ms=300000))
        write('plan.json', plan)
        sys.path.insert(0, str(ROOT))
        import numpy as np
        from openswing.bridge import dispatch
        from openswing.time_state import checkpoint
        from openswing import bridge
        check('native import is current checkout', Path(bridge.__file__).resolve() == ROOT/'openswing/bridge.py')
        report['import_path'] = str(Path(bridge.__file__).resolve())
        def progress(*values):
            events.append(list(values))
        def inspect(result, label):
            check(label+' converged time result', result['analysis'] == 'time_response' and result['converged'])
            check(label+' numerical identity', result['numerics'] == POLICY)
            context = result['restart_context']
            check(label+' moving operator identity', context['identity']['structural_operator'] == POLICY['structural_operator'])
            check(label+' no airflow or controller', context['setup']['condition'] is None and result['controller'] is None)
            rows = result['snapshots']
            check(label+' nonempty time history', len(rows) >= 2)
            scales = rows[-1]['restart']['accepted_method']['layout']['scales']
            V, W = scales['velocity'], scales['rate']
            for i, row in enumerate(rows):
                prefix = f'{label} snapshot {i}'
                check(prefix+' residual', math.isfinite(row['residual']) and row['residual'] <= 1e-8, residual=row['residual'])
                check(prefix+' node and interval counts', len(row['nodes']) == 5 and row['structural_elements'] == 4)
                stored = row['restart']['state']
                check(prefix+' material Euler history', np.asarray(stored['source_angles']).shape == (5, 3))
                check(prefix+' aircraft Euler history', np.asarray(stored['source_attitude']).shape == (3,))
                check(prefix+' lifted display', np.max(abs(np.deg2rad(row['frame']['attitude'])-stored['source_attitude'])) <= 2e-12)
                check(prefix+' rigid local velocities', np.max(abs(np.asarray(row['local_velocity']))) <= V*1e-8)
                check(prefix+' rigid local rates', np.max(abs(np.asarray(row['local_rates']))) <= W*1e-8)
                omega = np.array(request['time']['motion']['rates'])+row['time']*np.array(request['time']['motion']['angular_acceleration'])
                check(prefix+' independently linear prescribed angular velocity', np.max(abs(np.array(row['frame']['rates_body'])-omega)) <= 2e-8)
                for key in ('force_balance', 'moment_balance'):
                    scale = max(1., np.linalg.norm(row['support_force' if key == 'force_balance' else 'support_moment']))
                    check(prefix+' '+key, np.linalg.norm(row[key]) <= 1e-7*scale)
                accepted = row['restart']['accepted_method']
                if accepted['kind'] != 'bdf':
                    continue
                check(prefix+' exact temporal policy', accepted['scheme'] == SCHEME)
                current = np.asarray(stored['source_attitude'])
                before = np.asarray(accepted['previous']['source_attitude'])
                older = accepted['previous2']
                k = np.asarray(accepted['coefficients'])
                derivative = k[0]*(current-before)+(0 if older is None else k[2]*(np.asarray(older['source_attitude'])-before))
                phi, theta, _ = current
                # Independently evaluate the printed Eq12 forward map.
                E = np.array([[-1., 0., np.sin(theta)],
                    [0., np.cos(phi), np.sin(phi)*np.cos(theta)],
                    [0., np.sin(phi), -np.cos(phi)*np.cos(theta)]])
                defect = np.linalg.solve(E, np.asarray(row['frame']['rates_body']))-derivative
                check(prefix+' independent Euler-BDF row', np.max(abs(defect))/W <= 1e-8,
                      normalized_error=float(np.max(abs(defect))/W))
            return len(rows)
        check('all pins exact before cold call', all(pin(Path(p['path']))['sha256'] == p['sha256'] for p in inputs))
        report['actual_cold_calls'] += 1
        begin = time.monotonic()
        result = dispatch(request, progress=progress)
        report['cold_seconds'] = time.monotonic()-begin
        write('result.json', result)
        report['cold_snapshots'] = inspect(result, 'cold')
        report['cold_residual_evaluations'] = result['evaluations']
        check('cold final time', abs(result['end_time']-.08) <= 1e-14)
        check('heading lift crosses 180 degrees', result['snapshots'][-1]['frame']['attitude'][2] > 180.)
        saved = checkpoint(result)
        write('checkpoint.json', saved)
        continuation = dict(action='resume_time', source=text, numerics=POLICY,
                            checkpoint=saved, time=plan['continuation_options'])
        write('resume-request.json', continuation)
        report['actual_resume_calls'] += 1
        begin = time.monotonic()
        resumed = dispatch(continuation, progress=progress)
        report['resume_seconds'] = time.monotonic()-begin
        write('resumed-result.json', resumed)
        report['resume_snapshots'] = inspect(resumed, 'resume')
        report['resume_residual_evaluations'] = resumed['evaluations']
        check('resumed interval', abs(resumed['start_time']-.08) <= 1e-14 and abs(resumed['end_time']-.1) <= 1e-14)
        check('resumed BDF2 retained predecessor', resumed['snapshots'][1]['order'] == 2)
        write('events.json', events)
        check('all pins unchanged after both calls', all(pin(Path(p['path']))['sha256'] == p['sha256'] for p in inputs))
        report['kernel_pins'] = pins
        report['status'] = 'PASS_NATIVE_SOURCE_MOVING_TIME'
    except BaseException as error:
        report['status'] = 'FAILURE_RETAINED'
        report['error'] = {'type': type(error).__name__, 'message': str(error), 'traceback': traceback.format_exc()}
        print(report['error']['traceback'], file=sys.stderr)
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0.)
        report['seconds'] = time.monotonic()-began
        write('events.json', events)
        report['check_counts'] = {'passed': sum(c['passed'] for c in report['checks']), 'total': len(report['checks'])}
        if inputs:
            report['final_pin_changes'] = [p['path'] for p in inputs if not Path(p['path']).exists() or pin(Path(p['path']))['sha256'] != p['sha256']]
            if report['final_pin_changes']:
                report['status'] = 'FAILURE_RETAINED'
        write('report.json', report)
        print(json.dumps({k: v for k, v in report.items() if k not in ('checks', 'kernel_pins', 'error')}, allow_nan=False), flush=True)
    return 0 if report['status'].startswith('PASS') else 1


if __name__ == '__main__':
    raise SystemExit(main())
