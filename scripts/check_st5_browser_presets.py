"""Bounded saved-evidence check of ST-5 browser data, without JS or solves."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import resource
import signal
import sys

from prepare_st5_browser_presets import ROOT, PREFIX, SUFFIX, expected, sha


def check(output):
    files = expected()
    for path, content in files.items():
        assert path.read_bytes() == content, str(path)
    module = (ROOT / 'web/st5-baselines.js').read_text()
    records = json.loads(module.removeprefix(PREFIX).removesuffix(SUFFIX))
    provenance = json.loads((ROOT / 'docs/validation/isae-st5-browser-presets-sources.json').read_text())
    kernel = {str(p.relative_to(ROOT)): sha(p) for p in (ROOT / 'openswing').glob('*.py')}
    sys.path.insert(0, str(ROOT))
    from openswing.asw import parse_asw
    policy = {'beam_interpolation': 'drela-segspl-v1', 'structural_operator': 'drela-steady-section-v1'}
    cases = []
    for entry in provenance['cases']:
        preset = records[entry['key']]
        plan_path = ROOT / entry['reference_plan']
        plan = json.loads(plan_path.read_text())
        assert plan['kernel_pins'] == kernel
        source = (ROOT / 'public/examples' / (entry['key'] + '.asw')).read_text()
        model = parse_asw(source, beam_interpolation=policy['beam_interpolation'])
        assert model.dumps() == source
        assert preset['mesh'] == plan['meshes'][0]['panels']
        assert {b.index for b in model.beams} == {int(k) for k in preset['mesh']['beams']}
        for beam in model.beams:
            nodes = preset['mesh']['beams'][str(beam.index)]['nodes']
            assert all(a < b for a, b in zip(nodes, nodes[1:]))
            assert (nodes[0], nodes[-1]) == beam.domain
        raw_joints = [row.tolist() for row in model.records.get('joint', [])]
        if 'roller' in entry['case']:
            assert len(raw_joints) == 2 and all(len(r) >= 5 and r[4] == 2 for r in raw_joints)
        result_path = plan_path.parent / 'run-0/level0/result.json'
        result = json.loads(result_path.read_text())
        assert result['numerics'] == policy
        assert result['strut_mode'] == 'bilateral' and result['converged'] and result['residual'] < 1e-8
        comparison = json.loads((result_path.parent / 'comparison.json').read_text())
        assert comparison['numerical_gates_pass']
        cases.append(dict(case=entry['case'], example=entry['key'],
            source_sha256=entry['source_sha256'], intervals=plan['meshes'][0]['intervals_by_beam'],
            literal_joint_rows=raw_joints, native_comparison_rows=len(comparison['rows']),
            authenticated_saved_result=str(result_path.relative_to(ROOT)), result_sha256=sha(result_path)))
    result = dict(observed_utc=datetime.now(timezone.utc).isoformat(), status='PASS_DATA_AND_SAVED_EVIDENCE',
        cases=cases, generated_files_checked=len(files), kernel_modules_unchanged=len(kernel),
        solver_calls=0, browser_node_build_jobs=0, primary_passes_added=0,
        browser_behavior_verified=False, javascript_behavior_tests='written, not executed: existing Node test hold',
        file_hashes={str(p.relative_to(ROOT)): sha(p) for p in files})
    if output:
        with output.open('x') as stream:
            json.dump(result, stream, indent=2); stream.write('\n')
    print(json.dumps({k: v for k, v in result.items() if k not in ('cases', 'file_hashes')}))


if __name__ == '__main__':
    resource.setrlimit(resource.RLIMIT_AS, (512*1024**2,)*2)
    resource.setrlimit(resource.RLIMIT_CPU, (15,)*2)
    signal.alarm(25)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path)
    check(parser.parse_args().output)
