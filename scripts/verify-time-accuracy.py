"""Temporal refinement against damped mechanics, a controller and finite-wing lag.

References are closed-form mechanics or independent small linear systems. The
gust reference is a small-disturbance finite-wing model; halving its amplitude
checks the separate nonlinear-model discrepancy. No ASWING adaptive rule or
global accuracy guarantee is inferred from this study.
"""
from pathlib import Path
import argparse
import hashlib
import json
import platform
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import numpy as np
import scipy
from scipy.linalg import expm
from openswing.asw import parse_asw
from openswing.aero import FlightCondition
from openswing.time_integration import solve_time
from openswing.time_state import checkpoint,resume_time


def spring_source(units):
    L,T,F=units
    return f'''Name
Temporal accuracy spring
End
Unit
L {L} m
T {T} s
F {F} N
End
Constant
{9.80665*T*T/L} {1.225*L**4/(F*T*T)} {340.294*T/L}
End
Reference
{2/L**2} {1/L} {2/L}
End
Ground
1 0 0
End
Weight
1 2 0 {2/L} 0 {19.6133/F}
End
Beam 1
Axial spring
t y EA tdeps
0 0 {1000/F} {.02/T}
2 {2/L} {1000/F} {.02/T}
End
'''


def controls(spec):
    return dict(rtol=spec['rtol'],atol=spec['atol'])


def finish(spec,source,result,samples,scales,columns,*,restart=False):
    values=np.array([s['computed'] for s in samples]);reference=np.array([s['reference'] for s in samples])
    errors=np.max(abs(values-reference)/np.asarray(scales),axis=0)
    assert np.all(np.isfinite(errors))
    assert result['accuracy']['maximum_accepted_ratio']<=1
    assert result['internal_steps']==2*result['accepted_steps']
    for previous,row in zip(result['snapshots'],result['snapshots'][1:]):
        assert row['time']-previous['time']==row['accuracy']['trial_step']
        assert row['step']==row['time']-row['accuracy']['midpoint_time']
        if row['restart']['older'] is not None:
            assert row['restart']['older']['time']==row['accuracy']['midpoint_time']
    resumed=None
    if restart:
        index=len(result['snapshots'])//2;cp=checkpoint(result,index)
        out=resume_time(parse_asw(source),json.loads(json.dumps(cp)),duration=result['end_time']-cp['state']['time'])
        # Compare the physical endpoint, independent of tiny changes in the
        # adaptive grid from refactorization and floating-point arithmetic.
        a,b=out['snapshots'][-1],result['snapshots'][-1]
        differences=[]
        for key in ['local_velocity','local_rates','circulation_rate']:
            x,y=np.asarray(a[key]),np.asarray(b[key])
            if x.size:differences.extend((abs(x-y)/np.maximum(1.,abs(y))).ravel())
        x,y=np.array([n['position'] for n in a['nodes']]),np.array([n['position'] for n in b['nodes']])
        differences.extend((abs(x-y)/np.maximum(1.,abs(y))).ravel())
        for key in b.get('feedback',{}).get('states',{}):
            differences.append(abs(a['feedback']['states'][key]-b['feedback']['states'][key])/max(1.,abs(b['feedback']['states'][key])))
        difference=float(max(differences));assert difference<2e-7,difference
        assert out['restart_context']['method']['accuracy']==result['restart_context']['method']['accuracy']
        resumed=dict(checkpoint=cp,maximum_scaled_endpoint_difference=difference,accepted_steps=out['accepted_steps'])
    for sample,row in zip(samples,result['snapshots']):
        sample['residual']=row['residual'];sample['accuracy']=row.get('accuracy')
    return dict(spec=spec,source=source,columns=columns,error_scales=scales,
        maximum_scaled_errors=errors.tolist(),maximum_scaled_error=float(max(errors)),
        accuracy=result['accuracy'],accepted_steps=result['accepted_steps'],rejected_steps=result['rejected_steps'],
        samples=samples,restart=resumed)


def spring(spec):
    units=spec.get('units',[1.,1.,1.]);L,T,F=units;source=spring_source(units)
    result=solve_time(parse_asw(source),panels=4,duration=.12/T,dt=.06/T,order=spec['order'],gravity=[0,0,0],
        initial_loads=[dict(beam=1,t=2,force=[0,1/F,0])],accuracy=controls(spec))
    wd=np.sqrt(243.75);samples=[]
    for row in result['snapshots']:
        t=row['time']*T;decay=np.exp(-2.5*t)
        q=.002*decay*(np.cos(wd*t)+2.5/wd*np.sin(wd*t));v=-.5/wd*decay*np.sin(wd*t)
        # Internal spring/dashpot force and support reaction are algebraic
        # outputs; include them independently of the motion-state error.
        force=500*q+10*v
        samples.append(dict(time=t,computed=[row['nodes'][-1]['position'][1]*L-2,row['local_velocity'][-1][1]*L/T,
            row['elements'][0]['force_local'][1]*F,row['support_force'][1]*F],reference=[q,v,force,-force]))
    out=finish(spec,source,result,samples,[.002,.002*np.sqrt(250),1.,1.],
        ['tip displacement / m','tip velocity / (m/s)','axial section force / N','support force / N'],restart=spec.get('restart',False))
    assert out['maximum_scaled_error']<(.02 if spec['order']==2 else 1e-5),out['maximum_scaled_errors']
    return out


def controller(spec):
    source=(ROOT/'examples/instrumented-oscillator.asw').read_text()
    law=json.loads((ROOT/'examples/actuator-lag-controller.json').read_text())
    switch=.013;command=.01;end=.12
    forcing=f'time +RY[2]\n0 0\n{switch} 0\n{switch} {command}\n.2 {command}'
    result=solve_time(parse_asw(source),FlightCondition(speed=10,alpha=0,mach=0),4,
        duration=end,dt=.06,order=2,gravity=[0,0,0],controller=law,forcing=forcing,accuracy=controls(spec))
    matrix=np.array([[0,1,0],[-250,-5,.5],[-4000,-400,-20]])
    rhs=np.array([0.,0.,4000*command]);samples=[]
    for row in result['snapshots']:
        t=row['time'];exact=np.linalg.solve(matrix,(expm(matrix*max(0.,t-switch))-np.eye(3))@rhs)
        samples.append(dict(time=t,computed=[row['nodes'][-1]['position'][1]-2,row['local_velocity'][-1][1],row['feedback']['states']['lag']],reference=exact.tolist()))
    event=next(row for row in result['snapshots'] if row['time']==switch)
    assert event['forcing_side']=='left'
    out=finish(spec,source,result,samples,[command,command*np.sqrt(250),200*command],
        ['tip displacement / m','tip velocity / (m/s)','actuator lag state / N'],restart=spec.get('restart',False))
    out['reference_matrix']=matrix.tolist();out['command_step_time']=switch
    assert out['maximum_scaled_error']<.05,out['maximum_scaled_errors']
    return out


def finite_wing(count,span):
    """Direct straight-line Biot--Savart integrals, not solver AIC extraction."""
    edge=-span/2*np.cos(np.linspace(0,np.pi,count+1))
    y=-span/2*np.cos((np.arange(count)+.5)*np.pi/count)
    a=y[:,None]-edge[:-1];b=y[:,None]-edge[1:];dx=.5
    ra=np.sqrt(dx*dx+a*a);rb=np.sqrt(dx*dx+b*b)
    return -(a/ra-b/rb)/(4*np.pi*dx)+((1+dx/rb)/b-(1+dx/ra)/a)/(4*np.pi)


def gust(spec):
    span=12.;speed=10.;count=4;amplitude=spec.get('amplitude',.02)
    source=(ROOT/'examples/rectangular.asw').read_text()
    source=source[:source.index('t dCLdF1')]+'End\n';source=source.replace('.008','0')
    condition=FlightCondition(speed=speed,alpha=0,mach=0,stall=False,
        gust=dict(type='expression',components=['0','0',f'{amplitude}*t']))
    result=solve_time(parse_asw(source),condition,count,duration=.4,dt=.4,order=5,
        tolerance=1e-10,gravity=[0,0,0],accuracy=controls(spec))
    # M gamma_dot - W gamma = amplitude*t. Augment with t'=1 and 1'=0.
    mass=2/(np.pi*speed);w=finite_wing(count,span)
    matrix=np.zeros((count+2,count+2));matrix[:count,:count]=w/mass
    matrix[:count,count]=amplitude/mass;matrix[count,-1]=1.
    initial=np.zeros(count+2);initial[-1]=1.;samples=[]
    for row in result['snapshots']:
        t=row['time'];gamma=(expm(t*matrix)@initial)[:count];rate=(w@gamma+amplitude*t)/mass
        force=1.225*(speed*gamma+rate)
        strips=[s for s in row['strips'] if s['lifting']]
        assert len(strips)==count
        samples.append(dict(time=t,computed=[*[s['circulation'] for s in strips],*row['circulation_rate'],*[s['f_aero'] for s in strips]],
            reference=[*gamma,*rate,*force]))
    scale=max(abs(np.array(samples[-1]['reference'])[:count]))
    out=finish(spec,source,result,samples,[scale]*count+[scale/.2]*count+[1.225*speed*scale]*count,
        [f'{key} strip {i}' for key in ['circulation / (m2/s)','circulation rate / (m2/s2)','normal circulatory density / (N/m)'] for i in range(count)],restart=spec.get('restart',False))
    out['reference_matrix']=matrix.tolist()
    assert out['maximum_scaled_error']<.002,out['maximum_scaled_errors']
    return out


def compute(spec):
    return {'spring':spring,'controller':controller,'gust':gust}[spec['kind']](spec)


def specifications():
    return [dict(kind='spring',order=order,atol=a,rtol=1000*a,restart=order==2 and a==2.5e-6)
        for order,tolerances in [(2,[1e-5,2.5e-6]),(5,[1e-8,2.5e-9])] for a in tolerances]+[
        dict(kind='spring',order=2,atol=2.5e-6,rtol=.0025,units=[.3048,2.,4.4482216152605]),
        *[dict(kind='controller',atol=a,rtol=1000*a,restart=a==2.5e-6) for a in [1e-5,2.5e-6]],
        *[dict(kind='gust',atol=a,rtol=10000*a,restart=a==2.5e-9) for a in [1e-8,2.5e-9]],
        dict(kind='gust',atol=1.25e-9,rtol=2.5e-5,amplitude=.01)]


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--limit',type=int)
    parser.add_argument('--kind',choices=['spring','controller','gust']);args=parser.parse_args()
    files=[Path(__file__),ROOT/'examples/instrumented-oscillator.asw',ROOT/'examples/actuator-lag-controller.json',
           ROOT/'examples/rectangular.asw',*sorted((ROOT/'openswing').glob('*.py'))]
    provenance=dict(source_sha256={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files},
        versions=dict(python=platform.python_version(),numpy=np.__version__,scipy=scipy.__version__))
    cache=ROOT/'.reference/time-accuracy'/hashlib.sha256(json.dumps(provenance,sort_keys=True).encode()).hexdigest();cache.mkdir(parents=True,exist_ok=True)
    specs=specifications();chosen=[s for s in specs if args.kind is None or s['kind']==args.kind][:args.limit];cases=[]
    for spec in chosen:
        path=cache/(hashlib.sha256(json.dumps(spec,sort_keys=True).encode()).hexdigest()+'.json')
        if path.exists():case=json.loads(path.read_text());print('Cached',spec,flush=True)
        else:
            print('Computing',spec,flush=True);case=compute(spec)
            path.write_text(json.dumps(case,allow_nan=False)+'\n')
        cases.append(case);print('Result',spec,case['maximum_scaled_error'],case['accepted_steps'],flush=True)
    if len(cases)!=len(specs):return
    for loose,tight in [(0,1),(2,3),(5,6),(7,8)]:
        assert cases[tight]['maximum_scaled_error']<.85*cases[loose]['maximum_scaled_error'],(loose,tight)
    assert abs(cases[4]['maximum_scaled_error']-cases[1]['maximum_scaled_error'])<2e-7
    out=dict(description=__doc__,**provenance,cases=cases,
        scope='Local temporal discrepancy, measured global errors, units, BDF midpoint checkpoints, controller forcing events and small-amplitude finite-wing lag. No ASWING executable or aircraft/experimental validation.')
    (ROOT/'docs/validation/time-accuracy.json').write_text(json.dumps(out,indent=2,allow_nan=False)+'\n')
    print('Wrote docs/validation/time-accuracy.json',flush=True)


if __name__=='__main__':main()
