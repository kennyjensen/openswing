"""Saved graft curves and a variable-stiffness spring against independent laws."""
from pathlib import Path
import hashlib, json, platform, sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np
from scipy.integrate import quad
from openswing.asw import parse_asw
from openswing.bridge import dispatch


def specifications():
    wing=Path('examples/rectangular.asw').read_text()
    spring=Path('examples/instrumented-oscillator.asw').read_text()
    cases=[]
    for tangent in (True, False):
        cases.append(dict(name='curve_tangent' if tangent else 'curve_corner', kind='curve',
            edit=dict(action='edit_distribution',source=wing,beam=1,name='alpha',
                      edit=dict(points=[[0,0],[6,0]],graft=dict(points=[[5,0],[1,0],[3,1]],tangent=tangent,tolerance=1e-5)))))
    for count in (4,8,16):
        cases.append(dict(name=f'spring_{count}',kind='spring',count=count,
            edit=dict(action='edit_distribution',source=spring,beam=1,name='EA',
                      edit=dict(graft=dict(points=[[.5,1000],[1,1500],[1.5,1000]],tolerance=1e-5)))))
    return cases


def compute(spec):
    edited=dispatch(spec['edit']);source=edited['source'];model=parse_asw(source)
    d=model.beams[0].distributions[spec['edit']['name']]
    query=np.linspace(*edited['distribution']['editing']['domain'],601)
    result=dict(source=source,editing=edited['distribution']['editing'],query=query.tolist(),
                values=d.evaluate(query).tolist(),slopes=d.evaluate(query,derivative=1).tolist())
    if spec['kind']=='spring':
        request=dict(source=source,panels=dict(default=spec['count'],beams={'1':dict(count=spec['count'],spacing='uniform')}),
                     gravity=[0,0,0],condition=dict(speed=10,alpha=0,mach=0,powers={1:10}))
        static=dispatch(dict(action='solve',mode='mounted',**request))
        modes=dispatch(dict(action='modes',**{**request,'condition':dict(speed=10,alpha=0,mach=0)},modes=dict(count=8)))
        result.update(displacement=static['nodes'][-1]['position'][1]-2,
                      support=static['support_force'],poles=[m['eigenvalue'] for m in modes['modes']])
    return result


def smooth(u):
    return 3*u*u-2*u*u*u


def verify(spec,result):
    q=np.array(result['query']);actual=np.array(result['values']);slopes=np.array(result['slopes'])
    if spec['kind']=='curve':
        u=np.where(q<=3,(q-1)/2,(5-q)/2);inside=(q>=1)&(q<=5)
        if spec['edit']['edit']['graft']['tangent']:
            expected=np.where(inside,smooth(u),0)
            derivative=np.where(inside,(3*u-3*u*u)*np.where(q<=3,1,-1),0)
        else:
            # Natural cubic through (1,0),(3,1),(5,0): each half is
            # 3u/2-u^3/2, with one-sided slope corners at 1 and 5.
            expected=np.where(inside,1.5*u-.5*u**3,0)
            derivative=np.where((q>=1)&(q<5),(.75-.75*u*u)*np.where(q<=3,1,-1),0)
    else:
        u=np.where(q<=1,(q-.5)/.5,(1.5-q)/.5);inside=(q>=.5)&(q<=1.5)
        expected=1000+500*np.where(inside,smooth(u),0)
        derivative=500*np.where(inside,12*(u-u*u)*np.where(q<=1,1,-1),0)
    scale=result['editing']['value_scale'];length=result['editing']['slope_length_scale']
    error=max(float(np.max(abs(actual-expected))/scale),float(np.max(abs(slopes-derivative))*length/scale))
    assert error<1e-5,(spec['name'],error)
    assert result['editing']['maximum_relative_value_error']<=1e-5
    assert result['editing']['maximum_relative_slope_error']<=1e-5
    checks=dict(independent_scalar_checks=int(2*len(q)),maximum_scaled_curve_error=error)
    if spec['kind']=='spring':
        # Axial extension is F*integral(1/EA ds). The two half-grafts each
        # have length .5; the remaining total length 1 has EA=1000.
        compliance=.001+quad(lambda u:1/(1000+500*smooth(u)),0,1,epsabs=1e-14,epsrel=1e-13)[0]
        k=1/compliance;c=.02*k;m=2.
        exact=np.roots([m,c,k]);poles=[complex(*z) for z in result['poles']]
        displacement_error=abs(result['displacement']/(10*compliance)-1)
        pole_error=max(min(abs(p-z) for p in poles)/abs(z) for z in exact)
        midpoints=(np.arange(spec['count'])+.5)*2/spec['count']
        u=np.where(midpoints<=1,(midpoints-.5)/.5,(1.5-midpoints)/.5)
        stiffness=1000+500*np.where((midpoints>=.5)&(midpoints<=1.5),smooth(u),0)
        discrete_compliance=float(np.sum((2/spec['count'])/stiffness))
        discrete_poles=np.roots([m,.02/discrete_compliance,1/discrete_compliance])
        discrete_error=abs(result['displacement']/(10*discrete_compliance)-1)
        discrete_pole_error=max(min(abs(p-z) for p in poles)/abs(z) for z in discrete_poles)
        assert discrete_error<1e-7 and discrete_pole_error<1e-7,(spec['name'],discrete_error,discrete_pole_error)
        np.testing.assert_allclose(result['support'],[0,-10,0],atol=1e-7)
        checks.update(independent_scalar_checks=checks['independent_scalar_checks']+13,
                      exact_compliance=compliance,stiffness=k,damping=c,
                      relative_displacement_error=displacement_error,relative_pole_error=float(pole_error),
                      discrete_compliance=discrete_compliance,relative_discrete_displacement_error=discrete_error,
                      relative_discrete_pole_error=float(discrete_pole_error))
    return checks


def physical(result):
    values=[*result['values'],*result['slopes']]
    if 'displacement' in result:values.extend([result['displacement'],*result['support']])
    return np.asarray(values)


def run():
    files=[Path('scripts/verify-distribution-graft.py'),Path('examples/rectangular.asw'),Path('examples/instrumented-oscillator.asw'),*sorted(Path('openswing').glob('*.py'))]
    report=dict(description='Ordinary-ASW cubic graft reconstruction and independent variable-stiffness axial compliance/poles.',
        python=platform.python_version(),source_sha256={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in files},cases=[],
        limitations=['The ASWING spline endpoint and cursor-editor algorithms are not specified by the public guide.',
                     'Tangent grafts are saved as natural-spline station approximations with checked value and slope tolerances.',
                     'The mechanical reference covers an axial beam with tip mass and Kelvin–Voigt damping, not arbitrary edited aircraft.'])
    for spec in specifications():
        actual=compute(spec);checks=verify(spec,actual)
        report['cases'].append(dict(specification=spec,result=actual,checks=checks))
        print(spec['name'],json.dumps(checks),flush=True)
    errors=[c['checks']['relative_displacement_error'] for c in report['cases'][2:]]
    assert errors[-1]<errors[0]/8 and errors[-1]<2e-5,errors
    Path('docs/validation/distribution-graft.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    print('All five native graft cases passed.',flush=True)


if __name__=='__main__':run()
