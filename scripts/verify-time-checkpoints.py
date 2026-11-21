"""Restart equivalence and independent damped oscillator/time-state checks."""
import hashlib,json,platform,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
import scipy
from openswing.asw import parse_asw
from openswing.aero import FlightCondition
from openswing.time_integration import solve_time
from openswing.time_state import checkpoint,resume_time

source=Path('examples/instrumented-oscillator.asw').read_text()
files=[Path(__file__),Path('examples/instrumented-oscillator.asw'),*sorted(Path('openswing').glob('*.py'))]
provenance=dict(versions=dict(python=platform.python_version(),numpy=np.__version__,scipy=scipy.__version__),
    source_sha256={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in files})
cache_path=Path('.reference/time-checkpoint-verification.json')
saved=json.loads(cache_path.read_text()) if cache_path.exists() else {}
cache=saved.get('cases',{}) if saved.get('provenance')==provenance else {}


def record(name,compute):
    if name in cache:print('Resumed '+name,flush=True);return cache[name]
    result=compute();cache[name]=result
    tmp=cache_path.with_suffix('.tmp');tmp.write_text(json.dumps(dict(provenance=provenance,cases=cache),allow_nan=False));tmp.replace(cache_path)
    print(name+': '+json.dumps(result['comparison']),flush=True);return result


def release(dt):
    model=parse_asw(source);c=FlightCondition(speed=10,alpha=0,mach=0)
    full=solve_time(model,c,4,duration=.16,dt=dt,gravity=[0,0,0],initial_loads=[dict(beam=1,t=2,force=[0,1,0])])
    index=len(full['snapshots'])//2;state=checkpoint(full,index)
    resumed=resume_time(model,json.loads(json.dumps(state)),duration=.16-state['state']['time'])
    errors=[];velocity_errors=[];restart_errors=[];omega=np.sqrt(250-2.5**2)
    for s in full['snapshots']:
        t=s['time'];exact=.002*np.exp(-2.5*t)*(np.cos(omega*t)+2.5/omega*np.sin(omega*t))
        rate=-.002*250/omega*np.exp(-2.5*t)*np.sin(omega*t)
        errors.append(abs(s['nodes'][-1]['position'][1]-2-exact))
        velocity_errors.append(abs(s['local_velocity'][-1][1]-rate))
    assert len(resumed['snapshots'])==len(full['snapshots'])-index
    for a,b in zip(resumed['snapshots'],full['snapshots'][index:]):
        restart_errors.append(max(abs(a['nodes'][-1]['position'][1]-b['nodes'][-1]['position'][1]),
                                  abs(a['local_velocity'][-1][1]-b['local_velocity'][-1][1])))
        assert a['residual']<1e-8
    assert max(restart_errors)<2e-8
    return dict(source=source,full=full,checkpoint=state,resumed=resumed,comparison=dict(step=dt,
        max_displacement_error=max(errors),max_velocity_error=max(velocity_errors),max_restart_difference=max(restart_errors)))


def closed_loop():
    model=parse_asw(source);c=FlightCondition(speed=10,alpha=0,mach=0)
    controller=dict(outputs=[dict(actuator='E1',expression="state('lag')")],states=[dict(name='lag',unit='file engine setting',scale=1.,initial=0.,rate="(-200*error('RY[2]')-20*error('UY[2]')-state('lag'))/.05")])
    forcing='time +RY[2]\n0 0\n.04 0\n.04 .01\n.12 .01\n'
    full=solve_time(model,c,4,duration=.12,dt=.01,gravity=[0,0,0],controller=controller,forcing=forcing)
    runs=[]
    for index in (4,8):
        cp=checkpoint(full,index);result=resume_time(model,json.loads(json.dumps(cp)),duration=.12-cp['state']['time']);errors=[]
        for a,b in zip(result['snapshots'],full['snapshots'][index:]):
            errors.append(abs(a['feedback']['states']['lag']-b['feedback']['states']['lag']))
            np.testing.assert_allclose(a['frame']['position_earth'],b['frame']['position_earth'],atol=1e-8)
        assert max(errors)<2e-7
        runs.append(dict(checkpoint=cp,result=result,max_state_difference=max(errors)))
    assert runs[0]['result']['snapshots'][1]['order']==1 and runs[1]['result']['snapshots'][1]['order']==2
    assert all(r['result']['forcing']['channels'][0]['initial']==2 for r in runs)
    return dict(source=source,controller=controller,full=full,runs=runs,comparison=dict(max_restart_state_difference=max(r['max_state_difference'] for r in runs),
        resumed_times=[r['checkpoint']['state']['time'] for r in runs],first_step_orders=[r['result']['snapshots'][1]['order'] for r in runs]))


if __name__=='__main__':
    cases={f'release_{dt}':record(f'release_{dt}',lambda dt=dt:release(dt)) for dt in (.02,.01,.005)}
    errors=[c['comparison']['max_displacement_error'] for c in cases.values()]
    assert errors[1]<.35*errors[0] and errors[2]<.35*errors[1],errors
    cases['controller']=record('controller',closed_loop)
    Path('docs/validation/time-checkpoints.json').write_text(json.dumps(dict(description='Physical BDF checkpoint equivalence, independent damped-oscillator refinement and a controller forcing discontinuity.',
        **provenance,cases=cases,limitations=['These are OpenSwing checkpoints, not ASWING companion-file interchange.',
            'Restart agreement requires compatible source/setup and time-step sequences; a fresh LU factorization may change roundoff and Newton iteration counts.',
            'Replacing future forcing explicitly resets BDF history; the pre-switch state is retained.',
            'Direct time launch from saved steady trim, arbitrary initial-state construction, ASWING and experimental validation remain outstanding.']),indent=2,allow_nan=False)+'\n')
    print('Completed four checkpoint cases with '+str(len(provenance['source_sha256']))+' source hashes.',flush=True)
