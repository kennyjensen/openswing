"""Reference-airflow vector constraints: independent physics and native/WASM study."""
import hashlib
import json
import platform
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import numpy as np
import scipy
from scipy.spatial.transform import Rotation
from openswing.bridge import dispatch


def vector(speed,alpha,beta):
    a,b=np.deg2rad([alpha,beta])
    return speed*np.array([np.cos(a)*np.cos(b),-np.sin(b),np.sin(a)*np.cos(b)])


def targets(speed,alpha,beta):
    return [dict(variable=k,quantity='reference.'+k,target=v) for k,v in zip(('speed','alpha','beta'),(speed,alpha,beta))]


def specifications():
    source=(ROOT/'examples/gust-modes.asw').read_text().replace('2 1 2\nEnd','2 1 2\n.2 -.1 .3\n-.3 .4 .2\n1.1 -.5 .7\nEnd')
    request=dict(action='solve',mode='mounted',source=source,panels=4,gravity=[0,0,0])
    posed=dict(speed=20,alpha=6,beta=-3,mach=0,density=1.1,position_earth=[7,-3,9],attitude=[17,-11,31],rates=[.4,-.2,.3],time=2.5,
        gust=dict(type='expression',components=['.2*x+.3*t','-.4*y','.1*z-t']))
    cases=[dict(name='posed_spatial_inverse',request=dict(request,condition=posed,operating_constraints=targets(20,6,-3)))]
    for quantity,target in [('speed',12),('equivalent_airspeed',20),('dynamic_pressure',200)]:
        c=dict(speed=10,alpha=0,mach=0,density=.7,gust=dict(type='expression',components=['.2*x','0','0']))
        cases.append(dict(name=quantity,request=dict(request,condition=c,operating_constraints=[dict(variable='position_earth.x',quantity='reference.'+quantity,target=target)])))
    cases.append(dict(name='angle_branch',request=dict(request,condition=dict(speed=10,alpha=179,mach=0),operating_constraints=[dict(variable='alpha',quantity='reference.alpha',target=-179)])))
    flexible=(ROOT/'examples/flexible.asw').read_text()
    cases.append(dict(name='elastic_trim',request=dict(request,source=flexible,condition=dict(speed=18,alpha=3,mach=0,gust=dict(type='uniform',velocity=[2,-.2,.4])),operating_constraints=targets(18,3,0))))
    oscillator=(ROOT/'examples/instrumented-oscillator.asw').read_text()
    cases.append(dict(name='saved_frequency',request=dict(request,source=oscillator,condition=dict(speed=10,alpha=0,mach=0,powers={'1':2},gust=dict(type='uniform',velocity=[2,1,-.5])),operating_constraints=targets(10,0,0))))
    # Convert all dimensional entries of the original rigid model to feet/ms/N.
    length=1/.3048;time=1000;speed=length/time
    # A simple original dimensional fixture avoids altering internal parser metadata.
    converted=f'''Name
Original feet/millisecond reference-flow verification
End
Unit
L 1 ft
T 1 ms
F 1 N
End
Constant
{9.80665*length/time**2} {1.225*time**2/length**4} {340.294*speed}
End
Reference
{2*length**2} {length} {2*length}
{.2*length} {-.1*length} {.3*length}
{-.3*length} {.4*length} {.2*length}
{1.1*length} {-.5*length} {.7*length}
End
Ground
1 0 0
End
Weight
1 0 {1.2*length} {.6*length} {-.3*length} 0 {.4*length**2} 0
End
Beam 1
Rigid axis
t y
0 0
{2*length} {2*length}
End
'''
    cases.append(dict(name='feet_milliseconds',request=dict(request,source=converted,condition=dict(speed=20*speed,alpha=6,beta=-3,mach=0,density=1.1*time**2/length**4,gust=dict(type='uniform',velocity=(np.array([3,-1,2])*speed).tolist())),operating_constraints=targets(20*speed,6,-3))))
    return cases


def compute(spec):
    request=spec['request'];out=dispatch(request);result=dict(static=out)
    if spec['name']=='saved_frequency':
        result['frequency']=dispatch(dict(request,action='frequency',frequency=dict(initial_state=out['equilibrium_state'],frequencies=[0,10,16],inputs=['power.1'])))
    json.dumps(result,allow_nan=False)
    return result


def verify(spec,result):
    count=0;maximum=0.;integration=0
    def close(actual,expected,tolerance=4e-8,independent=True):
        nonlocal count,maximum,integration
        a,b=np.asarray(actual),np.asarray(expected);error=float(np.max(abs(a-b)/np.maximum(1.,abs(b))))
        if independent:count+=a.size*(2 if np.iscomplexobj(a) else 1)
        else:integration+=a.size
        maximum=max(maximum,error);assert error<tolerance,(spec['name'],actual,expected,error)
    name=spec['name'];req=spec['request'];out=result['static'];r=out['reference_flow'];v=out['operating_values'];c=req['condition'];rho=out['atmosphere']['density']
    close([row['normalized_residual'] for row in out['operating_constraints']],0,independent=False)
    if name=='posed_spatial_inverse':
        rot=Rotation.from_euler('z',-31,degrees=True).as_matrix()@Rotation.from_euler('y',-11,degrees=True).as_matrix()@Rotation.from_euler('x',-17,degrees=True).as_matrix()
        earth=np.array([7,-3,9])+rot@np.array([1.1,-.5,.7]);gust=np.array([.2*earth[0]+.75,-.4*earth[1],.1*earth[2]-2.5]);desired=vector(20,6,-3)
        close(r['reference_earth'],earth);close(r['relative_velocity_body'],desired);close(r['relative_velocity_earth'],rot@desired)
        still=desired-rot.T@gust;close(vector(v['speed'],v['alpha'],v['beta']),still)
        point=np.array([1.2,.6,-.3]);pe=np.array(c['position_earth'])+rot@point
        local=still-np.cross(c['rates'],point-np.array([1.1,-.5,.7]))+rot.T@np.array([.2*pe[0]+.75,-.4*pe[1],.1*pe[2]-2.5])
        force=.5*1.1*.4*np.linalg.norm(local)*local;close(out['force'],force);close(out['moment'],np.cross(point-np.array([.2,-.1,.3]),force))
    elif name in ('speed','equivalent_airspeed','dynamic_pressure'):
        speed={'speed':12,'equivalent_airspeed':20*np.sqrt(1.225/.7),'dynamic_pressure':np.sqrt(400/.7)}[name]
        close(r['speed'],speed);close(v['position_earth.x'],(speed-10)/.2-1.1)
        close(r['equivalent_airspeed'],speed*np.sqrt(.7/1.225));close(r['dynamic_pressure'],.35*speed**2)
    elif name=='angle_branch':
        close(v['alpha'],181);close(r['alpha'],-179)
    else:
        speed,alpha,beta=(18,3,0) if name=='elastic_trim' else (10,0,0) if name=='saved_frequency' else (20/.3048/1000,6,-3)
        desired=vector(speed,alpha,beta);still=desired-np.array(c['gust']['velocity'])
        close(r['relative_velocity_body'],desired);close(vector(v['speed'],v['alpha'],v['beta']),still)
        close(r['dynamic_pressure'],.5*rho*speed**2)
        if name=='elastic_trim':assert out['max_displacement']>1e-3
        elif name=='feet_milliseconds':
            force=.5*1.1*.4*20*vector(20,6,-3);close(out['force'],force)
            close(out['moment'],np.cross(np.array([1.2,.6,-.3])-np.array([.2,-.1,.3]),force)/.3048)
        else:
            close(out['sensors'][1]['displacement_body'][1],.004)
            f=result['frequency'];assert f['base']['equilibrium_initialization']['initialization']=='saved physical equilibrium'
            close(f['base']['reference_flow']['relative_velocity_body'],desired)
            for row in f['samples']:
                d=row['responses'][0]['output']['nodes'][-1]['displacement'];actual=d['real'][1]+1j*d['imag'][1];w=row['omega']
                close(actual,1/(500+10j*w-2*w*w))
    return dict(independent_scalar_checks=count,integration_checks=integration,maximum_scaled_error=maximum)


def physical(result):
    out=result['static'];values=[]
    for key in ('force','moment','support_force','support_moment'):values.extend(out[key])
    values.extend(out['operating_values'].values())
    for node in out['nodes']:values.extend(node['position'])
    for key in ('speed','alpha','beta','equivalent_airspeed','dynamic_pressure'):values.append(out['reference_flow'][key])
    for key in ('reference_earth','relative_velocity_body','relative_velocity_earth'):values.extend(out['reference_flow'][key])
    if 'frequency' in result:
        for row in result['frequency']['samples']:
            d=row['responses'][0]['output']['nodes'][-1]['displacement'];values.extend(d['real']);values.extend(d['imag'])
    return np.asarray(values)


def singularity_checks():
    from openswing.asw import parse_asw
    from openswing.aero import FlightCondition
    from openswing.reference_flow import reference_airflow
    source='Name\nOriginal singular air-data check\nEnd\nUnit\nL 1 m\nT 1 s\nF 1 N\nEnd\nConstant\n9.80665 1.225 340.294\nEnd\nReference\n2 1 2\nEnd\nBeam 1\nAxis\nt y\n0 0\n2 2\nEnd\n'
    m=parse_asw(source)
    for beta in (-90,90):
        r=reference_airflow(m,FlightCondition(speed=10,alpha=17,beta=beta,mach=0))
        assert r['alpha'] is None and abs(r['beta']-beta)<1e-12
    rot=Rotation.from_euler('z',-31,degrees=True).as_matrix()@Rotation.from_euler('y',-11,degrees=True).as_matrix()@Rotation.from_euler('x',-17,degrees=True).as_matrix()
    c=FlightCondition(speed=10,alpha=7,beta=3,mach=0,attitude=[17,-11,31],gust=dict(type='uniform',velocity=(-rot@vector(10,7,3)).tolist()))
    r=reference_airflow(m,c);assert r['speed']<1e-13 and r['alpha'] is r['beta'] is None
    return 3


def main():
    files=sorted((ROOT/'openswing').glob('*.py'))+[Path(__file__),*[ROOT/'examples'/n for n in ('gust-modes.asw','flexible.asw','instrumented-oscillator.asw')]]
    hashes={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    cases=[]
    for spec in specifications():
        result=compute(spec);checks=verify(spec,result);cases.append(dict(specification=spec,result=result,checks=checks));print(spec['name'],checks,flush=True)
    (ROOT/'docs/validation/reference-flow.json').write_text(json.dumps(dict(description='Reference airflow, ASW steady eqs181–184: vector constraints, posed spatial gusts, file units, angular branch, elastic equilibrium and saved frequency base.',source_sha256=hashes,python=platform.python_version(),numpy=np.__version__,scipy=scipy.__version__,cases=cases,singularity_checks=singularity_checks()),indent=2)+'\n')
    print('All native reference-flow checks passed.',flush=True)


if __name__=='__main__':main()
