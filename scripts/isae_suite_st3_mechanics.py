"""Recurring ST-3 mechanics: 86 static ordinates and nine modal frequencies.

Two meshes belong to each comparison. Unreadable source ordinates stay in
the denominator, and the overlapping historical archive is a separate scope.
"""
from copy import deepcopy
from decimal import Decimal
import hashlib
import json
import math
import os
from pathlib import Path
import resource
import signal
import subprocess
import sys
import tempfile

SCOPE='st3-mechanics'
INPUTS='docs/validation/isae-st3-mechanics-inputs.json'
TARGETS='docs/validation/isae-st3-mechanics-targets.json'
EXECUTION_HELPERS=('verify_st3_static_curves_current.py','verify_st3_modal_current.py',
    'verify_sa14_defaults.py','isae_st3_curve_markers.py','isae_st3_static_reference.py',
    'isae_st3_reference.py','isae_suite_st3_modal.py','isae_acceptance.py',
    'verify-isae-st3-still-air-reference.py','isae_suite_extra_polars.py',
    'isae_suite_polars.py','isae_suite_sa15.py')
STATIC_CHECKS=('residual','force_balance','moment_balance','gravity_force','gravity_moment',
               'clamp_position','clamp_rotation')
MODAL_CHECKS=('fresh_residual','force_balance','moment_balance','independent_force','independent_moment',
              'clamp_position','clamp_rotation')

def read(path):return json.loads(Path(path).read_text())
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def save(path,value):Path(path).write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')
def require(value,message):
    if not value:raise ValueError('ST3 mechanics: '+message)
def finite(value):return isinstance(value,(int,float)) and not isinstance(value,bool) and math.isfinite(value)


def plan(root, *, comparison_scopes=()):
    require(list(comparison_scopes) in ([],[SCOPE]),'unknown or duplicated comparison scope')
    if not comparison_scopes:return []
    root=Path(root);data=read(root/INPUTS);targets=read(root/TARGETS)
    require(hashlib.sha256(json.dumps(targets,sort_keys=True).encode()).hexdigest()==data['targets_sha256'],
            'reference targets changed; source review required')
    for p,h in data['source_pins'].items():require(sha(root/p)==h,'source changed: '+p)
    sources=[dict(path=p,sha256=h,bytes=(root/p).stat().st_size) for p,h in data['source_pins'].items()]
    sources += [dict(path=p,sha256=sha(root/p),bytes=(root/p).stat().st_size) for p in (INPUTS,TARGETS)]
    jobs=[]
    for state in data['static_states']:
        rows=[r for r in targets['static_targets'] if r['state_key']==state['key']]
        observations=[dict(name=r['id'],expected=r['expected'],
            tolerance=r['original_absolute_tolerance'] if r['source_available'] else 0.,
            quantity=r['quantity'],kind='continuous',comparison='<=',source_available=r['source_available'],
            source=str(Path(data['static_sources'][state['name']]).parent/r['figure']),
            target=deepcopy(r)) for r in rows]
        jobs.append(dict(id='ST-3/mechanics/static/'+state['key'],configuration=state['name'],target_kind='static',
            model_path=data['static_sources'][state['name']],state=deepcopy(state),observations=observations))
    for layup in data['static_sources']:
        rows=[r for r in targets['modal_targets'] if r['layup']==layup]
        native=[deepcopy(j) for j in data['modal_jobs'] if j['layup']==layup]
        observations=[dict(r,name=r['id'],quantity='frequency_Hz',comparison='<=',source_available=True) for r in rows]
        jobs.append(dict(id='ST-3/mechanics/modal/'+layup,configuration=layup,target_kind='modal',
            model_path=native[0]['model_path'].replace('.reference/','reference/',1),
            native_jobs=native,observations=observations))
    for job in jobs:
        job.update(adapter='st3',case_id='ST-3',comparison_scope=SCOPE,execution_route='worker',
            expected_outputs=len(job['observations']),source_pins=deepcopy(sources),
            complete_family_reproduction=False,literal_input_modified=job['target_kind']=='static',
            qualifications=[data['basis'],data['qualification'],'Historical ST-3 scopes remain separate.'])
    require(len(jobs)==43 and sum(j['expected_outputs'] for j in jobs)==95,'declared scope changed')
    require(sum(not r['source_available'] for j in jobs for r in j['observations'])==2,'unavailable references changed')
    return jobs


def verify_reference_sources(root,job):
    expected=next((j for j in plan(root,comparison_scopes=[SCOPE]) if j['id']==job.get('id')),None)
    require(expected is not None and all(job.get(k)==v for k,v in expected.items()),'job differs from canonical setup')
    return True


def reference_contract(job):
    require(job.get('adapter')=='st3' and job.get('case_id')=='ST-3' and job.get('comparison_scope')==SCOPE,'wrong scope')
    rows=job['observations'];require(len(rows)==job['expected_outputs']==len({r['name'] for r in rows}),'missing targets')
    return {r['name']:r for r in rows}


def state_jobs(job):
    if job['target_kind']=='modal':return deepcopy(job['native_jobs'])
    return [dict(job['state'],panels=n) for n in (64,128)]


def static_value(state,row):
    target=row['target'];value=state['observable']['h_m' if target['quantity']=='Z' else 'twist_asw_deg']
    if target['kind']=='M' and (target['quantity']=='T' or target['name']!='0_3_90'):value=-value
    return value


def frequency_pair(states,index):return [s['frequencies'][index]['predicted'] for s in states]


def evidence(job,states,folder=None):
    rows=[]
    if job['target_kind']=='modal':
        import numpy as np
        from isae_st3_reference import MATERIALS,weighted_shapes,assurance
        shapes=[]
        for i in range(2):
            with np.load(folder/f'job-{i}'/'shapes.npz') as z:shapes.append({k:z[k] for k in z.files})
        matrix=assurance(*[weighted_shapes(s['stations'],s['shapes'],MATERIALS[job['configuration']]['mass']) for s in shapes])
        mutual=bool(np.array_equal(np.argmax(matrix,axis=0),np.arange(3)) and np.array_equal(np.argmax(matrix,axis=1),np.arange(3)))
    for i,row in enumerate(job['observations']):
        pair=([static_value(s,row) for s in states] if job['target_kind']=='static' else frequency_pair(states,i))
        item=dict(name=row['name'],predictions=pair,absolute_change=abs(pair[1]-pair[0]))
        if job['target_kind']=='static':item['gate']=max(1e-9 if row['quantity']=='Z' else 1e-7,.001*abs(pair[1]))
        else:item.update(gate=.001*abs(pair[1]),shape_MAC=float(matrix[i,i]),mutual_shape_assignment=mutual)
        rows.append(item)
    return rows


def predicted(row,pair):
    return max(pair,key=lambda x:abs(x-row['expected'])) if row['source_available'] else None


def strict_pass(row,value):
    if value is None:return False
    if row['quantity']=='frequency_Hz':
        return abs(Decimal(str(value))-Decimal(row['exact_decimal_expected']))<=Decimal(row['exact_decimal_tolerance'])
    return abs(value-row['expected'])<=row['tolerance']


def numerical(job,states,mesh):
    names=STATIC_CHECKS if job['target_kind']=='static' else MODAL_CHECKS
    valid=all(set(s.get('checks',{}))==set(names) and all(finite(s['checks'].get(k)) and 0<=s['checks'][k]<1e-7 for k in names) for s in states)
    valid &= all(finite(m.get('absolute_change')) and 0<=m['absolute_change']<=m['gate'] for m in mesh)
    if job['target_kind']=='modal':
        valid &= all(s['checks']['fresh_residual']<1e-8 and len(s.get('pencil_audits',[]))==12
                     and len({a['index'] for a in s['pencil_audits']})==12
                     and all(finite(a.get(k)) and 0<=a[k]<1e-8 for a in s['pencil_audits'] for k in ('left','right','neutral_relative')) for s in states)
        valid &= all(m.get('mutual_shape_assignment') is True and finite(m.get('shape_MAC')) and .99<=m['shape_MAC']<=1+1e-12 for m in mesh)
    return bool(valid)


def validate_result_contract(job,result):
    contract=reference_contract(job)
    if result.get('status')!='computed':return True
    require(result.get('comparison_scope')==SCOPE and result.get('source_pins_unchanged') is True,'scope/provenance missing')
    checks=result.get('reference_checks',[]);states=result.get('states',[]);mesh=result.get('mesh_checks',[])
    require(len(checks)==len(contract) and {r.get('name') for r in checks}==set(contract),'missing or duplicate checks')
    require(len(states)==result.get('solver_calls')==2 and [s.get('job') for s in states]==state_jobs(job),'physical states changed')
    require(len(mesh)==len(checks),'missing mesh checks')
    if job['target_kind']=='modal':require(all(len(s.get('frequencies',[]))==3 for s in states),'missing modal roots')
    for i,(check,m) in enumerate(zip(checks,mesh,strict=True)):
        row=contract[check['name']]
        require(row==job['observations'][i] and all(check.get(k)==v for k,v in row.items()),'source target changed')
        pair=([static_value(s,row) for s in states] if job['target_kind']=='static' else frequency_pair(states,i))
        require(all(finite(x) for x in pair),'nonfinite physical prediction')
        gate=max(1e-9 if row['quantity']=='Z' else 1e-7,.001*abs(pair[1])) if job['target_kind']=='static' else .001*abs(pair[1])
        require(m.get('name')==row['name'] and m.get('predictions')==pair and m.get('absolute_change')==abs(pair[1]-pair[0]) and m.get('gate')==gate,'mesh evidence changed')
        require(check.get('predicted')==predicted(row,pair),'prediction detached from physical states or unavailable reference')
    require(result.get('numerical_pass') is numerical(job,states,mesh),'numerical pass differs from evidence')
    return True


def verify_artifacts(root,job,result):
    if result.get('status')!='computed':return []
    container=Path(result['artifact_root']);container=container if container.is_absolute() else Path(root)/container
    stages=[container] if (container/'adapter-result.json').is_file() else list(container.glob('st3-mechanics-*'))
    require(len(stages)==1,'missing or ambiguous physical artifacts')
    folder=stages[0];inner=read(folder/'plan.json');saved=read(folder/'adapter-result.json')
    require(inner['jobs']==state_jobs(job),'saved setup changed')
    for key in ('states','mesh_checks','reference_checks','numerical_pass','comparison_scope'):
        require(saved.get(key)==result.get(key),'saved adapter result changed: '+key)
    files=[folder/'plan.json',folder/'adapter-result.json'];static=job['target_kind']=='static'
    expected={'request.json','result.json'} if static else {'request.json','result.json','A.npz','M.npz','strict-result.json','accepted-result.json','shapes.npz'}
    for i,state in enumerate(result['states']):
        child=folder/(f'job-{i:02d}' if static else f'job-{i}')
        require(state['plan_sha256']==sha(folder/'plan.json') and read(child/'report.json')==state,'child report changed')
        require(set(state['artifacts'])==expected,'missing physical evidence')
        for name,digest in state['artifacts'].items():
            require(sha(child/name)==digest,'physical artifact changed: '+name);files.append(child/name)
        files.extend([child/'report.json',folder/f'child-{i}.json'])
        require(read(folder/f'child-{i}.json')['returncode']==0,'child did not exit successfully')
    return [dict(path=str(p.resolve()),bytes=p.stat().st_size,sha256=sha(p)) for p in files]


def run(root,job):
    require(all(os.environ.get(k)=='1' for k in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS')),'one BLAS thread required')
    resource.setrlimit(resource.RLIMIT_AS,(512*1024**2,512*1024**2));resource.setrlimit(resource.RLIMIT_CPU,(15,15));signal.alarm(75)
    root=Path(root);verify_reference_sources(root,job);data=read(root/INPUTS)
    folder=Path(tempfile.mkdtemp(prefix='st3-mechanics-'));static=job['target_kind']=='static'
    pins={p.relative_to(root).as_posix():sha(p) for p in sorted((root/'openswing').glob('*.py'))}
    pins.update({'scripts/'+p:sha(root/'scripts'/p) for p in (*EXECUTION_HELPERS,'isae_suite_st3_mechanics.py','run-isae-suite.py','summarize-isae-suite.py')})
    pins.update({p['path']:p['sha256'] for p in job['source_pins']})
    inner=dict(pins=pins,jobs=state_jobs(job),gates=data['modal_gates'])
    save(folder/'plan.json',inner);states=[]
    script='verify_st3_static_curves_current.py' if static else 'verify_st3_modal_current.py'
    for i in range(2):
        with (folder/f'child-{i}.stdout').open('w') as stdout,(folder/f'child-{i}.stderr').open('w') as stderr:
            try:
                child=subprocess.run([sys.executable,str(root/'scripts'/script),'run','--output',str(folder),'--index',str(i)],cwd=root,stdout=stdout,stderr=stderr,timeout=30)
                receipt=dict(returncode=child.returncode,terminal=True)
            except subprocess.TimeoutExpired:
                save(folder/f'child-{i}.json',dict(returncode=None,terminal=True,timeout=True));raise
        save(folder/f'child-{i}.json',receipt);require(child.returncode==0,f'state {i} failed; evidence at {folder}')
        path=folder/(f'job-{i:02d}' if static else f'job-{i}')/'report.json';state=read(path)
        require(state['plan_sha256']==sha(folder/'plan.json'),'child plan changed')
        for name,digest in state['artifacts'].items():require(sha(path.parent/name)==digest,'child artifact changed')
        states.append(state)
    mesh=evidence(job,states,folder);checks=[]
    for row,m in zip(job['observations'],mesh,strict=True):
        value=predicted(row,m['predictions']);checks.append(dict(row,predicted=value,passed=strict_pass(row,value)))
    for p,h in pins.items():require(sha(root/p)==h,'source changed during solve: '+p)
    result=dict(status='computed',comparison_scope=SCOPE,numerical_pass=numerical(job,states,mesh),
        reference_checks=checks,states=states,mesh_checks=mesh,solver_calls=2,source_pins_unchanged=True,
        complete_family_reproduction=False,literal_input_modified=job['literal_input_modified'],
        qualifications=job['qualifications'],artifact_root=str(folder))
    validate_result_contract(job,result);save(folder/'adapter-result.json',result)
    return result


def mesh_diagnostics(jobs,results):
    return [dict(job_id=j['id'],status='CHECKED_WITHIN_JOB' if results.get(j['id'],{}).get('status')=='computed' else 'UNAVAILABLE',
                 checks=results.get(j['id'],{}).get('mesh_checks',[])) for j in jobs]
