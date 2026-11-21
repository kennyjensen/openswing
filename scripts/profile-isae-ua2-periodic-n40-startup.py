"""Profile four real N40 continuation steps; do not add validation pass counts."""
import cProfile
import gc
import gzip
from hashlib import sha256
import json
from pathlib import Path
import pstats
import resource
import sys
import time
from isae_ua2_incidence_periodic_n40 import ROOT,BASE,grid,full_request


def digest(p):return sha256(p.read_bytes()).hexdigest()


def main():
    folder=BASE/'profile-startup';assert not folder.exists()
    parent=BASE/'production/part000';receipt_path=BASE/'production/part000-execution.json'
    receipt=json.loads(receipt_path.read_text());assert receipt['exit_code']==0 and digest(parent/'report.json')==receipt['report_sha256']
    plan=json.loads((BASE/'production-plan.json').read_text())
    pins={**plan['source_sha256'],str(Path(__file__).resolve().relative_to(ROOT)):digest(Path(__file__).resolve())}
    inputs={str(p.relative_to(ROOT)):digest(p) for p in (parent/'trajectory.json.gz',parent/'report.json',receipt_path,BASE/'production-plan.json')}
    assert all(digest(ROOT/n)==h for n,h in {**pins,**inputs}.items())
    sys.path.insert(0,str(ROOT))
    from openswing.time_state import checkpoint
    with gzip.open(parent/'trajectory.json.gz','rt') as stream:old=json.load(stream)
    saved=checkpoint(old);del old;gc.collect()
    assert saved['older'] is not None and saved['state']['time']==grid()[16]
    full=full_request();request={k:v for k,v in full.items() if k not in ('condition','time')}
    request.update(action='resume_time',checkpoint=saved,time=dict(duration=grid()[20]-saved['state']['time'],max_steps=16))
    folder.mkdir()
    started=time.monotonic()
    from openswing.bridge import dispatch
    import_seconds=time.monotonic()-started
    profiler=cProfile.Profile();started=time.monotonic();profiler.enable()
    raw=dispatch(request)
    profiler.disable();seconds=time.monotonic()-started
    assert raw['converged'] and raw['accepted_steps']==4 and raw['rejected_steps']==0
    assert raw['snapshots'][-1]['time']==grid()[20]
    assert max(s['residual'] for s in raw['snapshots'])<1e-10
    profiler.dump_stats(str(folder/'dispatch.pstats'))
    from isae_ua_artifacts import write_trajectory
    write_trajectory(folder/'trajectory.json.gz',raw)
    functions=[]
    for (filename,line,name),(primitive,calls,own,cumulative,callers) in pstats.Stats(profiler).stats.items():
        functions.append(dict(file=filename,line=line,name=name,primitive_calls=primitive,calls=calls,own_seconds=own,cumulative_seconds=cumulative))
    functions.sort(key=lambda r:r['cumulative_seconds'],reverse=True)
    assert all(digest(ROOT/n)==h for n,h in {**pins,**inputs}.items())
    report=dict(passed=True,scope='Instrumented setup and four continuation steps only; profiler timings are not uninstrumented performance claims.',
        bridge_import_seconds=import_seconds,profiled_dispatch_seconds=seconds,accepted_steps=4,rejected_steps=0,
        peak_rss_mib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,source_sha256=pins,input_sha256=inputs,
        functions=functions,production_changed=False,registered_pass_count_change=0,native_ASWING_comparison=False)
    (folder/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(passed=True,bridge_import_seconds=import_seconds,profiled_dispatch_seconds=seconds,peak_rss_mib=report['peak_rss_mib'],top_functions=functions[:12])))


if __name__=='__main__':main()
