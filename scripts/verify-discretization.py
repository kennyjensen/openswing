"""Reproduce material-mesh refinement, oscillator dynamics and portable states."""
import hashlib
import json
import platform
import sys
import time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import numpy as np
import scipy
from openswing.bridge import dispatch
from openswing.time_state import checkpoint


def requests():
    rod = 'Name\nOriginal circular-arc check\nEnd\nUnit\nL 1 m\nT 1 s\nF 1 N\nEnd\nConstant\n9.80665 1.225 340.294\nEnd\nReference\n2 1 2\nEnd\nGround\n1 0 0\nEnd\nBeam 1\nRod\nt y EIcc\n0 0 100\n2 2 100\nEnd\n'
    spring = (ROOT/'examples/instrumented-oscillator.asw').read_text()
    wing = (ROOT/'examples/rectangular.asw').read_text()
    cases = []
    for spacing in ('cosine', 'uniform', 'custom'):
        for n in (4, 8, 16):
            spec = dict(nodes=(2*np.linspace(0, 1, n+1)**1.4).tolist()) if spacing == 'custom' else dict(count=n, spacing=spacing)
            cases.append(dict(name=f'arc-{spacing}-{n}', request=dict(action='solve', mode='mounted', source=rod,
                panels=dict(default=4, beams={'1': spec}), condition=dict(alpha=0, mach=0), gravity=[0,0,0],
                loads=[dict(beam=1, t=2, moment=[50*np.pi/2, 0, 0])])) )
    custom = dict(default=4, beams={'1': dict(nodes=[0, .03, .41, 1.61, 2])})
    cases.append(dict(name='spring-static', request=dict(action='solve', mode='mounted', source=spring, panels=custom,
        condition=dict(speed=10, alpha=0, mach=0, powers={'1':2}), gravity=[0,0,0])))
    for spacing, panels in [('cosine', 4), ('uniform',dict(default=4,beams={'1':dict(count=4,spacing='uniform')})), ('custom',custom)]:
        cases.append(dict(name=f'spring-bode-{spacing}',request=dict(action='frequency',source=spring,panels=panels,
            condition=dict(speed=10,alpha=0,mach=0),gravity=[0,0,0],frequency=dict(frequencies=[0,1,10,np.sqrt(250),30]))))
    cases.append(dict(name='spring-modes-custom',request=dict(action='modes',source=spring,panels=custom,
        condition=dict(speed=10,alpha=0,mach=0),gravity=[0,0,0],modes=dict(count=6))))
    for modes in (0, 8):
        cases.append(dict(name=f'wing-custom-{modes}',request=dict(action='solve',mode='mounted',source=wing,
            panels=dict(default=4,beams={'1':dict(nodes=[-6,-4.2,-1.1,0,.8,3.7,6])}),
            condition=dict(alpha=5,beta=3,mach=0,controls={'1':2},circulation_modes={'1':modes}),gravity=[0,0,0])))
    return cases


def verify(case, result):
    name = case['name']; metrics = []; errors = []
    def close(actual, expected, tolerance=1e-8):
        a,b = np.asarray(actual), np.asarray(expected)
        difference = float(np.max(abs(a-b)/np.maximum(1.,abs(b)), initial=0.))
        assert difference < tolerance, (name, difference, tolerance)
        errors.append(difference)
    def snapshot(s):
        assert s['residual'] < 1e-8
        metrics.extend(np.asarray([v['position'] for v in s['nodes']]).ravel().tolist())
        metrics.extend(s['force_balance']);metrics.extend(s['moment_balance'])
        close(s['force_balance'], 0, 1e-7);close(s['moment_balance'], 0, 1e-7)
    extra = {}
    if name.startswith('arc-'):
        snapshot(result)
        expected = np.array([0, 4/np.pi, 4/np.pi]);tip = np.array(result['nodes'][-1]['position'])
        error = float(np.linalg.norm(tip-expected))
        assert error < .06
        extra['continuum_tip_error'] = error
        close(result['support_moment'], [-50*np.pi/2, 0, 0])
    elif name == 'spring-static':
        snapshot(result);close(result['nodes'][-1]['position'], [0,2.004,0])
    elif name.startswith('spring-bode'):
        snapshot(result['base'])
        for sample in result['samples']:
            w = sample['omega']; response = sample['responses'][0]['output'];d=response['nodes'][-1]['displacement']
            z = d['real'][1]+1j*d['imag'][1];close(z, 1/(500*(1+1j*.02*w)-2*w*w))
            for node in response['nodes']:
                for key in ('displacement', 'rotation'):
                    metrics.extend(node[key]['real']);metrics.extend(node[key]['imag'])
    elif name == 'spring-modes-custom':
        snapshot(result['base']);roots=sorted([complex(*m['eigenvalue']) for m in result['modes']],key=lambda z:z.imag)
        exact=np.roots([2,10,500])
        # Massless strain-rate equations also retain constitutive relaxation
        # poles at -1/tdeps; these are not extra oscillatory spring modes.
        for value in exact:close(min(abs(np.array(roots)-value)),0,1e-7)
        for value in roots:close(min([*abs(value-exact),abs(value+50)]),0,1e-7)
        metrics.extend([x for z in roots for x in (z.real,z.imag)])
    elif name.startswith('wing-'):
        snapshot(result);metrics.extend(result['force']);metrics.extend(result['moment'])
        metrics.extend(s['circulation'] for s in result['strips'])
        assert result['structural_elements']==8
    elif name in ('spring-launch', 'spring-restart'):
        for s in result['snapshots']:
            snapshot(s);close(s['nodes'][-1]['position'],[0,2.004,0])
            close(s['local_velocity'],0);close(s['local_acceleration'],0,1e-7)
        assert result['restart_context']['setup']['panels']==case['expected_panels']
    else:raise AssertionError(name)
    return dict(physical_values=metrics, maximum_independent_scaled_error=max(errors, default=0.), **extra)


def main():
    files = [Path(__file__), ROOT/'examples/instrumented-oscillator.asw',ROOT/'examples/rectangular.asw', *sorted((ROOT/'openswing').glob('*.py'))]
    hashes = {str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    versions = dict(python=platform.python_version(),numpy=np.__version__,scipy=scipy.__version__)
    key=hashlib.sha256(json.dumps(dict(hashes=hashes,versions=versions),sort_keys=True).encode()).hexdigest()
    cache=ROOT/'.reference/discretization'/key;cache.mkdir(parents=True,exist_ok=True)
    cases=[]
    def run(case):
        start=time.monotonic();path=cache/(case['name']+'.json')
        if path.exists():result=json.loads(path.read_text())
        else:
            result=dispatch(case['request']);path.write_text(json.dumps(result,allow_nan=False)+'\n')
        checks=verify(case,result);cases.append(dict(**case,result=result,checks=checks))
        print(case['name'],{k:v for k,v in checks.items() if k!='physical_values'},f'{time.monotonic()-start:.1f}s',flush=True)
        return result
    for case in requests():run(case)
    seed=next(c for c in cases if c['name']=='spring-static')
    launch=run(dict(name='spring-launch',expected_panels=seed['request']['panels'],request=dict(action='launch_time',
        source=seed['request']['source'],equilibrium_state=seed['result']['equilibrium_state'],time=dict(duration=.02,dt=.01))))
    run(dict(name='spring-restart',expected_panels=seed['request']['panels'],request=dict(action='resume_time',
        source=seed['request']['source'],checkpoint=checkpoint(launch),time=dict(duration=.02))))
    refinement={}
    for spacing in ('cosine','uniform','custom'):
        errors=[c['checks']['continuum_tip_error'] for c in cases if c['name'].startswith('arc-'+spacing)]
        assert errors[1]<.27*errors[0] and errors[2]<.27*errors[1]
        refinement[spacing]=dict(counts=[4,8,16],continuum_tip_errors=errors)
    wings=[c['result'] for c in cases if c['name'].startswith('wing-')]
    np.testing.assert_allclose(wings[0]['force'],wings[1]['force'],rtol=1e-9,atol=1e-8)
    record=dict(description='Original material-mesh verification: continuum circular-arc refinement, damped oscillator spectra/Bode response, full Fourier equivalence and portable steady/time states. No ASWING executable comparison.',source_sha256=hashes,versions=versions,cases=cases,refinement=refinement)
    (ROOT/'docs/validation/discretization.json').write_text(json.dumps(record,indent=2,allow_nan=False)+'\n')
    print('Wrote docs/validation/discretization.json',flush=True)


if __name__=='__main__':main()
