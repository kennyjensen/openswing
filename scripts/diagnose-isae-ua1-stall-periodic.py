"""Bounded settling and profiling diagnostics; no new validation pass counts."""
import argparse
import cProfile
import gzip
from hashlib import sha256
import json
from pathlib import Path
import pstats
import sys
import time

import numpy as np
from isae_ua_stall_reference import Section, trajectory
from isae_ua_artifacts import write_trajectory

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT/'artifacts/isae/ua1-stall-periodic-preparation-20261102'
PRIOR = ROOT/'artifacts/isae/ua1-stall-20261102-r1'
sys.path.insert(0, str(ROOT))


def read(path):
    return json.loads(path.read_text())


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['reference', 'profile'])
    parser.add_argument('--method', choices=['DOP853','Radau'], default='DOP853')
    args = parser.parse_args()
    section = Section()
    job = args.action+('-'+args.method if args.action == 'reference' else '')
    folder = BASE/job
    folder.mkdir(parents=True)
    pins = {name:value for name,value in read(PRIOR/'plan.json')['source_sha256'].items()}
    pins[str(Path(__file__).relative_to(ROOT))] = digest(Path(__file__))
    assert all(digest(ROOT/name) == value for name,value in pins.items())
    (folder/'plan.json').write_text(json.dumps(dict(source_sha256=pins, section=vars(section),
        scope='Preparation only; no new physical validation pass counts', serial=True, threads=1,
        maximum_subprocess_seconds=45),indent=2)+'\n')
    started = time.monotonic()
    if args.action == 'reference':
        result = trajectory(section, [section.period*i/128 for i in range(8*128+1)], args.method)
        rows = result['rows']
        cycles = []
        for cycle in range(1,9):
            selected = rows[(cycle-1)*128:cycle*128+1]
            changes = {}
            if cycle > 1:
                prior = rows[(cycle-2)*128:(cycle-1)*128+1]
                for key in ('CL','circulation','circulation_rate','CDp_fixed'):
                    values = np.array([r[key] for r in selected])
                    scale = np.max(abs(values-(np.mean(values[:-1]) if key in ('CL','circulation') else 0.)))
                    changes[key] = float(np.max(abs(values-[r[key] for r in prior]))/scale)
            cycles.append(dict(cycle=cycle, change_fractions=changes,
                section_cl_range=[min(r['section_cl'] for r in selected),max(r['section_cl'] for r in selected)],
                peak_pressure_drag=max(r['CDp_fixed'] for r in selected)))
        (folder/'trajectory.json').write_text(json.dumps(result,separators=(',',':'),allow_nan=False)+'\n')
        report = dict(cycles=cycles, seconds=time.monotonic()-started, evaluations=result['ode_evaluations'])
    else:
        from openswing.bridge import dispatch
        parent = PRIOR/'n160-part000/checkpoint.json'
        target = PRIOR/'n160-part001/trajectory.json.gz'
        saved = read(parent)
        full = read(PRIOR/'request-n160.json')
        request = {key:value for key,value in full.items() if key not in ('condition','time')}
        request.update(action='resume_time', checkpoint=saved,
            time=dict(duration=section.period*46/160-saved['state']['time'], max_steps=24))
        (folder/'request.json').write_text(json.dumps(request,separators=(',',':'))+'\n')
        inputs = {str(path.relative_to(ROOT)):digest(path) for path in (parent,target,PRIOR/'request-n160.json')}
        profiler = cProfile.Profile()
        before = time.monotonic()
        raw = profiler.runcall(dispatch, request)
        seconds = time.monotonic()-before
        profiler.dump_stats(str(folder/'dispatch.pstats'))
        write_trajectory(folder/'trajectory.json.gz', raw)
        assert raw['converged'] and raw['accepted_steps'] == 6 and raw['rejected_steps'] == 0
        with gzip.open(target,'rt') as stream:
            expected = json.load(stream)['snapshots'][:7]
        differences = {}
        for key in ('force','circulation_rate','CL','CDp','time'):
            actual, reference = [np.array([row[key] for row in group]) for group in (raw['snapshots'],expected)]
            differences[key] = float(np.max(abs(actual-reference)/np.maximum(1,abs(reference))))
        assert max(differences.values()) < 1e-10
        functions = []
        for (filename,line,name),(primitive,calls,own,cumulative,callers) in pstats.Stats(profiler).stats.items():
            functions.append(dict(file=filename,line=line,name=name,calls=calls,own_seconds=own,cumulative_seconds=cumulative))
        functions.sort(key=lambda r:r['cumulative_seconds'],reverse=True)
        report = dict(profiled_seconds=seconds, differences= differences, functions=functions,
            input_sha256=inputs, scope='Instrumented dispatch of six retained-history steps; not an uninstrumented performance claim.')
    assert all(digest(ROOT/name) == value for name,value in pins.items())
    report.update(source_unchanged=True, production_changed=False, registered_pass_count_change=0)
    (folder/'report.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    print(json.dumps({**report,'functions':report.get('functions',[])[:20]}),flush=True)


if __name__ == '__main__':
    main()
