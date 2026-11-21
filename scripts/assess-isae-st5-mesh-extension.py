"""Audit and publish the bounded ST-5 mesh extension without rerunning solves."""
import hashlib
import json
from pathlib import Path
import statistics
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT/'artifacts/isae/st5-mesh-extension-20261103'
STUDY = BASE/'large-mesh'
DEST = ROOT/'docs/validation/isae-st5-mesh-extension-20261103'


def read(path):
    return json.loads(Path(path).read_text())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def check_pins(pins):
    for name, value in pins.items():
        assert sha(ROOT/name) == value, name


def pin(path):
    return dict(path=str(path.relative_to(ROOT)), sha256=sha(path))


plan = read(STUDY/'plan.json')
check_pins(plan['pins'])
cases = []
all_groups = {}
for name in plan['cases']:
    levels = []
    for level in (3, 4):
        stage = STUDY/name/f'run-level{level}'
        execution = read(stage/'execution.json')
        assert execution['exit_code'] == 0 and execution['process_reaped']
        assert not execution['timed_out'] and execution['physical_checks_pass']
        check_pins(execution['input_sha256'])
        check_pins(execution['output_sha256'])
        summary = read(stage/'summary.json')
        case_plan = read(stage/'plan.json')
        comparison = read(stage/f'level{level}/comparison.json')
        assert summary['all_numerical_gates_pass']
        assert summary['cold_solves'] == summary['fresh_residuals'] == 1
        assert summary['original_acceptance_unchanged']
        assert summary['original_required_pair'] == [1, 2]
        assert summary['extension_pair'] == [level-1, level]
        assert len(comparison['rows']) == 80
        assert comparison['full_structural_rows'] == 0
        columns = summary['columns']
        assert len(columns) == 28
        groups = {}
        for group, indices in case_plan['field_groups'].items():
            matches = sum(abs(row['values'][i]-row['expected'][i]) <= row['half_last_place'][i]
                          for row in comparison['rows'] for i in indices)
            groups[group] = dict(matches=matches, total=80*len(indices))
            total = all_groups.setdefault(group, dict(matches=0, total=0))
            for key in total:
                total[key] += groups[group][key]
        assert sum(v['total'] for v in groups.values()) == 2160
        errors = {}
        for field in ('z-z0', 'tw-tw0', 'Mc_prime'):
            i = columns.index(field)
            percentages = [100*abs(row['values'][i]-row['expected'][i])/abs(row['expected'][i])
                           for row in comparison['rows'] if abs(row['expected'][i]) > 1e-8]
            errors[field] = dict(median_percent=statistics.median(percentages),
                                 maximum_percent=max(percentages), nonzero_rows=len(percentages))
        change = summary['mesh_changes'][-1]
        assert [change['coarse'], change['fine']] == [level-1, level]
        assert len(change['measures']) == 14
        mesh_passes = sum(v['passes'] for v in change['measures'].values())
        assert summary['all_fine_mesh_gates_pass'] == (mesh_passes == 14)
        levels.append(dict(level=level, intervals_by_beam=comparison['intervals_by_beam'],
            mesh_passes=mesh_passes, mesh_total=14, mesh_change=change,
            maximum_change_percent=100*max(v['relative_change'] for v in change['measures'].values()),
            reference_groups=groups, reference_error=errors,
            physical_checks=comparison['checks'], solve_seconds=comparison['seconds'],
            execution=execution, summary=pin(stage/'summary.json'),
            plan=pin(stage/'plan.json'), comparison=pin(stage/f'level{level}/comparison.json')))
    cases.append(dict(case=name, levels=levels))

browser_path = BASE/'browser-level4-restored/report.json'
browser = read(browser_path)
assert browser['status'] == 'PASS_OFFLINE_ST5_LARGE_MESH_AND_SAVED_PROJECT'
assert browser['planned_solves'] == 0 and browser['request_counts']['solve'] == 0
assert browser['retained_browser_solves'] == 1
assert browser['checks_passed'] == browser['checks_total']
tests = ET.parse(BASE/'mesh-tests.xml').getroot()
test_count = sum(int(e.attrib['tests']) for e in tests.iter('testsuite'))
assert test_count == 42
assert all(int(e.attrib.get(k, 0)) == 0 for e in tests.iter('testsuite') for k in ('failures', 'errors'))
rejected = read(BASE/'20lb_80_20/run-level4/execution.json')
assert rejected['exit_code'] == 1 and rejected['process_reaped']
report = dict(status='REFINEMENT_COMPLETE_REFERENCE_DIFFERENCES_RETAINED', goal_complete=False,
    source_plan=pin(STUDY/'plan.json'), assessment_script=pin(Path(__file__)),
    successful_cold_solves=8, successful_fresh_residuals=8, cases=cases,
    final_mesh_cases_pass=sum(c['levels'][-1]['mesh_passes'] == 14 for c in cases),
    final_mesh_measures_pass=sum(c['levels'][-1]['mesh_passes'] for c in cases),
    final_mesh_measures_total=56, reference_groups=all_groups,
    original_registered_matches=13833, original_registered_total=25920,
    original_counts_unchanged=True, mesh_limit_change=plan['mesh_limit_change'],
    mesh_tests=dict(passed=test_count, receipt=pin(BASE/'mesh-tests.xml')),
    earlier_limit_rejection=pin(BASE/'20lb_80_20/run-level4/execution.json'),
    browser=dict(receipt=pin(browser_path), status=browser['status'],
                 retained_attempt=pin(BASE/'browser-level4/report.json'),
                 checks_passed=browser['checks_passed'], checks_total=browser['checks_total'],
                 solve_seconds=browser['cases'][0]['solve_seconds'], parity=browser['parity']),
    limitations=[
        'Convergence is distinct from agreement with historical ASWING output; no complete structural row matches.',
        'The historical node arrays, startup state and exporter implementation are not recovered.',
        'f_reac is retained as a diagnostic display comparison, not validated reaction physics.',
        'All-zero and echoed-input matches do not establish nonzero dynamic or aerodynamic behavior.',
        'Only the input limits changed in the solver; other retained results are evidence on their recorded kernels.',
        'Browser coverage is one selected load case and grid, not all ST families or 3D rendering.'])
assert report['final_mesh_cases_pass'] == 4 and report['final_mesh_measures_pass'] == 56
DEST.with_suffix('.json').write_text(json.dumps(report, indent=2, allow_nan=False)+'\n')
lines = ['# ST-5 mesh convergence extension', '',
    'All four supported ST-5 load cases now pass the existing **0.1% mesh-change limit** on the two finer grids: **56/56 measures**. All eight new cold solves and fresh saved-state residual checks pass. This resolves the selected mesh-convergence failures, not the remaining archived-ASWING differences.', '',
    'The original three grids and failed comparisons remain recorded. Two exact bisections add 304/256 and 608/512 intervals on the forward/rear beams. Original loads, equations, duplicate output rows, field recovery and tolerances are unchanged; no parameter is fitted to the archive.', '',
    '| Load case | 280→560 intervals | 560→1,120 intervals | Finest median archived error: Z / twist / bending moment |',
    '|---|---:|---:|---|']
for case in cases:
    a, b = case['levels']
    error = ' / '.join(f"{b['reference_error'][key]['median_percent']:.4g}%" for key in ('z-z0','tw-tw0','Mc_prime'))
    lines.append(f"| {case['case']} | {a['mesh_passes']}/14; max {a['maximum_change_percent']:.5f}% | {b['mesh_passes']}/14; max {b['maximum_change_percent']:.5f}% | {error} |")
lines += ['',
    'Mesh percentages use the maximum absolute change over all 80 original rows divided by the corresponding fine-grid deformation envelope. Reference percentages above use all nonzero archived values with magnitude greater than 1e-8 on the finest grid. Near-zero values still receive the original absolute/printed-precision comparison. Finer convergence does not imply closer agreement with a historical finite-grid calculation.', '',
    'The original registered count remains **13,833/25,920 scalar matches**. This extension adds a separate 17,280 scalar comparisons across eight grids; they are not added silently to the registered score:', '',
    '| Supplemental field group | Printed-precision matches | Interpretation |',
    '|---|---:|---|']
labels = {'structural':'Structural fields', 'conditional_zero':'Conditional zero fields',
          'interval_input_echo':'Echoed input fields', 'unresolved_scalar_weight_display':'Unresolved f_reac display'}
meaning = {'structural':'Physical output comparison; no complete row matches.',
           'conditional_zero':'No evidence of nonzero response.', 'interval_input_echo':'Input/display agreement.',
           'unresolved_scalar_weight_display':'Diagnostic only; exporter law unresolved.'}
for group, counts in all_groups.items():
    lines.append(f"| {labels[group]} | {counts['matches']:,}/{counts['total']:,} | {meaning[group]} |")
lines += ['',
    'The first 608/512 attempt was rejected before solving by the application’s 512-interval input ceiling. The ceiling is now 1,024 intervals per beam, with matching global/per-beam controls. The numerical expressions are unchanged. All 13 retained grid settings and all 509 previously accepted integer counts normalize identically under the old and new code; 42 focused discretization tests pass. The Fourier-mode limit and default resolution are unchanged. The rejected attempt is retained.', '',
    f"The actual built browser performs one offline cold solve of `20lb_90_10` on 608/512 intervals in **{browser['cases'][0]['solve_seconds']:.2f} s**. All **{browser['checks_passed']}/{browser['checks_total']} audit checks** pass, including both 1,024-interval controls, exact mesh import, full native-result parity, portable project export/reopen, byte-identical restored results and no recomputation. Maximum parity error is **{browser['parity']['max_fraction']:.5g}** of the unchanged `2e-8 + 2e-8*abs(reference)` allowance across **{browser['parity']['numeric']:,} numeric fields**. GPU rendering is disabled for this bounded run; it is not a 3D rendering check.", '',
    'The initial browser audit stopped after the successful solve because its older expected request omitted the now-explicit `strut_mode: bilateral`. The pinned native bridge uses the same bilateral default, both results contain no struts, and every native result field passes the original numerical parity limit. The completed browser result is retained unchanged. A second, saved-only browser session finishes export/reopen checks with zero additional solves. Both attempts are recorded; no physical tolerance or result field was removed.', '',
    'Jobs run serially with one BLAS thread. Each native child has a 180-second wall limit and 512 MiB address-space limit. Receipts include source hashes, resource use and process cleanup. The retained first refinement used the old input validator; exact gate-only compatibility is verified before reuse. No completed solve was repeated.', '',
    'Historical mesh/startup/exporter identity, other original configurations and whole-family/native agreement remain unresolved. Other structural families retain the [initial ST-1–ST-6 results](isae-st1-st6-current-20261103.md); ST-4 has a separate [independent equation audit](isae-st4-transfer-diagnostic-20261103.md).', '',
    '[Machine report](isae-st5-mesh-extension-20261103.json). Raw plans, all comparisons, retained failed attempt and browser receipts: `artifacts/isae/st5-mesh-extension-20261103/`.']
DEST.with_suffix('.md').write_text('\n'.join(lines)+'\n')
print(json.dumps(dict(final_mesh_cases_pass=report['final_mesh_cases_pass'],
    final_mesh_measures_pass=report['final_mesh_measures_pass'], reference_groups=all_groups,
    browser_checks=browser['checks_passed'])))
