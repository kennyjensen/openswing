"""Original SA6 decoding and dispatch boundary tests; no physical solves."""
import copy
import importlib.util
import json
import math
from pathlib import Path
import subprocess
import sys
import types

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
SPEC = importlib.util.spec_from_file_location('isae_suite_sa6', ROOT/'scripts/isae_suite_sa6.py')
SA6 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SA6)


@pytest.fixture(scope='module')
def jobs():
    if not (ROOT/'.reference/isae-validation'/SA6.REVISION).exists():
        pytest.skip('Original optional ISAE archive is not installed.')
    return SA6.plan(ROOT)


def test_source_inventory_and_planning_import_no_production(jobs):
    assert len(jobs) == len({j['id'] for j in jobs}) == 91
    assert sum(j['expected_outputs'] for j in jobs) == 528
    active = [j for j in jobs if j['execution_route'] != 'unsupported']
    assert len(active) == 88
    assert len([j for j in jobs if j.get('source_binding')]) == 66
    assert not any(j['blocker_code'] == 'NO_MATCHING_DRIVER' for j in jobs)
    assert len([j for j in jobs if j['blocker_code'] == 'NO_PAIRED_EXPORT']) == 3
    assert {j['settings']['panels'] for j in active} == {64, 128}
    assert all(j['settings']['freeze_influences'] is True for j in active)
    assert all(j['settings']['stall_factor'] == 40. and j['settings']['stall_width'] == .05 for j in active)
    assert sorted({j['settings']['controls']['1'] for j in active}) == list(range(4, 45, 4))
    assert all(j['expected_outputs'] == 6 and j['required_outputs'] == list(SA6.OUTPUTS) for j in active)
    program = '''import pathlib,sys
root=pathlib.Path(sys.argv[1]);sys.path.insert(0,str(root/'scripts'))
import isae_suite_sa6 as s
j=s.plan(root)
for x in j:
 if x['execution_route']=='unsupported':
  r=s.validate_blocked(root,x);assert r['status']=='unsupported' and r['physical_calls']==0 and not r['reference_match']
assert not any(n=='openswing' or n.startswith('openswing.') or n in ('numpy','scipy') for n in sys.modules)
print(len(j))
'''
    done = subprocess.run([sys.executable, '-c', program, str(ROOT)], capture_output=True, text=True,
                          check=True, timeout=25)
    assert done.stdout.strip() == '91'


def test_driver_invocation_overrides_misleading_filename(jobs):
    j = next(j for j in jobs if j.get('driver_path'))
    assert Path(j['driver_path']).name == 'Post_Stall_15c.sh'
    assert Path(j['model_path']).name == 'Straight_Wing_20b_35c.asw'
    assert j['driver_declarations']['model_file'] == Path(j['model_path']).name
    assert j['driver_declarations']['requested_nodes'] is None
    assert j['driver_declarations']['node_count_token'] is None
    assert 'declared_panels' not in j['driver_declarations']
    assert 'panel_token' not in j['driver_declarations']
    text = (ROOT/j['driver_path']).read_text()
    with pytest.raises(ValueError, match='command sequence'):
        SA6.decode_driver(text.replace('aswing Straight_Wing_20b_35c', 'aswing Straight_Wing_20b_15c'))
    with pytest.raises(ValueError, match='command sequence'):
        SA6.decode_driver(text.replace('!V 20', '!V 20\n!B 2'))


def test_all_original_rows_and_six_printed_coefficients_preserved(jobs):
    source = next(j for j in jobs if j.get('driver_path'))
    row = SA6.decode_fmat((ROOT/source['table_path']).read_text())
    assert row['operating_point'] == 1
    assert row['fields']['CX'] == {'token': '-0.098756', 'value': -.098756, 'tolerance': 5e-7}
    assert row['fields']['CY']['token'] == '0.000000'
    assert row['fields']['CL']['value'] == 1.169827
    assert set(row['fields']) == set(SA6.OUTPUTS)
    assert row['metadata']['q']['value'] == 245.12
    assert row['metadata']['rho_ratio']['value'] == 1
    for j in jobs:
        if j['table_path']:
            assert j['reference_row']['operating_point'] == int(Path(j['table_path']).suffix.split('_')[-1])
            assert all(v['tolerance'] == 5e-7 for v in j['reference_row']['fields'].values())


@pytest.mark.parametrize('change', ['axes', 'missing', 'duplicate', 'badnumber'])
def test_malformed_fmat_rejected(jobs, change):
    text = (ROOT/next(j for j in jobs if j['table_path'])['table_path']).read_text()
    if change == 'axes':
        text = text.replace('Normalized forces in: Stability axes', 'Normalized forces in: Body axes')
    elif change == 'missing':
        text = text.replace('CX =', 'ZZ =')
    elif change == 'duplicate':
        text = text.replace('CX =', 'CX = 0.1 CX =')
    else:
        text = text.replace('CX =', 'CX = invalid ')
    with pytest.raises(ValueError):
        SA6.decode_fmat(text)


def test_stability_rotation_signs_and_reference_lengths():
    actual = SA6.stability_coefficients([2, 3, 5], [7, 11, 13], 0, 2, 5, 7)
    assert actual == dict(CX=-1., CY=1.5, CL=2.5, Cl=-.5, Cm=1.1, Cn=-13/14)
    turned = SA6.stability_coefficients([2, 3, 5], [7, 11, 13], 90, 2, 5, 7)
    assert turned == pytest.approx(dict(CX=-2.5, CY=1.5, CL=-1., Cl=-13/14, Cm=1.1, Cn=.5), abs=1e-15)


def test_precision_is_not_widened_and_missing_predictions_are_explicit(jobs):
    j = next(j for j in jobs if j['execution_route'] != 'unsupported')
    predicted = {name: j['reference_row']['fields'][name]['value'] for name in SA6.OUTPUTS}
    assert all(c['passed'] for c in SA6.reference_checks(predicted, j))
    predicted['Cl'] += 1.01e-6
    predicted['CY'] = math.nan
    checks = SA6.reference_checks(predicted, j)
    assert sum(c['passed'] for c in checks) == 4
    assert next(c for c in checks if c['name'] == 'CY')['predicted'] is None
    json.dumps(checks, allow_nan=False)


@pytest.mark.parametrize('field', ['controls', 'target', 'route'])
def test_job_tampering_is_rejected_before_dispatch(jobs, field):
    j = copy.deepcopy(next(j for j in jobs if j['execution_route'] != 'unsupported'))
    if field == 'controls':
        j['settings']['controls']['1'] = -4.
    elif field == 'target':
        j['reference_row']['fields']['CL']['tolerance'] = 1.
    else:
        j['execution_route'] = 'guessed'
    report = SA6.run(ROOT, j)
    assert report['status'] == 'error' and report['physical_calls'] == 0
    assert not report['reference_match']


def test_changed_source_pin_rejected_without_import(jobs):
    j = copy.deepcopy(next(j for j in jobs if j['execution_route'] != 'unsupported'))
    j['sources'][0]['sha256'] = '0'*64
    r = SA6.run(ROOT, j)
    assert r['status'] == 'source_mismatch' and r['physical_calls'] == 0


def _fake_production(monkeypatch, job, *, corrupt=False, converged=True):
    import numpy as np
    model = types.SimpleNamespace(constants=np.array([9.81, 1.2256, 340.21]),
        reference=np.array([[.3871, .254, 1.524], [0, 0, 0], [0, 0, 0], [0, 0, 0]]),
        diagnostics=[], records={'weight': []})
    calls = []
    force, moment = np.array([3., 2., 7.]), np.array([1., -4., 5.])
    qS = .5*1.2256*400*.3871
    a = math.radians(12); c, s = math.cos(a), math.sin(a)
    result = dict(converged=converged, residual=0., panels=64, force=force.tolist(), moment=moment.tolist(),
        strips=[dict(force=force.tolist(), moment=moment.tolist(), position=[0, 0, 0])],
        body_shoulders=[], engines=[], point_forces=[], CL=(-s*force[0]+c*force[2])/qS,
        CD=(c*force[0]+s*force[2])/qS, CY=force[1]/qS,
        Cl=-moment[0]/(qS*1.524), Cm=moment[1]/(qS*.254), Cn=-moment[2]/(qS*1.524),
        CDi_near=0., CDp=0., CDbody=0., CDam=0., CDeng=0., CDrate=0.)
    result['CDp'] = result['CD']
    if corrupt:
        result['CY'] += .1
    asw = types.ModuleType('openswing.asw'); asw.__file__ = str(ROOT/'openswing/asw.py')
    def parse(text, **kwargs):
        assert text == (ROOT/job['model_path']).read_text()
        assert kwargs == {'beam_interpolation': 'natural-v1'}
        return model
    asw.parse_asw = parse
    aero = types.ModuleType('openswing.aero'); aero.__file__ = str(ROOT/'openswing/aero.py')
    aero.FlightCondition = lambda **kw: types.SimpleNamespace(**kw)
    def solve(m, condition, **kw):
        calls.append((m, condition, kw)); return result
    aero.solve_rigid = solve
    package = types.ModuleType('openswing'); package.asw = asw; package.aero = aero
    monkeypatch.setitem(sys.modules, 'openswing', package)
    monkeypatch.setitem(sys.modules, 'openswing.asw', asw)
    monkeypatch.setitem(sys.modules, 'openswing.aero', aero)
    return calls


@pytest.mark.parametrize('variant', SA6.CHORDWISE)
@pytest.mark.parametrize('corrupt,converged', [(False, True), (True, True), (False, False)])
def test_lazy_dispatch_unchanged_inputs_one_call_and_numerical_failures(jobs, monkeypatch, corrupt, converged, variant):
    j = next(j for j in jobs if Path(j['model_path']).stem == 'Straight_Wing_'+variant)
    calls = _fake_production(monkeypatch, j, corrupt=corrupt, converged=converged)
    report = SA6.run(ROOT, j)
    assert len(calls) == report['physical_calls'] == 1
    _, condition, kw = calls[0]
    assert condition.controls == {1: 4.} and condition.density == 1.2256
    assert condition.mach == 0 and condition.alpha == 12 and condition.speed == 20
    assert kw == {'panels': 64, 'circulation_method': 'auto'}
    assert len(report['reference_checks']) == 6
    assert report['status'] == ('computed' if converged and not corrupt else 'numerical_failure')
    assert report['sources_unchanged']
    assert not report['reference_match']  # Arbitrary mock wrench is no archived prediction.
    assert report.get('source_binding') == j.get('source_binding')
    json.dumps(report, allow_nan=False)


def test_postprocessor_retains_complete_matrix_but_adds_no_synthetic_targets(jobs):
    new = [j for j in jobs if j.get('source_binding')]
    text = (ROOT/new[0]['source_binding']['postprocessor_path']).read_text()
    declaration = SA6.decode_postprocessor(text)
    assert len(declaration['rows']) == 12
    assert all(len(row['tokens']) == 17 for row in declaration['rows'])
    assert declaration['rows'][0]['synthetic_zero'] is True
    assert declaration['rows'][0]['line_number'] == 221
    assert [r['control_token'] for r in declaration['rows']] == [str(n) for n in range(0, 45, 4)]
    assert declaration['synthetic_zero_excluded'] is True
    assert declaration['columns_1based'] == {
        '20b_15c': {'Cl': 4, 'Cn': 5}, '20b_20c': {'Cl': 8, 'Cn': 9},
        '20b_30c': {'Cl': 12, 'Cn': 13}, '20b_35c': {'Cl': 16, 'Cn': 17}}
    witnesses = []
    for job in jobs:
        if not job['table_path'] or job['settings']['mesh_level']:
            continue
        variant = Path(job['model_path']).stem.removeprefix('Straight_Wing_')
        row = declaration['rows'][job['reference_row']['operating_point']]
        assert job['settings']['controls'] == {'1': row['control_value']}
        for name, column in declaration['columns_1based'][variant].items():
            assert job['reference_row']['fields'][name]['token'] == row['tokens'][column-1]
            witnesses.append((variant, job['row_index'], name))
    assert len(witnesses) == len(set(witnesses)) == 88
    assert all(job['settings']['controls']['1'] > 0 for job in jobs if job['table_path'])


def test_matlab_binding_keeps_missing_shell_and_all_six_native_targets_explicit(jobs):
    bound = [j for j in jobs if j.get('source_binding')]
    assert len(bound) == 66 and sum(j['expected_outputs'] for j in bound) == 396
    for job in bound:
        binding = job['source_binding']
        assert binding['kind'] == 'original_matlab_control_binding'
        assert binding['missing_original_driver'] is True
        assert binding['producer_execution_authenticated'] is False
        assert job['driver_path'] is job['driver_declarations'] is None
        assert binding['control'] == dict(name='F1', token=str(4*(job['row_index']+1)),
            value=float(4*(job['row_index']+1)), units='degree', source_line=222+job['row_index'],
            source_column_1based=1)
        assert binding['matrix_row_index'] == job['row_index']+1
        assert len(binding['matrix_row_tokens']) == 17
        assert {field['name'] for field in binding['matched_fields']} == {'Cl', 'Cn'}
        assert all(field['token'] == job['reference_row']['fields'][field['name']]['token']
                   for field in binding['matched_fields'])
        assert any(source['path'] == binding['postprocessor_path'] and
                   source['sha256'] == SA6.POSTPROCESSOR_SHA256 for source in job['sources'])
        assert job['required_outputs'] == list(SA6.OUTPUTS)
        assert job['expected_operations'] == {'cold_rigid_calls': 1}
        assert job['complete_family_reproduction'] is False
        assert binding['qualification'] in job['qualifications']
    assert all('source_binding' not in j for j in jobs if j.get('driver_path'))


@pytest.mark.parametrize('change', ['duplicate', 'width', 'control', 'units', 'plot_column', 'variant_label'])
def test_changed_postprocessor_semantics_are_rejected(jobs, change):
    source = next(j['source_binding']['postprocessor_path'] for j in jobs if j.get('source_binding'))
    text = (ROOT/source).read_text()
    if change == 'duplicate':
        text += '\n' + text
    elif change == 'width':
        text = text.replace('0.009420\t-0.002869', '0.009420', 1)
    elif change == 'control':
        text = text.replace('\n24\t0.0460', '\n25\t0.0460', 1)
    elif change == 'units':
        text = text.replace("xlabel('Aileron deflection in deg')", "xlabel('Aileron deflection in rad')")
    elif change == 'plot_column':
        text = text.replace("Clark_Y_Steady_chord(1:end,4),'rs'", "Clark_Y_Steady_chord(1:end,2),'rs'", 1)
    else:
        text = text.replace('= 0.15c,', '= 0.25c,')
    with pytest.raises(ValueError):
        SA6.decode_postprocessor(text)


def test_binding_requires_exact_native_tokens_not_nearby_or_cross_variant_values(jobs):
    job = next(j for j in jobs if j.get('source_binding'))
    text = (ROOT/job['source_binding']['postprocessor_path']).read_text()
    declaration = SA6.decode_postprocessor(text)
    native = (ROOT/job['table_path']).read_text()
    for variant in ('20b_20c', '20b_30c', '20b_35c'):
        with pytest.raises(ValueError, match='tokens do not match exactly'):
            SA6._postprocessor_binding(job['source_binding']['postprocessor_path'], declaration,
                                      variant, job['reference_row'], native)
    modified = copy.deepcopy(declaration)
    modified['rows'][1]['tokens'][3] = '0.0094200'  # Same float, different original token.
    with pytest.raises(ValueError, match='tokens do not match exactly'):
        SA6._postprocessor_binding(job['source_binding']['postprocessor_path'], modified,
                                  '20b_15c', job['reference_row'], native)


@pytest.mark.parametrize('field', ['kind', 'variant', 'missing_driver', 'authenticated',
                                 'token', 'line', 'column', 'path', 'settings', 'extra'])
def test_saved_matlab_binding_verifier_rejects_canonical_tampering(jobs, field):
    job = copy.deepcopy(next(j for j in jobs if j.get('source_binding')))
    binding = job['source_binding']
    if field == 'kind': binding['kind'] = 'inferred'
    elif field == 'variant': binding['variant'] = '20b_35c'
    elif field == 'missing_driver': binding['missing_original_driver'] = False
    elif field == 'authenticated': binding['producer_execution_authenticated'] = True
    elif field == 'token': binding['matched_fields'][0]['token'] = '0.0094200'
    elif field == 'line': binding['control']['source_line'] -= 1
    elif field == 'column': binding['matched_fields'][0]['postprocessor_column_1based'] += 1
    elif field == 'path': binding['postprocessor_path'] = job['table_path']
    elif field == 'settings': job['settings']['controls']['1'] = 8.
    else: job['unreviewed_extra'] = True
    with pytest.raises(ValueError):
        SA6.verify_postprocessor_sources(ROOT, job)


def test_saved_matlab_binding_verifier_allows_only_outer_result(jobs):
    job = copy.deepcopy(next(j for j in jobs if j.get('source_binding')))
    job['result'] = {'status': 'error'}
    assert SA6.verify_postprocessor_sources(ROOT, job) is True
    job['source_binding']['result'] = {'status': 'computed'}
    with pytest.raises(ValueError):
        SA6.verify_postprocessor_sources(ROOT, job)
