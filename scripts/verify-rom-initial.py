"""Initial-condition ROM verification against independent ODEs and a wing mode."""
import hashlib,json,platform,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import numpy as np
import scipy
from scipy.linalg import expm
from openswing.bridge import dispatch
from openswing.asw import parse_asw
from openswing.aero import FlightCondition
from openswing.linear_dynamics import make_system,linearize,eigensystem,complex_data
from openswing.reduced_model import MeasurementOutputs


def cases():
    source=(ROOT/'examples/instrumented-oscillator.asw').read_text()
    profiles=json.loads((ROOT/'examples/initial-spring.json').read_text());rows=[]
    for name,panels,step,unit in [('spring-4',4,1e-5,1),('spring-8-refined',8,3e-6,1),('spring-milliseconds',4,1e-5,.001)]:
        text=source;inputs=json.loads(json.dumps(profiles))
        if unit!=1:
            text=text.replace('T 1 s','T .001 s').replace('9.80665 1.225 340.294','0.00000980665 1225000 .340294').replace('1000 .02','1000 20')
            inputs[1]['state']['beam_fields'][0]['velocity'][-1][2]*=unit
        g=np.array([[0,1],[-250*unit**2,-5*unit]])
        rows.append(dict(name=name,generator=g.tolist(),physical_initials=[[.002,0],[0,.01*unit]],request=dict(action='rom',source=text,panels=panels,condition=dict(speed=10*unit,alpha=0,mach=0),gravity=[0,0,0],rom=dict(count=2,selected=[0],inputs=[],outputs=['RY[2]','UY[2]','Ay[2]'],step=step,initial_inputs=inputs,initial_shift=.7*unit,initial_times=(np.array([0,.03,.2,.7])/unit).tolist(),frequencies=(np.array([0,5,30])*unit).tolist()))))
    for kind in ('integral','lag','lag-truncated','unstable-truncated'):
        state=dict(beam_fields=[dict(beam=1,displacement=[[0,0,0,0],[2,0,.002,0]],velocity=[[0,0,0,0],[2,0,.01,0]])])
        if kind=='integral':
            law=dict(commands={'RY[2]':2},outputs=[dict(actuator='E1',terms=[dict(input='RY[2]',gain=-200),dict(input='RY[2]',gain=-100,mode='integral')])])
            state['feedback']=dict(integrals={'RY[2]':.003});g=[[0,1,0],[-350,-5,-50],[1,0,0]];q=[.002,.01,.003]
        elif kind.startswith('lag'):
            law=json.loads((ROOT/'examples/actuator-lag-controller.json').read_text());law['commands']={'RY[2]':2,'UY[2]':0}
            state['feedback']=dict(states={'lag':.1});g=[[0,1,0],[-250,-5,.5],[-4000,-400,-20]];q=[.002,.01,.1]
        else:
            law=dict(commands={'RY[2]':2},outputs=[dict(actuator='E1',terms=[dict(input='RY[2]',gain=800)])]);g=[[0,1],[150,-5]];q=[.002,.01]
        count=1 if kind=='lag-truncated' else 2 if kind=='unstable-truncated' else 3
        rows.append(dict(name=kind,generator=g,physical_initials=[q],request=dict(action='rom',source=source,panels=4,condition=dict(speed=10,alpha=0,mach=0),gravity=[0,0,0],rom=dict(count=count,selected=[1] if kind=='unstable-truncated' else None,inputs=['power.1'],outputs=['RY[2]','UY[2]','Ay[2]'],controller=law,initial_inputs=[dict(kind='initial',name=kind,state=state)],initial_shift=0 if kind=='unstable-truncated' else .3,initial_times=[0,.03,.2,.7],frequencies=[0,5,30]))))
    # This original loaded-aircraft case checks modal consistency, not external
    # ASWING agreement. Store its physical profile so WASM uses exactly the same
    # disturbance even if an eigenvector's arbitrary phase changes.
    wing=(ROOT/'examples/flexible.asw').read_text()+'\nSensor\n1 1 8 .8 8 .3\nEnd\n'
    c=dict(speed=30,alpha=4,mach=0,circulation_modes={'1':3})
    s,_=make_system(parse_asw(wing),FlightCondition(**c),4,gravity=[0,0,0]);a,m=linearize(s)
    modes,_=eigensystem(a,m,time_scale=s.W,count=6);index=next(i for i,v in enumerate(modes) if v['eigenvalue'][1]>1)
    mode=modes[index];v=mode['right']*.001;lam=complex(*mode['eigenvalue']);n=s.network;nodes=[]
    for beam,(ts,ids) in n.station_nodes.items():
        for t,i in zip(ts,ids):nodes.append(dict(beam=beam,t=float(t),displacement=(v[6*i:6*i+3].real*n.L).tolist(),rotation=v[6*i+3:6*i+6].real.tolist(),velocity=(v[s.velocity_start+3*i:s.velocity_start+3*i+3].real*s.V).tolist(),rates=(v[s.velocity_start+3*n.nn+3*i:s.velocity_start+3*n.nn+3*i+3].real*s.W).tolist()))
    gamma=n.circulation_basis.decode(v[n.gamma_start:n.operating_start].real*n.gamma_scale).tolist()
    outputs=['RZ[1]','UZ[1]','Az[1]'];measured=MeasurementOutputs(s,outputs)
    y=measured.tangent(v.real,(lam*v).real,1e-5)+1j*measured.tangent(v.imag,(lam*v).imag,1e-5)
    rows.append(dict(name='loaded-wing-mode',reference_mode=dict(eigenvalue=mode['eigenvalue'],output=complex_data(y)),request=dict(action='rom',source=wing,panels=4,condition=c,gravity=[0,0,0],rom=dict(count=6,selected=[index],inputs=[],outputs=outputs,initial_inputs=[dict(kind='initial',name='Loaded wing mode',state=dict(nodes=nodes,circulation=gamma))],initial_shift=100,initial_times=[0,.01,.03,.1],frequencies=[0,5,30]))))
    return rows


def verify(case,result):
    worst=0.;count=0
    def check(actual,expected):
        nonlocal worst,count
        actual=np.asarray(actual);expected=np.asarray(expected);error=float(np.max(abs(actual-expected)/np.maximum(1.,abs(expected))))
        assert error<2e-7,(case['name'],error,actual,expected)
        worst=max(worst,error);count+=actual.size
    if 'generator' in case:
        g=np.array(case['generator']);h=np.vstack((np.eye(len(g))[:2],g[1]));values,basis=np.linalg.eig(g);inverse=np.linalg.inv(basis)
        retained=[complex(*r['eigenvalue']) for r in result['diagnostics']['retained']]
        chosen=[k for k,val in enumerate(values) if min(min(abs(val-r),abs(val-r.conjugate())) for r in retained)<1e-6*max(1,abs(val))]
        projector=basis[:,chosen]@inverse[chosen]
        assert np.max(abs(projector.imag))<1e-8;projector=projector.real
    for i,row in enumerate(result['initial_responses']):
        assert row['converged'],row
        if 'generator' in case:initial=np.array(case['physical_initials'][i])
        else:
            lam=complex(*case['reference_mode']['eigenvalue']);y=case['reference_mode']['output'];y=np.array(y['real'])+1j*np.array(y['imag'])
        for sample in row['time_samples']:
            assert sample['converged'],sample;t=sample['time']
            if 'generator' in case:full=h@expm(g*t)@initial;reduced=h@expm(g*t)@projector@initial
            else:full=reduced=(y*np.exp(lam*t)).real
            check(sample['full'],full);check(sample['reduced'],reduced)
        if case['name']=='unstable-truncated':
            assert 'spectral abscissa' in row['spectrum_error'] and not row['samples']
            assert result['diagnostics']['initial_conditions']['spectral_abscissa']>0
            assert max(np.linalg.eigvals(result['matrices']['A']).real)<0
        else:
            assert len(row['samples'])==len(case['request']['rom']['frequencies'])
            for sample in row['samples']:
                assert sample['converged'],sample;s=sample['shift']+1j*sample['omega']
                if 'generator' in case:full=h@np.linalg.solve(s*np.eye(len(g))-g,initial);reduced=h@np.linalg.solve(s*np.eye(len(g))-g,projector@initial)
                else:full=reduced=.5*(y/(s-lam)+y.conj()/(s-lam.conjugate()))
                for key,want in [('full',full),('reduced',reduced)]:check(np.array(sample[key]['real'])+1j*np.array(sample[key]['imag']),want)
    return dict(maximum_scaled_reference_error=worst,physical_values_checked=count)


def main():
    files=[Path(__file__),*[ROOT/'examples'/n for n in ('instrumented-oscillator.asw','flexible.asw','actuator-lag-controller.json','initial-spring.json')],*sorted((ROOT/'openswing').glob('*.py'))]
    hashes={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    versions=dict(python=platform.python_version(),numpy=np.__version__,scipy=scipy.__version__)
    key=hashlib.sha256(json.dumps(dict(hashes=hashes,versions=versions),sort_keys=True).encode()).hexdigest();cache=ROOT/'.reference/rom-initial'/key;cache.mkdir(parents=True,exist_ok=True)
    specs=cache/'cases.json'
    if specs.exists():requests=json.loads(specs.read_text())
    else:requests=cases();specs.write_text(json.dumps(requests)+'\n')
    rows=[]
    for case in requests:
        start=time.monotonic();file=cache/(case['name']+'.json')
        if file.exists():result=json.loads(file.read_text())
        else:result=dispatch(case['request']);file.write_text(json.dumps(result,allow_nan=False)+'\n')
        checks=verify(case,result);rows.append(dict(specification=case,result=result,checks=checks));print(case['name'],checks,f'{time.monotonic()-start:.1f}s',flush=True)
    output=dict(description='Mass-dual physical initial-state projection, full/selected linear free histories and one-sided spectra. Independent oscillator/controller ODEs, mode truncation, omitted unstable modes, mesh/step/time units; loaded wing mode identity is an internal consistency check.',source_sha256=hashes,versions=versions,cases=rows)
    (ROOT/'docs/validation/rom-initial.json').write_text(json.dumps(output,indent=2,allow_nan=False)+'\n');print('Wrote rom-initial.json',flush=True)

if __name__=='__main__':main()
