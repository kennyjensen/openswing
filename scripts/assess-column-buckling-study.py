"""Saved-only independent pencil, mode-shape and refinement audit."""
import gc
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import resource

resource.setrlimit(resource.RLIMIT_AS,(512*1024**2,512*1024**2))
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'artifacts/isae/st6-column-supplement-20261103'
read=lambda p:json.loads(Path(p).read_text())
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
spec=importlib.util.spec_from_file_location('column_reference',ROOT/'scripts/verify-source-column-buckling.py')
reference=importlib.util.module_from_spec(spec);spec.loader.exec_module(reference)


def rotate_shape(load,count):
    """Direct derivative of the beam-column solution, divided by tip displacement."""
    s=np.linspace(0.,reference.L,count+1)
    if load==0:
        return (reference.L*s-s*s/2)/(reference.L**3/3-reference.L*(reference.L/count)**2/12)
    q=math.sqrt(load/reference.EI);step=2*math.atan(q*reference.L/(2*count))
    a=count*step;b=np.arange(count+1)*step
    return q*(math.cos(a)*(np.cos(b)-1)+math.sin(a)*np.sin(b))/(math.sin(a)-q*reference.L*math.cos(a))


plan=read(BASE/'plan.json');stream_plan=read(BASE/'streamed/plan.json')
for p,value in {**plan['pins'],**stream_plan['pins']}.items():assert sha(ROOT/p)==value,p
records={};pencil_count=0;shape_count=0;largest_pencil=0.;largest_shape=0.
for name,args in plan['jobs'].items():
    folder=(BASE/'streamed'/name) if name.startswith('n64-') else BASE/name
    report=read(folder/'report.json');job_plan=read(folder/'plan.json')
    assert report['status']=='PASS' and report['physical_checks_pass'] and report['source_pins_unchanged']
    if name!='n8-half':
        receipt=read(folder.parent/(name+'-execution.json'))
        assert receipt['exit_code']==0 and receipt['process_reaped'] and not receipt['timed_out']
        assert receipt['report_sha256']==sha(folder/'report.json')
    for p,value in job_plan['source_pins'].items():assert sha(ROOT/p)==value,p
    result=read(folder/'result.json');a=np.asarray(result['matrices']['A']);m=np.asarray(result['matrices']['M'])
    assert a.shape==m.shape and a.shape[0]==a.shape[1]
    anorm=np.linalg.norm(a);mnorm=np.linalg.norm(m);errors=[]
    load=job_plan['reference']['load'];count=args['intervals'];node_count=count+1
    assert result['base']['structural_nodes']==node_count and result['base']['structural_elements']==count
    assert abs(result['base']['mass_properties']['mass']-1.)<1e-12
    if args['method']=='dense':assert result['diagnostics']['finite_dimension']==2
    else:
        assert result['diagnostics']['finite_dimension'] is None
        assert result['diagnostics']['arnoldi']['factorizations']==1
    case_shape_error=0.
    for mode in result['modes']:
        lam=complex(*mode['eigenvalue'])
        for side in ('right','left'):
            v=np.asarray(mode[side]['real'])+1j*np.asarray(mode[side]['imag'])
            diff=a@v-lam*(m@v) if side=='right' else a.T@v-lam.conjugate()*(m.T@v)
            error=np.linalg.norm(diff)/((anorm+abs(lam)*mnorm)*np.linalg.norm(v))
            assert error<=1e-8,(name,side,error)
            errors.append(float(error));pencil_count+=1;largest_pencil=max(largest_pencil,float(error))
        displacement=np.array([np.asarray(n['displacement']['real'])+1j*np.asarray(n['displacement']['imag']) for n in mode['output']['nodes']])
        rotation=np.array([np.asarray(n['rotation']['real'])+1j*np.asarray(n['rotation']['imag']) for n in mode['output']['nodes']])
        scale=displacement[-1,2];assert abs(scale)>1e-15
        expected_d=np.zeros((node_count,3));expected_d[:,2]=reference.shape(load,count)
        expected_r=np.zeros((node_count,3));expected_r[:,0]=rotate_shape(load,count)
        error=max(float(np.max(abs(displacement/scale-expected_d))),float(np.max(abs(rotation/scale-expected_r))))
        assert error<=2e-7,(name,'all translation/rotation components',error)
        largest_shape=max(largest_shape,error);case_shape_error=max(case_shape_error,error);shape_count+=6*node_count
    poles=np.array([complex(*mode['eigenvalue']) for mode in result['modes']])
    continuum=abs(complex(-reference.stiffness(load))**.5)
    pole_magnitude=float(np.mean(abs(poles)))
    records[name]=dict(intervals=count,load=load,load_over_euler=load/reference.PCR,
        pole_magnitude=pole_magnitude,continuum_pole_magnitude=continuum,
        continuum_relative_error=abs(pole_magnitude-continuum)/continuum,
        poles=report['poles'],classifications=report['classifications'],
        independent_pencil_errors=errors,independent_full_shape_error=case_shape_error,
        solver_checks=report['checks'],seconds=report['seconds'],peak_RSS_KiB=report['peak_RSS_KiB'],
        pins={str((folder/p).relative_to(ROOT)):sha(folder/p) for p in ['plan.json','request.json','result.json','report.json','fresh-base.json','fresh-residual.json']})
    del result,a,m,displacement,rotation,poles;gc.collect()

refinement={}
for label,fine in [('zero',32),('half',32),('over',64)]:
    values=[records[f'n{n}-{label}'] for n in [8,16,32]+([64] if fine==64 else [])]
    pairs=[dict(coarse=a['intervals'],fine=b['intervals'],relative_change=abs(a['pole_magnitude']-b['pole_magnitude'])/b['pole_magnitude']) for a,b in zip(values[:-1],values[1:])]
    for p in pairs:p['passes']=p['relative_change']<=plan['gates']['fine_mesh_relative']
    assert pairs[-1]['passes'] and values[-1]['continuum_relative_error']<=plan['gates']['fine_continuum_relative']
    errors=[v['continuum_relative_error'] for v in values]
    assert all(b<a and .20<b/a<.30 for a,b in zip(errors[:-1],errors[1:]))
    refinement[label]=dict(pairs=pairs,fine_intervals=fine,fine_continuum_relative_error=errors[-1],error_ratios=[b/a for a,b in zip(errors[:-1],errors[1:])])

critical=[]
for n in (8,16,32,64):
    lower=records[f'n{n}-below-critical'];upper=records[f'n{n}-above-critical']
    assert 'unstable' not in lower['classifications'] and 'unstable' in upper['classifications']
    center=(lower['load']+upper['load'])/2;width=(upper['load']-lower['load'])/center
    assert width<=plan['gates']['critical_bracket_relative_width']
    critical.append(dict(intervals=n,lower=lower['load'],upper=upper['load'],center=center,
        relative_width=width,center_continuum_relative_error=(center/reference.PCR-1),
        worst_endpoint_continuum_relative_error=max(abs(lower['load']/reference.PCR-1),abs(upper['load']/reference.PCR-1))))
for a,b in zip(critical[:-1],critical[1:]):
    b['previous_mesh_relative_change']=abs(b['center']-a['center'])/b['center']
    b['mesh_pass']=b['previous_mesh_relative_change']<=plan['gates']['fine_mesh_relative']
assert critical[-1]['mesh_pass'] and critical[-1]['worst_endpoint_continuum_relative_error']<=plan['gates']['critical_continuum_relative']
summary=dict(status='PASS_ANALYTICAL_COLUMN_SUPPLEMENT',goal_complete=False,native_ASWING_validation=False,
    cases_pass=len(records),cases_total=len(plan['jobs']),records=records,refinement=refinement,
    critical_load_brackets=critical,continuum_critical_load=reference.PCR,
    independent_pencil_checks=pencil_count,maximum_independent_pencil_error=largest_pencil,
    independent_shape_components=shape_count,maximum_independent_shape_error=largest_shape,
    failed_attempt_retained=str((BASE/'n64-over/report.json').relative_to(ROOT)),
    io_only_retry_plan=str((BASE/'streamed/plan.json').relative_to(ROOT)),
    pins={str(p.relative_to(ROOT)):sha(p) for p in [Path(__file__),BASE/'plan.json',BASE/'streamed/plan.json']})
(BASE/'native-assessment.json').write_text(json.dumps(summary,indent=2,allow_nan=False)+'\n')
print(json.dumps({k:v for k,v in summary.items() if k not in ('records','refinement','critical_load_brackets','pins')}))
