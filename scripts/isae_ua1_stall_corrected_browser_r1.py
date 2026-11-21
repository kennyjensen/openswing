"""Prepare and audit the corrected full UA-1 stalled browser study.

Uses the established serial raw-history audit with fresh CPython targets and
expanded motion/load fields. No old production checkpoint seeds these runs.
"""
import argparse
import gzip
import json
from pathlib import Path
import shutil

import isae_ua1_stall_browser as engine
from isae_ua1_stall_expanded import physical_row, comparison_fields, RIGID_LIMIT

ROOT = engine.ROOT
PYTHON = ROOT/'artifacts/isae/ua1-stall-corrected-20261103'
BASE = ROOT/'artifacts/isae/ua1-stall-corrected-browser-20261103'
SCRIPT = Path(__file__).resolve()
engine.BASE = BASE
engine.OLD = engine.FINE = PYTHON
engine.SCRIPT = SCRIPT
engine.physical_row = physical_row
read, write, digest, pins, verify = engine.read, engine.write, engine.digest, engine.pins, engine.verify


def prepare():
    assert not BASE.exists()
    plan = read(PYTHON/'plan.json')
    verify(plan['source_sha256']); verify(plan['input_sha256'])
    result = read(PYTHON/'audit.json')
    assert result['passed'] and result['audited_unique_states'] == 3842
    assert plan['segment_steps'] == 20 and plan['grids'] == [320,640]
    assert plan['independent_rigid_local_motion_limit'] == RIGID_LIMIT
    manifest = read(ROOT/'dist/kernel/manifest.json')
    assert len(manifest) == 136
    for name in manifest:
        assert digest(ROOT/'dist/kernel'/name) == plan['source_sha256']['openswing/'+name]
    workers = list((ROOT/'dist/assets').glob('worker-*.js'))
    assert len(workers) == 1
    paths = [SCRIPT, workers[0], ROOT/'dist/kernel/manifest.json',
        *[ROOT/'dist/kernel'/name for name in manifest],
        *sorted(p for p in (ROOT/'dist/runtime').rglob('*') if p.is_file())]
    inputs = [PYTHON/name for name in ('plan.json','audit.json','request-n640.json',
        'reference-DOP853.json','reference-Radau.json','reference-check.json')]
    with gzip.open(PYTHON/'n640-part000/trajectory.json.gz', 'rt') as stream:
        sample = json.load(stream)['snapshots'][0]
    fields = comparison_fields(physical_row(sample, plan['section']))
    request = read(PYTHON/'request-n640.json')
    period = request['time']['duration']/4
    setup = dict(section=plan['section'], cycles=4, nominal_steps_per_cycle=640, period=period,
        times=[period*i/640 for i in range(2561)], full_request=request,
        gates={**plan['gates'], 'CPython_scaled_difference':2e-8},
        independent_rigid_local_motion_limit=RIGID_LIMIT, comparison_fields=fields,
        force_scale=plan['force_scale'], moment_scale=plan['moment_scale'], other_scale=plan['other_scale'],
        jobs=[dict(part=p,start_index=p*8,end_index=(p+1)*8) for p in range(320)],
        max_steps_per_job=8, worker_request_timeout_seconds=45, panels=4,
        audit_jobs_per_chunk=8, target_chunks=32, target_original_jobs_per_chunk=4,
        source_sha256={**plan['source_sha256'], **pins(paths)}, input_sha256=pins(inputs),
        worker_url='/assets/'+workers[0].name, serial=True, threads=1,
        initial_state='Own cold browser equilibrium, complete four-cycle forcing before startup.',
        scope='Current-source complete UA-1 repeated stall with expanded local motion and structural load checks.',
        normalization=plan['normalization'], production_changed=False,
        native_ASWING_comparison=False, full_history_UI_validation=False,
        new_browser_temporal_refinement_claim=False,
        refinement_note='Compare browser fine errors to current CPython coarse errors; not a two-grid browser refinement study.')
    BASE.mkdir(); (BASE/'targets').mkdir()
    for name in setup['source_sha256']:
        if name.startswith('dist/runtime/'):
            continue
        target = BASE/'frozen-code'/name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT/name, target)
    shutil.copyfile(ROOT/'docs/validation/ISAE_STATUS.md', BASE/'status-before.md')
    write(BASE/'setup.json', setup)
    print(json.dumps(dict(prepared=True, browser_jobs=320, fields=len(fields))), flush=True)



def target(index, setup):
    """Retain canonical accepted samples and audit each raw restart boundary.

    Dimensional internal loads undergo the existing scale conversion on resume.
    Their boundary audit permits only the established four-ULP roundoff; the
    expanded cross-runtime comparison still retains its original 2e-8 limit.
    """
    from isae_ua1_periodic_boundary import check_boundary
    assert 0 <= index < 32
    rows = []; inputs = {}; boundaries = []; rounding = []
    for part in range(index*4, index*4+4):
        folder = PYTHON/f'n640-part{part:03d}'
        receipt_path = PYTHON/(folder.name+'-execution.json')
        receipt = read(receipt_path)
        assert receipt['exit_code'] == 0
        verify(receipt['output_sha256'])
        inputs.update(receipt['output_sha256']); inputs.update(pins([receipt_path]))
        with gzip.open(folder/'trajectory.json.gz', 'rt') as stream:
            raw = json.load(stream)
        assert raw['converged'] and raw['accepted_steps'] == 20 and raw['rejected_steps'] == 0
        assert len(raw['snapshots']) == 21
        if part:
            prior = PYTHON/f'n640-part{part-1:03d}/checkpoint.json'
            rounding.extend(check_boundary(read(prior), raw['snapshots']))
            inputs.update(pins([prior])); boundaries.append(part)
        reduced = read(folder/'audit.json')['rows']
        current = [physical_row(s, setup['section']) for s in raw['snapshots']]
        del raw
        for local, row in enumerate(current):
            assert abs(row['time']-setup['times'][part*20+local]) < 1e-12
            if part and local == 0:
                continue
            expected = reduced[local if part == 0 else local-1]
            for key in expected:
                assert engine.difference(row[key], expected[key]) < 1e-12, key
        if rows:
            # Core displayed aerodynamic/frame fields have no structural scale conversion.
            for field in ('CL','force_coefficient','CDp_fixed','circulation','circulation_rate',
                          'section_cl','velocity','position','acceleration'):
                assert engine.difference(rows[-1][field], current[0][field]) == 0, field
        rows.extend(current if not rows else current[1:])
    assert len(rows) == 81
    targets = []
    for offset in range(10):
        part = index*10+offset
        path = BASE/'targets'/f'part{part:03d}.json'
        write(path, dict(job=setup['jobs'][part], rows=rows[offset*8:offset*8+9]))
        targets.append(dict(path=str(path.relative_to(BASE)), sha256=digest(path)))
    write(BASE/f'target-chunk{index:03d}.json', dict(targets=targets, input_sha256=inputs,
        audited_boundaries=boundaries, restart_rounding=rounding,
        setup_sha256=digest(BASE/'setup.json')))
    print(json.dumps(dict(target_chunk=index, target_jobs=10, physical_states=81,
                         audited_boundaries=len(boundaries))), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['prepare','target','freeze','audit','combine','run-targets','run-audits'])
    parser.add_argument('--index', type=int)
    parser.add_argument('--max-jobs', type=int)
    args = parser.parse_args()
    if args.action == 'prepare':
        prepare(); return
    plan = read(BASE/('plan.json' if args.action in ('audit','combine') else 'setup.json'))
    verify({k:v for k,v in plan['source_sha256'].items() if not k.startswith('dist/runtime/')})
    engine.FIELDS = tuple(plan['comparison_fields'])
    if args.action.startswith('run-'):
        engine.run(args.action[4:], args.max_jobs)
    elif args.action == 'target':
        target(args.index, plan)
    elif args.action == 'freeze':
        engine.freeze(plan)
    elif args.action == 'audit':
        engine.audit(args.index, plan)
    else:
        engine.combine(plan)


if __name__ == '__main__':
    main()
