"""Inverse time controls against separately integrated one-kilogram mechanics."""
from pathlib import Path
import hashlib,json,platform,sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import numpy as np
import scipy
from openswing.bridge import dispatch


def source(units):
    L,T,F=units
    if units==[1.,1.,1.]:
        return (ROOT/'examples/inverse-actuators.asw').read_text()
    return f'''Name
Inverse actuator unit verification
End
Unit
L {L:.17g} m
T {T:.17g} s
F {F:.17g} N
End
Constant
{9.80665*T*T/L:.17g} {1.225*L**4/(F*T*T):.17g} {340.294*T/L:.17g}
End
Reference
{2/L**2:.17g} {1/L:.17g} {2/L:.17g}
End
Ground
1 0 0
End
Weight
1 0 0 0 0 {9.80665/F:.17g} 0 0 0 0 0 {19.6133/(F*L*L):.17g} {29.41995/(F*L*L):.17g} {39.2266/(F*L*L):.17g}
End
Engine
1 0 1 0 0 0 0 1 0 0 1 0 -1 0 0
2 0 1 0 0 0 0 0 0 1 0 1 -1 0 0
End
Beam 1
Rigid frame
t y
0 0
2 {2/L:.17g}
End
'''


CASES=[dict(order=o,dt=h,units=[1.,1.,1.]) for o,h in [(1,.02),(1,.01),(2,.02),(2,.01),(5,.04)]]
CASES.append(dict(order=2,dt=.02,units=[.3048,.4,4.4482216152605]))


def request(spec):
    L,T,F=spec['units'];a=T*T/L
    return dict(action='time',source=source(spec['units']),panels=4,
        condition=dict(speed=10*T/L,alpha=0,mach=0,gravity_magnitude=0),
        time=dict(duration=.12/T,dt=spec['dt']/T,order=spec['order'],frame='free',
            actuator_constraints=[dict(variable='power.1',quantity='acceleration.x',target=.2*a)],
            forcing=f'time +Ax\n0 0\n{.12/T:.17g} {.12*a:.17g}'))


def physical(result,units):
    L,T,F=units
    return np.array([[s['time']*T,*np.array(s['frame']['velocity_origin_body'])*L/T,
        *np.array(s['frame']['position_earth'])*L,*np.array(s['frame']['acceleration_reference_body'])*L/T**2,
        s['operating_values']['power.1']*F,*np.array(s['applied_force'])*F] for s in result['snapshots']])


def verify(result,spec):
    values=physical(result,spec['units']);t=values[:,0]
    truth=np.column_stack([t,-10+.2*t+t*t/2,np.zeros((len(t),2)),
        -10*t+.1*t*t+t**3/6,np.zeros((len(t),2)),.2+t,np.zeros((len(t),2)),.2+t,np.zeros((len(t),3))])
    errors=np.max(abs(values-truth),axis=0)
    assert max(errors[[0,2,3,5,6,7,8,9,10,11,12,13]])<2e-8,errors
    trajectory=max(errors[[1,4]])
    assert trajectory<({1:.004,2:.0004,5:2e-8}[spec['order']]),errors
    return dict(maximum_force_acceleration_error=float(max(errors[[7,10,11,12,13]])),
        maximum_trajectory_error=float(trajectory),component_errors=errors.tolist(),physical_values=int(values.size))


if __name__=='__main__':
    files=[*sorted((ROOT/'openswing').glob('*.py')),Path(__file__),ROOT/'examples/inverse-actuators.asw']
    hashes={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    cases=[]
    for spec in CASES:
        req=request(spec);result=dispatch(req);comparison=verify(result,spec)
        cases.append(dict(specification=spec,request=req,result=result,comparison=comparison))
        print(spec,comparison,flush=True)
    for coarse,fine in [(0,1),(2,3)]:
        assert cases[fine]['comparison']['maximum_trajectory_error']<.55*cases[coarse]['comparison']['maximum_trajectory_error']
    unit_error=float(np.max(abs(physical(cases[2]['result'],CASES[2]['units'])-physical(cases[5]['result'],CASES[5]['units']))))
    assert unit_error<2e-8,unit_error
    assert hashes=={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    path=ROOT/'docs/validation/time-actuators.json'
    path.write_text(json.dumps(dict(source_sha256=hashes,versions=dict(python=platform.python_version(),numpy=np.__version__,scipy=scipy.__version__),
        cases=cases,unit_error=unit_error,scope='Independent one-kilogram translation, time refinement and unit conversion; not general aircraft or ASWING parity.'),indent=2,allow_nan=False)+'\n')
    print(path,flush=True)
