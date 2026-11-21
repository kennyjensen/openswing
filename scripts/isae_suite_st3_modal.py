"""Conditional ST3 workbook frequency sets on the original three modal models.

Planning and saved-result validation use only stdlib. Numerical imports occur
only in run(). Workbook mode labels are preserved, but never used to select
computed modes: compare ascending frequency sets from a fixed local survey.
"""
from decimal import Decimal
from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path
import time
import xml.etree.ElementTree as ET
from zipfile import ZipFile


ROOT = Path(__file__).resolve().parents[1]
REVISION = 'f62943df20e9e4d7d9f50e070477b22426b5f865'
MANIFEST_SHA256 = '813347a3bd9fcbd029a1ec86e0c3141f82422af26f33ebde7c2f732a16bf27f6'
FOLDER = '3 - Structure/CASE - ST3 Low aspect ratio/Vaccum_anaysis'
LAYUPS = {'0_3_90': 3, 'p15_0': 9, 'm15_0': 15}
GRIDS = (64, 128)
QUALIFICATIONS = [
    'Conditional ascending frequency-set comparison; native modal identity is not established.',
    'Workbook coupled-mode labels conflict with Dunn Table 2; original labels remain attached to source cells.',
    'Workbook General-format tokens are interpreted as rounded values using half-last-recorded-place intervals, not authenticated ASWING print precision or experimental uncertainty.',
    'Fixed upright gravity, density 1.23, exact still air and cosine meshes are declared assumptions; native startup settings are unavailable.',
    'The first three positive-frequency roots of a fixed count-12 local full-pencil survey are selected without consulting targets; global spectrum completeness is not established.',
    'Two meshes repeat the same nine workbook cells; eighteen comparison slots are not eighteen independent reference frequencies.',
    'Saved scalar diagnostics check reported left/right backward errors; this adapter does not independently reassemble the descriptor pencil or compare native eigenvectors.',
]
OPERATIONS = dict(cold_bridge_calls=1, equilibrium_solves=1, modal_solves=1,
                  fresh_residuals=1, retries=0)


def require(ok, message):
    if not ok:
        raise ValueError('ST3 modal: ' + message)


def finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def pin(root, relative):
    raw = (Path(root) / relative).read_bytes()
    return dict(path=str(relative), bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())


def plan(root):
    root = Path(root)
    manifest_path = '.reference/isae-validation/manifest.json'
    require(pin(root, manifest_path)['sha256'] == MANIFEST_SHA256, 'archive manifest changed')
    manifest = json.loads((root / manifest_path).read_text())
    require(manifest['revision'] == REVISION, 'archive revision changed')
    prefix = '.reference/isae-validation/' + REVISION + '/'
    names = ['Comparaison.xlsx'] + ['[' + name + '].asw' for name in LAYUPS]
    pins = {}
    for name in names:
        relative = FOLDER + '/' + name
        p = pin(root, prefix + relative)
        require(all(p[k] == manifest['files'][relative][k] for k in ('bytes', 'sha256')),
                'original input changed: ' + relative)
        pins[name] = p
    with ZipFile(root / pins['Comparaison.xlsx']['path']) as book:
        ns = {'s': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
        strings = [''.join(node.itertext()) for node in
                   ET.fromstring(book.read('xl/sharedStrings.xml')).findall('s:si', ns)]
        cells = {c.attrib['r']: c for c in
                 ET.fromstring(book.read('xl/worksheets/sheet1.xml')).findall('.//s:c', ns)}
        def text(cell):
            c = cells[cell]
            value = c.find('s:v', ns).text
            return strings[int(value)] if c.get('t') == 's' else value
        labels = {col: text(col + '1') for col in 'CDE'}
        require(list(labels.values()) == ['1B (in Hz)', '2B (in Hz)', '1T (in Hz)'],
                'workbook header changed')
        observations = {}
        for layup, row in LAYUPS.items():
            require(text('B' + str(row)) == 'Aswing', 'target row is not ASWING')
            entries = []
            for col in 'CDE':
                cell = col + str(row)
                require(cells[cell].get('t') == 'n' and cells[cell].find('s:f', ns) is None,
                        'reference must be a literal numeric cell')
                token = text(cell)
                value = Decimal(token)
                half = Decimal(5).scaleb(value.as_tuple().exponent - 1)
                entries.append(dict(cell=cell, original_label=labels[col], raw_token=token,
                    expected=float(value), tolerance=float(half), exact_decimal_expected=token,
                    exact_decimal_tolerance=str(half), unit='Hz', kind='continuous',
                    relative_tolerance_allowed=True))
            entries.sort(key=lambda item: item['expected'])
            observations[layup] = [dict(entry, name='frequency_rank_' + str(i), rank=i)
                                   for i, entry in enumerate(entries, 1)]
    jobs = []
    for layup in LAYUPS:
        for nominal in GRIDS:
            jobs.append(dict(id=f'ST-3:modal:{layup}:n{nominal}', case_id='ST-3',
                adapter='st3_modal', layup=layup, nominal=nominal, execution_route='worker',
                target_kind='conditional_workbook_frequency_set', expected_outputs=3,
                model_path=pins['[' + layup + '].asw']['path'],
                table_path=pins['Comparaison.xlsx']['path'],
                sources=[pins['[' + layup + '].asw'], pins['Comparaison.xlsx']],
                observations=observations[layup], qualifications=QUALIFICATIONS.copy(),
                expected_operations=OPERATIONS.copy(), mesh_relative_tolerance=.001))
    return jobs


def validate_record_contract(job, root=ROOT):
    original = next((j for j in plan(root) if j['id'] == job.get('id')), None)
    require(original is not None and all(job.get(k) == v for k, v in original.items()),
            'registered source, mesh, targets or qualifications changed')


def reference_contract(job):
    validate_record_contract(job)
    return {row['name']: row for row in job['observations']}


def request(job, source):
    n = job['nominal']
    return dict(action='modes', mode='modes', source=source,
        panels=dict(default=n, beams={'1': dict(count=n, spacing='cosine')}),
        condition=None, gravity=[0., 0., -9.81], loads=[],
        numerics=dict(beam_interpolation='drela-segspl-v1', structural_operator='drela-fixed-still-air-v1'),
        modes=dict(frame='fixed', vacuum=False, quiescent_density=1.23, count=12,
            shift=[-.01, 0.], method='full_shift_invert', step=1e-5, rank_tolerance=1e-9,
            matrices=False, tolerance=1e-9, continuation_steps=4,
            position=[0., 0., 0.], attitude=[0., 0., 0.]))


def selected_modes(evidence):
    modes = evidence['modes']
    require(len(modes) == 12 and len({m['index'] for m in modes}) == 12,
            'full count-12 survey required')
    for mode in modes:
        pole = mode['eigenvalue']
        require(len(pole) == 2 and all(finite(v) for v in pole), 'nonfinite pole')
        frequency = abs(pole[1]) / (2 * math.pi)
        require(finite(mode['frequency']) and math.isclose(mode['frequency'], frequency,
                rel_tol=1e-12, abs_tol=1e-12), 'frequency detached from eigenvalue')
        for key in ('left_backward_error', 'right_backward_error'):
            require(finite(mode[key]) and 0 <= mode[key] < 1e-8, 'eigenvector residual failed')
    selected = sorted((m for m in modes if m['eigenvalue'][1] > 1e-6),
                      key=lambda m: m['frequency'])[:3]
    require(len(selected) == 3 and all(abs(m['eigenvalue'][0]) < 1e-6 * abs(m['eigenvalue'][1])
            for m in selected), 'three neutral positive-frequency roots required')
    return selected


def reference_checks(job, selected):
    checks = []
    for row, mode in zip(job['observations'], selected):
        prediction = mode['frequency']
        error = abs(Decimal(str(prediction)) - Decimal(row['exact_decimal_expected']))
        checks.append(dict(row, predicted=prediction, mode_index=mode['index'],
            comparison='<=', passed=error <= Decimal(row['exact_decimal_tolerance']),
            abs_error=float(error), error_percent=100 * float(error) / abs(row['expected'])))
    return checks


def assess_bridge(job, raw, fresh_residual, circulation_unknowns):
    """Build compact evidence from an actual bridge result and fresh restoration."""
    fields = ('index', 'eigenvalue', 'frequency', 'left_backward_error', 'right_backward_error')
    diag, base, fluid = raw['diagnostics'], raw['base'], raw['fluid']
    evidence = dict(modes=[{key: mode[key] for key in fields} for mode in raw['modes']],
        converged=raw['converged'], base_converged=base['converged'], base_residual=base['residual'],
        fresh_residual=fresh_residual, circulation_unknowns=circulation_unknowns,
        frame=raw['frame_mode'], vacuum=raw['vacuum'], density=fluid['density'],
        mean_velocity=fluid['mean_velocity_body'], gravity=base['gravity_body'],
        operator=diag['structural_operator'], method=diag['method'],
        requested_count=diag['requested_count'], shift=diag['shift'],
        structural_nodes=base['structural_nodes'], structural_elements=base['structural_elements'])
    checks = reference_checks(job, selected_modes(evidence))
    result = dict(status='computed', numerical_pass=True,
        reference_match=all(c['passed'] for c in checks), reference_checks=checks,
        numerical_evidence=evidence, source_pins_unchanged=True, operations=OPERATIONS.copy(),
        qualifications=QUALIFICATIONS.copy(), complete_family_reproduction=False,
        historical_settings_authenticated=False, native_modal_identity_verified=False,
        complete_finite_spectrum=False)
    validate_result_contract(job, result)
    return result


def validate_result_contract(job, result):
    validate_record_contract(job)
    require(result.get('qualifications') == QUALIFICATIONS and all(result.get(k) is False for k in
        ('complete_family_reproduction', 'historical_settings_authenticated',
         'native_modal_identity_verified', 'complete_finite_spectrum')), 'conditional scope lost')
    if result.get('status') != 'computed':
        require(result.get('reference_match') is not True, 'failed job claims agreement')
        return True
    require(result.get('numerical_pass') is True and result.get('source_pins_unchanged') is True
            and result.get('operations') == OPERATIONS, 'execution evidence incomplete')
    e = result['numerical_evidence']
    require(e['converged'] is True and e['base_converged'] is True and
        all(finite(e[k]) and 0 <= e[k] < 1e-8 for k in ('base_residual', 'fresh_residual')),
        'equilibrium or fresh restoration failed')
    require(e['circulation_unknowns'] == 0 and e['frame'] == 'fixed' and e['vacuum'] is False
        and e['density'] == 1.23 and e['mean_velocity'] == [0., 0., 0.]
        and e['gravity'] == [0., 0., -9.81] and e['operator'] == 'drela-fixed-still-air-v1'
        and e['method'] == 'full_shift_invert' and e['requested_count'] == 12
        and e['shift'] == [-.01, 0.], 'declared physical setup or survey changed')
    require(e['structural_elements'] == job['nominal'] + 1 and
        e['structural_nodes'] == e['structural_elements'] + 1, 'mesh evidence incomplete')
    checks = reference_checks(job, selected_modes(e))
    actual = result.get('reference_checks', [])
    require(len(actual) == len(checks) and all(all(a.get(k) == v for k, v in b.items())
            for a, b in zip(actual, checks)), 'targets, predictions or selection changed')
    require(result.get('reference_match') is all(c['passed'] for c in checks), 'incorrect pass flag')
    return True


def run(root, job):
    validate_record_contract(job, root)
    import numpy as np
    from openswing.asw import parse_asw
    from openswing.bridge import dispatch
    from openswing.equilibrium_state import restore, warm_start_recipe
    from openswing.source_quiescent import SourceQuiescentNetwork
    source = (Path(root) / job['model_path']).read_text()
    payload = request(job, source)
    started = time.monotonic()
    raw = dispatch(payload)
    seconds = time.monotonic() - started
    model = parse_asw(source, beam_interpolation='drela-segspl-v1')
    saved = raw['base']['equilibrium_state']
    network = SourceQuiescentNetwork(model, payload['panels'], None, payload['gravity'], [],
        mesh_recipe=warm_start_recipe(model, payload['panels'], saved), quiescent_density=1.23)
    state = restore(network, saved)
    zero = np.zeros_like(network.rj)
    residual, _ = network.residual(state, detail=True, elastic_motion=(zero, zero, zero, zero),
                                   circulation_rate=np.zeros(network.ng))
    require(np.isfinite(residual).all(), 'nonfinite restored residual')
    result = assess_bridge(job, raw, float(np.max(abs(residual))), network.ng)
    validate_record_contract(job, root)
    result['solver_seconds'] = seconds
    return result


def mesh_diagnostics(jobs, results):
    """Rank-wise frequency convergence only; not a mode-shape identity test."""
    rows = []
    for layup in LAYUPS:
        pair = {j['nominal']: j for j in jobs if j.get('layup') == layup}
        if not pair:
            continue
        ready = all(n in pair and results.get(pair[n]['id'], {}).get('status') == 'computed'
                    for n in GRIDS)
        row = dict(layup=layup, grids=list(GRIDS), status='INCOMPLETE',
            tolerance=.001, checks=[], historical_modal_identity_verified=False,
            definition='Frequency ranks in fixed local surveys; not a modal-shape MAC check.')
        if ready:
            for n in GRIDS:
                validated_strict_result(pair[n], results[pair[n]['id']])
            coarse, fine = [results[pair[n]['id']]['reference_checks'] for n in GRIDS]
            for a, b in zip(coarse, fine):
                error = abs(a['predicted'] - b['predicted']) / abs(b['predicted'])
                row['checks'].append(dict(rank=b['rank'], relative_error=error, passed=error <= .001))
            row['status'] = 'PASS' if all(c['passed'] for c in row['checks']) else 'FAIL'
        rows.append(row)
    return rows


def validated_strict_result(job, result):
    """Authenticate a relative-policy view before using it for mesh checks."""
    if 'reference_acceptance_policy' not in result:
        validate_result_contract(job, result)
        return result
    from isae_acceptance import apply_reference_acceptance, reference_acceptance_policy
    policy = result['reference_acceptance_policy']
    require(policy == reference_acceptance_policy(
        relative_tolerance=policy['relative_tolerance'], tiny_reference=policy['tiny_reference']),
        'reference policy changed')
    strict = deepcopy(result)
    strict.pop('reference_acceptance_policy')
    strict.pop('strict_reference_match')
    strict.pop('strict_output_accounting')
    checks = reference_checks(job, selected_modes(result['numerical_evidence']))
    strict['reference_checks'] = checks
    strict['reference_match'] = all(c['passed'] for c in checks)
    strict['output_accounting'] = dict(required=job['expected_outputs'], reported=len(checks),
        finite=len(checks), unavailable=0, numerically_valid=len(checks),
        passed=sum(c['passed'] for c in checks), missing=0)
    validate_result_contract(job, strict)
    expected = apply_reference_acceptance(strict, relative_tolerance=policy['relative_tolerance'],
                                          tiny_reference=policy['tiny_reference'])
    require(expected == result, 'relative policy view does not reproduce strict evidence')
    return strict
