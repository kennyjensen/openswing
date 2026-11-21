"""Rerunnable ST-1 mechanics scope: 201 displacement and 22 frequency targets.

Reference inputs are immutable; each suite plan pins the current solver. Mesh
refinements and unloaded baselines do not add reference comparison slots.
"""
from copy import deepcopy
import hashlib
import json
import math
import os
from pathlib import Path
import resource
import signal
import tempfile

SCOPE = 'st1-mechanics'
INPUTS = 'docs/validation/isae-st1-mechanics-inputs.json'
TARGETS = 'docs/validation/isae-st1-mechanics-scope.json'
STATIC_LIMITS = dict(residual=1e-8, force_balance=1e-7, moment_balance=1e-7,
                     independent_force=2e-10, independent_moment=2e-10,
                     clamp_position=1e-10, clamp_rotation=1e-10)
MODAL_LIMITS = dict(residual=1e-8, pencil=1e-8, real_fraction=1e-6)


def _read(path): return json.loads(Path(path).read_text())
def _sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def _save(path, data): Path(path).write_text(json.dumps(data, indent=2, allow_nan=False)+'\n')


def _require(condition, message):
    if not condition: raise ValueError('ST1 mechanics: '+message)


def _finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def reference_records(scope):
    return dict(static=[{k:r[k] for k in ('case','mass_kg','axis','expected_m','absolute_allowance_m','source_path','source_line')}
                        for r in scope['static_targets']],
                modal=[{k:r[k] for k in ('case','label','expected_Hz','source')} for r in scope['modal_targets']])


def plan(root):
    root=Path(root); data=_read(root/INPUTS); scope=_read(root/TARGETS)
    digest=hashlib.sha256(json.dumps(reference_records(scope),sort_keys=True).encode()).hexdigest()
    _require(digest==data['targets_sha256'], 'reference values changed; review their source before updating the manifest')
    for path,expected in data['source_pins'].items():
        _require(_sha(root/path)==expected, 'reference source changed: '+path)
    sources=[dict(path=path,sha256=digest) for path,digest in data['source_pins'].items()]
    sources += [dict(path=path,sha256=_sha(root/path)) for path in (INPUTS,TARGETS)]
    jobs=[]
    for kind,configs in [('static',data['static']),('modal',data['modal'])]:
        for case,config in configs.items():
            targets=[r for r in scope['static_targets' if kind=='static' else 'modal_targets'] if r['case']==case]
            masses=sorted({r['mass_kg'] for r in targets}) if kind=='static' else [None]
            for mass in masses:
                rows=[r for r in targets if kind=='modal' or r['mass_kg']==mass]
                observations=[dict(name=r['axis'] if kind=='static' else r['label'],
                    expected=r['expected_m'] if kind=='static' else r['expected_Hz'],
                    tolerance=r['absolute_allowance_m'] if kind=='static' else 0.,
                    comparison='<=',kind='continuous') for r in rows]
                name=f'ST-1/mechanics/{kind}/{case}'+(f'/mass-{mass:g}' if mass is not None else '')
                refine=kind=='modal' or mass==masses[-1]
                jobs.append(dict(id=name,adapter='st1',case_id='ST-1',comparison_scope=SCOPE,
                    target_kind=kind,configuration=case,config=deepcopy(config),mass=mass,
                    refine=refine,observations=observations,expected_outputs=len(observations),
                    source_pins=sources,execution_route='worker',nominals=[100,200] if kind=='static' else [40,80],
                    complete_family_reproduction=False,original_file_modified=True,
                    qualifications=[data['basis'],'Mesh repeats and unloaded states receive no additional votes.',
                        'Coupled 95 Hz identity and thin-down literal 218 Hz remain required and unresolved.']))
    _require(len(jobs)==72 and sum(j['expected_outputs'] for j in jobs)==223, 'complete mechanics scope changed')
    return jobs


def verify_reference_sources(root,job):
    expected=next((j for j in plan(root) if j['id']==job.get('id')),None)
    _require(expected is not None and all(job.get(k)==v for k,v in expected.items()), 'job differs from its canonical source/setup')
    return True


def reference_contract(job):
    _require(job.get('comparison_scope')==SCOPE and job.get('case_id')=='ST-1', 'wrong scope')
    rows=job['observations'];names=[r['name'] for r in rows]
    _require(len(names)==len(set(names))==job['expected_outputs'], 'missing or duplicate targets')
    return {r['name']:r for r in rows}


def derive(root,job,mass=None):
    c=job['config']; original=(Path(root)/c['source']).read_text();lines=original.splitlines(keepends=True)
    if job['target_kind']=='static':
        index=next(i for i,line in enumerate(lines) if line.strip()=='#  MASS')+1
        values=lines[index].split();_require(values[:5]==['1','-0.280','0.0','-0.280','0.0'], 'unexpected point mass')
        values[-1]=str(job['mass'] if mass is None else mass);lines[index]=' '.join(values)+'\n'
        index=next(i for i,line in enumerate(lines) if line.strip()=='# twist')+1
        lines[index]=c['transform']+'\n'
    header=next(i for i,line in enumerate(lines) if line.split()[:6]==['t','x','y','z','chord','Xax'])
    fields=lines[header].split();scales=lines[header+1].split()
    if c['trim_surplus']:
        _require(len(scales)==len(fields)+2,'unexpected surplus scale count')
        scales=scales[:-1]
    _require(len(scales)==len(fields)+1 and scales[0]=='*','unexpected named scale count')
    for name,value in c.get('scale_overrides',{}).items():scales[1+fields.index(name)]=str(value)
    lines[header+1]=' '.join(scales)+'\n'
    return ''.join(lines)+('End\n' if original.rstrip().endswith('\nEngine') else '')


def _bounded():
    _require(all(os.environ.get(k)=='1' for k in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS')),'one BLAS thread required')
    resource.setrlimit(resource.RLIMIT_AS,(512*1024**2,512*1024**2))
    resource.setrlimit(resource.RLIMIT_CPU,(15,15));signal.alarm(25)


def _static_state(root,job,mass,nominal,folder):
    import numpy as np
    from openswing.asw import parse_asw
    from openswing.bridge import dispatch
    source=derive(root,job,mass);folder.mkdir();(folder/'model.asw').write_text(source)
    model=parse_asw(source,beam_interpolation='drela-segspl-v1')
    _require(not model.diagnostics and len(model.beams)==1,'static input diagnostics')
    np.testing.assert_allclose(model.beams[0].value('mg',np.array([-.28,0.,.28])),job['config']['density']*9.81,rtol=2e-15,atol=0)
    request=dict(action='solve',mode='structural',source=source,
        panels=dict(default=nominal,beams={'1':dict(count=nominal,spacing='cosine')}),
        numerics=dict(beam_interpolation='drela-segspl-v1',structural_operator='drela-steady-section-v1'),
        gravity=[0.,0.,-9.81],loads=[],tolerance=1e-8,continuation_steps=4)
    _save(folder/'request.json',request);result=dispatch(request);_save(folder/'result.json',result)
    _require(result['converged'],'unconverged static state')
    nodes=sorted(result['nodes'],key=lambda n:n['t']);t=np.array([n['t'] for n in nodes]);r=np.array([n['position'] for n in nodes])
    _require(len(nodes)==nominal+2 and t[0]==-.28 and t[-1]==.28 and -.22 in t,'static mesh or sensor station changed')
    weights=np.zeros(len(t));half=job['config']['density']*np.diff(t)/2
    weights[:-1]+=half;weights[1:]+=half;weights[0]+=mass
    force=weights[:,None]*[0.,0.,-9.81];moment=np.cross(r,force).sum(axis=0)
    def relative(a,b):
        a,b=np.asarray(a),np.asarray(b)
        return float(np.max(abs(a-b))/(1+max(np.max(abs(a)),np.max(abs(b)))))
    checks=dict(residual=result['residual'],force_balance=relative(result['force_balance'],[0.,0.,0.]),
        moment_balance=relative(result['moment_balance'],[0.,0.,0.]),independent_force=relative(force.sum(axis=0),result['applied_force']),
        independent_moment=relative(moment,result['applied_moment']),clamp_position=float(np.max(abs(r[-1]-[0.,.28,0.]))),
        clamp_rotation=float(np.max(abs(np.asarray(nodes[-1]['rotation'])-np.eye(3)))))
    sensor=result['sensors'][0];_require(sensor['beam']==1 and sensor['t']==-.22,'sensor changed')
    np.testing.assert_allclose(sensor['anchor_position_body'],r[np.where(t==-.22)[0][0]],rtol=0,atol=1e-12)
    return dict(position=sensor['anchor_position_body'],checks=checks,nominal=nominal,mass=mass)


def classify(mode,base,c):
    import numpy as np
    t=np.array([n['t'] for n in base['nodes']]);q=np.array([n['rotation'] for n in base['nodes']]);parts=[]
    for name in ('displacement','rotation'):
        v=np.array([n[name]['real'] for n in mode['output']['nodes']])+1j*np.array([n[name]['imag'] for n in mode['output']['nodes']])
        parts.append(np.einsum('nji,nj->ni',q,v))
    u,r=parts;w=np.zeros(len(t));w[:-1]+=np.diff(t)/2;w[1:]+=np.diff(t)/2
    activity=dict(B=float(w@(c['mass']*abs(u[:,2])**2+c['icc']*abs(r[:,0])**2)),
        F=float(w@(c['mass']*abs(u[:,0])**2+c['inn']*abs(r[:,2])**2)),
        T=float(w@((c['icc']+c['inn'])*abs(r[:,1])**2)),A=float(w@(c['mass']*abs(u[:,1])**2)))
    total=sum(activity.values());_require(total>0,'zero modal activity')
    fractions={k:v/total for k,v in activity.items()};family=max(fractions,key=fractions.get)
    if fractions[family]<=.55:family='mixed'
    shape=r[:,1] if family=='T' else u[:,{'B':2,'F':0,'A':1}.get(family,2)]
    pivot=shape[np.argmax(abs(shape))];real=(shape*pivot.conjugate()/abs(pivot)).real
    active=real[abs(real)>1e-3*np.max(abs(real))]
    return dict(mode_index=mode['index'],frequency=mode['frequency'],family=family,
        activity_fractions=fractions,internal_zeros=int(np.sum(active[:-1]*active[1:]<0))),np.column_stack(parts)


def _modal_state(root,job,nominal,folder):
    import numpy as np
    from scipy.sparse import save_npz
    from openswing.asw import parse_asw
    from openswing.bridge import dispatch
    from openswing import linear_dynamics as dynamics
    c=job['config'];source=derive(root,job);folder.mkdir();(folder/'model.asw').write_text(source)
    model=parse_asw(source,beam_interpolation='drela-segspl-v1');_require(not model.diagnostics and len(model.beams)==1,'modal input diagnostics')
    for name,value in dict(**c['fields'],mg=c['mass']*9.81,mgcc=c['icc']*9.81,mgnn=c['inn']*9.81,twist=0.).items():
        np.testing.assert_allclose(model.beams[0].value(name,np.array([-.28,0.,.28])),value,rtol=2e-15,atol=0)
    _require(len(model.records['weight'])==1 and model.records['weight'][0][5]==0,'modal point load')
    request=dict(action='modes',mode='modes',source=source,condition=None,gravity=[0.,0.,-9.81],loads=[],
        panels=dict(default=nominal,beams={'1':dict(count=nominal,spacing='cosine')}),
        numerics=dict(beam_interpolation='drela-segspl-v1',structural_operator='drela-fixed-vacuum-v1'),
        modes=dict(frame='fixed',vacuum=True,count=12,shift=[-.01,0.],method='full_shift_invert',step=1e-5,
            matrices=False,rank_tolerance=1e-9,tolerance=1e-9,continuation_steps=4,position=[0.,0.,0.],attitude=[0.,0.,0.]))
    _save(folder/'request.json',request);original=dynamics.linearize;captured=[]
    def capture(system,*args,**kwargs):
        a,m=original(system,*args,**kwargs);captured.append((system,a,m));return a,m
    dynamics.linearize=capture
    try:raw=dispatch(request)
    finally:dynamics.linearize=original
    _save(folder/'result.json',raw);_require(len(captured)==1,'unexpected number of linearizations')
    system,a,m=captured[0];save_npz(folder/'A.npz',a);save_npz(folder/'M.npz',m)
    base=raw['base'];_require(raw['converged'] and base['converged'] and raw['vacuum'] and raw['frame_mode']=='fixed','modal convergence/frame')
    _require(base['gravity_body']==[0.,0.,-9.81] and system.network.ng==0 and len(base['nodes'])==nominal+1,'modal base setup')
    residual=max(base['residual'],float(np.max(abs(system.residual(np.zeros(system.size),np.zeros(system.size))))))
    errors=[];real=[];classified=[];fields={}
    for mode in raw['modes']:
        lam=complex(*mode['eigenvalue']);real.append(abs(lam.real)/max(1.,abs(lam.imag)))
        for side in ('right','left'):
            v=np.asarray(mode[side]['real'])+1j*np.asarray(mode[side]['imag'])
            av,mv=(a@v,m@v) if side=='right' else (v.conjugate()@a,v.conjugate()@m)
            errors.append(float(np.linalg.norm(av-lam*mv)/(np.linalg.norm(av)+abs(lam)*np.linalg.norm(mv))))
        if lam.imag>1e-6:
            row,field=classify(mode,base,c);classified.append(row);fields[row['mode_index']]=field
    selected={}
    for family,count in [('B',3),('T',1),('F',1 if job['configuration'].startswith('thin-') else 0)]:
        candidates=sorted((r for r in classified if r['family']==family),key=lambda r:r['frequency'])
        _require(len(candidates)>=count,'required mode family absent from survey')
        for rank,row in enumerate(candidates[:count],1):
            _require(row['internal_zeros']==rank-1 or family=='T' and c['allow_torsion_sign_change'],'unresolved modal shape identity')
            selected[f'{rank}{family}']=row
    return dict(t=np.array([n['t'] for n in base['nodes']]),fields=fields,selected=selected,
        checks=dict(residual=residual,pencil=max(errors),real_fraction=max(real)),pencil_equations=len(errors),nominal=nominal)


def validate_result_contract(job,result):
    contract=reference_contract(job);checks=result.get('reference_checks',[])
    _require(result.get('complete_family_reproduction') is False and result.get('source_pins_unchanged') is True,'missing scope/source qualification')
    _require(len(checks)==len(contract) and {r['name'] for r in checks}==set(contract),'incomplete reference comparisons')
    for row in checks:
        _require(all(row.get(k)==v for k,v in contract[row['name']].items()),'reference value/tolerance changed')
        if job['target_kind']=='modal':
            pair=result.get('modal_identification',{}).get(row['name'],{})
            _require(set(pair)=={'coarse','fine'},'missing modal identification')
            family=row['name'][-1]
            for state in pair.values():
                _require(state.get('family')==family and state.get('activity_fractions',{}).get(family,0)>.55,
                         'mode family differs from its shape evidence')
                _require(state.get('internal_zeros')==int(row['name'][0])-1 or
                         family=='T' and job['config']['allow_torsion_sign_change'],'mode shape ordering changed')
            coarse,fine=pair['coarse']['frequency'],pair['fine']['frequency']
            _require(_finite(coarse) and _finite(fine) and coarse>0 and fine>0,'invalid modal frequency')
            _require(row.get('coarse_Hz')==coarse and row.get('fine_Hz')==fine and
                     row.get('predicted')==max((coarse,fine),key=lambda v:abs(v-row['expected'])) and
                     row.get('assessment')=='worst_error_across_meshes','both mesh frequencies must satisfy the reference check')
    states=result.get('state_checks',[]);limits=STATIC_LIMITS if job['target_kind']=='static' else MODAL_LIMITS
    count=2 if job['target_kind']=='modal' else 1+(job['mass']!=0)+job['refine']
    _require(len(states)==count and result.get('solver_calls')==count,'incomplete physical states')
    valid=True
    for state in states:
        _require(set(state)==set(limits),'missing numerical gate')
        valid=valid and all(_finite(state[k]) and 0<=state[k]<limit for k,limit in limits.items())
    mesh=result.get('mesh_checks',[])
    if job['target_kind']=='modal':
        _require(len(mesh)==len(contract) and {r['name'] for r in mesh}==set(contract),'missing modal mesh/shape checks')
        for row in mesh:
            pair=result['modal_identification'][row['name']]
            expected_change=abs(pair['coarse']['frequency']/pair['fine']['frequency']-1)
            _require(row.get('relative_change')==expected_change,'modal mesh error differs from saved frequencies')
        valid=valid and all(_finite(r['relative_change']) and 0<=r['relative_change']<.01 and _finite(r['shape_MAC']) and .99<r['shape_MAC']<=1+1e-12 for r in mesh)
    else:
        _require(len(mesh)==int(job['refine']),'missing loaded mesh check')
        valid=valid and all(_finite(r['relative_change']) and 0<=r['relative_change']<.01 for r in mesh)
    _require(result.get('numerical_pass') is valid,'numerical pass claim differs from evidence')
    return True


def run(root,job):
    _bounded();verify_reference_sources(root,job)
    import gc
    import numpy as np
    folder=Path(tempfile.mkdtemp(prefix='st1-mechanics-'));states=[];mesh=[];modal_details={}
    if job['target_kind']=='static':
        base=_static_state(root,job,0.,100,folder/'unloaded');states.append(base['checks'])
        loaded=base if job['mass']==0 else _static_state(root,job,job['mass'],100,folder/'loaded')
        if loaded is not base:states.append(loaded['checks'])
        displacement=abs(np.asarray(loaded['position'])-base['position']);values=dict(zip('xyz',map(float,displacement)))
        if job['refine']:
            fine=_static_state(root,job,job['mass'],200,folder/'refined');states.append(fine['checks'])
            mesh.append(dict(relative_change=math.dist(fine['position'],loaded['position'])/max(1e-12,float(np.linalg.norm(displacement)))))
    else:
        coarse=_modal_state(root,job,40,folder/'coarse');gc.collect()
        fine=_modal_state(root,job,80,folder/'fine');states=[coarse['checks'],fine['checks']]
        t=coarse['t'];w=np.zeros(len(t));w[:-1]+=np.diff(t)/2;w[1:]+=np.diff(t)/2;c=job['config']
        inertia=np.array([c['mass']]*3+[c['icc'],c['icc']+c['inn'],c['inn']]);values={}
        for name in reference_contract(job):
            old,new=coarse['selected'][name],fine['selected'][name];field=fine['fields'][new['mode_index']]
            interpolated=np.column_stack([np.interp(t,fine['t'],field[:,j].real)+1j*np.interp(t,fine['t'],field[:,j].imag) for j in range(6)])
            u=(coarse['fields'][old['mode_index']]*np.sqrt(w[:,None]*inertia)).ravel()
            v=(interpolated*np.sqrt(w[:,None]*inertia)).ravel()
            mac=float(abs(np.vdot(u,v))**2/(np.vdot(u,u).real*np.vdot(v,v).real))
            mesh.append(dict(name=name,relative_change=abs(old['frequency']/new['frequency']-1),shape_MAC=mac))
            values[name]=new['frequency'];modal_details[name]=dict(coarse=old,fine=new)
    checks=[]
    for r in job['observations']:
        value=values[r['name']];extra={}
        if job['target_kind']=='modal':
            pair=modal_details[r['name']]
            coarse_value=pair['coarse']['frequency'];fine_value=pair['fine']['frequency']
            # One target vote must satisfy the reference allowance on both
            # meshes. Score the less favorable value, retaining both actuals.
            value=max((coarse_value,fine_value),key=lambda v:abs(v-r['expected']))
            extra=dict(coarse_Hz=coarse_value,fine_Hz=fine_value,assessment='worst_error_across_meshes')
        checks.append(dict(**r,**extra,predicted=value,passed=abs(value-r['expected'])<=r['tolerance']))
    for source in job['source_pins']:_require(_sha(Path(root)/source['path'])==source['sha256'],'source changed during solve')
    limits=STATIC_LIMITS if job['target_kind']=='static' else MODAL_LIMITS
    numerical=all(_finite(s[k]) and 0<=s[k]<limit for s in states for k,limit in limits.items()) and all(
        0<=r['relative_change']<.01 and ('shape_MAC' not in r or .99<r['shape_MAC']<=1+1e-12) for r in mesh)
    result=dict(status='computed',numerical_pass=numerical,reference_checks=checks,state_checks=states,mesh_checks=mesh,
        solver_calls=len(states),source_pins_unchanged=True,complete_family_reproduction=False,
        comparison_scope=SCOPE,artifact_root=str(folder),modal_identification=modal_details,
        peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,qualifications=job['qualifications'])
    validate_result_contract(job,result);_save(folder/'adapter-result.json',result);return result


def mesh_diagnostics(jobs,results):
    return [dict(job_id=j['id'],status='CHECKED_WITHIN_JOB' if results.get(j['id'],{}).get('status')=='computed' else 'UNAVAILABLE',
                 checks=results.get(j['id'],{}).get('mesh_checks',[])) for j in jobs if j.get('comparison_scope')==SCOPE]
