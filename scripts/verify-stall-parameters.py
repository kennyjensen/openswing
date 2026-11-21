"""Published stall-parameter sensitivity against an independent infinite-span root.

This verifies equations 202–204 and their limiting forces, not measured post-stall
accuracy or uniqueness of arbitrary finite-wing branches.
"""
from pathlib import Path
from dataclasses import asdict
import decimal,hashlib,json,math,platform,sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import numpy as np
import scipy
from scipy.optimize import brentq
from openswing.asw import parse_asw
from openswing.aero import FlightCondition,solve_rigid

SETTINGS=[(0.,.05),(10.,.05),(40.,.05),(80.,.05),(40.,.01),(40.,.15)]

def source_for(span=5.9,units=(1.,1.,1.)):
    L,T,F=units
    return f'''Name
Stall parameter verification wing
End
Unit
L {L:.17g} m
T {T:.17g} s
F {F:.17g} N
End
Constant
{9.81*T*T/L:.17g} {1.2256*L**4/(F*T*T):.17g} {340.21*T/L:.17g}
End
Reference
{span/L**2:.17g} {1/L:.17g} {span/L:.17g}
End
Ground
1 0 0
End
Beam 1
Rectangular wing
t x y z chord Xax
0 0 0 0 {1/L:.17g} 0
{span/2:.17g} 0 {span/2/L:.17g} 0 {1/L:.17g} 0
t dCLda CLmin CLmax Cdf Cdp
0 6.2832 -1.2 1.2 .00352562 .00771413
{span/2:.17g} 6.2832 -1.2 1.2 .00352562 .00771413
End
'''

def reference_leakage(cl,lower,upper,width):
    """Independent direct logarithms and derivative in 450-digit arithmetic.

    Inputs are the exact binary floats. Exponential tails beyond +/-2000
    cannot affect the returned double-precision values on the checked grid.
    """
    with decimal.localcontext() as context:
        context.prec=450
        D=decimal.Decimal
        c,lo,hi,w=map(D.from_float,map(float,[cl,lower,upper,width]))
        def softplus(x):
            if x>2000:return x
            if x< -2000:return D(0)
            return (1+x.exp()).ln()
        def logistic(x):
            if x>2000:return D(1)
            if x< -2000:return D(0)
            return 1/(1+(-x).exp())
        a,b=(c-hi)/w,(lo-c)/w
        return float(w*(softplus(a)-softplus(b))),float(logistic(a)+logistic(b))

def reference(alpha,factor,width,high_precision=False):
    a=math.radians(alpha);slope=6.2832
    def softplus(x):return max(x,0.)+math.log1p(math.exp(-abs(x)))
    def leakage(cl):
        if high_precision:return reference_leakage(cl,-1.2,1.2,width)[0]
        return width*(softplus((cl-1.2)/width)-softplus((-1.2-cl)/width))
    cl=brentq(lambda cl:slope*math.sin(a)-cl*math.cos(a)-factor*leakage(cl),-64.,64.,xtol=1e-14)
    normal=math.sin(a)-cl*math.cos(a)/slope
    return dict(CL=cl,CD=.00352562+.00771413+4*normal**2,section_leakage=leakage(cl),
                normalized_normal_velocity=normal,scalar_residual=slope*math.sin(a)-cl*math.cos(a)-factor*leakage(cl))

def compute(spec):
    units=spec.get('units',[1.,1.,1.]);L,T,F=units;span=spec.get('span',5.9)
    condition=FlightCondition(speed=47.9*T/L,alpha=spec['alpha'],mach=0,
        stall=spec.get('stall',True),stall_factor=spec['factor'],stall_width=spec['width'],
        freeze_influences=spec.get('freeze_influences',False))  # Historical study uses wind-aligned influences.
    result=solve_rigid(parse_asw(source_for(span,units)),condition,spec.get('panels',16))
    assert result['residual']<1e-8
    force=np.sum([r['force'] for r in result['strips']],axis=0)*F
    np.testing.assert_allclose(force,np.array(result['force'])*F,rtol=2e-12,atol=1e-8)
    qS=.5*1.2256*47.9**2*span
    return dict(coefficients={k:result[k] for k in ['CL','CD','CDi','CDp','Cm','CY','Cl','Cn']},
        force_N=force.tolist(),moment_Nm=(np.array(result['moment'])*F*L).tolist(),
        circulation_m2_s=[r['circulation']*L*L/T for r in result['strips']],
        residual=result['residual'],panels=result['panels'],condition=asdict(condition),
        scales=dict(force_N=qS,moment_Nm=[qS*span,qS,qS*span],circulation_m2_s=.5*47.9))

def physical(result):
    return np.r_[list(result['coefficients'].values()),np.array(result['force_N'])/result['scales']['force_N'],
        np.array(result['moment_Nm'])/result['scales']['moment_Nm'],
        np.array(result['circulation_m2_s'])/result['scales']['circulation_m2_s']]

def corner_reference(spread):
    from openswing.circulation_solve import continue_circulation
    forcing=2.6+spread*np.cos(np.arange(16)*.3)
    actual,report=continue_circulation(lambda z:forcing-z-40*np.maximum(z-1.2,0),np.eye(16),
        derivative=lambda z:np.diag(-1-40*(z>1.2)))
    expected=(forcing+48)/41
    error=float(np.max(abs(actual-expected)))
    assert error<2e-12 and report['physical_residual']<1e-11
    assert report['final_regularization']==0 and report['trace'][-1]['parameter']==1
    return dict(spread=spread,result=actual.tolist(),reference=expected.tolist(),maximum_error=error,report=report)

def main():
    cases=[];limits=[]
    def run(spec):
        result=compute(spec);cases.append(dict(specification=spec,result=result));return result
    for factor,width in SETTINGS:
        for alpha in [-25.,0.,25.]:
            exact=reference(alpha,factor,width);errors=[]
            for span in [5900.,59000.,590000.]:
                spec=dict(factor=factor,width=width,alpha=alpha,span=span,panels=16)
                result=run(spec)
                errors.append(max(abs(result['coefficients'][k]-exact[k]) for k in ['CL','CD']))
            assert errors[-1]<1e-4,(factor,width,alpha,errors)
            if alpha:assert all(b<.2*a for a,b in zip(errors,errors[1:])),(factor,width,alpha,errors)
            limits.append(dict(factor=factor,width=width,alpha=alpha,reference=exact,spans=[5900.,59000.,590000.],errors=errors))
            print('infinite-span',factor,width,alpha,errors,flush=True)
    finite=[]
    for factor,width in SETTINGS:
        spec=dict(factor=factor,width=width,alpha=25.,panels=16)
        result=run(spec);finite.append(dict(specification=spec,result=result))
        print('finite',factor,width,result['coefficients']['CL'],result['coefficients']['CD'],flush=True)
    base=finite[-1]['result'];unit_errors=[]
    for units in [[.3048,.1,4.4482216152605],[1000.,60.,1000.]]:
        other=run(dict(factor=40.,width=.15,alpha=25.,panels=16,units=units))
        a,b=physical(other),physical(base);error=float(np.max(abs(a-b)/np.maximum(1,abs(b))))
        assert error<2e-8,error;unit_errors.append(dict(units=units,maximum_scaled_difference=error))
    disabled=run(dict(factor=80.,width=.01,alpha=25.,panels=16,stall=False))
    a,b=physical(disabled),physical(finite[0]['result']);disabled_error=float(np.max(abs(a-b)/np.maximum(1,abs(b))))
    assert disabled_error<2e-9,disabled_error
    assert finite[1]['result']['coefficients']['CL']>finite[3]['result']['coefficients']['CL']
    assert abs(finite[4]['result']['coefficients']['CL']-finite[5]['result']['coefficients']['CL'])>1e-4
    extreme_limits=[]
    for width in [1e-310,1e100]:
        for alpha in [-25.,25.]:
            exact=reference(alpha,40.,width,high_precision=True);errors=[]
            for span in [5900.,59000.,590000.]:
                result=run(dict(factor=40.,width=width,alpha=alpha,span=span,panels=16,high_precision_reference=True))
                errors.append(max(abs(result['coefficients'][k]-exact[k]) for k in ['CL','CD']))
            assert errors[-1]<1e-4,(width,alpha,errors)
            assert all(b<.2*a for a,b in zip(errors,errors[1:])),(width,alpha,errors)
            extreme_limits.append(dict(factor=40.,width=width,alpha=alpha,reference=exact,spans=[5900.,59000.,590000.],errors=errors))
            print('extreme infinite-span',width,alpha,errors,flush=True)
    from openswing.aero import _stall_leakage
    leakage_checks=[]
    for lower,upper in [(-1.2,1.2),(-.7,1.3),(.3,1.9)]:
        for width in [1e-310,1e-100,1e-12,.01,.05,.15,10.,1e12,1e100,1e308]:
            for cl in [-3.,-.01,0.,.01,3.,lower,upper,np.nextafter(lower,-np.inf),np.nextafter(upper,np.inf)]:
                expected=np.array(reference_leakage(cl,lower,upper,width))
                actual=np.array(_stall_leakage(cl,lower,upper,width))
                error=float(np.max(abs(actual-expected)/np.maximum(1,abs(expected))))
                assert np.all(np.isfinite(actual)) and error<3e-15,(cl,lower,upper,width,actual,expected)
                leakage_checks.append(dict(cl=float(cl),lower=lower,upper=upper,width=width,value=float(actual[0]),derivative=float(actual[1]),reference=expected.tolist(),maximum_scaled_error=error))
    corner_checks=[corner_reference(spread) for spread in [.01,.2]]
    hashes={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),*sorted((ROOT/'openswing').glob('*.py'))]}
    output=dict(description=__doc__,source_sha256=hashes,versions=dict(python=platform.python_version(),numpy=np.__version__,scipy=scipy.__version__),
        cases=cases,limits=limits,extreme_limits=extreme_limits,leakage_checks=leakage_checks,corner_checks=corner_checks,finite=finite,unit_checks=unit_errors,disabled_stall_scaled_difference=disabled_error,
        scope='Parameter sensitivity and independent infinite-span verification of the documented model. Finite-wing browser values are portability fixtures, not experimental validation. No stall law or numerical tolerance is fitted.')
    (ROOT/'docs/validation/stall-parameters.json').write_text(json.dumps(output,indent=2,allow_nan=False)+'\n')
    print('Completed',len(cases),'native cases',flush=True)

if __name__=='__main__':main()
