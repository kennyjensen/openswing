"""Independent flutter progression, scaling and scheduled-feedback checks."""
import hashlib,json,platform,runpy,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
import scipy
from scipy.optimize import brentq
from openswing.asw import parse_asw
from openswing.aero import FlightCondition
from openswing.stability import solve_stability
benchmark=runpy.run_path(str(Path(__file__).with_name('modal-benchmark.py')))
files=[Path(__file__).resolve(),Path(__file__).with_name('modal-benchmark.py').resolve(),
       Path('examples/instrumented-oscillator.asw').resolve(),*sorted(Path('openswing').resolve().glob('*.py'))]
provenance=dict(versions=dict(python=platform.python_version(),numpy=np.__version__,scipy=scipy.__version__),
    source_sha256={str(p.relative_to(Path.cwd())):hashlib.sha256(p.read_bytes()).hexdigest() for p in files})
checkpoint=Path('.reference/stability-verification-checkpoint.json')
saved=json.loads(checkpoint.read_text()) if checkpoint.exists() else {}
cache=saved.get('cases',{}) if saved.get('provenance')==provenance else {}


def record(key,compute):
    if key in cache:print('Resumed '+key,flush=True);return cache[key]
    out=compute();cache[key]=out
    temp=checkpoint.with_suffix('.tmp');temp.write_text(json.dumps(dict(provenance=provenance,cases=cache),allow_nan=False));temp.replace(checkpoint)
    print(key+': '+json.dumps(out.get('comparison',{})),flush=True);return out


def flutter(span,panels=4,step=1e-6,rank=1e-9):
    model=benchmark['configuration'](span)
    out=solve_stability(model,FlightCondition(speed=40,alpha=0,mach=0,stall=False),panels,gravity=[0,0,0],
        values=[40,45,50],modes=dict(count=panels+4,step=step,rank_tolerance=rank),
        parameter_rtol=1e-4,growth_tolerance=1e-6,
        progress=lambda stage,i,n:print(f'span={span} panels={panels} point {i}',flush=True) if stage=='point' else None)
    assert out['converged'] and out['spectrum_complete']
    assert len(out['boundaries'])==1 and out['boundaries'][0]['status']=='resolved',out['boundaries']
    b=out['boundaries'][0];root=complex(*b['eigenvalue'])
    exact=benchmark['typical_section']
    critical=brentq(lambda v:max(x.real for x in exact(v) if x.imag>1),40,60,xtol=1e-10)
    exact_root=max((v for v in exact(critical) if v.imag>1),key=lambda v:v.real)
    assert abs(root.real)<1e-6*abs(root) and b['bracket'][1]-b['bracket'][0]<1e-4*b['value']
    return dict(source=model.dumps(),panels=panels,step=step,rank_tolerance=rank,result=out,
        comparison=dict(independent_2d_critical_speed=float(critical),independent_2d_frequency=float(exact_root.imag),
                        computed_critical_speed=b['value'],computed_frequency=root.imag,
                        speed_error=float(abs(b['value']-critical)),frequency_error=float(abs(root.imag-exact_root.imag))))


def time_units(reference):
    # Same physical aircraft, represented in a two-second input time unit.
    # Input velocity doubles, g quadruples, density divides by four.
    model=benchmark['configuration'](40);source=model.dumps().replace('T 1 s','T 2 s').replace('9.80665 1.225 340.294','39.2266 0.30625 680.588')
    assert source!=model.dumps()
    out=solve_stability(parse_asw(source),FlightCondition(speed=80,alpha=0,density=.30625,mach=0,stall=False),4,
        gravity=[0,0,0],values=[80,90,100],modes=dict(count=8,step=1e-6),refine=False,
        progress=lambda stage,i,n:print(f'time units point {i}',flush=True) if stage=='point' else None)
    assert out['converged'] and out['tracking_complete'] and out['spectrum_complete']
    errors=[]
    for a,b in zip(reference['result']['points'][:3],out['points']):
        old=np.array([complex(*r['eigenvalue']) for r in a['result']['modes']]);new=np.array([complex(*r['eigenvalue'])/2 for r in b['result']['modes']])
        errors.append(float(max(min(abs(new-v)) for v in old)))
    assert max(errors)<1e-5,errors
    assert out['boundaries'][0]['bracket']==[90,100]
    return dict(source=source,result=out,comparison=dict(maximum_root_error_per_second=max(errors)))


def feedback():
    source=Path('examples/instrumented-oscillator.asw').read_text()
    # Positive velocity feedback: 2 ydd + (30-V) yd + 500 y = 0.
    # The independent crossing is V=30, omega=sqrt(250), with stable stiffness.
    law=dict(outputs=[dict(actuator='E1',expression="(speed-20)*error('UY[2]')")])
    out=solve_stability(parse_asw(source),FlightCondition(speed=25,alpha=0,mach=0),4,
        gravity=[0,0,0],values=[25,35],modes=dict(count=2,controller=law),
        progress=lambda stage,i,n:print(f'feedback point {i}',flush=True) if stage=='point' else None)
    assert out['converged'] and out['tracking_complete']
    assert len(out['boundaries'])==1 and out['boundaries'][0]['status']=='resolved',out['boundaries']
    boundary=out['boundaries'][0];errors=[]
    for point in out['points']:
        expected=np.roots([2,30-point['value'],500]);actual=complex(*point['roots'][0]['eigenvalue'])
        errors.append(float(min(abs(expected-actual))))
    assert max(errors)<2e-6,errors
    assert abs(boundary['value']-30)<1e-5
    return dict(source=source,controller=law,result=out,comparison=dict(independent_speed=30.,independent_frequency=float(np.sqrt(250)),
        computed_critical_speed=boundary['value'],maximum_root_error=max(errors)))


if __name__=='__main__':
    cases={}
    cases['span40']=record('span40',lambda:flutter(40))
    cases['span80']=record('span80',lambda:flutter(80,rank=1e-10))
    assert cases['span80']['comparison']['speed_error']<.65*cases['span40']['comparison']['speed_error']
    cases['mesh8']=record('mesh8',lambda:flutter(40,panels=8,rank=1e-10))
    cases['time_units']=record('time_units',lambda:time_units(cases['span40']))
    cases['feedback']=record('feedback',feedback)
    Path('docs/validation/stability.json').write_text(json.dumps(dict(description='Full-model root progression and bracket refinement with independent 2D/feedback references.',
        **provenance,cases=cases,limitations=['The independent 2D reference uses the published empirical circulation lag, not Theodorsen flow or measured flutter.',
            'Finite-span effects remain; span refinement is distinct from spatial mesh and tangent refinement.',
            'The feedback crossing is a mechanical control instability, not aerodynamic flutter.',
            'No ASWING executable or experimental aircraft agreement is established.']),indent=2,allow_nan=False)+'\n')
    print(f'Completed {len(cases)} stability cases with {len(provenance["source_sha256"])} source hashes.',flush=True)
