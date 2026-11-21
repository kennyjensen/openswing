#!/usr/bin/env python3
"""One declared original ST-4 source-vacuum modal comparison.

Usage: verify-isae-st4-source-modes.py NEW_OUTPUT_DIR {16,32,64}
The caller owns the process deadline. There is one cold bridge call, no retry,
no settings search and no experiment-derived input. Historical setup remains
qualified even when every numerical check passes.
"""
import argparse
from decimal import Decimal
import hashlib
import json
import math
from pathlib import Path
import sys
import time
import traceback

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT/'.reference/isae-validation/f62943df20e9e4d7d9f50e070477b22426b5f865/3 - Structure/CASE - ST4 Concentrated weight/Simulation_files/Weight7a'
SOURCE = ROOT/'examples/isae-st4-7a-b17.asw'
ORIGINAL_HASHES = {
    '7a_b17.asw': 'a2608f3c8554991f8f491bd0d2beb077ea3af43dfe4d48098dee3bed6d1a2fd3',
    'Flutter_analysis.sh': '569443e835443bc91c144f1bb6c6d73b025f0f4a5b0ebb69a0c5b7a05c3e1e87',
    'vaccum.txt': 'fa9c047b103bc9519650c1142bb5765e5f7b73461928b58ad11f01f39afa61ac',
}
POLICY = dict(beam_interpolation='drela-segspl-v1', structural_operator='drela-fixed-vacuum-v1')
SPECTRUM_SCOPE = 'Complete numerically reduced finite spectrum, including deflated zero roots.'
BASE_GATE = 1e-9
PENCIL_GATE = 1e-8
ROOT_ABSOLUTE_GATE = 2e-8
ROOT_RELATIVE_GATE = 2e-8
NEUTRAL_RELATIVE_GATE = 1e-8
MESH_RELATIVE_GATE = .001


def pin(path):
    data = path.read_bytes()
    return dict(path=str(path.resolve()), bytes=len(data), sha256=hashlib.sha256(data).hexdigest())


def write(output, name, value):
    temporary = output/(name+'.tmp')
    temporary.write_text(json.dumps(value, indent=2, allow_nan=False)+'\n')
    temporary.replace(output/name)


def targets():
    rows = []
    for line_number, line in enumerate((ARCHIVE/'vaccum.txt').read_text().splitlines(), 1):
        if not line.strip() or line.lstrip().startswith('#'):
            continue
        tokens = line.split()
        if len(tokens) != 3 or tokens[0] != '1':
            raise ValueError('Unexpected original modal reference row.')
        values = [Decimal(token) for token in tokens[1:]]
        halves = [Decimal(5)*Decimal(10)**(value.as_tuple().exponent-1) for value in values]
        rows.append(dict(line=line_number, raw_tokens=tokens, operating_point=1,
            eigenvalue=[float(value) for value in values], frequency_Hz=float(values[1])/(2*math.pi),
            half_printed_units=[float(value) for value in halves],
            exact_decimal_values=[str(value) for value in values],
            exact_decimal_half_units=[str(value) for value in halves]))
    if len(rows) != 6 or any(row['eigenvalue'][1] <= 0 for row in rows):
        raise ValueError('Expected six original positive-imaginary reference roots.')
    if any(a['eigenvalue'][1] >= b['eigenvalue'][1] for a, b in zip(rows, rows[1:])):
        raise ValueError('Preserve original ascending reference order; do not silently sort the target.')
    return rows


def prepare(output, count):
    inputs = [pin(ARCHIVE/name) for name in ORIGINAL_HASHES]
    for entry in inputs:
        if entry['sha256'] != ORIGINAL_HASHES[Path(entry['path']).name]:
            raise ValueError('Original reference pin changed: '+entry['path'])
    if SOURCE.read_bytes() != (ARCHIVE/'7a_b17.asw').read_bytes():
        raise ValueError('Example must remain byte-identical to the original model.')
    inputs += [pin(SOURCE), pin(Path(__file__)), pin(ROOT/'.reference/aswing_doc.txt'),
               pin(ROOT/'.reference/version_notes.txt')]
    kernels = {p.name: pin(p)['sha256'] for p in sorted((ROOT/'openswing').glob('*.py'))}
    request = dict(action='modes', mode='modes', source=SOURCE.read_text(),
        panels=dict(default=count, beams={'1': dict(count=count, spacing='uniform')}),
        condition=None, numerics=POLICY,
        modes=dict(frame='fixed', vacuum=True, count=16, shift=[-.1, 300.], method='dense',
            step=1e-5, rank_tolerance=1e-9, matrices=True, position=[0., 0., 0.],
            attitude=[0., 0., 0.], gravity_magnitude=0.))
    # For this straight, constant-property original model, the distinct point
    # anchor .4318 lies between uniform nodes at all three declared counts.
    # Verify against returned geometry; never tune the count to force a rank.
    expected_elements = count+1
    reference = targets()
    plan = dict(kernel_pins=kernels, kernel_module_count=len(kernels), pins=inputs,
        source_file=str(SOURCE.relative_to(ROOT)), source_sha256=pin(SOURCE)['sha256'], policy=POLICY,
        nominal_intervals=count, expected_elements=expected_elements, expected_nodes=expected_elements+1,
        expected_finite_dimension=4*expected_elements, finite_dimension_rule='4 * actual structural intervals',
        expected_returned_count=16, expected_relaxation_multiplicity=0,
        spectrum_scope=SPECTRUM_SCOPE, pencil_backward_gate=PENCIL_GATE, base_residual_gate=BASE_GATE,
        eigenvalue_absolute_gate=ROOT_ABSOLUTE_GATE, eigenvalue_relative_gate=ROOT_RELATIVE_GATE,
        neutral_relative_gate=NEUTRAL_RELATIVE_GATE,
        mesh_criterion=dict(nominal_grids=[16, 32, 64], relative_gate=MESH_RELATIVE_GATE,
            formula='abs(finer_frequency - coarser_frequency) / abs(finer_frequency)',
            quantities='six lowest positive frequencies from each complete census, ordinal comparison',
            required_final_pair=[32, 64], other_pair_reported=[16, 32],
            scope='Numerical convergence only; not a historical or experimental agreement gate.'),
        reference_rows=reference, reference_status='NOT_ESTABLISHED',
        scope='Unchanged original ST-4 7a_b17 model and archived ASWING roots; conditional declared vacuum/unloaded setup, not an experimental reconstruction or exact historical settings claim.',
        historical_limits=[
            'Original script enters MODE before OPER, selects anchored defaults, toggles MODE F, requests16 at shift(-.1,300), then writes vaccum.txt.',
            'MODE F is the documented free-body/vacuum toggle, not the frozen-influence K/F switch. Its initial value and startup sidecars are not retained.',
            'Zero gravity/pose and uniform meshes are declared prospective choices. Unloaded zero-lift base is documented without preceding operating points, but detailed historical gravity treatment is not proved.',
            'Original node array, mode shapes and complete spectrum are absent. Six archived positive roots are compared ordinally; their completeness is not proved.',
            'Retain literal Constant g9.81/rho_SL1.0771417304, section properties, point positions and parameter anchors. No damping or property fitting.',
            'Tiny original real components are separate numerical residue, not a fitted material damping target.'],
        operations=dict(cold_bridge_calls=1, retries=0, additional_equilibrium_solves=0),
        browser_case=dict(scope='Original ST-4 conditional source-vacuum modal reference; numerical parity is not archived-ASWING agreement.',
            project_name='ISAE ST-4 original 7a_b17 source modes',
            case_name=f'Original model, {count} uniform intervals, declared unloaded vacuum',
            solution_name=f'ST-4 source vacuum, nominal {count}', plot_beam=1,
            plot_quantity='nodes.displacement.1',
            require_nonzero_plot=True, solve_timeout_ms=120000, total_timeout_ms=300000))
    write(output, 'request.json', request)
    write(output, 'plan.json', plan)
    write(output, 'targets.json', reference)
    return request, plan


def verify(result, plan, report):
    import numpy as np
    from scipy.optimize import linear_sum_assignment

    def check(name, passed, **details):
        report['checks'].append(dict(name=name, passed=bool(passed), **details))

    base, diagnostics = result['base'], result['diagnostics']
    ne, nn = base['structural_elements'], base['structural_nodes']
    report['mesh'] = dict(nominal_intervals=plan['nominal_intervals'], actual_elements=ne, actual_nodes=nn,
        mesh_discretization=base['mesh_discretization'], expected_finite_dimension=4*ne)
    check('original attachment-enriched mesh count', ne == plan['expected_elements'] and nn == ne+1,
          predicted_elements=plan['expected_elements'], actual_elements=ne, actual_nodes=nn)
    check('dense finite dimension equals four times actual intervals', diagnostics['finite_dimension'] == 4*ne,
          observed=diagnostics['finite_dimension'], expected=4*ne)
    check('base converged with declared residual gate', result['converged'] and base['converged'] and
          max(base['residual'], diagnostics['base_residual']) <= BASE_GATE,
          base_residual=base['residual'], fresh_modal_base_residual=diagnostics['base_residual'], gate=BASE_GATE)
    check('returned unloaded base has zero gravity', base.get('gravity_body') == [0., 0., 0.],
          gravity_body=base.get('gravity_body'))
    check('source fixed vacuum identity', result['vacuum'] is True and result['frame_mode'] == 'fixed' and
          result.get('fluid') is None and result.get('controller') is None and result['numerics'] == POLICY and
          result['structural_operator'] == base['structural_operator'] == POLICY['structural_operator'])
    identity = base['equilibrium_state']['identity']
    check('equilibrium numerical identity', all(identity.get(key) == value for key, value in POLICY.items()))
    check('zero material damping retained', not any(mode['constitutive_relaxation'] for mode in result['modes']))
    census = diagnostics['finite_spectrum']
    check('complete dense census identified', census is not None and census['scope'] == SPECTRUM_SCOPE)
    if census is None:
        raise ValueError('Complete finite spectrum is required; selected roots cannot substitute.')
    raw = np.asarray(census['eigenvalues'], dtype=float)
    check('census finite and complete', raw.shape == (4*ne, 2) and bool(np.all(np.isfinite(raw))), shape=list(raw.shape))
    if raw.ndim != 2 or raw.shape[1] != 2 or not np.all(np.isfinite(raw)):
        raise ValueError('Invalid complete spectrum.')
    values = raw[:, 0]+1j*raw[:, 1]
    limits = ROOT_ABSOLUTE_GATE+ROOT_RELATIVE_GATE*np.maximum(abs(values[:, None]), abs(values[None, :]))
    conjugate_error = abs(values[:, None]-values.conj()[None, :])
    rows, columns = linear_sum_assignment(conjugate_error/limits)
    conjugate_fraction = conjugate_error[rows, columns]/limits[rows, columns]
    report['census'] = dict(scope=census['scope'], count=len(values), eigenvalues=census['eigenvalues'],
        maximum_real_absolute=float(np.max(abs(values.real))),
        maximum_neutral_relative=float(np.max(abs(values.real)/np.maximum(1., abs(values.imag)))),
        maximum_conjugacy_gate_fraction=float(np.max(conjugate_fraction)),
        conjugate_matches=[dict(index=int(i), conjugate_index=int(j), absolute_error=float(conjugate_error[i, j]),
            gate=float(limits[i, j])) for i, j in zip(rows, columns)])
    check('complete census conjugacy with multiplicity', np.all(conjugate_fraction <= 1.))
    check('undamped census near imaginary axis', report['census']['maximum_neutral_relative'] <= NEUTRAL_RELATIVE_GATE,
          maximum_relative=report['census']['maximum_neutral_relative'], gate=NEUTRAL_RELATIVE_GATE)
    positive_indices = np.flatnonzero(values.imag > 0)
    positive_indices = positive_indices[np.argsort(values.imag[positive_indices], kind='stable')]
    check('expected positive and negative census counts', len(positive_indices) == 2*ne and np.count_nonzero(values.imag < 0) == 2*ne)
    if len(positive_indices) < 6:
        raise ValueError('Complete census contains fewer than six positive frequencies.')
    low_indices = positive_indices[:6]
    selected = np.array([complex(*mode['eigenvalue']) for mode in result['modes']])
    check('exactly sixteen selected vectors', len(selected) == 16)
    selected_distance = abs(selected[:, None]-selected[None, :])
    np.fill_diagonal(selected_distance, np.inf)
    selected_limits = ROOT_ABSOLUTE_GATE+ROOT_RELATIVE_GATE*np.maximum(abs(selected[:, None]), abs(selected[None, :]))
    check('selected roots distinct at declared matching gate', np.all(selected_distance > selected_limits))
    target_distance = abs(values[low_indices, None]-selected[None, :])
    target_limits = ROOT_ABSOLUTE_GATE+ROOT_RELATIVE_GATE*abs(values[low_indices, None])
    ordinal_rows, selected_columns = linear_sum_assignment(target_distance/target_limits)
    check('all six lowest census roots have selected vectors', len(ordinal_rows) == 6 and
          bool(np.all(target_distance[ordinal_rows, selected_columns] <= target_limits[ordinal_rows, 0])))
    selected_map = {int(i): int(j) if target_distance[i, j] <= target_limits[i, 0] else None
                    for i, j in zip(ordinal_rows, selected_columns)}
    report['reference_comparison'] = []
    for ordinal, index in enumerate(low_indices):
        target = plan['reference_rows'][ordinal]
        actual = [float(values[index].real), float(values[index].imag)]
        differences = [actual[k]-target['eigenvalue'][k] for k in range(2)]
        # Decimal.from_float preserves the exact computed binary value when
        # assessing the source's printed interval; there is no extra tolerance.
        precision = [abs(Decimal.from_float(actual[k])-Decimal(target['exact_decimal_values'][k])) <=
                     Decimal(target['exact_decimal_half_units'][k]) for k in range(2)]
        report['reference_comparison'].append(dict(ordinal=ordinal+1, census_index=int(index),
            selected_mode_index=selected_map.get(ordinal), reference=target,
            actual_eigenvalue=actual, actual_frequency_Hz=actual[1]/(2*math.pi),
            difference_per_s=differences, frequency_relative_difference=differences[1]/target['eigenvalue'][1],
            printed_precision=dict(real=bool(precision[0]), imaginary=bool(precision[1])),
            real_component_scope='Numerical residue retained separately; no fitted damping or stability claim.'))
    report['lowest_six_positive_frequencies_Hz'] = [row['actual_frequency_Hz'] for row in report['reference_comparison']]
    report['printed_precision_counts'] = dict(real=sum(row['printed_precision']['real'] for row in report['reference_comparison']),
        imaginary=sum(row['printed_precision']['imaginary'] for row in report['reference_comparison']), per_component_total=6)

    # Independent full original-pencil algebra; no additional model evaluation.
    a, m = [np.asarray(result['matrices'][key], dtype=float) for key in ('A', 'M')]
    check('full saved pencil finite and square', a.ndim == 2 and a.shape[0] == a.shape[1] and m.shape == a.shape
          and bool(np.all(np.isfinite(a))) and bool(np.all(np.isfinite(m))))
    anorm, mnorm = np.linalg.norm(a), np.linalg.norm(m)
    report['pencil_checks'] = []
    for i, mode in enumerate(result['modes']):
        lam = complex(*mode['eigenvalue'])
        entry = dict(index=i, eigenvalue=mode['eigenvalue'])
        for side in ('right', 'left'):
            vector = np.asarray(mode[side]['real'])+1j*np.asarray(mode[side]['imag'])
            if side == 'right':
                residual = a@vector-lam*(m@vector)
            else:
                residual = a.T@vector-lam.conjugate()*(m.T@vector)
            denominator = (anorm+abs(lam)*mnorm)*np.linalg.norm(vector)
            backward = float(np.linalg.norm(residual)/denominator) if denominator > 0 else None
            entry[side] = dict(backward_error=backward, residual_norm=float(np.linalg.norm(residual)),
                denominator=float(denominator), reported_backward_error=mode[side+'_backward_error'])
            check(f'selected mode{i} {side} full-pencil residual', backward is not None and math.isfinite(backward)
                  and backward <= PENCIL_GATE and mode[side+'_backward_error'] <= PENCIL_GATE,
                  independent_backward_error=backward, reported_backward_error=mode[side+'_backward_error'], gate=PENCIL_GATE)
        report['pencil_checks'].append(entry)
    report['maximum_pencil_backward_error'] = max(entry[side]['backward_error'] for entry in report['pencil_checks'] for side in ('right', 'left'))
    report['base_residual'] = diagnostics['base_residual']
    report['finite_dimension'] = diagnostics['finite_dimension']
    report['returned_count'] = len(selected)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    parser.add_argument('count', type=int, choices=[16, 32, 64])
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    report = dict(status='PREPARING', numerical_status='NOT_RUN', reference_status='NOT_ESTABLISHED',
        checks=[], cold_bridge_calls=0, additional_equilibrium_solves=0, retries=0)
    start = time.monotonic()
    plan = None
    error = None
    try:
        request, plan = prepare(output, args.count)
        report.update(status='RUNNING', source_pins=plan['kernel_pins'], reference_scope=plan['scope'],
                      historical_limits=plan['historical_limits'])
        write(output, 'report.json', report)
        sys.path.insert(0, str(ROOT))
        from openswing.bridge import dispatch
        def progress(*args):
            with (output/'progress.jsonl').open('a') as stream:
                stream.write(json.dumps(dict(seconds=time.monotonic()-start, progress=args), allow_nan=False,
                    default=lambda value: value.item() if hasattr(value, 'item') else str(value))+'\n')
        solve_start = time.monotonic()
        report['cold_bridge_calls'] = 1
        result = dispatch(request, progress=progress)
        report['seconds'] = time.monotonic()-solve_start
        write(output, 'result.json', result)
        verify(result, plan, report)
    except BaseException as exc:
        error = exc
        report['error'] = dict(type=type(exc).__name__, message=str(exc), traceback=traceback.format_exc())
    finally:
        if plan is not None:
            pins = plan['pins']+[dict(path=str(ROOT/'openswing'/name), sha256=value) for name, value in plan['kernel_pins'].items()]
            for item in pins:
                try:
                    unchanged = pin(Path(item['path']))['sha256'] == item['sha256']
                except OSError:
                    unchanged = False
                report['checks'].append(dict(name='source pin '+item['path'], passed=unchanged))
        passed = error is None and bool(report['checks']) and all(item['passed'] for item in report['checks'])
        report.update(status='PASS_NUMERICAL_REFERENCE_NOT_ESTABLISHED' if passed else 'FAIL_NUMERICAL_REFERENCE_NOT_ESTABLISHED',
            numerical_status='PASS' if passed else 'FAIL', total_seconds=time.monotonic()-start,
            check_counts=dict(passed=sum(item['passed'] for item in report['checks']), total=len(report['checks'])))
        write(output, 'report.json', report)
        print(json.dumps({key: report.get(key) for key in ('status', 'seconds', 'check_counts', 'finite_dimension',
            'returned_count', 'lowest_six_positive_frequencies_Hz', 'printed_precision_counts', 'error')}), flush=True)
    if error is not None:
        raise error
    if report['numerical_status'] != 'PASS':
        raise SystemExit(1)


if __name__ == '__main__':
    main()
