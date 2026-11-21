"""Trace the existing AE-2 cold continuation one accepted load boundary per job.

Uses the production continuation API; partial states never receive native votes.
All original failed attempts remain intact. Production source is unchanged.
"""
import argparse
from copy import deepcopy
import faulthandler
import json
import os
from pathlib import Path
import resource
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.probe_isae_ae2_cold_trace import read,write,pin,THREADS


def checked(out):
    p=read(out/'plan.json')
    assert all(pin(x['path'])==x for x in p['pins'])
    return p


def prepare(out):
    assert not out.exists()
    parent=ROOT/'artifacts/isae/ae2-cold-trace-20261110'
    previous=read(parent/'plan.json')
    assert all(pin(x['path'])==x for x in previous['pins'])
    cases=[];paths=[Path(__file__),parent/'plan.json',parent/'cases/control19-m80/terminal.json']
    paths += [Path(x['path']) for x in previous['pins']]
    for c in previous['cases']:
        request=parent/'cases'/c['name']/'cases'/c['mesh']/'request.json'
        source=read(request)
        assert not source.get('initial_state') and 'continuation' not in source
        paths.append(request)
        case=dict(c,request=str(request),expected_elements=int(c['mesh'][1:])+1)
        if c['prior_status']=='computed':
            base=Path(c['prior_result'])/'cases'/c['mesh']/'result.json'
            assert base.exists();case['control_result']=str(base);paths.append(base)
        cases.append(case)
    write(out/'plan.json',dict(observed_utc=datetime.now(timezone.utc).isoformat(),
        cases=cases,pins=[pin(p) for p in sorted(set(paths))],limits=previous['limits'],
        primary_votes_added=0,method=__doc__,
        qualifications=['This is a new partitioned diagnostic, not a retry of the same timed-out process.',
            'Only the declared continuation checkpoint/max_load_steps transport is added.',
            'Original load stepping, matrix refresh, rank and physical residual gates remain.',
            'Complete control must match the prior accepted cold solution before candidate cases start.']))
    print('Prepared three cold continuations using production checkpoint boundaries.')


def verify(request,result,case):
    import numpy as np
    from scripts.probe_isae_ae2_staged_inverse import network
    from openswing.equilibrium_state import identity,restore
    from openswing.network import network_snapshot
    n=network(request);x=restore(n,result['equilibrium_state']);checks=[]
    def check(name,passed):checks.append(dict(name=name,passed=bool(passed)))
    check('identity',identity(n)==result['equilibrium_state']['identity'])
    check('restore_no_residual',n.nfev==0)
    r,data=n.residual(x,detail=True);fresh=network_snapshot(n,r,data)
    check('one_fresh_residual',n.nfev==1)
    check('fresh_full_residual',np.max(abs(r))<=1e-8)
    check('node_element_counts',n.ne==case['expected_elements'] and n.nn==n.ne+1)
    check('cold_state',not request.get('initial_state'))
    check('source_identity_and_no_launch',result['numerics']==request['numerics'] and
          result['structural_operator']==request['numerics']['structural_operator'] and 'launch' not in result['equilibrium_state'])
    check('inertia_unavailable',result['mass_properties']['dynamic_inertia_available'] is False and result['mass_properties']['spatial_matrix'] is None)
    check('source_recovery',result['structure']['strain_source']=='source_discrete_constitutive')
    for kind in ('force','moment'):
        a=np.asarray(result['applied_'+kind]);b=np.asarray(result['support_'+kind]);scale=np.linalg.norm(a)+np.linalg.norm(b)
        check(kind+'_balance',np.linalg.norm(a+b)<=1e-7*scale)
    for c in n.constraints:
        if c['kind']=='ground':
            check('clamp_position',np.max(abs(data['r'][c['a']]-n.rj[c['a']]))<=1e-10)
            check('clamp_frame',np.max(abs(data['Q'][c['a']]-np.eye(3)))<=1e-10)
    sensor=result['sensors'][0];other=fresh['sensors'][0]
    def values(s):return dict(RY_m=s['position_earth'][1],Psi_deg=s['heading'],sensor_V_m_s=s['speed'],sensor_beta_deg=s['beta'])
    v,f=values(sensor),values(other)
    check('sensor_restored_parity',all(abs(v[k]-f[k])<=2e-10*(1+abs(v[k])) for k in v))
    u,b,w=sensor['air_velocity_sensor'];speed=np.linalg.norm([u,b,w])
    check('sensor_flow_speed',abs(speed-v['sensor_V_m_s'])<=1e-12)
    check('sensor_flow_beta',abs(np.rad2deg(np.arcsin(-b/speed))-v['sensor_beta_deg'])<=1e-10)
    strips=result['strips'];sf=np.asarray([s['force'] for s in strips]);sm=np.asarray([s['moment'] for s in strips]);sp=np.asarray([s['position'] for s in strips])
    check('aero_force_total',np.max(abs(sf.sum(axis=0)-result['surface_force']))<=2e-10)
    check('aero_moment_total',np.max(abs((sm+np.cross(sp-n.model.reference[1],sf)).sum(axis=0)-result['moment']))<=2e-10)
    parity=None
    if 'control_result' in case:
        old=read(case['control_result']);ov=values(old['sensors'][0]);ox=restore(n,old['equilibrium_state'])
        parity=dict(values={k:abs(v[k]-ov[k]) for k in v},maximum_coordinate_difference=float(np.max(abs(x-ox))))
        check('control_values',all(z<=1e-10 for z in parity['values'].values()))
        check('control_full_coordinates',parity['maximum_coordinate_difference']<=1e-11)
    assert all(c['passed'] for c in checks),checks
    return dict(status='computed',values=v,checks=checks,parity=parity,fresh_residual=float(np.max(abs(r))),primary_votes_added=0)


def worker(out,name,index):
    limits=read(out/'plan.json')['limits']
    resource.setrlimit(resource.RLIMIT_AS,(limits['address_space_bytes'],)*2)
    resource.setrlimit(resource.RLIMIT_CPU,(limits['soft_cpu_seconds'],limits['hard_cpu_seconds']))
    plan=checked(out);case=next(c for c in plan['cases'] if c['name']==name)
    assert all(os.environ.get(k)=='1' for k in THREADS)
    folder=out/'cases'/name/f'{index:02d}';request=deepcopy(read(case['request']))
    original=deepcopy(request)
    if index:
        prior=folder.parent/f'{index-1:02d}'
        assert read(prior/'terminal.json')['returncode']==0
        old=read(prior/'result.json');assert old['continuation_status']=='pending'
        options=dict(checkpoint=old['checkpoint'],max_load_steps=1)
    else:options=dict(max_load_steps=1)
    request['continuation']=options;write(folder/'request.json',request)
    stack=(folder/'signal-stack.log').open('x')
    faulthandler.register(signal.SIGXCPU,file=stack,all_threads=False,chain=False)
    faulthandler.register(signal.SIGALRM,file=stack,all_threads=False,chain=True)
    signal.alarm(limits['alarm_seconds'])
    from openswing.bridge import dispatch
    from openswing.steady_continuation import plain
    start=time.monotonic();last=[0.]
    with (folder/'progress.jsonl').open('x') as events:
        def progress(stage,current,total):
            now=time.monotonic()
            if stage!='static_load' and now-last[0]<.2:return
            frame=sys._getframe().f_back;net=None
            while frame:
                for k in ('net','network'):
                    obj=frame.f_locals.get(k)
                    if type(obj).__name__=='SourceCoupledNetwork':net=obj;break
                if net is not None:break
                frame=frame.f_back
            del frame
            event=dict(wall_seconds=now-start,cpu_seconds=time.process_time(),stage=stage,current=current,total=total)
            if net is not None:event.update(nfev=net.nfev,iterations=getattr(net,'structured_iterations',[])[-2:],loads=getattr(net,'continuation_diagnostics',[])[-2:])
            events.write(json.dumps(plain(event),allow_nan=False)+'\n');events.flush();last[0]=now
        result=dispatch(request,progress=progress)
    write(folder/'result.json',result)
    report=verify(original,result,case) if result['continuation_status']=='complete' else dict(status='pending',accepted=False,load_fraction=result['load_fraction'],boundary_residual=result['checkpoint']['physical_residual'],primary_votes_added=0)
    checked(out);report.update(wall_seconds=time.monotonic()-start,cpu_seconds=time.process_time())
    write(folder/'report.json',report)
    print(json.dumps(dict(case=name,index=index,**report)),flush=True)


def launch(out,name,index):
    plan=checked(out);case=next(c for c in plan['cases'] if c['name']==name)
    if 'control_result' not in case:
        reports=list((out/'cases/control19-m80').glob('*/report.json'))
        assert any(read(p)['status']=='computed' for p in reports),'Control must pass first.'
    folder=out/'cases'/name/f'{index:02d}';folder.mkdir(parents=True,exist_ok=False)
    write(folder/'started.json',dict(observed_utc=datetime.now(timezone.utc).isoformat()))
    start=time.monotonic();timeout=False
    with (folder/'stdout.log').open('x') as stdout,(folder/'stderr.log').open('x') as stderr:
        child=subprocess.Popen([sys.executable,str(Path(__file__).resolve()),'worker','--output',str(out),'--case',name,'--index',str(index)],cwd=ROOT,env={**os.environ,**THREADS},stdout=stdout,stderr=stderr,start_new_session=True)
        try:
            while True:
                pid,status,usage=os.wait4(child.pid,os.WNOHANG)
                if pid:break
                if time.monotonic()-start>plan['limits']['supervisor_seconds']:
                    timeout=True;os.killpg(child.pid,signal.SIGKILL);pid,status,usage=os.wait4(child.pid,0);break
                time.sleep(.05)
        finally:
            if not locals().get('pid'):
                os.killpg(child.pid,signal.SIGKILL);pid,status,usage=os.wait4(child.pid,0)
            child.returncode=os.waitstatus_to_exitcode(status)
    receipt=dict(case=name,index=index,returncode=child.returncode,process_reaped=True,supervisor_timeout=timeout,wall_seconds=time.monotonic()-start,cpu_seconds=usage.ru_utime+usage.ru_stime,peak_rss_kib=usage.ru_maxrss,finished_utc=datetime.now(timezone.utc).isoformat())
    write(folder/'terminal.json',receipt);print(json.dumps(receipt),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=['prepare','worker','launch']);p.add_argument('--output',type=Path,required=True);p.add_argument('--case');p.add_argument('--index',type=int);a=p.parse_args()
    if a.action=='prepare':prepare(a.output.resolve())
    else:globals()[a.action](a.output.resolve(),a.case,a.index)
