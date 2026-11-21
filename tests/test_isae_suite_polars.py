"""Polar decoding, original declaration pairing and refusal paths; no solves."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import types

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('isae_suite_polars', ROOT / 'scripts/isae_suite_polars.py')
POLARS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(POLARS)
HEADER = '# i t alpha Lift Drag CL CD CDi CM span eff.\n'
ROW = '1 1.000 -0.00000 0.00000 99.2303 0.00000 0.117626E-01 -0.00000 0.130565E-01 0.00000\n'
DRIVER = '''#!/bin/sh
/a path/aswing actual_model <<EOF
NODE
I
80

oper
k
I
500
F
!V 89.4
!A
0.016150740242261596
!A 0.29
w
different_table_name.txt
EOF
'''


def test_duplicate_rows_negative_zero_and_printed_precision_are_retained():
    rows = POLARS.decode_polar('# title\n' + HEADER + ROW + ROW)
    assert len(rows) == 2 and [row['row_index'] for row in rows] == [0, 1]
    assert rows[0]['tokens'] == rows[1]['tokens']
    assert rows[0]['fields']['alpha']['token'] == '-0.00000'
    assert rows[0]['fields']['CD'] == {'token': '0.117626E-01', 'value': .0117626, 'tolerance': 5e-8}
    assert rows[0]['fields']['drag']['tolerance'] == 5e-5
    json.dumps(rows, allow_nan=False)


@pytest.mark.parametrize('token, center, half_place', [
    ('-1.200D+02', -120., .05), ('0.00000', 0., 5e-6),
    ('.123e-3', .000123, 5e-7), ('123', 123., .5),
])
def test_decimal_and_fortran_precision(token, center, half_place):
    value = POLARS.printed_value(token)
    assert value['value'] == center
    assert value['tolerance'] == half_place


@pytest.mark.parametrize('bad', ['1 2 3', ROW.replace('99.2303', 'broken'), ROW + 'unexpected footer'])
def test_malformed_rows_are_not_silently_skipped(bad):
    with pytest.raises(ValueError, match='Line'):
        POLARS.decode_polar(HEADER + bad)


def test_headers_are_explicit_and_multiple_tables_rejected():
    assert POLARS.decode_polar('alpha CL CD CDp CM Top_Xtr Bot_Xtr\n0 0 0 0 0 1 1') is None
    assert POLARS.decode_polar(HEADER.replace('CDi', 'CDp') + ROW) is None
    with pytest.raises(ValueError, match='exactly one'):
        POLARS.decode_polar(HEADER + ROW + HEADER + ROW)
    with pytest.raises(ValueError, match='no data'):
        POLARS.decode_polar(HEADER)


@pytest.mark.parametrize('token', ['NaN', '-Inf', '********'])
def test_unavailable_output_is_explicit_and_json_finite(token):
    row = POLARS.decode_polar(HEADER + ROW.replace('99.2303', token))[0]
    assert row['fields']['drag']['value'] is None
    checks = POLARS.reference_checks({name: 0. for name in POLARS.OUTPUTS}, row)
    drag = next(check for check in checks if check['name'] == 'drag')
    assert not drag['passed'] and drag['abs_error'] is None
    assert drag['unavailable_reason']
    json.dumps(checks, allow_nan=False)


def test_driver_output_model_pair_and_node_count_do_not_use_stems_or_oper_k_i():
    driver = POLARS.decode_driver(DRIVER)
    assert driver['model_file'] == 'actual_model.asw'
    assert driver['output_files'] == ['different_table_name.txt']
    assert driver['requested_nodes'] == 80  # OPER K I 500 is an iteration cap.
    assert driver['node_count_token'] == '80'
    assert 'declared_panels' not in driver and 'panel_token' not in driver
    assert driver['speed'] == 89.4
    assert driver['alpha_tokens'] == ['0.016150740242261596', '0.29']


def test_missing_node_mesh_remains_unrecovered():
    driver = POLARS.decode_driver(DRIVER.replace('NODE\nI\n80\n', ''))
    assert driver['requested_nodes'] is None and driver['node_count_token'] is None


@pytest.mark.parametrize('token', ['80', '080', '80.0', '8.0D+01'])
def test_node_request_preserves_original_token_separately_from_circulation_k(token):
    # NODE/K is the separate circulation declaration; OPER/K/I is a solve cap.
    driver = POLARS.decode_driver(DRIVER.replace('NODE\nI\n80', f'NODE\nK\n19\nI\n{token}'))
    assert driver['requested_nodes'] == 80 and driver['node_count_token'] == token
    assert 'declared_panels' not in driver and 'panel_token' not in driver


def test_node_semantics_qualification_is_bound_to_primary_revision_note():
    source = ROOT / '.reference/version_notes.txt'
    if not source.is_file():
        pytest.skip('Optional primary ASWING revision notes are not installed.')
    note = source.read_text().split('Revisions for ASWING v 5.67', 1)[1].split(
        '* Also fixed up the node display plot', 1)[0]
    assert '22 Jan 07' in note
    assert 'minimum number of nodes (one per breakpoint)' in note
    assert 'i command' in note and 'automatically set' in note
    assert 'v5.67' in POLARS.NODE_I_QUALIFICATION
    assert '.reference/version_notes.txt:591-598' in POLARS.NODE_I_QUALIFICATION
    assert POLARS.NODE_I_QUALIFICATION in POLARS.QUALIFICATIONS


@pytest.mark.parametrize('text', [
    DRIVER.replace('!V 89.4', '!V 89.4\n!V 90'),
    DRIVER.replace('!V 89.4', '!V nan'),
    DRIVER.replace('I\n80', 'I\n80.5'),
    DRIVER.replace('I\n80', 'I\n80\nI\n40'),
    DRIVER.replace('actual_model', '$MODEL'),
    DRIVER.replace('different_table_name.txt', '../escape.txt'),
    DRIVER.replace('EOF\n', ''),
])
def test_ambiguous_or_nonliteral_driver_is_rejected(text):
    with pytest.raises(ValueError):
        POLARS.decode_driver(text)


def test_all_seven_fields_use_unwidened_last_place_gate():
    row = POLARS.decode_polar(HEADER + ROW)[0]
    predicted = {name: row['fields'][name]['value'] for name in POLARS.OUTPUTS}
    assert len(POLARS.reference_checks(predicted, row)) == 7
    assert all(check['passed'] for check in POLARS.reference_checks(predicted, row))
    predicted['drag'] += 2 * row['fields']['drag']['tolerance']
    checks = POLARS.reference_checks(predicted, row)
    assert sum(check['passed'] for check in checks) == 6
    predicted['efficiency'] = None
    assert not POLARS.reference_checks(predicted, row)[-1]['passed']


def test_null_point_records_do_not_shift_force_positions_or_modify_originals():
    import numpy as np
    null = np.zeros(17); null[:5] = [1, 9, 99, 77, -55]
    first = np.zeros(17); first[:5] = [1, 0, 0, 0, 4]; first[5] = 1.
    second = np.zeros(17); second[:5] = [1, 0, 1, 2, 3]; second[16] = 1e-300
    rows = [null.copy(), first, null.copy(), second, null.copy()]
    before = np.array(rows).copy()
    model = types.SimpleNamespace(reference=np.zeros((2, 3)), records={'weight': rows})
    result = dict(point_forces=[[0, 5, 0], [2, -1, 4]])
    force, moment, counts = POLARS.reconstructed_wrench(model, result)
    assert np.array_equal(force, [2, 4, 4])
    assert np.array_equal(moment, [-9, 2, -5])
    assert counts['point_forces'] == 2 and counts['omitted_null_point_records'] == 3
    assert np.array_equal(np.array(rows), before)
    result['point_forces'].pop()
    with pytest.raises(ValueError, match='position count mismatch'):
        POLARS.reconstructed_wrench(model, result)


@pytest.mark.parametrize('physical_field', range(5, 17))
def test_any_nonzero_physical_weight_field_keeps_its_force_slot(physical_field):
    import numpy as np
    row = np.zeros(17); row[0] = 1; row[physical_field] = 1e-300
    model = types.SimpleNamespace(reference=np.zeros((2, 3)), records={'weight': [row]})
    with pytest.raises(ValueError, match='position count mismatch'):
        POLARS.reconstructed_wrench(model, dict(point_forces=[]))
    force, _, counts = POLARS.reconstructed_wrench(model, dict(point_forces=[[1, 2, 3]]))
    assert np.array_equal(force, [1, 2, 3]) and counts['point_forces'] == 1
    assert 'omitted_null_point_records' not in counts


def test_current_archived_inventory_is_complete_and_does_not_import_production():
    if not (ROOT / '.reference/isae-validation' / POLARS.REVISION).exists():
        pytest.skip('Original optional ISAE archive is not installed.')
    # A separate interpreter proves both import and planning remain stdlib-only.
    program = '''import importlib.util, json, pathlib, sys
r=pathlib.Path(sys.argv[1]); s=importlib.util.spec_from_file_location('polars',r/'scripts/isae_suite_polars.py')
m=importlib.util.module_from_spec(s);s.loader.exec_module(m);jobs=m.plan(r)
assert not any(n=='openswing' or n.startswith('openswing.') or n in ('numpy','scipy') for n in sys.modules)
print(json.dumps(jobs,allow_nan=False))
'''
    completed = subprocess.run([sys.executable, '-c', program, str(ROOT)], check=True, capture_output=True, text=True, timeout=15)
    jobs = json.loads(completed.stdout)
    assert len(jobs) == 372 and len({job['id'] for job in jobs}) == 372
    assert len({job['table_path'] for job in jobs}) == 10
    assert all(job['expected_outputs'] == 7 and job['settings']['density'] == 1.2256 for job in jobs)
    assert all(job['settings']['mach'] == 0 and not job['settings']['freeze_influences'] for job in jobs)
    coarse = [job for job in jobs if job['row_index'] == 0 and job['settings']['mesh_level'] == 0]
    counts = {Path(job['table_path']).name: job['settings']['panels'] for job in coarse}
    assert counts['SA_1_CL.txt'] == 200
    assert counts['SA_4.txt'] == 80 and counts['SA_4_ASW_CD.txt'] == 20
    assert sum(job['settings']['base_panels'] == 64 for job in coarse) == 4
    for job in jobs:
        declaration, settings = job['driver_declarations'], job['settings']
        assert 'declared_panels' not in declaration and 'panel_token' not in declaration
        assert settings['base_panels'] == (declaration['requested_nodes'] or 64)
        assert settings['panels'] == settings['base_panels'] * 2 ** settings['mesh_level']
        assert 'interval-count reconstruction' in settings['mesh_source']
        assert 'historical node array and circulation K unknown' in settings['mesh_source']
        assert POLARS.NODE_I_QUALIFICATION in job['qualifications']
    sa1 = [job for job in jobs if job['case_id'] == 'SA-1']
    assert len(sa1) == 22 and sum(job['expected_outputs'] for job in sa1) == 154
    assert {job['settings']['panels'] for job in sa1} == {200, 400}
    assert {job['driver_declarations']['requested_nodes'] for job in sa1} == {200}
    assert {job['driver_declarations']['node_count_token'] for job in sa1} == {'200'}
    assert {job['id'] for job in sa1} == {
        f'SA-1:SA_1_CL:row{row:03d}:n{count}' for row in range(11) for count in (200, 400)}
    sa5 = [job for job in jobs if job['case_id'] == 'SA-5' and job['settings']['mesh_level'] == 0]
    assert sa5[0]['reference_row']['tokens'][2:] == sa5[1]['reference_row']['tokens'][2:]
    assert sa5[0]['id'] != sa5[1]['id']


def test_source_pin_failure_cannot_be_reported_as_computed(tmp_path):
    model = tmp_path / 'model.asw'
    model.write_text('original')
    source = POLARS._pin(model, tmp_path)
    model.write_text('changed')
    job = dict(id='changed', case_id='SA-1', adapter='polars', model_path='model.asw',
               table_path='model.asw', driver_path='model.asw', row_index=0,
               expected_outputs=7, settings={}, sources=[source], qualifications=[])
    report = POLARS.run(tmp_path, job)
    assert report['status'] == 'source_mismatch'
    assert not report['reference_match'] and not report['numerical_pass']
    assert report['physical_calls'] == 0 and report['error_type'] == 'ValueError'
    json.dumps(report, allow_nan=False)


@pytest.mark.parametrize('failure', [None, 'convergence', 'residual', 'normalization', 'origin_normalization', 'unavailable_efficiency'])
@pytest.mark.parametrize('moment_reference', [[0., 0., 0.], [.4, .3, -.2]])
def test_stubbed_worker_keeps_numerical_and_reference_gates_separate(tmp_path, monkeypatch, failure, moment_reference):
    # This known wrench is a return-value stub, never a production solver call.
    import numpy as np
    source = tmp_path / 'model.asw'
    source.write_text('pinned literal model placeholder')
    model = types.SimpleNamespace(constants=[9.81, 1., 340.],
        reference=np.array([[2., 3., 4.], [0., 0., 0.]]), diagnostics=[], records={})
    value = dict(converged=True, residual=1e-12, panels=2,
        strips=[dict(position=[0., 0., 0.], force=[.08, 0., .4], moment=[0., .12, 0.])],
        force=[.08, 0., .4], moment=[0., .12, 0.], moment_origin=[0., .12, 0.], CL=.1, CD=.02, Cm=.01, Cm_origin=.01,
        CDi=.006, CDi_near=.005, CDp=.015, CDbody=0., CDam=0., CDeng=0., CDrate=0., efficiency=.8)
    model.reference[1] = moment_reference
    value['moment'] = (np.array(value['moment_origin']) - np.cross(moment_reference, value['force'])).tolist()
    value['Cm'] = value['moment'][1] / 12.
    if failure == 'convergence': value['converged'] = False
    if failure == 'residual': value['residual'] = 1e-5
    if failure == 'normalization': value['CL'] = .2
    if failure == 'origin_normalization': value['Cm_origin'] = .2
    if failure == 'unavailable_efficiency': value['efficiency'] = None
    calls = []
    fake_asw = types.ModuleType('openswing.asw')
    fake_asw.__file__ = str(tmp_path / 'openswing/asw.py')
    fake_asw.parse_asw = lambda source, **kwargs: model
    fake_aero = types.ModuleType('openswing.aero')
    fake_aero.__file__ = str(tmp_path / 'openswing/aero.py')
    fake_aero.FlightCondition = lambda **kwargs: types.SimpleNamespace(**kwargs)
    def solve(*args, **kwargs):
        calls.append((args, kwargs))
        return value
    fake_aero.solve_rigid = solve
    fake_package = types.ModuleType('openswing')
    fake_package.asw, fake_package.aero = fake_asw, fake_aero
    monkeypatch.setitem(sys.modules, 'openswing', fake_package)
    monkeypatch.setitem(sys.modules, 'openswing.asw', fake_asw)
    monkeypatch.setitem(sys.modules, 'openswing.aero', fake_aero)
    settings = dict(panels=2, speed=2., alpha=0., beta=0., density=1., mach=0.,
        freeze_influences=False, stall=True, stall_factor=40., stall_width=.05,
        wake_core_ratio=.25, aero_lag=True, body_added_mass_factor=1., circulation_method='auto')
    row = POLARS.decode_polar(HEADER + '1 1.000 0.000 0.40000 0.08000 0.10000 0.02000 0.00600 0.01000 0.80000\n')[0]
    job = dict(id='stub', case_id='SA-1', adapter='polars', model_path='model.asw',
        table_path='model.asw', driver_path='model.asw', row_index=0, expected_outputs=7,
        settings=settings, sources=[POLARS._pin(source, tmp_path)], qualifications=[], reference_row=row)
    result = POLARS.run(tmp_path, job)
    assert len(calls) == 1 and result['physical_calls'] == 1
    assert len(result['reference_checks']) == 7
    assert result['reference_match'] is (failure is None)
    assert result['numerical_pass'] is (failure in (None, 'unavailable_efficiency'))
    assert result['status'] == ('computed' if failure in (None, 'unavailable_efficiency') else 'numerical_failure')
    if failure == 'unavailable_efficiency':
        assert [x['name'] for x in result['unsupported_outputs']] == ['efficiency']
    json.dumps(result, allow_nan=False)


def test_complete_wrench_includes_shoulders_point_drag_and_engine_arms():
    import numpy as np
    model = types.SimpleNamespace(reference=np.zeros((2, 3)), records={'weight': [[1, 0, 0, 0, 4]]})
    result = {
        'strips': [dict(position=[0, 0, 0], force=[1, 0, 0], moment=[0, 0, 1])],
        'body_shoulders': [dict(position=[0, 2, 0], force=[3, 0, 0], moment=[0, 0, 2])],
        'point_forces': [[0, 5, 0]],
        'engines': [dict(position=[0, 0, 1], force=[0, 2, 0], moment=[1, 0, 0])],
    }
    force, moment, counts = POLARS.reconstructed_wrench(model, result)
    np.testing.assert_array_equal(force, [4, 7, 0])
    np.testing.assert_array_equal(moment, [-21, 0, -3])
    assert counts == dict(strips=1, body_shoulders=1, engines=1, point_forces=1)
    result['point_forces'] = []
    with pytest.raises(ValueError, match='count mismatch'):
        POLARS.reconstructed_wrench(model, result)
