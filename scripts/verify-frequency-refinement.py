"""Frozen Bode grids: independent transfer functions, phases and source hashes."""
import hashlib,json,platform,sys
from copy import deepcopy
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import numpy as np
import scipy
from openswing.asw import parse_asw
from openswing.aero import FlightCondition
from openswing.frequency_sweep import FrequencySweep
from openswing.frequency_response import solve_frequency_response


def specifications():
    oscillator=(ROOT/'examples/forced-oscillator.asw').read_text();instrumented=(ROOT/'examples/instrumented-oscillator.asw').read_text()
    profiles=json.loads((ROOT/'examples/initial-spring.json').read_text())
    common=dict(panels=4,condition=dict(speed=10,alpha=0,mach=0,stall=False),options=dict(gravity=[0,0,0]))
    out=[dict(common,name='oscillator',source=oscillator,initial=[1.,30.],additional=[[0.,10.,14.,15.,float(np.sqrt(250)),16.,17.,18.,100.],[1.,16.]],options=dict(common['options'],matrices=True))]
    text=oscillator.replace('T 1 s','T 1 ms').replace('9.80665 1.225 340.294','9.80665e-6 1.225e6 .340294').replace('1000 .02','1000 20')
    out.append(dict(common,name='milliseconds',source=text,condition=dict(common['condition'],speed=.01),initial=[.001,.03],additional=[[0.,.01,.015,.016,.1]]))
    out.append(dict(common,name='initial_spectra',source=instrumented,initial=[0.,30.],additional=[[1.,10.,16.,100.]],options=dict(common['options'],inputs=['power.1',*profiles],initial_shift=.7)))
    law=dict(outputs=[dict(actuator='E1',terms=[dict(input='RY[2]',gain=-200),dict(input='UY[2]',gain=-20),dict(input='RY[2]',gain=-100,mode='integral'),dict(input='Ay[2]',gain=-3)])])
    out.append(dict(common,name='closed_loop',source=instrumented,initial=[0.,30.],additional=[[1.,10.,16.,100.]],options=dict(common['options'],inputs=['power.1','command.RY[2]'],controller=law)))
    fixed='''Name
Original fixed drag-point gust reference
End
Unit
L 1 m
T 1 s
F 1 N
End
Constant
9.80665 1.225 340.294
End
Reference
2 1 2
End
Ground
1 0 0
End
Weight
1 0 1.2 .6 -.3 0 .4 0
End
Beam 1
Rigid axis
t y
0 0
2 2
End
'''
    out.append(dict(common,name='gust_phase',source=fixed,initial=[.4],additional=[[36.,12.,.4,4.]],options=dict(common['options'],inputs=[dict(kind='gust',name=k,symmetry=k,span_mode=1) for k in ('cosine','sine')])))
    free=fixed.replace('1 0 1.2 .6 -.3 0 .4 0','1 0 0 0 0 9.80665 0 0 0 0 0 19.6133 29.41995 39.2266')+'\nEngine\n1 0 1 0 0 0 0 1 0 0 1 0 -1 0 0\nEnd\n'
    out.append(dict(common,name='free_dc_gap',source=free,initial=[0.,.3],additional=[[3.,1.,0.]],options=dict(common['options'],frame='free')))
    flexible=(ROOT/'examples/flexible.asw').read_text().rsplit('End',1)[0]+'t dCLdF1 dCMdF1\n0 .03 -.004\n8 .03 -.004\nEnd\n'
    out.append(dict(common,name='loaded_trim',source=flexible,condition=dict(common['condition'],speed=18,alpha=3),initial=[.5,20.],additional=[[1.,5.,10.]],options=dict(common['options'],operating_constraints=[dict(variable='alpha',quantity='CL',target=.4)])))
    return out


def z(value):return np.asarray(value['real'])+1j*np.asarray(value['imag'])


def physical(out):
    values=list(out['base']['force'])+list(out['base']['moment'])
    for node in out['base']['nodes']:values+=node['position']
    def collect(value):
        if isinstance(value,dict):
            if 'real' in value and 'imag' in value:
                for k in ('real','imag'):values.extend(np.asarray(value[k]).ravel())
            else:
                for v in value.values():collect(v)
        elif isinstance(value,list):
            for v in value:collect(v)
    for row in out['samples']:
        values.append(row['omega']);collect(row['responses'])
        if 'B' in row:collect(row['B'])
    return np.asarray(values)


def compute(spec):
    original=deepcopy(spec);events=[];m=parse_asw(spec['source']);condition=FlightCondition(**spec['condition'])
    sweep=FrequencySweep(m,condition,spec['panels'],frequencies=spec['initial'],**spec['options'])
    initial=sweep.report();batches=[];previous=initial
    for frequencies in spec['additional']:
        events.clear();out=sweep.extend(frequencies,lambda *x:events.append(x))
        new=out['frequency_refinement'];assert len(events)==len(new['added_frequencies']) and all(e[0]=='frequency' for e in events)
        assert out['base']==initial['base'] and out['diagnostics']==initial['diagnostics'] and out['inputs']==initial['inputs']
        if 'matrices' in initial:assert out['matrices']==initial['matrices']
        for row in previous['samples']:assert row==next(s for s in out['samples'] if s['omega']==row['omega'])
        batches.append(dict(refinement=new,events=deepcopy(events)));previous=out
    direct=solve_frequency_response(m,condition,spec['panels'],frequencies=[s['omega'] for s in out['samples']],**spec['options'])
    a,b=physical(out),physical(direct);difference=float(np.max(abs(a-b)/np.maximum(1.,abs(b))))
    assert difference<2e-7,(spec['name'],difference)
    assert original==spec;json.dumps(out,allow_nan=False)
    # Live handles are not persistent artifacts. The study retains their model
    # and settings identities, but removes process-specific random tokens.
    for value in (initial,out):value['frequency_session'].pop('id')
    return dict(initial=initial,result=out,batches=batches,one_shot_difference=difference,one_shot_values_compared=a.size)


def verify(spec,case):
    count=0;maximum=0.
    def close(actual,expected,tolerance=3e-8):
        nonlocal count,maximum
        a,b=np.asarray(actual),np.asarray(expected);error=float(np.max(abs(a-b)/np.maximum(1.,abs(b))))
        count+=a.size*(2 if np.iscomplexobj(a) else 1);maximum=max(maximum,error)
        assert error<tolerance,(spec['name'],error,a,b)
    out=case['result'];name=spec['name'];gap=0
    for row in out['samples']:
        w=row['omega'];responses=row['responses']
        if not row['converged']:
            assert name=='free_dc_gap' and w==0 and not responses;gap+=1;continue
        if name in ('oscillator','milliseconds','initial_spectra'):
            physical_w=w*(1000 if name=='milliseconds' else 1);h=1/(500+10j*physical_w-2*physical_w**2);o=responses[0]['output']
            close(z(o['nodes'][-1]['displacement'])[1],h,3e-11);close(z(o['nodes'][-1]['velocity'])[1]*(1000 if name=='milliseconds' else 1),1j*physical_w*h,3e-10)
        if name=='initial_spectra':
            s=.7+1j*w
            for i,(q0,v0) in enumerate(((.002,0),(0,.01)),1):
                value=responses[i];o=value['output'];q=((2*s+10)*q0+2*v0)/(2*s*s+10*s+500);v=s*q-q0
                close(z(o['nodes'][-1]['displacement'])[1],q,3e-11);close(z(o['nodes'][-1]['velocity'])[1],v,3e-10)
                close(z(o['sensors'][-1]['acceleration_sensor'])[1],s*v-v0,3e-9)
                close(z(value['state_rate']),s*z(value['state'])-out['inputs'][i]['resolved_state'],3e-11)
        elif name=='closed_loop':
            s=1j*w;den=5*s**3+30*s*s+700*s+100
            for i,q in enumerate((s/den,(200*s+100)/den)):
                o=responses[i]['output'];close(z(o['sensors'][1]['displacement_body'])[1],q)
                close(z(o['sensors'][1]['acceleration_sensor'])[1],s*s*q)
                close(z(o['feedback']['actuators_E1']),(2*s*s+10*s+500)*q)
        elif name=='gust_phase':
            p=np.array([1.2,.6,-.3])
            for i,trig in enumerate((np.cos,np.sin)):
                force=np.array([0,0,.5*1.225*.4*10*trig(np.pi*p[1])*np.exp(-1j*w*p[0]/10)])
                o=responses[i]['output'];close(z(o['global']['force']),force);close(z(o['global']['moment']),np.cross(p,force))
                close(np.dot(row['gust_profiles'][i]['streamwise_wavevector_earth'],out['inputs'][i]['convection_velocity_earth']),w)
        elif name=='free_dc_gap':
            o=responses[0]['output'];close(z(o['frame']['position_earth']),[-1/w**2,0,0]);close(z(o['frame']['velocity_origin_body']),[1/(1j*w),0,0]);close(z(o['operating']['acceleration.x']),1)
    if name=='loaded_trim':
        assert out['base']['max_displacement']>1e-3
        close(out['base']['CL'],.4,2e-8)
    assert gap==(1 if name=='free_dc_gap' else 0)
    return dict(reference_values_checked=count,maximum_scaled_reference_error=maximum,retained_gaps=gap)


def main():
    files=sorted((ROOT/'openswing').glob('*.py'))+[Path(__file__),*[ROOT/'examples'/name for name in ('forced-oscillator.asw','instrumented-oscillator.asw','flexible.asw','initial-spring.json')]]
    hashes={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    cache=ROOT/'.reference/frequency-refinement'/hashlib.sha256(json.dumps(hashes,sort_keys=True).encode()).hexdigest();cache.mkdir(parents=True,exist_ok=True)
    cases=[]
    for spec in specifications():
        path=cache/(spec['name']+'.json');value=json.loads(path.read_text()) if path.exists() else compute(spec);checks=verify(spec,value)
        path.write_text(json.dumps(value,allow_nan=False));cases.append(dict(specification=spec,result=value,checks=checks));print(spec['name'],checks,'one-shot',value['one_shot_difference'],flush=True)
    (ROOT/'docs/validation/frequency-refinement.json').write_text(json.dumps(dict(description='Exact frozen-pencil frequency refinement, retained samples/gaps, independent mechanical/phase/Laplace references and full-grid replay.',source_sha256=hashes,python=platform.python_version(),numpy=np.__version__,scipy=scipy.__version__,cases=cases),indent=2)+'\n')
    print('All native frequency-refinement cases passed.',flush=True)
if __name__=='__main__':main()
