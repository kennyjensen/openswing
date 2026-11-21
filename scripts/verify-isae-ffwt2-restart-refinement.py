"""Refine only the second-command window from the identical saved 2 s state.

Both grids restart with one BDF1 step and then use BDF2. This controls the
command boundary; it does not refine the first two seconds or recover native
startup. All physical inputs, kernel hashes and residual gates remain fixed.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def pin(path):
    path = Path(path).resolve(); raw = path.read_bytes()
    return dict(path=str(path), bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())


def write(path, data):
    Path(path).write_text(json.dumps(data, indent=2, allow_nan=False)+'\n')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--parent', required=True, type=Path)
    p.add_argument('--dt', type=float, choices=(.005, .0025), required=True)
    p.add_argument('--output-dir', required=True, type=Path)
    a = p.parse_args(); folder = a.output_dir.resolve()
    folder.mkdir(parents=True, exist_ok=False)
    parent = a.parent.resolve(); plan = json.loads((parent/'plan.json').read_text())
    report = json.loads((parent/'report.json').read_text())
    assert report['status'] == 'SEGMENT_COMPUTED'
    saved = json.loads((parent/'checkpoint.json').read_text())
    assert pin(parent/'checkpoint.json') == report['checkpoint']
    assert abs(saved['state']['time']-2.) < 1e-12
    assert saved['context']['method']['maximum_step'] == .01
    assert plan['continuation_version'] == 2 and plan['startup'] == 'jig-zero-motion-zero-circulation'
    assert 'command_restarts' not in plan
    pins = plan['source_pins']+plan['kernel_pins']+[pin(__file__)]
    for item in pins:assert pin(item['path']) == item
    write(folder/'plan.json', dict(scope='Second-command temporal refinement only',
        source_pins=plan['source_pins'], kernel_pins=plan['kernel_pins'], helper=pin(__file__),
        parent_checkpoint=pin(parent/'checkpoint.json'), dt=a.dt, start=2., end=2.04,
        numerical_tolerance=1e-8, initial_history_refined=False,
        accuracy_gate=dict(relative=.001, normalization='maximum fine-grid magnitude per output over common 2.00--2.04 s rows'),
        full_family_validated=False))
    from openswing.bridge import dispatch
    from openswing.time_state import checkpoint
    source = Path(plan['source_pins'][0]['path']).read_text()
    began = time.monotonic(); records = []
    with (folder/'progress.jsonl').open('w') as log:
        def progress(*event):
            log.write(json.dumps(dict(seconds=time.monotonic()-began, event=event))+'\n'); log.flush()
        for label, order, duration in [('first', 1, a.dt), ('continued', 2, .04-a.dt)]:
            request = dict(action='resume_time', source=source,
                numerics=dict(beam_interpolation='drela-segspl-v1', structural_operator='drela-moving-airflow-v1'),
                checkpoint=saved, time=dict(duration=duration, dt=a.dt, order=order))
            write(folder/(label+'-request.json'), request)
            result = dispatch(request, progress=progress)
            assert result['converged'] and result['rejected_steps'] == 0
            assert result['checkpoint_validation']['discrete_replayed']
            assert all(s['converged'] and s['residual'] <= 1e-8 for s in result['snapshots'])
            assert all(s['restart']['accepted_method']['effective_order'] == order for s in result['snapshots'][1:])
            write(folder/(label+'-result.json'), result)
            saved = checkpoint(result, -1); write(folder/(label+'-checkpoint.json'), saved)
            records.append(dict(result=pin(folder/(label+'-result.json')), checkpoint=pin(folder/(label+'-checkpoint.json')),
                accepted_steps=result['accepted_steps'], rejected_steps=result['rejected_steps']))
    assert abs(saved['state']['time']-2.04) < 1e-12
    assert sum(r['accepted_steps'] for r in records) == round(.04/a.dt)
    for item in pins:assert pin(item['path']) == item
    report = dict(status='LOCAL_REFINEMENT_COMPUTED', dt=a.dt, seconds=time.monotonic()-began,
        records=records, complete_preceding_history_refined=False, native_passes_added=0, full_family_validated=False)
    write(folder/'report.json', report); print(json.dumps(report))


if __name__ == '__main__':main()
