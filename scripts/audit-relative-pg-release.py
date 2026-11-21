"""Verify a built relative-PG release against frozen sources and scoped evidence.

Read-only except for a new external report. This is a byte/provenance audit, not
a fresh numerical test or full-app browser run. The release spec must be frozen
after the final documentation/evidence selection and supplied by SHA256.
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from zipfile import ZipFile
import argparse
import hashlib
import importlib.util
import json
import time
import traceback
import urllib.parse
import xml.etree.ElementTree as ET

HELPER_SHA = 'de67db5dc4c75005eaf05d3285682e7a2ae326569dc153a23f2507b01f826506'
COMPOSITION_SHA = '7c975b8be70942dc49a301c6bd4c61dc60c84decd3c3ba1333661ef10e411b65'
OLD_COMPOSITION_SHA = 'd3d0afbe45aa86a7478d8b7b47ccb5d8d2e1af2802063d5304a4d411d12822b0'
OLD_EVIDENCE_SHA = '88f1eabee848800aaa1ab2c479fafd3597192f82cedb828393ab7f3dcd737187'
OLD_AUDIT_SHA = '0e56fc2da5e4e13c2ebfdd9ef368ea9587b2877e232d1d6130713dae4816972a'
OLD_CLOSEOUT_SHA = '60348044362826dc5180aa893537d2660912a107ab580cdc85f6a13d048d29ab'
NATIVE_SHA = '03593f9ae1a017ed1bc7d3e107b49c530897676f2b633e75430bfb10e7cc2484'
WASM_SHA = '4ede642e05b5edcf4af191a668b26baa4dcb192812148cb5d723f580120991d6'
PYTHON_SHA = '23eb2e7cb979833b1ae9d1e8367d5fb47472a52e9cf7ab00fb5f78a3acb2f436'
TEST_PINS_SHA = '47c2e81d905b203fb618dbad5ee5c9bb663571913c6a27a16eb23d93ef2331ca'
ROOT_SMOKE_SHA = 'a297aefc69ebcad58b0f02e930a8fe3dcc298ee9ed2b50ae08675342ff196f15'
INSTALLED_SHA = '65a13bac7c64b0b24d733f14e19531a3b8083c9189c29716f7dc9dd23c887c66'
AUTHOR_REVIEW_SHA = '81081deba78dc98e3ead5c6167521b3a6dd2aa384231cf312665fd091504249d'
FULL_APP_SHA = '9abb737f3dbca586b631b75d189bb960c58d0d594c8ba3844a75a480a76317b4'
FULL_APP_PINS_SHA = '4baec7458ddde9271bfbf6ee8e39595237ecb7d1a76ead29e48cd4c772b66a3d'
PRODUCTION_MANIFEST = dict(bytes=2134, sha256='b1b8e291d407e1052407c30a3c963f5af3dac075c0a3507a274245637f009e01')
FULL_APP_COMPACT_MANIFEST = dict(bytes=2032, sha256='fe72fff11e096e1c0a6f0ce13a82b93c540027f0b45543d9e705058b77e1e637')
WORKER_CONSUMER_SHA = 'fdd3784bf5e4edfe4c28aa5f68c633deb3f8e616d39f20673fdb0b2165f0cf78'
CHANGED = {'aero.py', 'tangent_influences.py', 'vortex_tangent.py'}
ADDED_ARCHIVES = {'docs/validation/isae-ffwt1-nominal-evidence.zip',
                  'docs/validation/isae-ffwt1-nominal-07-evidence.zip',
                  'docs/validation/relative-pg-evidence.zip'}
FINAL_CLAIMS = dict(recorded_new_full_app_equilibrium=True, original_full_app_harness_pass=False,
                    followup_residual_replay=True, numerical_runs_by_release_auditor=False,
                    full_repository_suite=False, experimental_validation=False)


def load_helpers(root):
    path = root / 'scripts/audit-hinge-solver-release.py'
    if hashlib.sha256(path.read_bytes()).hexdigest() != HELPER_SHA:
        raise ValueError('Historical release auditor/helper changed.')
    spec = importlib.util.spec_from_file_location('pinned_hinge_release_helpers', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def check_spec(h, root, work, spec):
    h.require(spec['format'] == 'openswing-relative-pg-release-spec' and spec['version'] == 1
              and spec['status'] == 'FINAL_FROZEN_BEFORE_BUILD', 'Spec is not final/frozen.')
    h.require(spec['composition_sha256'] == COMPOSITION_SHA, 'Wrong release composition.')
    h.require(spec['claims'] == FINAL_CLAIMS, 'Unsupported or unqualified release claims.')
    required = {'docs/STATUS.md', 'docs/validation/isae-validation.md', 'scripts/prepare.mjs',
                'scripts/package-source.py', 'scripts/package-local.py', 'tests/test_relative_pg.py'}
    h.require(required <= set(spec['root_files']), 'Spec omits release source/docs pins.')
    for folder, key in [(root, 'root_files'), (work, 'work_files')]:
        for name, expected in spec[key].items():
            h.require(h.pin(h.relative(folder, name)) == expected, f'Frozen spec file changed: {key}/{name}')
    for assertion in spec['json_assertions']:
        group = assertion['root']
        h.require(group in ('root', 'work'), 'Unknown JSON assertion root.')
        h.require(assertion['file'] in spec[group + '_files'], 'Unpinned JSON assertion source.')
        value = h.read(h.relative(root if group == 'root' else work, assertion['file']))
        for key in assertion['path']:
            value = value[key]
        h.require(value == assertion['equals'], f'JSON assertion failed: {assertion}')
    h.require(set(spec['added_archives']) == ADDED_ARCHIVES,
              'Expected exact nominal06, nominal07 and relative-PG raw archive additions.')
    for name, expected in spec['added_archives'].items():
        h.require(name.startswith('docs/validation/') and name.endswith('.zip'), 'Invalid added raw archive path.')
        h.require(h.pin(h.relative(root, name)) == expected, f'New archive differs: {name}')
    return dict(root_files=spec['root_files'], work_files=spec['work_files'],
                json_assertions=spec['json_assertions'], added_archives=spec['added_archives'], claims=spec['claims'])


def check_sources(h, root, work, installed):
    cpath = work / 'relative-pg-candidate/composition.json'
    opath = work / 'integrated-06/composition.json'
    h.require(h.sha(cpath) == COMPOSITION_SHA and h.sha(opath) == OLD_COMPOSITION_SHA, 'Composition changed.')
    c, old = h.read(cpath), h.read(opath)
    pins = c['modules']
    h.require(len(pins) == 103 and c['baseline_modules'] == old['modules']
              and c['parent_composition_sha256'] == OLD_COMPOSITION_SHA, 'Composition baseline differs.')
    h.require(set(c['changes']) == CHANGED == {n for n in pins if pins[n] != old['modules'][n]},
              'Unexpected kernel change set.')
    for name, row in c['changes'].items():
        h.require(row == dict(before=old['modules'][name], after=pins[name]), 'Change pin mismatch.')
    directories = [work / 'relative-pg-candidate/candidate/openswing',
                   work / 'independent/relative-pg-wasm/candidate/openswing']
    if installed:
        directories += [root / p for p in ('openswing', 'public/kernel', 'dist/kernel')]
    for folder in directories:
        h.require({p.name for p in folder.glob('*.py')} == set(pins), f'Kernel membership mismatch: {folder}')
        for name, value in pins.items():
            h.require(h.sha(folder / name) == value, f'Kernel source differs: {folder}/{name}')
    for folder in [work / 'integrated-06/web', root / 'web']:
        h.require({p.name for p in folder.iterdir() if p.is_file()} == set(old['web']), 'Web membership changed.')
        for name, value in old['web'].items():
            h.require(h.sha(folder / name) == value, f'Web source changed: {name}')
    test = work / 'relative-pg-candidate/portable-tests/test_relative_pg.py'
    h.require(h.sha(test) == c['new_test_sha256'], 'New test changed.')
    if installed:
        h.require(h.sha(root / 'tests/test_relative_pg.py') == c['new_test_sha256'], 'Installed test changed.')
    h.require(h.sha(work / 'relative-pg-candidate/changes.patch') == c['patch_sha256'], 'Candidate patch changed.')
    return pins, dict(composition=h.pin(cpath), baseline_composition=h.pin(opath), changes=c['changes'],
                      unchanged_web_sources=len(old['web']), module_count=len(pins), new_test=h.pin(test))


def check_historical(h, root, work):
    folder = root / 'docs/validation/hinge-solver-evidence'
    h.require(h.sha(folder / 'manifest.json') == OLD_EVIDENCE_SHA, 'Historical evidence manifest changed.')
    h.require(h.sha(work / 'release/audit-hinge-solver-release.json') == OLD_AUDIT_SHA
              and h.sha(work / 'release/closeout.json') == OLD_CLOSEOUT_SHA, 'Historical release records changed.')
    manifest = h.read(folder / 'manifest.json')
    h.require(set(manifest['files']) == {p.name for p in folder.iterdir() if p.is_file()} - {'manifest.json'},
              'Historical selected evidence membership changed.')
    for name, row in manifest['files'].items():
        expected = {k: row[k] for k in ('bytes', 'sha256')}
        h.require(h.pin(h.relative(folder, name)) == expected
                  == h.pin(h.relative(work, row['original_artifact'])), f'Historical evidence changed: {name}')
    old = h.read(work / 'integrated-06/composition.json')
    tests = dict(old['test_files'])
    tests.update({n: r['sha256'] for n, r in h.read(work / 'release-tests/release-files.json')['install_root_relative_files'].items()})
    for name, value in tests.items():
        h.require(h.sha(h.relative(root, name)) == value, f'Historical portable test changed: {name}')
    lifecycle = h.read(folder / 'cold-copy-review.json')['test_sha256']
    h.require(h.sha(root / 'tests/test_hinge_initial_state_ownership.py') == lifecycle, 'Lifecycle tests changed.')
    suites = {}
    for filename, count in [('hinge-tests.xml', 132), ('combined-tests.xml', 47), ('dense-tests.xml', 25)]:
        xml = ET.parse(folder / filename).getroot()
        actual = sum(int(s.get('tests', 0)) for s in xml.iter('testsuite'))
        failures = sum(int(s.get('failures', 0)) + int(s.get('errors', 0)) for s in xml.iter('testsuite'))
        h.require(actual == count and failures == 0, 'Historical native record differs.')
        suites[filename] = dict(tests=actual, failures=failures, kernel='integrated-06')
    return dict(selected_manifest_sha256=OLD_EVIDENCE_SHA, selected_files=len(manifest['files']),
                audit_sha256=OLD_AUDIT_SHA, closeout_sha256=OLD_CLOSEOUT_SHA, native_records=suites,
                historical_raw_bundle_sha256=h.RAW_SHA,
                scope='Preserved records only; these native/full-app controls were not rerun on the relative-PG kernel.')


def check_new_controls(h, root, work, pins):
    native_folder = work / 'relative-pg-candidate'
    h.require(h.sha(native_folder / 'summary.json') == NATIVE_SHA, 'Native summary changed.')
    native = h.read(native_folder / 'summary.json')
    h.require(native['modules'] == pins and native['composition_sha256'] == COMPOSITION_SHA
              and native['tests']['candidate']['passed'] == 148 and native['tests']['candidate']['exit_code'] == 0
              and native['all_sessions_reaped'] and not native['live_servers'], 'Native control record failed.')
    h.require(h.sha(work / 'integrated-07/root-smoke.json') == ROOT_SMOKE_SHA
              and h.sha(work / 'integrated-07/composition.json') == INSTALLED_SHA, 'Installed smoke source pin changed.')
    smoke, installed = h.read(work / 'integrated-07/root-smoke.json'), h.read(work / 'integrated-07/composition.json')
    h.require(smoke['status'] == 'PASS_INSTALLED_ROOT_RELATIVE_PG_TESTS' and smoke['tests'] == 11
              and smoke['exit_code'] == 0 and smoke['reaped'] and smoke['overlaps_candidate_148_checks']
              and smoke['composition_sha256'] == INSTALLED_SHA and installed['modules'] == pins
              and installed['candidate_sha256'] == COMPOSITION_SHA, 'Installed root smoke scope differs.')
    h.require(h.sha(work / 'relative-pg-review/review.json') == AUTHOR_REVIEW_SHA, 'Final author review record changed.')
    for key, filename in [('candidate', 'tests.log'), ('baseline_new_regression', 'baseline-regression.log')]:
        h.require(h.sha(native_folder / filename) == native['tests'][key]['log_sha256'], 'Native log changed.')
    h.require(h.sha(native_folder / 'retained-check.json') == native['tests']['retained_arrays']['report_sha256'],
              'Retained native array evidence changed.')
    for name, value in native['independent_evidence'].items():
        h.require(h.sha(h.relative(work, name)) == value, 'Independent precision evidence changed.')
    h.require(h.sha(native_folder / 'candidate-test-pins.json') == TEST_PINS_SHA, 'Native test pins changed.')
    test_pins = h.read(native_folder / 'candidate-test-pins.json')
    h.require(test_pins['modules'] == pins, 'Native tested modules differ.')
    for old_path, value in test_pins['tests'].items():
        name = Path(old_path).name
        path = native_folder / ('portable-tests' if name == 'test_relative_pg.py' else 'tested-original-files/tests') / name
        h.require(h.sha(path) == value, f'Tested snapshot differs: {name}')
        if name != 'test_relative_pg.py':
            h.require(h.sha(root / 'tests' / name) == value, f'Installed existing test differs: {name}')
    folder = work / 'independent/relative-pg-wasm'
    h.require(h.sha(folder / 'browser-result.json') == WASM_SHA and h.sha(folder / 'python-result.json') == PYTHON_SHA,
              'New WASM report changed.')
    browser, python = h.read(folder / 'browser-result.json'), h.read(folder / 'python-result.json')
    status = 'PASS_BROWSER_PYODIDE_RELATIVE_PG_KERNEL_CONTROLS'
    h.require(browser['status'] == python['status'] == status and browser['python'] == python
              and browser['modules'] == pins and browser['composition_sha256'] == COMPOSITION_SHA
              and not python['equilibrium_solve'], 'New WASM scope/kernel mismatch.')
    h.require(not browser['page_errors'] and not browser['blocked_requests'] and not browser['post_run_input_errors']
              and browser['browser_closed'] and browser['server_closed'], 'New WASM execution did not close cleanly.')
    for filename, field in [('input-pins.json', 'input_pins_sha256'), ('browser.mjs', 'runner_sha256'), ('check.py', 'python_sha256')]:
        h.require(h.sha(folder / filename) == browser[field], f'WASM input changed: {filename}')
    input_pins = h.read(folder / 'input-pins.json')['files']
    for name, row in input_pins.items():
        h.require(h.sha(h.relative(folder, name)) == row['sha256'], f'WASM input pin mismatch: {name}')
    for route, expected in browser['assets'].items():
        if route.startswith('/test/'):
            path = h.relative(folder, route.removeprefix('/test/'))
        elif route.startswith('/runtime/'):
            path = h.relative(root / 'public', route[1:])
        else:
            h.require(route == '/', 'Unknown WASM test route.')
            continue  # The 99-byte control harness is not the production app HTML.
        h.require(h.pin(path) == expected, f'WASM served evidence bytes changed: {route}')
    h.require(set(python['imports']) == set(pins)
              and all(v == '/home/pyodide/openswing/' + k for k, v in python['imports'].items()), 'WASM import routing differs.')
    h.require(len(python['retained']) == 2 and {r['checkpoint'] for r in python['retained']} == {'00493', '00842'},
              'Retained WASM case set differs.')
    for row in python['retained']:
        h.require(len(row['cache_checks']) == 10 and all(c['exact'] for c in row['cache_checks']), 'WASM cache control failed.')
        h.require(len(row['fields']) == 2 and all(f['shape'] == [184, 184, 3]
                  and f['native_relative_max_absolute_difference'] == 0 for f in row['fields']), 'WASM/native arrays differ.')
    return dict(native_summary_sha256=NATIVE_SHA, native_tests=native['tests'], browser_sha256=WASM_SHA,
                python_sha256=PYTHON_SHA, tested_modules=103, retained_exact_cache_checks=20,
                installed_root_smoke_sha256=ROOT_SMOKE_SHA, installed_root_tests=11,
                installed_root_tests_overlap_native_148=True, author_review_sha256=AUTHOR_REVIEW_SHA,
                scope='148 scoped native controls and actual Chromium/Pyodide kernel/partial/cache controls; the separate full-app evidence is checked independently.')


def check_full_app(h, root, work, pins, spec):
    prefix = 'independent/relative-pg-full-app/'
    folder = work / prefix
    h.require(h.sha(folder / 'summary.json') == FULL_APP_SHA
              and h.sha(folder / 'artifact-pins.json') == FULL_APP_PINS_SHA, 'Qualified full-app freeze changed.')
    for name in ['summary.json', 'artifact-pins.json', 'browser.json', 'comparison.json', 'request-audit.json',
                 'output.json', 'residual-replay/native-report.json', 'residual-replay/wasm-report.json',
                 'residual-replay/browser.json', 'view-only/browser.json', 'view-only-readiness-failure/browser.json']:
        h.require(prefix + name in spec['work_files'], 'Full-app record omitted from frozen release spec: ' + name)
    summary = h.read(folder / 'summary.json')
    h.require(summary['numerical_completion'] and summary['raw_browser_status'] == 'FAIL_RETAINED'
              and summary['original_failure_stage'] == 'post_export_bitwise_mesh_assertion'
              and not summary['equilibrium_rerun'] and summary['modules'] == pins
              and summary['candidate_composition_sha256'] == COMPOSITION_SHA and summary['ui_files'] == 51
              and summary['both_replay_gates_pass'] and not summary['replay_correction_performed']
              and summary['all_browser_servers_closed'] and summary['all_sessions_reaped']
              and not summary['experimental_validation'] and not summary['accuracy_acceptance_established'],
              'Full-app qualified summary scope differs.')
    artifact_pins = h.read(folder / 'artifact-pins.json')['files']
    for name, row in artifact_pins.items():
        expected = row if isinstance(row, str) else row['sha256']
        h.require(h.sha(h.relative(folder, name)) == expected, 'Frozen full-app artifact differs: ' + name)
    browser = h.read(folder / 'browser.json')
    h.require(browser['status'] == 'FAIL_RETAINED' and browser['worker_terminal_retained']
              and browser['solve_request_retained'] and browser['browser_closed'] and browser['server_closed']
              and not browser['page_errors'] and not browser['blocked_requests'] and not browser['post_run_source_errors'],
              'Original full-app failure/terminal evidence differs.')
    output = h.read(folder / 'output.json')
    comparison, request = h.read(folder / 'comparison.json'), h.read(folder / 'request-audit.json')
    h.require(request['status'] == 'PASS_ACTUAL_UI_REQUEST_EQUIVALENCE' and request['cold_start']
              and request['solver_defaults']['structured_acceptance'] == 1e-12, 'Actual UI request/gate differs.')
    h.require(comparison['status'] == 'COMPLETED_RETAINED_NATIVE_WASM_COMPARISON'
              and comparison['strict_gate_preserved'] and comparison['actual_residual'] <= 1e-12
              and not comparison['equilibrium_rerun'] and not comparison['accuracy_acceptance_established'],
              'Raw comparison must not invent a cross-runtime accuracy acceptance.')
    replays = {}
    for kind in ['native', 'wasm']:
        report = h.read(folder / 'residual-replay' / (kind + '-report.json'))
        h.require(report['status'] == 'COMPLETED_RESIDUAL_ONLY_REPLAY' and report['runtime_kind'] == kind
                  and not report['equilibrium_solve'] and not report['correction_performed']
                  and report['returned_state_unchanged'] and report['passes_unchanged_1e_12_gate']
                  and report['full_original_residual'] <= 1e-12 and report['modules'] == pins
                  and report['output_sha256'] == h.sha(folder / 'output.json'), 'Residual-only replay differs: ' + kind)
        replays[kind] = dict(report=h.pin(folder / 'residual-replay' / (kind + '-report.json')),
                             residual=report['full_original_residual'], correction_performed=False)
    replay_browser = h.read(folder / 'residual-replay/browser.json')
    h.require(replay_browser['status'] == 'COMPLETED_BROWSER_WASM_RESIDUAL_ONLY_REPLAY'
              and not replay_browser['equilibrium_solve'] and not replay_browser['correction_performed']
              and not replay_browser['errors'] and not replay_browser['blocked']
              and replay_browser['browser_closed'] and replay_browser['server_closed'], 'WASM replay lifecycle differs.')
    view, failed_view = h.read(folder / 'view-only/browser.json'), h.read(folder / 'view-only-readiness-failure/browser.json')
    h.require(view['status'] == 'PASS_VIEW_ONLY_SAVED_UI_OUTPUT' and view['offline'] and view['roundtrip_output_exact']
              and not view['equilibrium_rerun'] and not view['errors'] and not view['blocked']
              and view['browser_closed'] and view['server_closed'] and failed_view['status'] == 'FAIL_RETAINED'
              and view['original_output_sha256'] == h.sha(folder / 'output.json'), 'View-only follow-up scope/failure differs.')
    return dict(summary=h.pin(folder / 'summary.json'), artifact_manifest=h.pin(folder / 'artifact-pins.json'),
                artifact_count=len(artifact_pins), recorded_new_full_app_equilibrium=True,
                original_full_app_harness_pass=False, original_browser_status=browser['status'],
                original_browser=h.pin(folder / 'browser.json'), request=h.pin(folder / 'request-audit.json'),
                comparison=h.pin(folder / 'comparison.json'), original_ui_residual=comparison['actual_residual'],
                followup_residual_replay=replays, view_only_status=view['status'],
                retained_view_readiness_failure_status=failed_view['status'], numerical_runs_by_release_auditor=False,
                scope='The original solve/export completed, then its bitwise mesh assertion failed. Separate fresh residual-only replays passed the unchanged gate; view-only follow-up passed without another solve. Raw failures remain failures.')


def check_assets(h, root, work, pins, url):
    registry = work / 'full-app-06/tested-assets.json'
    h.require(h.sha(registry) == h.ASSETS_SHA, 'Old tested asset registry changed.')
    tested = h.read(registry)['assets']
    h.require(len(tested) == 123, 'Old asset count changed.')
    manifest_path = work / 'full-app-06/kernel-manifest.json'
    names = h.read(manifest_path)
    h.require(isinstance(names, list) and names == sorted(pins) and len(names) == len(set(names)) == 103,
              'Historical manifest schema/order mismatch.')
    encoded = ('[' + ', '.join(json.dumps(n) for n in names) + ']').encode()
    h.require(manifest_path.read_bytes() == encoded and h.pin(manifest_path) == PRODUCTION_MANIFEST,
              'Historical manifest serialization differs.')
    for directory in ('public/kernel', 'dist/kernel'):
        h.require((root / directory / 'manifest.json').read_bytes() == encoded,
                  'Current prepare filename-list serialization/order differs.')
    old_kernel = h.read(work / 'integrated-06/composition.json')['modules']
    h.require({n.removeprefix('/kernel/'): r['sha256'] for n, r in tested.items() if n.endswith('.py')}
              == old_kernel, 'Historical tested module map differs.')
    expected, changed = {}, {}
    for route, row in tested.items():
        h.require(route.startswith('/') and not route.startswith('//') and urllib.parse.urlsplit(route).path == route,
                  'Invalid asset route.')
        origin = {'work': work, 'openswing': root}.get(row['root'])
        h.require(origin is not None, 'Unknown old asset origin.')
        old_pin = {k: row[k] for k in ('bytes', 'sha256')}
        h.require(h.pin(h.relative(origin, row['path'])) == old_pin, f'Historical asset origin changed: {route}')
        new_pin = old_pin
        if route.startswith('/kernel/') and route.endswith('.py'):
            name = route.removeprefix('/kernel/')
            new_pin = h.pin(root / 'openswing' / name)
            h.require(new_pin['sha256'] == pins[name], 'Unexpected source module hash.')
        elif route == '/kernel/manifest.json':
            new_pin = h.pin(root / 'public/kernel/manifest.json')
        expected[route] = new_pin
        if new_pin != old_pin:
            changed[route] = dict(before=old_pin, after=new_pin)
        h.require(h.pin(h.relative(root / 'dist', 'index.html' if route == '/' else route[1:])) == new_pin,
                  f'Built asset differs: {route}')
    allowed = {'/kernel/' + n for n in CHANGED} | {'/kernel/manifest.json'}
    h.require(set(changed) <= allowed and {'/kernel/' + n for n in CHANGED} <= set(changed),
              'Changed runtime asset set exceeds approved three modules/manifest.')
    actual_full_app = h.read(work / 'independent/relative-pg-full-app/browser.json')['assets']
    full_app_bytes = {name: {k: row[k] for k in ('bytes', 'sha256')} for name, row in actual_full_app.items()}
    manifest_route = '/kernel/manifest.json'
    h.require(set(full_app_bytes) == set(expected), 'New full-app route membership differs.')
    h.require(all(full_app_bytes[name] == wanted for name, wanted in expected.items() if name != manifest_route),
              'A non-manifest new full-app asset differs from final runtime bytes.')
    # The pinned new harness used candidate insertion order and compact JSON;
    # production retains old06 lexicographic order and comma-space JSON. Accept
    # only these two fixed byte strings, not arbitrary equivalent JSON. The
    # exact pinned consumer awaits all downloads, writes every source, then
    # imports bridge (worker.js13-35); manifest order does not execute modules.
    fresh_names = list(h.read(work / 'independent/relative-pg-full-app/source-pins.json')['modules'])
    compact = json.dumps(fresh_names, separators=(',', ':')).encode()
    compact_pin = dict(bytes=len(compact), sha256=hashlib.sha256(compact).hexdigest())
    h.require(len(fresh_names) == len(set(fresh_names)) == 103 and set(fresh_names) == set(names)
              and fresh_names != names and compact_pin == FULL_APP_COMPACT_MANIFEST == full_app_bytes[manifest_route]
              and expected[manifest_route] == PRODUCTION_MANIFEST and h.sha(root / 'web/worker.js') == WORKER_CONSUMER_SHA,
              'Manifest or consumer differs beyond the exact pinned order/serialization distinction.')
    def compare(item):
        route, wanted = item
        actual = h.fetch(url, route)
        h.require(actual == wanted, f'Served asset differs: {route}')
        return route, actual
    with ThreadPoolExecutor(max_workers=6) as pool:
        served = dict(pool.map(compare, sorted(expected.items())))
    h.require(h.fetch(url, '/distribution.json') == h.pin(root / 'dist/distribution.json'), 'Served metadata differs.')
    return dict(count=len(served), unchanged_count=len(served) - len(changed), changed_count=len(changed),
                changed_routes=changed, allowed_changed_routes=sorted(allowed), served=served,
                fresh_full_app_assets=dict(bit_exact_count=len(expected) - 1,
                    manifest_order_and_serialization=dict(production=PRODUCTION_MANIFEST, browser=FULL_APP_COMPACT_MANIFEST,
                        order_difference=True, unique_members_equal=True, modules=103,
                        production_order=names, browser_order=fresh_names, consumer_sha256=WORKER_CONSUMER_SHA,
                        consumer_source_lines='web/worker.js:13-35',
                        consumer_semantics='Await all source downloads; write all103 files; then import openswing.bridge. Manifest order does not execute modules.',
                        accepted_difference='Only pinned candidate insertion order/compact JSON versus pinned lexicographic/comma-space JSON.')),
                manifest=dict(pin=h.pin(manifest_path), schema='ordered filename list', order='lexicographic',
                              serialization='JSON strings joined by comma-space; no trailing newline'),
                scope='All123 production routes are hashed over HTTP.122 match new full-app bytes exactly. The manifest has the same103 unique names in the two explicitly pinned orders/serializations; production retains exact old06 bytes. The pinned consumer writes all sources before import. Raw harness failures remain separate from numerical completion.')


def check_archives(h, root, work, url, spec):
    d = root / 'docs/validation'
    metadata = h.read(root / 'public/distribution.json')
    h.require(metadata == h.read(root / 'dist/distribution.json') and metadata['format'] == 'openswing-distribution'
              and metadata['version'] == 1 and metadata['kind'] == 'hosted', 'Distribution metadata differs.')
    old_catalog_path = work / 'release/before/archive-index.json'
    h.require(h.sha(old_catalog_path) == h.CATALOG_SHA, 'Historical raw catalog changed.')
    old_catalog, catalog = h.read(old_catalog_path), h.read(d / 'archive-index.json')
    old, current, added = old_catalog['archives'], catalog['archives'], spec['added_archives']
    h.require(len(old) == 133 and not set(old) & set(added) and current == dict(old, **added),
              'Raw catalog does not preserve the exact prior133 plus explicit additions.')
    raw_paths = {p for p in d.rglob('*.zip') if p.is_file()}
    h.require(set(current) == {p.relative_to(root).as_posix() for p in raw_paths}, 'Raw archive membership differs.')
    for name, row in current.items():
        h.require(h.relative(root, name).stat().st_size == row['bytes'], 'Raw source size differs.')
    h.require(metadata['validation']['archives'] == metadata['validation']['catalog_archives'] == len(current),
              'Raw metadata counts differ.')
    downloads = {}
    for key, filename in [('source', 'openswing-source.zip'), ('validation', 'openswing-validation.zip')]:
        expected = {k: metadata[key][k] for k in ('bytes', 'sha256')}
        h.require(metadata[key]['file'] == filename, 'Unexpected download filename.')
        for directory in ('public', 'dist'):
            h.require(h.pin(root / directory / filename) == expected, f'Download hash differs: {directory}/{filename}')
        h.require(h.fetch(url, '/' + filename, head=True)['bytes'] == expected['bytes'], 'HTTP download size differs.')
        downloads[key] = expected
    source_files = [root / n for n in h.SOURCE_SINGLE if (root / n).is_file()]
    for folder in h.SOURCE_ROOTS:
        source_files.extend(p for p in (root / folder).rglob('*') if p.is_file()
                            and '__pycache__' not in p.parts and '.pytest_cache' not in p.parts and p not in raw_paths)
    h.require(all(not p.is_symlink() and p.resolve().is_relative_to(root) for p in source_files), 'External source member.')
    source_map = {p.relative_to(root).as_posix(): p for p in source_files}
    h.require(len(source_map) == len(source_files), 'Duplicate source membership.')
    with ZipFile(root / 'public/openswing-source.zip') as source, ZipFile(root / 'public/openswing-validation.zip') as raw, \
            ZipFile(root / 'dist/openswing-local.zip') as local:
        source_names, raw_names, local_names = map(h.members, [source, raw, local])
        notice, catalog_name = 'openswing/VALIDATION-ARCHIVES.txt', 'openswing/docs/validation/archive-index.json'
        h.require(source_names == {'openswing/' + n for n in source_map} | {notice}, 'Source ZIP membership differs.')
        for name, path in source_map.items():
            h.require(h.member_pin(source, 'openswing/' + name) == h.pin(path), f'Source member differs: {name}')
        h.require(raw_names == {'openswing/' + n for n in current} | {notice, catalog_name}, 'Raw ZIP membership differs.')
        h.require(source.read(catalog_name) == raw.read(catalog_name) == (d / 'archive-index.json').read_bytes(), 'Catalog copies differ.')
        h.require(source.read(notice) == raw.read(notice), 'Source/raw notices differ.')
        # The aggregate raw bundle changed. Hash each nested member against the
        # old immutable133 catalog or explicit new pins, not just new metadata.
        for name, expected in current.items():
            h.require(h.member_pin(raw, 'openswing/' + name) == expected, f'Raw member content differs: {name}')
        excluded = {root / 'dist' / n for n in ('openswing-local.zip', 'openswing-validation.zip', 'distribution.json')}
        local_files = [p for p in (root / 'dist').rglob('*') if p.is_file() and p not in excluded and '.openai' not in p.parts]
        h.require(all(not p.is_symlink() and p.resolve().is_relative_to(root / 'dist') for p in local_files), 'External local member.')
        h.require(local_names == {p.relative_to(root / 'dist').as_posix() for p in local_files}
                  | {'README-local.txt', 'distribution.json'}, 'Local ZIP membership differs.')
        for path in local_files:
            name = path.relative_to(root / 'dist').as_posix()
            h.require(h.member_pin(local, name) == h.pin(path), f'Local ZIP member differs: {name}')
        h.require(json.loads(local.read('distribution.json')) == dict(metadata, kind='local', validation=None)
                  and 'openswing-validation.zip' not in local_names, 'Local download metadata/scope differs.')
    downloads['local'] = h.pin(root / 'dist/openswing-local.zip')
    h.require(h.fetch(url, '/openswing-local.zip', head=True)['bytes'] == downloads['local']['bytes'], 'HTTP local size differs.')
    return dict(metadata=metadata, downloads=downloads, source_members=len(source_names), local_members=len(local_names),
                raw_members=len(raw_names), unchanged_raw_archives=len(old), added_archives=added,
                historical_raw_bundle_sha256=h.RAW_SHA, source_file_pins={n: h.pin(p) for n, p in sorted(source_map.items())},
                raw_check_scope='New whole public/dist bundle hashes and every nested raw member checked; old133 entries retain exact hashes.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--work', type=Path, required=True)
    parser.add_argument('--url', default='http://127.0.0.1:8000')
    parser.add_argument('--spec', type=Path)
    parser.add_argument('--spec-sha256')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--preflight-only', action='store_true', help='Candidate/evidence checks only; no built/download/HTTP checks or release PASS.')
    a = parser.parse_args()
    root, work, output = a.root.resolve(), a.work.resolve(), a.output.resolve()
    h = load_helpers(root)
    h.require(not output.exists() and not output.is_relative_to(root), 'Use a new external output path.')
    endpoint = urllib.parse.urlsplit(a.url)
    h.require(endpoint.scheme == 'http' and endpoint.hostname in ('127.0.0.1', 'localhost', '::1')
              and not endpoint.path and not endpoint.query and not endpoint.fragment, 'Use a local HTTP origin.')
    start = time.monotonic()
    report = dict(status='RUNNING', started_utc=datetime.now(timezone.utc).isoformat(), script_sha256=h.sha(Path(__file__)),
                  helper_sha256=HELPER_SHA, full_repository_suite=False, numerical_runs_by_release_auditor=False,
                  experimental_validation=False, preflight_only=a.preflight_only)
    code = 1
    try:
        h.phase(report, 'candidate sources and unchanged web')
        pins, report['source'] = check_sources(h, root, work, not a.preflight_only)
        report['modules'] = pins
        h.phase(report, 'historical evidence and coverage')
        report['historical_evidence'] = check_historical(h, root, work)
        report['coverage'] = h.check_coverage(root)
        h.phase(report, 'new scoped native and WASM controls')
        report['new_controls'] = check_new_controls(h, root, work, pins)
        if a.preflight_only:
            report['status'] = 'PASS_CANDIDATE_EVIDENCE_PREFLIGHT_ONLY_NOT_A_RELEASE_AUDIT'
        else:
            h.require(a.spec is not None and a.spec_sha256 is not None, 'Final audit requires a SHA-pinned frozen release spec.')
            h.require(h.sha(a.spec) == a.spec_sha256, 'Release spec hash differs.')
            report['spec_pin'] = h.pin(a.spec)
            spec = h.read(a.spec)
            h.phase(report, 'frozen final source and documentation selection')
            report['selection'] = check_spec(h, root, work, spec)
            h.phase(report, 'qualified full-app completion with retained harness failures')
            report['full_app'] = check_full_app(h, root, work, pins, spec)
            h.phase(report, 'built and served asset classification')
            report['runtime'] = check_assets(h, root, work, pins, a.url)
            h.phase(report, 'source local and expanded raw downloads')
            report['archives'] = check_archives(h, root, work, a.url, spec)
            report['status'] = 'PASS_RELATIVE_PG_RELEASE_WITH_RETAINED_PHYSICAL_LIMITATIONS'
        report['limitations'] = [
            'Historical native/full-app/physical studies keep their original103 or98 module pins; this audit does not rerun them.',
            'New evidence includes scoped native/WASM kernel controls and separately pinned nominal and qualified full-app records; no full repository suite is claimed.',
            'The original full-app solve/export completed but the harness failed its bitwise mesh assertion. Residual-only and view-only follow-ups are separate; retained failures are not relabeled PASS.',
            'The17/24/0 coverage ledger and177/102 literal parse inventory remain unchanged; conditional nominal comparisons do not validate FFWT1.',
            'HTTP runtime assets are hashed in full; large HTTP downloads are checked by size and independently verified local package bytes.']
        code = 0
    except Exception as error:
        report.update(status='FAIL_RETAINED', error=type(error).__name__ + ': ' + str(error), traceback=traceback.format_exc())
    report['elapsed_seconds'] = time.monotonic() - start
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('x') as stream:
        stream.write(json.dumps(report, indent=2, sort_keys=True) + '\n')
    print(json.dumps(dict(status=report['status'], output=str(output), sha256=h.sha(output),
                          elapsed_seconds=report['elapsed_seconds'], error=report.get('error'))), flush=True)
    raise SystemExit(code)


if __name__ == '__main__':
    main()
