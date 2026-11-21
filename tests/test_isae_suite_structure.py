"""Static-suite catalog/generator tests; no production imports or solves."""
import importlib.util
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('suite_structure', ROOT/'scripts/isae_suite_structure.py')
ADAPTER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ADAPTER)
ORIGINAL = (ROOT/'.reference/isae-validation'/ADAPTER.REVISION/ADAPTER.ST5_RELATIVE/
            'JW_1_30lb_80_20')


@pytest.fixture(scope='module')
def jobs():
    return ADAPTER.plan(ROOT)


@pytest.fixture(scope='module')
def original_target():
    return ADAPTER.decode_st5_original(ROOT)


def test_all_snapshot_rows_fields_and_duplicate_coordinates_are_registered(jobs):
    assert len(jobs) == 17
    assert sum(job['expected_outputs'] for job in jobs) == 97632
    assert [job['rows_per_grid'] for job in jobs] == [45]+[80]*8+[58]*4+[80]*4
    assert [job['outputs_per_row'] for job in jobs] == [8]+[27]*16
    assert [job['case_id'] for job in jobs] == ['ST-3']+['ST-5']*16
    assert all(job['expected_operations'] == dict(cold_solves=3, fresh_residuals=3) for job in jobs)
    json.dumps(jobs, allow_nan=False)


@pytest.mark.parametrize('case', ADAPTER.CASES)
def test_existing_verifier_prepare_matches_declared_grids_without_running(case, jobs, tmp_path):
    job = next(job for job in jobs if job['snapshot'] == case)
    text, _, _ = ADAPTER._generated(ROOT, case)
    if ADAPTER.TARGET_MARKER in text:
        target, _, _ = ADAPTER._target(ROOT, case)
        path = tmp_path/'target.json'
        ADAPTER._write(path, target)
        text = text.replace(ADAPTER.TARGET_MARKER, str(path))
    verifier = tmp_path/'verifier.py'
    verifier.write_text(text)
    module = ADAPTER._load(verifier, 'prepared_'+case.replace('-', '_'))
    # prepare() has no production import or numerical evaluation.
    module.prepare(tmp_path)
    actual = json.loads((tmp_path/'plan.json').read_text())
    assert [m['panels'] for m in actual['meshes']] == [m['panels'] for m in job['grids']]
    assert actual['numerical_gates']['residual'] == 1e-8
    assert actual['cold_solves'] == 3


def test_changed_prepared_snapshot_cannot_run(jobs):
    job = dict(jobs[0], expected_outputs=1)
    with pytest.raises(ValueError, match='expected_outputs'):
        ADAPTER.run(ROOT, job)


def test_new_literal_triplet_is_untouched_and_preserves_original_loads(jobs, original_target):
    # Pin expectations are independent of the decoder and manifest reader.
    expected = {
        '.asw': (13272, '0615f0f6e551a05970d763b2191bd473ba545e61d04726bf9a5b62a9db77c765'),
        '.sh': (189, 'c2677bd1f9b8763f6e459f68f888d589ca5a93a5c96dbb04db4805e483c5fc2e'),
        '.txt': (36109, '1ea62b15605c4402903faceab7a43b2a843fc4f86c8bf649f32502340b1e015b'),
    }
    for suffix, (size, digest) in expected.items():
        raw = ORIGINAL.with_suffix(suffix).read_bytes()
        assert len(raw) == size
        assert hashlib.sha256(raw).hexdigest() == digest
    model = ORIGINAL.with_suffix('.asw').read_text().splitlines()
    assert model[111].split()[:3] == ['*', '3.335', '-24']
    assert model[178].split()[:3] == ['*', '2.001', '-6']
    assert model[172].split()[:3] == ['*', '0.5', '1.1699']
    changes = {(v['beam'], v['property']): v['multiplier']
               for v in original_target['literal_changes_from_20lb80_20']}
    assert changes == {(1, 'Dmg'): -24., (2, 'Dmg'): -6., (2, 'mg'): 1.1699}
    driver = ORIGINAL.with_suffix('.sh').read_text().splitlines()
    assert driver[0].endswith('Aswing_R_5_92/bin/aswing JW_1_30lb_80_20 <<EOF')
    assert driver[1:] == ['oper', 'x', 'k', 'v', '1 4 6 9 10 11 13 14 15 16 17 18 19 20 21 23 24 25 26 ',
                          '', '', 'w', 'JW_1_30lb_80_20.txt', 'O', 'EOF', '', '']
    assert Path(next(j for j in jobs if j['snapshot'] == 'st5-30lb_80_20')['source']) == ORIGINAL.with_suffix('.asw')
    assert next(j for j in jobs if j['snapshot'] == 'st5-30lb_80_20')['settings'] == {'beam_interpolation': 'drela-segspl-v1',
                                    'structural_operator': 'drela-steady-section-v1'}


def test_decoder_retains_every_original_token_and_per_beam_exponents(original_target):
    lines = ORIGINAL.with_suffix('.txt').read_text().splitlines()
    # Extract source rows without the decoder's block/scaling/anchor logic.
    literal = [(i+1, line.split()) for i, line in enumerate(lines)
               if len(line.split()) == 28 and all(re.fullmatch(r'-?\d+\.\d{6}', t) for t in line.split())]
    rows = [r for b in original_target['beams'] for r in b['rows']]
    assert len(literal) == len(rows) == 80
    assert [(r['source_line'], r['raw_tokens']) for r in rows] == literal
    assert [b['row_count'] for b in original_target['beams']] == [44, 36]
    expected_exponents = [
        [0, 0, 0, -1, -1, -3, 0, 1, 0, 1, 1, 1, 1, 0, 0, 0, 0, 0, 0, -4, 3, 0, 0, -1, 0, 1, 0, 0],
        [0, 0, 0, 0, -1, -3, 0, 0, -1, 1, 0, 1, 0, 0, 0, 0, 0, 0, 0, -4, 2, -1, 0, -2, 0, 0, 0, 0],
    ]
    for beam, exponents in zip(original_target['beams'], expected_exponents):
        assert [0]+list(map(int, lines[beam['exponent_line']-1].split())) == exponents
        assert beam['header_exponents'] == exponents
        for row in beam['rows']:
            for j, token in enumerate(row['raw_tokens']):
                multiplier = 10.**exponents[j] if j in (7, 8, 9, 10, 11, 12, 19, 20) else 1.
                assert row['physical'][j] == float(token)*multiplier
                assert beam['printed_half_unit_by_column'][j] == .5e-6*multiplier
    units = [c['physical_unit'] for c in original_target['columns']]
    assert units == ['model t', 'ft', 'ft', 'ft', 'deg', 'deg', 'deg', 'lb*ft', 'lb*ft', 'lb*ft',
                     'lb', 'lb', 'lb', 'ft/s', 'ft/s', 'ft/s', 'deg/s', 'deg/s', 'deg/s', '1',
                     'lb/ft^2', 'ft', '1', '1', 'lb/ft', 'lb/ft', 'deg', 'deg']
    by_line = {r['source_line']: r for r in rows}
    assert by_line[56]['physical'][7:13] == pytest.approx([18.06942, -1.638070, 47.31729,
                                                        17.32093, 12.25924, -17.93833])
    assert by_line[102]['physical'][7:13] == pytest.approx([3.239066, .4532562, 6.30306,
                                                         3.205293, -21.23046, -4.726376])
    # Geometry and input echoes are raw even where a nonzero exponent is printed.
    assert by_line[102]['physical'][4] == 14.657063
    assert by_line[102]['physical'][21:24] == [.2476, 0., -.0322]


def test_duplicate_traces_exact_joint_anchor_and_all_grid_rows_survive(original_target, jobs):
    forward, rear = original_target['beams']
    assert [g['rows'] for g in forward['duplicate_groups']] == [[10, 11], [16, 17], [22, 23], [28, 29], [34, 35]]
    assert [g['rows'] for g in rear['duplicate_groups']] == [[10, 11], [18, 19], [26, 27]]
    assert [forward['rows'][i]['printed_t'] for i in (33, 34)] == [2.000999, 2.000999]
    assert [forward['rows'][i]['exact_anchor_t'] for i in (33, 34)] == [2.001, 2.001]
    assert forward['rows'][21]['raw_tokens'][0] == '-0.000000'
    assert forward['rows'][22]['raw_tokens'][0] == '-0.000000'
    assert forward['rows'][21]['physical'][12] < 0 < forward['rows'][22]['physical'][12]
    assert [g['intervals_by_beam'] for g in next(j for j in jobs if j['snapshot'] == 'st5-30lb_80_20')['grids']] == [
        {'1': 38, '2': 32}, {'1': 76, '2': 64}, {'1': 152, '2': 128}]
    assert next(j for j in jobs if j['snapshot'] == 'st5-30lb_80_20')['expected_outputs'] == 3*80*27
    assert sum(next(j for j in jobs if j['snapshot'] == 'st5-30lb_80_20')['field_groups'].values()) == 80*27
    assert all(r['physical'][j] == 0 for b in original_target['beams'] for r in b['rows']
               for j in (13, 14, 15, 16, 17, 18, 22, 24, 26, 27))
    assert rear['rows'][-1]['physical'][19] != 0 and rear['rows'][-1]['physical'][20] != 0
    assert rear['rows'][-1]['physical'][21:] == [0.]*7


def test_source_body_origin_balance_distinguishes_wrong_export_scaling(original_target):
    # Independent numeric witnesses fixed from original rows56/57/102/103,
    # using primary steady Eq4 rotations and r cross F at each literal root.
    balance = original_target['root_balance_alternatives']
    assert balance['physical']['force_lb'] == pytest.approx(
        [4.939122405289709e-6, 3.984236013110376e-6, 58.07335317036629], abs=1e-11)
    assert balance['physical']['moment_about_body_origin_lbft'] == pytest.approx(
        [-3.554953613477314e-7, -61.576451140361804, -4.8123632967534465e-6], abs=1e-11)
    assert abs(balance['physical']['force_lb'][2]-58.07) <= .005
    assert abs(balance['physical']['moment_about_body_origin_lbft'][1]+61.58) <= .005
    for wrong in ('raw', 'historical_matlab'):
        assert abs(balance[wrong]['force_lb'][2]-58.07) > .005
        assert abs(balance[wrong]['moment_about_body_origin_lbft'][1]+61.58) > .005
    assert original_target['header_force_moment_weight']['Weight']['token'] == '-58.07'


def test_strict_original_disagreements_and_unsupported_display_are_not_repaired(original_target):
    assert original_target['status'] == 'FAIL_RETAINED'
    assert original_target['checks_passed'] == 124 and original_target['checks_total'] == 126
    failed = [c for c in original_target['checks'] if not c['passed']]
    assert [c['name'] for c in failed] == ['beam1:raw root scalar signed weight',
                                         'rear row12:tau propagated printing interval']
    assert failed[0]['original_value'] == 9.485807
    literal_weight = -(1.1699*.2248 - 24*.4062)
    assert failed[0]['literal_value'] == literal_weight
    assert abs(9.485807-literal_weight) > .5e-6
    shell = next(c for c in original_target['rear_shell_interval_checks']
                 if c['row'] == 12 and c['column'] == 'tau')
    assert shell['source_line'] == 96 and shell['value'] == 337.4984
    assert shell['output_half_unit'] == .5e-6*100
    assert shell['value'] > shell['input_interval'][1]+shell['output_half_unit']
    assert shell['overlap'] is False
    assert 'f_reac' in original_target['proposed_comparison']['unsupported_fields']
    assert original_target['input_echo_evidence']['matched_original_tokens'] == 160


def test_original_target_origin_binds_raw_and_decoded_evidence(original_target, jobs):
    origin = next(j for j in jobs if j['snapshot'] == 'st5-30lb_80_20')['target_origin']
    assert origin['decoder'] == 'st5-original-text-v1'
    assert Path(origin['path']) == ORIGINAL.with_suffix('.txt')
    raw = json.dumps(original_target, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
    assert origin['decoded_sha256'] == hashlib.sha256(raw).hexdigest()
    required = {str(ORIGINAL.with_suffix(s)) for s in ('.asw', '.sh', '.txt')}
    assert required <= {p['path'] for p in next(j for j in jobs if j['snapshot'] == 'st5-30lb_80_20')['source_pins']}


@pytest.mark.parametrize('changed', ['manifest', 'original'])
def test_decoder_rejects_mutated_source_without_any_physics(tmp_path, changed):
    cache = tmp_path/'.reference/isae-validation'
    cache.mkdir(parents=True)
    manifest = ROOT/'.reference/isae-validation/manifest.json'
    shutil.copyfile(manifest, cache/'manifest.json')
    if changed == 'manifest':
        (cache/'manifest.json').write_text('{}')
    else:
        (tmp_path/'scripts').mkdir()
        shutil.copyfile(ROOT/'scripts/extract-isae-st5-load-cases.py',
                        tmp_path/'scripts/extract-isae-st5-load-cases.py')
        destination = cache/ADAPTER.REVISION/ADAPTER.ST5_RELATIVE
        destination.mkdir(parents=True)
        (destination/'JW_1_30lb_80_20.asw').write_text('changed original')
    with pytest.raises(ValueError, match='manifest changed|input/export changed'):
        ADAPTER.decode_st5_original(tmp_path)


@pytest.mark.parametrize('case', ADAPTER.ROLLER_CASES + ADAPTER.FORWARD_CASES)
def test_registered_variants_keep_literal_triples_all_rows_and_raw_tokens(case, jobs):
    job = next(j for j in jobs if j['snapshot'] == case)
    target, _, origin = ADAPTER._target(ROOT, case)
    raw = Path(origin['path']).read_text().splitlines()
    literal = [(i+1, line.split()) for i,line in enumerate(raw)
               if len(line.split()) == 28 and all(re.fullmatch(r'-?\d+\.\d{6}', t) for t in line.split())]
    rows = [r for b in target['beams'] for r in b['rows']]
    assert [(r['source_line'], r['raw_tokens']) for r in rows] == literal
    forward = case in ADAPTER.FORWARD_CASES
    assert len(rows) == (58 if forward else 80)
    assert job['expected_outputs'] == 3*len(rows)*27
    assert sum(job['field_groups'].values()) == len(rows)*27
    assert job['field_groups']['unresolved_display_per_grid'] == len(rows)
    assert Path(job['source']) == Path(target['source_pins'][0]['path'])
    assert Path(job['source']).read_bytes() == Path(origin['path']).with_suffix('.asw').read_bytes()
    assert job['settings']['structural_operator'] == 'drela-steady-section-v1'
    assert all(c['passed'] for c in target['source_decoder_diagnostics'])
    if forward:
        assert [g['intervals_by_beam'] for g in job['grids']] == [{'1': n} for n in (38,76,152)]
        assert all('joint' not in (r['anchor_reason'] or '') or 'no joint' in r['anchor_reason'] for r in rows)
        assert len(target['byte_identical_duplicates']) == (6 if 'cosine' in case else 0)
    else:
        assert target['joint_rows'] == [[1.,2.,2.001,2.001,2.], [1.,2.,-2.001,-2.001,2.]]
        assert [g['intervals_by_beam'] for g in job['grids']] == [{'1':38,'2':32},{'1':76,'2':64},{'1':152,'2':128}]


def test_single_job_validation_does_not_redecode_other_snapshots(monkeypatch, jobs):
    wanted = 'st5-forward-elliptical_30lb'
    original = ADAPTER._target
    calls = []
    def selected_only(root, case):
        calls.append(case)
        assert case == wanted
        return original(root, case)
    monkeypatch.setattr(ADAPTER, '_target', selected_only)
    assert ADAPTER.plan(ROOT, snapshots=[wanted]) == [next(j for j in jobs if j['snapshot'] == wanted)]
    assert calls == [wanted]


@pytest.mark.parametrize('case,loads,passed', [
    ('st5-elliptical-20lb_80_20',(-16.,-4.),125),
    ('st5-elliptical-20lb_90_10',(-18.,-2.),125),
    ('st5-elliptical-30lb_80_20',(-24.,-6.),126),
    ('st5-elliptical-30lb_90_10',(-27.,-3.),126),
])
def test_elliptical_originals_keep_load_tables_self_weight_and_source_disagreements(case, loads, passed, jobs):
    job = next(j for j in jobs if j['snapshot'] == case)
    target, _, origin = ADAPTER._target(ROOT, case)
    decoder = ADAPTER._load(ROOT/'scripts/extract-isae-st5-load-cases.py', 'elliptical_test_decoder')
    source = Path(job['source'])
    assert source.parent.name == 'Elliptical_Loading'
    assert source.with_suffix('.txt') == Path(origin['path'])
    tables = decoder.tables(source)
    for beam, multiplier in zip((1,2), loads):
        distributed = decoder.field_table(tables, beam, 'Dmg')
        assert len(distributed['rows']) == 25 and distributed['multiplier'][1] == multiplier
        assert decoder.field_table(tables, beam, 'mg')['multiplier'][1] == 1.1699
    assert target['joint_rows'] == [[1.,2.,2.001,2.001],[1.,2.,-2.001,-2.001]]
    lines = source.with_suffix('.txt').read_text().splitlines()
    literal = [(i+1,line.split()) for i,line in enumerate(lines)
               if len(line.split()) == 28 and all(re.fullmatch(r'-?\d+\.\d{6}',v) for v in line.split())]
    rows = [r for b in target['beams'] for r in b['rows']]
    assert [(r['source_line'],r['raw_tokens']) for r in rows] == literal
    assert len(rows) == 80 and job['expected_outputs'] == 6480
    assert job['field_groups']['unresolved_display_per_grid'] == 80
    assert target['checks_passed'] == passed and target['checks_total'] == 126
    failed = [c for c in target['checks'] if not c['passed']]
    if passed == 125:
        assert target['status'] == 'FAIL_RETAINED'
        assert [c['name'] for c in failed] == ['beam1:raw root scalar signed weight']
        assert abs(failed[0]['original_value']-failed[0]['literal_value']) > .5e-6
    else:
        assert not failed and target['status'] == 'PASS_SOURCE_SUPPORTED_TARGET'
    expected_changes = set() if case.endswith('20lb_80_20') else {(1,'Dmg'),(2,'Dmg')}
    assert {(c['beam'],c['property']) for c in target['literal_changes_from_20lb80_20']} == expected_changes


def test_hash_sharing_is_limited_to_one_plan_and_job_pins_are_independent(tmp_path, monkeypatch):
    (tmp_path/'openswing').mkdir()
    kernel = tmp_path/'openswing/kernel.py'
    kernel.write_text('alpha\n')
    source = tmp_path/'model.asw'
    source.write_text('unchanged model\n')
    (tmp_path/'scripts').mkdir()
    for name in ('verify-source-discrete-integration.py', 'verify-isae-st3-archived-output.py',
                 'isae_st3_static_reference.py', 'verify-isae-st5-archived-output.py', 'verify-isae-st5-load-cases.py'):
        (tmp_path/'scripts'/name).write_text('pass\n')
    original_pin = ADAPTER._pin
    target = dict(source_pins=[original_pin(source)], beams=[dict(row_count=58)])
    monkeypatch.setattr(ADAPTER, '_target', lambda root, case: (target, [], {}))
    monkeypatch.setattr(ADAPTER, '_source', lambda root, case: source)
    monkeypatch.setattr(ADAPTER, '_generated', lambda root, case: ('pass\n', [], ''))
    monkeypatch.setattr(ADAPTER, '_meshes', lambda target, st3: [])
    calls = []
    def count_reads(path):
        calls.append(Path(path))
        return original_pin(path)
    monkeypatch.setattr(ADAPTER, '_pin', count_reads)
    snapshots = ADAPTER.FORWARD_CASES[:2]
    first = ADAPTER.plan(tmp_path, snapshots=snapshots)
    assert calls.count(kernel) == 1
    assert calls.count(source) == 1
    assert first[0]['kernel_pins'] == first[1]['kernel_pins']
    expected = first[1]['kernel_pins'][0]['sha256']
    first[0]['kernel_pins'][0]['sha256'] = 'changed caller object'
    first[0]['source_pins'][0]['sha256'] = 'changed caller object'
    assert first[1]['kernel_pins'][0]['sha256'] == expected
    assert first[1]['source_pins'][0]['sha256'] != 'changed caller object'
    # Even a same-size edit with the old timestamp must be rehashed next time.
    stamp = kernel.stat()
    kernel.write_text('bravo\n')
    os.utime(kernel, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
    second = ADAPTER.plan(tmp_path, snapshots=snapshots)
    assert calls.count(kernel) == 2 and calls.count(source) == 2
    assert second[0]['kernel_pins'][0]['sha256'] == hashlib.sha256(b'bravo\n').hexdigest()
    assert second[0]['kernel_pins'][0]['sha256'] != expected
    # Execution must reject the stale plan before it reaches any verifier.
    with pytest.raises(ValueError, match='kernel_pins'):
        ADAPTER.run(tmp_path, first[1])
    assert calls.count(kernel) == 3
