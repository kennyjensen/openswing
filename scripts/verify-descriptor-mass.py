"""Loaded-aircraft derivative rank, complete spectra and physical tangent checks."""
import hashlib,json,platform,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import numpy as np
import scipy
from scipy.linalg import svdvals
from scipy.optimize import linear_sum_assignment
from openswing.asw import parse_asw
from openswing.aero import FlightCondition
from openswing.linear_dynamics import make_system,linearize,eigensystem,complex_data,output_perturbation
from openswing.initial_response import ConsistentSubspace
from openswing.frequency_response import harmonic_solve


def cases():
    wing=(ROOT/'examples/flexible.asw').read_text();spring=(ROOT/'examples/instrumented-oscillator.asw').read_text()
    result=[]
    for name,panels,step,tol,unit,fourier in [('wing-4',4,1e-5,1e-9,1,True),('wing-4-refined',4,3e-6,1e-11,1,True),
        ('wing-8',8,1e-5,1e-11,1,True),('wing-8-refined',8,3e-6,1e-11,1,True),
        ('wing-milliseconds',4,1e-5,1e-9,.001,True),('wing-pointwise',4,1e-5,1e-9,1,False)]:
        source=wing
        if unit!=1:source=source.replace('T 1 s','T .001 s').replace('9.80665 1.225 340.294','0.00000980665 1225000 .340294')
        result.append(dict(name=name,source=source,panels=panels,step=step,rank_tolerance=tol,time_unit=unit,
            condition=dict(speed=30*unit,alpha=4,mach=0,circulation_modes={'1':3} if fourier else {})))
    result.append(dict(name='smooth-accelerometer',source=spring,panels=4,step=1e-5,rank_tolerance=1e-9,time_unit=1,
        condition=dict(speed=10,alpha=0,mach=0),controller=dict(outputs=[dict(actuator='E1',expression="command('E1')-3*tanh(2*error('Ay[2]'))")]),expected_roots=np.roots([8,10,500]).tolist()))
    # A second tip sensor makes a physically identical, but syntactically distinct, signal.
    lines=spring.splitlines();at=lines.index('Sensor');end=lines.index('End',at)
    row=lines[end-1].split();row[0]='3';lines.insert(end,' '.join(row));source='\n'.join(lines)+'\n'
    result.append(dict(name='coincident-sensor-composite',source=source,panels=4,step=1e-5,rank_tolerance=1e-9,time_unit=1,
        condition=dict(speed=10,alpha=0,mach=0),controller=dict(outputs=[dict(actuator='E1',expression="abs(measurement('Ay[2]')-measurement('Ay[3]'))")]),expected_roots=np.roots([2,10,500]).tolist()))
    # Keep the on-disk specification pure JSON.
    for spec in result:
        if 'expected_roots' in spec:spec['expected_roots']=[[v.real,v.imag] for v in spec['expected_roots']]
    return result


def compute(spec, phase_index=None):
    system,_=make_system(parse_asw(spec['source']),FlightCondition(**spec['condition']),spec['panels'],gravity=[0,0,0],controller=spec.get('controller'))
    a,m=linearize(system,step=spec['step']);base=system.base_report();zero=np.zeros(system.size)
    modes,meta=eigensystem(a,m,time_scale=system.W,count=1000,rank_tolerance=spec['rank_tolerance'])
    roots=np.array([complex(*v['eigenvalue']) for v in modes]);space=ConsistentSubspace(a,m,system.dynamic_indices,system.W,spec['rank_tolerance'])
    assert meta['finite_dimension']==space.report['finite_dimension']==len(roots)
    assert max(max(v['left_backward_error'],v['right_backward_error']) for v in modes)<1e-9
    rng=np.random.default_rng(13);d=zero.copy();d[system.dynamic_indices]=rng.normal(size=len(system.dynamic_indices))*system.W
    odd=[]
    for h in (.1,.7,2.):
        derivative=(system.residual(zero,h*d)-system.residual(zero,-h*d))/(2*h)
        error=float(np.max(abs((derivative+m@d)[:system.feedback_start])))
        assert error<2e-11,error
        odd.append(error)
    if 'expected_roots' in spec:
        for value in spec['expected_roots']:assert min(abs(roots-complex(*value)))<1e-7
    else:assert base['max_displacement']>.01
    selected=next(v for v in modes if v['eigenvalue'][1]>1e-3*spec['time_unit'])
    # Symmetric wings have tied maximum components. The eigensolver's valid
    # largest-component pivot can select opposite tips on different runtimes.
    # Define the initial disturbance with one explicit state-coordinate phase
    # anchor, and reuse that anchor in the cross-platform comparison.
    vector=selected['right']
    if phase_index is None:phase_index=int(np.flatnonzero(abs(vector)>.5*np.max(abs(vector)))[0])
    assert abs(vector[phase_index])>.25*np.max(abs(vector))
    v=vector/vector[phase_index]*.001;value=complex(*selected['eigenvalue'])
    initial,rate,consistency=space.complete(v.real)
    np.testing.assert_allclose(initial,v.real,atol=1e-9,rtol=1e-7)
    outputs=[];maximum=0.;shift=(max(0,space.growth/spec['time_unit'])+100)*spec['time_unit']
    for w in np.array([0.,5.,50.])*spec['time_unit']:
        s=shift+1j*w;x,checks=harmonic_solve(a,m,m@initial,w,shift=shift)
        exact=.5*(v/(s-value)+v.conj()/(s-value.conjugate()))
        error=float(np.max(abs(x-exact)/np.maximum(1.,abs(exact))));assert error<1e-8,error
        maximum=max(maximum,error)
        out=output_perturbation(system,x,s*x-initial,spec['step'])
        outputs.append(dict(omega=float(w),shift=shift,state=complex_data(x),output=out,backward_error=checks['backward_errors'][0]))
    rows=np.maximum(np.maximum(np.linalg.norm(a,axis=1),np.linalg.norm(m*system.W,axis=1)),1e-30)
    singular=svdvals(m*system.W/rows[:,None]);rank=int(np.sum(singular>spec['rank_tolerance']*max(np.linalg.norm(a/rows[:,None],2),np.linalg.norm(m*system.W/rows[:,None],2),1)))
    return dict(base=base,roots=complex_data(roots),finite_dimension=len(roots),mass=complex_data(m),
        mass_singular_values=singular.tolist(),mass_rank=rank,largest_discarded_derivative=float(singular[rank]) if rank<len(singular) else 0.,
        maximum_odd_residual_error=max(odd),maximum_initial_resolvent_error=maximum,initial_consistency=consistency,
        initial_mode=dict(phase_index=phase_index,eigenvalue=selected['eigenvalue'],right=complex_data(v)),
        initial_spectra=outputs,derivative_linearization=system.derivative_diagnostics,spectrum=meta)


def root_error(first,second,scale=1.):
    def z(x):return np.array(x['roots']['real'])+1j*np.array(x['roots']['imag'])
    a,b=z(first),z(second)/scale;assert a.shape==b.shape
    cost=abs(a[:,None]-b[None,:])/np.maximum(1.,abs(a[:,None]));i,j=linear_sum_assignment(cost)
    return float(max(cost[i,j]))


def main():
    files=[Path(__file__),ROOT/'examples/flexible.asw',ROOT/'examples/instrumented-oscillator.asw',*sorted((ROOT/'openswing').glob('*.py'))]
    hashes={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    versions=dict(python=platform.python_version(),numpy=np.__version__,scipy=scipy.__version__)
    key=hashlib.sha256(json.dumps(dict(hashes=hashes,versions=versions),sort_keys=True).encode()).hexdigest()
    cache=ROOT/'.reference/descriptor-mass'/key;cache.mkdir(parents=True,exist_ok=True);rows=[]
    for spec in cases():
        start=time.monotonic();file=cache/(spec['name']+'.json')
        if file.exists():result=json.loads(file.read_text())
        else:result=compute(spec);file.write_text(json.dumps(result,allow_nan=False)+'\n')
        rows.append(dict(specification=spec,result=result))
        print(spec['name'],result['finite_dimension'],result['maximum_odd_residual_error'],result['largest_discarded_derivative'],f'{time.monotonic()-start:.1f}s',flush=True)
    results={r['specification']['name']:r['result'] for r in rows}
    comparisons={name:root_error(results[a],results[b],scale) for name,a,b,scale in [('four-interval refinement','wing-4','wing-4-refined',1),('eight-interval refinement','wing-8','wing-8-refined',1),('input time units','wing-4','wing-milliseconds',.001)]}
    assert max(comparisons.values())<1e-6,comparisons
    record=dict(description='Physical load-coefficient extraction: original loaded swept/twisted flexible wing, mesh/step/rank/unit variations, smooth accelerometer and coincident-sensor controller laws. Full-pencil residual and initial-mode resolvent identities are internal consistency checks, not external ASWING parity.',source_sha256=hashes,versions=versions,cases=rows,comparisons=comparisons)
    (ROOT/'docs/validation/descriptor-mass.json').write_text(json.dumps(record,indent=2,allow_nan=False)+'\n')
    print('Wrote descriptor-mass.json',comparisons,flush=True)


if __name__=='__main__':main()
