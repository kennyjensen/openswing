#!/usr/bin/env python3
"""Declared local full-descriptor Arnoldi comparison for unchanged ST-4.

One original cold call: verify-isae-st4-arnoldi.py NEW_OUTPUT_DIR {16,32,64}
Prospective refinement: NEW_OUTPUT_DIR 128 --refinement-from FAILED_32_64_REPORT
Preparation only: append --prepare-only (no production imports).
Saved mesh comparison: NEW_OUTPUT_DIR --compare-pair COARSE_DIR FINE_DIR

The process owner supplies a deadline. No retries, settings search or complete
spectrum claim. The existing dense protocol is imported read-only and unchanged.
"""
import argparse
from copy import deepcopy
from decimal import Decimal
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sys
import time
import traceback

ROOT = Path(__file__).resolve().parents[1]
DENSE_SCRIPT = ROOT/'scripts/verify-isae-st4-source-modes.py'
_spec = importlib.util.spec_from_file_location('isae_st4_dense_reference', DENSE_SCRIPT)
reference = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(reference)
METHOD = 'full_shift_invert'
LOCAL_SCOPE = 'Local full-descriptor Arnoldi search; total finite dimension unclassified.'
ORDINAL_SCOPE = ('First six ascending positive frequencies within the sixteen selected roots, '
                 'compared to the six archived ordinals; not certified globally lowest modes.')
PAIRING_GATE = reference.PENCIL_GATE
pin, write = reference.pin, reference.write


def verify_pins(plan):
    entries = plan['pins']+[dict(path=str(ROOT/'openswing'/name), sha256=digest)
                           for name, digest in plan['kernel_pins'].items()]
    rows = []
    for item in entries:
        try:
            unchanged = pin(Path(item['path']))['sha256'] == item['sha256']
        except OSError:
            unchanged = False
        rows.append(dict(name='source pin '+item['path'], passed=unchanged))
    return rows


def refinement_record(path):
    """Retain the failed original criterion; a later pair cannot replace it."""
    path = path.resolve()
    prior = json.loads(path.read_text())
    rows = prior.get('mesh_checks', [])
    if (prior.get('actual_pair') != [32, 64] or prior.get('required_final_pair') != [32, 64]
            or prior.get('status') != 'FAIL_SELECTED_ORDINAL_MESH'
            or prior.get('numerical_status') != 'FAIL' or len(rows) != 6
            or any(row.get('gate') != reference.MESH_RELATIVE_GATE for row in rows)
            or not any(row.get('passed') is False for row in rows)):
        raise ValueError('Refinement requires the retained failed original 32-to-64 mesh report at the unchanged gate.')
    other_failures = [row for row in prior.get('checks', []) if not row['passed'] and
                      not row['name'].endswith(' unchanged mesh gate')]
    if other_failures:
        raise ValueError('Resolve non-mesh protocol failures separately; they do not justify this refinement.')
    return dict(justification='Prospective refinement after the observed failure of the original required 32-to-64 mesh criterion; no model, solver, shift, selected count or accuracy-gate change.',
        original_required_pair=[32, 64], extension_pair=[64, 128], original_required_status=prior['status'],
        original_report=pin(path), original_mesh_checks=rows,
        original_failed_ordinals=[row['ordinal'] for row in rows if not row['passed']],
        scope='The extension does not relabel, supersede or turn the original required-pair failure into a pass.')


def prepare(output, count, refinement_from=None):
    if (count == 128) != (refinement_from is not None):
        raise ValueError('Only the prospective 128 grid requires --refinement-from FAILED_32_64_REPORT.')
    refinement = refinement_record(refinement_from) if refinement_from is not None else None
    request, plan = reference.prepare(output, count)
    dense_request = deepcopy(request)
    request['modes']['method'] = METHOD
    unchanged = deepcopy(request)
    unchanged['modes']['method'] = 'dense'
    if unchanged != dense_request:
        raise ValueError('Arnoldi setup differs from the immutable dense setup beyond method.')
    plan['pins'].append(pin(Path(__file__)))
    if refinement is not None:
        plan['pins'].append(refinement['original_report'])
    for key in ('expected_finite_dimension', 'finite_dimension_rule', 'expected_relaxation_multiplicity'):
        plan.pop(key, None)
    plan.update(method=METHOD, expected_finite_dimension=None, expected_returned_count=16,
        spectrum_scope=LOCAL_SCOPE, ordinal_scope=ORDINAL_SCOPE,
        immutable_dense_protocol=pin(DENSE_SCRIPT), dense_request=deepcopy(dense_request),
        allowed_setup_difference={'modes.method': {'original': 'dense', 'current': METHOD}},
        mass_pairing_gate=PAIRING_GATE,
        mass_pairing_scope='Each selected left^H M right must equal one; cross-pairings retained as diagnostics.',
        original_required_pair=[32, 64], extension_pair=[64, 128] if refinement is not None else None,
        refinement=refinement,
        reference_status='NOT_ESTABLISHED')
    plan['mesh_criterion']['quantities'] = 'six selected positive ordinal frequencies; no complete-spectrum ordering claim'
    plan['mesh_criterion'].update(original_required_pair=[32, 64],
        extension_grids=[128] if refinement is not None else [],
        extension_pair=[64, 128] if refinement is not None else None)
    plan['scope'] += ' This separate local Arnoldi protocol leaves complete spectrum coverage unclassified.'
    plan['historical_limits'].append(ORDINAL_SCOPE)
    plan['browser_case'].update(scope='Original ST-4 conditional local source-vacuum modes; no complete spectrum or archived agreement claim.',
        solution_name=f'ST-4 source vacuum local Arnoldi, nominal {count}')
    plan['operations'].update(production_imports_before_plan=0, request_only_change='modes.method')
    write(output, 'request.json', request)
    write(output, 'plan.json', plan)
    return request, plan


def verify(result, plan, report):
    import numpy as np

    def check(name, passed, **details):
        report['checks'].append(dict(name=name, passed=bool(passed), **details))

    base, diagnostics = result['base'], result['diagnostics']
    ne, nn = base['structural_elements'], base['structural_nodes']
    report['mesh'] = dict(nominal_intervals=plan['nominal_intervals'], actual_elements=ne,
        actual_nodes=nn, mesh_discretization=base['mesh_discretization'])
    check('original attachment-enriched mesh count', ne == plan['expected_elements'] and nn == ne+1,
          predicted_elements=plan['expected_elements'], actual_elements=ne, actual_nodes=nn)
    check('base converged with unchanged gate', result['converged'] and base['converged'] and
          max(base['residual'], diagnostics['base_residual']) <= reference.BASE_GATE,
          base_residual=base['residual'], fresh_modal_base_residual=diagnostics['base_residual'], gate=reference.BASE_GATE)
    check('returned unloaded base has zero gravity', base.get('gravity_body') == [0., 0., 0.])
    check('source fixed vacuum identity', result['vacuum'] is True and result['frame_mode'] == 'fixed' and
          result.get('fluid') is None and result.get('controller') is None and result['numerics'] == reference.POLICY and
          result['structural_operator'] == base['structural_operator'] == reference.POLICY['structural_operator'])
    identity = base['equilibrium_state']['identity']
    check('equilibrium numerical identity', all(identity.get(key) == value for key, value in reference.POLICY.items()))
    check('zero material damping retained', not any(mode['constitutive_relaxation'] for mode in result['modes']))
    check('actual local full descriptor method', diagnostics['method'] == diagnostics['requested_method'] == METHOD)
    check('local coverage explicitly unclassified', diagnostics['finite_dimension'] is None and
          diagnostics['finite_spectrum'] is None and diagnostics['spectrum_scope'] == LOCAL_SCOPE)
    check('declared count and shift retained', diagnostics['requested_count'] == 16 and diagnostics['shift'] == [-.1, 300.])
    values = np.asarray([complex(*mode['eigenvalue']) for mode in result['modes']])
    check('sixteen finite selected vectors', len(values) == 16 and bool(np.all(np.isfinite(values))))
    if len(values) != 16 or not np.all(np.isfinite(values)):
        raise ValueError('Exactly sixteen finite local roots are required; no automatic retry.')
    distances = abs(values[:, None]-values[None, :])
    np.fill_diagonal(distances, np.inf)
    limits = reference.ROOT_ABSOLUTE_GATE+reference.ROOT_RELATIVE_GATE*np.maximum(abs(values[:, None]), abs(values[None, :]))
    check('selected roots distinct at unchanged matching gate', bool(np.all(distances > limits)))
    neutral = abs(values.real)/np.maximum(1., abs(values.imag))
    check('undamped selected roots near imaginary axis', bool(np.max(neutral) <= reference.NEUTRAL_RELATIVE_GATE),
          maximum_relative=float(np.max(neutral)), gate=reference.NEUTRAL_RELATIVE_GATE)
    positive = np.flatnonzero(values.imag > 0)
    positive = positive[np.argsort(values.imag[positive], kind='stable')]
    check('six positive selected ordinal candidates available', len(positive) >= 6, selected_positive_count=len(positive))
    if len(positive) < 6:
        raise ValueError('Local search did not return six positive ordinal candidates; preserve failure without changing shift/count.')
    report['selected_spectrum'] = dict(scope=LOCAL_SCOPE, count=len(values), eigenvalues=[m['eigenvalue'] for m in result['modes']],
        positive_count=len(positive), negative_count=int(np.count_nonzero(values.imag < 0)),
        maximum_real_absolute=float(np.max(abs(values.real))), maximum_neutral_relative=float(np.max(neutral)),
        conjugacy_scope='A local complex-shift selection need not include every conjugate; no paired-count claim.')
    comparisons = []
    for ordinal, index in enumerate(positive[:6]):
        target = plan['reference_rows'][ordinal]
        actual = [float(values[index].real), float(values[index].imag)]
        differences = [actual[k]-target['eigenvalue'][k] for k in range(2)]
        precision = [abs(Decimal.from_float(actual[k])-Decimal(target['exact_decimal_values'][k])) <=
                     Decimal(target['exact_decimal_half_units'][k]) for k in range(2)]
        comparisons.append(dict(ordinal=ordinal+1, selected_mode_index=int(index), reference=target,
            actual_eigenvalue=actual, actual_frequency_Hz=actual[1]/(2*math.pi),
            difference_per_s=differences, frequency_relative_difference=differences[1]/target['eigenvalue'][1],
            printed_precision=dict(real=bool(precision[0]), imaginary=bool(precision[1])),
            assignment_scope=ORDINAL_SCOPE, real_component_scope='Numerical residue, not a fitted damping or stability target.'))
    report['reference_comparison'] = comparisons
    report['ordinal_selected_positive_frequencies_Hz'] = [r['actual_frequency_Hz'] for r in comparisons]
    report['printed_precision_counts'] = dict(real=sum(r['printed_precision']['real'] for r in comparisons),
        imaginary=sum(r['printed_precision']['imaginary'] for r in comparisons), per_component_total=6)

    a, m = [np.asarray(result['matrices'][key], dtype=float) for key in ('A', 'M')]
    valid = a.ndim == 2 and a.shape[0] == a.shape[1] and m.shape == a.shape and np.all(np.isfinite(a)) and np.all(np.isfinite(m))
    check('full original pencil finite and square', valid)
    if not valid:
        raise ValueError('Invalid original matrices.')
    anorm, mnorm = np.linalg.norm(a), np.linalg.norm(m)
    report['pencil_checks'] = []
    rights, lefts = [], []
    for i, mode in enumerate(result['modes']):
        lam = complex(*mode['eigenvalue']);entry = dict(index=i, eigenvalue=mode['eigenvalue'])
        vectors = {}
        for side in ('right', 'left'):
            vector = np.asarray(mode[side]['real'])+1j*np.asarray(mode[side]['imag'])
            if vector.shape != (len(a),) or not np.all(np.isfinite(vector)):
                raise ValueError(f'Invalid full {side} vector for mode{i}.')
            vectors[side] = vector
            residual = a@vector-lam*(m@vector) if side == 'right' else a.T@vector-lam.conjugate()*(m.T@vector)
            denominator = (anorm+abs(lam)*mnorm)*np.linalg.norm(vector)
            backward = float(np.linalg.norm(residual)/denominator) if denominator > 0 else None
            entry[side] = dict(backward_error=backward, residual_norm=float(np.linalg.norm(residual)),
                denominator=float(denominator), reported_backward_error=mode[side+'_backward_error'])
            check(f'mode{i} {side} original-pencil residual', backward is not None and math.isfinite(backward) and
                  backward <= reference.PENCIL_GATE and mode[side+'_backward_error'] <= reference.PENCIL_GATE,
                  independent_backward_error=backward, reported_backward_error=mode[side+'_backward_error'], gate=reference.PENCIL_GATE)
        pairing = np.vdot(vectors['left'], m@vectors['right'])
        pairing_error = float(abs(pairing-1))
        entry['mass_pairing'] = dict(value=[float(pairing.real), float(pairing.imag)], error=pairing_error,
                                    reported_normalized=mode['biorthogonal_normalized'])
        check(f'mode{i} independent mass normalization', mode['biorthogonal_normalized'] and pairing_error <= PAIRING_GATE,
              absolute_error=pairing_error, gate=PAIRING_GATE)
        report['pencil_checks'].append(entry);rights.append(vectors['right']);lefts.append(vectors['left'])
    pairs = np.column_stack(lefts).conj().T@m@np.column_stack(rights)
    cross = pairs-np.diag(np.diag(pairs))
    report['mass_pairing_matrix'] = dict(real=pairs.real.tolist(), imag=pairs.imag.tolist(),
        maximum_cross_pair_absolute=float(np.max(abs(cross))),
        scope='Cross-pair diagnostic for the distinct selected modes; each diagonal has the declared acceptance gate.')
    report['maximum_mass_pairing_error'] = max(r['mass_pairing']['error'] for r in report['pencil_checks'])
    report['maximum_pencil_backward_error'] = max(r[s]['backward_error'] for r in report['pencil_checks'] for s in ('right', 'left'))
    report.update(base_residual=diagnostics['base_residual'], finite_dimension=None, returned_count=len(values))


def compare_pair(coarse, fine, output):
    paths = [root/name for root in (coarse, fine) for name in ('plan.json', 'request.json', 'report.json')]
    inputs = [pin(p) for p in paths]
    cp, cq, cr, fp, fq, fr = [json.loads(p.read_text()) for p in paths]
    checks = []
    def check(name, passed):checks.append(dict(name=name, passed=bool(passed)))
    check('both numerical reports passed', cr['numerical_status'] == fr['numerical_status'] == 'PASS')
    actual_pair = [cp['nominal_intervals'], fp['nominal_intervals']]
    check('declared adjacent grid pair', actual_pair in ([16, 32], [32, 64], [64, 128]))
    check('same exact kernel sources', cp['kernel_pins'] == fp['kernel_pins'])
    check('same original targets and policies', cp['reference_rows'] == fp['reference_rows'] and cp['policy'] == fp['policy'] == reference.POLICY)
    check('local Arnoldi protocol on both grids', cp['method'] == fp['method'] == METHOD and cp['ordinal_scope'] == fp['ordinal_scope'] == ORDINAL_SCOPE)
    c_without = {k:v for k,v in cq.items() if k != 'panels'};f_without = {k:v for k,v in fq.items() if k != 'panels'}
    check('requests differ only in declared mesh', c_without == f_without)
    extension = actual_pair == [64, 128]
    refinement = fp.get('refinement') if extension else None
    if extension:
        check('prospective extension retains original required failure', refinement is not None and
            refinement.get('original_required_pair') == [32, 64] and refinement.get('extension_pair') == [64, 128] and
            refinement.get('original_required_status') == 'FAIL_SELECTED_ORDINAL_MESH' and
            fp.get('original_required_pair') == [32, 64] and fp.get('extension_pair') == [64, 128])
        if refinement is not None:
            original_pin = refinement['original_report']
            check('original failed report remains byte-identical', pin(Path(original_pin['path'])) == original_pin)
            inputs.append(original_pin)
    rows = []
    check('all six ordinal rows retained', len(cr['reference_comparison']) == len(fr['reference_comparison']) == 6)
    for c, f in zip(cr['reference_comparison'], fr['reference_comparison']):
        check(f'ordinal{c["ordinal"]} source identity', c['ordinal'] == f['ordinal'] and c['reference'] == f['reference'])
        cv, fv = c['actual_frequency_Hz'], f['actual_frequency_Hz']
        relative = abs(fv-cv)/abs(fv) if fv else (0. if cv == 0 else None)
        passed = relative is not None and math.isfinite(relative) and relative <= reference.MESH_RELATIVE_GATE
        rows.append(dict(ordinal=f['ordinal'], coarse_frequency_Hz=cv, fine_frequency_Hz=fv,
            relative_change=relative, gate=reference.MESH_RELATIVE_GATE, passed=passed))
        check(f'ordinal{f["ordinal"]} unchanged mesh gate', passed)
    for entry in inputs:check('saved input unchanged '+entry['path'], pin(Path(entry['path'])) == entry)
    passed = bool(checks) and all(c['passed'] for c in checks)
    report = dict(status='PASS_SELECTED_ORDINAL_MESH' if passed else 'FAIL_SELECTED_ORDINAL_MESH',
        numerical_status='PASS' if passed else 'FAIL', reference_status='NOT_ESTABLISHED', input_pins=inputs,
        scope=ORDINAL_SCOPE, formula='abs(finer_frequency-coarser_frequency)/abs(finer_frequency); exact zero only matches zero',
        required_final_pair=[32, 64], original_required_pair=[32, 64],
        extension_pair=[64, 128] if extension else None, actual_pair=actual_pair,
        comparison_role='prospective_extension' if extension else 'original_required' if actual_pair == [32, 64] else 'original_reported',
        original_required_status=(refinement['original_required_status'] if refinement is not None
                                  else ('PASS_SELECTED_ORDINAL_MESH' if passed else 'FAIL_SELECTED_ORDINAL_MESH')
                                  if actual_pair == [32, 64] else 'NOT_EVALUATED_IN_THIS_REPORT'),
        refinement=refinement,
        mesh_checks=rows, checks=checks, check_counts=dict(passed=sum(c['passed'] for c in checks), total=len(checks)),
        operations=dict(cold_bridge_calls=0, physical_evaluations=0, residuals=0, retries=0))
    write(output, 'report.json', report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    parser.add_argument('count', type=int, nargs='?', choices=[16, 32, 64, 128])
    parser.add_argument('--prepare-only', action='store_true')
    parser.add_argument('--refinement-from', type=Path, metavar='FAILED_32_64_REPORT')
    parser.add_argument('--compare-pair', nargs=2, type=Path, metavar=('COARSE', 'FINE'))
    args = parser.parse_args()
    if bool(args.compare_pair) == (args.count is not None) or (args.compare_pair and args.prepare_only):
        parser.error('Specify either one grid count or --compare-pair COARSE FINE; preparation requires a count.')
    if (args.count == 128) != (args.refinement_from is not None):
        parser.error('Only count128 requires --refinement-from FAILED_32_64_REPORT; pair comparison reads the fine plan provenance.')
    output = args.output.resolve();output.mkdir(parents=True, exist_ok=False)
    report = dict(status='PREPARING', numerical_status='NOT_RUN', reference_status='NOT_ESTABLISHED',
        checks=[], cold_bridge_calls=0, additional_equilibrium_solves=0, retries=0)
    start = time.monotonic();plan = None;error = None
    try:
        if args.compare_pair:
            report = compare_pair(*(p.resolve() for p in args.compare_pair), output)
        else:
            request, plan = prepare(output, args.count, args.refinement_from)
            report.update(source_pins=plan['kernel_pins'], reference_scope=plan['scope'], historical_limits=plan['historical_limits'])
            before = verify_pins(plan);report['checks'].extend(dict(c, phase='before') for c in before)
            if not all(c['passed'] for c in before):raise ValueError('A frozen input changed before the sole call.')
            if args.prepare_only:
                report['status'] = 'PREPARED_NO_EXECUTION'
            else:
                report['status'] = 'RUNNING';write(output, 'report.json', report)
                sys.path.insert(0, str(ROOT))
                from openswing.bridge import dispatch
                def progress(*values):
                    with (output/'progress.jsonl').open('a') as stream:
                        stream.write(json.dumps(dict(seconds=time.monotonic()-start, progress=values), allow_nan=False,
                            default=lambda v:v.item() if hasattr(v, 'item') else str(v))+'\n')
                report['cold_bridge_calls'] = 1;solve_start = time.monotonic()
                result = dispatch(request, progress=progress)
                report['seconds'] = time.monotonic()-solve_start;write(output, 'result.json', result)
                verify(result, plan, report)
    except BaseException as exc:
        error = exc;report['error'] = dict(type=type(exc).__name__, message=str(exc), traceback=traceback.format_exc())
    finally:
        if plan is not None:report['checks'].extend(dict(c, phase='after') for c in verify_pins(plan))
        passed = error is None and bool(report['checks']) and all(c['passed'] for c in report['checks'])
        if args.prepare_only and passed:
            report.update(status='PREPARED_NO_EXECUTION', numerical_status='NOT_RUN')
        elif not args.compare_pair or error:
            report.update(status='PASS_LOCAL_NUMERICAL_REFERENCE_NOT_ESTABLISHED' if passed else 'FAIL_LOCAL_NUMERICAL_REFERENCE_NOT_ESTABLISHED',
                numerical_status='PASS' if passed else 'FAIL')
        report.update(total_seconds=time.monotonic()-start,
            check_counts=dict(passed=sum(c['passed'] for c in report['checks']), total=len(report['checks'])))
        write(output, 'report.json', report)
        print(json.dumps({k:report.get(k) for k in ('status', 'seconds', 'check_counts', 'returned_count',
            'ordinal_selected_positive_frequencies_Hz', 'printed_precision_counts', 'error')}), flush=True)
    if error is not None:raise error
    if not passed:raise SystemExit(1)


if __name__ == '__main__':
    main()
