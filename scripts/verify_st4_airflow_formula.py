"""Bounded ST-4 diagnostic using Drela 1989 Eqs.37–38 as explicit nodes.

This is an ASWING 3.x source hypothesis, not an authenticated 5.x default.
The present mandatory-station insertion is retained; the old paper does not
specify its adjustment algorithm. No production mesh setting is added.
"""
import argparse
from copy import deepcopy
from datetime import datetime, timezone
import math
import os
from pathlib import Path
import resource
import signal
import sys
import time

import verify_st4_airflow_current as common

ROOT, read, sha, write = common.ROOT, common.read, common.sha, common.write


def prepare(out):
    parent_path = ROOT/'artifacts/isae/st4-airflow-current-20261109/forty-nodes/plan.json'
    parent = read(parent_path)
    for path, digest in parent['pins'].items():
        assert sha(ROOT/path) == digest, path
    n, lo, hi = 38, .0001, 1.2192
    u = [2*i/n-1 for i in range(n+1)]
    theta = [math.pi/2*(1-.5*v*(1+abs(v))) for v in u]
    nodes = [lo+(hi-lo)*.5*(1+math.cos(v)) for v in theta]
    nodes[0], nodes[-1] = lo, hi
    assert all(a < b for a,b in zip(nodes,nodes[1:]))
    # Independent equivalent expression and prescribed symmetric end limits.
    for v,t in zip(u,nodes):
        assert abs(t-(lo+(hi-lo)*.5*(1+math.sin(math.pi/4*v*(1+abs(v)))))) < 5e-16
    assert max(abs(a+b-lo-hi) for a,b in zip(nodes,reversed(nodes))) < 5e-16
    reference = ROOT/'reference/st4-node-placement-20261109'
    receipt = read(reference/'receipt.json')
    assert sha(reference/'drela-1989-wing-loads.pdf') == receipt['sha256']
    assert sha(reference/'drela-1989-wing-loads.txt') == receipt['text_sha256']
    pins = dict(parent['pins'])
    for p in [Path(__file__), ROOT/'scripts/assess_st4_airflow_current.py',
              ROOT/'reference/aswing_doc.txt', *reference.glob('*')]:
        if p.is_file(): pins[str(p.relative_to(ROOT))] = sha(p)
    out.mkdir(parents=True)
    write(out/'plan.json', dict(observed_utc=datetime.now(timezone.utc).isoformat(),
        parent_plan_sha256=sha(parent_path), model=parent['model'], pins=pins,
        request_template=parent['request_template'], limits=parent['limits'],
        jobs=[dict(speed=speed, panels=n, spacing='drela-1989-eq37', nodes=nodes,
                   expected_nodes=40) for speed in (120.5,139.5)],
        qualification=__doc__, primary_votes_added=0))
    print('Prepared two formula-based spacing probes with original physical inputs.')


def run(out,index):
    assert all(os.environ.get(k)=='1' for k in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'))
    resource.setrlimit(resource.RLIMIT_AS,(512*1024**2,)*2)
    resource.setrlimit(resource.RLIMIT_CPU,(15,)*2);signal.alarm(25)
    plan=read(out/'plan.json');job=plan['jobs'][index]
    for path,digest in plan['pins'].items():assert sha(ROOT/path)==digest,path
    folder=out/f'job-{index:02d}';folder.mkdir()
    request=deepcopy(plan['request_template'])
    request['condition']['speed']=job['speed']
    request['panels']=dict(default=job['panels'],beams={'1':dict(nodes=job['nodes'])})
    write(folder/'request.json',request)
    start,cpu=time.monotonic(),time.process_time();events=[]
    def event(stage):
        row=dict(stage=stage,wall_seconds=time.monotonic()-start,cpu_seconds=time.process_time()-cpu,
                 peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
        events.append(row);print(row,flush=True)
    import numpy as np
    from scipy.sparse import save_npz
    from openswing.bridge import dispatch
    from openswing import linear_dynamics as dynamics
    event('imports_done');original=dynamics.linearize;held=[]
    def capture(system,*args,**kwargs):
        event('assembly_start');a,m=original(system,*args,**kwargs);event('assembly_done')
        save_npz(folder/'A.npz',a);save_npz(folder/'M.npz',m)
        held.append(system);return a,m
    dynamics.linearize=capture
    try:result=dispatch(request)
    finally:dynamics.linearize=original
    event('dispatch_done');write(folder/'result.json',result)
    assert result['converged'] and result['base']['converged'] and len(held)==1
    assert len(result['modes'])==16 and result['base']['structural_nodes']==job['expected_nodes']
    zero=np.zeros(held[0].size);fresh=float(np.max(abs(held[0].residual(zero,zero))))
    assert fresh < 1e-8
    for path,digest in plan['pins'].items():assert sha(ROOT/path)==digest,path
    event('saved_for_independent_audit')
    write(folder/'report.json',dict(job=job,fresh_residual=fresh,events=events,
        roots=[m['eigenvalue'] for m in result['modes']],actual_nodes=result['base']['structural_nodes'],
        actual_elements=result['base']['structural_elements'],plan_sha256=sha(out/'plan.json'),
        artifacts={p.name:sha(p) for p in folder.iterdir()},primary_votes_added=0))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['prepare','run']);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--index',type=int,default=0);args=parser.parse_args()
    prepare(args.output) if args.action=='prepare' else run(args.output.resolve(),args.index)
