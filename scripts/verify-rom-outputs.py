"""Physical ROM outputs against independent spring and finite-wing equations."""
from pathlib import Path
import argparse
import hashlib
import json
import platform
import runpy
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import numpy as np
import scipy
from openswing.asw import parse_asw
from openswing.aero import AnalysisError, FlightCondition
from openswing.linear_dynamics import make_system
from openswing.reduced_model import solve_reduced_model
from openswing.rom_file import export_rom,parse_rom,rom_response,array

SECTION=runpy.run_path(str(ROOT/'scripts/verify-section-outputs.py'))
BEAM=runpy.run_path(str(ROOT/'scripts/modal-benchmark.py'))
RHO,SOUND=1.225,340.294


def pick(base,group,key,index=0,component=None):
    out=dict(group=group,key=key)
    if component is not None:out['component']=component
    if group!='global':
        row=base['elements' if group=='sections' else group][index]
        out.update(index=index,beam=row['beam'],t=row['t'])
    return out


def flow(count,span=2.):
    """Straight finite-segment and wake integrals, independent of solver AIC."""
    edge=-span/2*np.cos(np.linspace(0,np.pi,count+1))
    y=-span/2*np.cos((np.arange(count)+.5)*np.pi/count)
    a=y[:,None]-edge[:-1];b=y[:,None]-edge[1:];dx=.5
    ra=np.sqrt(dx*dx+a*a);rb=np.sqrt(dx*dx+b*b)
    w=-(a/ra-b/rb)/(4*np.pi*dx)+((1+dx/rb)/b-(1+dx/ra)/a)/(4*np.pi)
    return w,np.diff(edge)/span


def factors(units):
    L,T,F=units
    return {'input L':L,'rad':1.,'input L/T':L/T,'rad/input T':1/T,
            'input F':F,'input F L':F*L,'dimensionless':1.,'1/input L':1/L,
            'input F/L^2':F/L**2,'input L^2/T':L**2/T,'input F/L':F/L}


def compare(rom,expected,units):
    scale=factors(units)
    os=np.array([scale[item['unit']] for item in rom['outputs']])
    ins=np.array([scale.get(item['unit'],1.) for item in rom['inputs']])
    full=np.array([array(s['full'])*os[:,None]/ins for s in rom['samples']])
    actual=np.array([array(s['reduced'])*os[:,None]/ins for s in rom['samples']])
    expected=np.asarray(expected)
    errors={key:float(np.max(abs(value-expected)/np.maximum(1.,abs(expected)))) for key,value in [('full',full),('reduced',actual)]}
    assert max(errors.values())<2e-6,(errors,actual,expected)
    return actual,full,errors,os,ins


def rigid(spec):
    units=spec.get('units',[1.,1.,1.]);L,T,F=units;n=spec.get('panels',4)
    source=SECTION['source'](dict(units=units));model=parse_asw(source)
    condition=FlightCondition(speed=30*T/L,alpha=0,mach=0,controls={1:3.},freeze_influences=spec.get('frozen',False))
    system,_=make_system(model,condition,n,gravity=[0,0,0]);base=system.base_report()
    outputs=[pick(base,'strips',key,i) for i in range(n) for key in ['cm','f_aero','circulation']]
    initial=.2*np.sin((np.arange(n)+.5)*np.pi/n);omega=np.array([0.,3.,25.]);w,_=flow(n);mass=2/(np.pi*30)*np.eye(n)
    rom=solve_reduced_model(model,condition,n,gravity=[0,0,0],count=n,outputs=outputs,step=spec.get('step',1e-5),
        inputs=['control.1',dict(kind='gust',wave='uniform')],frequencies=omega*T,
        initial_inputs=[dict(kind='initial',name='circulation',state=dict(circulation=(initial*T/L**2).tolist()))],
        initial_times=[0,.05/T,.2/T])
    expected=[];initial_expected=[]
    for frequency in omega:
        s=1j*frequency;gamma=np.linalg.solve(s*mass-w,np.ones(n))
        row=np.zeros((n,3,2),complex);row[:,0,0]=.005/np.sqrt(1-(30/SOUND)**2)
        row[:,1,1]=RHO*(30+s)*gamma;row[:,2,1]=gamma;expected.append(row.reshape(-1,2))
        gamma=np.linalg.solve(s*mass-w,mass@initial)
        initial_expected.append(np.column_stack([np.zeros(n),RHO*((30+s)*gamma-initial),gamma]).ravel())
    actual,full,errors,os,ins=compare(rom,expected,units)
    initial_expected=np.asarray(initial_expected)
    profile=rom['initial_responses'][0];assert profile['converged'],profile
    initial_actual={key:np.array([array(s[key])*os*T for s in profile['samples']]) for key in ['full','reduced']}
    initial_error=max(float(np.max(abs(v-initial_expected)/np.maximum(1.,abs(initial_expected)))) for v in initial_actual.values())
    assert initial_error<2e-6,initial_error
    return finish(spec,source,rom,actual,full,expected,errors,units,
        initial_reference=packed(initial_expected),initial_computed={k:packed(v) for k,v in initial_actual.items()},initial_maximum_scaled_error=initial_error)


def mechanical(spec):
    units=spec.get('units',[1.,1.,1.]);L,T,F=units;preload=spec.get('preload',5.)
    # This case declares alternate units without rescaling the printed numbers:
    # it is a different SI oscillator, checked against its own dimensional law.
    source=(ROOT/'examples/instrumented-oscillator.asw').read_text()
    for letter,factor in zip('LTF',units):source=source.replace(f'{letter} 1 '+{'L':'m','T':'s','F':'N'}[letter],f'{letter} {factor} '+{'L':'m','T':'s','F':'N'}[letter])
    model=parse_asw(source);condition=FlightCondition(speed=10,alpha=0,mach=0,powers={1:preload})
    n=spec.get('panels',4);system,_=make_system(model,condition,n,gravity=[0,0,0]);base=system.base_report()
    tip=max(range(len(base['nodes'])),key=lambda i:base['nodes'][i]['t'])
    outputs=[pick(base,'nodes','displacement',tip,1),pick(base,'nodes','velocity',tip,1),
             pick(base,'sections','strain',0,1),pick(base,'sections','force_local',0,1),
             pick(base,'global','engine_force',component=1),pick(base,'global','support_force',component=1)]
    omega=np.array([0.,10.,50.])
    rom=solve_reduced_model(model,condition,n,gravity=[0,0,0],count=2,selected=[0],outputs=outputs,
                            frequencies=omega,step=spec.get('step',1e-5))
    expected=[]
    for frequency in omega/T:
        s=1j*frequency;m=2*F*T*T/L;c=10*F*T/L;k=500*F/L
        h=F/(m*s*s+c*s+k)
        expected.append(np.array([h,s*h,h/(2*L),(k+c*s)*h,F,-(k+c*s)*h])[:,None])
    actual,full,errors,_,_=compare(rom,expected,units)
    return finish(spec,source,rom,actual,full,expected,errors,units)


def coupled_reference(count,speed,omega,span=40.):
    """Exact finite-wing heave/pitch/lag transfer for this rigid supported wing.

    Mechanical unknowns h and theta are followed by constant strip circulations.
    The integrated lift uses exact interval lengths; no 2D limit is substituted.
    """
    s=1j*omega;w,weight=flow(count,span);ma=RHO*np.pi/4;m=20*ma;j=.06*m
    a,d,e=-.15,.1,.1
    matrix=np.zeros((count+2,count+2),complex);rhs=np.zeros((count+2,2),complex)
    matrix[0,:2]=[(m+ma)*s*s+400*m,-(m*e+ma*d)*s*s-ma*speed*s]
    matrix[1,:2]=[-(m*e+ma*d)*s*s,(j+ma*(d*d+1/32))*s*s+2500*j+ma*(d+.25)*speed*s]
    matrix[0,2:]=-RHO*(speed+s)*weight
    matrix[1,2:]=a*RHO*(speed+s)*weight
    matrix[2:,0]=s;matrix[2:,1]=-speed-(a+.5)*s
    matrix[2:,2:]=2/(np.pi*speed)*s*np.eye(count)-w
    rhs[0,0]=1.;rhs[2:,1]=1.
    state=np.linalg.solve(matrix,rhs);h,theta=state[:2];gamma=state[2:]
    out=[]
    for g in gamma:
        out.extend([RHO*(speed+s)*g,ma*(-s*s*h+d*s*s*theta+speed*s*theta),theta])
    out.extend([h,theta])
    return np.array(out)


def coupled(spec):
    n=spec.get('panels',4);span=40.;speed=40.
    source=BEAM['configuration'](span).dumps()+f'\nEngine\n1 0 2 0 0 0 1 0 0 1 {span} 0 -1 0 0\nEnd\n'
    model=parse_asw(source);condition=FlightCondition(speed=speed,alpha=0,mach=0,stall=False)
    system,_=make_system(model,condition,n,gravity=[0,0,0]);base=system.base_report()
    ids=[i for i,row in enumerate(base['strips']) if row['lifting']]
    assert len(ids)==n,(len(ids),n)
    outputs=[pick(base,'strips',key,i) for i in ids for key in ['f_aero','f_reac','da_eff']]
    root=next(i for i,row in enumerate(base['nodes']) if row['beam']==2 and row['t']==0)
    outputs.extend([pick(base,'nodes','displacement',root,2),pick(base,'nodes','rotation',root,1)])
    omega=[1.,15.,25.,35.,50.]
    rom=solve_reduced_model(model,condition,n,gravity=[0,0,0],count=n+4,outputs=outputs,
        inputs=['power.1',dict(kind='gust',wave='uniform')],frequencies=omega,step=spec.get('step',1e-5))
    expected=[coupled_reference(n,speed,w) for w in omega]
    actual,full,errors,_,_=compare(rom,expected,[1.,1.,1.])
    return finish(spec,source,rom,actual,full,expected,errors,[1.,1.,1.])


def packed(value):
    value=np.asarray(value);return dict(real=value.real.tolist(),imag=value.imag.tolist())


def finish(spec,source,rom,actual,full,expected,errors,units,**extra):
    # Export and reparse the delivered annotations. Explicitly retain any
    # D_rate rejection; the matrices themselves remain available in JSON.
    legacy_error=None;legacy=None
    try:
        text=export_rom(rom,parse_asw(source).units)
        parsed=parse_rom(text)
        result=rom_response(parsed,np.array([s['omega'] for s in rom['samples']])/units[1])
        replay=np.array([array(s['response']) for s in result['samples']])
        error=float(np.max(abs(replay-actual)/np.maximum(1.,abs(actual))))
        assert error<2e-8,error
        legacy=dict(text=text,outputs=parsed['outputs'],maximum_scaled_replay_error=error)
    except AnalysisError as exc:
        legacy_error=str(exc)
    return dict(spec=spec,source=source,outputs=rom['outputs'],output_base=rom['output_base'],
        matrices=rom['matrices'],diagnostics=rom['diagnostics'],frequencies_rad_per_s=(np.array([s['omega'] for s in rom['samples']])/units[1]).tolist(),
        computed=packed(actual),full=packed(full),reference=packed(expected),maximum_scaled_errors=errors,
        legacy_export=legacy,legacy_export_error=legacy_error,**extra)


def compute(spec):
    return {'rigid':rigid,'mechanical':mechanical,'coupled':coupled}[spec['kind']](spec)


def specifications():
    return [dict(kind='rigid',panels=n) for n in [4,8]]+[
        dict(kind='rigid',units=[.3048,2.,4.4482216152605]),dict(kind='rigid',frozen=True,step=3e-6),
        dict(kind='mechanical'),dict(kind='mechanical',panels=6,preload=0.,units=[2.,2.,3.]),
        dict(kind='coupled',panels=4),dict(kind='coupled',panels=8),dict(kind='coupled',panels=4,step=3e-6)]


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--limit',type=int);args=parser.parse_args()
    files=[Path(__file__),ROOT/'scripts/verify-section-outputs.py',ROOT/'scripts/modal-benchmark.py',
           ROOT/'examples/instrumented-oscillator.asw',*sorted((ROOT/'openswing').glob('*.py'))]
    provenance=dict(source_sha256={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files},
        versions=dict(python=platform.python_version(),numpy=np.__version__,scipy=scipy.__version__))
    cache=ROOT/'.reference/rom-outputs'/hashlib.sha256(json.dumps(provenance,sort_keys=True).encode()).hexdigest();cache.mkdir(parents=True,exist_ok=True)
    specs=specifications();paths=[]
    for spec in specs:
        paths.append(cache/(hashlib.sha256(json.dumps(spec,sort_keys=True).encode()).hexdigest()+'.json'))
    for spec,path in list(zip(specs,paths))[:args.limit]:
        if not path.exists():path.write_text(json.dumps(compute(spec),allow_nan=False)+'\n')
        result=json.loads(path.read_text());print(spec,result['maximum_scaled_errors'],result['legacy_export_error'],flush=True)
    if not all(p.exists() for p in paths):
        print('Partial cache retained; complete report unchanged.',flush=True);return
    cases=[json.loads(p.read_text()) for p in paths]
    out=dict(description=__doc__,**provenance,cases=cases,
        scope='Analytical spring, finite-wing circulation and supported heave/pitch references. No ASWING executable or experimental aircraft validation.')
    (ROOT/'docs/validation/rom-outputs.json').write_text(json.dumps(out,indent=2,allow_nan=False)+'\n')
    print('Wrote docs/validation/rom-outputs.json',flush=True)


if __name__=='__main__':main()
