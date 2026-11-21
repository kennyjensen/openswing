"""Coverage and failure accounting must not silently turn partial studies green."""
import importlib.util
import hashlib
import json
import sys
from pathlib import Path

import pytest
import asyncio
from types import SimpleNamespace
from copy import deepcopy


path = Path(__file__).resolve().parents[1] / "scripts/run-isae-suite.py"
spec = importlib.util.spec_from_file_location("isae_suite_runner", path)
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


def catalog():
    return {"cases": [
        {"id": "A", "path": "a", "models": ["m"], "reference_candidates": ["r"]},
        {"id": "B", "path": "b", "models": [], "reference_candidates": ["figure"]},
    ]}


def jobs():
    return [{"id": f"A-{i}", "case_id": "A", "expected_outputs": 1} for i in range(3)]


def test_family_without_adapter_remains_in_report():
    rows = runner.summarize(catalog(), jobs(), {})
    assert [r["id"] for r in rows] == ["A", "B"]
    assert rows[1]["status"] == "NO_SELECTED_COMPARISON_JOBS"
    assert rows[1]["reference_candidates"] == 1
    assert not rows[1]["complete_family_reproduction"]


def test_timeout_does_not_disappear_from_denominator():
    results = {"A-0": {"status": "computed", "reference_match": True},
               "A-1": {"status": "computed", "reference_match": True},
               "A-2": {"status": "timeout", "reference_match": False}}
    row = runner.summarize(catalog(), jobs(), results)[0]
    assert row["jobs_planned"] == row["jobs_finished"] == 3
    assert row["jobs_computed"] == row["jobs_matching"] == 2
    assert row["status"] == "NUMERICAL_OR_INPUT_FAILURES"


def test_output_difference_is_not_numerical_success():
    results = {j["id"]: {"status": "computed", "reference_match": False} for j in jobs()}
    row = runner.summarize(catalog(), jobs(), results)[0]
    assert row["status"] == "ARCHIVED_OUTPUT_DIFFERENCES"
    assert row["jobs_computed"] == 3
    assert row["jobs_matching"] == 0


def test_selected_output_match_is_not_full_family_pass():
    results = {j["id"]: {"status": "computed", "reference_match": True} for j in jobs()}
    row = runner.summarize(catalog(), jobs(), results)[0]
    assert row["status"] == "SELECTED_SCOPE_MATCHES"
    assert not row["complete_family_reproduction"]


def test_interrupted_run_is_incomplete():
    rows = runner.summarize(catalog(), jobs(), {"A-0": {"status": "computed", "reference_match": True}})
    assert rows[0]["status"] == "INCOMPLETE_RUN"
    assert rows[0]["jobs_finished"] == 1


@pytest.mark.parametrize('adapter', ['polars', 'extra_polars', 'sa11', 'sa12'])
def test_mesh_comparison_requires_both_successful_original_solves(adapter):
    request = [dict(id=f"A-{n}", case_id="A", adapter=adapter, table_path="a.txt",
                    row_index=0, settings={"panels": n}) for n in [10, 20]]
    result = {"A-10": {"status": "computed", "reference_checks": [{"name": "CL", "predicted": 1.}]},
              "A-20": {"status": "timeout"}}
    assert runner.mesh_diagnostics(request, result)[0]["status"] == "UNAVAILABLE"
    result["A-20"] = {"status": "computed", "reference_checks": [{"name": "CL", "predicted": 1.25}]}
    comparison = runner.mesh_diagnostics(request, result)[0]
    assert comparison["status"] == "DIAGNOSTIC_ONLY"
    assert comparison["absolute_changes"] == {"CL": .25}
    assert "passed" not in comparison


def test_empty_or_duplicate_reference_checks_cannot_pass():
    for checks in [[], [{"name": "CL"}, {"name": "CL"}]]:
        result = runner.checked_result({"expected_outputs": 2},
            {"status": "computed", "reference_match": True,
             "numerical_pass": True, "reference_checks": checks})
        assert result["status"] == "adapter_contract_failure"
        assert not result["reference_match"]


def test_reported_match_must_satisfy_the_unchanged_precision_check():
    result = runner.checked_result({"expected_outputs": 1},
        {"status": "computed", "numerical_pass": True, "reference_match": True,
         "reference_checks": [{"name": "CL", "predicted": 1., "expected": 2.,
                               "tolerance": .001, "passed": True}]})
    assert result["status"] == "adapter_contract_failure"
    assert result["output_accounting"]["passed"] == 0


def test_scalar_totals_do_not_mix_families_or_hide_timeouts():
    request = [{"id": "A-0", "expected_outputs": 7}, {"id": "A-1", "expected_outputs": 7}]
    results = {"A-0": {"output_accounting": {"reported": 7, "passed": 3, "missing": 0}},
               "A-1": runner.checked_result({"expected_outputs": 7}, {"status": "timeout"}),
               "B-0": {"output_accounting": {"reported": 20, "passed": 20}}}
    counts = runner.output_totals(request, results)
    assert counts["required"] == counts["finished_required"] == 14
    assert counts["reported"] == 7 and counts["passed"] == 3 and counts["missing"] == 7
    assert counts["unrun"] == 0


def test_registered_reference_is_checked_against_upstream_not_only_current_bytes(tmp_path):
    cache = tmp_path / ".reference/isae-validation/revision"
    cache.mkdir(parents=True)
    original = b"original archived output\n"
    source = cache / "polar.txt"
    source.write_bytes(original)
    (cache.parent / "manifest.json").write_text(json.dumps({"revision": "revision", "files": {
        "polar.txt": {"bytes": len(original), "sha256": hashlib.sha256(original).hexdigest()}}}))
    jobs = [{"sources": [{"path": str(source)}]}]
    assert runner.verify_registered_upstream_inputs(tmp_path, jobs, "revision")["polar.txt"]["bytes"] == len(original)
    source.write_bytes(b"changed! archived output\n")
    with pytest.raises(ValueError, match="differs from pinned upstream"):
        runner.verify_registered_upstream_inputs(tmp_path, jobs, "revision")


def test_registered_reference_rejects_wrong_archive_revision(tmp_path):
    parent = tmp_path / ".reference/isae-validation"
    parent.mkdir(parents=True)
    (parent / "manifest.json").write_text(json.dumps({"revision": "other", "files": {}}))
    with pytest.raises(ValueError, match="revision differs"):
        runner.verify_registered_upstream_inputs(tmp_path, [], "revision")


def test_shared_upstream_source_is_resolved_once_per_preflight(tmp_path, monkeypatch):
    cache = tmp_path / ".reference/isae-validation/revision"
    cache.mkdir(parents=True)
    source = cache / "polar.txt"
    source.write_bytes(b"original")
    (cache.parent/"manifest.json").write_text(json.dumps({"revision": "revision", "files": {
        "polar.txt": {"bytes": 8, "sha256": hashlib.sha256(b"original").hexdigest()}}}))
    calls = []
    original_resolve = Path.resolve
    def resolve(path, *args, **kwargs):
        calls.append(str(path))
        return original_resolve(path, *args, **kwargs)
    monkeypatch.setattr(Path, "resolve", resolve)
    requests = [{"sources": [{"path": str(source)}]} for _ in range(100)]
    assert len(runner.verify_registered_upstream_inputs(tmp_path, requests, "revision")) == 1
    assert calls.count(str(source)) == calls.count(str(cache)) == 1


def test_unavailable_prediction_is_not_a_numerically_valid_scalar():
    result = runner.checked_result({"expected_outputs": 1},
        {"status": "computed", "numerical_pass": True,
         "reference_checks": [{"name": "efficiency", "predicted": None, "expected": 1.,
                               "tolerance": .001, "passed": False}]})
    assert result["status"] == "computed"
    assert result["output_accounting"]["numerically_valid"] == 0
    assert result["output_accounting"]["unavailable"] == 1
    assert not result["reference_match"]


def test_unsupported_rows_remain_distinct_from_failed_solves():
    results = {j["id"]: {"status": "unsupported", "reference_match": False} for j in jobs()}
    row = runner.summarize(catalog(), jobs(), results)[0]
    assert row["status"] == "UNSUPPORTED_COMPARISONS"
    assert row["jobs_unsupported"] == 3
    results["A-0"] = {"status": "computed", "reference_match": False}
    assert runner.summarize(catalog(), jobs(), results)[0]["status"] == "PARTLY_UNSUPPORTED"


def test_adapter_selection_avoids_loading_unselected_modules(monkeypatch, tmp_path):
    loaded = []
    def load(name):
        loaded.append(name)
        return SimpleNamespace(plan=lambda root: [{"id": "P-1", "case_id": "P-1", "expected_outputs": 1}])
    monkeypatch.setattr(runner.importlib, "import_module", load)
    assert runner.plan_jobs(tmp_path, ["components"])[0]["adapter"] == "components"
    assert loaded == ["isae_suite_components"]


def test_added_kernel_invalidates_a_frozen_execution_plan(tmp_path):
    folder = tmp_path/"openswing"
    folder.mkdir()
    (folder/"existing.py").write_text("unchanged = True\n")
    pins = {"openswing/existing.py": runner.digest(folder/"existing.py")}
    assert runner.stable_code(tmp_path, pins)
    (folder/"additional.py").write_text("changed_dependency = True\n")
    assert not runner.stable_code(tmp_path, pins)


def test_blocked_jobs_are_retained_without_starting_a_solver(monkeypatch, tmp_path):
    job = {"id": "blocked", "case_id": "A", "adapter": "extra_polars",
           "execution_route": "unsupported", "expected_outputs": 1}
    def no_process(*args, **kwargs):
        raise AssertionError("Unsupported input must not start a subprocess")
    monkeypatch.setattr(runner.asyncio, "create_subprocess_exec", no_process)
    monkeypatch.setattr(runner.importlib, "import_module", lambda name:
        SimpleNamespace(validate_blocked=lambda root, request: {"status": "unsupported",
          "reference_checks": [{"name": "CL", "predicted": None, "expected": 1.,
                                "tolerance": .01, "passed": False}]}))
    results = {}
    asyncio.run(runner.execute({"jobs": [job], "code_sha256": {}}, tmp_path,
                                SimpleNamespace(workers=1, timeout_seconds=1), results))
    result = results["blocked"]
    assert result["execution_completed"] and not result["subprocess_started"]
    assert result["output_accounting"]["required"] == 1
    assert result["physical_solver_calls"] == 0
    assert json.loads((tmp_path/"progress.json").read_text())["finished"] == 1


@pytest.fixture(scope='module')
def st2_jobs():
    if not (runner.ROOT/'.reference/isae-validation/manifest.json').is_file():
        pytest.skip('Optional original ISAE archive unavailable')
    from scripts import isae_suite_st2
    return isae_suite_st2.plan(runner.ROOT)


def test_st2_registration_default_selection_and_dependency_pins(monkeypatch, st2_jobs):
    assert runner.ADAPTERS['st2'] == 'isae_suite_st2'
    # The legacy scope retains its dependencies when the adapter also supports
    # the separately selected mechanics comparisons.
    assert {'isae_st2_archive.py', 'isae_suite_st2_modal.py'} <= set(runner.HELPERS['st2'])
    loaded = []
    def load(name):
        loaded.append(name)
        return SimpleNamespace(plan=lambda root: st2_jobs if name == 'isae_suite_st2' else [])
    monkeypatch.setattr(runner.importlib, 'import_module', load)
    planned = runner.plan_jobs(runner.ROOT)
    assert len(planned) == 17 and sum(job['expected_outputs'] for job in planned) == 490
    assert 'isae_suite_st2' in loaded
    pins = runner.code_pins(runner.ROOT, ['st2'])
    assert {'scripts/isae_suite_st2.py', 'scripts/isae_st2_archive.py',
            'scripts/isae_suite_st2_modal.py'} <= set(pins)
    assert sum(job['execution_route'] == 'worker' for job in planned) == 8
    assert sum(job['execution_route'] == 'unsupported' for job in planned) == 9


def test_st2_inline_blocker_path_keeps_zero_target_records_and_starts_no_worker(monkeypatch, tmp_path, st2_jobs):
    from scripts import isae_suite_st2
    monkeypatch.setattr(runner.asyncio, 'create_subprocess_exec',
                        lambda *a, **k: pytest.fail('ST2 source registration started a solver subprocess'))
    monkeypatch.setattr(runner.importlib, 'import_module', lambda name: isae_suite_st2)
    blocked = [job for job in st2_jobs if job['execution_route'] == 'unsupported']
    results = {}
    asyncio.run(runner.execute({'jobs': blocked, 'code_sha256': {}}, tmp_path,
                              SimpleNamespace(workers=1, timeout_seconds=1), results))
    assert len(results) == 9 and all(row['status'] == 'unsupported' for row in results.values())
    assert all(row['execution_kind'] == 'inline_blocker_validation' and not row['subprocess_started'] and
               row['physical_solver_calls'] == 0 and not row['reference_match'] for row in results.values())
    counts = runner.output_totals(blocked, results)
    assert counts['required'] == counts['reported'] == counts['finished_required'] == 378
    assert counts['passed'] == 0
    family = {'cases': [{'id': 'ST-2', 'path': 'original', 'models': list(range(6)), 'reference_candidates': list(range(5))}]}
    row, = runner.summarize(family, blocked, results)
    assert row['jobs_finished'] == row['jobs_unsupported'] == 9 and row['jobs_computed'] == row['jobs_matching'] == 0
    assert row['status'] == 'UNSUPPORTED_COMPARISONS'


@pytest.mark.parametrize('claim', ['computed', 'match', 'numerical', 'prediction'])
def test_st2_checked_result_rejects_any_invented_numerical_claim(st2_jobs, claim):
    from scripts import isae_suite_st2
    job = next(job for job in st2_jobs if job['target_kind'] == 'native_static')
    result = deepcopy(isae_suite_st2.validate_blocked(runner.ROOT, job))
    if claim == 'computed': result['status'] = 'computed'
    if claim == 'match': result['reference_match'] = True
    if claim == 'numerical': result['numerical_pass'] = True
    if claim == 'prediction': result['reference_checks'][0]['predicted'] = 0.
    checked = runner.checked_result(job, result)
    assert checked['status'] == 'adapter_contract_failure' and not checked['reference_match']
    assert checked['output_accounting']['passed'] == checked['output_accounting']['numerically_valid'] == 0


@pytest.fixture(scope='module')
def ap1_jobs():
    if not (runner.ROOT/'.reference/isae-validation/manifest.json').is_file():
        pytest.skip('Optional original ISAE archive unavailable')
    from scripts import isae_suite_ap1
    return isae_suite_ap1.plan(runner.ROOT)


def test_ap1_default_registration_preserves_executable_and_blocked_scopes(monkeypatch, ap1_jobs):
    assert runner.ADAPTERS['ap1'] == 'isae_suite_ap1' and runner.HELPERS['ap1'] == []
    loaded = []
    def load(name):
        loaded.append(name)
        return SimpleNamespace(plan=lambda root: ap1_jobs if name == 'isae_suite_ap1' else [])
    monkeypatch.setattr(runner.importlib, 'import_module', load)
    planned = runner.plan_jobs(runner.ROOT)
    assert len(planned) == 26 and sum(job['expected_outputs'] for job in planned) == 15470
    assert 'isae_suite_ap1' in loaded
    active = [job for job in planned if job['execution_route'] != 'unsupported']
    assert len(active) == 6 and all(job['target_kind'] == 'paired_header' and job['expected_outputs'] == 13 for job in active)
    assert 'scripts/isae_suite_ap1.py' in runner.code_pins(runner.ROOT, ['ap1'])


def test_ap1_blocked_target_executes_only_source_validation(monkeypatch, tmp_path, ap1_jobs):
    from scripts import isae_suite_ap1
    selected = [next(job for job in ap1_jobs if job['target_kind'] == kind and job['execution_route'] == 'unsupported')
                for kind in ('paired_header', 'paired_span', 'unpaired_span_and_header', 'unpaired_operating')]
    monkeypatch.setattr(runner.asyncio, 'create_subprocess_exec',
                        lambda *a, **k: pytest.fail('Blocked AP1 route started a worker'))
    monkeypatch.setattr(runner.importlib, 'import_module', lambda name: isae_suite_ap1)
    results = {}
    asyncio.run(runner.execute({'jobs': selected, 'code_sha256': {}}, tmp_path,
                              SimpleNamespace(workers=1, timeout_seconds=1), results))
    assert len(results) == 4 and all(row['status'] == 'unsupported' for row in results.values())
    assert all(row['execution_kind'] == 'inline_blocker_validation' and not row['subprocess_started'] and
               row['physical_solver_calls'] == 0 and not row['reference_match'] for row in results.values())


@pytest.mark.parametrize('claim', ['computed', 'match', 'numerical', 'prediction'])
def test_ap1_blocked_result_cannot_be_promoted_to_execution(ap1_jobs, claim):
    from scripts import isae_suite_ap1
    job = next(job for job in ap1_jobs if job['target_kind'] == 'paired_header' and job['execution_route'] == 'unsupported')
    result = deepcopy(isae_suite_ap1.validate_blocked(runner.ROOT, job))
    if claim == 'computed': result['status'] = 'computed'
    if claim == 'match': result['reference_match'] = True
    if claim == 'numerical': result['numerical_pass'] = True
    if claim == 'prediction': result['reference_checks'][0]['predicted'] = 0.
    checked = runner.checked_result(job, result)
    assert checked['status'] == 'adapter_contract_failure' and not checked['reference_match']
    assert checked['output_accounting']['passed'] == checked['output_accounting']['numerically_valid'] == 0


def test_ap1_report_collects_descriptive_adapter_mesh_diagnostics(monkeypatch, ap1_jobs):
    from scripts import isae_suite_ap1
    monkeypatch.setattr(runner.importlib, 'import_module', lambda name: isae_suite_ap1)
    source_catalog = {'cases': [dict(id='AP-1', path='original', models=[], reference_candidates=[])], 'counts': {}}
    plan = dict(catalog=source_catalog, jobs=ap1_jobs, code_sha256={}, runtime={}, execution_policy={'adapters': ['ap1']})
    result = runner.report(plan, {}, runner.ROOT, 0.)
    diagnostic = result['adapter_mesh_diagnostics']['ap1']
    assert len(diagnostic) == 3
    assert all(row['status'] == 'UNAVAILABLE' and row['passed'] is None and row['acceptance_gate'] is None for row in diagnostic)


def expansion_selection_fixture():
    cases = [f'SA-{i}' for i in range(1, 16) if i != 9]
    for prefix, count in [('UA', 2), ('AP', 2), ('P', 5), ('ST', 6), ('AE', 7), ('FFWT', 5)]:
        cases.extend(f'{prefix}-{i}' for i in range(1, count+1))
    source_catalog = dict(cases=[dict(id=name, path=name, models=[], reference_candidates=[]) for name in cases],
        models=[dict(path=f'synthetic-model-{i}') for i in range(279)], counts=dict(families=41, models=279), revision='fixture')
    planned = [dict(id='ST5-30LB_80_20-static-three-grids', case_id='ST-5', adapter='structure', expected_outputs=6480),
               dict(id='ST5-20LB_80_20-static-three-grids', case_id='ST-5', adapter='structure', expected_outputs=6480),
               dict(id='AE-2-m15_02-b01-ias001-m80', case_id='AE-2', adapter='aeroelastic', expected_outputs=4),
               dict(id='AE-2-p15_02-b01-ias001-m80', case_id='AE-2', adapter='aeroelastic', expected_outputs=4),
               dict(id='AE-2-b01-ias001-m80', case_id='AE-2', adapter='aeroelastic', expected_outputs=4)]
    return source_catalog, planned


def test_default_selection_keeps_all_jobs_and_full_family_model_inventory():
    source_catalog, planned = expansion_selection_fixture()
    before = deepcopy(source_catalog)
    assert runner.select_jobs(planned, source_catalog) == planned
    assert source_catalog == before and len(source_catalog['cases']) == 41 and len(source_catalog['models']) == 279


def test_case_and_job_globs_intersect_without_dropping_unselected_catalog_families():
    source_catalog, planned = expansion_selection_fixture()
    selected = runner.select_jobs(planned, source_catalog, ['AE-2', 'ST-5'],
        ['AE-2-m15_02-*', 'AE-2-p15_02-*', 'ST5-30LB_80_20-*'])
    assert [job['id'] for job in selected] == [planned[i]['id'] for i in (0, 2, 3)]
    rows = runner.summarize(source_catalog, selected, {})
    assert len(rows) == 41 and sum(row['status'] == 'NO_SELECTED_COMPARISON_JOBS' for row in rows) == 39
    assert all(row['complete_family_reproduction'] is False for row in rows)


@pytest.mark.parametrize('cases,patterns', [([], None), (['AE-2', 'AE-2'], None), (['AE2'], None),
    (['SA-9'], None), (['ae-2'], None), (['ST-1'], None), (None, []), (None, ['']),
    (None, ['missing*']), (None, ['AE-2-*', 'typo*']), (None, ['AE-2-*', 'AE-2-*']),
    (['AE-2'], ['ST5-*']), (['AE-2', 'ST-5'], ['AE-2-*'])])
def test_selection_rejects_empty_unknown_or_partly_unmatched_requests(cases, patterns):
    source_catalog, planned = expansion_selection_fixture()
    with pytest.raises(ValueError):
        runner.select_jobs(planned, source_catalog, cases, patterns)


def test_resume_requires_identical_selectors_even_if_matched_jobs_are_identical(tmp_path):
    path = tmp_path/'plan.json'
    plan = dict(jobs=[{'id': 'AE-2-only'}], execution_policy=dict(cases=['AE-2'], job_patterns=['AE-2-*']))
    runner.write_json(path, plan)
    runner.validate_resume_plan(path, plan, True)
    with pytest.raises(ValueError, match='identical plan'):
        runner.validate_resume_plan(path, plan, False)
    for key, value in [('cases', None), ('job_patterns', ['*'])]:
        changed = deepcopy(plan)
        changed['execution_policy'][key] = value
        with pytest.raises(ValueError, match='selectors'):
            runner.validate_resume_plan(path, changed, True)


def test_cli_selection_is_pinned_and_retains_full_catalog_on_plan_only(tmp_path, monkeypatch):
    monkeypatch.syspath_prepend(str(runner.ROOT / 'scripts'))
    source_catalog, planned = expansion_selection_fixture()
    monkeypatch.setitem(sys.modules, 'isae_suite_catalog', SimpleNamespace(build_catalog=lambda root: source_catalog))
    monkeypatch.setattr(runner, 'plan_jobs', lambda root, adapters: planned)
    monkeypatch.setattr(runner, 'verify_registered_upstream_inputs', lambda *args: {})
    monkeypatch.setattr(runner, 'code_pins', lambda *args: {})
    monkeypatch.setattr(runner, 'execute', lambda *a: pytest.fail('Plan-only selection started execution'))
    argv = ['run-isae-suite.py', '--output-dir', str(tmp_path), '--plan-only', '--adapters', 'structure', 'aeroelastic',
            '--cases', 'ST-5', 'AE-2', '--job-pattern', 'ST5-30LB_80_20-*', '--job-pattern', 'AE-2-m15_02-*', 'AE-2-p15_02-*']
    monkeypatch.setattr(sys, 'argv', argv)
    runner.main()
    saved = json.loads((tmp_path/'plan.json').read_text())
    assert saved['catalog'] == source_catalog
    assert len(saved['jobs']) == 3 and saved['execution_policy']['cases'] == ['ST-5', 'AE-2']
    assert saved['execution_policy']['job_patterns'] == ['ST5-30LB_80_20-*', 'AE-2-m15_02-*', 'AE-2-p15_02-*']
    assert saved['selection_scope']['omitted_jobs_in_requested_adapters'] == 2
    assert len(saved['selection_scope']['families_without_selected_jobs']) == 39
    monkeypatch.setattr(sys, 'argv', argv+['--resume'])
    runner.main()


@pytest.mark.parametrize('adapters,pairings', [(['polars'], ['sa7-fore-f745fb40']),
    (['extra_polars'], ['unknown']), (['extra_polars'], ['sa7-fore-f745fb40']*2)])
def test_historical_pairing_requires_unique_reviewed_name_and_owning_adapter(adapters, pairings, monkeypatch):
    monkeypatch.setattr(runner.importlib, 'import_module', lambda name: pytest.fail('Invalid pairing imported adapter'))
    with pytest.raises(ValueError):
        runner.plan_jobs(runner.ROOT, adapters, source_pairings=pairings)


def test_cli_historical_pairing_is_explicit_and_recorded(tmp_path, monkeypatch):
    monkeypatch.syspath_prepend(str(runner.ROOT / 'scripts'))
    source_catalog, _ = expansion_selection_fixture()
    ordinary = dict(id='SA-7:current', case_id='SA-7', expected_outputs=7, adapter='extra_polars')
    historical = dict(ordinary, id='SA-7:historical-f745fb40')
    calls = []
    def plan(root, adapters, *, source_pairings=()):
        calls.append(tuple(source_pairings))
        return [ordinary, historical] if source_pairings else [ordinary]
    monkeypatch.setitem(sys.modules, 'isae_suite_catalog', SimpleNamespace(build_catalog=lambda root: source_catalog))
    monkeypatch.setattr(runner, 'plan_jobs', plan)
    monkeypatch.setattr(runner, 'verify_registered_upstream_inputs', lambda *args: {})
    monkeypatch.setattr(runner, 'code_pins', lambda *args: {})
    monkeypatch.setattr(runner, 'execute', lambda *args: pytest.fail('Plan-only started a solve'))
    monkeypatch.setattr(sys, 'argv', ['run-isae-suite.py', '--output-dir', str(tmp_path), '--plan-only',
        '--adapters', 'extra_polars', '--source-pairing', 'sa7-fore-f745fb40',
        '--cases', 'SA-7', '--job-pattern', '*historical-f745fb40*'])
    runner.main()
    saved = json.loads((tmp_path/'plan.json').read_text())
    assert calls == [('sa7-fore-f745fb40',)]
    assert saved['jobs'] == [historical]
    assert saved['execution_policy']['source_pairings'] == ['sa7-fore-f745fb40']
    assert saved['selection_scope']['omitted_jobs_in_requested_adapters'] == 1
    assert saved['catalog'] == source_catalog


def test_current_and_historical_models_have_separate_mesh_diagnostics():
    rows = [dict(id=f'{kind}-{n}', case_id='SA-7', table_path='same.txt', row_index=0,
                 adapter='extra_polars' if kind == 'historical' else 'polars',
                 settings=dict(panels=n), **({'source_pairing': {'id': 'sa7-fore-f745fb40'}}
                                           if kind == 'historical' else {}))
            for kind in ('current', 'historical') for n in (64, 128)]
    results = {row['id']: dict(status='computed', reference_checks=[dict(name='CL', predicted=value)])
               for row, value in zip(rows, [10., 11., 1., 1.1])}
    comparisons = runner.mesh_diagnostics(rows, results)
    assert len(comparisons) == 2
    assert comparisons[0]['absolute_changes']['CL'] == 1.
    assert comparisons[1]['absolute_changes']['CL'] == pytest.approx(.1)
    assert comparisons[1]['source_pairing_id'] == 'sa7-fore-f745fb40'


@pytest.fixture(scope='module')
def ap2_jobs():
    if not (runner.ROOT/'.reference/isae-validation/manifest.json').is_file():
        pytest.skip('Optional original ISAE archive unavailable')
    from scripts import isae_suite_ap2
    return isae_suite_ap2.plan(runner.ROOT)


def test_ap2_default_registration_retains_grid_states_and_unpaired_targets(monkeypatch, ap2_jobs):
    assert runner.ADAPTERS['ap2'] == 'isae_suite_ap2' and runner.HELPERS['ap2'] == ['isae_suite_ap1.py']
    loaded = []
    def load(name):
        loaded.append(name)
        return SimpleNamespace(plan=lambda root: ap2_jobs if name == 'isae_suite_ap2' else [])
    monkeypatch.setattr(runner.importlib, 'import_module', load)
    planned = runner.plan_jobs(runner.ROOT)
    assert 'isae_suite_ap2' in loaded and len(planned) == 237
    assert sum(row['expected_outputs'] for row in planned) == 248
    active = [row for row in planned if row['execution_route'] != 'unsupported']
    assert len(active) == 234 and all(row['target_kind'] == 'grid_state' for row in active)
    pins = runner.code_pins(runner.ROOT, ['ap2'])
    assert {'scripts/isae_suite_ap2.py', 'scripts/isae_suite_ap1.py'} <= pins.keys()


def test_ap2_unpaired_targets_complete_inline_without_starting_physics(monkeypatch, tmp_path, ap2_jobs):
    from scripts import isae_suite_ap2
    selected = [row for row in ap2_jobs if row['execution_route'] == 'unsupported']
    assert len(selected) == 3 and sum(row['expected_outputs'] for row in selected) == 6
    monkeypatch.setattr(runner.asyncio, 'create_subprocess_exec',
                        lambda *a, **k: pytest.fail('Blocked AP2 route started a solver subprocess'))
    monkeypatch.setattr(runner.importlib, 'import_module', lambda name: isae_suite_ap2)
    results = {}
    asyncio.run(runner.execute({'jobs': selected, 'code_sha256': {}}, tmp_path,
                              SimpleNamespace(workers=1, timeout_seconds=1), results))
    assert len(results) == 3 and all(row['status'] == 'unsupported' for row in results.values())
    assert all(row['execution_kind'] == 'inline_blocker_validation' and not row['subprocess_started'] and
               row['physical_calls'] == 0 and row['physical_solver_calls'] == 0 for row in results.values())
    counts = runner.output_totals(selected, results)
    assert counts['required'] == counts['reported'] == counts['finished_required'] == 6
    assert counts['finite'] == counts['passed'] == 0


@pytest.mark.parametrize('claim', ['computed', 'match', 'numerical', 'prediction', 'physical_calls'])
def test_ap2_blocked_result_cannot_be_promoted_to_execution(ap2_jobs, claim):
    from scripts import isae_suite_ap2
    row = next(row for row in ap2_jobs if row['execution_route'] == 'unsupported')
    result = deepcopy(isae_suite_ap2.validate_blocked(runner.ROOT, row))
    if claim == 'computed': result['status'] = 'computed'
    if claim == 'match': result['reference_match'] = True
    if claim == 'numerical': result['numerical_pass'] = True
    if claim == 'prediction': result['reference_checks'][0]['predicted'] = 0.
    if claim == 'physical_calls': result['physical_calls'] = 1
    checked = runner.checked_result(row, result)
    assert checked['status'] == 'adapter_contract_failure' and not checked['reference_match']
    assert checked['numerical_pass'] is False
    assert checked['output_accounting']['passed'] == checked['output_accounting']['numerically_valid'] == 0


def test_ap2_runner_rejects_computed_scalars_without_complete_physical_evidence(monkeypatch, ap2_jobs):
    from scripts import isae_suite_ap2
    monkeypatch.setattr(runner.importlib, 'import_module', lambda name: isae_suite_ap2)
    row = next(row for row in ap2_jobs if row['execution_route'] == 'worker')
    result = dict(status='computed', numerical_pass=True, reference_match=True,
        operations=dict(cold_solves=1, fresh_residuals=1, retries=0), physical_calls=2,
        source_pins_unchanged=True, kernel_pins_unchanged=True, physical_checks=[],
        reference_checks=[dict(name=name, **reference, predicted=reference['expected'], passed=True)
                          for name, reference in isae_suite_ap2.reference_contract(row).items()])
    checked = runner.checked_result(row, result)
    assert checked['status'] == 'adapter_contract_failure' and checked['numerical_pass'] is False
    assert 'physical' in checked['contract_error']['ap2_result_contract_error']
    assert checked['output_accounting']['numerically_valid'] == checked['output_accounting']['passed'] == 0


def test_ap2_report_collects_descriptive_mesh_diagnostics_and_keeps_full_catalog(monkeypatch, ap2_jobs):
    from scripts import isae_suite_ap2
    monkeypatch.setattr(runner.importlib, 'import_module', lambda name: isae_suite_ap2)
    source_catalog, _ = expansion_selection_fixture()
    plan = dict(catalog=source_catalog, jobs=ap2_jobs, code_sha256={}, runtime={}, execution_policy={'adapters': ['ap2']})
    result = runner.report(plan, {}, runner.ROOT, 0.)
    diagnostic = result['adapter_mesh_diagnostics']['ap2']
    assert len(diagnostic) == 117 and all(row['status'] == 'UNAVAILABLE' and row['passed'] is None for row in diagnostic)
    assert result['case_families'] == 41 and result['full_suite_validated'] is False
    assert sum(row['status'] == 'NO_SELECTED_COMPARISON_JOBS' for row in result['cases']) == 40


@pytest.fixture(scope='module')
def ae1_jobs():
    if not (runner.ROOT/'.reference/isae-validation/manifest.json').is_file():
        pytest.skip('Optional original ISAE archive unavailable')
    from scripts import isae_suite_ae1
    return isae_suite_ae1.plan(runner.ROOT)


def test_ae1_default_registration_retains_all_sensors_and_unknown_starts(monkeypatch, ae1_jobs):
    assert runner.ADAPTERS['ae1'] == 'isae_suite_ae1' and runner.HELPERS['ae1'] == ['isae_suite_ap1.py']
    loaded = []
    def load(name):
        loaded.append(name)
        return SimpleNamespace(plan=lambda root: ae1_jobs if name == 'isae_suite_ae1' else [])
    monkeypatch.setattr(runner.importlib, 'import_module', load)
    planned = runner.plan_jobs(runner.ROOT)
    assert 'isae_suite_ae1' in loaded and len(planned) == 200
    assert sum(row['expected_outputs'] for row in planned) == 1200
    active = [row for row in planned if row['execution_route'] != 'unsupported']
    assert len(active) == 196 and all(row['target_kind'] == 'paired_sensor' for row in active)
    assert {row['nominal'] for row in planned} == {40, 80}
    pins = runner.code_pins(runner.ROOT, ['ae1'])
    assert {'scripts/isae_suite_ae1.py', 'scripts/isae_suite_ap1.py'} <= pins.keys()


def test_ae1_unknown_starts_finish_inline_without_importing_or_starting_physics(monkeypatch, tmp_path, ae1_jobs):
    from scripts import isae_suite_ae1
    selected = [row for row in ae1_jobs if row['execution_route'] == 'unsupported']
    assert len(selected) == 4 and sum(row['expected_outputs'] for row in selected) == 24
    monkeypatch.setattr(runner.asyncio, 'create_subprocess_exec',
                        lambda *a, **k: pytest.fail('Unknown AE1 initial state started a solver subprocess'))
    monkeypatch.setattr(runner.importlib, 'import_module', lambda name: isae_suite_ae1)
    results = {}
    asyncio.run(runner.execute({'jobs': selected, 'code_sha256': {}}, tmp_path,
                              SimpleNamespace(workers=1, timeout_seconds=1), results))
    assert len(results) == 4 and all(row['status'] == 'unsupported' for row in results.values())
    assert all(row['execution_kind'] == 'inline_blocker_validation' and not row['subprocess_started'] and
               row['physical_calls'] == row['physical_solver_calls'] == row['production_imports'] == 0
               for row in results.values())
    counts = runner.output_totals(selected, results)
    assert counts['required'] == counts['reported'] == counts['finished_required'] == 24
    assert counts['finite'] == counts['passed'] == 0


@pytest.mark.parametrize('claim', ['computed', 'match', 'numerical', 'prediction', 'physical_calls', 'imports'])
def test_ae1_initial_blockers_cannot_be_promoted_to_computation(ae1_jobs, claim):
    from scripts import isae_suite_ae1
    row = next(row for row in ae1_jobs if row['execution_route'] == 'unsupported')
    result = deepcopy(isae_suite_ae1.validate_blocked(runner.ROOT, row))
    if claim == 'computed': result['status'] = 'computed'
    if claim == 'match': result['reference_match'] = True
    if claim == 'numerical': result['numerical_pass'] = True
    if claim == 'prediction': result['reference_checks'][0]['predicted'] = 0.
    if claim == 'physical_calls': result['physical_calls'] = 1
    if claim == 'imports': result['production_imports'] = 1
    checked = runner.checked_result(row, result)
    assert checked['status'] == 'adapter_contract_failure' and not checked['reference_match']
    assert checked['numerical_pass'] is False
    assert checked['output_accounting']['passed'] == checked['output_accounting']['numerically_valid'] == 0


def test_ae1_computed_sensor_row_requires_complete_physical_evidence(monkeypatch, ae1_jobs):
    from scripts import isae_suite_ae1
    monkeypatch.setattr(runner.importlib, 'import_module', lambda name: isae_suite_ae1)
    row = next(row for row in ae1_jobs if row['execution_route'] == 'worker')
    result = dict(status='computed', numerical_pass=True, reference_match=True,
        operations=dict(cold_solves=1, fresh_residuals=1, retries=0), physical_calls=2,
        source_pins_unchanged=True, kernel_pins_unchanged=True, physical_checks=[],
        reference_checks=[dict(name=name, **reference, predicted=reference['expected'], passed=True)
                          for name, reference in isae_suite_ae1.reference_contract(row).items()])
    checked = runner.checked_result(row, result)
    assert checked['status'] == 'adapter_contract_failure' and checked['numerical_pass'] is False
    assert 'physical' in checked['contract_error']['ae1_result_contract_error']
    assert checked['output_accounting']['numerically_valid'] == checked['output_accounting']['passed'] == 0


def test_ae1_selected_report_retains_full_catalog_and_descriptive_mesh(monkeypatch, ae1_jobs):
    from scripts import isae_suite_ae1
    monkeypatch.setattr(runner.importlib, 'import_module', lambda name: isae_suite_ae1)
    source_catalog, _ = expansion_selection_fixture()
    plan = dict(catalog=source_catalog, jobs=ae1_jobs, code_sha256={}, runtime={}, execution_policy={'adapters': ['ae1']})
    result = runner.report(plan, {}, runner.ROOT, 0.)
    diagnostic = result['adapter_mesh_diagnostics']['ae1']
    assert len(diagnostic) == 100 and all(row['status'] == 'UNAVAILABLE' and row['passed'] is None for row in diagnostic)
    assert result['case_families'] == 41 and result['full_suite_validated'] is False
    assert sum(row['status'] == 'NO_SELECTED_COMPARISON_JOBS' for row in result['cases']) == 40


@pytest.fixture
def report_acceptance_inputs(monkeypatch):
    # Direct CLI execution places scripts on sys.path; reproduce that import
    # environment while loading the runner through its existing test fixture.
    monkeypatch.syspath_prepend(str(runner.ROOT / 'scripts'))
    from isae_acceptance import reference_acceptance_policy

    def make(relative_tolerance=.03, numerical_pass=True, status='computed'):
        job = dict(id='A-0', case_id='A', adapter='acceptance_test', expected_outputs=1)
        raw = dict(status=status, numerical_pass=numerical_pass, reference_match=False,
            reference_checks=[dict(name='CL', predicted=1.02, expected=1.,
                                   tolerance=5e-7, passed=False)],
            numerical_checks=[dict(name='circulation residual', tolerance=1e-8,
                                   value=1e-12 if numerical_pass else 1e-2,
                                   passed=numerical_pass)])
        strict = runner.checked_result(job, raw)
        plan = dict(catalog=catalog(), jobs=[job], code_sha256={}, runtime={},
                    execution_policy={'adapters': []},
                    reference_acceptance=reference_acceptance_policy(
                        relative_tolerance=relative_tolerance))
        return plan, {job['id']: strict}
    return make


def test_report_accepts_two_percent_but_preserves_strict_evidence(report_acceptance_inputs, tmp_path):
    plan, results = report_acceptance_inputs()
    original = deepcopy(results)
    saved_result = tmp_path / 'result.json'
    runner.write_json(saved_result, results['A-0'])
    original_bytes = saved_result.read_bytes()

    data = runner.report(plan, results, runner.ROOT, .1)
    view = data['jobs'][0]['result']
    check = view['reference_checks'][0]
    assert data['output_accounting']['passed'] == 1
    assert data['strict_output_accounting']['passed'] == 0
    assert view['reference_match'] is True and view['strict_reference_match'] is False
    assert check['passed'] is True and check['strict_passed'] is False
    assert check['effective_tolerance'] == .03 and check['tolerance'] == 5e-7
    assert view['strict_output_accounting'] == original['A-0']['output_accounting']
    assert view['numerical_checks'] == original['A-0']['numerical_checks']
    assert data['cases'][0]['status'] == 'SELECTED_SCOPE_MATCHES'
    assert data['cases'][0]['complete_family_reproduction'] is False
    assert data['cases'][1]['status'] == 'NO_SELECTED_COMPARISON_JOBS'
    assert results == original and saved_result.read_bytes() == original_bytes
    # Saved job evidence still satisfies the original strict adapter contract
    # when loaded again during --resume.
    resumed = runner.checked_result(plan['jobs'][0], json.loads(saved_result.read_text()))
    assert resumed == original['A-0']


def test_report_zero_relative_tolerance_restores_strict_outcomes(report_acceptance_inputs):
    plan, results = report_acceptance_inputs(relative_tolerance=0)
    original = deepcopy(results)
    data = runner.report(plan, results, runner.ROOT, .1)
    assert data['output_accounting'] == data['strict_output_accounting']
    assert data['output_accounting']['passed'] == 0
    view = data['jobs'][0]['result']
    assert view['reference_match'] is view['strict_reference_match'] is False
    assert view['reference_checks'][0]['effective_tolerance'] == 5e-7
    assert data['cases'][0]['status'] == 'ARCHIVED_OUTPUT_DIFFERENCES'
    assert results == original


@pytest.mark.parametrize('status', ['computed', 'timeout', 'unsupported'])
def test_report_relative_acceptance_does_not_hide_numerical_or_execution_failures(
        report_acceptance_inputs, status):
    plan, results = report_acceptance_inputs(numerical_pass=False, status=status)
    original = deepcopy(results)
    data = runner.report(plan, results, runner.ROOT, .1)
    view = data['jobs'][0]['result']
    assert view['reference_match'] is False
    assert view['reference_checks'][0]['passed'] is False
    assert view['status'] == original['A-0']['status']
    assert view['numerical_pass'] is False
    assert data['output_accounting']['passed'] == 0
    assert data['output_accounting']['numerically_valid'] == 0
    assert data['output_accounting']['required'] == 1
    assert data['cases'][0]['jobs_matching'] == 0
    assert data['cases'][0]['status'] != 'SELECTED_SCOPE_MATCHES'
    assert results == original
