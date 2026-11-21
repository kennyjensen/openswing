"""Independent initial-state transforms, controllers and unit/refinement checks."""
import hashlib
import json
import platform
import sys
import time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import numpy as np
import scipy
from openswing.bridge import dispatch
from openswing.asw import parse_asw
from openswing.geometry import model_meshes
from openswing.circulation import CirculationBasis


def requests():
    spring=(ROOT/'examples/instrumented-oscillator.asw').read_text()
    profiles=json.loads((ROOT/'examples/initial-spring.json').read_text())
    cases=[]
    for name,panels,shift,step,unit_time in [('spring-4',4,0,1e-5,1),('spring-8-shifted',8,.7,1e-5,1),
            ('spring-custom-step',dict(default=4,beams={'1':dict(nodes=[0,.03,.41,1.61,2])}),0,3e-6,1),('spring-milliseconds',4,.7,1e-5,.001)]:
        source=spring;inputs=json.loads(json.dumps(profiles))
        if unit_time!=1:
            source=source.replace('T 1 s','T .001 s').replace('9.80665 1.225 340.294','0.00000980665 1225000 .340294').replace('1000 .02','1000 20')
            inputs[1]['state']['beam_fields'][0]['velocity'][-1][2]*=unit_time
        cases.append(dict(name=name,unit_time=unit_time,request=dict(action='frequency',source=source,panels=panels,
            condition=dict(speed=10*unit_time,alpha=0,mach=0,powers={'1':3}),gravity=[0,0,0],
            frequency=dict(frequencies=(np.array([0,1,10,30,100])*unit_time).tolist(),inputs=['power.1',*inputs],initial_shift=shift*unit_time,step=step))))
    for kind in ('integral','lag','unstable'):
        state=dict(beam_fields=[dict(beam=1,displacement=[[0,0,0,0],[2,0,.002,0]],velocity=[[0,0,0,0],[2,0,.01,0]])])
        if kind=='integral':
            control=dict(commands={'RY[2]':2},outputs=[dict(actuator='E1',terms=[dict(input='RY[2]',gain=-200),dict(input='RY[2]',gain=-100,mode='integral')])])
            state['feedback']=dict(integrals={'RY[2]':.003})
        elif kind=='lag':
            control=json.loads((ROOT/'examples/actuator-lag-controller.json').read_text());control['commands']={'RY[2]':2,'UY[2]':0}
            state['feedback']=dict(states={'lag':.1})
        else:control=dict(commands={'RY[2]':2},outputs=[dict(actuator='E1',terms=[dict(input='RY[2]',gain=800)])])
        cases.append(dict(name=kind,request=dict(action='frequency',source=spring,panels=4,
            condition=dict(speed=10,alpha=0,mach=0),gravity=[0,0,0],frequency=dict(frequencies=[0,5,30],initial_shift=12 if kind=='unstable' else .3,
            inputs=[dict(kind='initial',name=kind,state=state)],controller=control))))
    body=(ROOT/'examples/guided-body.asw').read_text()+'\nEngine\n1 0 1 0 0 0 0 1 0 0 1 0 -1 0 0\nEnd\n'
    cases.append(dict(name='free-velocity',request=dict(action='frequency',source=body,panels=4,condition=dict(speed=10,alpha=0,mach=0),gravity=[0,0,0],
        frequency=dict(frame='free',frequencies=[0,1,5],initial_shift=.7,inputs=['power.1',dict(kind='initial',name='Velocity',state=dict(frame=dict(velocity_origin_body=[1,0,0])))]))))
    source=(ROOT/'examples/rectangular.asw').read_text().split('t dCLdF1')[0]+'End\n'
    source=source.replace('6 0 6 0','100000 0 100000 0').replace('6 .008','100000 .008').replace('.008','0').replace('12 1 12','200000 1 200000')
    basis=CirculationBasis(model_meshes(parse_asw(source),8),{1:1});gamma=basis.decode(np.array([.1])).tolist()
    cases.append(dict(name='fourier-circulation',gamma=gamma,request=dict(action='frequency',source=source,panels=8,
        condition=dict(speed=30,alpha=0,mach=0,stall=False,circulation_modes={'1':1}),gravity=[0,0,0],
        frequency=dict(frequencies=[0,5,30],inputs=[dict(kind='initial',name='Circulation',state=dict(circulation=gamma))]))))
    return cases


def verify(case,result):
    name=case['name'];errors=[];values=[]
    def z(v):return np.asarray(v['real'])+1j*np.asarray(v['imag'])
    def close(actual,expected,tolerance=2e-8):
        a,b=np.asarray(actual),np.asarray(expected)
        difference=float(np.max(abs(a-b)/np.maximum(1.,abs(b)),initial=0.))
        assert difference<tolerance,(name,difference,tolerance)
        values.extend(a.real.ravel().tolist());values.extend(a.imag.ravel().tolist());errors.append(difference)
    for sample in result['samples']:
        w=sample['omega']
        if name.startswith('spring'):
            unit=case['unit_time'];mass=2/unit**2;damping=10/unit
            for i,(q0,v0) in enumerate(((.002,0),(0,.01*unit)),1):
                s=result['inputs'][i]['laplace_shift']+1j*w;den=mass*s*s+damping*s+500
                q=((mass*s+damping)*q0+mass*v0)/den;v=s*q-q0;acc=s*v-v0;o=sample['responses'][i]['output']
                close(z(o['nodes'][-1]['displacement'])[1],q);close(z(o['nodes'][-1]['velocity'])[1],v)
                close(z(o['sensors'][-1]['acceleration_sensor'])[1],acc)
                close(z(o['sections'][-1]['force_local'])[1],500*q+damping*v)
                close(z(o['global']['applied_force'])+z(o['global']['support_force']),0)
            close(z(sample['responses'][0]['output']['nodes'][-1]['displacement'])[1],1/(500-mass*w*w+1j*damping*w))
        elif name in ('integral','lag','unstable'):
            s=result['inputs'][0]['laplace_shift']+1j*w
            if name=='integral':a=np.array([[0,1,0],[-350,-5,-50],[1,0,0.]]);initial=[.002,.01,.003]
            elif name=='lag':a=np.array([[0,1,0],[-250,-5,.5],[-4000,-400,-20.]]);initial=[.002,.01,.1]
            else:a=np.array([[0,1],[150,-5.]]);initial=[.002,.01]
            exact=np.linalg.solve(s*np.eye(len(a))-a,initial);o=sample['responses'][0]['output']
            close(z(o['nodes'][-1]['displacement'])[1],exact[0]);close(z(o['nodes'][-1]['velocity'])[1],exact[1])
            close(z(o['sensors'][-1]['acceleration_sensor'])[1],s*exact[1]-initial[1])
            actuator=(-200*exact[0]-100*exact[2]) if name=='integral' else exact[2] if name=='lag' else 800*exact[0]
            close(z(o['feedback']['actuators_E1']),actuator)
            if name!='unstable':close(z(o['feedback']['integrals_RY[2]' if name=='integral' else 'states_lag']),exact[2])
            if name=='lag':close(z(o['feedback']['state_rates_lag']),s*exact[2]-initial[2])
        elif name=='free-velocity':
            s=.7+1j*w;o=sample['responses'][1]['output']
            close(z(o['frame']['position_earth']),[1/s**2,0,0]);close(z(o['frame']['velocity_origin_body']),[1/s,0,0])
            close(z(o['operating']['acceleration.x']),0)
            if w==0:assert sample['resolved_inputs']==1 and not sample['responses'][0]['converged']
            else:close(z(sample['responses'][0]['output']['frame']['position_earth'])[0],-1/w**2)
        else:
            close([z(row['circulation']) for row in sample['responses'][0]['output']['strips']],np.array(case['gamma'])/(15+1j*w),2e-6)
        assert all(value is None or value<1e-9 for value in sample['diagnostics']['backward_errors'])
    info=result['diagnostics']['initial_conditions']
    assert info['full_equation_backward_error']<1e-9
    assert all(c['kind']!='initial' or c['consistency']['dynamic_coordinate_mismatch']<1e-7 for c in result['inputs'])
    if name=='unstable':close(info['spectral_abscissa'],10,1e-7)
    return dict(physical_values=values,maximum_independent_scaled_difference=max(errors),finite_dimension=info['finite_dimension'],spectral_abscissa=info['spectral_abscissa'])


def main():
    examples=['instrumented-oscillator.asw','initial-spring.json','actuator-lag-controller.json','guided-body.asw','rectangular.asw']
    files=[Path(__file__),*(ROOT/'examples'/name for name in examples),*sorted((ROOT/'openswing').glob('*.py'))]
    hashes={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    versions=dict(python=platform.python_version(),numpy=np.__version__,scipy=scipy.__version__)
    key=hashlib.sha256(json.dumps(dict(hashes=hashes,versions=versions),sort_keys=True).encode()).hexdigest()
    cache=ROOT/'.reference/initial-response'/key;cache.mkdir(parents=True,exist_ok=True);cases=[]
    for case in requests():
        start=time.monotonic();file=cache/(case['name']+'.json')
        if file.exists():result=json.loads(file.read_text())
        else:
            result=dispatch(case['request']);file.write_text(json.dumps(result,allow_nan=False)+'\n')
        checks=verify(case,result);cases.append(dict(**case,result=result,checks=checks))
        print(case['name'],{k:v for k,v in checks.items() if k!='physical_values'},f'{time.monotonic()-start:.1f}s',flush=True)
    record=dict(description='One-sided initial-state Laplace transforms of original mechanical, controlled, free-flight and circulation models. Independent ODE formulas, rate-boundary terms, loaded bases, material meshes, difference steps and time-unit changes. No ASWING executable comparison.',source_sha256=hashes,versions=versions,cases=cases)
    (ROOT/'docs/validation/initial-response.json').write_text(json.dumps(record,indent=2,allow_nan=False)+'\n')
    print('Wrote docs/validation/initial-response.json',flush=True)


if __name__=='__main__':main()
