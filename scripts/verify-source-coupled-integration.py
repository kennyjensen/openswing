#!/usr/bin/env python3
"""Four bounded, cold AE-2 bridge comparisons; no property/setting sweep.

Preparation uses only stdlib. Workers run under a pinned plan, one cold solve
and one restored residual each. A physical-check failure stops the sequence.
Reference printed precision and mesh sensitivity are reported independently.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
AUDIT=Path('/tmp/openswing-source-aero-case-audit-20261026/report.json')
POLICY=dict(beam_interpolation='drela-segspl-v1',structural_operator='drela-steady-coupled-v1')
THREADS={key:'1' for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS')}

def read(p):return json.loads(Path(p).read_text())
def write(p,value):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')
def pin(p):
 p=Path(p).resolve();b=p.read_bytes();return dict(path=str(p),bytes=len(b),sha256=hashlib.sha256(b).hexdigest())
def require(ok,message):
 if not ok:raise RuntimeError(message)
def unchanged(plan):return all(pin(p['path'])==p for p in plan['pins'])

def prepare(stage):
 require(not stage.exists(),'Use a new stage; no overwrite.')
 stage.mkdir(parents=True)
 source=read(AUDIT);model=Path(source['model']['pin']['path']);require(pin(model)==source['model']['pin'],'Literal model changed.')
 cases=[];inputs=[Path(__file__),AUDIT,model,Path(source['archive']['output']['path']),Path(source['archive']['script']['path'])]
 for count in (80,160):
  for kind in ('midpoint','source'):
   name=f'{kind}-{count}';folder=stage/'cases'/name
   condition=dict(source['proposed_condition'],circulation_modes={'1':0})
   request=dict(action='solve',mode='mounted',source=model.read_text(),panels=dict(default=count,beams={'1':dict(count=count,spacing='cosine')}),condition=condition,operating_constraints=[],strut_mode='bilateral',controller=None)
   if kind=='source':request['numerics']=POLICY
   write(folder/'request.json',request);inputs.append(folder/'request.json')
   cases.append(dict(name=name,kind=kind,nominal=count,expected_elements=count+1,request=str(folder/'request.json')))
 inputs.extend(sorted((ROOT/'openswing').glob('*.py')))
 inputs.extend(sorted((ROOT/'web').rglob('*.js')))
 inputs.extend(ROOT/n for n in ('tests/test_source_coupled.py','tests/test_source_sections.py'))
 inputs.extend(Path(p) for p in ('/tmp/openswing-source-aero-primary-20261026/spec.md','/tmp/openswing-source-aero-primary-20261026/oracles.json'))
 plan=dict(status='PREPARED_NOT_EXECUTED',cases=cases,policy=POLICY,cold_solves=4,fresh_residuals=4,retries=0,child_cap_seconds=120,
  gates=dict(residual=1e-8,relative_balance=1e-7,clamp=1e-10,paired_grid=1e-12,restored_parity=2e-10,mesh_relative=.01),
  archive=source['archive'],condition=source['proposed_condition'],literal_model=pin(model),
  kernel_pins={p.name:pin(p)['sha256'] for p in sorted((ROOT/'openswing').glob('*.py'))},pins=[pin(p) for p in sorted(set(inputs))],
  thread_environment=THREADS,acceptance='All four original archived output channels and printed half-units retained. No experimental matching or fitted parameters.',
  scope='Frozen-influence PG0 candidate with declared atmosphere/pose; historical ASWING K/F/PG/mesh and sensor implementation remain unknown.',
  request_normalization='Pointwise beam-1 circulation is explicitly serialized as {1:0} instead of the equivalent empty mapping; empty constraints/null controller/bilateral struts match the UI request. No condition physics changed.')
 require(unchanged(plan),'Preparation inputs changed.')
 write(stage/'plan.json',plan);print(json.dumps(dict(status=plan['status'],plan=pin(stage/'plan.json'))),flush=True)

def worker(stage,name):
 plan=read(stage/'plan.json');authorization=read(stage/'authorization.json')
 require(authorization['plan_sha256']==pin(stage/'plan.json')['sha256'] and authorization['authorized'],'Missing exact-plan authorization.')
 require(unchanged(plan),'Frozen source changed before worker.')
 case=next(c for c in plan['cases'] if c['name']==name);folder=stage/'cases'/name
 require(not (folder/'started.json').exists(),'No worker retries.')
 write(folder/'started.json',dict(pid=os.getpid(),started=time.time(),cold_solve_budget=1))
 sys.path.insert(0,str(ROOT))
 import numpy as np
 from openswing.asw import parse_asw
 from openswing.aero import FlightCondition
 from openswing.bridge import dispatch
 from openswing.network import StaticNetwork,network_snapshot
 from openswing.source_coupled import SourceCoupledNetwork
 from openswing.equilibrium_state import identity,restore
 request=read(folder/'request.json')
 began=time.monotonic();result=dispatch(request);seconds=time.monotonic()-began
 write(folder/'result.json',result)
 condition=dict(request['condition']);condition['controls']={int(k):v for k,v in condition['controls'].items()};condition['powers']={int(k):v for k,v in condition['powers'].items()}
 model=parse_asw(request['source'],beam_interpolation=POLICY['beam_interpolation'] if case['kind']=='source' else 'natural-v1')
 cls=SourceCoupledNetwork if case['kind']=='source' else StaticNetwork
 net=cls(model,request['panels'],FlightCondition(**condition),None,[])
 checks=[]
 def check(label,value,**details):checks.append(dict(name=label,passed=bool(value),**details))
 check('identity',identity(net)==result['equilibrium_state']['identity'])
 x=restore(net,result['equilibrium_state']);check('restore_no_residual',net.nfev==0)
 residual,data=net.residual(x,detail=True);snapshot=network_snapshot(net,residual,data)
 check('one_fresh_residual',net.nfev==1)
 error=float(np.max(abs(residual)));check('fresh_full_residual',error<=plan['gates']['residual'],maximum=error)
 check('node_element_counts',net.ne==case['expected_elements'] and net.nn==case['expected_elements']+1)
 check('cold_state',not request.get('initial_state'))
 if case['kind']=='source':
  check('source_identity_and_no_launch',result.get('numerics')==POLICY and result['structural_operator']==POLICY['structural_operator'] and 'launch' not in result['equilibrium_state'])
  check('inertia_unavailable',result['mass_properties']['dynamic_inertia_available'] is False and result['mass_properties']['spatial_matrix'] is None)
  check('source_recovery',result['structure']['strain_source']=='source_discrete_constitutive')
 balances={}
 for kind in ('force','moment'):
  a=np.asarray(result['applied_'+kind]);s=np.asarray(result['support_'+kind]);scale=float(np.linalg.norm(a)+np.linalg.norm(s));defect=float(np.linalg.norm(a+s));relative=defect/scale if scale else (0. if defect==0 else None)
  balances[kind]=dict(defect=defect,scale=scale,relative=relative)
  check(kind+'_balance',relative is not None and relative<=plan['gates']['relative_balance'],**balances[kind])
 for c in net.constraints:
  if c['kind']=='ground':
   node=c['a'];check('clamp_position',np.max(abs(data['r'][node]-net.rj[node]))<=plan['gates']['clamp'])
   check('clamp_frame',np.max(abs(data['Q'][node]-np.eye(3)))<=plan['gates']['clamp'])
 sensor=result['sensors'][0];fresh=snapshot['sensors'][0]
 values=dict(RY_m=sensor['position_earth'][1],Psi_deg=sensor['heading'],sensor_V_m_s=sensor['speed'],sensor_beta_deg=sensor['beta'])
 fresh_values=dict(RY_m=fresh['position_earth'][1],Psi_deg=fresh['heading'],sensor_V_m_s=fresh['speed'],sensor_beta_deg=fresh['beta'])
 check('sensor_restored_parity',all(abs(values[k]-fresh_values[k])<=plan['gates']['restored_parity']*(1+abs(values[k])) for k in values))
 # Recover the reported speed/angles directly from retained sensor-frame flow.
 u,v,w=sensor['air_velocity_sensor'];speed=float(np.linalg.norm([u,v,w]));beta=float(np.rad2deg(np.arcsin(-v/speed)))
 check('sensor_flow_speed',abs(speed-values['sensor_V_m_s'])<=1e-12)
 check('sensor_flow_beta',abs(beta-values['sensor_beta_deg'])<=1e-10)
 target=plan['archive']['coordinate']['archived_values'];precision=plan['archive']['raw_row']['printed_resolution']
 reference={k:dict(value=values[k],archived=target[k],difference=values[k]-target[k],half_unit=float(precision[k]['nearest_rounding_half_unit_decimal']),passed=abs(values[k]-target[k])<=float(precision[k]['nearest_rounding_half_unit_decimal'])) for k in values}
 strips=result['strips'];sf=np.asarray([s['force'] for s in strips]);sm=np.asarray([s['moment'] for s in strips]);sp=np.asarray([s['position'] for s in strips])
 check('aero_force_total',np.max(abs(sf.sum(axis=0)-np.asarray(result['surface_force'])))<=2e-10)
 # This literal case has no engines, body or point objects, so all aero loads are strips.
 aero_moment=(sm+np.cross(sp-model.reference[1],sf)).sum(axis=0)
 check('aero_moment_total',np.max(abs(aero_moment-np.asarray(result['moment'])))<=2e-10)
 np.savez_compressed(folder/'fresh-fields.npz',residual=residual,r=data['r'],Q=data['Q'],N=data['N'],M=data['M'],gamma=net.unpack(x)[-1],
  element_forces=data['element_forces'],element_moments=data['element_moments'],distributed_mass_force=data['distributed_mass_force'],
  strip_force=sf,strip_moment=sm,strip_position=sp,sensor_position=sensor['position_body'],sensor_axes=sensor['axes_body'],sensor_flow=sensor['air_velocity_sensor'])
 write(folder/'restored-result.json',snapshot)
 passed=all(c['passed'] for c in checks)
 report=dict(status='PASS_PHYSICS_REFERENCE_RECORDED' if passed else 'FAIL_PHYSICAL_CHECKS',case=name,checks=checks,checks_passed=sum(c['passed'] for c in checks),checks_total=len(checks),
  solve_seconds=seconds,fresh_residual=error,balances=balances,values=values,reference=reference,reference_passed=sum(v['passed'] for v in reference.values()),
  mesh_observables=dict(deflection=-values['RY_m'],incremental_projected_twist=-values['Psi_deg']),
  operations=dict(cold_solves=1,fresh_residuals=1),kernel_pins=plan['kernel_pins'],request=pin(folder/'request.json'),result=pin(folder/'result.json'))
 require(unchanged(plan),'Source changed during worker.')
 write(folder/'report.json',report);print(json.dumps({k:report[k] for k in ('status','case','solve_seconds','fresh_residual','reference_passed')}),flush=True)
 require(passed,'Physical checks failed; retain output and stop.')

def run(stage):
 plan=read(stage/'plan.json');auth=read(stage/'authorization.json');require(auth['authorized'] and auth['plan_sha256']==pin(stage/'plan.json')['sha256'],'Plan authorization missing.')
 require(unchanged(plan),'Frozen source changed.')
 require(not (stage/'execution.json').exists(),'No execution retries.')
 execution=dict(status='RUNNING',children=[],cold_solves_planned=4,retries=0);write(stage/'execution.json',execution)
 for case in plan['cases']:
  log=stage/'cases'/case['name']/'run.log';start=time.monotonic()
  with log.open('w') as out:
   child=subprocess.Popen([str(ROOT/'.venv/bin/python'),str(Path(__file__).resolve()),'worker',str(stage),'--case',case['name']],cwd=ROOT,env={**os.environ,**THREADS},stdout=out,stderr=subprocess.STDOUT)
   record=dict(case=case['name'],pid=child.pid,state='RUNNING');execution['children'].append(record);write(stage/'execution.json',execution)
   try:code=child.wait(timeout=plan['child_cap_seconds'])
   except subprocess.TimeoutExpired:
    child.terminate()
    try:code=child.wait(timeout=5)
    except subprocess.TimeoutExpired:child.kill();code=child.wait()
    record['timed_out']=True
   record.update(state='TERMINAL',exit_code=code,reaped=True,seconds=time.monotonic()-start,log=pin(log));write(stage/'execution.json',execution)
  if code!=0:
   execution['status']='FAILURE_RETAINED';write(stage/'execution.json',execution);raise RuntimeError('Child failed: '+case['name'])
  if case['kind']=='source':
   a=read(stage/'cases'/f'midpoint-{case["nominal"]}'/'result.json')['equilibrium_state']['identity']
   b=read(stage/'cases'/case['name']/'result.json')['equilibrium_state']['identity']
   require(a['elements']==b['elements'] and a['stations'].keys()==b['stations'].keys(),'Paired topology mismatch.')
   require(all(a['stations'][k][1]==b['stations'][k][1] and len(a['stations'][k][0])==len(b['stations'][k][0]) and max((abs(x-y) for x,y in zip(a['stations'][k][0],b['stations'][k][0])),default=0)<=plan['gates']['paired_grid'] for k in a['stations']),'Paired station grid mismatch.')
   require(len(a['nodes'])==len(b['nodes']) and max(abs(x-y) for p,q in zip(a['nodes'],b['nodes']) for x,y in zip(p,q))<=plan['gates']['paired_grid'],'Paired node geometry mismatch.')
 reports={c['name']:read(stage/'cases'/c['name']/'report.json') for c in plan['cases']};mesh={}
 for kind in ('midpoint','source'):
  coarse,fine=[reports[f'{kind}-{n}']['mesh_observables'] for n in (80,160)]
  mesh[kind]={k:dict(coarse=coarse[k],fine=fine[k],relative_change=abs(fine[k]-coarse[k])/abs(fine[k]),passed=abs(fine[k]-coarse[k])/abs(fine[k])<=plan['gates']['mesh_relative']) for k in coarse}
 require(all(item['passed'] for policy in mesh.values() for item in policy.values()),'Mesh convergence gate failed.')
 require(unchanged(plan),'Source changed during run.')
 execution.update(status='TERMINAL_COMPLETE',all_children_reaped=True,inputs_unchanged=True);write(stage/'execution.json',execution)
 summary=dict(status='PASS_SOURCE_COUPLED_PHYSICS_REFERENCE_INCOMPLETE',cases={n:{k:v for k,v in r.items() if k!='checks'} for n,r in reports.items()},mesh=mesh,checks_passed=sum(r['checks_passed'] for r in reports.values()),checks_total=sum(r['checks_total'] for r in reports.values()),operations=dict(cold_solves=4,fresh_residuals=4),plan=pin(stage/'plan.json'),acceptance=plan['acceptance'],scope=plan['scope'])
 write(stage/'summary.json',summary);print(json.dumps(dict(status=summary['status'],checks=summary['checks_passed'],mesh=mesh)),flush=True)

if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('action',choices=('prepare','run','worker'));parser.add_argument('stage',type=Path);parser.add_argument('--case');args=parser.parse_args()
 if args.action=='prepare':prepare(args.stage.resolve())
 elif args.action=='worker':worker(args.stage.resolve(),args.case)
 else:
  try:run(args.stage.resolve())
  except Exception as exc:
   path=args.stage.resolve()/'execution.json'
   if path.exists():
    receipt=read(path);receipt.update(status='FAILURE_RETAINED',error=str(exc));write(path,receipt)
   raise
