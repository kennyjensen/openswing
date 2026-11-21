"""Reproduce physical closed-loop equilibrium derivatives and their refinement."""
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


def requests():
    spring=(ROOT/'examples/instrumented-oscillator.asw').read_text()
    basic=dict(commands={'RY[2]':2.01},outputs=[dict(actuator='E1',terms=[dict(input='RY[2]',gain=-200)])])
    def mechanical(name,controller=basic,panels=4,step=1e-5,parameters=None):
        return dict(name=name,request=dict(action='solve',mode='mounted',source=spring,panels=panels,
            condition=dict(speed=10,alpha=0,mach=0),gravity=[0,0,0],controller=controller,
            derivatives=dict(parameters=parameters or ['command.E1','command.RY[2]'],step=step)))
    cases=[mechanical('proportional-4'),mechanical('proportional-8',panels=8),mechanical('proportional-step',step=3e-6)]
    pi=dict(commands={'RY[2]':2.01},outputs=[dict(actuator='E1',terms=[dict(input='RY[2]',gain=-200),dict(input='RY[2]',gain=-100,mode='integral')])])
    cases.append(mechanical('integral',pi))
    lag=json.loads((ROOT/'examples/actuator-lag-controller.json').read_text());lag['commands']={'RY[2]':2.01}
    cases.append(mechanical('lag',lag))
    nonlinear=dict(commands={'RY[2]':2.1},outputs=[dict(actuator='E1',residual="actuator('E1')-command('E1')+200*error('RY[2]')+10000*error('RY[2]')**3")])
    cases.append(mechanical('nonlinear',nonlinear))
    scheduled=dict(commands={'RY[2]':2.02},outputs=[dict(actuator='E1',terms=[dict(input='RY[2]',gain=dict(speed=[5,15],density=[0],values=[[-150,-250]]))])])
    cases.append(mechanical('schedule',scheduled,parameters=['speed','u']))
    body='Name\nControlled acceleration verification\nEnd\nUnit\nL 1 m\nT 1 s\nF 1 N\nEnd\nConstant\n9.80665 1.225 340.294\nEnd\nReference\n2 1 2\nEnd\nGround\n1 0 0\nEnd\nWeight\n1 0 0 0 0 9.80665 0 0 0 0 0 19.6133 29.41995 39.2266\nEnd\nEngine\n1 0 1 0 0 0 0 1 0 0 1 0 -1 0 0\nEnd\nBeam 1\nRigid body\nt x y z EIcc EInn GJ EA GKc GKn\n0 0 0 0 0 0 0 0 0 0\n2 0 2 0 0 0 0 0 0 0\nEnd\n'
    acceleration=dict(commands={'V':10,'Ax':0},outputs=[dict(actuator='E1',terms=[dict(input='V',gain=3),dict(input='Ax',gain=-2)])])
    case=mechanical('acceleration',acceleration,parameters=['speed','command.V','command.E1'])
    case['request'].update(source=body,mode='free')
    case['request']['derivatives']['response']='free_flight';cases.append(case)
    wing=(ROOT/'examples/flexible.asw').read_text().rsplit('End',1)[0]+'t dCLdF1 dCMdF1\n0 .08 -.01\n8 .08 -.01\nEnd\n'
    for panels,modes,step in ((4,3,1e-5),(8,3,1e-5),(8,7,1e-5),(8,7,3e-6)):
        controller=dict(commands={'A':1.},outputs=[dict(actuator='F1',terms=[dict(input='A',gain=-.2)])])
        cases.append(dict(name=f'wing-{panels}-{modes}-{step}',request=dict(action='solve',mode='mounted',source=wing,
            panels=panels,condition=dict(alpha=4.,mach=0.,circulation_modes={1:modes},controls={1:2.}),gravity=[0,0,0],
            controller=controller,derivatives=dict(parameters=['alpha','command.F1','command.A'],step=step))))
    return cases


def verify(case,result):
    d=result['derivatives'];name=case['name'];checks=[]
    def close(actual,expected,tolerance=2e-6):
        actual,expected=np.asarray(actual),np.asarray(expected)
        error=float(np.max(abs(actual-expected)/np.maximum(1.,abs(expected)),initial=0.))
        assert error<tolerance,(name,error)
        checks.append(error)
    def row(name):return d['matrices']['feedback'][next(i for i,r in enumerate(d['feedback_rows']) if r['name']==name)]
    assert result['residual']<1e-8 and max(d['linear_residuals'])<1e-8
    if name=='acceleration':
        close(d['matrices']['accelerations'][0],[1,-1,1/3]);close(row('actuators.E1'),[1,-1,1/3])
        close(d['matrices']['net_wrench'],0.)
    elif name.startswith('wing'):
        close(row('actuators.F1'),[-.2*180/np.pi,1,.2])
        assert result['circulation_discretization']['independent_unknowns'] in (3,7)
    else:
        if name=='integral':
            dy=np.array([0.,1.]);close(row('integrals.RY[2]'),[.01,-5.])
        elif name=='nonlinear':
            error=next(v.real for v in np.roots([10000,0,700,50]) if abs(v.imag)<1e-12)
            k=200+30000*error**2;dy=np.array([1,k])/(500+k)
        elif name=='schedule':dy=500*.02*10/700**2*np.array([1,10])
        else:dy=np.array([1,200])/700
        close(np.array(d['matrices']['positions'])[-1,1],dy)
        close(row('actuators.E1'),500*dy)
        if name=='lag':close(row('states.lag'),500*dy);close(row('state_rates.lag'),0.)
    return dict(maximum_scaled_independent_difference=max(checks),linear_residual=max(d['linear_residuals']))


def main():
    files=[Path(__file__),*(ROOT/'examples'/name for name in ('instrumented-oscillator.asw','actuator-lag-controller.json','flexible.asw')),*sorted((ROOT/'openswing').glob('*.py'))]
    hashes={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    versions=dict(python=platform.python_version(),numpy=np.__version__,scipy=scipy.__version__)
    key=hashlib.sha256(json.dumps(dict(hashes=hashes,versions=versions),sort_keys=True).encode()).hexdigest()
    cache=ROOT/'.reference/feedback-derivatives'/key;cache.mkdir(parents=True,exist_ok=True)
    cases=[]
    for case in requests():
        path=cache/(case['name']+'.json');start=time.monotonic()
        if path.exists():result=json.loads(path.read_text())
        else:
            result=dispatch(case['request']);path.write_text(json.dumps(result,allow_nan=False)+'\n')
        checks=verify(case,result)
        cases.append(dict(**case,result=result,checks=checks))
        print(case['name'],checks,f'{time.monotonic()-start:.1f}s',flush=True)
    record=dict(description='Closed-loop quasi-steady derivatives: independent mechanical checks and elastic Fourier mesh/mode/step refinement. No ASWING executable comparison.',
        source_sha256=hashes,versions=versions,cases=cases,
        convention='Trim targets are released. Solved commands stay fixed except the selected command input. Actuators, integrals and custom controller states solve their equilibrium equations; all local and controller state rates remain zero. Axes and coefficient normalizations are frozen at the base.')
    (ROOT/'docs/validation/feedback-derivatives.json').write_text(json.dumps(record,indent=2,allow_nan=False)+'\n')
    print('Wrote docs/validation/feedback-derivatives.json',flush=True)


if __name__=='__main__':main()
