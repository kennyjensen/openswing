"""Trace the literal AE-2 wing with a sensor coordinate and solved airspeed.

These are derived equilibrium diagnostics, not native output replacements.
Each command runs one declared case; retain failed attempts without retrying.
"""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
import time
import traceback

ROOT=Path(__file__).resolve().parents[1]
read=lambda p:json.loads(p.read_text())


def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')


def pin(path):
    path=path.resolve();data=path.read_bytes()
    return dict(path=str(path),bytes=len(data),sha256=hashlib.sha256(data).hexdigest())


def prepare(stage):
    assert not stage.exists()
    original=ROOT/'artifacts/isae/ae2-full-load-20261105/m80-v20/cases/m80/request.json'
    base=read(original)
    cases=[]
    for nominal in (20,40):
        request=deepcopy(base)
        request['panels']=dict(default=nominal,beams={'1':dict(count=nominal,spacing='cosine')})
        request['operating_constraints']=[]
        request.pop('initial_state',None)
        cold=f'm{nominal}-cold20'
        cases.append(dict(name=cold,predecessor=None,request=request))
        target=deepcopy(request)
        target['operating_constraints']=[dict(variable='speed',quantity='user.tip',
            expression='sensor("1.position_earth.y")',target=.24,unit='input L',residual_scale=.558)]
        cases.append(dict(name=f'm{nominal}-y024',predecessor=cold,request=target))
    pins=[pin(p) for p in [*sorted((ROOT/'openswing').glob('*.py')),Path(__file__),original]]
    write(stage/'plan.json',dict(status='PREPARED',cases=cases,pins=pins,
        child_cap_seconds=120,retries=0,new_solves=4,native_reference_cells=0,
        motivation='Parameterize the positive branch by sensor RY instead of speed near the failed descending step.',
        physical_inputs='Literal original model, beta5, frozen influences, PG0, gravity and atmosphere unchanged.',
        mesh_scope='Exploratory nominal20/40; neither replaces the registered 80/160 comparison.',
        limitations=['A local branch trace is not a proof of global uniqueness or stability.',
                     'Sensor targets are continuation coordinates, not fitted model parameters or native validation passes.']))
    print(json.dumps(dict(status='PREPARED',new_solves=4)),flush=True)


def run(stage,name):
    plan=read(stage/'plan.json');case,=[c for c in plan['cases'] if c['name']==name]
    folder=stage/'cases'/name
    assert not (folder/'started.json').exists()
    assert all(pin(Path(p['path']))==p for p in plan['pins'])
    request=deepcopy(case['request']);predecessor=None
    if case['predecessor']:
        previous=stage/'cases'/case['predecessor']
        report=read(previous/'report.json')
        assert report['status']=='computed' and pin(previous/'result.json')==report['result']
        request['initial_state']=read(previous/'result.json')['equilibrium_state']
        predecessor=pin(previous/'report.json')
    original_request=deepcopy(request)
    write(folder/'request.json',request)
    write(folder/'started.json',dict(time=time.time(),request=pin(folder/'request.json'),predecessor=predecessor))
    sys.path.insert(0,str(ROOT))
    import numpy as np
    from openswing.bridge import dispatch
    from openswing.aero import FlightCondition
    from openswing.asw import parse_asw
    from openswing.source_coupled import SourceCoupledNetwork
    from openswing.equilibrium_state import identity,restore
    from openswing.network import network_snapshot
    checks=[];started=time.monotonic()
    def check(label,ok,**values):checks.append(dict(name=label,passed=bool(ok),**values))
    try:
        result=dispatch(request)
        solve_seconds=time.monotonic()-started
        write(folder/'result.json',result)
        condition=deepcopy(request['condition'])
        for key in ('controls','powers'):condition[key]={int(k):v for k,v in condition[key].items()}
        model=parse_asw(request['source'],beam_interpolation=request['numerics']['beam_interpolation'])
        net=SourceCoupledNetwork(model,request['panels'],FlightCondition(**condition),None,[],
            operating_constraints=request['operating_constraints'])
        check('identity',identity(net)==result['equilibrium_state']['identity'])
        state=restore(net,result['equilibrium_state']);check('restore_without_residual',net.nfev==0)
        residual,data=net.residual(state,detail=True);fresh=network_snapshot(net,residual,data)
        check('one_fresh_full_residual',net.nfev==1 and np.max(abs(residual))<=1e-8,maximum=float(np.max(abs(residual))))
        check('unchanged_request_and_seed',request==original_request)
        check('source_operator',result['numerics']==request['numerics'])
        for kind in ('force','moment'):
            a=np.asarray(result['applied_'+kind]);b=np.asarray(result['support_'+kind])
            scale=float(np.linalg.norm(a)+np.linalg.norm(b));defect=float(np.linalg.norm(a+b))
            check(kind+'_balance',defect<=1e-7*scale,defect=defect,scale=scale)
        for c in net.constraints:
            if c['kind']=='ground':
                check('clamp_position',np.max(abs(data['r'][c['a']]-net.rj[c['a']]))<=1e-10)
                check('clamp_frame',np.max(abs(data['Q'][c['a']]-np.eye(3)))<=1e-10)
        sensor=result['sensors'][0];other=fresh['sensors'][0]
        check('fresh_sensor_position',np.max(abs(np.array(sensor['position_earth'])-other['position_earth']))<=1e-10)
        check('fresh_sensor_angles',abs(sensor['heading']-other['heading'])<=1e-8 and abs(sensor['beta']-other['beta'])<=1e-8)
        if request['operating_constraints']:
            target=request['operating_constraints'][0]['target']
            check('sensor_constraint',abs(sensor['position_earth'][1]-target)<=1e-8)
            check('complete_custom_rank',result['custom_trim']['column_scaled_reciprocal_condition']>1e-10)
            check('custom_smoothness',result['custom_trim']['one_sided_tangent_ratio']<=1)
        check('unchanged_sources',all(pin(Path(p['path']))==p for p in plan['pins']))
        values=dict(IAS=result['operating_values']['speed'],RY_m=sensor['position_earth'][1],
            Psi_deg=sensor['heading'],sensor_V_m_s=sensor['speed'],sensor_beta_deg=sensor['beta'])
        write(folder/'restored-result.json',fresh)
        report=dict(name=name,status='computed' if all(c['passed'] for c in checks) else 'physical_check_failure',
            solve_seconds=solve_seconds,seconds=time.monotonic()-started,checks=checks,values=values,
            result=pin(folder/'result.json'),request=pin(folder/'request.json'),predecessor=predecessor,
            native_reference_checks=0)
        write(folder/'report.json',report)
        assert report['status']=='computed','Physical check failure'
    except Exception as exc:
        if not (folder/'report.json').exists():
            write(folder/'report.json',dict(name=name,status='failure_retained',seconds=time.monotonic()-started,
                error=dict(type=type(exc).__name__,message=str(exc),traceback=traceback.format_exc()),checks=checks))
        raise
    print(json.dumps({k:report[k] for k in ('name','status','solve_seconds','values')}),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('prepare','run'));parser.add_argument('stage',type=Path)
    parser.add_argument('--case');args=parser.parse_args()
    if args.action=='prepare':prepare(args.stage.resolve())
    else:
        assert args.case
        run(args.stage.resolve(),args.case)
