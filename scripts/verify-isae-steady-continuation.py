"""Verify the portable continuation implementation and retain its evidence pins.

The six-job native study used the earlier frozen serializer. Verify that only
canonical JSON hashing differs, without rewriting those historical packets.
"""
import ast
import hashlib
import json
from pathlib import Path
import sys
import xml.etree.ElementTree as ET
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
STUDY = ROOT/'artifacts/isae/ffwt4-continuation-20261106'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def read(path):
    return json.loads(path.read_text())


def pin(path):
    return dict(path=str(path.relative_to(ROOT)), bytes=path.stat().st_size,
                sha256=sha(path.read_bytes()))


def main():
    current = {p.name: sha(p.read_bytes()) for p in sorted((ROOT/'openswing').glob('*.py'))}
    snapshots = {}
    for name in ('ffwt4-continuation-20261106', 'ffwt4-continuation-json-20261106'):
        folder = ROOT/'.reference/solver-snapshots'/name
        records = read(folder/'manifest.json')['files']
        archived = {}
        for record in records:
            path = Path(record['archived'])
            assert path.stat().st_size == record['original']['bytes']
            archived[path.name] = sha(path.read_bytes())
            assert archived[path.name] == record['original']['sha256']
        assert set(archived) == set(current)
        snapshots[name] = archived
    before = snapshots['ffwt4-continuation-20261106']
    assert snapshots['ffwt4-continuation-json-20261106'] == current
    assert [name for name in current if current[name] != before[name]] == ['steady_continuation.py']
    def without_canonical(path):
        tree = ast.parse(path.read_text())
        tree.body = [node for node in tree.body if not
                     (isinstance(node, ast.FunctionDef) and node.name == 'canonical')]
        return ast.dump(tree)
    assert without_canonical(ROOT/'openswing/steady_continuation.py') == without_canonical(
        ROOT/'.reference/solver-snapshots/ffwt4-continuation-20261106/openswing/steady_continuation.py')
    for location in ('public/kernel', 'dist/kernel'):
        assert {p.name: sha(p.read_bytes()) for p in (ROOT/location).glob('*.py')} == current
    for location in ('public/openswing-source.zip', 'dist/openswing-source.zip', 'dist/openswing-local.zip'):
        prefix = 'kernel/' if location.endswith('local.zip') else 'openswing/openswing/'
        with ZipFile(ROOT/location) as archive:
            for name, expected in current.items():
                assert sha(archive.read(prefix+name)) == expected, (location, name)
            if not location.endswith('local.zip'):
                for relative in ('docs/validation/ISAE_STATUS.md','docs/STATUS.md','docs/REQUIREMENTS.md',
                        'docs/validation/isae-ffwt4-continuation-20261106.md',
                        'docs/validation/isae-suite-backlog.md','docs/validation/isae-suite-backlog.json',
                        'tests/test_steady_continuation.py','scripts/test-steady-continuation-browser.mjs'):
                    assert archive.read('openswing/'+relative) == (ROOT/relative).read_bytes(), (location, relative)
    tests = {}
    for name, count in (('tests-numeric-final.xml',38), ('tests-transport-final.xml',2)):
        suite = ET.parse(STUDY/name).getroot().find('testsuite')
        assert int(suite.attrib['tests']) == count
        assert all(int(suite.attrib[key]) == 0 for key in ('failures','errors','skipped'))
        tests[name] = count
    browser = read(STUDY/'browser/report.json')
    assert browser['status'] == 'PASS' and browser['modules'] == current
    assert len(browser['checks']) >= 20 and all(row['passed'] for row in browser['checks'])
    assert not browser['page_errors'] and not browser['external_requests']
    assert (STUDY/'browser/runner-at-execution.mjs').read_bytes() == (ROOT/'scripts/test-steady-continuation-browser.mjs').read_bytes()
    assessment = read(STUDY/'assessment.json')
    assert assessment['status'] == 'COMPLETE_COLD_EQUILIBRIUM' and assessment['complete']
    assert assessment['accepted_load_steps'] == 17 and assessment['rejected_load_attempts'] == 0
    assert assessment['original_targets_identical'] and assessment['original_uninterrupted_targets_compared'] == 11
    for row in assessment['jobs']:
        assert sha((STUDY/row['job']/'result.json').read_bytes()) == row['result_sha256']
        assert read(STUDY/row['job']/'execution.json')['exit_code'] == 0
    receipts = read(STUDY/'terminal-receipts.json')
    for action in ('final numeric tests','final JavaScript transport tests','portable kernel build',
                   'built browser continuation','final source and local packaging'):
        assert any(row['action'] == action and row.get('exit_code') == 0 for row in receipts), action
    # Check the retained full-load physical state with the shipped kernel too.
    sys.path.insert(0, str(ROOT))
    import numpy as np
    from openswing.asw import parse_asw
    from openswing.aero import FlightCondition
    from openswing.source_airflow import SourceAirflowNetwork
    from openswing.equilibrium_state import restore
    request = read(STUDY/'job-006/request.json')
    model = parse_asw(request['source'], beam_interpolation=request['numerics']['beam_interpolation'])
    net = SourceAirflowNetwork(model,request['panels'],FlightCondition(**request['condition']),None,[],steady_trim=True)
    state = restore(net,read(STUDY/'job-006/result.json')['equilibrium_state'])
    residual = float(np.max(abs(net.residual(state))))
    assert residual <= 1e-12 and len(net.rigid_weight_attachments) == 2
    evidence = [STUDY/name for name in ('assessment.json','tests-numeric-final.xml',
        'tests-transport-final.xml','terminal-receipts.json','build-json.log','browser/report.json')]
    evidence += [ROOT/'tests/test_steady_continuation.py', ROOT/'tests/test_structured_rank.py',
        ROOT/'scripts/test-steady-continuation-browser.mjs', Path(__file__)]
    result = dict(status='VERIFIED_PORTABLE_CONTINUATION_WITH_COARSE_EQUILIBRIUM',
        native_tests=tests,built_browser_checks=len(browser['checks']),modules=current,
        native_study_kernel=snapshots['ffwt4-continuation-20261106'],
        change_since_native_study='Only canonical JSON numeric hashing; physical algorithms unchanged.',
        current_kernel_full_load_residual=residual,native_values_added=0,
        driver_mesh_accuracy_established=False,pm2_gust_histories_computed=False,
        evidence=[pin(path) for path in evidence])
    target = STUDY/'verification.json'
    assert not target.exists(), 'Retain prior verification; do not overwrite it.'
    target.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    print(json.dumps({key:value for key,value in result.items()
                      if key not in ('modules','native_study_kernel','evidence')}))


if __name__ == '__main__':
    main()
