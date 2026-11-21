"""Trace AE-2's verified beta1 positive branch toward beta5 at IAS17.

Diagnostic only: no original cold comparison is replaced and no native vote is
added. Each unchanged production warm solve and each independent physical
recheck runs separately with one BLAS thread and bounded resources.
"""
import argparse
from copy import deepcopy
from datetime import datetime, timezone
import json
import os
from pathlib import Path
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
    assert all(pin(p['path'])==p for p in plan['pins']), 'Pinned diagnostic source changed.'
    return plan


def prepare(out):
    assert not out.exists()
    previous=ROOT/'artifacts/isae/ae2-beta1-recovery-staged-0048-20261110'
    from scripts.recover_isae_ae2_saved import checked as checked_recovery
    old=checked_recovery(previous)
    case=next(c for c in old['cases'] if c['id']=='AE-2-m15_02-b01-ias017-m160')
    verified=previous/case['id'];report=read(verified/'report.json')
    assert report['status']=='VERIFIED_ORIGINAL_SAVED_EQUILIBRIUM'
    assert all(c['passed'] for c in report['checks']) and report['fresh_residual']<=1e-12
    assert read(verified/'terminal.json')['returncode']==0
    assert read(verified/'sources-verified.json')['all_pins_checked_before_and_after'] is True
    base=read(case['request']);seed=read(case['result'])
    assert base['condition']['beta']==1 and base['condition']['speed']==17
    assert seed['converged'] and seed['residual']<=1e-12 and not base.get('initial_state')
    paths=[Path(__file__),Path(case['request']),Path(case['result']),
        previous/'plan.json',previous/'assessment.json',
        ROOT/'scripts/probe_isae_ae2_cold_trace.py',ROOT/'scripts/probe_isae_ae2_staged_inverse.py',
        ROOT/'scripts/probe_isae_ae2_inverse_speed.py',ROOT/'docs/validation/aswing-authoritative-sources.json']
    paths += [verified/name for name in ('report.json','terminal.json','sources-verified.json')]
    paths += [Path(p['path']) for p in case['job']['source_pins']+case['job']['kernel_pins']]
    references=read(ROOT/'docs/validation/aswing-authoritative-sources.json')
    for ref in references['files']:
        if ref['id'] in ('isae-part-4','aswing-steady'):
            paths += [ROOT/ref['local_pdf'],ROOT/ref['local_text']]
    cases=[dict(name=f'beta{b:02d}',beta=b,predecessor=None if b==1 else f'beta{b-1:02d}') for b in range(1,6)]
    write(out/'plan.json',dict(observed_utc=datetime.now(timezone.utc).isoformat(),cases=cases,
        seed_result=case['result'],base_request=base,expected_elements=case['job']['expected_elements'],
        pins=[pin(p) for p in sorted(set(paths))],limits=LIMITS,primary_votes_added=0,
        physical_residual_gate=1e-12,method=__doc__,
        qualifications=['Intermediate incidences are diagnostics, not additional original reference cells.',
            'Only incidence, the explicit saved-state seed and tolerance=1e-12 change from the original beta1 request.',
            'The stricter corrector tolerance preserves the existing full-residual acceptance gate.',
            'The first solve is an unchanged-condition control; it must preserve the original full state.',
            'A local branch trace does not prove uniqueness or stability.']))
    print('Prepared beta1 control and beta2–5 continuation; no solver started.',flush=True)


def request_for(out,plan,case):
    if case['predecessor']:
        prior=out/case['predecessor']
        assert read(prior/'verify/terminal.json')['returncode']==0
        assert read(prior/'verify/sources-verified.json')['all_pins_checked_before_and_after'] is True
        report=read(prior/'report.json');assert report['status']=='VERIFIED_WARM_EQUILIBRIUM'
        assert report['result']==pin(prior/'result.json')
        seed_path=prior/'result.json'
    else:seed_path=Path(plan['seed_result'])
    request=deepcopy(plan['base_request']);request['condition']['beta']=case['beta']
    request['tolerance']=plan['physical_residual_gate']
    request['initial_state']=read(seed_path)['equilibrium_state']
    return request,seed_path


def solve(out,case):
    from openswing.bridge import dispatch
    folder=out/case['name'];request=read(folder/'request.json')
    before=time.monotonic();last=[None,0.]
    with (folder/'solve/progress.jsonl').open('x') as events:
        def progress(stage,current,total):
            now=time.monotonic()
            if stage==last[0] and now-last[1]<.5 and current!=total:return
            events.write(json.dumps(dict(stage=stage,current=current,total=total,
                wall_seconds=now-before,cpu_seconds=time.process_time()),default=float)+'\n');events.flush()
            last[:]=[stage,now]
        result=dispatch(request,progress=progress)
    write(folder/'result.json',result)
    write(folder/'solve-report.json',dict(result=pin(folder/'result.json'),
        request=pin(folder/'request.json'),solve_seconds=time.monotonic()-before,
        operations=dict(warm_solves=1,cold_solves=0),
        initialization=result.get('equilibrium_initialization'),primary_votes_added=0))
    print(json.dumps(dict(beta=case['beta'],residual=result['residual'],
        initialization=result.get('equilibrium_initialization'))),flush=True)


def verify(out,plan,case):
    import numpy as np
    from scripts.probe_isae_ae2_staged_inverse import network
    from openswing.equilibrium_state import identity,restore
    from openswing.network import network_snapshot
    folder=out/case['name'];request=read(folder/'request.json');result=read(folder/'result.json')
    expected,seed_path=request_for(out,plan,case);assert request==expected
    n=network(request);x=restore(n,result['equilibrium_state']);checks=[]
    def check(name,ok):checks.append(dict(name=name,passed=bool(ok)))
    check('identity',identity(n)==result['equilibrium_state']['identity'])
    check('restore_no_residual',n.nfev==0)
    residual,data=n.residual(x,detail=True);fresh=network_snapshot(n,residual,data)
    error=float(np.max(abs(residual)))
    check('one_fresh_residual',n.nfev==1)
    check('fresh_full_residual',result['converged'] and result['residual']<=1e-12 and error<=1e-12)
    check('node_element_counts',n.ne==plan['expected_elements'] and n.nn==n.ne+1)
    initialization=result['equilibrium_initialization']
    check('verified_seed_and_warm_initialization',request['initial_state']==read(seed_path)['equilibrium_state']
          and initialization['initialization']=='saved physical equilibrium')
    check('complete_final_tangent_rank',initialization['rank_check'] in
        ('sparse inverse-norm certificate','full-Jacobian SVD') and initialization['residual']<=1e-12)
    check('source_identity',result['numerics']==request['numerics'] and
        result['structural_operator']==request['numerics']['structural_operator'])
    check('inertia_unavailable',result['mass_properties']['dynamic_inertia_available'] is False)
    check('source_recovery',result['structure']['strain_source']=='source_discrete_constitutive')
    for kind in ('force','moment'):
        a=np.asarray(result['applied_'+kind]);b=np.asarray(result['support_'+kind]);scale=np.linalg.norm(a)+np.linalg.norm(b)
        check(kind+'_balance',np.linalg.norm(a+b)<=1e-7*scale)
    for c in n.constraints:
        if c['kind']=='ground':
            check('clamp_position',np.max(abs(data['r'][c['a']]-n.rj[c['a']]))<=1e-10)
            check('clamp_frame',np.max(abs(data['Q'][c['a']]-np.eye(3)))<=1e-10)
    def values(s):return dict(RY_m=s['position_earth'][1],Psi_deg=s['heading'],sensor_V_m_s=s['speed'],sensor_beta_deg=s['beta'])
    sensor=result['sensors'][0];v=values(sensor);f=values(fresh['sensors'][0])
    check('sensor_restored_parity',all(abs(v[k]-f[k])<=2e-10*(1+abs(v[k])) for k in v))
    u,b,w=sensor['air_velocity_sensor'];speed=np.linalg.norm([u,b,w])
    check('sensor_flow_speed',abs(speed-v['sensor_V_m_s'])<=1e-12)
    check('sensor_flow_beta',abs(np.rad2deg(np.arcsin(-b/speed))-v['sensor_beta_deg'])<=1e-10)
    strips=result['strips'];sf=np.asarray([s['force'] for s in strips]);sm=np.asarray([s['moment'] for s in strips]);sp=np.asarray([s['position'] for s in strips])
    check('aero_force_total',np.max(abs(sf.sum(axis=0)-result['surface_force']))<=2e-10)
    check('aero_moment_total',np.max(abs((sm+np.cross(sp-n.model.reference[1],sf)).sum(axis=0)-result['moment']))<=2e-10)
    control=None
    if case['predecessor'] is None:
        old=read(seed_path);ox=restore(n,old['equilibrium_state']);ov=values(old['sensors'][0])
        control=dict(maximum_coordinate_difference=float(np.max(abs(x-ox))),value_differences={k:abs(v[k]-ov[k]) for k in v})
        check('control_full_state',control['maximum_coordinate_difference']<=1e-10)
        check('control_values',all(z<=1e-10 for z in control['value_differences'].values()))
    assert all(c['passed'] for c in checks),checks
    write(folder/'report.json',dict(status='VERIFIED_WARM_EQUILIBRIUM',beta=case['beta'],
        checks=checks,fresh_residual=error,values=v,control=control,
        result=pin(folder/'result.json'),request=pin(folder/'request.json'),seed=pin(seed_path),
        original_solve_process=read(folder/'solve/terminal.json'),primary_votes_added=0))
    print(json.dumps(dict(beta=case['beta'],checks=len(checks),residual=error,values=v)),flush=True)


def launch(out,name,phase):
    resource.setrlimit(resource.RLIMIT_AS,(LIMITS['address_space_bytes'],)*2)
    plan=checked(out);case=next(c for c in plan['cases'] if c['name']==name)
    folder=out/name;phase_folder=folder/phase
    if phase=='solve':
        assert not folder.exists()
        request,seed=request_for(out,plan,case);folder.mkdir()
        write(folder/'request.json',request)
    else:
        assert read(folder/'solve/terminal.json')['process_reaped'] is True
        assert read(folder/'solve/sources-verified.json')['all_pins_checked_before_and_after'] is True
        assert (folder/'result.json').exists(), 'No complete result is available for verification.'
    phase_folder.mkdir(exist_ok=False)
    write(phase_folder/'started.json',dict(observed_utc=datetime.now(timezone.utc).isoformat(),phase=phase))
    def caps():
        resource.setrlimit(resource.RLIMIT_AS,(LIMITS['address_space_bytes'],)*2)
        resource.setrlimit(resource.RLIMIT_CPU,(LIMITS['cpu_seconds'],)*2)
    start=time.monotonic();pid=0;timeout=False
    with (phase_folder/'stdout.log').open('x') as stdout,(phase_folder/'stderr.log').open('x') as stderr:
        child=subprocess.Popen([sys.executable,str(Path(__file__).resolve()),'worker','--output',str(out),
            '--case',name,'--phase',phase],cwd=ROOT,env={**os.environ,**THREADS},preexec_fn=caps,
            stdout=stdout,stderr=stderr,start_new_session=True)
        try:
            while not pid:
                pid,status,usage=os.wait4(child.pid,os.WNOHANG)
                if pid:break
                if time.monotonic()-start>LIMITS['wall_seconds']:
                    timeout=True;os.killpg(child.pid,signal.SIGKILL);pid,status,usage=os.wait4(child.pid,0);break
                time.sleep(.05)
        finally:
            if not pid:
                os.killpg(child.pid,signal.SIGKILL);pid,status,usage=os.wait4(child.pid,0)
            child.returncode=os.waitstatus_to_exitcode(status)
    terminal=dict(returncode=child.returncode,supervisor_timeout=timeout,process_reaped=True,
        wall_seconds=time.monotonic()-start,cpu_seconds=usage.ru_utime+usage.ru_stime,
        peak_rss_kib=usage.ru_maxrss,finished_utc=datetime.now(timezone.utc).isoformat())
    write(phase_folder/'terminal.json',terminal);checked(out)
    write(phase_folder/'sources-verified.json',dict(all_pins_checked_before_and_after=True,
        plan=pin(out/'plan.json'),terminal=pin(phase_folder/'terminal.json')))
    print(json.dumps(dict(case=name,phase=phase,**terminal)),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',choices=['prepare','launch','worker']);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--case');p.add_argument('--phase',choices=['solve','verify']);a=p.parse_args();out=a.output.resolve()
    if a.action=='prepare':prepare(out)
    elif a.action=='launch':launch(out,a.case,a.phase)
    else:
        assert all(os.environ.get(k)==v for k,v in THREADS.items())
        plan=read(out/'plan.json');case=next(c for c in plan['cases'] if c['name']==a.case)
        if a.phase=='solve':solve(out,case)
        else:verify(out,plan,case)
