"""Small synthetic warm-start witnesses shared by native Python and Pyodide.

The command verifies the chosen packaged kernel against native sources before
writing its protocol and evaluating either synthetic wing. Importing this file
does not run a solve. It never reads archived aircraft inputs.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import sys
import time
import traceback


CASES = [dict(id='pointwise', modes=0), dict(id='fourier4', modes=4)]
SETTINGS = dict(panels=12, speed=27., mach=.15, seed_alpha=14., target_alpha=18.)
RESIDUAL_GATE = 1e-8
PARITY_GATE = 1e-9


def save(path, value):
    with path.open('x') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')


def pin(root, path):
    raw = path.read_bytes()
    return dict(path=str(path.relative_to(root)), bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())


def verify_pins(root, pins):
    for expected in pins:
        assert pin(root, root/expected['path']) == expected, expected['path']


def comparison_fields(result):
    """Physical data only; iteration counts may differ between BLAS runtimes."""
    fields = {name: result[name] for name in (
        'CL', 'CY', 'CD', 'CDi', 'CDi_near', 'CDp', 'Cl', 'Cm', 'Cn', 'efficiency',
        'force', 'moment', 'surface_force', 'distributed_aero_force', 'distributed_aero_moment',
        'residual', 'circulation_residual', 'circulation_local_residual')}
    fields['circulation_coefficients'] = result['circulation_discretization']['coefficients']
    fields['strips'] = [{name: row[name] for name in (
        'beam', 't', 'length', 'position', 'circulation', 'cl', 'force', 'moment',
        'velocity_position', 'relative_velocity', 'normal_speed', 'normal_mach', 'cm', 'f_aero')}
        for row in result['strips'] if row.get('lifting')]
    return fields


def run_case(spec, source):
    import numpy as np
    from openswing.aero import FlightCondition, evaluate_aerodynamics, solve_rigid
    from openswing.asw import parse_asw
    from openswing.geometry import model_meshes

    started = time.monotonic()
    result = dict(id=spec['id'], modes=spec['modes'], status='error', checks=[])
    try:
        assert spec in CASES
        model = parse_asw(source)
        condition = FlightCondition(speed=SETTINGS['speed'], alpha=SETTINGS['seed_alpha'],
            mach=SETTINGS['mach'], circulation_modes={1: spec['modes']})
        base = solve_rigid(model, condition, SETTINGS['panels'])
        result['base'] = base
        seed = np.array([row['circulation'] for row in base['strips'] if row.get('lifting')])
        original = seed.copy()
        seed.setflags(write=False)
        condition.alpha = SETTINGS['target_alpha']
        warm = solve_rigid(model, condition, SETTINGS['panels'], initial_circulation=seed)
        result['warm'] = warm
        gamma = np.array([row['circulation'] for row in warm['strips'] if row.get('lifting')])
        replay = evaluate_aerodynamics(model, condition, model_meshes(model, SETTINGS['panels']),
                                       circulation=gamma)
        result['prescribed_replay'] = replay
        initialization = warm['circulation_solver']['initialization']
        attempt = initialization['seed_attempt']
        checks = [dict(name='seed_is_immutable', passed=bool(np.array_equal(seed, original))),
            dict(name='seeded_direct_accepted', passed=warm['circulation_solver']['method'] == 'direct'
                 and bool(attempt['accepted']) and not initialization['cold_fallback']),
            dict(name='analytic_seed_jacobian', passed=attempt['derivative'] == 'analytic'),
            dict(name='seed_was_corrected', passed=bool(np.max(abs(gamma-original)) > 1e-3)),
            dict(name='seed_metadata_matches_input', passed=bool(np.array_equal(initialization['initial_circulation'], original))),
            dict(name='prescription_is_unsolved', passed=replay['circulation_solver'] == dict(method='prescribed', evaluations=0))]
        for label, value in (('base', base), ('warm', warm), ('prescribed_replay', replay)):
            checks.append(dict(name=label+'_residual', value=value['residual'], tolerance=RESIDUAL_GATE,
                passed=bool(np.isfinite(value['residual']) and value['residual'] <= RESIDUAL_GATE)))
            maximum = value['lifting_airflow']['maximum']['normal_mach']
            checks.append(dict(name=label+'_subsonic', value=maximum, tolerance=1.,
                passed=bool(np.isfinite(maximum) and maximum < 1.)))
        for name in ('force', 'moment', 'circulation_residual', 'circulation_local_residual'):
            a, b = np.asarray(warm[name]), np.asarray(replay[name])
            error = float(np.max(abs(a-b)/np.maximum(1., abs(b)), initial=0.))
            checks.append(dict(name='fresh_replay_'+name, value=error, tolerance=1e-12,
                passed=bool(np.isfinite(error) and error <= 1e-12)))
        result.update(seed_input=original.tolist(), seed_after=seed.tolist(), endpoint_circulation=gamma.tolist(),
            comparison_fields={name: comparison_fields(value) for name, value in
                (('base', base), ('warm', warm), ('prescribed_replay', replay))}, checks=checks)
        assert all(check['passed'] for check in checks), [check for check in checks if not check['passed']]
        result['status'] = 'computed'
    except Exception as exc:
        result.update(error_type=type(exc).__name__, error=str(exc), traceback=traceback.format_exc())
    result['seconds'] = time.monotonic()-started
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', default='artifacts/isae/sa4-operating-sequence-20261029/wasm')
    parser.add_argument('--kernel-dir', default='dist/kernel')
    parser.add_argument('--runtime-dir', default='dist/runtime')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    os.chdir(root)
    sys.path.insert(0, str(root))
    output = root/args.output_dir
    output.mkdir(parents=True, exist_ok=True)
    kernel, runtime = root/args.kernel_dir, root/args.runtime_dir
    names = json.loads((kernel/'manifest.json').read_text())
    native_names = sorted(p.name for p in (root/'openswing').glob('*.py'))
    assert sorted(names) == native_names and len(set(names)) == len(names), 'Module inventory mismatch'
    for name in names:
        assert Path(name).name == name and name.endswith('.py')
        assert (kernel/name).read_bytes() == (root/'openswing'/name).read_bytes(), 'Stale packaged module: '+name
    source_paths = [root/'scripts/test-rigid-circulation-initialization-native.py',
        root/'scripts/test-rigid-circulation-initialization-wasm.mjs', root/'examples/stall-branch.asw',
        kernel/'manifest.json']
    source_paths += [root/'openswing'/name for name in native_names]
    source_paths += [kernel/name for name in native_names]
    source_paths += sorted(path for path in runtime.iterdir() if path.is_file())
    protocol = dict(schema='rigid-circulation-initialization-wasm-v1', cases=CASES, settings=SETTINGS,
        residual_gate=RESIDUAL_GATE, scaled_native_parity_gate=PARITY_GATE,
        kernel_dir=args.kernel_dir, runtime_dir=args.runtime_dir, module_names=native_names,
        source_pins=[pin(root, path) for path in source_paths],
        qualification='Packaged kernel modules must equal native modules. Synthetic warm solves only; no historical startup or archived aircraft claim.',
        operations_per_runtime=dict(cold_synthetic_solves=2, seeded_synthetic_solves=2,
                                    prescribed_residual_replays=2, archived_aircraft_solves=0))
    save(output/'protocol.json', protocol)
    report = dict(schema='rigid-circulation-initialization-native-v1', cases=[], passed=False,
        protocol=pin(root, output/'protocol.json'), python=platform.python_version())
    started = time.monotonic()
    try:
        verify_pins(root, protocol['source_pins'])
        source = (root/'examples/stall-branch.asw').read_text()
        for case in CASES:
            actual = run_case(case, source)
            case_path = output/(case['id']+'-native.json')
            save(case_path, actual)
            row = dict(id=case['id'], status=actual['status'], seconds=actual['seconds'],
                output=pin(root, case_path), passed=actual['status'] == 'computed' and all(c['passed'] for c in actual['checks']))
            report['cases'].append(row)
            print(json.dumps(row), flush=True)
        verify_pins(root, protocol['source_pins'])
        report.update(sources_unchanged=True, passed=len(report['cases']) == 2 and all(c['passed'] for c in report['cases']))
    except Exception as exc:
        report.update(error_type=type(exc).__name__, error=str(exc), traceback=traceback.format_exc())
    report['seconds'] = time.monotonic()-started
    save(output/'native-report.json', report)
    print(json.dumps(dict(passed=report['passed'], seconds=report['seconds'])), flush=True)
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    sys.exit(main())
