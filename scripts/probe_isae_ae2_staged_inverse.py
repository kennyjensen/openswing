"""AE-2 inverse-speed solve and complete verification in bounded stages.

An in-process checkpoint interrupts the unchanged production solver exactly
before its final custom-tangent check. This never returns an accepted solve.
Acceptance requires every original stencil column, full rank/smoothness tests,
and fresh physical checks in a separate process. No production file is edited.
"""
import argparse
from copy import deepcopy
import importlib.util
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
from scripts.probe_isae_ae2_inverse_speed import checked as old_checked, pin, read, write, now, THREADS


def prepare(stage):
    assert not stage.exists()
    parent=ROOT/'artifacts/isae/ae2-inverse-speed-20261110'
    old=old_checked(parent)
    pins={p['path']:p for p in old['pins']}
    inputs=[parent/'plan.json',parent/'assessment.json',Path(__file__),
        ROOT/'scripts/isae_custom_tangent_stages.py',ROOT/'tests/test_isae_custom_tangent_stages.py']
    for name in ('m40-cold20','m20-cold20','m20-native19-y'):
        folder=parent/'cases'/name
        assert read(folder/'terminal.json')['returncode']==0
        assert read(folder/'report.json')['status']=='computed'
        inputs += [folder/name for name in ('request.json','result.json','report.json','terminal.json')]
    for p in inputs:pins[str(p.resolve())]=pin(p)
    cases=[]
    for speed in (19,17,18):
        original,=[c for c in old['cases'] if c['name']==f'm40-native{speed}-y']
        cases.append(dict(name=f'native{speed}',native_speed=speed,native_row=original['native_row'],
            request=original['request'],seed=str(parent/'cases/m40-cold20/result.json') if speed==19 else 'native19',
            size=546,columns_per_job=96))
    write(stage/'plan.json',dict(observed_utc=now(),cases=cases,pins=list(pins.values()),
        control=str(parent/'cases/m20-native19-y'),control_seed=str(parent/'cases/m20-cold20/result.json'),
        parent=str(parent),primary_votes_added=0,limits=old['limits'],
        new_solver_executions=3,method=__doc__,
        qualifications=old['limitations']+[
            'This is a new staged attempt after the retained monolithic nominal40 failure.',
            'No candidate is accepted or used as a seed until all verification stages pass.',
            'All 546 full-system columns and four original residual perturbations per column are required.',
            'Control parity limits: rank absolute1e-10 plus relative1e-7; smoothness absolute1e-4 (roundoff in restored state).']))
    print('Prepared three nominal40 staged diagnostics, six tangent blocks each; production code unchanged.')


def checked(stage):
    plan=read(stage/'plan.json')
    assert all(pin(p['path'])==p for p in plan['pins']), 'Pinned input changed.'
    return plan


def network(request):
    from openswing.asw import parse_asw
    from openswing.aero import FlightCondition
    from openswing.source_coupled import SourceCoupledNetwork
    condition=deepcopy(request['condition'])
    for key in ('controls','powers'):condition[key]={int(k):v for k,v in condition[key].items()}
    model=parse_asw(request['source'],beam_interpolation=request['numerics']['beam_interpolation'])
    return SourceCoupledNetwork(model,request['panels'],FlightCondition(**condition),None,[],
        operating_constraints=request['operating_constraints'])


def load_candidate(stage,case):
    import numpy as np
    from openswing.equilibrium_state import restore
    folder=stage/'cases'/case['name'];candidate=read(folder/'candidate.json')
    assert candidate['status']=='PENDING_VERIFICATION'
    assert all(pin(p['path'])==p for p in candidate['pins'])
    request=read(folder/'request.json');n=network(request)
    restored=restore(n,read(folder/'state.json'))
    with np.load(folder/'candidate.npz') as saved:x=saved['x'].copy();base=saved['residual'].copy()
    assert len(x)==case['size']==n.size
    np.testing.assert_allclose(restored,x,rtol=1e-14,atol=2e-15)
    n.operating.initial_values=candidate['initial_values']
    fresh=n.residual(x)
    np.testing.assert_allclose(fresh,base,atol=1e-12,rtol=1e-8)
    assert np.max(abs(fresh))<=1e-8
    return n,x,folder,candidate


def candidate(stage,case):
    import numpy as np
    from openswing import custom_constraints
    from openswing.source_discrete import _solve_source_network
    from openswing.equilibrium_state import capture
    from openswing.network import network_snapshot
    assert read(stage/'control.json')['status']=='PASS'
    folder=stage/'cases'/case['name'];assert not folder.exists();folder.mkdir(parents=True)
    if case['seed']=='native19':
        previous=stage/'cases/native19'
        report=read(previous/'report.json');assert report['status']=='computed'
        assert report['result']==pin(previous/'result.json')
        seed_path=previous/'result.json'
    else:seed_path=Path(case['seed'])
    seed=read(seed_path)['equilibrium_state'];seed_pin=pin(seed_path)
    request=deepcopy(case['request']);request['initial_state']=seed
    write(folder/'request.json',request);n=network(request)
    original=custom_constraints.check_custom_tangent
    started=time.monotonic();calls=[]
    class PendingVerification(Exception):pass
    def checkpoint(operating,residual,x,start,**kwargs):
        assert operating is n.operating and start==n.operating_start
        assert kwargs.get('derivative_context') is not None and kwargs.get('rank',True)
        assert not calls;calls.append(True)
        r,data=n.residual(x,detail=True)
        assert np.max(abs(r))<=request['tolerance']
        np.savez_compressed(folder/'candidate.npz',x=x,residual=r)
        write(folder/'state.json',capture(n,x,residual=float(np.max(abs(r))),include_launch=False))
        write(folder/'candidate-fields.json',network_snapshot(n,r,data))
        files=[folder/name for name in ('request.json','candidate.npz','state.json','candidate-fields.json')]
        write(folder/'candidate.json',dict(status='PENDING_VERIFICATION',accepted=False,
            observed_utc=now(),size=len(x),initial_values=n.operating.initial_values,
            solve_to_checkpoint_seconds=time.monotonic()-started,solver_evaluations=n.nfev,
            pins=[pin(p) for p in files]+[seed_pin],primary_votes_added=0))
        raise PendingVerification()
    custom_constraints.check_custom_tangent=checkpoint
    try:
        try:_solve_source_network(n,request['tolerance'],request['continuation_steps'],seed,None)
        except PendingVerification:pass
        else:raise AssertionError('The pending state must not return as an accepted solve.')
    finally:custom_constraints.check_custom_tangent=original
    assert calls==[True] and pin(seed_path)==seed_pin
    checked(stage)
    print(json.dumps(dict(status='PENDING_VERIFICATION',case=case['name'],seconds=time.monotonic()-started)),flush=True)


def column(stage,case,index):
    import numpy as np
    from openswing.wall_root import wall_root_derivatives
    from scripts.isae_custom_tangent_stages import columns
    n,x,folder,pending=load_candidate(stage,case)
    first=index*case['columns_per_job'];stop=min(len(x),first+case['columns_per_job'])
    path=folder/'columns'/f'{index:03d}.npz';assert not path.exists()
    began=time.monotonic()
    block=columns(n.operating,lambda v:n.residual(v),x,n.operating_start,first,stop,
        derivative_context=lambda v:wall_root_derivatives(n,v))
    path.parent.mkdir(exist_ok=True);np.savez_compressed(path,**block)
    write(path.with_suffix('.json'),dict(status='COLUMNS_CHECKED',first=first,stop=stop,
        candidate=pin(folder/'candidate.json'),block=pin(path),seconds=time.monotonic()-began,
        residual_evaluations=block['residual_evaluations'],mismatch=block['mismatch']))
    checked(stage);print(json.dumps(dict(case=case['name'],first=first,stop=stop,mismatch=block['mismatch'])),flush=True)


def finalize(stage,case):
    import numpy as np
    from openswing.source_discrete import source_network_result
    from openswing.equilibrium_state import capture,restore,identity
    from openswing.network import network_snapshot
    from scripts.isae_custom_tangent_stages import conclude
    n,x,folder,pending=load_candidate(stage,case);assert not (folder/'report.json').exists()
    blocks=[];block_pins=[]
    for index,first in enumerate(range(0,len(x),case['columns_per_job'])):
        path=folder/'columns'/f'{index:03d}.npz';receipt=read(path.with_suffix('.json'))
        assert receipt['candidate']==pin(folder/'candidate.json') and receipt['block']==pin(path)
        with np.load(path) as data:b={k:data[k].copy() for k in data.files}
        b.update(first=int(b['first']),stop=int(b['stop']),mismatch=float(b['mismatch']))
        assert b['first']==first and b['stop']==min(len(x),first+case['columns_per_job'])
        blocks.append(b);block_pins += [pin(path),pin(path.with_suffix('.json'))]
    tangent=conclude(blocks,len(x));n.custom_trim=tangent
    result=source_network_result(n,x)
    result['equilibrium_state']=capture(n,x,residual=result['residual'],include_launch=False)
    fresh_net=network(read(folder/'request.json'));decoded=restore(fresh_net,result['equilibrium_state'])
    assert fresh_net.nfev==0
    residual,data=fresh_net.residual(decoded,detail=True);fresh=network_snapshot(fresh_net,residual,data)
    checks=[]
    def check(name,value):checks.append(dict(name=name,passed=bool(value)))
    check('one_fresh_full_residual',fresh_net.nfev==1 and np.max(abs(residual))<=1e-8)
    check('identity',identity(fresh_net)==result['equilibrium_state']['identity'])
    check('declared_mesh',fresh_net.ne==41 and fresh_net.nn==42)
    check('source_operator',result['structural_operator']=='drela-steady-coupled-v1')
    for kind in ('force','moment'):
        a=np.asarray(result['applied_'+kind]);b=np.asarray(result['support_'+kind])
        check(kind+'_balance',np.linalg.norm(a+b)<=1e-7*(np.linalg.norm(a)+np.linalg.norm(b)))
    for c in fresh_net.constraints:
        if c['kind']=='ground':
            check('clamp_position',np.max(abs(data['r'][c['a']]-fresh_net.rj[c['a']]))<=1e-10)
            check('clamp_frame',np.max(abs(data['Q'][c['a']]-np.eye(3)))<=1e-10)
    sensor=result['sensors'][0];other=fresh['sensors'][0]
    check('fresh_sensor_position',np.max(abs(np.array(sensor['position_earth'])-other['position_earth']))<=1e-10)
    check('fresh_sensor_angles',abs(sensor['heading']-other['heading'])<=1e-8 and abs(sensor['beta']-other['beta'])<=1e-8)
    target=case['request']['operating_constraints'][0]['target']
    check('sensor_constraint',abs(sensor['position_earth'][1]-target)<=1e-8)
    check('complete_custom_rank',tangent['column_scaled_reciprocal_condition']>1e-10)
    check('custom_smoothness',tangent['one_sided_tangent_ratio']<=1)
    check('unchanged_seed_and_request',all(pin(p['path'])==p for p in pending['pins']))
    check('unchanged_sources',all(pin(p['path'])==p for p in read(stage/'plan.json')['pins']))
    assert all(c['passed'] for c in checks),checks
    values=dict(IAS=result['operating_values']['speed'],RY_m=sensor['position_earth'][1],
        Psi_deg=sensor['heading'],sensor_V_m_s=sensor['speed'],sensor_beta_deg=sensor['beta'])
    write(folder/'result.json',result);write(folder/'restored-result.json',fresh)
    write(folder/'report.json',dict(status='computed',values=values,checks=checks,custom_tangent=tangent,
        fresh_residual=float(np.max(abs(residual))),candidate=pin(folder/'candidate.json'),blocks=block_pins,
        result=pin(folder/'result.json'),fresh_result=pin(folder/'restored-result.json'),primary_votes_added=0,
        native_speed=case['native_speed'],native_row=case['native_row'],observed_utc=now()))
    print(json.dumps(dict(status='computed',case=case['name'],values=values,tangent=tangent)),flush=True)


def control(stage):
    import numpy as np
    from openswing.equilibrium_state import restore
    from openswing.wall_root import wall_root_derivatives
    from scripts.isae_custom_tangent_stages import columns,conclude
    plan=checked(stage);folder=Path(plan['control']);request=read(folder/'request.json');old=read(folder/'result.json')
    n=network(request);x=restore(n,old['equilibrium_state'])
    n.operating.initial_values=[read(Path(plan['control_seed']))['sensors'][0]['position_earth'][1]]
    blocks=[columns(n.operating,lambda v:n.residual(v),x,n.operating_start,first,min(first+96,len(x)),
        derivative_context=lambda v:wall_root_derivatives(n,v)) for first in range(0,len(x),96)]
    actual=conclude(blocks,len(x));expected=old['custom_trim']
    assert abs(actual['one_sided_tangent_ratio']-expected['one_sided_tangent_ratio'])<=1e-4
    assert abs(actual['column_scaled_reciprocal_condition']-expected['column_scaled_reciprocal_condition'])<=1e-10+1e-7*abs(expected['column_scaled_reciprocal_condition'])
    assert np.max(abs(n.residual(x)))<=1e-8
    checked(stage)
    write(stage/'control.json',dict(status='PASS',actual=actual,expected=expected,new_solves=0,
        input=pin(folder/'result.json'),observed_utc=now()))
    print(json.dumps(dict(status='PASS',actual=actual)),flush=True)


def worker(stage,task,name,index):
    plan=checked(stage);limits=plan['limits']
    resource.setrlimit(resource.RLIMIT_AS,(limits['address_space_bytes'],)*2)
    resource.setrlimit(resource.RLIMIT_CPU,(limits['cpu_seconds'],)*2);signal.alarm(limits['elapsed_seconds'])
    if task=='control':return control(stage)
    case,=[c for c in plan['cases'] if c['name']==name]
    if task=='candidate':candidate(stage,case)
    elif task=='column':column(stage,case,index)
    elif task=='finalize':finalize(stage,case)


def launch(stage,task,name,index):
    plan=checked(stage);key=f'{name}-{task}-{index:03d}'
    folder=stage/'executions'/key;assert not folder.exists(),'Retain previous attempt.'
    folder.mkdir(parents=True);began=time.monotonic();stamp=now();timeout=False
    with (folder/'stdout.log').open('w') as stdout,(folder/'stderr.log').open('w') as stderr:
        child=subprocess.Popen([sys.executable,str(Path(__file__).resolve()),'worker','--stage',str(stage),
            '--task',task,'--case',name,'--index',str(index)],cwd=ROOT,env={**os.environ,**THREADS},
            stdout=stdout,stderr=stderr,start_new_session=True)
        try:code=child.wait(timeout=plan['limits']['supervisor_seconds'])
        except subprocess.TimeoutExpired:
            timeout=True;os.killpg(child.pid,signal.SIGKILL);code=child.wait()
    usage=resource.getrusage(resource.RUSAGE_CHILDREN)
    receipt=dict(started_utc=stamp,finished_utc=now(),returncode=code,reaped=child.poll() is not None,
        supervisor_timeout=timeout,seconds=time.monotonic()-began,cpu_seconds=usage.ru_utime+usage.ru_stime,
        peak_rss_kib=usage.ru_maxrss,task=task,case=name,index=index)
    write(folder/'terminal.json',receipt);print(json.dumps(receipt),flush=True)
    print((folder/'stdout.log').read_text()[-2200:],flush=True)
    if code:print((folder/'stderr.log').read_text()[-2200:],flush=True)
    return code


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=('prepare','worker','launch'))
    p.add_argument('--stage',type=Path,required=True);p.add_argument('--task',choices=('control','candidate','column','finalize'),default='control')
    p.add_argument('--case',default='control');p.add_argument('--index',type=int,default=0)
    a=p.parse_args();stage=a.stage.resolve()
    if a.action=='prepare':prepare(stage)
    elif a.action=='worker':worker(stage,a.task,a.case,a.index)
    else:raise SystemExit(launch(stage,a.task,a.case,a.index))
