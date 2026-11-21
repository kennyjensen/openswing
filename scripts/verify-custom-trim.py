"""Independent mechanics and sensor references for declarative user trim."""
import hashlib,json,platform,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import numpy as np
import scipy
from scipy.optimize import brentq
from openswing.bridge import dispatch


def constraint(expression='sensor("2.displacement_body.y")',target=.01,**kwargs):
    return dict(variable='power.1',quantity='user.tip',expression=expression,target=target,residual_scale=.01,unit='input L',**kwargs)


def specifications():
    spring=(ROOT/'examples/instrumented-oscillator.asw').read_text()
    common=dict(action='solve',mode='mounted',source=spring,panels=4,gravity=[0,0,0],condition=dict(speed=10,alpha=0,mach=0))
    specs=[]
    for name,expression,value,unit in [('displacement','sensor("2.displacement_body.y")',.01,'input L'),('strain','sensor("2.strain.s")',.005,'dimensionless'),('nonlinear_expression','exp(sensor("2.displacement_body.y"))',np.exp(.01),'dimensionless')]:
        t=constraint(expression,value);t['unit']=unit
        specs.append(dict(name=name,request=dict(common,operating_constraints=[t])))
    t=constraint('sensor("2.alpha")',20);t.update(variable='alpha',unit='deg',residual_scale=10)
    specs.append(dict(name='gust_angle',request=dict(common,condition=dict(common['condition'],gust=dict(type='uniform',velocity=[0,0,2])),operating_constraints=[t])))
    t=constraint();t['variable']='command.E1'
    controller=dict(commands={'RY[2]':2},outputs=[dict(actuator='E1',terms=[dict(input='RY[2]',gain=-200)])])
    specs.append(dict(name='closed_loop',request=dict(common,controller=controller,operating_constraints=[t])))
    two=spring.replace('1 0 1 2 0 2 0 0 1 0 1 0 -1 0 0','1 0 1 2 0 2 0 0 1 0 1 0 -1 0 0\n2 0 1 2 0 2 0 0 1 0 2 0 -1 0 0')
    specs.append(dict(name='weighted',request=dict(common,source=two,operating_constraints=[constraint(),dict(variable='power.2',quantity='minimum_control',weight=4)])))
    specs.append(dict(name='saved_frequency',request=dict(common,operating_constraints=[constraint()])))
    # Same physical spring in centimetres: EA unchanged, L=200 cm, stiffness
    # 5 N/cm, rho=1.225e-8 N s²/cm⁴. The dimensionless strain is still .005.
    cm=spring.replace('L 1 m','L 1 cm').replace('9.80665 1.225 340.294','980.665 1.225e-8 34029.4').replace('2 1 2\nEnd','20000 100 200\nEnd').replace('1 2 0 2 0 19.6133','1 200 0 200 0 19.6133').replace('1 0 1 2 0 2 0 0 1 0 1 0 -1 0 0','1 0 1 200 0 200 0 0 1 0 1 0 -100 0 0').replace('2 2 1000 .02','200 200 1000 .02').replace('1 1 0 0 0 .2','1 1 0 0 0 20').replace('2 1 2 .3 2 .2','2 1 200 30 200 20')
    t=constraint(target=1);t['residual_scale']=1
    specs.append(dict(name='centimetres',request=dict(common,source=cm,condition=dict(common['condition'],speed=1000),operating_constraints=[t])))
    # Pure bending: EI=100, L=2; torque about x is the engine setting.
    bend=spring.replace('t y EA tdeps\n0 0 1000 .02\n2 2 1000 .02','t y EIcc\n0 0 100\n2 2 100').replace('1 0 1 2 0 2 0 0 1 0 1 0 -1 0 0','1 0 1 2 0 2 0 1 0 0 0 1 -1 0 0')
    z=2*(1-np.cos(1.))
    t=constraint('sensor("2.displacement_body.z")',z);t['residual_scale']=1
    for panels in (4,8):specs.append(dict(name=f'curved_beam_{panels}',request=dict(common,source=bend,panels=panels,operating_constraints=[t])))
    return specs


def compute(spec):
    req=spec['request'];out=dict(static=dispatch(req))
    if spec['name']=='closed_loop':
        unbound=dict(req,initial_state=out['static']['equilibrium_state'],operating_constraints=[dict(variable='power.1',quantity='minimum_control')])
        unbound.pop('controller')
        try:dispatch(unbound)
        except ValueError as exc:
            assert 'matching controller' in str(exc),str(exc)
            out['unbound_seed_rejection']=str(exc)
        else:raise AssertionError('Weighted trim silently dropped the saved controller.')
        try:dispatch(dict(unbound,initial_state=[],operating_constraints=[constraint()]))
        except ValueError as exc:
            assert 'equilibrium' in str(exc),str(exc)
            out['malformed_seed_rejection']=str(exc)
        else:raise AssertionError('Malformed custom-trim seed was accepted.')
    if spec['name']=='saved_frequency':
        out['frequency']=dispatch(dict(req,action='frequency',frequency=dict(initial_state=out['static']['equilibrium_state'],frequencies=[0,10,16],inputs=['power.1'])))
        t=dict(req['operating_constraints'][0],target=.02)
        out['continued']=dispatch(dict(req,initial_state=out['static']['equilibrium_state'],operating_constraints=[t]))
    json.dumps(out,allow_nan=False);return out


def verify(spec,result):
    count=0;integration=0;maximum=0.
    def close(a,b,tol=1e-7,independent=True):
        nonlocal count,integration,maximum
        a,b=np.asarray(a),np.asarray(b);e=float(np.max(abs(a-b)/np.maximum(1.,abs(b))))
        if independent:count+=a.size*(2 if np.iscomplexobj(a) else 1)
        else:integration+=a.size
        maximum=max(maximum,e);assert e<tol,(spec['name'],a,b,e)
    name=spec['name'];o=result['static'];v=o['operating_values'];sensor=o['sensors'][1]
    close(o['residual'],0,1e-8,False);assert o['custom_trim']['one_sided_tangent_ratio']<=1
    assert o['equilibrium_state']['launch']['released_constraints'][0]['expression']==spec['request']['operating_constraints'][0]['expression']
    metrics={}
    if name=='gust_angle':
        alpha=20-np.rad2deg(np.arcsin(.2*np.cos(np.deg2rad(20))))
        close(v['alpha'],alpha);close(sensor['alpha'],20);close(sensor['speed'],np.linalg.norm([10*np.cos(np.deg2rad(alpha)),0,10*np.sin(np.deg2rad(alpha))+2]))
    elif name.startswith('curved_beam_'):
        # Independent closed-form finite-rotation bending geometry; integrate
        # constant curvature over the actual material intervals. The separate
        # continuum comparison must converge to M=EI*angle/L=50, angle=1 rad.
        t=np.array([n['t'] for n in o['nodes']]);ds=np.diff(t);mid=(t[1:]+t[:-1])/2
        desired=2*(1-np.cos(1.));angle=brentq(lambda a:np.sum(ds*np.sin(a*mid/2))-desired,.5,1.5,xtol=1e-14)
        close(v['power.1'],50*angle);close(sensor['displacement_body'][2],desired)
        close(sensor['anchor_position_body'][1],np.sum(ds*np.cos(angle*mid/2)))
        close(sensor['bank'],-np.rad2deg(angle));close(sensor['curvature_change'][0],angle/2)
        metrics=dict(continuum_torque_relative_error=abs(v['power.1']-50)/50,rotation_rad=angle)
    else:
        close(sensor['displacement_body'][1],1 if name=='centimetres' else .01)
        close(sensor['strain'][1],.005)
        close(o['support_force'],[0,-5,0])
        if name=='weighted':
            close([v['power.1'],v['power.2']],[2.5,1.25],3e-6)
            close(o['control_allocation']['objective'],6.25)
        else:close(v['power.1'],5)
        if name=='closed_loop':
            close(o['feedback']['commands']['E1'],7);close(o['feedback']['actuators']['E1'],5)
            assert 'matching controller' in result['unbound_seed_rejection'];integration+=1
            assert 'equilibrium' in result['malformed_seed_rejection'];integration+=1
        if name=='saved_frequency':
            close(result['continued']['operating_values']['power.1'],10)
            close(result['frequency']['base']['sensors'][1]['displacement_body'][1],.01)
            for row in result['frequency']['samples']:
                d=row['responses'][0]['output']['sensors'][1]['displacement_body'];w=row['omega']
                close(d['real'][1]+1j*d['imag'][1],1/(500+10j*w-2*w*w),1e-9)
    return dict(independent_scalar_checks=count,integration_checks=integration,maximum_scaled_error=maximum,**metrics)


def physical(result):
    o=result['static'];values=[]
    for k in ('force','moment','support_force','support_moment'):values.extend(o[k])
    values.extend(o['operating_values'].values())
    for n in o['nodes']:values.extend(n['position']);values.extend(np.ravel(n['rotation']))
    for s in o['sensors']:
        for k in ('position_body','displacement_body','strain','force_local','curvature_change'):values.extend(s[k])
    if 'frequency' in result:
        for row in result['frequency']['samples']:
            d=row['responses'][0]['output']['sensors'][1]['displacement_body'];values.extend(d['real']);values.extend(d['imag'])
        values.append(result['continued']['operating_values']['power.1'])
    return np.asarray(values)


def main():
    paths=sorted((ROOT/'openswing').glob('*.py'))+[Path(__file__),ROOT/'examples/instrumented-oscillator.asw']
    hashes={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    cases=[]
    for spec in specifications():
        result=compute(spec);checks=verify(spec,result);cases.append(dict(specification=spec,result=result,checks=checks));print(spec['name'],checks,flush=True)
    coarse,fine=[c['checks']['continuum_torque_relative_error'] for c in cases if c['specification']['name'].startswith('curved_beam_')]
    assert fine<.27*coarse and fine<.003,(coarse,fine)
    (ROOT/'docs/validation/custom-trim.json').write_text(json.dumps(dict(description='Custom coupled trim: independent spring compliance, strain, gust vectors, feedback and allocation; finite-rotation circular-arc inversion and continuum refinement; saved harmonic response and units.',source_sha256=hashes,python=platform.python_version(),numpy=np.__version__,scipy=scipy.__version__,cases=cases),indent=2)+'\n')
    print('All native custom-trim checks passed.',flush=True)


if __name__=='__main__':main()
