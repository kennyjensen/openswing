"""Independent weighted-control references and source-hashed native/WASM study."""
import hashlib,json,platform,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import numpy as np
import scipy
from scipy.optimize import minimize_scalar
from openswing.bridge import dispatch


def specifications():
    thrust=(ROOT/'examples/redundant-thrust.asw').read_text()
    common=dict(action='solve',mode='mounted',panels=4,source=thrust,gravity=[0,0,0],condition=dict(speed=10,alpha=0,mach=0))
    controls=[dict(variable='power.1',quantity='force.x',target=20),dict(variable='power.2',quantity='minimum_control',weight=4),dict(variable='power.3',quantity='minimum_control',weight=2)]
    out=[dict(name='weighted_force',request=dict(common,operating_constraints=controls))]
    trim=[dict(x,preferred=p) for x,p in zip(controls,[1,-.5,2])];trim[1]=dict(trim[1],quantity='moment.z',target=0)
    out.append(dict(name='force_moment_preferred',request=dict(common,operating_constraints=trim)))
    out.append(dict(name='closed_loop',request=dict(common,operating_constraints=controls[:2],controller=dict(outputs=[dict(actuator='E3',expression='2')]))))
    start=thrust.index('Engine\n');end=thrust.index('End\n',start)+4
    disks=thrust[:start]+'Engine\n1 1 1 0 0 -1 0 -1 0 0 0 0 -.3 80 0\n2 1 1 0 0 1 0 -1 0 0 0 0 -.5 80 0\nEnd\n'+thrust[end:]
    out.append(dict(name='nonlinear_disks',request=dict(common,source=disks,condition=dict(common['condition'],density=1.225),operating_constraints=[dict(variable='power.1',quantity='force.x',target=-20),dict(variable='power.2',quantity='minimum_control',weight=3)])))
    flexible=(ROOT/'examples/flexible.asw').read_text().rsplit('End',1)[0]+'t dCLdF1 dCMdF1 dCLdF2 dCMdF2 dCLdF3 dCMdF3\n0 .03 -.004 .06 -.008 -.03 .004\n8 .03 -.004 .06 -.008 -.03 .004\nEnd\n'
    # Fixed CL target; proportional flap influence makes allocation ratios exact
    # even when the common structure and lifting-line solution are nonlinear.
    out.append(dict(name='elastic_flaps',request=dict(common,source=flexible,condition=dict(speed=18,alpha=3,mach=0),operating_constraints=[dict(variable='control.1',quantity='CL',target=.45),dict(variable='control.2',quantity='minimum_control',weight=4),dict(variable='control.3',quantity='minimum_control',weight=2)])))
    spring=(ROOT/'examples/instrumented-oscillator.asw').read_text().replace('1 0 1 2 0 2 0 0 1 0 1 0 -1 0 0','1 0 1 2 0 2 0 0 1 0 1 0 -1 0 0\n2 0 1 2 0 2 0 0 1 0 2 0 -1 0 0')
    out.append(dict(name='saved_spring',request=dict(common,source=spring,operating_constraints=[dict(variable='power.1',quantity='force.y',target=5),dict(variable='power.2',quantity='minimum_control',weight=4)])))
    # A common weight multiplier and a changed unit of time leave setting-based
    # allocation invariant for proportional engines with force/setting gains.
    milli=thrust.replace('T 1 s','T 1 ms').replace('9.80665 1.225 340.294','9.80665e-6 1.225e6 .340294')
    out.append(dict(name='milliseconds_weight_scale',request=dict(common,source=milli,condition=dict(common['condition'],speed=.01),operating_constraints=[dict(x,weight=x.get('weight',1)*17) for x in controls])))
    return out


def compute(spec):
    req=spec['request'];result=dict(static=dispatch(req))
    if spec['name']=='saved_spring':
        result['frequency']=dispatch(dict(req,action='frequency',frequency=dict(initial_state=result['static']['equilibrium_state'],frequencies=[0,10,16],inputs=['power.2'])))
    json.dumps(result,allow_nan=False);return result


def verify(spec,result):
    count=0;integration=0;maximum=0.
    def close(actual,expected,tol=5e-6,independent=True):
        nonlocal count,integration,maximum
        a,b=np.asarray(actual),np.asarray(expected);error=float(np.max(abs(a-b)/np.maximum(1.,abs(b))))
        if independent:count+=a.size*(2 if np.iscomplexobj(a) else 1)
        else:integration+=a.size
        maximum=max(maximum,error);assert error<tol,(spec['name'],a,b,error)
    out=result['static'];name=spec['name'];r=out['control_allocation'];values=out['operating_values']
    close(r['equality_residual'],0,1e-8,False);assert r['normalized_stationarity']<2e-6 and min(r['reduced_curvatures'])>0
    if name in ('weighted_force','milliseconds_weight_scale'):
        expected=np.array([40,5,10])/4.75
        close([values[f'power.{k}'] for k in (1,2,3)],expected);close(out['applied_force'],[20,0,0],1e-8)
        close(r['objective'],.5*np.sum(np.array([1,4,2])*expected**2)*(17 if name=='milliseconds_weight_scale' else 1),1e-9)
    elif name=='force_moment_preferred':
        a=np.array([[2,1,1],[2,-1,0.]]);w=np.array([1,4,2]);p=np.array([1,-.5,2.]);b=np.array([20,0.])
        expected=p+(a.T/w[:,None])@np.linalg.solve((a/w)@a.T,b-a@p)
        close([values[f'power.{k}'] for k in (1,2,3)],expected);close([out['applied_force'][0],out['applied_moment'][2]],b,1e-8)
    elif name=='closed_loop':
        close([values['power.1'],values['power.2']],np.array([36,4.5])/4.25)
        close(out['feedback']['actuators']['E3'],2,1e-9);close(out['applied_force'][0],20,1e-8)
    elif name=='nonlinear_disks':
        def power(t,radius):
            dv=np.sqrt(100+2*t/(1.225*np.pi*radius**2))-10
            return t*(10+(1+5*(10/(80*radius))**2)*dv/2)
        optimum=minimize_scalar(lambda t:.5*(power(t,.3)**2+3*power(20-t,.5)**2),bounds=(0,20),method='bounded',options=dict(xatol=1e-11))
        close([values['power.1'],values['power.2']],[power(optimum.x,.3),power(20-optimum.x,.5)])
        close(r['objective'],optimum.fun,1e-9);close(out['applied_force'][0],-20,1e-8)
    elif name=='elastic_flaps':
        u=np.array([values[f'control.{k}'] for k in (1,2,3)]);total=u@np.array([1,2,-1])
        close(u,total*np.array([1,.5,-.5])/2.5);close(out['CL'],.45,1e-8,False);assert out['max_displacement']>1e-3
    else:
        close([values['power.1'],values['power.2']],[2.5,1.25]);close(out['sensors'][1]['displacement_body'][1],.01,1e-9)
        response=result['frequency'];assert response['base']['control_allocation']['free_directions']==1
        close(response['base']['sensors'][1]['displacement_body'][1],.01,1e-9)
        for row in response['samples']:
            d=row['responses'][0]['output']['nodes'][-1]['displacement'];w=row['omega']
            close(d['real'][1]+1j*d['imag'][1],2/(500+10j*w-2*w*w),1e-9)
    return dict(independent_scalar_checks=count,integration_checks=integration,maximum_scaled_error=maximum)


def physical(result):
    out=result['static'];values=[]
    for key in ('force','moment','support_force','support_moment'):values.extend(out[key])
    values.extend(out['operating_values'].values())
    for node in out['nodes']:values.extend(node['position'])
    values.append(out['control_allocation']['objective'])
    if 'frequency' in result:
        for row in result['frequency']['samples']:
            d=row['responses'][0]['output']['nodes'][-1]['displacement'];values.extend(d['real']);values.extend(d['imag'])
    return np.asarray(values)


def main():
    paths=sorted((ROOT/'openswing').glob('*.py'))+[Path(__file__),*[ROOT/'examples'/name for name in ('redundant-thrust.asw','flexible.asw','instrumented-oscillator.asw')]]
    hashes={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    cases=[]
    for spec in specifications():
        result=compute(spec);checks=verify(spec,result);cases.append(dict(specification=spec,result=result,checks=checks));print(spec['name'],checks,flush=True)
    (ROOT/'docs/validation/control-allocation.json').write_text(json.dumps(dict(description='Hard-equation weighted control trim: independent projections, nonlinear disk momentum, elastic proportional flaps, controller-owned actuator, units and saved spring response.',source_sha256=hashes,python=platform.python_version(),numpy=np.__version__,scipy=scipy.__version__,cases=cases),indent=2)+'\n')
    print('All native control-allocation checks passed.',flush=True)


if __name__=='__main__':main()
