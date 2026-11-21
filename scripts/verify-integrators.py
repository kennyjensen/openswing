"""Exact integrator factors, weak poles and rigid-body modes with source hashes."""
import hashlib,json,platform,sys
from dataclasses import asdict
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'tests')]
import numpy as np
import scipy
from scipy.linalg import block_diag
from scipy.optimize import linear_sum_assignment
from openswing.bridge import dispatch
from openswing.linear_dynamics import eigensystem,complex_data
from test_dynamic_constraints import body,feedback_setup

files=[Path(__file__),ROOT/'tests/test_dynamic_constraints.py',ROOT/'examples/guided-body.asw',
       *sorted((ROOT/'openswing').glob('*.py'))]
provenance=dict(versions=dict(python=platform.python_version(),numpy=np.__version__,scipy=scipy.__version__),
    source_sha256={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files})
cache=ROOT/'.reference/integrators-verification.json'
saved=json.loads(cache.read_text()) if cache.exists() else {}
cases=saved.get('cases',{}) if saved.get('provenance')==provenance else {}


def record(name,request,expected,zeros,kind='model'):
    if name in cases:print('Resumed '+name,flush=True);return
    if kind=='model':result=dispatch(request)
    else:
        modes,meta=eigensystem(np.array(request['A']),np.array(request['M']),
            time_scale=request['time_scale'],count=20)
        for mode in modes:
            for key in ('right','left'):mode[key]=complex_data(mode[key])
        result=dict(analysis='matrix_eigenmodes',modes=modes,diagnostics=meta,
                    matrices={key:request[key] for key in ('A','M')})
    values=np.array([complex(*mode['eigenvalue']) for mode in result['modes']])
    exact=[mode for mode in result['modes'] if mode['exact_integrator']]
    assert len(exact)==zeros and all(mode['eigenvalue']==[0.,0.] for mode in exact)
    assert result['diagnostics']['integrator_deflation']['count']==zeros
    assert len(values)==result['diagnostics']['finite_dimension']==len(expected)
    expected=np.asarray(expected,dtype=complex)
    rows,columns=linear_sum_assignment(abs(values[:,None]-expected[None,:]))
    error=float(max(abs(values[rows]-expected[columns]),default=0))
    assert error<3e-8
    for wanted in expected:
        if 0<abs(wanted)<1e-6:
            nearest=min(result['modes'],key=lambda mode:abs(complex(*mode['eigenvalue'])-wanted))
            assert not nearest['exact_integrator'] and abs(complex(*nearest['eigenvalue'])-wanted)<1e-10*abs(wanted)
    right=max(mode['right_backward_error'] for mode in result['modes'])
    left=max(mode['left_backward_error'] for mode in result['modes'])
    assert max(right,left)<1e-9
    comparison=dict(expected_roots=[[float(v.real),float(v.imag)] for v in expected],
        exact_zero_count=zeros,maximum_root_error=error,maximum_right_backward_error=right,
        maximum_left_backward_error=left)
    cases[name]=dict(kind=kind,request=request,result=result,comparison=comparison)
    tmp=cache.with_suffix('.tmp');tmp.write_text(json.dumps(dict(provenance=provenance,cases=cases),allow_nan=False));tmp.replace(cache)
    print(name+': '+json.dumps(comparison),flush=True)


chain=block_diag(np.array([[0,2,0],[0,0,-3],[0,0,0.]]),np.array([[-1,-2],[2,-1.]]),[[1e-10]],[[1.]])
mass=np.diag([1.,1.,1.,1.,1.,1.,0.])
rp=[4,2,6,0,5,1,3];cp=[1,6,3,5,0,2,4]
row=np.array([1e-4,7.,1e3,.3,90.,.02,2.]);column=np.array([3,.1,8,.03,2,7,.4])
for label,time in [('seconds',1.),('minutes',60.),('milliseconds',.001)]:
    a=(row[:,None]*chain*column)[np.ix_(rp,cp)]
    m=(row[:,None]*mass*column)[np.ix_(rp,cp)]/time
    record('chain_'+label,dict(A=a.tolist(),M=m.tolist(),time_scale=time),
        [0,0,0,(-1+2j)*time,(-1-2j)*time,1e-10*time],3,'matrix')
record('independent_integrators',dict(A=np.zeros((3,3)).tolist(),M=np.diag([2.,3.,4.]).tolist(),time_scale=1.),[0]*3,3,'matrix')

source=body().dumps()
record('prescribed_rest',dict(action='modes',source=source,panels=4,gravity=[0,0,0],
    condition=dict(speed=10,alpha=0,mach=0),modes=dict(frame='prescribed',count=20,vacuum=True,matrices=True)),[0]*12,12)
for name,spin,targets,expected,zeros,step in [
    ('gyro_y',[0,2,0],{'moment.x':0,'moment.z':0},[1/np.sqrt(2),-1/np.sqrt(2),2j,-2j],8,1e-5),
    ('gyro_z',[0,0,2],{'moment.x':0,'moment.y':0},[2j/np.sqrt(3),-2j/np.sqrt(3),2j,-2j,2j,-2j],6,1e-5),
    ('gyro_y_fine',[0,2,0],{'moment.x':0,'moment.z':0},[1/np.sqrt(2),-1/np.sqrt(2),2j,-2j],8,3e-6)]:
    request=dict(action='modes',source=source,panels=4,gravity=[0,0,0],condition=dict(speed=10,alpha=0,mach=0,rates=spin),
        modes=dict(frame='mixed',load_targets=targets,count=20,vacuum=True,matrices=True,step=step))
    record(name,request,[0]*zeros+expected,zeros)
m,c,options=feedback_setup();gravity=options.pop('gravity')
record('feedback',dict(action='modes',source=m.dumps(),condition=asdict(c),panels=4,gravity=gravity,
    modes=dict(options,count=20,matrices=True)),[0]*11+[-3.2],11)
assert len(cases)==9
artifact=dict(**provenance,cases=cases,limitations=[
    'Exact coordinate row/column factors only; a dense similarity transform can hide an integrator from this criterion.',
    'Algebraic multiplicity is retained but repeated right/left vectors do not construct generalized eigenvectors or a Jordan basis.',
    'Component verification against independent mechanics and prescribed matrices, not ASWING executable or aircraft/experimental validation.',
    'Rotating and accelerating models are frozen local linearizations; their spectra do not establish trajectory stability.'])
destination=ROOT/'docs/validation/integrators.json';destination.write_text(json.dumps(artifact,allow_nan=False)+'\n')
print(f'Wrote {destination.relative_to(ROOT)}: {len(cases)} cases, {len(provenance["source_sha256"])} hashes, {destination.stat().st_size} bytes',flush=True)
