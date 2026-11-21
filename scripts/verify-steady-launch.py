"""Independent mechanics and helical-flight checks for saved steady launch."""
import hashlib,json,platform,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
import scipy
from scipy.linalg import expm
from openswing.asw import parse_asw
from openswing.aero import FlightCondition
from openswing.network import solve_static
from openswing.operating import steady_turn_constraints
from openswing.time_initialization import launch_time
from openswing.time_state import checkpoint,resume_time

files=[Path(__file__),Path('examples/instrumented-oscillator.asw'),Path('examples/trim-aircraft.asw'),*sorted(Path('openswing').glob('*.py'))]
provenance=dict(versions=dict(python=platform.python_version(),numpy=np.__version__,scipy=scipy.__version__),
    source_sha256={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in files})
cache_path=Path('.reference/steady-launch-verification.json')
saved=json.loads(cache_path.read_text()) if cache_path.exists() else {}
cache=saved.get('cases',{}) if saved.get('provenance')==provenance else {}


def record(name,compute):
    if name in cache:print('Resumed '+name,flush=True);return cache[name]
    result=compute();cache[name]=result
    tmp=cache_path.with_suffix('.tmp');tmp.write_text(json.dumps(dict(provenance=provenance,cases=cache),allow_nan=False));tmp.replace(cache_path)
    print(name+': '+json.dumps(result.get('comparison',{})),flush=True);return result


def lag_base():
    source=Path('examples/instrumented-oscillator.asw').read_text();model=parse_asw(source)
    control=dict(commands={'RY[2]':2.01},outputs=[dict(actuator='E1',expression="state('lag')")],
        states=[dict(name='lag',initial=0,scale=10,unit='file engine setting',
            rate="(command('E1')-200*error('RY[2]')-20*error('UY[2]')-state('lag'))/.05")])
    steady=solve_static(model,FlightCondition(speed=10,alpha=0,mach=0),4,gravity=[0,0,0],controller=control)
    assert abs(steady['feedback']['states']['lag']-10/7)<1e-8
    return dict(source=source,steady=steady,comparison=dict(actuator=steady['feedback']['states']['lag']))


def lag_response(base,dt):
    seed=base['steady']['equilibrium_state'];model=parse_asw(base['source'])
    forcing='time +RY[2]\n0 .01\n.2 .01\n'
    trajectory=launch_time(model,seed,duration=.12,dt=dt,forcing=forcing)
    # Independently assembled 2 kg / 500 N/m / 10 Ns/m plant, 0.05 s actuator,
    # proportional 200 and derivative 20 gains. The command steps .01 -> .02.
    A=np.array([[0,1,0],[-250,-5,.5],[-4000,-400,-20.]])
    initial=np.array([2/700,0,10/7]);final=2*initial
    errors=np.zeros(3)
    for s in trajectory['snapshots']:
        exact=final+expm(A*s['time'])@(initial-final)
        actual=[s['nodes'][-1]['position'][1]-2,s['local_velocity'][-1][1],s['feedback']['states']['lag']]
        errors=np.maximum(errors,abs(np.array(actual)-exact))
    index=len(trajectory['snapshots'])//2;cp=checkpoint(trajectory,index)
    resumed=resume_time(model,json.loads(json.dumps(cp)),duration=.12-cp['state']['time'])
    restart=max(np.max(abs(np.array(a['restart']['state']['feedback'])-b['restart']['state']['feedback']))
        for a,b in zip(resumed['snapshots'],trajectory['snapshots'][index:]))
    assert restart<1e-7
    assert trajectory['snapshots'][0]['feedback']['commands']['RY[2]']==2.01
    return dict(source=base['source'],seed=seed,time=dict(duration=.12,dt=dt,forcing=forcing),trajectory=trajectory,
        checkpoint=cp,resumed=resumed,comparison=dict(step=dt,max_error=errors.tolist(),max_restart_state_difference=restart))


def flight_base():
    source=Path('examples/trim-aircraft.asw').read_text();model=parse_asw(source)
    targets=steady_turn_constraints(np.deg2rad(3),2,trim_controls=[2,1,3],engine_control=1)
    steady=solve_static(model,FlightCondition(alpha=4,mach=0,powers={1:120},attitude=(0,4,57)),4,
        operating_constraints=targets,tolerance=1e-10)
    assert max(abs(np.array(steady['applied_force'])))<1e-5
    assert max(abs(np.array(steady['applied_moment'])))<1e-5
    return dict(source=source,steady=steady,comparison=dict(alpha=steady['operating_values']['alpha'],
        thrust=steady['operating_values']['power.1'],residual=steady['residual']))


def flight_response(base,dt):
    seed=base['steady']['equilibrium_state'];model=parse_asw(base['source'])
    trajectory=launch_time(model,seed,duration=.2,dt=dt,frame='free')
    f0=trajectory['snapshots'][0]['frame'];R=np.array(f0['body_to_earth']);U=np.array(f0['velocity_origin_body']);w=np.array(f0['rates_body'])
    # Exact constant body twist: the homogeneous exponential gives the body
    # origin helix, including the offset velocity/acceleration references.
    twist=np.zeros((4,4));x,y,z=w;twist[:3,:3]=[[0,-z,y],[z,0,-x],[-y,x,0]];twist[:3,3]=U
    errors=[];velocity=[];rotation=[]
    for s in trajectory['snapshots']:
        exact=expm(twist*s['time']);f=s['frame']
        errors.append(np.linalg.norm(np.array(f['position_earth'])-f0['position_earth']-R@exact[:3,3]))
        velocity.append(np.linalg.norm(np.array(f['velocity_origin_body'])-U))
        rotation.append(np.linalg.norm(np.array(f['body_to_earth'])-R@exact[:3,:3]))
    assert max(errors)<.01 and max(velocity)<.005 and max(rotation)<1e-4
    assert trajectory['continuation_steps']==0
    return dict(source=base['source'],seed=seed,time=dict(duration=.2,dt=dt,frame='free'),trajectory=trajectory,
        comparison=dict(step=dt,max_origin_position_error=max(errors),max_body_velocity_error=max(velocity),max_rotation_matrix_error=max(rotation)))


if __name__=='__main__':
    lag=record('lag_base',lag_base)
    runs=[record(f'lag_{dt}',lambda dt=dt:lag_response(lag,dt)) for dt in (.02,.01,.005)]
    for a,b in zip(runs,runs[1:]):assert np.all(np.array(b['comparison']['max_error'])<.45*np.array(a['comparison']['max_error']))
    flight=record('flight_base',flight_base)
    runs=[record(f'flight_{dt}',lambda dt=dt:flight_response(flight,dt)) for dt in (.05,.025)]
    assert runs[1]['comparison']['max_origin_position_error']<.4*runs[0]['comparison']['max_origin_position_error']
    Path('docs/validation/steady-launch.json').write_text(json.dumps(dict(description='Saved steady launch without re-equilibration: independent actuator-lag matrix exponential, BDF continuation and exact steady-turn helix.',
        **provenance,cases=cache,limitations=['The steady and dynamic residuals now use the same distributed mass quadrature and virtual-power load transfer.',
            'Only zero-local-rate, residual-consistent equilibria launch directly; arbitrary initial states and inconsistent support release are not projected.',
            'These original demonstrations do not establish ASWING or experimental equivalence.']),indent=2,allow_nan=False)+'\n')
    print('Completed seven cases with '+str(len(provenance['source_sha256']))+' source hashes.',flush=True)
