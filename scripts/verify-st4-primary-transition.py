"""Audit primary ST-4 evidence and the exact still-air source transition.

Run from a source checkout or the extracted evidence archive. This audit proves
source and evidence consistency; experimental acceptance remains unestablished.
"""
from pathlib import Path
import argparse
import hashlib
import json
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024*1024), b''):
            h.update(block)
    return h.hexdigest()


def read(path, digest=None):
    if digest is not None:
        assert sha(path) == digest, path
    return json.loads(Path(path).read_text())


def modules(folder):
    return {p.name: sha(p) for p in sorted((folder/'openswing').glob('*.py'))}


def native_report(path, pins, air=False):
    report = read(path)
    assert report['modules'] == pins and len(report['runs']) == report['requested'] == 126
    expected_status = ('PRIMARY_CONDITIONAL_STILL_AIR_RUNS_COMPLETE_WITH_REJECTIONS_RETAINED' if air
                       else 'PRIMARY_CONDITIONAL_MODAL_COMPARISONS_COMPUTED_NOT_PHYSICALLY_VALIDATED')
    assert report['status'] == expected_status and not report['full_physical_validation']
    if air:
        assert report['density'] == 1.225 and report['counts'] == dict(computed=126, rejected=0)
    for name, digest in report['scripts_and_inputs'].items():
        source = ROOT/'scripts'/name if name.endswith('.py') else ROOT/'.reference/isae-st4-experiment-inputs'/name
        assert sha(source) == digest, name
    for row in report['runs']:
        cache = read(ROOT/row['cache'], row['sha256'])
        assert cache['status'] == row['status'] == 'computed'
        assert cache['identity']['modules'] == pins
        assert cache['identity']['specification'] == row['specification']
        assert cache['identity']['scripts_and_inputs'] == report['scripts_and_inputs']
        assert hashlib.sha256(cache['source'].encode()).hexdigest() == cache['identity']['source_sha256']
        assert sha(ROOT/cache['matrices']['path']) == cache['matrices']['sha256']
        result = cache['result']
        assert result['converged'] and len(result['modes']) == 12
        if air:
            assert not result['vacuum'] and result['fluid']['kind'] == 'quiescent'
            assert result['fluid']['density'] == 1.225
            assert result['fluid']['mean_velocity_body'] == [0., 0., 0.]
        else:
            assert result['vacuum']
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--work', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    work = args.work.resolve()
    baseline = modules(work/'primary-baseline-source')
    current = modules(ROOT)
    integration = read(work/'root-integration.json')
    assert len(baseline) == 97 and len(current) == 98
    assert baseline == integration['baseline_modules'] and current == integration['candidate_modules']
    assert current == modules(work/'quiescent-candidate') == modules(work/'integrated-kernel')
    changed = sorted(name for name in current if baseline.get(name) != current[name])
    assert changed == ['equilibrium_state.py', 'frequency_response.py', 'linear_dynamics.py',
                       'network.py', 'quiescent.py', 'reduced_model.py', 'stability.py', 'time_initialization.py']
    for row in integration['changes']:
        assert row['candidate_sha256'] == sha(ROOT/row['path'])
        assert row['baseline_sha256'] == baseline.get(Path(row['path']).name)
    for row in integration['web_changes']:
        assert sha(ROOT/row['path']) == row['candidate_sha256'] == sha(work/'quiescent-ui'/row['path'])
        old = work/'primary-baseline-source'/row['path']
        assert (sha(old) if old.exists() else None) == row['original_sha256']
    changed_web = {row['path'] for row in integration['web_changes']}
    for old in (work/'primary-baseline-source/web').rglob('*'):
        if old.is_file() and old.relative_to(work/'primary-baseline-source').as_posix() not in changed_web:
            assert sha(old) == sha(ROOT/'web'/old.relative_to(work/'primary-baseline-source/web'))
    for name in ['asw.py', 'geometry.py', 'inertia.py', 'descriptor_mass.py']:
        assert current[name] == baseline[name]

    inventory = read(work/'integrated-inventory.json')
    old_inventory = read(work/'baseline-isae-suite-inventory.json')
    assert inventory['kernel_modules'] == current and inventory['models'] == old_inventory['models']
    assert inventory['cases'] == old_inventory['cases'] and inventory['model_files'] == 279
    assert inventory['parse_counts'] == dict(parsed=177, rejected=102)

    test_count, test_pins = 0, {}
    for name in ['integrated-tests', 'integrated-reuse-tests']:
        tree = ET.parse(work/(name+'.xml'))
        assert not any(tree.findall('.//'+tag) for tag in ['failure', 'error', 'skipped'])
        cases = tree.findall('.//testcase')
        test_count += len(cases)
        for case in cases:
            path = case.attrib['classname'].replace('.', '/')+'.py'
            test_pins[path] = sha(ROOT/path)
    assert test_count == 176
    original_test = (work/'quiescent-candidate/tests/test_quiescent.py').read_text()
    old_path = "SOURCE=Path('/home/userland/aswing/.reference/isae-validation/f62943df20e9e4d7d9f50e070477b22426b5f865/3 - Structure/CASE - ST4 Concentrated weight/Simulation_files/Weight7a/7a_b11.asw')"
    assert old_path in original_test
    assert (ROOT/'tests/test_quiescent.py').read_text() == original_test.replace(old_path, "SOURCE=Path(__file__).parent/'fixtures/isae-zero-area.asw'")
    test_pins['tests/fixtures/isae-zero-area.asw'] = sha(ROOT/'tests/fixtures/isae-zero-area.asw')
    test_pins['tests/quiescent-settings.test.mjs'] = sha(ROOT/'tests/quiescent-settings.test.mjs')
    assert 'pass 1' in (work/'integrated-js-tests.log').read_text()

    for endpoint in ['lower', 'upper']:
        native_report(work/f'primary-native-{endpoint}.json', baseline)
        native_report(work/f'primary-air-{endpoint}.json', current, air=True)
    numerical = read(work/'primary-numerical.json')
    assert numerical['complete'] and numerical['modules'] == baseline
    assert numerical['native_states'] == 252 and numerical['reference_states'] == 672
    assert numerical['matched_modes'] == 1512 and numerical['complete_refinement_groups'] == 84
    assert numerical['script_sha256'] == sha(ROOT/'scripts/summarize-isae-st4-primary.py')
    assert not numerical['full_physical_validation'] and not numerical['accuracy_acceptance_established']
    reference = read(work/'primary-reference-reciprocal.json')
    assert len(reference['runs']) == 672 and reference['status'] != 'RUNNING'
    for row in reference['runs']:
        read(ROOT/row['cache'], row['sha256'])
    air = read(work/'primary-air-comparison/final.json')
    assert air['complete'] and air['native_states'] == air['terminal_native_states'] == air['expected_native_states'] == 252
    assert air['modules'] == current and air['reference_states'] == 672 and air['density_matched_reference_states'] == 336
    assert air['matched_modes'] == 1512 and air['complete_refinement_groups'] == 84
    assert not air['rejected'] and not air['cache_audit_errors'] and not air['missing_native_states']
    assert not air['full_physical_validation'] and not air['accuracy_acceptance_established']
    assert air['script_sha256'] == sha(ROOT/'scripts/summarize-isae-st4-primary-air.py')
    assert all(value for key, value in air['checks'].items() if key != 'all_six_frequency_errors_decrease_in_complete_groups')
    assert air['method']['frequency_order_retained'] and air['method']['kinetic_metric_includes_air']
    assert not any(air['method'][key] for key in ['nearest_frequency_assignment_used', 'frequency_fitting_or_input_tuning_used', 'measured_triplets_averaged'])
    assert air['experiment']['scalar_comparisons'] == 1296 and not air['experiment']['missing_triplet_comparisons']
    assert len(air['experiment']['all_observations']) == 78 and len(air['experiment']['not_clear_cells']) == 6
    for name in ['primary-air-lower.json', 'primary-air-upper.json', 'primary-reference-reciprocal.json']:
        assert air['input_reports'][name]['sha256'] == sha(work/name)
    for pin in air['companion_outputs'].values():
        assert sha(work/'primary-air-comparison'/Path(pin['path']).name) == pin['sha256']
    independent_air = read(work/'physical-setup/primary-air-audit.json')
    assert independent_air['status'] == 'PRIMARY_AIR_AUDIT_COMPLETE_WITH_DIAGNOSTICS_RETAINED'
    assert independent_air['full_sweep_complete'] and not independent_air['summarizer_review_pending']
    assert not independent_air['physical_validation'] and not independent_air['accuracy_acceptance_established']
    for key, count in dict(expected_native_states=252, snapshot_states=252, computed_states=252,
                           rejected_states=0, original_observations=78, complete_triplets=72,
                           incomplete_triplets=6, scalar_comparisons=1296).items():
        assert independent_air['counts'][key] == count
    assert independent_air['source_pins']['summarize-isae-st4-primary-air.py']['sha256'] == air['script_sha256']
    assert independent_air['source_pins']['comparison']['sha256'] == sha(work/'primary-air-comparison/final.json')

    candidate = read(work/'quiescent-candidate/candidate-verification.json')
    assert candidate['status'] == 'PASSED'
    assert candidate['module_sha256'] == {'openswing/'+name: digest for name, digest in current.items()}
    assert len(candidate['ST4']) == 2 and len(candidate['analytic']) == 8
    for case in candidate['ST4']:
        assert case['checks']['vacuum_A_M_base_bitwise_preserved'] and case['checks']['vacuum_identity_unchanged']
        assert case['checks']['quiescent_A_max_difference'] == case['checks']['quiescent_base_max_difference'] == 0
    pilot = read(work/'quiescent-primary/review.json')
    assert pilot['all9computed'] and pilot['all_physical_matrix_and_base_controls_passed'] and pilot['all_A_bytes_exactly_match_vacuum']
    independent_ui = read(work/'physical-setup/quiescent-frame-fix-independent-review.json')
    assert independent_ui['status'] == 'FRAME_RETENTION_FIX_INDEPENDENTLY_VERIFIED' and not independent_ui['page_errors']
    for name, pin in independent_ui['source_pins'].items():
        assert sha(ROOT/'web'/name) == pin

    runtime = work/'quiescent-runtime/2026-10-15T09-34-05-839Z-1803'
    wasm = read(runtime/'report.json')
    assert wasm['status'] == 'PASS_ST4_QUIESCENT_WASM' and wasm['modules'] == current and len(wasm['rows']) == 3
    assert wasm['script_sha256'] == sha(ROOT/'scripts/test-st4-quiescent-wasm.mjs')
    assert wasm['runtime_inputs_sha256'] == sha(runtime/'inputs.json')
    for row in wasm['rows']:
        assert row['status'] == 'PASS'
        assert sha(runtime/Path(row['matrices']['path']).name) == row['matrices']['sha256']
    browser_paths = list((work/'integrated-browser-results').rglob('st4-quiescent-browser.json'))
    assert len(browser_paths) == 1
    browser = read(browser_paths[0])
    assert browser['status'] == 'PASS_PRIMARY_ST4_QUIESCENT_FRESH_OFFLINE_BROWSER'
    assert browser['offline'] and browser['served_build'] and browser['modules'] == current and len(browser['runs']) == 3
    assert browser['test_sha256'] == sha(ROOT/'tests/browser/st4-quiescent.spec.js')
    assert browser['runtime_inputs_sha256'] == sha(runtime/'inputs.json')
    for row in browser['runs']:
        assert row['result']['software_provenance']['modules'] == current
        assert not row['result']['vacuum'] and row['result']['fluid']['kind'] == 'quiescent'
        assert all(m['frequency_difference_Hz'] < 2e-6 and m['shape_assurance'] > 1-2e-8 for m in row['matches'])

    evidence = [
        'primary-native-lower.json', 'primary-native-upper.json', 'primary-reference-reciprocal.json',
        'primary-numerical.json', 'primary-native-experiment.json', 'primary-air-lower.json', 'primary-air-upper.json',
        'primary-air-comparison/final.json', 'quiescent-primary/review.json', 'quiescent-primary/shape-diagnosis.json',
        'physical-setup/additional-native-refinement.json', 'primary-targeted-refinement.json',
        'physical-setup/primary-input-audit.json', 'physical-setup/primary-reference-reciprocal-audit.json',
        'physical-setup/primary-air-audit.json', 'physical-setup/quiescent-frame-fix-independent-review.json',
        'quiescent-ui/frame-fix-evidence.json', 'quiescent-candidate/candidate-verification.json',
        'quiescent-runtime/2026-10-15T09-34-05-839Z-1803/report.json', 'integrated-inventory.json',
        'integrated-tests.xml', 'integrated-reuse-tests.xml', 'integrated-js-tests.log',
        browser_paths[0].relative_to(work).as_posix(), 'root-integration.json']
    documented = read(work/'documentation-evidence.json')
    for name, digest in documented.items():
        assert sha(ROOT/'docs/validation'/name) == digest
    result = dict(status='PASS_ST4_PRIMARY_SOURCE_AND_NUMERICAL_EVIDENCE_WITH_PHYSICAL_LIMITATIONS',
                  baseline_modules=baseline, candidate_modules=current, changed_solver_modules=changed,
                  web_changes=integration['web_changes'], selected_python_tests=176, selected_js_tests=1,
                  test_source_sha256=test_pins, literal_models=279, parse_counts=inventory['parse_counts'],
                  native_vacuum_states=252, native_still_air_states=252, independent_reference_states=672,
                  wasm_cases=3, offline_browser_cases=3, vacuum_numerical_summary=numerical['summary'],
                  still_air_numerical_summary=air['summary'], experimental_summary=air['experiment']['summary'],
                  documentation_evidence_sha256=documented,
                  evidence_sha256={name: sha(work/name) for name in evidence}, script_sha256=sha(__file__),
                  full_suite_rerun=False, full_physical_validation=False, accuracy_acceptance_established=False,
                  limitations=air['limitations'])
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False)+'\n')
    print(result['status'], flush=True)


if __name__ == '__main__':
    main()
