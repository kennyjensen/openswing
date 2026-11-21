"""Independent summary accounting/merge semantics; no production imports."""
import importlib.util
import json
import math
from copy import deepcopy
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('suite_summary', ROOT / 'scripts/summarize-isae-suite.py')
SUMMARY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SUMMARY)


def check(name, predicted, expected=1., tolerance=.1):
    return dict(name=name, predicted=predicted, expected=expected, tolerance=tolerance,
                passed=predicted is not None and abs(predicted - expected) <= tolerance)


def job(name, checks, required=None, status='computed'):
    required = len(checks) if required is None else required
    result = None if status == 'unrun' else dict(status=status, numerical_pass=status == 'computed',
        reference_match=status == 'computed' and all(row['passed'] for row in checks), reference_checks=checks)
    return dict(id=name, case_id='SA-1', adapter='other', expected_outputs=required, result=result)


def packet(jobs):
    cases = [dict(id=name, path=name, models=[], reference_candidates=[]) for name in sorted(SUMMARY.FAMILIES)]
    catalog = dict(repository='original', revision='frozen', sources=[], models=[], cases=cases,
                   counts=dict(families=41, models=0, parse={}))
    report = dict(repository='original', revision='frozen', runtime={'python': 'same'},
                  current_code_unchanged=True, jobs=jobs,
                  code_sha256={'openswing/a.py': 'kernel', 'scripts/isae_suite_other.py': 'adapter',
                               'scripts/run-isae-suite.py': 'runner-one'})
    return dict(report=report, catalog=catalog)


def test_unavailable_failed_timeout_and_unrun_outputs_keep_distinct_denominators():
    rows = [job('valid', [check('a', 1), check('b', None), check('c', 3, 4)]),
            job('failed', [check('a', 1), check('b', 1)], required=3, status='numerical_failure'),
            job('timeout', [], required=2, status='timeout'), job('unrun', [], required=4, status='unrun')]
    counts = SUMMARY.totals(rows)
    assert counts == dict(required=12, reported=5, finite=4, numerically_valid_finite=2, passed=1,
                         absent=7, reported_unavailable=1, unrun_required=4, failed_job_required=5,
                         unsupported_required=0)
    assert counts['required'] == counts['reported'] + counts['absent']
    assert counts['reported'] == counts['finite'] + counts['reported_unavailable']


@pytest.mark.parametrize('fault', ['duplicate', 'empty', 'wrong_pass', 'wrong_match', 'incomplete'])
def test_invalid_saved_check_contract_is_refused(fault):
    row = job('bad', [check('a', 1), check('b', 2)])
    if fault == 'duplicate': row['result']['reference_checks'][1]['name'] = 'a'
    if fault == 'empty': row['result']['reference_checks'][1]['name'] = ''
    if fault == 'wrong_pass': row['result']['reference_checks'][1]['passed'] = True
    if fault == 'wrong_match': row['result']['reference_match'] = True
    if fault == 'incomplete': row['expected_outputs'] = 3
    with pytest.raises(ValueError): SUMMARY.scalar_counts(row)


def test_merge_never_selects_best_or_drops_duplicate_ids():
    first = packet([job('same', [check('a', 1)])])
    other = packet([job('same', [check('a', 9)])])
    with pytest.raises(ValueError, match='Duplicate job ID'):
        SUMMARY.merge_runs([first, other])


@pytest.mark.parametrize('field', ['kernel', 'helper', 'runtime', 'revision', 'family'])
def test_incompatible_provenance_is_rejected(field):
    first, other = packet([job('one', [check('a', 1)])]), packet([job('two', [check('a', 1)])])
    if field == 'kernel': other['report']['code_sha256']['openswing/a.py'] = 'different'
    if field == 'helper': other['report']['code_sha256']['scripts/isae_suite_other.py'] = 'different'
    if field == 'runtime': other['report']['runtime']['python'] = 'different'
    if field == 'revision': other['catalog']['revision'] = 'different'
    if field == 'family': other['catalog']['cases'].pop()
    with pytest.raises(ValueError): SUMMARY.merge_runs([first, other])


def test_new_orchestration_version_can_add_jobs_without_altering_numerical_helpers():
    first, other = packet([job('one', [check('a', 1)])]), packet([job('two', [check('a', 2)])])
    other['report']['code_sha256']['scripts/run-isae-suite.py'] = 'runner-two'
    merged = SUMMARY.merge_runs([first, other])
    summary = SUMMARY.summarize(merged)
    assert summary['family_count'] == 41 and summary['jobs'] == 2
    assert len(summary['missing_adapters']) == 40
    assert summary['scalar_counts']['passed'] == 1
    assert summary['full_suite_validated'] is False


def polar(index, panels, predicted=1., status='computed'):
    row = job(f'polar-{index}-{panels}', [check(name, predicted) for name in SUMMARY.CHANNELS], status=status)
    row.update(adapter='polars', table_path='original.txt', model_path='original.asw', row_index=index,
        settings={'panels': panels, 'mesh_level': 0 if panels == 4 else 1, 'alpha': 0}, sources=[],
        reference_row={'fields': {name: {'value': 1., 'tolerance': .1} for name in SUMMARY.CHANNELS}})
    if status == 'timeout': row['result']['reference_checks'] = []
    return row


def test_fine_mesh_is_predeclared_even_when_worse_or_failed_and_duplicates_remain():
    jobs = [polar(0, 4, 1.), polar(0, 8, 3.), polar(1, 4, 1.), polar(1, 8, status='timeout')]
    table, = SUMMARY.polar_tables(jobs, {'original.asw': 'N'})
    assert table['fine_panels'] == [8] and table['rows'] == 2
    assert table['scalar_counts']['required'] == 14 and table['scalar_counts']['absent'] == 7
    for name, stat in table['channels'].items():
        assert stat['required_rows'] == 2 and stat['valid_comparison_pairs'] == 1
        assert stat['rmse'] == stat['maximum_absolute_error'] == 2
        assert stat['failed_or_unrun_rows'] == stat['absent_rows'] == 1
        assert stat['unit'] == ('N' if name in ('lift', 'drag') else '1')


def test_additional_mesh_cannot_silently_change_predeclared_pair():
    with pytest.raises(ValueError, match='two declared meshes'):
        SUMMARY.polar_tables([polar(0, 4), polar(0, 8), polar(0, 16)])


def historical_polar(panels, *, index=0):
    row = polar(index, panels)
    row.update(id=f'historical-{index}-{panels}', case_id='SA-7', adapter='extra_polars',
               model_path='historical.asw', required_outputs=list(SUMMARY.CHANNELS),
               target_kind='historical_source_polar', execution_route='historical_seven_fields',
               comparison_scope='supplemental_historical_source_pairing',
               source_pairing=dict(id='sa7-fore-f745fb40', existing_native_targets_reused=True))
    row['result'].update({key: deepcopy(row[key]) for key in ('source_pairing', 'target_kind', 'comparison_scope')})
    return row


def test_polar_summary_keeps_historical_and_current_source_comparisons_separate():
    current = [polar(0, n) for n in (64, 128)]
    for row in current:
        row['case_id'] = 'SA-7'
    rows = current + [historical_polar(n) for n in (64, 128)]
    tables = SUMMARY.polar_tables(rows)
    assert len(tables) == 2
    assert [table['model_path'] for table in tables] == ['original.asw', 'historical.asw']
    assert all(table['rows'] == 1 and table['scalar_counts']['required'] == 7 for table in tables)
    assert tables[1]['existing_native_targets_reused'] is True
    scope = SUMMARY.declared_scope(rows)
    assert scope['supplemental_historical_jobs'] == 2
    assert scope['historical_pairings_reuse_existing_native_targets'] is True
    rendered = SUMMARY.markdown(SUMMARY.summarize(dict(catalog=packet([])['catalog'], jobs=rows,
        runtime={}, kernel_pins={}, helper_pins={}, source_provenance={})))
    assert '[pairing sa7-fore-f745fb40; historical.asw]' in rendered
    assert 'reuse existing native target cells' in rendered
    assert 'historical producing execution and startup state remain unverified' in rendered


@pytest.mark.parametrize('fault', ['pairing', 'scope', 'route', 'kind', 'result', 'family', 'adapter'])
def test_historical_polar_cannot_lose_its_qualification(fault):
    row = historical_polar(64)
    if fault == 'pairing': row['source_pairing']['id'] = 'arbitrary-model'
    if fault == 'scope': row['comparison_scope'] = 'authenticated-original-execution'
    if fault == 'route': row['execution_route'] = 'seven_fields'
    if fault == 'kind': row['target_kind'] = 'native'
    if fault == 'result': row['result'].pop('source_pairing')
    if fault == 'family': row['case_id'] = 'SA-10'
    if fault == 'adapter': row['adapter'] = 'polars'
    with pytest.raises(ValueError): SUMMARY.scalar_counts(row)


def test_original_polar_precision_cannot_be_widened_in_saved_results():
    row = polar(0, 8)
    row['result']['reference_checks'][0]['tolerance'] = 10
    with pytest.raises(ValueError, match='precision gate changed'):
        SUMMARY.scalar_counts(row)


def test_rmse_uses_independent_known_errors_without_relative_near_zero_gate():
    rows = [job('a', [check('x', 3., 0., 0.)]), job('b', [check('x', 4., 0., 0.)])]
    stats = SUMMARY.error_stats(rows, 'x')
    assert stats['rmse'] == 5 / math.sqrt(2)
    assert stats['maximum_absolute_error'] == 4
    assert stats['precision_passed'] == 0


@pytest.fixture
def frozen_run_files(tmp_path):
    root = tmp_path / 'repository'
    (root / 'openswing').mkdir(parents=True)
    (root / 'scripts').mkdir()
    kernel = root / 'openswing/a.py'
    helper = root / 'scripts/isae_suite_other.py'
    kernel.write_text('retained kernel bytes')
    helper.write_text('retained helper bytes')
    item = packet([job('one', [check('a', 1)])])
    report, catalog = item['report'], item['catalog']
    report['code_sha256']['openswing/a.py'] = SUMMARY.pin(kernel)['sha256']
    report['code_sha256']['scripts/isae_suite_other.py'] = SUMMARY.pin(helper)['sha256']
    stage = tmp_path / 'run'
    stage.mkdir()
    plan = dict(catalog=catalog, jobs=[{k: v for k, v in report['jobs'][0].items() if k != 'result'}],
                runtime=report['runtime'], code_sha256=report['code_sha256'])
    for name, value in [('report', report), ('catalog', catalog), ('plan', plan)]:
        (stage / (name + '.json')).write_text(json.dumps(value))
    return root, stage, report, plan


@pytest.mark.parametrize('changed', ['kernel', 'helper', 'plan'])
def test_file_loader_requires_current_code_and_exact_frozen_plan(frozen_run_files, changed):
    root, stage, report, plan = frozen_run_files
    assert len(SUMMARY.load_runs([stage], root)['jobs']) == 1
    if changed == 'kernel': (root/'openswing/a.py').write_text('different numerical kernel')
    if changed == 'helper': (root/'scripts/isae_suite_other.py').write_text('different helper')
    if changed == 'plan':
        plan['jobs'][0]['expected_outputs'] = 2
        (stage / 'plan.json').write_text(json.dumps(plan))
    with pytest.raises(ValueError): SUMMARY.load_runs([stage], root)


@pytest.mark.parametrize('fault', ['none', 'model', 'speed', 'target', 'provenance', 'family'])
def test_historical_summary_rebuilds_canonical_pairing_even_when_plan_and_report_agree(
        frozen_run_files, monkeypatch, fault):
    from scripts import isae_suite_extra_polars
    root, stage, report, plan = frozen_run_files
    row = historical_polar(64)
    row['result'] = None
    canonical = {key: deepcopy(value) for key, value in row.items() if key != 'result'}
    monkeypatch.setattr(isae_suite_extra_polars, 'plan_source_pairing', lambda root, pairing: [canonical])
    helper = root/'scripts/isae_suite_extra_polars.py'
    helper.write_text('historical source adapter fixture')
    report['code_sha256'].pop('scripts/isae_suite_other.py')
    report['code_sha256']['scripts/isae_suite_extra_polars.py'] = SUMMARY.pin(helper)['sha256']
    (root/'historical.asw').write_text('Unit\nF 1 N\nEnd\n')
    if fault == 'model': row['model_path'] = 'arbitrary.asw'
    if fault == 'speed': row['settings']['speed'] = 99.
    if fault == 'target': row['reference_row']['fields']['drag']['value'] = -99.
    if fault == 'provenance': row['source_pairing']['existing_native_targets_reused'] = False
    if fault == 'family': row['case_id'] = 'SA-10'
    report['jobs'] = [row]
    plan['jobs'] = [{key: value for key, value in row.items() if key != 'result'}]
    for name, value in [('report', report), ('plan', plan)]:
        (stage/(name+'.json')).write_text(json.dumps(value))
    if fault == 'none':
        assert len(SUMMARY.load_runs([stage], root)['jobs']) == 1
    else:
        with pytest.raises(ValueError, match='reviewed .*pairing'):
            SUMMARY.load_runs([stage], root)


SELECTION_METADATA = dict(
    execution_policy=dict(adapters=['other'], cases=['SA-1'], job_patterns=['one'], workers=1),
    selection_scope=dict(selected_jobs=1, omitted_jobs_in_requested_adapters=0,
                         families_without_selected_jobs=sorted(SUMMARY.FAMILIES - {'SA-1'})))


@pytest.mark.parametrize('fields', [[], ['execution_policy'], ['execution_policy', 'selection_scope']])
def test_file_loader_accepts_historical_and_current_selection_metadata(frozen_run_files, fields):
    root, stage, report, plan = frozen_run_files
    for saved in (report, plan):
        saved.update({field: deepcopy(SELECTION_METADATA[field]) for field in fields})
    for name, saved in [('report', report), ('plan', plan)]:
        (stage/(name+'.json')).write_text(json.dumps(saved))
    assert len(SUMMARY.load_runs([stage], root)['jobs']) == 1


@pytest.mark.parametrize('field', ['execution_policy', 'selection_scope'])
@pytest.mark.parametrize('fault', ['changed', 'missing_report', 'missing_plan'])
def test_file_loader_rejects_selection_metadata_tampering(frozen_run_files, field, fault):
    root, stage, report, plan = frozen_run_files
    for saved in (report, plan):
        saved.update(deepcopy(SELECTION_METADATA))
    if fault == 'changed':
        if field == 'execution_policy': report[field]['job_patterns'] = ['*']
        else: report[field]['selected_jobs'] = 2
    elif fault == 'missing_report': del report[field]
    else: del plan[field]
    for name, saved in [('report', report), ('plan', plan)]:
        (stage/(name+'.json')).write_text(json.dumps(saved))
    with pytest.raises(ValueError, match=field + ' differs from frozen plan'):
        SUMMARY.load_runs([stage], root)


def test_unsupported_scope_is_separate_from_failures_and_stays_in_denominator():
    unsupported = job('blocked', [check('a', None)], status='unsupported')
    row = SUMMARY.summarize(SUMMARY.merge_runs([packet([unsupported])]))
    family = next(item for item in row['families'] if item['id'] == 'SA-1')
    assert family['status'] == 'DECLARED_SCOPE_UNSUPPORTED'
    assert family['scalar_counts']['required'] == family['scalar_counts']['unsupported_required'] == 1
    assert family['scalar_counts']['reported_unavailable'] == 1
    assert family['scalar_counts']['failed_job_required'] == family['scalar_counts']['passed'] == 0
    mixed = SUMMARY.summarize(SUMMARY.merge_runs([packet([unsupported, job('valid', [check('a', 1.)])])]))
    assert next(item for item in mixed['families'] if item['id'] == 'SA-1')['status'] == 'PARTLY_UNSUPPORTED_SCOPE'
    assert 'explicitly unsupported' in SUMMARY.markdown(mixed)


def extra_polar(index, panels, status='computed'):
    row = polar(index, panels, status=status)
    row.update(case_id='SA-14', adapter='extra_polars', expected_outputs=1, required_outputs=['CL'])
    row['reference_row']['fields'] = {'CL': {'value': 1., 'tolerance': .1}}
    row['result']['reference_checks'] = [check('CL', None if status == 'unsupported' else 1.)]
    row['result']['reference_match'] = status == 'computed'
    return row


@pytest.mark.parametrize('fault', ['scope', 'target', 'tolerance', 'name'])
def test_extra_polar_original_scope_and_precision_cannot_be_changed(fault):
    row = extra_polar(0, 8)
    if fault == 'scope': row['required_outputs'] = ['CD']
    if fault == 'target': row['result']['reference_checks'][0]['expected'] = 0.
    if fault == 'tolerance': row['result']['reference_checks'][0]['tolerance'] = 1.
    if fault == 'name': row['result']['reference_checks'][0]['name'] = 'CD'
    with pytest.raises(ValueError): SUMMARY.scalar_counts(row)


def test_extra_cl_only_table_has_no_fabricated_generic_channels():
    rows = [extra_polar(0, 4), extra_polar(0, 8), extra_polar(1, 4, 'unsupported'), extra_polar(1, 8, 'unsupported')]
    table, = SUMMARY.polar_tables(rows)
    assert set(table['channels']) == {'CL'}
    assert table['rows'] == 2 and table['scalar_counts']['required'] == 2
    assert table['scalar_counts']['unsupported_required'] == 1
    assert table['channels']['CL']['valid_comparison_pairs'] == 1


def dedicated_polar(adapter, index, panels, status='computed', table='original.txt', model='original.asw'):
    channels = SUMMARY.CHANNELS if adapter == 'sa11' else SUMMARY.EXTRA_CHANNELS['SA-12']
    row = polar(index, panels, status=status)
    row.update(id=f'{adapter}:{table}:row{index}:n{panels}', case_id='SA-11' if adapter == 'sa11' else 'SA-12',
               adapter=adapter, expected_outputs=len(channels), required_outputs=list(channels),
               table_path=table, model_path=model, complete_family_reproduction=False)
    row['settings']['mesh_level'] = 0 if panels == 64 else 1
    width, start = (82, 75) if adapter == 'sa11' else (9, 5)
    tokens = [str(index+1), *(['0']*(width-1))]
    tokens[start:] = ['1.0']*len(channels)
    row['reference_row'] = dict(row_index=index, line_number=index+1, tokens=tokens,
        fields={name: dict(token='1.0', value=1., tolerance=.05) for name in channels})
    predicted = None if status == 'unsupported' else 1.
    if row['result'] is not None:
        row['result']['reference_checks'] = [check(name, predicted, tolerance=.05) for name in channels]
    return row


@pytest.mark.parametrize('adapter', ['sa11', 'sa12'])
@pytest.mark.parametrize('fault', ['none', 'family', 'scope', 'count', 'target', 'tolerance', 'name'])
def test_dedicated_polar_scalar_scope_and_original_precision(adapter, fault):
    row = dedicated_polar(adapter, 0, 64)
    if fault == 'family': row['case_id'] = 'SA-14'
    if fault == 'scope': row['required_outputs'][0] = 'CY'
    if fault == 'count': row['expected_outputs'] -= 1
    if fault == 'target': row['result']['reference_checks'][0]['expected'] = 0.
    if fault == 'tolerance': row['result']['reference_checks'][0]['tolerance'] = .5
    if fault == 'name': row['result']['reference_checks'][0]['name'] = 'CY'
    if fault == 'none':
        assert SUMMARY.scalar_counts(row)['passed'] == (7 if adapter == 'sa11' else 4)
    else:
        with pytest.raises(ValueError): SUMMARY.scalar_counts(row)


@pytest.mark.parametrize('adapter', ['sa11', 'sa12'])
@pytest.mark.parametrize('fault', ['none', 'line', 'row', 'token', 'value', 'tolerance', 'column'])
def test_dedicated_polar_targets_bind_to_original_table_columns(tmp_path, adapter, fault):
    row = dedicated_polar(adapter, 0, 64)
    original = row['reference_row']
    (tmp_path/'original.txt').write_text(' '.join(original['tokens'])+'\n')
    name = row['required_outputs'][0]
    if fault == 'line': original['line_number'] = 0
    if fault == 'row': row['row_index'] = 1
    if fault == 'token': original['fields'][name]['token'] = '1.00'
    if fault == 'value': original['fields'][name]['value'] = 2.
    if fault == 'tolerance': original['fields'][name]['tolerance'] = .5
    if fault == 'column':
        original['tokens'][75 if adapter == 'sa11' else 5] = '2.0'
        original['fields'][name]['token'] = '2.0'
        original['fields'][name]['value'] = 2.
    if fault == 'none': SUMMARY.verify_reference_lines(row, tmp_path)
    else:
        with pytest.raises(ValueError): SUMMARY.verify_reference_lines(row, tmp_path)


def test_sa11_and_sa12_full_declared_scope_keeps_blocked_rows_and_mesh_repeats_separate():
    rows = []
    for variant in ('wing_alone', 'wing_extension', 'wingtip_up', 'wingtip_up_and_down'):
        for label in ('0_70', '0_75', '0_78', '0_80'):
            status = 'unsupported' if label in ('0_75', '0_78') or variant.startswith('wingtip_') else 'computed'
            rows.extend(dedicated_polar('sa11', index, panels, status, f'{variant}_{label}.txt', variant+'.asw')
                        for index in range(41) for panels in (64, 128))
    for flap in ('Flap', 'No_Flap'):
        for height in ('05', '2', 'inf'):
            rows.extend(dedicated_polar('sa12', index, panels, table=f'{flap}_{height}.txt', model=flap+'.asw')
                        for index in range(85) for panels in (64, 128))
    item = packet(rows)
    item['report']['code_sha256'].update({'scripts/isae_suite_sa11.py': 'sa11', 'scripts/isae_suite_sa12.py': 'sa12'})
    merged = SUMMARY.merge_runs([item])
    merged['force_units'] = {v+'.asw':'N' for v in ('wing_alone','wing_extension','wingtip_up','wingtip_up_and_down')}
    data = SUMMARY.summarize(merged)
    families = {row['id']: row for row in data['families']}
    sa11, sa12 = families['SA-11'], families['SA-12']
    assert data['jobs'] == 2332 and data['scalar_counts']['required'] == 13264
    assert data['scalar_counts']['passed'] == 6376 and data['scalar_counts']['unsupported_required'] == 6888
    assert sa11['jobs_planned'] == 1312 and sa11['unsupported_jobs'] == 984
    assert sa11['status'] == 'PARTLY_UNSUPPORTED_SCOPE'
    assert sa11['declared_scope']['original_reference_samples'] == 656
    assert sa11['declared_scope']['numerically_valid_reference_samples'] == 164
    assert sa12['jobs_planned'] == 1020 and sa12['unsupported_jobs'] == 0
    assert sa12['declared_scope']['original_reference_samples'] == 510
    assert sa12['declared_scope']['numerically_valid_reference_samples'] == 510
    assert sa11['declared_scope']['unique_model_count']==4
    assert sa12['declared_scope']['unique_model_count']==2
    assert not sa11['complete_family_reproduction'] and not sa12['complete_family_reproduction']
    tables = data['fine_grid_polar_tables']
    assert len(tables) == 22 and all(table['fine_panels'] == [128] for table in tables)
    assert sum(table['rows'] for table in tables) == 1166
    for table in tables:
        channels = SUMMARY.CHANNELS if table['case_id'] == 'SA-11' else SUMMARY.EXTRA_CHANNELS['SA-12']
        assert tuple(table['channels']) == channels
        for name, stat in table['channels'].items():
            assert stat['unit'] == ('N' if name in ('lift', 'drag') else '1')
    rendered = SUMMARY.markdown(data)
    assert '| SA-11 | 2/4 | 164/656 |' in rendered and '| SA-12 | 2/2 | 510/510 |' in rendered
    assert data['full_suite_validated'] is False


def test_historical_extra_sa12_polar_scope_is_still_readable():
    rows = [dedicated_polar('sa12', 0, panels, 'unsupported') for panels in (64, 128)]
    for row in rows: row['adapter'] = 'extra_polars'
    table, = SUMMARY.polar_tables(rows)
    assert tuple(table['channels']) == ('CL', 'CD', 'CDi', 'Cm')
    assert table['scalar_counts']['unsupported_required'] == 4


@pytest.mark.parametrize('adapter', ['sa11', 'sa12'])
def test_dedicated_polar_loader_verifies_source_precision_units_and_helper_pins(tmp_path, adapter):
    root, stage = tmp_path/'repository', tmp_path/'run'
    (root/'openswing').mkdir(parents=True); (root/'scripts').mkdir(); stage.mkdir()
    (root/'openswing/a.py').write_text('retained kernel bytes')
    helper = root/f'scripts/isae_suite_{adapter}.py'
    helper.write_text('retained adapter bytes')
    (root/'original.asw').write_text('Unit\n F 1 N\nEnd\n')
    rows = [dedicated_polar(adapter, 0, panels) for panels in (64, 128)]
    (root/'original.txt').write_text(' '.join(rows[0]['reference_row']['tokens'])+'\n')
    sources = [dict(SUMMARY.pin(root/name), path=name) for name in ('original.asw', 'original.txt')]
    for row in rows: row['sources'] = sources
    item = packet(rows); report, catalog = item['report'], item['catalog']
    report['code_sha256'] = {name: SUMMARY.pin(root/name)['sha256'] for name in
                            ('openswing/a.py', f'scripts/isae_suite_{adapter}.py')}
    plan = dict(catalog=catalog, jobs=[{k: v for k, v in row.items() if k != 'result'} for row in rows],
                runtime=report['runtime'], code_sha256=report['code_sha256'])
    for name, value in [('report', report), ('catalog', catalog), ('plan', plan)]:
        (stage/(name+'.json')).write_text(json.dumps(value))
    loaded = SUMMARY.load_runs([stage], root)
    assert loaded['force_units'] == {'original.asw': 'N'}
    assert SUMMARY.polar_tables(loaded['jobs'], loaded['force_units'])[0]['rows'] == 1
    helper.write_text('changed adapter')
    with pytest.raises(ValueError, match='Current adapter/helper differs'): SUMMARY.load_runs([stage], root)


def structure_job(snapshot):
    st3 = snapshot.startswith('st3')
    return dict(id=snapshot, case_id='ST-3' if st3 else 'ST-5', adapter='structure', snapshot=snapshot,
                rows_per_grid=45 if st3 else 80, outputs_per_row=8 if st3 else 27,
                expected_outputs=1080 if st3 else 6480, grids=[{'level': level} for level in range(3)])


def test_st3_full_original_rows_scales_and_two_sided_exact_attachment_contract():
    target = json.loads((ROOT/'docs/validation/isae-st3-reference-target.json').read_text())
    row = structure_job('st3-m15_0')
    contract = SUMMARY.structure_contract(row, target)
    assert len(contract) == 1080
    root = contract['grid0:row000:Mc_prime_Nm']
    assert root['expected'] == -.0207 and root['tolerance'] == 5e-5 and root['trace'] == 'right'
    duplicates = [i for i, item in enumerate(target['rows']) if item['physical_values'][0] == .335]
    for i, side in zip(duplicates, ['left', 'right']):
        item = contract[f'grid2:row{i:03d}:y_m']
        assert item['t_printed'] == .335 and math.isclose(item['t_evaluated'], .3348, rel_tol=0., abs_tol=1e-16) and item['trace'] == side
    row['_summary_reference_contract'] = contract
    name, target_check = next(iter(contract.items()))
    check = dict(name=name, predicted=target_check['expected'], passed=True, **target_check)
    row['result'] = dict(status='numerical_failure', reference_match=False, reference_checks=[check])
    assert SUMMARY.scalar_counts(row)['reported'] == 1
    check['trace'] = 'left'
    with pytest.raises(ValueError, match='coordinate/trace'): SUMMARY.scalar_counts(row)


@pytest.mark.parametrize('snapshot', ['st5-20lb_80_20', 'st5-20lb_90_10', 'st5-30lb_90_10'])
def test_st5_all_original_rows_and_printed_gates_decode_without_solver(snapshot):
    row = structure_job(snapshot)
    if snapshot == 'st5-20lb_80_20':
        path = ROOT/'docs/validation/isae-st5-reference-target.json'
        row['target_origin'] = SUMMARY.pin(path)
    else:
        audit = json.loads((ROOT/'docs/validation/isae-st5-load-cases-source-audit.json').read_text())
        name = 'JW_1_' + snapshot[4:] + '-target.json'
        source = next(item for item in audit['targets'] if Path(item['path']).name == name)
        row['target_origin'] = dict(archive=str(ROOT/'docs/validation/isae-st5-load-cases-20261026-evidence.zip'),
                                    member='source-audit/'+name, bytes=source['bytes'], sha256=source['sha256'])
    contract = SUMMARY.load_structure_contract(row, ROOT)
    assert len(contract) == 6480 and len({name.split(':')[1] for name in contract}) == 80
    assert all(item['tolerance'] > 0 for item in contract.values())
    row['_summary_reference_contract'] = contract
    name, original = next(iter(contract.items()))
    check = dict(name=name, predicted=original['expected'], passed=True, **original)
    row['result'] = dict(status='numerical_failure', reference_match=False, reference_checks=[check])
    assert SUMMARY.scalar_counts(row)['reported'] == 1
    check['tolerance'] *= 2
    with pytest.raises(ValueError, match='precision gate'): SUMMARY.scalar_counts(row)


def modal_job(status='computed'):
    row = dict(id='mode', case_id='ST-4', adapter='modes', execution_route='local_vacuum',
               expected_outputs=3, grid_counts=[16, 32, 64], required_components=['imaginary'],
               reference_rows=[dict(line=4, raw_tokens=['1', '0.000E+00', '1.234E+02'],
                                    operating_point=1, eigenvalue=[0., 123.4], half_printed_units=[.0005, .05])])
    checks = [dict(name=f'n{n}:row0001:imaginary', predicted=123.4, expected=123.4, tolerance=.05,
                   expected_token='1.234E+02', source_line=4, operating_point=1, units='1/s', passed=True)
              for n in (16, 32, 64)]
    row['result'] = dict(status=status, numerical_pass=True, reference_match=True, reference_checks=checks)
    return row


@pytest.mark.parametrize('fault', ['none', 'component', 'value', 'tolerance', 'coordinate', 'unit'])
def test_modal_selected_frequency_scope_and_original_precision(fault):
    row = modal_job()
    if fault == 'component': row['required_components'] = ['real', 'imaginary']
    if fault == 'value': row['reference_rows'][0]['eigenvalue'][1] = 123.45
    if fault == 'tolerance': row['result']['reference_checks'][0]['tolerance'] = .1
    if fault == 'coordinate': row['result']['reference_checks'][0]['operating_point'] = 2
    if fault == 'unit': row['result']['reference_checks'][0]['units'] = 'Hz'
    if fault == 'none':
        assert SUMMARY.scalar_counts(row)['passed'] == 3
    else:
        with pytest.raises(ValueError): SUMMARY.scalar_counts(row)


def no_target_job(status):
    row = dict(id='unpaired', case_id='ST-4', adapter='modes', expected_outputs=0,
               blocker_code='NO_PAIRED_EXPORT', execution_route='unsupported', model_path='original.asw',
               table_path=None, reference_rows=[], required_components=[],
               expected_operations={'cold_bridge_calls': 0}, unsupported_reason='No paired export.')
    row['result'] = None if status == 'unrun' else dict(status=status, reference_match=False, reference_checks=[])
    return row


@pytest.mark.parametrize('status,expected', [('unrun', 'INCOMPLETE_RUN'), ('unsupported', 'DECLARED_SCOPE_UNSUPPORTED'),
                                         ('source_mismatch', 'NUMERICAL_OR_INPUT_FAILURES')])
def test_zero_target_inventory_uses_job_completion_not_scalar_zero(status, expected):
    row = no_target_job(status)
    item = packet([row]); item['report']['code_sha256']['scripts/isae_suite_modes.py'] = 'modes'
    data = SUMMARY.summarize(SUMMARY.merge_runs([item]))
    family = next(item for item in data['families'] if item['id'] == 'ST-4')
    assert family['status'] == expected and family['model_inventory_jobs_without_targets'] == 1
    assert data['scalar_counts']['required'] == data['scalar_counts']['passed'] == 0
    assert data['model_inventory_without_targets'][0]['status'] == status


def test_zero_target_record_cannot_be_a_computed_pass_or_unqualified_empty_job():
    row = no_target_job('computed')
    row['result'].update(numerical_pass=True, reference_match=True)
    with pytest.raises(ValueError, match='inventory'): SUMMARY.scalar_counts(row)
    row = job('empty', [], required=0, status='unsupported')
    with pytest.raises(ValueError, match='Zero scalar'): SUMMARY.scalar_counts(row)


def test_aeroelastic_four_original_tokens_include_explicit_nan_without_fabrication():
    channels = SUMMARY.AE_CHANNELS['AE-2']
    observations = [dict(name=name, original_name=name, token='NaN', expected=None, tolerance=None,
                         missing=True, source_line=4, source_column_1based=i+3) for i, name in enumerate(channels)]
    row = dict(id='ae', case_id='AE-2', adapter='aeroelastic', expected_outputs=4,
               observations=observations, reference_row={'raw_tokens': ['1', '0', *(['NaN']*4)]},
               result=dict(status='unsupported', reference_match=False,
                   reference_checks=[dict(item, predicted=None, passed=False) for item in observations]))
    counts = SUMMARY.scalar_counts(row)
    assert counts['reported_unavailable'] == counts['unsupported_required'] == 4
    row['result']['reference_checks'][0]['expected'] = 0.
    with pytest.raises(ValueError, match='Original target'): SUMMARY.scalar_counts(row)


@pytest.mark.parametrize('fault', ['none', 'value', 'tolerance', 'column'])
def test_aeroelastic_original_printing_and_four_channel_scope(fault):
    observations = [dict(name=name, original_name=name, token='1.230', expected=1.23, tolerance=.0005,
                         missing=False, source_line=4, source_column_1based=i+3)
                    for i, name in enumerate(SUMMARY.AE_CHANNELS['FFWT-1'])]
    row = dict(id='ff', case_id='FFWT-1', adapter='aeroelastic', expected_outputs=4, observations=observations,
               reference_row={'raw_tokens': ['1', '0', *(['1.230']*4)]},
               result=dict(status='computed', numerical_pass=True, reference_match=True,
                   reference_checks=[dict(item, predicted=1.23, passed=True) for item in observations]))
    if fault == 'value': row['observations'][0]['expected'] = 1.24
    if fault == 'tolerance': row['result']['reference_checks'][0]['tolerance'] = .005
    if fault == 'column': row['observations'][0]['source_column_1based'] = 4
    if fault == 'none': assert SUMMARY.scalar_counts(row)['passed'] == 4
    else:
        with pytest.raises(ValueError): SUMMARY.scalar_counts(row)


def test_aggregate_aswing_cells_are_storage_candidates_not_experimental_targets(tmp_path):
    source = tmp_path/'original.csv'
    source.write_text('Weight;Position;Vf_Asw;fb1_Asw;fb2_Asw;ft_Asw;ff_Asw;experiment\n7A;17;2.30;NC;;4.00;5.00;999\n')
    targets = []
    for column, label, token, expected, tolerance in [(3, 'Vf_Asw', '2.30', 2.3, .005),
            (4, 'fb1_Asw', 'NC', None, None), (5, 'fb2_Asw', '', None, None),
            (6, 'ft_Asw', '4.00', 4., .005), (7, 'ff_Asw', '5.00', 5., .005)]:
        targets.append(dict(name='row2:'+label, source_line=2, column_1based=column, weight_label='7A',
            position_token='17', raw_token=token, expected=expected, tolerance=tolerance,
            units='m/s' if label == 'Vf_Asw' else 'Hz',
            precision_scope='Stored cell token only; spreadsheet storage precision is not a recovered ASWING print format.'))
    row = dict(adapter='modes', case_id='ST-4', execution_route='unsupported', expected_outputs=5,
               table_path=str(source), reference_rows=[], required_components=[], aggregate_targets=targets)
    SUMMARY.verify_reference_lines(row, tmp_path)
    assert len(SUMMARY.modes_contract(row)) == 5
    targets[-1]['raw_token'] = '999'
    with pytest.raises(ValueError, match='stored cell'): SUMMARY.verify_reference_lines(row, tmp_path)


@pytest.fixture(scope='module')
def sa6_plan():
    path = Path('/tmp/openswing-isae-suite-sa6-preparation-20261026/plan.json')
    if not path.exists():
        pytest.skip('Optional frozen SA6 preparation is absent.')
    return json.loads(path.read_text())['jobs']


def test_sa6_independent_target_contract_and_original_source_lines(sa6_plan):
    for original in sa6_plan:
        row = dict(original)
        SUMMARY.verify_reference_lines(row, ROOT)
        assert len(SUMMARY.sa6_contract(row)) == row['expected_outputs']
        assert SUMMARY.scalar_counts(row)['required'] == row['expected_outputs']


@pytest.mark.parametrize('fault', ['token', 'precision', 'axis', 'control'])
def test_sa6_changes_to_original_targets_or_control_pairing_are_rejected(sa6_plan, fault):
    row = json.loads(json.dumps(next(j for j in sa6_plan if j['execution_route'] != 'unsupported')))
    if fault == 'token': row['reference_row']['fields']['CL']['token'] = '1.169828'
    if fault == 'precision': row['reference_row']['fields']['CL']['tolerance'] = .1
    if fault == 'axis': row['required_outputs'][0] = 'CD'
    if fault == 'control': row['settings']['controls']['1'] = -4.
    with pytest.raises(ValueError):
        SUMMARY.verify_reference_lines(row, ROOT)
        SUMMARY.sa6_contract(row)


def test_sa6_coverage_counts_original_samples_not_mesh_repeats(sa6_plan):
    rows = json.loads(json.dumps(sa6_plan))
    for row in rows:
        active = row['execution_route'] != 'unsupported'
        # Deliberately synthetic complete outputs test accounting, not physics.
        contract = SUMMARY.sa6_contract(row)
        row['result'] = dict(status='computed' if active else 'unsupported', numerical_pass=active,
            reference_match=active, reference_checks=[dict(name=name, **ref,
                predicted=ref['expected'] if active else None, passed=active) for name, ref in contract.items()])
    item = packet(rows); item['report']['code_sha256']['scripts/isae_suite_sa6.py'] = 'sa6'
    data = SUMMARY.summarize(SUMMARY.merge_runs([item]))
    family = next(row for row in data['families'] if row['id'] == 'SA-6')
    assert family['status'] == 'PARTLY_UNSUPPORTED_SCOPE'
    assert family['declared_scope']['unique_model_count'] == 4
    assert family['declared_scope']['models_with_numerical_results'] == 1
    assert family['declared_scope']['original_reference_samples'] == 44
    assert family['declared_scope']['numerically_valid_reference_samples'] == 11
    assert family['model_inventory_jobs_without_targets'] == 3
    assert data['scalar_counts']['required'] == 528 and data['scalar_counts']['passed'] == 132
    assert len(data['fine_grid_sa6_coefficients']) == 4
    assert all(table['rows'] == 11 and table['fine_panels'] == [128] for table in data['fine_grid_sa6_coefficients'])
    rendered = SUMMARY.markdown(data)
    assert 'not a validation or completion percentage' in rendered
    assert 'jobs are execution units, not distinct cases' in rendered
    assert '| SA-6 | 1/4 | 11/44 |' in rendered


def test_sa6_zero_target_inventory_cannot_pass_as_computed(sa6_plan):
    row = json.loads(json.dumps(next(j for j in sa6_plan if j['expected_outputs'] == 0)))
    row['result'] = dict(status='computed', numerical_pass=True, reference_match=True, reference_checks=[])
    with pytest.raises(ValueError, match='inventory'): SUMMARY.scalar_counts(row)


@pytest.fixture(scope='module')
def sa6_current_plan():
    if not (ROOT/'.reference/isae-validation/manifest.json').is_file():
        pytest.skip('Optional original ISAE archive unavailable')
    from scripts import isae_suite_sa6
    return isae_suite_sa6.plan(ROOT)


def test_sa6_postprocessor_scope_retains_all_original_targets(sa6_plan, sa6_current_plan):
    old = {row['id']: row for row in sa6_plan}
    assert set(old) == {row['id'] for row in sa6_current_plan}
    assert sum(row['expected_outputs'] for row in sa6_current_plan) == 528
    bound = [row for row in sa6_current_plan if SUMMARY.sa6_postprocessor(row)]
    assert len(bound) == 66
    for row in sa6_current_plan:
        previous = old[row['id']]
        for field in ('model_path', 'table_path', 'row_index', 'expected_outputs', 'required_outputs'):
            assert row[field] == previous[field]
        assert row.get('reference_row') == previous.get('reference_row')
        if SUMMARY.sa6_postprocessor(row):
            SUMMARY.verify_reference_lines(row, ROOT)
            assert row['settings']['controls'] == {'1': float(4*(row['row_index']+1))}
        assert len(SUMMARY.sa6_contract(row)) == row['expected_outputs']


@pytest.mark.parametrize('fault', ['control', 'model', 'target', 'binding', 'family', 'adapter', 'missing_binding', 'removed_binding_adapter'])
def test_sa6_postprocessor_summary_rejects_changed_pairing(sa6_current_plan, fault):
    row = deepcopy(next(row for row in sa6_current_plan if SUMMARY.sa6_postprocessor(row)))
    if fault == 'control': row['settings']['controls']['1'] = -4.
    if fault == 'model': row['model_path'] = row['model_path'].replace('15c', '20c')
    if fault == 'target': row['reference_row']['fields']['Cl']['token'] = '0.000000'
    if fault == 'binding': row['source_binding']['producer_execution_authenticated'] = True
    if fault == 'family': row['case_id'] = 'SA-10'
    if fault == 'adapter': row['adapter'] = 'other'
    if fault == 'missing_binding': row.pop('source_binding')
    if fault == 'removed_binding_adapter':
        row.pop('source_binding'); row['adapter'] = 'other'
    with pytest.raises(ValueError):
        SUMMARY.scalar_counts(row)
        SUMMARY.verify_reference_lines(row, ROOT)
        SUMMARY.sa6_contract(row)


@pytest.mark.parametrize('fault', ['none', 'control', 'source_binding', 'family', 'adapter', 'removed_binding_adapter'])
def test_sa6_loader_checks_canonical_postprocessor_job_when_plan_and_report_agree(
        frozen_run_files, sa6_current_plan, monkeypatch, fault):
    from scripts import isae_suite_sa6
    root, stage, report, plan = frozen_run_files
    row = deepcopy(next(row for row in sa6_current_plan if SUMMARY.sa6_postprocessor(row)))
    row['sources'] = []
    original = deepcopy(row)
    calls = []
    def canonical(actual_root):
        calls.append(actual_root)
        return [deepcopy(original)]
    monkeypatch.setattr(isae_suite_sa6, 'plan', canonical)
    helper = root/'scripts/isae_suite_sa6.py'
    helper.write_text('postprocessor adapter fixture')
    # Keep the generic adapter pinned so a coordinated relabel cannot pass
    # merely because an earlier missing-helper check happens to reject it.
    report['code_sha256']['scripts/isae_suite_sa6.py'] = SUMMARY.pin(helper)['sha256']
    if fault == 'control': row['settings']['controls']['1'] += 4.
    if fault == 'source_binding': row['source_binding']['variant'] = '20b_30c'
    if fault == 'family': row['case_id'] = 'SA-10'
    if fault == 'adapter': row['adapter'] = 'other'
    if fault == 'removed_binding_adapter':
        row.pop('source_binding'); row['adapter'] = 'other'
    report['jobs'] = [dict(row, result=None)]
    plan['jobs'] = [row]
    for name, value in [('report', report), ('plan', plan)]:
        (stage/(name+'.json')).write_text(json.dumps(value))
    if fault == 'none':
        merged = SUMMARY.load_runs([stage], root)
        assert calls == [root]
        assert len(merged['jobs']) == 1
    else:
        with pytest.raises(ValueError, match='source binding|original sources'):
            SUMMARY.load_runs([stage], root)


def test_sa6_summary_labels_shell_and_postprocessor_control_sources(sa6_current_plan):
    rows = deepcopy(sa6_current_plan)
    for row in rows:
        active = row['execution_route'] != 'unsupported'
        contract = SUMMARY.sa6_contract(row)
        row['result'] = dict(status='computed' if active else 'unsupported', numerical_pass=active,
            reference_match=active, reference_checks=[dict(name=name, **ref,
                predicted=ref['expected'] if active else None, passed=active) for name, ref in contract.items()])
        if SUMMARY.sa6_postprocessor(row):
            row['result']['source_binding'] = deepcopy(row['source_binding'])
    item = packet(rows)
    item['report']['code_sha256']['scripts/isae_suite_sa6.py'] = 'sa6'
    data = SUMMARY.summarize(SUMMARY.merge_runs([item]))
    family = next(row for row in data['families'] if row['id'] == 'SA-6')
    assert family['declared_scope']['models_with_numerical_results'] == 4
    assert family['declared_scope']['numerically_valid_reference_samples'] == 44
    assert family['model_inventory_jobs_without_targets'] == 3
    assert data['scalar_counts']['required'] == data['scalar_counts']['passed'] == 528
    sources = [row['control_source'] for row in data['fine_grid_sa6_coefficients']]
    assert sources.count('Original shell driver') == 1
    assert sources.count('Original MATLAB postprocessor; original shell driver absent') == 3
    rendered = SUMMARY.markdown(data)
    assert 'do not recover the missing shell drivers or authenticate historical startup' in rendered
    assert 'three model/driver pairings remain unsupported' not in rendered


def test_sa6_computed_result_must_retain_postprocessor_qualification(sa6_current_plan):
    row = deepcopy(next(row for row in sa6_current_plan if SUMMARY.sa6_postprocessor(row)))
    contract = SUMMARY.sa6_contract(row)
    row['result'] = dict(status='computed', numerical_pass=True, reference_match=True,
        reference_checks=[dict(name=name, **ref, predicted=ref['expected'], passed=True)
                          for name, ref in contract.items()])
    with pytest.raises(ValueError, match='lost its postprocessor'):
        SUMMARY.scalar_counts(row)
    row['result']['source_binding'] = deepcopy(row['source_binding'])
    assert SUMMARY.scalar_counts(row)['passed'] == 6


@pytest.fixture(scope='module')
def st2_records():
    if not (ROOT/'.reference/isae-validation/manifest.json').is_file():
        pytest.skip('Optional original ISAE archive unavailable')
    from scripts import isae_suite_st2
    rows = isae_suite_st2.plan(ROOT)
    for row in rows:
        row['result'] = (isae_suite_st2.validate_blocked(ROOT, row)
                         if row['execution_route'] == 'unsupported' else None)
    return rows


def st2_packet(rows):
    item = packet(rows)
    item['report']['code_sha256']['scripts/isae_suite_st2.py'] = 'st2-adapter'
    item['report']['code_sha256']['scripts/isae_st2_archive.py'] = 'st2-archive-parser'
    item['report']['code_sha256']['scripts/isae_suite_st2_modal.py'] = 'st2-modal-helper'
    family = next(case for case in item['catalog']['cases'] if case['id'] == 'ST-2')
    family['models'] = [row['model_path'] for row in rows if row['target_kind'] == 'model_inventory']
    return item


def test_st2_native_rows_workbook_cells_and_six_models_are_separate_source_scopes(st2_records):
    data = SUMMARY.summarize(SUMMARY.merge_runs([st2_packet(st2_records)]))
    family = next(row for row in data['families'] if row['id'] == 'ST-2')
    assert family['status'] == 'INCOMPLETE_RUN' and family['jobs_planned'] == 17 and family['unsupported_jobs'] == 9
    assert family['original_models'] == family['model_inventory_jobs_without_targets'] == 6
    scope = family['declared_scope']
    assert scope['original_reference_samples'] == 70 and scope['native_reference_samples'] == 60
    assert scope['native_scalar_targets'] == 396 and scope['qualified_workbook_cells'] == scope['qualified_workbook_scalar_targets'] == 10
    assert scope['native_scalar_slots'] == 480 and scope['modal_reference_roots'] == 14
    assert scope['modal_distinct_scalar_targets'] == 28 and scope['conditional_modal_jobs'] == 8
    assert scope['conditional_modal_scalar_slots'] == 112 and scope['blocked_scalar_slots'] == 378
    assert scope['literal_model_inventory_records'] == 6 and scope['unique_model_count'] == 3
    assert scope['models_with_numerical_results'] == scope['numerically_valid_reference_samples'] == 0
    assert data['scalar_counts'] == dict(required=490, reported=378, finite=0, numerically_valid_finite=0,
        passed=0, absent=112, reported_unavailable=378, unrun_required=112, failed_job_required=0, unsupported_required=378)
    assert 'ST-2' not in data['missing_adapters'] and not data['full_suite_validated']
    assert len(data['model_inventory_without_targets']) == 6
    rendered = SUMMARY.markdown(data)
    assert '| ST-2 | 0/3 | 0/70 | 9/17 |' in rendered
    assert '60 native rows / 396 native scalar targets' in rendered
    assert '10 separately qualified workbook cells' in rendered
    assert 'Static, workbook and inventory routes remain blocked' in rendered
    assert 'Local ordinal root comparisons' in rendered


@pytest.mark.parametrize('kind', ['native_static', 'workbook_summary', 'model_inventory'])
@pytest.mark.parametrize('claim', ['computed', 'match', 'numerical', 'physical_call'])
def test_st2_summary_cannot_promote_blocked_records_to_validation(st2_records, kind, claim):
    row = deepcopy(next(row for row in st2_records if row['target_kind'] == kind))
    if claim == 'computed': row['result']['status'] = 'computed'
    if claim == 'match': row['result']['reference_match'] = True
    if claim == 'numerical': row['result']['numerical_pass'] = True
    if claim == 'physical_call': row['result']['physical_calls'] = 1
    with pytest.raises(ValueError, match='ST2 blocked registration'):
        SUMMARY.scalar_counts(row)


@pytest.mark.parametrize('fault', ['target', 'precision', 'coordinate', 'token', 'component', 'prediction', 'partial'])
def test_st2_saved_static_result_retains_full_original_contract(st2_records, fault):
    row = deepcopy(next(row for row in st2_records if row['target_kind'] == 'native_static'))
    result = row['result']
    if fault == 'target': result['reference_checks'][0]['expected'] = 2.
    if fault == 'precision': result['reference_checks'][0]['tolerance'] *= 10
    if fault == 'coordinate': result['reference_checks'][0]['coordinate_token'] = '0'
    if fault == 'token': result['reference_checks'][0]['expected_token'] = '0'
    if fault == 'component': row['required_components'].pop()
    if fault == 'prediction': result['reference_checks'][0]['predicted'] = 0.
    if fault == 'partial': result['reference_checks'].pop()
    with pytest.raises(ValueError):
        SUMMARY.scalar_counts(row)


@pytest.mark.parametrize('status,expected', [('unrun', 'INCOMPLETE_RUN'),
    ('unsupported', 'DECLARED_SCOPE_UNSUPPORTED'), ('source_mismatch', 'NUMERICAL_OR_INPUT_FAILURES')])
def test_st2_zero_target_model_record_completion_remains_required(st2_records, status, expected):
    row = deepcopy(next(row for row in st2_records if row['target_kind'] == 'model_inventory'))
    if status == 'unrun': row['result'] = None
    else: row['result']['status'] = status
    data = SUMMARY.summarize(SUMMARY.merge_runs([st2_packet([row])]))
    family = next(row for row in data['families'] if row['id'] == 'ST-2')
    assert family['status'] == expected and family['model_inventory_jobs_without_targets'] == 1
    assert data['scalar_counts']['required'] == 0


def test_st2_loader_binds_result_to_pinned_original_source_rows(tmp_path, st2_records):
    row = deepcopy(next(row for row in st2_records if row['target_kind'] == 'native_static'))
    item = st2_packet([row])
    report, catalog = item['report'], item['catalog']
    paths = [*sorted((ROOT/'openswing').glob('*.py')), ROOT/'scripts/isae_suite_st2.py',
             ROOT/'scripts/isae_st2_archive.py', ROOT/'scripts/isae_suite_st2_modal.py']
    report['code_sha256'] = {path.relative_to(ROOT).as_posix(): SUMMARY.pin(path)['sha256'] for path in paths}
    plan = dict(catalog=catalog, jobs=[{key: value for key, value in row.items() if key != 'result'}],
                runtime=report['runtime'], code_sha256=report['code_sha256'])
    for name, value in [('report', report), ('catalog', catalog), ('plan', plan)]:
        (tmp_path/(name+'.json')).write_text(json.dumps(value))
    merged = SUMMARY.load_runs([tmp_path], ROOT)
    assert len(merged['jobs'][0]['_summary_reference_contract']) == 368
    assert SUMMARY.scalar_counts(merged['jobs'][0])['unsupported_required'] == 368
    # Alter plan and result consistently: only binding to the original catches
    # the invented physical source line after token arithmetic still agrees.
    for saved in (report['jobs'][0], plan['jobs'][0]):
        saved['reference_rows'][0]['line_number'] = 99
        saved['target_profile']['rows'][0]['line_number'] = 99
        for obs in saved['observations'][:8]: obs['source_line'] = 99
    for check in report['jobs'][0]['result']['reference_checks'][:8]: check['source_line'] = 99
    for name, value in [('report', report), ('plan', plan)]:
        (tmp_path/(name+'.json')).write_text(json.dumps(value))
    with pytest.raises(ValueError, match='original sources'):
        SUMMARY.load_runs([tmp_path], ROOT)


@pytest.fixture(scope='module')
def ap1_records():
    if not (ROOT/'.reference/isae-validation/manifest.json').is_file():
        pytest.skip('Optional original ISAE archive unavailable')
    from scripts import isae_suite_ap1
    rows = isae_suite_ap1.plan(ROOT)
    for row in rows:
        if row['execution_route'] == 'unsupported':
            row['result'] = isae_suite_ap1.validate_blocked(ROOT, row)
        else:
            # Synthetic complete headers exercise accounting, not physics.
            contract = isae_suite_ap1.reference_contract(row)
            physical = []
            for name in isae_suite_ap1.REQUIRED_PHYSICAL_CHECKS:
                spec = isae_suite_ap1.PHYSICAL_CHECK_SPECS[name]
                check = dict(name=name, passed=True)
                if spec['metric'] is not None:
                    check.update({spec['metric']: 0., 'gate': row['numerical_gates'][spec['gate']]})
                else:
                    expected = deepcopy(spec.get('expected', {'fixture': 'same operator identity'}))
                    check.update(actual=deepcopy(expected), expected=expected)
                if name.startswith('independent_header_'):
                    output = name.removeprefix('independent_header_')
                    check.update(reported=contract[output]['expected'], reconstructed=contract[output]['expected'])
                elif name.startswith('independent_'):
                    check.update(reported=[0., 0., 0.], reconstructed=[0., 0., 0.])
                elif name in ('force_balance', 'moment_balance'):
                    check.update(applied=[0., 0., 0.], support=[0., 0., 0.])
                elif name == 'restored_header_parity':
                    values = {name: reference['expected'] for name, reference in contract.items()}
                    check.update(reported=values, restored=dict(values), channels={name: 0. for name in values})
                physical.append(check)
            row['result'] = dict(status='computed', numerical_pass=True, reference_match=True,
                source_pins_unchanged=True, kernel_pins_unchanged=True,
                physical_checks=physical,
                operations=dict(cold_solves=1, fresh_residuals=1, retries=0), physical_calls=2,
                reference_checks=[dict(name=name, **reference, predicted=reference['expected'],
                    abs_error=0., passed=True, comparison='<=') for name, reference in contract.items()])
    return rows


def ap1_packet(rows):
    item = packet(rows)
    item['report']['code_sha256']['scripts/isae_suite_ap1.py'] = 'ap1-adapter'
    return item


def test_ap1_header_agreement_never_counts_as_span_validation(ap1_records):
    data = SUMMARY.summarize(SUMMARY.merge_runs([ap1_packet(ap1_records)]))
    family = next(row for row in data['families'] if row['id'] == 'AP-1')
    assert family['status'] == 'PARTLY_UNSUPPORTED_SCOPE' and family['jobs_planned'] == family['jobs_finished'] == 26
    assert family['unsupported_jobs'] == 20 and family['model_inventory_jobs_without_targets'] == 0
    counts = family['scalar_counts']
    assert counts['required'] == counts['reported'] == 15470
    assert counts['passed'] == counts['numerically_valid_finite'] == counts['finite'] == 78
    assert counts['unsupported_required'] == counts['reported_unavailable'] == 15392
    scope = family['declared_scope']
    assert scope['original_reference_samples'] == 1001 and scope['span_reference_samples'] == 1000
    assert scope['operating_reference_samples'] == 1 and scope['header_reference_states'] == 7
    assert scope['paired_header_scalar_targets'] == 156
    assert scope['numerically_valid_header_reference_states'] == 3
    assert scope['numerically_valid_reference_samples'] == scope['numerically_valid_span_reference_samples'] == 0
    assert scope['numerically_valid_operating_reference_samples'] == 0
    assert 'AP-1' not in data['missing_adapters'] and not family['complete_family_reproduction']
    assert 'supplied runs' in data['definitions']['missing_adapters']
    assert data['ap1_mesh_diagnostics']
    rendered = SUMMARY.markdown(data)
    assert '1000 distinct span rows and 1 operating rows' in rendered
    assert '3 header/state records and 0 span rows have numerical results' in rendered
    assert 'header agreement does not validate blocked span recovery' in rendered
    assert 'Families not covered by these supplied runs:' in rendered
    assert 'still lack a current comparison adapter' not in rendered


@pytest.mark.parametrize('fault', ['physical_false', 'physical_absent', 'physical_missing', 'physical_duplicate',
    'physical_unknown', 'metric_failed', 'recorded_gate', 'plan_gate', 'wrench_metric', 'wrench_missing',
    'header_metric', 'source', 'kernel', 'residual', 'retry', 'physical_calls', 'value', 'precision'])
def test_ap1_computed_header_requires_physics_provenance_and_original_target(ap1_records, fault):
    row = deepcopy(next(row for row in ap1_records if row['execution_route'] == 'worker'))
    result = row['result']
    if fault == 'physical_false': result['physical_checks'][0]['passed'] = False
    if fault == 'physical_absent': result['physical_checks'] = []
    if fault == 'physical_missing': result['physical_checks'].pop()
    if fault == 'physical_duplicate': result['physical_checks'][-1] = deepcopy(result['physical_checks'][0])
    if fault == 'physical_unknown': result['physical_checks'][0]['name'] = 'invented'
    residual = next((check for check in result['physical_checks'] if check['name'] == 'fresh_full_residual'), None)
    if fault == 'metric_failed': residual['maximum'] = row['numerical_gates']['residual']*2
    if fault == 'recorded_gate': residual['gate'] *= 10
    if fault == 'plan_gate': row['numerical_gates']['residual'] *= 10
    wrench = next((check for check in result['physical_checks'] if check['name'].startswith('independent_') and
                   not check['name'].startswith('independent_header_')), None)
    if fault == 'wrench_metric': wrench['reported'][0] = 1.
    if fault == 'wrench_missing': wrench.pop('reported')
    if fault == 'header_metric':
        next(check for check in result['physical_checks'] if check['name'] == 'independent_header_Lift')['reconstructed'] += 1
    if fault == 'source': result['source_pins_unchanged'] = False
    if fault == 'kernel': result['kernel_pins_unchanged'] = False
    if fault == 'residual': result['operations']['fresh_residuals'] = 0
    if fault == 'retry': result['operations']['retries'] = 1
    if fault == 'physical_calls': result['physical_calls'] = 1
    if fault == 'value': result['reference_checks'][0]['expected'] += 1
    if fault == 'precision': result['reference_checks'][0]['tolerance'] *= 10
    with pytest.raises(ValueError):
        SUMMARY.scalar_counts(row)


@pytest.mark.parametrize('kind', ['paired_header', 'paired_span', 'unpaired_span_and_header', 'unpaired_operating'])
@pytest.mark.parametrize('claim', ['computed', 'match', 'prediction', 'operations'])
def test_ap1_blocked_scope_rejects_numerical_claims(ap1_records, kind, claim):
    row = deepcopy(next(row for row in ap1_records if row['target_kind'] == kind and row['execution_route'] == 'unsupported'))
    if claim == 'computed': row['result']['status'] = 'computed'
    if claim == 'match': row['result']['reference_match'] = True
    if claim == 'prediction': row['result']['reference_checks'][0]['predicted'] = 0.
    if claim == 'operations': row['result']['operations']['cold_solves'] = 1
    with pytest.raises(ValueError, match='AP1 blocked route'):
        SUMMARY.scalar_counts(row)


def test_ap1_unrun_and_failed_header_results_do_not_hide_span_scope(ap1_records):
    rows = deepcopy(ap1_records)
    workers = [row for row in rows if row['execution_route'] == 'worker']
    workers[0]['result'] = None
    workers[1]['result'] = dict(status='timeout', reference_match=False, reference_checks=[])
    data = SUMMARY.summarize(SUMMARY.merge_runs([ap1_packet(rows)]))
    family = next(row for row in data['families'] if row['id'] == 'AP-1')
    assert family['status'] == 'INCOMPLETE_RUN'
    assert family['scalar_counts']['unrun_required'] == family['scalar_counts']['failed_job_required'] == 13
    assert family['scalar_counts']['unsupported_required'] == 15392
    assert family['declared_scope']['original_reference_samples'] == 1001


def test_ap1_summary_source_verification_rejects_changed_pairing(ap1_records):
    row = deepcopy(next(row for row in ap1_records if row['execution_route'] == 'worker'))
    SUMMARY.verify_reference_lines(row, ROOT)
    row['model_path'] = 'invented-model.asw'
    with pytest.raises(ValueError):
        SUMMARY.verify_reference_lines(row, ROOT)


def test_selected_matches_cannot_claim_full_suite_or_family_reproduction():
    row = job('selected', [check('a', 1.)])
    row['complete_family_reproduction'] = True
    row['result'].update(full_suite_validated=True, complete_family_reproduction=True)
    item = packet([row])
    item['report']['full_suite_validated'] = True
    item['catalog']['models'] = [dict(path=f'synthetic-{i}', bytes=1, sha256=str(i)) for i in range(279)]
    item['catalog']['counts']['models'] = 279
    result = SUMMARY.summarize(SUMMARY.merge_runs([item]))
    assert result['family_count'] == 41 and result['source_inventory_separate_from_output_counts']['models'] == 279
    assert result['full_suite_validated'] is False
    assert all(family['complete_family_reproduction'] is False for family in result['families'])
    assert sum(family['status'] == 'NO_COMPARISON_JOBS_IN_SUPPLIED_RUNS' for family in result['families']) == 40
    assert 'have no comparison jobs in the supplied runs' in SUMMARY.markdown(result)


@pytest.fixture(scope='module')
def expanded_structure_plan():
    if not (ROOT/'.reference/isae-validation/manifest.json').is_file():
        pytest.skip('Optional original ISAE archive unavailable')
    from scripts import isae_suite_structure
    return isae_suite_structure.plan(ROOT)


def test_st5_new_original_text_scope_keeps_all_three_grids_and_source_identity(expanded_structure_plan):
    row = next(row for row in expanded_structure_plan if row['snapshot'] == 'st5-30lb_80_20')
    assert row['id'] == 'ST5-30LB_80_20-static-three-grids' and row['expected_outputs'] == 6480
    contract = SUMMARY.load_structure_contract(row, ROOT)
    assert len(contract) == 6480 and len({key.split(':')[1] for key in contract}) == 80
    assert {key.split(':')[0] for key in contract} == {'grid0', 'grid1', 'grid2'}
    saved = dict(row, _summary_reference_contract=contract)
    assert SUMMARY.scalar_counts(saved)['unrun_required'] == 6480
    scope = SUMMARY.declared_scope([saved])
    assert scope['original_reference_samples'] == 80 and scope['unique_model_count'] == 1


@pytest.mark.parametrize('fault', ['raw_hash', 'decoded_hash', 'decoder', 'snapshot', 'column_count'])
def test_st5_text_target_tampering_rejected(expanded_structure_plan, fault):
    row = deepcopy(next(row for row in expanded_structure_plan if row['snapshot'] == 'st5-30lb_80_20'))
    if fault == 'raw_hash': row['target_origin']['sha256'] = '0'*64
    if fault == 'decoded_hash': row['target_origin']['decoded_sha256'] = '0'*64
    if fault == 'decoder': row['target_origin']['decoder'] = 'invented'
    if fault == 'snapshot': row['snapshot'] = 'st5-invented'
    if fault == 'column_count': row['outputs_per_row'] -= 1
    with pytest.raises(ValueError):
        SUMMARY.load_structure_contract(row, ROOT)


@pytest.mark.parametrize('suffix', ['.asw', '.sh', '.mat'])
def test_st5_text_target_cannot_be_relabelled_as_another_valid_pinned_source(expanded_structure_plan, suffix):
    row = deepcopy(next(row for row in expanded_structure_plan if row['snapshot'] == 'st5-30lb_80_20'))
    original = Path(row['target_origin']['path'])
    replacement = SUMMARY.pin(original.with_suffix(suffix))
    assert replacement in row['source_pins']
    # Preserve the correct canonical decoded target hash and use real original
    # bytes/hash: only the exact export identity distinguishes this mutation.
    row['target_origin'].update(replacement)
    with pytest.raises(ValueError, match='original .txt export'):
        SUMMARY.load_structure_contract(row, ROOT)


@pytest.mark.parametrize('snapshot,rows', [
    ('st5-roller-'+name,80) for name in ('20lb_80_20','20lb_90_10','30lb_80_20','30lb_90_10')
] + [('st5-forward-'+name,58) for name in ('cosine_20lb','cosine_30lb','elliptical_20lb','elliptical_30lb')]
  + [('st5-elliptical-'+name,80) for name in ('20lb_80_20','20lb_90_10','30lb_80_20','30lb_90_10')])
def test_original_variant_contract_retains_every_grid_row_and_unresolved_column(expanded_structure_plan, snapshot, rows):
    job = deepcopy(next(j for j in expanded_structure_plan if j['snapshot'] == snapshot))
    contract = SUMMARY.load_structure_contract(job, ROOT)
    assert len(contract) == 3*rows*27
    assert len([k for k in contract if k.endswith(':f_reac')]) == 3*rows
    assert {k.split(':')[0] for k in contract} == {'grid0','grid1','grid2'}
    assert len({k.split(':')[1] for k in contract}) == rows
    job['_summary_reference_contract'] = contract
    assert SUMMARY.scalar_counts(job)['unrun_required'] == 3*rows*27
    # A valid hash of the wrong paired model must not masquerade as its output.
    job['target_origin'].update(SUMMARY.pin(Path(job['target_origin']['path']).with_suffix('.asw')))
    with pytest.raises(ValueError, match='original .txt export'):
        SUMMARY.load_structure_contract(job, ROOT)


@pytest.fixture(scope='module')
def expanded_ae2_plan():
    if not (ROOT/'.reference/isae-validation/manifest.json').is_file():
        pytest.skip('Optional original ISAE archive unavailable')
    from scripts import isae_suite_aeroelastic
    return isae_suite_aeroelastic.plan(ROOT)


def test_coupled_ae2_rows_are_counted_once_across_both_meshes(expanded_ae2_plan):
    rows = [row for row in expanded_ae2_plan if row['id'].startswith(('AE-2-m15_02-', 'AE-2-p15_02-'))]
    assert len(rows) == 368 and sum(row['expected_outputs'] for row in rows) == 1472
    assert sum(row['execution_route'] == 'unsupported' for row in rows) == 16
    assert all(len(SUMMARY.aeroelastic_contract(row)) == 4 for row in rows)
    scope = SUMMARY.declared_scope(rows)
    assert scope['original_reference_samples'] == 184 and scope['unique_model_count'] == 2
    assert SUMMARY.totals(rows)['unrun_required'] == 1472
    for prefix in ('AE-2-m15_02-', 'AE-2-p15_02-'):
        selected = [row for row in rows if row['id'].startswith(prefix)]
        for row in (selected[0], selected[-1]):
            SUMMARY.verify_reference_lines(row, ROOT)
    assert len(expanded_ae2_plan) == 566 and sum(row['expected_outputs'] for row in expanded_ae2_plan) == 2264


def synthetic_ap2_result(row):
    """Complete saved-evidence shape for accounting tests; no physics is run."""
    from scripts import isae_suite_ap2
    contract = isae_suite_ap2.reference_contract(row)
    values = dict(CL=contract.get('CL', contract['CL_CD_ratio'])['expected'],
                  CD=contract.get('CD', {'expected': 1.})['expected'])
    values['CL_CD_ratio'] = values['CL']/values['CD']
    expected = dict(same_operator_identity={'fixture': 'same retained operator identity'},
        restore_without_evaluation=0, one_restored_residual=1, converged=True,
        source_policy=dict(numerics=deepcopy(isae_suite_ap2.POLICY),
                           operator=isae_suite_ap2.POLICY['structural_operator'], launch=False),
        two_shared_power_engines=[dict(power=330., clipped=False)]*2,
        literal_reference_normalization=[.1536, .24, .64], root_clamp_count=1,
        finite_outputs={name: True for name in isae_suite_ap2.CHANNELS})
    physical = []
    for name, spec in isae_suite_ap2.PHYSICAL_CHECK_SPECS.items():
        item = dict(name=name, passed=True)
        if spec['kind'] == 'exact':
            item.update(actual=deepcopy(expected[name]), expected=deepcopy(expected[name]))
        else:
            item.update(metric=0., gate=row['numerical_gates'][spec['gate']])
            if spec['kind'] == 'independent':
                channel = name.removeprefix('independent_')
                value = values[channel] if channel in values else [0., 0., 0.]
                item.update(reported=deepcopy(value), reconstructed=deepcopy(value))
            elif spec['kind'] == 'balance':
                item.update(applied=[0., 0., 0.], support=[0., 0., 0.])
            elif spec['kind'] == 'parity':
                item.update(reported=dict(values), restored=dict(values), channels={name: 0. for name in values})
            if name == 'engine_position_error':
                positions = [[float(token) for token in row['source_row']['engine_tokens'][key][4:7]]
                             for key in ('positive', 'negative')]
                item.update(reported=deepcopy(positions), expected=deepcopy(positions))
        physical.append(item)
    checks = [dict(name=name, **reference, predicted=values[name],
                   abs_error=abs(values[name]-reference['expected']),
                   passed=abs(values[name]-reference['expected']) <= reference['tolerance'], comparison='<=')
              for name, reference in contract.items()]
    return dict(id=row['id'], case_id='AP-2', adapter='ap2', target_kind='grid_state',
        status='computed', numerical_pass=True, reference_match=all(item['passed'] for item in checks),
        source_pins_unchanged=True, kernel_pins_unchanged=True, physical_checks=physical,
        operations=dict(cold_solves=1, fresh_residuals=1, retries=0), physical_calls=2,
        reference_checks=checks)


@pytest.fixture(scope='module')
def ap2_records():
    if not (ROOT/'.reference/isae-validation/manifest.json').is_file():
        pytest.skip('Optional original ISAE archive unavailable')
    from scripts import isae_suite_ap2
    rows = isae_suite_ap2.plan(ROOT)
    for row in rows:
        row['result'] = (isae_suite_ap2.validate_blocked(ROOT, row) if row['execution_route'] == 'unsupported'
                         else synthetic_ap2_result(row))
    return rows


def ap2_packet(rows):
    item = packet(rows)
    item['report']['code_sha256'].update({'scripts/isae_suite_ap2.py': 'ap2-adapter',
                                        'scripts/isae_suite_ap1.py': 'ap2-header-recovery-helper'})
    return item


def test_ap2_grid_cells_csv_witnesses_and_unpaired_rows_keep_separate_denominators(ap2_records):
    data = SUMMARY.summarize(SUMMARY.merge_runs([ap2_packet(ap2_records)]))
    family = next(row for row in data['families'] if row['id'] == 'AP-2')
    scope = family['declared_scope']
    assert family['jobs_planned'] == family['jobs_finished'] == 237
    assert family['status'] == 'PARTLY_UNSUPPORTED_SCOPE' and family['unsupported_jobs'] == 3
    assert family['scalar_counts']['required'] == family['scalar_counts']['reported'] == 248
    assert family['scalar_counts']['numerically_valid_finite'] == 242
    assert family['scalar_counts']['unsupported_required'] == family['scalar_counts']['reported_unavailable'] == 6
    assert scope['original_reference_samples'] == 120 and scope['numerically_valid_reference_samples'] == 117
    assert scope['mat_grid_cells'] == scope['numerically_valid_mat_grid_cells'] == 117
    assert scope['final_csv_witness_states'] == scope['numerically_valid_final_csv_witness_states'] == 2
    assert scope['unpaired_operating_rows'] == 3 and scope['numerically_valid_unpaired_operating_rows'] == 0
    assert scope['mat_binary_identity_scalar_targets'] == 234
    assert scope['final_csv_printed_scalar_targets'] == 8 and scope['unpaired_txt_scalar_targets'] == 6
    assert len(data['ap2_mesh_diagnostics']) == 117
    assert all(row['status'] == 'COMPARED' and row['passed'] is None and row['acceptance_gate'] is None
               for row in data['ap2_mesh_diagnostics'])
    assert data['family_count'] == 41 and len(data['missing_adapters']) == 40
    assert not data['full_suite_validated'] and not family['complete_family_reproduction']
    rendered = SUMMARY.markdown(data)
    assert 'MAT zero-tolerance identity is not original print precision' in rendered
    assert '2 final-state CSV witnesses' in rendered


@pytest.mark.parametrize('fault', ['missing_check', 'duplicate_check', 'metric', 'gate', 'calls', 'operations',
                                  'source', 'kernel', 'prediction', 'output_binding', 'ratio_binding',
                                  'engine_expected', 'engine_metric', 'reference_metadata'])
def test_ap2_computed_result_requires_complete_bound_physical_evidence(ap2_records, fault):
    row = deepcopy(next(row for row in ap2_records if row['execution_route'] == 'worker'))
    result = row['result']; physical = {item['name']: item for item in result['physical_checks']}
    if fault == 'missing_check': result['physical_checks'].pop()
    if fault == 'duplicate_check': result['physical_checks'][-1] = deepcopy(result['physical_checks'][0])
    if fault == 'metric': physical['fresh_full_residual']['metric'] = 1.
    if fault == 'gate': row['numerical_gates']['residual'] = 1.
    if fault == 'calls': result['physical_calls'] = 1
    if fault == 'operations': result['operations']['retries'] = 1
    if fault == 'source': result['source_pins_unchanged'] = False
    if fault == 'kernel': result['kernel_pins_unchanged'] = False
    if fault in ('prediction', 'ratio_binding'):
        check = next(item for item in result['reference_checks'] if item['name'] == 'CL_CD_ratio')
        check['predicted'] += 1.
        check.update(abs_error=abs(check['predicted']-check['expected']), passed=False)
        result['reference_match'] = False
    if fault == 'output_binding':
        physical['independent_CL']['reported'] += 1.
        physical['independent_CL']['reconstructed'] += 1.
    if fault == 'ratio_binding':
        for key in ('reported', 'reconstructed'): physical['independent_CL_CD_ratio'][key] += 1.
        for key in ('reported', 'restored'): physical['restored_output_parity'][key]['CL_CD_ratio'] += 1.
    if fault == 'engine_expected':
        for key in ('reported', 'expected'): physical['engine_position_error'][key][0][0] += 1.
    if fault == 'engine_metric': physical['engine_position_error']['reported'][0][0] += 1.
    if fault == 'reference_metadata': result['reference_checks'][0]['precision_scope'] = 'Invented print accuracy'
    with pytest.raises(ValueError): SUMMARY.scalar_counts(row)


@pytest.mark.parametrize('claim', ['computed', 'numerical', 'match', 'prediction', 'physical_calls'])
def test_ap2_unpaired_exports_cannot_claim_computation_or_matches(ap2_records, claim):
    row = deepcopy(next(row for row in ap2_records if row['execution_route'] == 'unsupported'))
    result = row['result']
    if claim == 'computed': result['status'] = 'computed'
    if claim == 'numerical': result['numerical_pass'] = True
    if claim == 'match': result['reference_match'] = True
    if claim == 'prediction': result['reference_checks'][0]['predicted'] = 0.
    if claim == 'physical_calls': result['physical_calls'] = 1
    with pytest.raises(ValueError): SUMMARY.scalar_counts(row)


@pytest.mark.parametrize('fault', ['condition', 'coordinate', 'mat_precision', 'generated_source'])
def test_ap2_original_sources_reject_altered_setup_or_grid_contract(ap2_records, fault):
    row = deepcopy(next(row for row in ap2_records if row['execution_route'] == 'worker'))
    if fault == 'condition': row['condition']['speed'] += 1.
    if fault == 'coordinate': row['reference_rows'][0]['grid_column'] += 1
    if fault == 'mat_precision': row['observations'][0]['tolerance'] = 1e-6
    if fault == 'generated_source': row['source_row']['generated_source_sha256'] = '0'*64
    with pytest.raises(ValueError): SUMMARY.verify_reference_lines(row, ROOT)


def test_ap2_loader_rebuilds_source_and_reference_contract_without_physics(tmp_path, ap2_records):
    row = deepcopy(next(row for row in ap2_records if row['execution_route'] == 'worker'))
    item = ap2_packet([row]); report, catalog = item['report'], item['catalog']
    paths = [*sorted((ROOT/'openswing').glob('*.py')), ROOT/'scripts/isae_suite_ap2.py', ROOT/'scripts/isae_suite_ap1.py']
    report['code_sha256'] = {path.relative_to(ROOT).as_posix(): SUMMARY.pin(path)['sha256'] for path in paths}
    plan = dict(catalog=catalog, jobs=[{key: value for key, value in row.items() if key != 'result'}],
                runtime=report['runtime'], code_sha256=report['code_sha256'])
    for name, value in [('report', report), ('catalog', catalog), ('plan', plan)]:
        (tmp_path/(name+'.json')).write_text(json.dumps(value))
    merged = SUMMARY.load_runs([tmp_path], ROOT)
    assert merged['jobs'][0]['_summary_reference_contract'] == SUMMARY.ap2_contract(row)
    assert SUMMARY.scalar_counts(merged['jobs'][0])['numerically_valid_finite'] == 1
    for saved in (report['jobs'][0], plan['jobs'][0]): saved['condition']['speed'] += 1.
    for name, value in [('report', report), ('plan', plan)]:
        (tmp_path/(name+'.json')).write_text(json.dumps(value))
    with pytest.raises(ValueError, match='original sources'):
        SUMMARY.load_runs([tmp_path], ROOT)


def synthetic_ae1_result(row):
    """Complete synthetic sensor evidence for accounting, with no solved state."""
    from scripts import isae_suite_ae1 as adapter
    angle = math.radians(11.); c, s = math.cos(angle), math.sin(angle)
    tip = dict(beam=1, t=.55, position=[0.,.54,.02], jig_position=[0.,.55,0.],
               rotation=[[c,0.,s],[0.,1.,0.],[-s,0.,c]])
    sensors = adapter.reconstruct_sensors([tip]); values = adapter.sensor_values(sensors)
    expected = adapter._expectations(row)
    physical = []
    for name, spec in adapter.PHYSICAL_CHECK_SPECS.items():
        item = dict(name=name, passed=True)
        if spec['kind'] == 'exact':
            value = expected.get(name, {'fixture': 'same complete operator identity'})
            item.update(actual=deepcopy(value), expected=deepcopy(value))
        else:
            item.update(metric=0., gate=row['numerical_gates'][spec['gate']])
            if spec['kind'] == 'vector': item.update(reported=[0.,0.,0.], reconstructed=[0.,0.,0.])
            if spec['kind'] == 'balance': item.update(applied=[0.,0.,0.], support=[0.,0.,0.])
            if spec['kind'] == 'clamp':
                value = [0.,0.,0.] if name.endswith('position') else [1.,0.,0.,0.,1.,0.,0.,0.,1.]
                item.update(reported=list(value), expected=list(value))
            if spec['kind'] == 'sensors':
                item.update(reported=deepcopy(sensors), reconstructed=deepcopy(sensors), tip_nodes=[tip])
            if spec['kind'] == 'parity':
                item.update(reported=dict(values), restored=dict(values), channels={name:0. for name in adapter.NAMES})
        physical.append(item)
    checks = [dict(name=name, **reference, predicted=values[name],
                   abs_error=abs(values[name]-reference['expected']),
                   passed=abs(values[name]-reference['expected']) <= reference['tolerance'], comparison='<=')
              for name, reference in adapter.reference_contract(row).items()]
    return dict(id=row['id'], case_id='AE-1', adapter='ae1', status='computed', numerical_pass=True,
        reference_match=all(item['passed'] for item in checks), source_pins_unchanged=True, kernel_pins_unchanged=True,
        physical_calls=2, operations=dict(cold_solves=1, fresh_residuals=1, retries=0),
        reference_checks=checks, physical_checks=physical)


@pytest.fixture(scope='module')
def ae1_records():
    if not (ROOT/'.reference/isae-validation/manifest.json').is_file():
        pytest.skip('Optional original ISAE archive unavailable')
    from scripts import isae_suite_ae1
    rows = isae_suite_ae1.plan(ROOT)
    for row in rows:
        row['result'] = (isae_suite_ae1.validate_blocked(ROOT, row) if row['execution_route'] == 'unsupported'
                         else synthetic_ae1_result(row))
    return rows


def ae1_packet(rows):
    item = packet(rows)
    item['report']['code_sha256'].update({'scripts/isae_suite_ae1.py': 'ae1-adapter',
                                        'scripts/isae_suite_ap1.py': 'ae1-wrench-helper'})
    return item


def test_ae1_all_six_channels_and_both_unknown_starts_keep_distinct_denominators(ae1_records):
    data = SUMMARY.summarize(SUMMARY.merge_runs([ae1_packet(ae1_records)]))
    family = next(row for row in data['families'] if row['id'] == 'AE-1'); scope = family['declared_scope']
    assert family['jobs_planned'] == family['jobs_finished'] == 200
    assert family['status'] == 'PARTLY_UNSUPPORTED_SCOPE' and family['unsupported_jobs'] == 4
    assert family['scalar_counts']['required'] == family['scalar_counts']['reported'] == 1200
    assert family['scalar_counts']['numerically_valid_finite'] == 1176
    assert family['scalar_counts']['unsupported_required'] == family['scalar_counts']['reported_unavailable'] == 24
    assert scope['original_reference_samples'] == scope['sensor_reference_rows'] == 100
    assert scope['numerically_valid_reference_samples'] == scope['conditional_operating_rows'] == 98
    assert scope['numerically_valid_conditional_operating_rows'] == 98 and scope['numerically_valid_initial_rows'] == 0
    assert scope['unknown_initial_rows'] == 2 and scope['conditional_sensor_scalar_targets'] == 1176
    assert scope['blocked_initial_scalar_targets'] == 24 and scope['unique_model_count'] == 1
    assert len(data['ae1_mesh_diagnostics']) == 100
    assert sum(row['status'] == 'COMPARED' for row in data['ae1_mesh_diagnostics']) == 98
    assert sum(row['status'] == 'UNAVAILABLE' for row in data['ae1_mesh_diagnostics']) == 2
    assert all(row['passed'] is None and row['acceptance_gate'] is None for row in data['ae1_mesh_diagnostics'])
    assert data['family_count'] == 41 and len(data['missing_adapters']) == 40
    assert not data['full_suite_validated'] and not family['complete_family_reproduction']
    rendered = SUMMARY.markdown(data)
    assert '100 distinct original sensor rows' in rendered and 'Mounted setup is conditional' in rendered
    assert 'NODE I40' in rendered and 'intervals40/80' in rendered


@pytest.mark.parametrize('fault', ['missing_check', 'duplicate_check', 'metric', 'gate', 'calls', 'operations',
                                  'source', 'kernel', 'prediction', 'sensor_geometry', 'cold_setup',
                                  'restored_setup', 'restored_condition', 'null_weights', 'reference_metadata'])
def test_ae1_computed_row_requires_complete_bound_physical_evidence(ae1_records, fault):
    row = deepcopy(next(row for row in ae1_records if row['execution_route'] == 'worker'))
    result = row['result']; physical = {item['name']:item for item in result['physical_checks']}
    if fault == 'missing_check': result['physical_checks'].pop()
    if fault == 'duplicate_check': result['physical_checks'][-1] = deepcopy(result['physical_checks'][0])
    if fault == 'metric': physical['fresh_full_residual']['metric'] = 1.
    if fault == 'gate': row['numerical_gates']['residual'] = 1.
    if fault == 'calls': result['physical_calls'] = 1
    if fault == 'operations': result['operations']['retries'] = 1
    if fault == 'source': result['source_pins_unchanged'] = False
    if fault == 'kernel': result['kernel_pins_unchanged'] = False
    if fault == 'prediction': result['reference_checks'][0]['predicted'] += 1.
    if fault == 'sensor_geometry':
        for key in ('reported', 'reconstructed'):
            physical['independent_sensor_geometry'][key][0]['position_earth'][0] += 1.
    if fault == 'cold_setup': physical['cold_operating_setup']['actual']['ground_flag'] = 0
    if fault == 'restored_setup': physical['restored_operating_setup']['actual']['gravity_body'] = [0.,0.,0.]
    if fault == 'restored_condition': physical['restored_condition']['actual']['freeze_influences'] = True
    if fault == 'null_weights': physical['literal_weight_rows']['actual'].pop()
    if fault == 'reference_metadata': result['reference_checks'][0]['sensor'] = 2
    with pytest.raises(ValueError): SUMMARY.scalar_counts(row)


@pytest.mark.parametrize('claim', ['computed', 'numerical', 'match', 'prediction', 'physical_calls', 'imports'])
def test_ae1_unknown_initial_rows_cannot_claim_computation_or_matches(ae1_records, claim):
    row = deepcopy(next(row for row in ae1_records if row['execution_route'] == 'unsupported'))
    result = row['result']
    if claim == 'computed': result['status'] = 'computed'
    if claim == 'numerical': result['numerical_pass'] = True
    if claim == 'match': result['reference_match'] = True
    if claim == 'prediction': result['reference_checks'][0]['predicted'] = 0.
    if claim == 'physical_calls': result['physical_calls'] = 1
    if claim == 'imports': result['production_imports'] = 1
    with pytest.raises(ValueError): SUMMARY.scalar_counts(row)


@pytest.mark.parametrize('fault', ['condition', 'gravity', 'mesh', 'weight', 'token', 'command'])
def test_ae1_original_sources_reject_altered_setup_or_sensor_contract(ae1_records, fault):
    row = deepcopy(next(row for row in ae1_records if row['execution_route'] == 'worker'))
    if fault == 'condition': row['condition']['speed'] += 1.
    if fault == 'gravity': row['gravity'] = [0.,0.,0.]
    if fault == 'mesh': row['panels']['default'] = 60
    if fault == 'weight': row['literal_weight_rows'].pop()
    if fault == 'token': row['reference_rows'][0]['tokens'][2] = '0.0'
    if fault == 'command': row['reference_rows'][0]['command']['line'] += 1
    with pytest.raises(ValueError): SUMMARY.verify_reference_lines(row, ROOT)


@pytest.mark.parametrize('adapter_name', ['ap2', 'ae1'])
def test_loader_rebuilds_one_canonical_context_per_adapter_without_physics(tmp_path, monkeypatch, ap2_records, ae1_records, adapter_name):
    import builtins
    from scripts import isae_suite_ap2, isae_suite_ae1
    adapter = {'ap2': isae_suite_ap2, 'ae1': isae_suite_ae1}[adapter_name]
    records = {'ap2': ap2_records, 'ae1': ae1_records}[adapter_name]
    rows = deepcopy([row for row in records if row['execution_route'] == 'worker'][:2])
    item = {'ap2': ap2_packet, 'ae1': ae1_packet}[adapter_name](rows)
    report, catalog = item['report'], item['catalog']
    paths = [*sorted((ROOT/'openswing').glob('*.py')), ROOT/f'scripts/isae_suite_{adapter_name}.py', ROOT/'scripts/isae_suite_ap1.py']
    report['code_sha256'] = {path.relative_to(ROOT).as_posix(): SUMMARY.pin(path)['sha256'] for path in paths}
    plan = dict(catalog=catalog, jobs=[{key:value for key,value in row.items() if key != 'result'} for row in rows],
                runtime=report['runtime'], code_sha256=report['code_sha256'])
    for name, value in [('report', report), ('catalog', catalog), ('plan', plan)]:
        (tmp_path/(name+'.json')).write_text(json.dumps(value))
    actual_plan = adapter.plan; calls = []
    def counted(root):
        calls.append(root)
        return actual_plan(root)
    monkeypatch.setattr(adapter, 'plan', counted)
    monkeypatch.setattr(adapter, 'verify_reference_sources',
                        lambda *a: pytest.fail('Repeated complete source rebuild for each job'))
    actual_import = builtins.__import__
    def guarded(name, *args, **kwargs):
        assert not name.startswith(('openswing', 'numpy', 'scipy'))
        return actual_import(name, *args, **kwargs)
    monkeypatch.setattr(builtins, '__import__', guarded)
    merged = SUMMARY.load_runs([tmp_path], ROOT)
    assert calls == [ROOT] and len(merged['jobs']) == 2
    assert all(row['_summary_reference_contract'] == adapter.reference_contract(row) for row in merged['jobs'])
    SUMMARY.verify_summary_sources(merged)
    assert len({item['path'] for item in merged['_verified_file_pins']}) == len(merged['_verified_file_pins'])


def isolated_verified_context(tmp_path, monkeypatch, ap2_records):
    """Small local source files exercise verification transactions safely."""
    from types import SimpleNamespace
    root = tmp_path/'root'; run = tmp_path/'run'
    (root/'openswing').mkdir(parents=True); (root/'scripts').mkdir(); run.mkdir()
    kernel = root/'openswing/kernel.py'; kernel.write_text('kernel = 1\n')
    helper = root/'scripts/isae_suite_ap2.py'; helper.write_text('# fixture helper\n')
    source = root/'original.txt'; source.write_text('original source bytes\n')
    row = deepcopy(next(row for row in ap2_records if row['execution_route'] == 'worker'))
    row['source_pins'] = [SUMMARY.pin(source)]; row['kernel_pins'] = [SUMMARY.pin(kernel)]
    item = ap2_packet([row]); report, catalog = item['report'], item['catalog']
    report['code_sha256'] = {path.relative_to(root).as_posix(): SUMMARY.pin(path)['sha256'] for path in (kernel, helper)}
    plan = dict(catalog=catalog, jobs=[{key:value for key,value in row.items() if key != 'result'}],
                runtime=report['runtime'], code_sha256=report['code_sha256'])
    for name, value in [('report', report), ('catalog', catalog), ('plan', plan)]:
        (run/(name+'.json')).write_text(json.dumps(value))
    canonical = deepcopy(plan['jobs']); calls = []
    def build(actual_root):
        assert actual_root == root
        calls.append(actual_root)
        return deepcopy(canonical)
    module = SimpleNamespace(plan=build)
    monkeypatch.setattr(SUMMARY.importlib, 'import_module', lambda name: module)
    return dict(root=root, run=run, source=source, helper=helper, kernel=kernel,
                canonical=canonical, calls=calls, module=module)


@pytest.mark.parametrize('changed', ['source', 'helper', 'kernel', 'report', 'catalog', 'plan', 'new_kernel'])
def test_final_context_rehash_rejects_any_changed_verified_file_even_with_same_mtime(tmp_path, monkeypatch, ap2_records, changed):
    import os
    fixture = isolated_verified_context(tmp_path, monkeypatch, ap2_records)
    merged = SUMMARY.load_runs([fixture['run']], fixture['root'])
    if changed == 'new_kernel':
        (fixture['root']/'openswing/new.py').write_text('# added after validation\n')
    else:
        path = fixture[changed] if changed in ('source', 'helper', 'kernel') else fixture['run']/(changed+'.json')
        stat = path.stat(); raw = path.read_bytes()
        path.write_bytes(bytes([raw[0] ^ 1]) + raw[1:])
        os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns))
    with pytest.raises(ValueError, match='changed during summary'):
        SUMMARY.verify_summary_sources(merged)


def test_source_mutation_during_canonical_rebuild_is_rejected_before_load_returns(tmp_path, monkeypatch, ap2_records):
    fixture = isolated_verified_context(tmp_path, monkeypatch, ap2_records)
    build = fixture['module'].plan
    def mutate(root):
        rows = build(root)
        fixture['source'].write_text('different source bytes\n')
        return rows
    fixture['module'].plan = mutate
    with pytest.raises(ValueError, match='Verified file changed during summary'):
        SUMMARY.load_runs([fixture['run']], fixture['root'])


def test_verified_canonical_context_is_not_reused_across_load_calls(tmp_path, monkeypatch, ap2_records):
    fixture = isolated_verified_context(tmp_path, monkeypatch, ap2_records)
    SUMMARY.load_runs([fixture['run']], fixture['root'])
    fixture['canonical'][0]['condition']['speed'] += 1.
    with pytest.raises(ValueError, match='original sources'):
        SUMMARY.load_runs([fixture['run']], fixture['root'])
    assert fixture['calls'] == [fixture['root'], fixture['root']]


def test_canonical_context_cannot_replace_verified_file_identity(tmp_path, monkeypatch, ap2_records):
    fixture = isolated_verified_context(tmp_path, monkeypatch, ap2_records)
    fixture['canonical'][0]['source_pins'][0]['sha256'] = '0'*64
    with pytest.raises(ValueError, match='Conflicting verified file pins'):
        SUMMARY.load_runs([fixture['run']], fixture['root'])


def test_publication_rechecks_verified_sources_after_accounting(tmp_path, monkeypatch, ap2_records):
    fixture = isolated_verified_context(tmp_path, monkeypatch, ap2_records)
    merged = SUMMARY.load_runs([fixture['run']], fixture['root'])
    output = tmp_path/'summary'; summarize = SUMMARY.summarize
    monkeypatch.setattr(SUMMARY, 'load_runs', lambda paths: merged)
    def mutate(data):
        result = summarize(data)
        fixture['source'].write_text('changed after accounting\n')
        return result
    monkeypatch.setattr(SUMMARY, 'summarize', mutate)
    monkeypatch.setattr(SUMMARY.sys, 'argv', ['summary', '--run', str(fixture['run']), '--output-dir', str(output)])
    with pytest.raises(ValueError, match='Verified file changed during summary'):
        SUMMARY.main()
    assert not (output/'summary.json').exists() and not (output/'summary.md').exists()


def policy_job(row, relative_tolerance=.03):
    """Build the runner's report view while keeping strict source fields."""
    from scripts.isae_acceptance import apply_reference_acceptance
    row = deepcopy(row)
    counts = SUMMARY.scalar_counts(row)
    if row.get('result') is not None:
        row['result']['output_accounting'] = dict(required=counts['required'], reported=counts['reported'],
            finite=counts['finite'], unavailable=counts['reported_unavailable'],
            numerically_valid=counts['numerically_valid_finite'], passed=counts['passed'], missing=counts['absent'])
        row['result'] = apply_reference_acceptance(row['result'], relative_tolerance=relative_tolerance)
    return row


def policy_packet(rows, relative_tolerance=.03):
    from scripts.isae_acceptance import reference_acceptance_policy
    item = packet([policy_job(row, relative_tolerance) for row in rows])
    item['report']['reference_acceptance'] = reference_acceptance_policy(relative_tolerance=relative_tolerance)
    item['report']['code_sha256']['scripts/isae_acceptance.py'] = 'reference-policy-helper'
    return item


def test_policy_summary_verifies_strict_checks_and_counts_additional_reference_matches():
    item = policy_packet([job('two-percent', [check('CL', 1.02, tolerance=5e-7)])])
    original = deepcopy(item)
    merged = SUMMARY.merge_runs([item])
    data = SUMMARY.summarize(merged)
    assert data['scalar_counts']['passed'] == 1
    assert data['strict_scalar_counts']['passed'] == 0
    assert data['reference_acceptance']['relative_tolerance'] == .03
    assert next(row for row in data['families'] if row['id'] == 'SA-1')['status'] == 'SELECTED_SCOPE_MATCHES'
    stats = SUMMARY.error_stats(merged['jobs'], 'CL')
    assert stats['precision_passed'] == 0 and stats['acceptance_passed'] == 1
    assert stats['maximum_absolute_error'] == pytest.approx(.02)
    assert '**3%**' in SUMMARY.markdown(data)
    assert item == original


def test_policy_validation_passes_only_reconstructed_strict_fields_to_adapter_checks(monkeypatch):
    source = job('two-percent', [check('CL', 1.02, tolerance=5e-7)])
    view = policy_job(source)
    strict = SUMMARY.strict_policy_job(view)
    observed = []
    validate = SUMMARY.strict_scalar_counts
    def inspect(row):
        observed.append(deepcopy(row))
        assert row == strict
        assert row['result']['reference_checks'] == source['result']['reference_checks']
        assert 'reference_acceptance_policy' not in row['result']
        return validate(row)
    monkeypatch.setattr(SUMMARY, 'strict_scalar_counts', inspect)
    assert SUMMARY.scalar_counts(view)['passed'] == 1
    assert len(observed) == 1


@pytest.mark.parametrize('fault', [
    'passed', 'strict_passed', 'effective_tolerance', 'original_tolerance',
    'strict_reference_match', 'strict_accounting', 'policy_metadata', 'missing_strict',
])
def test_policy_metadata_or_pass_tampering_is_rejected(fault):
    row = policy_job(job('two-percent', [check('CL', 1.02, tolerance=5e-7)]))
    result = row['result']; target = result['reference_checks'][0]
    if fault == 'passed': target['passed'] = False
    if fault == 'strict_passed': target['strict_passed'] = True
    if fault == 'effective_tolerance': target['effective_tolerance'] = .5
    if fault == 'original_tolerance': target['original_tolerance'] = .5
    if fault == 'strict_reference_match': result['strict_reference_match'] = True
    if fault == 'strict_accounting': result['strict_output_accounting']['passed'] = 1
    if fault == 'policy_metadata': result['reference_acceptance_policy']['scope'] = 'all numerical checks'
    if fault == 'missing_strict': target.pop('strict_passed')
    with pytest.raises(ValueError):
        SUMMARY.scalar_counts(row)


def test_policy_does_not_allow_changes_to_the_original_polar_contract():
    row = policy_job(polar(0, 8))
    # Alter both redundant copies so only the underlying source contract can
    # detect the change; reported policy metadata must not replace that check.
    target = row['result']['reference_checks'][0]
    target['tolerance'] = target['original_tolerance'] = target['effective_tolerance'] = 1.
    with pytest.raises(ValueError, match='precision gate changed'):
        SUMMARY.scalar_counts(row)


@pytest.mark.parametrize('predicted, expected, status', [
    (1e-10, 0., 'computed'), (1.02e-8, 1e-8, 'computed'),
    (None, 1., 'computed'), (1.02, 1., 'numerical_failure'),
    (None, 1., 'unsupported'),
])
def test_policy_retains_zero_tiny_unavailable_and_failure_gates(predicted, expected, status):
    row = policy_job(job('gated', [check('CL', predicted, expected, 1e-12)], status=status))
    counts = SUMMARY.scalar_counts(row)
    assert counts['required'] == 1 and counts['passed'] == 0
    assert row['result']['reference_match'] is False


def test_zero_relative_policy_and_legacy_reports_keep_strict_semantics():
    rows = [job('strict', [check('CL', 1.02, tolerance=5e-7)])]
    original = SUMMARY.summarize(SUMMARY.merge_runs([packet(rows)]))
    explicit_zero = SUMMARY.summarize(SUMMARY.merge_runs([policy_packet(rows, 0)]))
    assert original['scalar_counts'] == explicit_zero['scalar_counts']
    assert explicit_zero['scalar_counts']['passed'] == 0
    assert explicit_zero['scalar_counts'] == explicit_zero['strict_scalar_counts']


@pytest.mark.parametrize('other_policy', [None, 0, .01])
def test_merging_different_reference_policies_is_rejected(other_policy):
    first = policy_packet([job('one', [check('CL', 1.02, tolerance=5e-7)])])
    rows = [job('two', [check('CL', 1.02, tolerance=5e-7)])]
    second = packet(rows) if other_policy is None else policy_packet(rows, other_policy)
    with pytest.raises(ValueError, match='policy differs across runs'):
        SUMMARY.merge_runs([first, second])


@pytest.mark.parametrize('fault', ['missing_policy', 'changed_policy', 'missing_helper_pin'])
def test_run_policy_must_match_every_job_and_have_pinned_implementation(fault):
    item = policy_packet([job('one', [check('CL', 1.02, tolerance=5e-7)])])
    if fault == 'missing_policy':
        item['report']['reference_acceptance'] = None
    if fault == 'changed_policy':
        item['report']['jobs'][0]['result']['reference_acceptance_policy']['relative_tolerance'] = .01
    if fault == 'missing_helper_pin':
        item['report']['code_sha256'].pop('scripts/isae_acceptance.py')
    with pytest.raises(ValueError):
        SUMMARY.merge_runs([item])


@pytest.mark.parametrize('fault', ['none', 'plan_policy', 'missing_plan_policy', 'helper_bytes'])
@pytest.mark.parametrize('relative_tolerance', [.03, .05])
def test_file_loader_verifies_policy_against_frozen_plan_and_helper(frozen_run_files, fault, relative_tolerance):
    from scripts.isae_acceptance import reference_acceptance_policy
    root, stage, report, plan = frozen_run_files
    source = job('one', [check('CL', 1.02, tolerance=5e-7)])
    report['jobs'] = [policy_job(source,relative_tolerance)]
    plan['jobs'] = [{key: value for key, value in source.items() if key != 'result'}]
    helper = root / 'scripts/isae_acceptance.py'
    helper.write_bytes((ROOT / 'scripts/isae_acceptance.py').read_bytes())
    for saved in (report, plan):
        saved['reference_acceptance'] = reference_acceptance_policy(relative_tolerance=relative_tolerance)
        saved['code_sha256']['scripts/isae_acceptance.py'] = SUMMARY.pin(helper)['sha256']
    if fault == 'plan_policy':
        plan['reference_acceptance'] = reference_acceptance_policy(relative_tolerance=.01)
    if fault == 'missing_plan_policy':
        plan.pop('reference_acceptance')
    if fault == 'helper_bytes':
        helper.write_text('# changed policy implementation\n')
    for name, saved in [('report', report), ('plan', plan)]:
        (stage / (name + '.json')).write_text(json.dumps(saved))
    if fault == 'none':
        merged = SUMMARY.load_runs([stage], root)
        assert SUMMARY.totals(merged['jobs'])['passed'] == 1
    else:
        with pytest.raises(ValueError):
            SUMMARY.load_runs([stage], root)
