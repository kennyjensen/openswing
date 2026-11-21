"""Independent finite-duration forcing and mixed frame-load verification."""
import hashlib,json,platform,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
import scipy
from scipy.linalg import expm
from openswing.asw import parse_asw
from openswing.bridge import dispatch
from openswing.time_state import checkpoint,resume_time

files=[Path(__file__),Path('examples/guided-body.asw'),Path('examples/instrumented-oscillator.asw'),*sorted(Path('openswing').glob('*.py'))]
provenance=dict(versions=dict(python=platform.python_version(),numpy=np.__version__,scipy=scipy.__version__),
    source_sha256={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in files})
cache_path=Path('.reference/time-targets-verification.json')
saved=json.loads(cache_path.read_text()) if cache_path.exists() else {}
cases=saved.get('cases',{}) if saved.get('provenance')==provenance else {}


def record(name,compute):
    if name in cases:print('Resumed '+name,flush=True);return cases[name]
    result=compute();cases[name]=result
    tmp=cache_path.with_suffix('.tmp');tmp.write_text(json.dumps(dict(provenance=provenance,cases=cases),allow_nan=False));tmp.replace(cache_path)
    print(name+': '+json.dumps(result['comparison']),flush=True);return result


def pulse(channel,dt):
    tau=.113;duration=.21;target='force.x' if channel=='Fx' else 'moment.z'
    request=dict(action='time',source=Path('examples/guided-body.asw').read_text(),panels=4,gravity=[0,0,0],
        condition=dict(speed=10,alpha=0,mach=0),time=dict(frame='mixed',load_targets={target:0},duration=duration,dt=dt,
        forcing=f'time {channel}\n0 0\n{tau} {tau}'))
    out=dispatch(request);rate_error=pose_error=0.;factor=-.5 if channel=='Fx' else -.125
    event=next(i for i,s in enumerate(out['snapshots']) if s['time']==tau)
    assert out['snapshots'][event]['forcing_side']=='left' and out['snapshots'][event+1]['order']==1
    for s in out['snapshots']:
        t=s['time'];v=factor*min(t,tau)**2;x=factor*(t**3/3 if t<=tau else tau**2*t-2*tau**3/3)
        f=s['frame']
        if channel=='Fx':rate=f['velocity_origin_body'][0]+10;pose=f['position_earth'][0]+10*t
        else:
            R=np.array(f['body_to_earth']);rate=f['rates_body'][2];pose=np.arctan2(R[1,0],R[0,0])
        rate_error=max(rate_error,abs(rate-v));pose_error=max(pose_error,abs(pose-x))
        assert abs(s['operating_constraints'][0]['actual']-(t if t<=tau else 0))<1e-7
    return dict(request=request,trajectory=out,comparison=dict(rate_error=rate_error,pose_error=pose_error,cutoff=tau))


def controller_release(dt):
    tau=.063;duration=.143
    # Command Ay is selected by the controller; it does not prescribe frame Ay.
    # Engine bias 5 plus relative increment 1 plus command Ay=2 gives 8 N.
    control=dict(outputs=[dict(actuator='E1',expression="command('E1')+command('Ay')")])
    request=dict(action='time',source=Path('examples/instrumented-oscillator.asw').read_text(),panels=4,gravity=[0,0,0],
        condition=dict(speed=10,alpha=0,mach=0,powers={1:5}),
        time=dict(duration=duration,dt=dt,controller=control,forcing=f'time +E1 Ay\n0 1 2\n{tau} 1 2'))
    out=dispatch(request);A=np.array([[0,1],[-250,-5.]])
    error=np.zeros(2)
    for s in out['snapshots']:
        exact=expm(A*max(0,s['time']-tau))@np.array([.016,0])
        actual=np.array([s['nodes'][-1]['position'][1]-2,s['local_velocity'][-1][1]])
        error=np.maximum(error,abs(actual-exact))
        assert abs(s['feedback']['actuators']['E1']-(8 if s['time']<=tau else 0))<1e-8
        assert abs(s['frame']['acceleration_reference_body'][1])<1e-12
    return dict(request=request,trajectory=out,comparison=dict(displacement_error=float(error[0]),velocity_error=float(error[1]),cutoff=tau))


def mixed_offsets():
    m=parse_asw(Path('examples/guided-body.asw').read_text());m.reference[1:]=[[.7,.1,-.2],[.3,-.2,.4],[-.4,.2,.1]]
    targets={'force.x':.4,'force.z':-.7,'moment.y':.2}
    request=dict(action='time',source=m.dumps(),panels=4,gravity=[0,0,0],
        condition=dict(speed=10,alpha=0,mach=0,rates=[.2,-.3,.4],acceleration=[0,.7,0],angular_acceleration=[.1,0,-.2]),
        loads=[dict(beam=1,t=0,force=[1,2,3],moment=[.2,-.1,.3])],
        time=dict(frame='mixed',load_targets=targets,duration=.08,dt=.02,forcing='time Fx My\n0 .4 .2\n.04 .8 -.1'))
    out=dispatch(request);I=np.diag([2.,3.,4.]);rm=m.reference[1];ra=m.reference[2];error=0.
    for s in out['snapshots']:
        f=s['frame'];omega=np.array(f['rates_body'])
        specified=np.array([s['forcing_values']['Fx'],-.7,s['forcing_values']['My']])
        def wrench(x):
            acceleration=np.array([x[0],.7,x[1]]);angular=np.array([.1,x[2],-.2])
            acg=acceleration+np.cross(angular,-ra)+np.cross(omega,np.cross(omega,-ra))
            F=np.array([1,2,3])-acg
            M=np.array([.2,-.1,.3])-I@angular-np.cross(omega,I@omega)+np.cross(-rm,F)
            return np.r_[F,M]
        zero=wrench(np.zeros(3));indices=[0,2,4]
        A=np.column_stack([wrench(e)-zero for e in np.eye(3)])[indices]
        exact=np.linalg.solve(A,specified-zero[indices])
        actual=np.r_[np.array(f['acceleration_reference_body'])[[0,2]],f['angular_acceleration_body'][1]]
        error=max(error,float(max(abs(actual-exact))))
    assert error<1e-7
    cp=checkpoint(out,2);resumed=resume_time(parse_asw(request['source']),cp,duration=.04)
    restart=max(float(np.max(abs(np.asarray(a['frame'][key])-b['frame'][key])))
        for a,b in zip(resumed['snapshots'],out['snapshots'][2:])
        for key in ('position_earth','velocity_origin_body','rates_body','body_to_earth'))
    assert restart<1e-8 and cp['older'] is None
    return dict(request=request,trajectory=out,checkpoint=cp,resumed=resumed,comparison=dict(acceleration_error=error,restart_difference=restart))


if __name__=='__main__':
    for channel in ('Fx','Mz'):
        coarse=record(f'{channel}_0.02',lambda channel=channel:pulse(channel,.02))
        fine=record(f'{channel}_0.01',lambda channel=channel:pulse(channel,.01))
        for key in ('rate_error','pose_error'):assert fine['comparison'][key]<.45*coarse['comparison'][key]
    coarse=record('controller_0.01',lambda:controller_release(.01))
    fine=record('controller_0.005',lambda:controller_release(.005))
    for key in ('displacement_error','velocity_error'):assert fine['comparison'][key]<.4*coarse['comparison'][key]
    record('mixed_offsets',mixed_offsets)
    path=Path('docs/validation/time-targets.json')
    path.write_text(json.dumps(dict(description='Finite forcing support, mixed frame load constraints, independent Newton-Euler equations and commanded-force release.',
        **provenance,cases=cases,limitations=['The last sample is included; all specified channel values are zero thereafter, including relative channels.',
            'The public extended manual states the zero-after-end rule; the relative-channel interaction still needs an ASWING executable comparison.',
            'The natural spline endpoint convention and general inverse time histories remain parity gaps.',
            'Step refinement and restart checks do not establish general aircraft or ASWING agreement.']),indent=2,allow_nan=False)+'\n')
    print(f'Completed seven cases, {len(provenance["source_sha256"])} source hashes, {path.stat().st_size} bytes.',flush=True)
