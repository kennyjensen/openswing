"""Bounded AE-2 recovery using exact sparse LU only after beam MemoryError.

The control deliberately exercises recovery and compares a complete saved cold
state. Candidate jobs catch real allocation failures; other solver rules stay
unchanged. This diagnostic does not add native-reference votes.
"""
from copy import deepcopy
from datetime import datetime,timezone
from pathlib import Path
import argparse
import os
import resource
import signal
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.probe_isae_ae2_cold_trace import read,write,pin,THREADS
LIMITS=dict(address_space_bytes=512*1024**2,cpu_seconds=15,wall_seconds=25)


def checked(out):
    plan=read(out/'plan.json')
    assert all(pin(p['path'])==p for p in plan['pins'])
    return plan


def prepare(out):
    assert not (out/'plan.json').exists()
    base=ROOT/'artifacts/isae'
    parent=base/'ae2-beta5-cold20-fine-20261111/attempts'
    previous=read(parent/'plan.json');audit=read(parent/'assessment.json')
    assert audit['status']=='COLD_ATTEMPT_DIAGNOSTIC_AUDIT_PASS'
    pins={p['path']:p for p in audit['source_pins']}
    for p in previous['pins']:assert pins.setdefault(p['path'],p)==p
    control_base=base/'ae2-beta5-cold19-fine-20261111'
    old_control_plan=read(control_base/'plan.json')
    for p in old_control_plan['pins']:assert pins.setdefault(p['path'],p)==p
    def remember(path):
        p=pin(path);assert pins.setdefault(p['path'],p)==p
    for p in [__file__,ROOT/'scripts/ae2_sparse_newton_candidate.py',ROOT/'tests/test_sparse_newton.py',
              parent/'plan.json',parent/'assessment.json',control_base/'plan.json',
              out/'sparse-unit.json',out/'sparse-unit.xml']:
        remember(p)
    assert read(out/'sparse-unit.json')['exit_code']==0
    candidate=deepcopy(next(c for c in previous['cases'] if c['name']=='cold20-m160'))
    candidate['boundary']=str(parent/'cases/cold20-m160/14/result.json')
    assert read(candidate['boundary'])['load_fraction']==.921630859375
    control_name='AE-2-m15_02-b05-ias019-m160'
    control=deepcopy(next(c for c in old_control_plan['cases'] if c['name']==control_name))
    control.update(name='control19-m160',boundary=str(control_base/'cases'/control_name/'04/result.json'),
        control_result=str(control_base/'cases'/control_name/'05/result.json'))
    for case in (control,candidate):
        remember(case['request']);remember(case['boundary'])
        if 'control_result' in case:remember(case['control_result'])
    for index in ('04','05'):
        for p in (control_base/'cases'/control_name/index).iterdir():
            if p.is_file():remember(p)
    assert all(pin(p['path'])==p for p in pins.values())
    write(out/'plan.json',dict(observed_utc=datetime.now(timezone.utc).isoformat(),
        cases=[control,candidate],pins=list(pins.values()),limits=LIMITS,
        parent_chain_audit=pin(parent/'assessment.json'),
        method=__doc__,primary_votes_added=0,production_route_changed=False,
        qualification='A separate diagnostic path; source equations and nonlinear gates are unchanged. Control injects one approximate-direction failure and beam allocation failure to exercise sparse recovery. Candidate catches real MemoryError only.'))


def worker(out,name,index):
    plan=checked(out);assert all(os.environ.get(k)=='1' for k in THREADS)
    from scripts.probe_isae_ae2_attempt_boundaries import worker as original_worker
    import openswing.newton_structure as beam
    import openswing.structured_static as static
    from scripts.ae2_sparse_newton_candidate import SparseNewtonFactor
    original=beam.NewtonBeamFactor;old_solve=static.block_solve
    events=[];forced=[False];folder=out/'cases'/name/f'{index:02d}'
    def recovery(network,matrix,**options):
        injected=name.startswith('control')
        try:
            if injected:raise MemoryError('deliberate control allocation failure')
            return original(network,matrix,**options)
        except MemoryError:
            event=dict(injected=injected,status='beam_allocation_failed')
            events.append(event)
            write(folder/'recovery-events.json',events)
        factor=SparseNewtonFactor(network,matrix,**options)
        event.update(status='sparse_factor_created',factor=factor.report)
        write(folder/'recovery-events.json',events)
        return factor
    def force_control(matrix,rhs,*args,**kwargs):
        if not forced[0]:
            forced[0]=True
            raise ValueError('deliberate control approximate-direction failure')
        return old_solve(matrix,rhs,*args,**kwargs)
    beam.NewtonBeamFactor=recovery
    if name.startswith('control'):static.block_solve=force_control
    try:original_worker(out,name,index)
    finally:
        beam.NewtonBeamFactor=original;static.block_solve=old_solve
        write(folder/'recovery-events.json',events)
    report=read(folder/'report.json')
    if name.startswith('control'):
        assert forced[0] and events and all(e['injected'] for e in events)
        assert report['status']=='computed' and report['fresh_residual']<=1e-12
        assert len(report['checks'])==20 and all(c['passed'] for c in report['checks'])
    else:assert all(not e['injected'] for e in events)
    report.update(sparse_recovery=events,diagnostic_solver_override=True,primary_votes_added=0)
    write(folder/'report.json',report)


def launch(out,name,index):
    plan=checked(out)
    if not name.startswith('control'):
        folder=out/'cases/control19-m160/00'
        report=read(folder/'report.json')
        assert report['status']=='computed' and report['fresh_residual']<=1e-12
        assert report['parity']['maximum_coordinate_difference']<=1e-11
        assert read(folder/'terminal.json')['returncode']==0
        assert read(folder/'sources-verified.json')['all_pins_checked_before_and_after']
    prior=[]
    if index:
        folder=out/'cases'/name/f'{index-1:02d}'
        assert read(folder/'terminal.json')['returncode']==0
        assert read(folder/'report.json')['status']=='pending'
        assert read(folder/'sources-verified.json')['all_pins_checked_before_and_after']
        prior=[pin(folder/f) for f in ('result.json','report.json','terminal.json','sources-verified.json')]
    folder=out/'cases'/name/f'{index:02d}';folder.mkdir(parents=True,exist_ok=False)
    write(folder/'started.json',dict(observed_utc=datetime.now(timezone.utc).isoformat(),
        plan=pin(out/'plan.json'),prior=prior,limits=LIMITS))
    def caps():
        resource.setrlimit(resource.RLIMIT_AS,(LIMITS['address_space_bytes'],)*2)
        resource.setrlimit(resource.RLIMIT_CPU,(LIMITS['cpu_seconds'],)*2)
    pid=0;timeout=False;start=time.monotonic()
    with (folder/'stdout.log').open('x') as stdout,(folder/'stderr.log').open('x') as stderr:
        child=subprocess.Popen([sys.executable,str(Path(__file__).resolve()),'worker',
            '--output',str(out),'--case',name,'--index',str(index)],cwd=ROOT,
            env={**os.environ,**THREADS},preexec_fn=caps,stdout=stdout,stderr=stderr,start_new_session=True)
        try:
            while not pid:
                pid,status,usage=os.wait4(child.pid,os.WNOHANG)
                if pid:break
                if time.monotonic()-start>LIMITS['wall_seconds']:
                    timeout=True;os.killpg(child.pid,signal.SIGKILL)
                    pid,status,usage=os.wait4(child.pid,0);break
                time.sleep(.05)
        finally:
            if not pid:
                os.killpg(child.pid,signal.SIGKILL);pid,status,usage=os.wait4(child.pid,0)
            child.returncode=os.waitstatus_to_exitcode(status)
    terminal=dict(returncode=child.returncode,process_reaped=True,supervisor_timeout=timeout,
        cpu_seconds=usage.ru_utime+usage.ru_stime,wall_seconds=time.monotonic()-start,
        peak_rss_kib=usage.ru_maxrss,limits=LIMITS,finished_utc=datetime.now(timezone.utc).isoformat())
    write(folder/'terminal.json',terminal);checked(out)
    assert all(pin(p['path'])==p for p in prior)
    write(folder/'sources-verified.json',dict(all_pins_checked_before_and_after=True,
        plan=pin(out/'plan.json'),terminal=pin(folder/'terminal.json'),prior=prior))
    report=read(folder/'report.json') if (folder/'report.json').exists() else {}
    print(dict(**terminal,status=report.get('status'),load_fraction=report.get('load_fraction'),
               sparse_recoveries=len(report.get('sparse_recovery',[]))),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['prepare','worker','launch'])
    parser.add_argument('--output',type=Path,required=True);parser.add_argument('--case')
    parser.add_argument('--index',type=int)
    args=parser.parse_args();out=args.output.resolve()
    if args.action=='prepare':prepare(out)
    else:globals()[args.action](out,args.case,args.index)
