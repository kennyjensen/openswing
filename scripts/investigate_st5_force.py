"""Source and printed-coordinate diagnostics for the retained ST-5 Fn miss.

Diagnostic perturbations never replace a native target or add accepted passes.
Each run is one cold, capped solve using the unchanged reviewed recovery code.
"""
import argparse
from copy import deepcopy
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import resource
import re
import signal
import statistics
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
CASE='st5-30lb_80_20'
SCOPE=ROOT/'docs/validation/isae-st5-mechanics-scope.json'
OLD=ROOT/'artifacts/isae/st5-family-current-20261109'/CASE
VERIFIER=ROOT/'artifacts/isae/st5-convergence-current-20261109'/CASE/'verifier.py'
THREADS={k:'1' for k in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS')}


def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,v):Path(p).write_text(json.dumps(v,indent=2,allow_nan=False)+'\n')
def stamp():return datetime.now(timezone.utc).isoformat()
def norm(v):return math.sqrt(sum(x*x for x in v))
def half(token):return float(Decimal(10)**Decimal(Decimal(token).as_tuple().exponent))/2
def coordinate(row):return row['printed_t'] if row['exact_anchor_t'] is None else row['exact_anchor_t']


def prepare(out):
    assert not out.exists(),'Preserve prior attempts.'
    original=read(OLD/'plan.json');target=read(original['target'])
    assert original['kernel_pins']=={str(p.relative_to(ROOT)):sha(p) for p in (ROOT/'openswing').glob('*.py')}
    out.mkdir(parents=True)
    pins={str(OLD/'plan.json'):sha(OLD/'plan.json'),str(VERIFIER):sha(VERIFIER),
          str(Path(__file__).resolve()):sha(__file__),str(SCOPE):sha(SCOPE)}
    pins.update({p['path']:p['sha256'] for p in target['source_pins']})
    pins[str(Path(original['target']))]=original['target_sha256']
    pins.update({str(ROOT/p):h for p,h in original['kernel_pins'].items()})
    jobs=[]
    for pattern in ('critical_node','positive_ordinary_nodes'):
        for sign in (-1,1):
            name=pattern+('_minus' if sign<0 else '_plus');folder=out/name;folder.mkdir()
            positions={};changed=[];nodes={}
            for beam in target['beams']:
                values=[]
                for row in beam['rows']:
                    t=coordinate(row)
                    selected=(row['beam']==1 and row['source_line']==67 if pattern=='critical_node' else
                              row['exact_anchor_t'] is None and row['printed_t']>0)
                    delta=sign*half(row['raw_tokens'][0])*beam['physical_multipliers'][0] if selected else 0.
                    positions[str(row['source_line'])]=t+delta;values.append(t+delta)
                    if selected:changed.append(dict(beam=row['beam'],source_line=row['source_line'],original=t,delta=delta))
                nodes[str(beam['beam'])]=sorted(set(values))
            mesh=deepcopy(original['meshes'][0])
            for beam,values in nodes.items():
                assert len(values)-1==mesh['intervals_by_beam'][beam]
                mesh['panels']['beams'][beam]['nodes']=values
            plan=deepcopy(original)
            plan.update(meshes=[mesh],retained_comparisons=[],script_sha256=sha(VERIFIER),
                diagnostic=dict(name=name,pattern=pattern,sign=sign,positions=positions,changed=changed,
                    driver_sha256=sha(__file__),primary_votes_added=0))
            save(folder/'plan.json',plan);pins[str(folder/'plan.json')]=sha(folder/'plan.json')
            jobs.append(dict(name=name,changed_rows=len(changed)))
    save(out/'study.json',dict(observed_utc=stamp(),case=CASE,jobs=jobs,pins=pins,
        limits=dict(address_space_bytes=512*1024**2,cpu_seconds=15,wall_seconds=25),
        hypotheses=['Check Fn token/exponent and its derivative MATLAB copy.',
                    'Compare mirrored source rows and cancellation in the normal projection.',
                    'Move the failing coordinate to each endpoint of its original printed interval.',
                    'Move all ordinary positive-side coordinates together to their printed endpoints, holding known anchors fixed.'],
        limitation='These two coordinate directions are diagnostics, not an exhaustive uncertainty bound or a recovered ASWING grid.',
        acceptance_changes=False,primary_votes_added=0,previous_goal_turn='progress: recurring ST5 runner completed and verified'))
    print(json.dumps(dict(prepared=jobs,primary_votes_added=0)),flush=True)


def check_pins(out):
    for p,h in read(out/'study.json')['pins'].items():assert sha(p)==h,p


def archive(out):
    import numpy as np
    from scipy.io import loadmat
    check_pins(out);cases=[];pinned={}
    scope=read(SCOPE)
    for entry in scope['cases']:
        path=ROOT/entry['reference_plan'];assert sha(path)==entry['reference_plan_sha256']
        plan=read(path);target=read(plan['target']);packet_path=path.parent/'run-0/level0/comparison.json'
        packet=read(packet_path);pinned[str(packet_path)]=sha(packet_path)
        assert packet['numerical_gates_pass'] and plan['kernel_pins']==read(OLD/'plan.json')['kernel_pins']
        assert sha(plan['target'])==plan['target_sha256']
        source=next(Path(p['path']) for p in target['source_pins'] if p['path'].endswith('.txt'))
        for pin in target['source_pins']:assert sha(pin['path'])==pin['sha256']
        lines=source.read_text().splitlines();pairs=[];vectors=[]
        for beam in target['beams']:
            header=next(i for i,line in enumerate(lines) if (m:=re.match(r'\s*Surface\s+Beam\s+(\d+):',line)) and int(m.group(1))==beam['beam'])
            exponents=[0,*map(int,lines[header+1].split())]
            assert lines[header+2].split()[10:13]==['Fc/10','Fs/10','Fn/10']
            assert exponents==beam['header_exponents']
            current=[r for r in packet['rows'] if r['beam']==beam['beam']]
            assert len(current)==len(beam['rows'])
            for ref,row in zip(beam['rows'],current,strict=True):
                assert lines[ref['source_line']-1].split()==ref['raw_tokens']
                force=[float(ref['raw_tokens'][j])*10.**exponents[j] for j in (10,11,12)]
                assert force==row['expected'][10:13]
                error=norm([a-b for a,b in zip(row['values'][10:13],force)])
                if norm(force):vectors.append(dict(beam=beam['beam'],line=ref['source_line'],error_lb=error,
                    native_norm_lb=norm(force),relative_percent=100*error/norm(force)))
            n=len(current)
            for i in range(n//2):
                left,right=current[i],current[n-1-i]
                # Mirror ordering preserves the appropriate duplicate-junction trace.
                assert abs(left['t_printed']+right['t_printed'])<=2.000001e-6
                native=[right['expected'][j]-parity*left['expected'][j] for j,parity in ((10,-1),(11,1),(12,-1))]
                actual=[right['values'][j]-parity*left['values'][j] for j,parity in ((10,-1),(11,1),(12,-1))]
                allowance=right['half_last_place'][12]+left['half_last_place'][12]
                pairs.append(dict(beam=beam['beam'],lines=[left['source_line'],right['source_line']],
                    printed_t=[left['t_printed'],right['t_printed']],native_force_symmetry_error_lb=native,
                    current_force_symmetry_error_lb=actual,native_Fn_rounding_sum_lb=allowance,
                    native_Fn_asymmetry_exceeds_printed_precision=abs(native[-1])>allowance+1e-14))
        cases.append(dict(case=entry['case'],vector_errors=vectors,symmetric_pairs=pairs,
            median_vector_error_percent=statistics.median(v['relative_percent'] for v in vectors),
            maximum_vector_error_percent=max(v['relative_percent'] for v in vectors)))
    target_plan=read(OLD/'plan.json');target=read(target_plan['target']);packet=read(OLD/'run-0/level0/comparison.json')
    row=next(r for r in packet['rows'] if r['source_line']==67)
    terms=[row['frame'][i][2]*row['force_body'][i] for i in range(3)]
    assert math.isclose(sum(terms),row['values'][12],abs_tol=1e-14)
    matpath=next(Path(p['path']) for p in target['source_pins'] if p['path'].endswith('.mat'))
    data=loadmat(matpath,simplify_cells=True)['beam_data'];mat_checks=0
    for beam,matrix in zip(target['beams'],data,strict=True):
        assert matrix.shape==(len(beam['rows']),28)
        for ref,values in zip(beam['rows'],matrix,strict=True):
            for j in (10,11,12):
                assert values[j]==ref['physical'][j];mat_checks+=1
    ref=next(r for b in target['beams'] for r in b['rows'] if r['source_line']==67)
    specific=dict(source_line=67,raw_Fn_token=ref['raw_tokens'][12],header_exponent=target['beams'][0]['header_exponents'][12],native_Fn_lb=row['expected'][12],
        current_Fn_lb=row['values'][12],local_force_vector_native=row['expected'][10:13],
        local_force_vector_current=row['values'][10:13],normal_projection_terms_lb=terms,
        cancellation_ratio=sum(map(abs,terms))/abs(sum(terms)),
        vector_error_percent=100*norm([a-b for a,b in zip(row['values'][10:13],row['expected'][10:13])])/norm(row['expected'][10:13]),
        relative_Fn_error_percent=100*abs(row['values'][12]-row['expected'][12])/abs(row['expected'][12]),
        fresh_residual=packet['checks']['fresh_residual'],mat_force_tokens_checked=mat_checks,
        mat_is_independent_run=False)
    result=dict(observed_utc=stamp(),specific=specific,cases=cases,comparison_pins=pinned,
        primary_votes_added=0,acceptance_changes=False)
    assert not (out/'archive-audit.json').exists();save(out/'archive-audit.json',result)
    print(json.dumps(specific),flush=True)


def worker(out,name):
    assert all(os.environ.get(k)=='1' for k in THREADS)
    limits=read(out/'study.json')['limits']
    resource.setrlimit(resource.RLIMIT_AS,(limits['address_space_bytes'],)*2)
    resource.setrlimit(resource.RLIMIT_CPU,(limits['cpu_seconds'],)*2);signal.alarm(limits['wall_seconds'])
    plan=read(out/name/'plan.json');assert plan['diagnostic']['driver_sha256']==sha(__file__)
    spec=importlib.util.spec_from_file_location('st5_coordinate_recovery',VERIFIER)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    module.coordinate=lambda row:plan['diagnostic']['positions'][str(row['source_line'])]
    started=time.monotonic();cpu=time.process_time();module.run(out/name)
    save(out/name/'timing.json',dict(wall_seconds=time.monotonic()-started,cpu_seconds=time.process_time()-cpu,
        peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss))


def run(out,name):
    check_pins(out);folder=out/name;assert not (folder/'execution.json').exists()
    command=[sys.executable,str(Path(__file__).resolve()),'worker','--output',str(out),'--case',name]
    with (folder/'run.log').open('x') as log:
        try:child=subprocess.run(command,cwd=ROOT,env=dict(os.environ,**THREADS),stdout=log,stderr=subprocess.STDOUT,timeout=30)
        except subprocess.TimeoutExpired:
            save(folder/'execution.json',dict(returncode=None,terminal=True,timeout=True));raise
    save(folder/'execution.json',dict(returncode=child.returncode,terminal=True,timeout=False))
    assert child.returncode==0,'Failed attempt retained; do not retry.'
    check_pins(out);packet=read(folder/'level0/comparison.json')
    row=next(r for r in packet['rows'] if r['source_line']==67)
    print(json.dumps(dict(case=name,Fn=row['values'][12],t=row['t_evaluated'],checks=packet['checks'])),flush=True)


def summarize(out):
    check_pins(out);archive_data=read(out/'archive-audit.json');baseline=archive_data['specific']['current_Fn_lb'];rows=[]
    for job in read(out/'study.json')['jobs']:
        folder=out/job['name'];receipt=read(folder/'execution.json')
        assert receipt==dict(returncode=0,terminal=True,timeout=False)
        plan=read(folder/'plan.json');packet=read(folder/'level0/comparison.json')
        assert packet['numerical_gates_pass']
        for row in packet['rows']:assert row['t_evaluated']==plan['diagnostic']['positions'][str(row['source_line'])]
        row=next(r for r in packet['rows'] if r['source_line']==67)
        rows.append(dict(case=job['name'],changed_rows=job['changed_rows'],Fn_lb=row['values'][12],
            change_from_nominal_lb=row['values'][12]-baseline,
            native_error_percent=100*abs(row['values'][12]-row['expected'][12])/abs(row['expected'][12]),
            physical_checks=packet['checks'],timing=read(folder/'timing.json')))
    result=dict(observed_utc=stamp(),baseline=archive_data['specific'],diagnostics=rows,
        native_absolute_error_lb=abs(baseline-archive_data['specific']['native_Fn_lb']),
        maximum_tested_coordinate_effect_lb=max(abs(r['change_from_nominal_lb']) for r in rows),
        exhaustive_coordinate_bound=False,primary_votes_added=0,production_changes=False,
        qualification='No archived iteration history, unrounded original nodes or native executable; no native error or stopping-rule claim established.')
    assert not (out/'summary.json').exists();save(out/'summary.json',result);print(json.dumps(result),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=['prepare','archive','run','worker','summarize'])
    p.add_argument('--output',required=True,type=Path);p.add_argument('--case');a=p.parse_args();out=a.output.resolve()
    if a.action in ('run','worker'):
        assert a.case in [j['name'] for j in read(out/'study.json')['jobs']]
        (run if a.action=='run' else worker)(out,a.case)
    else:
        if a.action=='archive':
            resource.setrlimit(resource.RLIMIT_AS,(512*1024**2,)*2)
            resource.setrlimit(resource.RLIMIT_CPU,(15,)*2);signal.alarm(25)
        {'prepare':prepare,'archive':archive,'summarize':summarize}[a.action](out)
