#!/usr/bin/env python3
"""Freeze and run one native bridge baseline for the static browser replay.

Uses the literal archived ST5 model and the already declared 70-interval grid.
No experiment fitting, reference gate changes or additional mesh sweep.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
PRIOR = Path('/tmp/openswing-source-discrete-integration-20261026/st5')
POLICY = dict(beam_interpolation='drela-segspl-v1', structural_operator='drela-steady-zero-offset-v1')


def pin(path):
    path = Path(path).resolve()
    data = path.read_bytes()
    return dict(path=str(path), bytes=len(data), sha256=hashlib.sha256(data).hexdigest())


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False)+'\n')


def prepare(stage):
    stage.mkdir(parents=True, exist_ok=False)
    old = json.loads((PRIOR/'plan.json').read_text())
    mesh = old['meshes'][0]
    assert mesh['intervals_by_beam'] == {'1': 38, '2': 32}
    source = ROOT/old['source']
    assert pin(source)['sha256'] == old['source_sha256']
    request = dict(action='solve', mode='structural', source=source.read_text(),
                   panels=mesh['panels'], condition=None, gravity=None, numerics=POLICY)
    write(stage/'request.json', request)
    paths = [Path(__file__), ROOT/'scripts/test-source-static-browser.mjs',
             source, PRIOR/'plan.json', PRIOR/'level0/result.json',
             ROOT/'examples/isae-st5-reference-project.json', stage/'request.json']
    paths += sorted((ROOT/'openswing').glob('*.py')) + sorted((ROOT/'web').glob('*.js'))
    write(stage/'plan.json', dict(status='PREPARED', policy=POLICY, mesh=mesh,
        cold_solves=1, retries=0, pins=[pin(p) for p in paths],
        kernel_pins={p.name: pin(p)['sha256'] for p in sorted((ROOT/'openswing').glob('*.py'))},
        gates=dict(native_unchanged_absolute=2e-10, native_unchanged_relative=2e-10,
                   browser_absolute=2e-8, browser_relative=2e-8, residual=1e-8),
        reference_scope='Preserve prior archived-output gates and differences. This run checks browser integration, not a new reference pass.'))
    print(json.dumps(dict(prepared=pin(stage/'plan.json'))))


def run(stage):
    plan = json.loads((stage/'plan.json').read_text())
    assert not (stage/'execution.json').exists(), 'No automatic retry/overwrite'
    assert all(pin(p['path']) == p for p in plan['pins']), 'Frozen source changed'
    write(stage/'execution.json', dict(status='RUNNING', cold_solves=1))
    sys.path.insert(0, str(ROOT))
    import numpy as np
    from openswing.bridge import dispatch
    progress = []
    began = time.monotonic()
    try:
        result = dispatch(json.loads((stage/'request.json').read_text()),
                          progress=lambda *event: progress.append(list(event)))
        elapsed = time.monotonic()-began
        write(stage/'result.json', result)
        write(stage/'progress.json', progress)
        assert result['converged'] and result['residual'] <= plan['gates']['residual']
        assert result['numerics'] == POLICY
        assert result['structure']['strain_source'] == 'source_discrete_constitutive'
        assert len(result['elements']) == 70
        assert all(len(e['endpoint_traces']) == 2 for e in result['elements'])
        assert 'launch' not in result['equilibrium_state']
        old = json.loads((PRIOR/'level0/result.json').read_text())
        comparisons = {}
        for name in ('positions', 'rotations', 'internal_force', 'internal_moment', 'reactions'):
            a = np.array(result['equilibrium_state'][name])
            b = np.array(old['equilibrium_state'][name])
            assert a.shape == b.shape
            delta = np.abs(a-b)
            limit = plan['gates']['native_unchanged_absolute']+plan['gates']['native_unchanged_relative']*np.abs(b)
            assert np.all(delta <= limit), name
            comparisons[name] = dict(values=a.size, max_abs=float(np.max(delta, initial=0)))
        assert all(pin(p['path']) == p for p in plan['pins']), 'Frozen source changed'
        report = dict(status='PASS_NATIVE_BRIDGE_BASELINE', seconds=elapsed,
            residual=result['residual'], cold_solves=1, endpoint_traces=140,
            unchanged_physical_state=comparisons, result=pin(stage/'result.json'),
            reference_scope=plan['reference_scope'])
        write(stage/'report.json', report)
        write(stage/'execution.json', dict(status='TERMINAL', success=True, cold_solves=1, seconds=elapsed))
        print(json.dumps(report))
    except BaseException as exc:
        write(stage/'execution.json', dict(status='FAILURE_RETAINED', error=repr(exc), cold_solves=1, seconds=time.monotonic()-began))
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('prepare', 'run'))
    parser.add_argument('stage', type=Path)
    args = parser.parse_args()
    globals()[args.action](args.stage.resolve())
