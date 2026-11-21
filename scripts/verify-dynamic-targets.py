"""Source-keyed studies of mixed continuous dynamics and harmonic frame inputs."""
import hashlib,json,platform,sys
from dataclasses import asdict
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'tests')]
import numpy as np
import scipy
from openswing.bridge import dispatch
from test_dynamic_constraints import body,offset_request,compare_offset,feedback_setup,z,prescribed_request,compare_prescribed,test_six_mixed_inputs_recover_force_inertia_kinematics_and_reactions

files=[Path(__file__),ROOT/'tests/test_dynamic_constraints.py',ROOT/'tests/rigid_frame_reference.py',
       ROOT/'examples/guided-body.asw',*sorted((ROOT/'openswing').glob('*.py'))]
provenance=dict(versions=dict(python=platform.python_version(),numpy=np.__version__,scipy=scipy.__version__),
    source_sha256={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files})
cache=ROOT/'.reference/dynamic-targets-verification.json'
saved=json.loads(cache.read_text()) if cache.exists() else {}
cases=saved.get('cases',{}) if saved.get('provenance')==provenance else {}


def record(name,request,check):
    if name in cases:print('Resumed '+name,flush=True);return
    result=dispatch(request);comparison=check(result)
    cases[name]=dict(request=request,result=result,comparison=comparison)
    tmp=cache.with_suffix('.tmp');tmp.write_text(json.dumps(dict(provenance=provenance,cases=cases),allow_nan=False));tmp.replace(cache)
    print(name+': '+json.dumps(comparison),flush=True)


def simple_check(result):
    test_six_mixed_inputs_recover_force_inertia_kinematics_and_reactions(result)
    return dict(inputs=6,dc_gap=not result['samples'][0]['converged'],
        maximum_backward_error=max(max(s['diagnostics']['backward_errors']) for s in result['samples'] if s['converged']))


source=body().dumps()
record('six_inputs',dict(action='frequency',source=source,panels=4,gravity=[0,0,0],condition=dict(speed=10,alpha=0,mach=0),
    frequency=dict(frame='mixed',load_targets={'force.x':0,'moment.z':0},frequencies=[0,.7,3.],matrices=True,
    inputs=['target.force.x','acceleration.y','acceleration.z','angular_acceleration.x','angular_acceleration.y','target.moment.z'])),simple_check)
record('prescribed',prescribed_request(),lambda result:dict(maximum_velocity_error=compare_prescribed(result),inputs=6))
for step in [1e-5,3e-6]:
    record('offsets_'+str(step),offset_request(step),lambda result:dict(maximum_state_error=compare_offset(result)))

def gyro_check(result,expected):
    values=np.array([complex(*m['eigenvalue']) for m in result['modes']])
    error=float(max(min(abs(values-expected)),min(abs(values+expected))))
    assert error<1e-7 and result['diagnostics']['finite_dimension']==12
    neutral=values[abs(values)<.1]
    return dict(expected_pair=[[expected.real,expected.imag],[-expected.real,-expected.imag]],maximum_root_error=error,
        near_zero_roots=len(neutral),maximum_near_zero_magnitude=float(max(abs(neutral),default=0)),
        note='Defective kinematic zero roots can split numerically; individual small growth rates are not established physical instability.')

for name,spin,targets,expected in [('gyro_z',[0,0,2],{'moment.x':0,'moment.y':0},2j/np.sqrt(3)),
                                  ('gyro_y',[0,2,0],{'moment.x':0,'moment.z':0},complex(2/np.sqrt(8)))]:
    request=dict(action='modes',source=source,panels=4,gravity=[0,0,0],condition=dict(speed=10,alpha=0,mach=0,rates=spin),
        modes=dict(frame='mixed',load_targets=targets,count=20,vacuum=True,matrices=True))
    record(name,request,lambda result:gyro_check(result,expected))

m,c,options=feedback_setup();gravity=options.pop('gravity')
base=dict(source=m.dumps(),condition=asdict(c),panels=4,gravity=gravity)

def feedback_check(result):
    error=0.
    for sample in result['samples']:
        s=1j*sample['omega']
        for j,response in enumerate(sample['responses']):
            expected=(1 if j==0 else 3)/(s+3.2)
            error=max(error,abs(z(response['output']['frame']['velocity_origin_body'])[0]+expected))
    assert error<3e-8
    return dict(maximum_velocity_transfer_error=float(error),expected_speed_pole=-3.2)

record('feedback',dict(base,action='frequency',frequency=dict(options,frequencies=[.7,3.],inputs=['target.force.x','command.V'])),feedback_check)

def rom_check(result):
    error=0.
    for sample in result['samples']:
        s=1j*sample['omega'];expected=np.array([[1/(s+3.2)],[-s/(s+3.2)]])
        error=max(error,float(np.max(abs(z(sample['full'])-expected))),float(np.max(abs(z(sample['reduced'])-expected))))
    assert result['diagnostics']['dimension']==1 and error<5e-8
    assert result.get('legacy_export') and not result.get('legacy_export_error')
    return dict(maximum_transfer_error=error,dimension=1,legacy_export=True)

record('rom',dict(base,action='rom',rom=dict(options,count=1,shift=[-3.2,0],inputs=['target.force.x'],outputs=['V','Ax'],frequencies=[.7,3.])),rom_check)
assert len(cases)==8
artifact=dict(**provenance,cases=cases,limitations=[
    'Independent rigid-body, controller and reduced-model component checks; not ASWING executable or experimental validation.',
    'Nonstationary operating points use frozen coefficients; a harmonic particular solution does not establish trajectory stability.',
    'General inverse dynamic constraints and generalized/defective mode ROMs remain pending.'])
destination=ROOT/'docs/validation/dynamic-targets.json';destination.write_text(json.dumps(artifact,allow_nan=False)+'\n')
print(f'Wrote {destination.relative_to(ROOT)}: {len(cases)} cases, {len(provenance["source_sha256"])} hashes, {destination.stat().st_size} bytes',flush=True)
