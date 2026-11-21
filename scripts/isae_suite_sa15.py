"""Explicit SA-15 reconstruction; does not decode or replace historical .set.

The optional scope retains every original polar cell on both declared meshes.
Native printed comparisons remain strict here; the runner applies its separate
reference allowance only after validating numerical and source contracts.
"""
from copy import deepcopy
import hashlib
import math
from pathlib import Path
import time

from scripts import isae_suite_polars as polar

SCOPE='sa15-declared-setup'
PREFIX='SA-15:declared:'
ROUTE='sa15_rigid_coefficients'
OUTPUTS=('CD','CY','CL','Cl','Cm','Cn','efficiency')
GATES=dict(residual=1e-8,normalization=2e-10)
# Two literal rows, followed by the parser's documented zero defaults for
# the absent acceleration and rotation reference locations.
REFERENCE=[[3.026,.484,6.667],[1.049,0.,0.],[0.,0.,0.],[0.,0.,0.]]
METRICS=('force','moment','CD','CY','CL','Cl','Cm','Cn','drag_decomposition')
QUALIFICATIONS=[
 'Optional declared reconstruction; the original blocked registration is retained separately.',
 'The original .set is an undecoded version/build-dependent memory dump; no historical startup or coefficient-selector identity is claimed.',
 'Literal original model and driver incidence tokens are retained; no airfoil, geometry or control parameter is fitted.',
 '380 ft/s, literal sea-level density, zero controls/beta, Mach0, current influences and existing stall/core defaults are explicit choices.',
 'Drela spline interpolation and nominal64/128 cosine intervals are declared; historical nodes and circulation representation are unknown.',
 'Conventional stability axes, moments about Reference row2, near-field total CD and Trefftz span efficiency are declared output mappings.',
 'All seven original columns, including small lateral residuals, remain required. Mesh repeats add no independent native targets.',
 'No whole-family reproduction is established by scalar agreement.']


def require(ok,message):
    if not ok:raise ValueError('SA15 '+message)


def identifies(job):
    return (job.get('comparison_scope')==SCOPE or job.get('execution_route')==ROUTE
            or job.get('id','').startswith(PREFIX))


def plan(root):
    # Lazy import avoids a cycle when the owning extra_polars adapter calls us.
    import json
    from scripts import isae_suite_extra_polars as extra
    root=Path(root).resolve();cache=root/'.reference/isae-validation'
    manifest_path=cache/'manifest.json';raw=manifest_path.read_bytes()
    require(hashlib.sha256(raw).hexdigest()==extra.MANIFEST_SHA256,'original manifest changed')
    manifest=json.loads(raw);require(manifest['revision']==polar.REVISION,'revision changed')
    folders=list((cache/polar.REVISION/'1 - Aerodynamics/SA - Steady Aerodynamics Cases').glob('SA - 15 - *'))
    require(len(folders)==1,'ambiguous original family')
    folder=folders[0];model=folder/'JW-1_FW_Only_Body.asw';driver=folder/'JW-1_FW_Only_Body.sh'
    output='JW1_FW_Only_Body_Aswing_simulations/JW1_FW_Only_Body_CL_alpha.txt';table=folder/output
    paths=[model,table,driver,folder/'JW-1_FW_Only_Body.set']
    sources=[polar._pin(p,root) for p in paths]
    for p,s in zip(paths,sources,strict=True):
        original=manifest['files'][p.relative_to(cache/polar.REVISION).as_posix()]
        require(all(s[k]==original[k] for k in ('sha256','bytes')),'original source changed')
    sources += [polar._pin(p,root) for p in [manifest_path,root/'scripts/isae_suite_sa15.py',
                  root/'scripts/isae_suite_extra_polars.py',root/'scripts/isae_suite_polars.py']]
    rows=extra.decode_table(table.read_text(),15);declaration=extra.decode_driver(driver.read_text(),output)
    require(len(rows)==len(declaration['alpha_tokens'])==13 and declaration['speed']==380.,'driver row/speed scope changed')
    require(declaration['model_file']==model.name and declaration['requested_nodes'] is None,'model/node declaration changed')
    require(declaration['scalar_commands']==['!V 380']+['!A '+a for a in declaration['alpha_tokens']], 'unreviewed driver controls')
    rho,token=polar._rho_sl(model.read_text());require(rho==.002378,'literal density changed')
    kernels=[polar._pin(p,root) for p in sorted((root/'openswing').glob('*.py'))]
    jobs=[]
    for row,angle in zip(rows,declaration['alpha_tokens'],strict=True):
        index=row['row_index'];ref=row['fields']['alpha']
        require(abs(float(angle)-ref['value'])<=ref['tolerance'],'driver/table incidence mismatch')
        for level,n in enumerate((64,128)):
            settings=dict(panels=n,mesh_level=level,alpha=float(angle),alpha_token=angle,
                speed=380.,density=rho,density_token=token,mach=0.,beta=0.,controls={},
                freeze_influences=False,stall=True,stall_factor=40.,stall_width=.05,wake_core_ratio=.25,
                aero_lag=True,body_added_mass_factor=1.,beam_interpolation='drela-segspl-v1',circulation_method='auto')
            jobs.append(dict(id=f'{PREFIX}row{index+1:03d}:n{n}',case_id='SA-15',adapter='extra_polars',
                comparison_scope=SCOPE,execution_route=ROUTE,target_kind='declared_rigid_polar',
                model_path=sources[0]['path'],table_path=sources[1]['path'],driver_path=sources[2]['path'],
                row_index=index,reference_row=deepcopy(row),required_outputs=list(OUTPUTS),expected_outputs=7,
                settings=settings,sources=deepcopy(sources),kernel_pins=deepcopy(kernels),
                numerical_gates=deepcopy(GATES),qualifications=list(QUALIFICATIONS),
                original_set_decoded=False,historical_settings_recovered=False,complete_family_reproduction=False,
                expected_operations=dict(cold_rigid_solves=1,retries=0),
                source_node_request=None,existing_native_targets_reused=True))
    return jobs


def reference_contract(job):
    require(job.get('case_id')=='SA-15' and job.get('adapter')=='extra_polars' and
        job.get('comparison_scope')==SCOPE and job.get('execution_route')==ROUTE and
        job.get('target_kind')=='declared_rigid_polar','scope identity changed')
    s=job['settings'];i=job['row_index']
    require(type(i) is int and 0<=i<13 and s['panels'] in (64,128) and
        job['id']==f'{PREFIX}row{i+1:03d}:n{s["panels"]}', 'row/mesh identity changed')
    require(job.get('required_outputs')==list(OUTPUTS) and job.get('expected_outputs')==7,
            'required outputs changed')
    require(job.get('numerical_gates')==GATES and job.get('expected_operations')==dict(cold_rigid_solves=1,retries=0),
            'physical gates or operation scope changed')
    require(job.get('original_set_decoded') is False and job.get('historical_settings_recovered') is False
        and job.get('complete_family_reproduction') is False and job.get('qualifications')==QUALIFICATIONS,
        'historical qualifications changed')
    return {name:dict(expected=job['reference_row']['fields'][name]['value'],
                     tolerance=job['reference_row']['fields'][name]['tolerance'],comparison='<=') for name in OUTPUTS}


def verify_reference_sources(root,job):
    reference_contract(job)
    original=next((j for j in plan(root) if j['id']==job['id']),None)
    require(original is not None and all(job.get(k)==v for k,v in original.items()),'job differs from original sources or declared setup')
    return True


def finite(x):return isinstance(x,(int,float)) and not isinstance(x,bool) and math.isfinite(x)


def validate_result_contract(job,result):
    contract=reference_contract(job)
    for key in ('id','case_id','adapter','comparison_scope','settings','qualifications','original_set_decoded','historical_settings_recovered'):
        require(result.get(key)==job.get(key),'saved identity or qualification changed: '+key)
    checks=result.get('reference_checks',[])
    require([c.get('name') for c in checks]==list(OUTPUTS),'missing/duplicate/reordered outputs')
    for c in checks:
        require(all(c.get(k)==v for k,v in contract[c['name']].items()),'native reference interval changed')
    if result.get('status')=='computed':
        require(result.get('numerical_pass') is True and result.get('sources_unchanged') is True
            and result.get('kernel_pins_unchanged') is True and result.get('original_model_modified') is False,
            'computed source or physics qualification missing')
        require(result.get('operations')==job['expected_operations'],'operation count changed')
        metrics=result.get('metrics',{})
        require(set(metrics)==set(METRICS)|{'residual'},'physical metrics incomplete')
        require(all(finite(x) and 0<=x<=GATES['residual' if k=='residual' else 'normalization'] for k,x in metrics.items()),
                'physical metric exceeds unchanged gate')
        flags=result.get('numerical_checks',[])
        require([c.get('name') for c in flags]==['parser','converged']+list(metrics)
                and all(c.get('passed') is True for c in flags),'missing physical checks')
        for c in flags[2:]:
            require(c.get('value')==metrics[c['name']] and c.get('tolerance')==GATES['residual' if c['name']=='residual' else 'normalization'],
                    'physical metric/check differs')
        require(all(finite(c.get('predicted')) and c['predicted']==result['predicted'][c['name']]
            and c.get('passed')==(abs(c['predicted']-c['expected'])<=c['tolerance']) for c in checks),
            'saved output or strict comparison changed')
        physical=result.get('physical',{})
        require(physical.get('reference')==REFERENCE,'literal reference normalization changed')
        for key in ('force','moment'):
            require(isinstance(physical.get(key),list) and len(physical[key])==3 and
                    all(finite(v) for v in physical[key]),'saved wrench missing')
        s=job['settings'];a=math.radians(s['alpha']);c,sn=math.cos(a),math.sin(a)
        area,chord,span=REFERENCE[0];qS=.5*s['density']*s['speed']**2*area
        x,y,z=physical['force'];mx,my,mz=physical['moment']
        values=dict(CD=(c*x+sn*z)/qS,CY=y/qS,CL=(-sn*x+c*z)/qS,
                    Cl=(-c*mx-sn*mz)/(qS*span),Cm=my/(qS*chord),Cn=(sn*mx-c*mz)/(qS*span))
        require(all(abs(v-result['predicted'][k])<=GATES['normalization'] for k,v in values.items()),
                'saved coefficients disagree with the full wrench')
        require(all(finite(physical.get(k)) for k in ('CLi','CYi','CDi')) and physical['CDi']>0,
                'Trefftz normalization missing')
        eff=(physical['CLi']**2+physical['CYi']**2)/(math.pi*span**2/area*physical['CDi'])
        require(abs(eff-result['predicted']['efficiency'])<=GATES['normalization'],
                'saved span efficiency differs from declared Trefftz normalization')
    return True


def run(root,job):
    root=Path(root).resolve();verify_reference_sources(root,job);start=time.monotonic()
    report={k:deepcopy(job[k]) for k in ('id','case_id','adapter','comparison_scope','settings','qualifications','original_set_decoded','historical_settings_recovered')}
    report.update(status='error',numerical_pass=False,reference_match=False,original_model_modified=False,
        operations=dict(cold_rigid_solves=0,retries=0),numerical_checks=[],
        reference_checks=[dict(name=k,**v,predicted=None,passed=False) for k,v in reference_contract(job).items()])
    try:
        import numpy as np
        from openswing.asw import parse_asw
        from openswing.aero import FlightCondition,solve_rigid
        s=job['settings'];model=parse_asw((root/job['model_path']).read_text(),beam_interpolation=s['beam_interpolation'])
        require(model.reference.tolist()==REFERENCE,'literal reference changed')
        keys=('alpha','speed','density','mach','beta','controls','freeze_influences','stall','stall_factor','stall_width','wake_core_ratio','aero_lag','body_added_mass_factor')
        condition=FlightCondition(**{k:s[k] for k in keys})
        report['operations']['cold_rigid_solves']=1
        r=solve_rigid(model,condition,panels=s['panels'],circulation_method=s['circulation_method'])
        force,moment,counts=polar.reconstructed_wrench(model,r)
        area,chord,span=model.reference[0];qS=.5*s['density']*s['speed']**2*area
        a=math.radians(s['alpha']);c,sn=math.cos(a),math.sin(a)
        predicted=dict(CD=r['CD'],CY=r['CY'],CL=r['CL'],Cl=c*r['Cl']+sn*r['Cn'],Cm=r['Cm'],
                       Cn=-sn*r['Cl']+c*r['Cn'],efficiency=r['efficiency'])
        x,y,z=force;mx,my,mz=moment
        expected=dict(CD=(c*x+sn*z)/qS,CY=y/qS,CL=(-sn*x+c*z)/qS,
                      Cl=(-c*mx-sn*mz)/(qS*span),Cm=my/(qS*chord),Cn=(sn*mx-c*mz)/(qS*span))
        metrics=dict(force=float(np.max(abs(force-r['force']))/qS),moment=float(np.max(abs(moment-r['moment']))/(qS*chord)),
            **{k:float(abs(v-predicted[k])) for k,v in expected.items()},
            drag_decomposition=abs(r['CD']-sum(r[k] for k in ('CDi_near','CDp','CDbody','CDam','CDeng','CDrate'))),
            residual=float(r['residual']))
        flags=[dict(name='parser',passed=not model.diagnostics),dict(name='converged',passed=bool(r['converged']))]
        for name,value in metrics.items():
            gate=GATES['residual' if name=='residual' else 'normalization']
            flags.append(dict(name=name,value=value,tolerance=gate,passed=bool(finite(value) and 0<=value<=gate)))
        valid=all(c['passed'] for c in flags) and all(finite(v) for v in predicted.values())
        for check in report['reference_checks']:
            check['predicted']=float(predicted[check['name']]);check['abs_error']=abs(check['predicted']-check['expected'])
            check['passed']=check['abs_error']<=check['tolerance']
        report.update(status='computed' if valid else 'numerical_failure',numerical_pass=valid,
            numerical_checks=flags,metrics=metrics,predicted=predicted,
            reference_match=valid and all(c['passed'] for c in report['reference_checks']),
            physical=dict(panels=r['panels'],force=r['force'],moment=r['moment'],moment_origin=r['moment_origin'],
                reference=model.reference.tolist(),wrench_component_counts=counts,
                CDi=r['CDi'],CLi=r['CLi'],CYi=r['CYi'],CDi_near=r['CDi_near'],CDp=r['CDp'],
                coefficient_definitions=r['coefficient_definitions'],circulation_solver=r.get('circulation_solver')))
    except Exception as exc:
        report.update(status='error',numerical_pass=False,reference_match=False,error=type(exc).__name__+': '+str(exc))
    report['sources_unchanged']=all(polar._pin(root/p['path'],root)==p for p in job['sources'])
    report['kernel_pins_unchanged']=all(polar._pin(root/p['path'],root)==p for p in job['kernel_pins'])
    if not report['sources_unchanged'] or not report['kernel_pins_unchanged']:
        report.update(status='source_mismatch',numerical_pass=False,reference_match=False)
    report['seconds']=time.monotonic()-start
    validate_result_contract(job,report)
    return report
