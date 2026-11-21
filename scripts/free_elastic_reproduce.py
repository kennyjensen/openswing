"""Reproduce the independent/native free elastic wing-fin comparison.

Run from any working directory with the repository's NumPy/SciPy environment:
  python -I -B scripts/free_elastic_reproduce.py --mesh 16 --output new-results

The output directory must not exist. Mesh 16 is the accepted comparison mesh;
mesh 8 deliberately retains the same 1% limit and can fail it. Both use all
three fixture frequencies and both physical inputs. There is no automatic
refinement, retry, modal truncation, or aircraft parameter adjustment.

One invocation uses the current repository sources, records their hashes, and
checks them again before completion. It sets numerical thread counts to one.
Use an external process timeout for a wall-clock cap (300 seconds is the
declared reproduction budget); partial artifacts and failures are retained.
Importing this file performs no numerical work.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import time
import traceback


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = (
    'free_elastic_reproduce.py', 'free_elastic_reference.py',
    'free_elastic_mechanics.py', 'free_elastic_aero.py',
    'elastic_fin_aero.py', 'elastic_fin_kinematics.py', 'elastic_fin_io.py',
)
THREADS = ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS',
           'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS')


def pin(path):
    raw = Path(path).read_bytes()
    return dict(bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False)+'\n')


def source_pins():
    paths = [ROOT/'scripts'/name for name in SCRIPTS]
    paths += [ROOT/'tests'/name for name in
              ('free_elastic_adapter.py', 'free_elastic_comparison.py')]
    paths += [ROOT/'tests/data/free-elastic-coupling'/name
              for name in ('fixture.json', 'model.asw')]
    paths += sorted((ROOT/'openswing').glob('*.py'))
    return {str(p.relative_to(ROOT)): pin(p) for p in paths}


def run(mesh, output):
    """One declared calculation; original independent and native laws imported separately."""
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    for name in THREADS:
        os.environ[name] = '1'
    sys.path[:0] = [str(ROOT/'scripts'), str(ROOT/'tests'), str(ROOT)]
    fixture = json.loads((ROOT/'tests/data/free-elastic-coupling/fixture.json').read_text())
    frequencies = fixture['proposed_frequencies_Hz']
    if frequencies != [.1, 1., 1.15737773741517]:
        raise ValueError('The three declared fixture frequencies changed.')
    pins = source_pins()
    plan = dict(mesh=mesh, frequencies_Hz=frequencies,
        inputs=['+1 rad fin incidence (native control.3)', '+1 N m carrier yaw'],
        quadrature=32, complex_step=1e-24, mechanics_rtol=1e-11,
        native_derivative_step=1e-5, output_step=2.5e-6,
        native_base_limit=1e-9, native_residual_cap=5000,
        native_physical_balance_limit=2e-6, reference_physical_balance_limit=1e-7,
        agreement_relative_limit=.01, exact_zero_absolute_limit=1e-8,
        expected_agreement_checks=186, threads=1,
        recommended_external_timeout_seconds=300,
        source_root=str(ROOT), source_pins=pins,
        limitations=[
            'A combined elastic wing/fin/free-frame component, not a Daedalus or historical ASWING match.',
            'Q32 manufacture is held through reference derivatives and native correction.',
            'This replay uses the accepted Q32/1e-24 and tight mechanical tolerance; it does not repeat quadrature, width, or tolerance refinement.',
            'One selected mesh does not establish mesh convergence. Mesh 8 has the same 1% gate and may fail it.',
            'The affine tensioned base does not test finite-curvature preload or noncommuting loaded interpolation.',
        ])
    write(output/'plan.json', plan)
    operations = dict(manufacture_calls=0, completed_manufactures=0,
        derivative_calls=0, completed_derivative_evaluations=0,
        completed_derivative_fields=0, completed_derivative_field_sets=0,
        reference_harmonic_two_rhs_calls=0,
        native_network_residual_calls=0, native_base_corrections=0,
        native_pencils=0, native_input_matrix_calls=0,
        native_harmonic_two_rhs_calls=0, native_output_snapshots=0)
    checks, criteria, cases = [], [], []
    started = time.monotonic()
    error = None
    mechanics = None

    def progress(phase):
        write(output/'progress.json', dict(phase=phase, seconds=time.monotonic()-started,
              operations=operations, checks=checks, completed_frequencies=cases))
        print(phase, flush=True)

    def check(name, passed, **details):
        checks.append(dict(name=name, passed=bool(passed), **details))
        if not passed:
            raise ValueError('Reproduction gate failed: '+name)

    try:
        import numpy as np
        import scipy
        from scipy import sparse
        # The independent modules have no production imports. Complete their
        # work before importing the native driver and preserve that separation.
        import free_elastic_reference as reference
        from free_elastic_mechanics import FreeElasticMechanics
        from elastic_fin_io import save_tree
        independent_dir = output/'reference'
        independent_dir.mkdir()
        progress('independent Q32 manufacture')
        operations['manufacture_calls'] += 1
        manufacture = reference.manufacture(fixture, mesh)
        operations['completed_manufactures'] += 1
        save_tree(independent_dir/'manufacture', manufacture)
        # A completed manufacture contains one checked circulation solve and
        # one aero evaluation; its base-system field set is reused by evaluate.
        operations['completed_manufacture_circulation_solves'] = 1
        operations['completed_manufacture_aero_evaluations'] = 1
        progress('independent Q32 derivatives at 1e-24')
        operations['derivative_calls'] += 1
        derivative = reference.derivative_model(fixture, mesh, manufacture, 32, 1e-24)
        operations.update(completed_derivative_evaluations=derivative['evaluations'],
            completed_derivative_fields=derivative['fields'],
            completed_derivative_field_sets=derivative['field_sets'])
        save_tree(independent_dir/'derivative', derivative)
        check('declared derivative evaluation count', derivative['evaluations'] == 40*mesh+47)
        check('finite independent derivative blocks', all(np.isfinite(value).all()
              for block in derivative['blocks'].values() for value in block.values()))
        mechanics = FreeElasticMechanics(fixture, rtol=1e-11)
        invariants = mechanics.static_invariants()
        save_tree(independent_dir/'mechanical-invariants', invariants)
        for branch, data in invariants['branches'].items():
            for key in ('static_translation_residual', 'static_rigid_rotation_residual',
                        'section_kinetic_gram_difference'):
                check(branch+' '+key, np.max(abs(data[key])) <= 1e-11)
        check('preload carrier balance', np.max(abs(invariants['base_rigid_load_balance'])) <= 1e-11)
        check('positive rigid real mass', np.min(np.linalg.eigvalsh(invariants['rigid_real_mass'])) > 0)
        expected = []
        for index, frequency in enumerate(frequencies):
            progress('independent Green and coupled response '+str(frequency)+' Hz')
            case_dir = independent_dir/('frequency-'+str(index))
            case_dir.mkdir()
            green = mechanics.green(frequency, mesh, manufacture['body_fixed_nodal_loads'],
                                    manufacture['carrier_balancer'])
            # Preserve nested segment transfer/initial/after maps, LU, boundary
            # arrays and physical recovery. Top-level-only NPZ would lose them.
            save_tree(case_dir/'green', green)
            check('mechanical numerical gates '+str(index), green['diagnostics']['available'])
            for field in ('positions', 'material_frames', 'endpoints', 'fractions'):
                actual, target = green['base'][field], manufacture['geometry'][field]
                check('reference geometry '+str(index)+' '+field,
                      np.all(abs(actual-target) <= 2e-11+2e-11*abs(target)))
            balance = float(np.max(abs(green['physical_global_balance'])))
            check('reference global Green balance '+str(index), balance <= 1e-7, maximum=balance)
            operations['reference_harmonic_two_rhs_calls'] += 1
            response = reference.harmonic(fixture, green, derivative, frequency)
            save_tree(case_dir/'response', response)
            expected.append(response['outputs'])
        check('independent phase has no production imports',
              not any(name == 'openswing' or name.startswith('openswing.') for name in sys.modules))

        import free_elastic_adapter as adapter
        from free_elastic_comparison import errors
        from openswing.linear_dynamics import linearize, state_layout
        from openswing.frequency_response import harmonic_solve
        native_dir = output/'native'
        native_dir.mkdir()

        def observe():
            operations['native_network_residual_calls'] += 1
            if operations['native_network_residual_calls'] > plan['native_residual_cap']:
                raise RuntimeError('Native residual cap exceeded')

        progress('native manufactured base and one reused pencil')
        prepared = adapter.build_network(fixture, mesh, manufacture['counterloads'],
                                         residual_observer=observe)
        network = prepared['network']
        seed, packet, geometry = adapter.seed_packet(prepared, manufacture['gamma'])
        save_tree(native_dir/'seed', dict(raw=seed, packet=packet, geometry=geometry))
        check('no native residual before geometry proof', operations['native_network_residual_calls'] == 0)
        for key in ('a', 'b', 'hv', 'cp'):
            a, b = geometry['lifting_geometry'][key], manufacture['response']['geometry'][key]
            check('independent native geometry '+key, np.all(abs(a-b) <= 2e-11+2e-11*abs(b)))
        residual = network.residual(seed)
        np.save(native_dir/'seed-residual.npy', residual)
        check('native manufactured seed residual', np.max(abs(residual)) <= 1e-9,
              maximum=float(np.max(abs(residual))))
        operations['native_base_corrections'] += 1
        system, base, base_report = adapter.correct_base(prepared, packet, tolerance=1e-9)
        save_tree(native_dir/'base', dict(state=base, report=base_report))
        zero = np.zeros(system.size)
        residual = system.residual(zero, zero)
        np.save(native_dir/'dynamic-base-residual.npy', residual)
        check('native dynamic base residual', np.max(abs(residual)) <= 1e-9,
              maximum=float(np.max(abs(residual))))
        operations['native_pencils'] += 1
        A, M = linearize(system, step=1e-5, sparse=True)
        sparse.save_npz(native_dir/'A.npz', A)
        sparse.save_npz(native_dir/'M.npz', M)
        operations['native_input_matrix_calls'] += 1
        B, forcings, metadata = adapter.input_rhs(system, step=1e-5)
        np.save(native_dir/'B.npy', B)
        write(native_dir/'state-layout.json', state_layout(system))
        write(native_dir/'inputs.json', metadata)
        for index, frequency in enumerate(frequencies):
            progress('native reused-pencil response '+str(frequency)+' Hz')
            case_dir = native_dir/('frequency-'+str(index))
            case_dir.mkdir()
            omega = 2*np.pi*frequency
            operations['native_harmonic_two_rhs_calls'] += 1
            state, diagnostics = harmonic_solve(A, M, B, omega)
            np.save(case_dir/'state.npy', state)
            write(case_dir/'harmonic-diagnostics.json', diagnostics)

            def record(label, raw):
                operations['native_output_snapshots'] += 1
                save_tree(case_dir/label, raw)

            actual, output_report = adapter.directional_outputs(system, state, omega,
                forcings, metadata, step=2.5e-6, include_baseline=index == 0, recorder=record)
            save_tree(case_dir/'output-stencil', dict(outputs=actual, report=output_report))
            balance = float(np.max(abs(actual['physical_global_balance_body'])))
            check('native physical balance '+str(index), balance <= 2e-6, maximum=balance)
            selected = adapter.selected_outputs(system, state, omega)
            save_tree(case_dir/'selected', selected)
            actual.update(selected)
            rows = errors(actual, expected[index], mesh, fixture['normalization']['motion_length'])
            for row in rows:
                row.update(frequency_Hz=frequency, passed=bool(
                    row['absolute'] <= 1e-8 if row['relative'] is None else row['relative'] <= .01))
            criteria.extend(rows)
            write(case_dir/'comparison.json', rows)
            cases.append(dict(frequency_Hz=frequency, harmonic=diagnostics,
                agreement_passed=sum(row['passed'] for row in rows), agreement_total=len(rows),
                maximum_relative=max(row['relative'] for row in rows if row['relative'] is not None),
                physical_balance=balance))
        check('one base pencil and input matrix reused', operations['native_base_corrections'] == 1
              and operations['native_pencils'] == 1 and operations['native_input_matrix_calls'] == 1)
        check('three native and independent two-RHS solves', operations['native_harmonic_two_rhs_calls'] == 3
              and operations['reference_harmonic_two_rhs_calls'] == 3)
        check('49 saved native output snapshots', operations['native_output_snapshots'] == 49)
        check('three mechanical Green boundary solves', mechanics.operations['green_calls'] == 3
              and mechanics.operations['boundary_factorizations'] == 3
              and mechanics.operations['boundary_solves'] == 3)
        check('186 complete complex agreement criteria', len(criteria) == 186)
        write(output/'comparison.json', criteria)  # Retain every failure before gating.
        check('all current source and fixture pins unchanged', source_pins() == pins)
        check('all physical groups satisfy the fixed 1% criterion', all(row['passed'] for row in criteria))
    except BaseException as exc:
        error = dict(type=type(exc).__name__, message=str(exc), traceback=traceback.format_exc())
        if hasattr(exc, 'saved_segment'):
            save_tree(output/'failed-reference-segment', exc.saved_segment)
    finally:
        if mechanics is not None:
            operations['independent_mechanics'] = mechanics.operations.copy()
        report = dict(status='PASS' if error is None else 'FAILURE_RETAINED', error=error,
            mesh=mesh, frequencies_Hz=frequencies, operations=operations, cases=cases,
            checks=dict(passed=sum(row['passed'] for row in checks), total=len(checks), items=checks),
            agreement_checks=dict(passed=sum(row['passed'] for row in criteria), total=len(criteria)),
            seconds=time.monotonic()-started, source_pins=pins, plan_pin=pin(output/'plan.json'),
            production_changed=False, daedalus_match=False,
            counts_note='Started high-level calls and completed returned reference counters are separate; a failed unreturned derivative call has unknown internal work.',
            limitations=plan['limitations'])
        write(output/'report.json', report)
        print(json.dumps({key: report[key] for key in ('status', 'mesh', 'agreement_checks', 'seconds')}), flush=True)
    return 0 if error is None else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mesh', type=int, choices=(8, 16), default=16)
    parser.add_argument('--output', required=True, help='New directory; existing outputs are never overwritten.')
    args = parser.parse_args()
    return run(args.mesh, args.output)


if __name__ == '__main__':
    raise SystemExit(main())
