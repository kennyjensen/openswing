"""Finite-chord sine-mode vortex fields against independent continuum integrals.

No circulation solve or ISAE fitting. The Prandtl expression is only the
lifting-line limit; the finite-chord oracle retains both complete integrals.
"""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import hashlib
import json
import math
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def pin(p):
    raw=p.read_bytes()
    return dict(path=str(p.relative_to(ROOT)),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())


def write(path,obj):
    path.write_text(json.dumps(obj,indent=2,allow_nan=False)+'\n')


def prepare(out):
    assert not (out/'protocol.json').exists()
    out.mkdir(parents=True,exist_ok=True)
    paths=[Path(__file__),ROOT/'.reference/asw_theory.txt']+sorted((ROOT/'openswing').glob('*.py'))
    protocol=dict(format='finite-wing-mode-continuum-v1',created_utc=datetime.now(timezone.utc).isoformat(),
        sources=[pin(p) for p in paths],halfspan=1.,amplitude=1.,offsets=[.1,.3],modes=[1,2,3],counts=[32,64,128],
        receivers='Existing Glauert midpoint indices N//4, N//2, 3*N//4. Each has y=B*cos(theta_a), z=0, x=d; none lies on a wake filament.',
        geometry='Straight unswept bound line x=z=0, y=-B..B; cosine nodes. Unit x wake, Mach0, no core, no images. Gamma=A*sin(k*theta_a) constant per interval.',
        oracle='Gamma(y)=A*sin(k*acos(y/B)). w_bound=-d*A*B/(4*pi)*int_0^pi sin(k*t)*sin(t)/(d*d+(y-B*cos(t))**2)**1.5 dt. w_wake=A*k/(4*pi)*PVint_0^pi cos(k*t)*(1+d/sqrt(d*d+(y-B*cos(t))**2))/(y-B*cos(t)) dt.',
        cauchy='Use scipy.integrate.quad weight=cauchy at t0=acos(y/B). Stable denominator (y-B*cos(t))/(t-t0)=B*sin((t+t0)/2)*sinc((t-t0)/2). Independent integrals, not production filament expressions.',
        controls='With the offset-dependent wake multiplier omitted, the half-wake integral equals -A*k/(4*B)*sin(k*t0)/sin(t0). All x/y induced components vanish by planar symmetry.',
        tolerances=dict(quadrature_absolute=[1e-10,1e-12],quadrature_relative=[1e-10,1e-12],
            quadrature_refinement_scaled=1e-10,pure_half_wake_scaled=1e-10,
            fine_component_characteristic_error=.01,final_refinement_ratio=.4,reference_floor=1e-9,
            decomposition_absolute=1e-12,planar_components_absolute=0.),
        counting=dict(field_configurations=18,receiver_rows=54,nonlinear_solves=0,production_edits=0),
        scope=['This tests discrete bound and CP wake fields against finite-chord continuum integrals; the finite-grid error is measured, not assumed zero.',
            'It does not assert exact equality to the p31 Prandtl expression at finite chord, or authenticate any native ISAE setup.',
            'No continuum quadrature in this script imports a production vortex, geometry, residual or stall function. Production FactoredInfluence is the implementation under test.'])
    write(out/'protocol.json',protocol)
    write(out/'preparation-receipt.json',dict(protocol=pin(out/'protocol.json'),nonlinear_solves=0))
    print('Prepared18fieldconfigurations,54receiverrows,0nonlinearsolves.',flush=True)


def continuum(mode,theta,offset,epsilon,halfspan=1.,amplitude=1.):
    from scipy.integrate import quad
    B,A,k,d=halfspan,amplitude,mode,offset
    def delta(t): return 2*B*math.sin((t+theta)/2)*math.sin((t-theta)/2)
    def bound(t):
        return math.sin(k*t)*math.sin(t)/math.hypot(d,delta(t))**3
    def smooth(t,complete=True):
        h=(t-theta)/2
        sinc=math.sin(h)/h if h else 1.
        value=math.cos(k*t)/(B*math.sin((t+theta)/2)*sinc)
        return value*(1+d/math.hypot(d,delta(t))) if complete else value
    options=dict(epsabs=epsilon,epsrel=epsilon,limit=200)
    # Split ordinary bound integration at its smooth peak; the wake uses a
    # Cauchy principal-value integration with an explicitly smooth numerator.
    b0,e0=quad(bound,0,theta,**options);b1,e1=quad(bound,theta,math.pi,**options)
    w,ew=quad(smooth,0,math.pi,weight='cauchy',wvar=theta,**options)
    h,eh=quad(lambda t:smooth(t,False),0,math.pi,weight='cauchy',wvar=theta,**options)
    bound_value=-d*A*B/(4*math.pi)*(b0+b1)
    wake_value=A*k/(4*math.pi)*w
    half_value=A*k/(4*math.pi)*h
    exact_half=-A*k/(4*B)*math.sin(k*theta)/math.sin(theta)
    return dict(bound=bound_value,wake=wake_value,total=bound_value+wake_value,
        half_wake=half_value,exact_half_wake=exact_half,
        quadrature_estimated_errors=dict(bound=d*abs(A)*B/(4*math.pi)*(e0+e1),wake=abs(A)*k/(4*math.pi)*ew,half_wake=abs(A)*k/(4*math.pi)*eh))


def run(out):
    import numpy as np
    from openswing.factored_influence import FactoredInfluence
    protocol=json.loads((out/'protocol.json').read_text())
    expected=json.loads((out/'preparation-receipt.json').read_text())['protocol']
    def verify():
        assert pin(out/'protocol.json')==expected
        for p in protocol['sources']: assert pin(ROOT/p['path'])==p
    verify();assert not (out/'report.json').exists()
    gates=protocol['tolerances'];B=protocol['halfspan'];A=protocol['amplitude']
    rows=[];summaries=[];checks=[]
    def check(name,value,limit): checks.append(dict(name=name,value=float(value),limit=float(limit),passed=bool(value<=limit)))
    for d in protocol['offsets']:
        for k in protocol['modes']:
            case_rows=[]
            for N in protocol['counts']:
                theta=np.linspace(math.pi,0,N+1);middle=(theta[:-1]+theta[1:])/2
                nodes=np.column_stack((np.zeros(N+1),B*np.cos(theta),np.zeros(N+1)))
                gamma=A*np.sin(k*middle)
                indices=np.array([N//4,N//2,3*N//4]);angles=middle[indices]
                points=np.column_stack((np.full(3,d),B*np.cos(angles),np.zeros(3)))
                operator=FactoredInfluence(points,nodes[:-1],nodes[1:],[1.,0.,0.],np.eye(3),0.)
                actual_bound=np.einsum('rsd,s->rd',operator.bound,gamma)
                actual_wake=np.einsum('rsd,s->rd',operator.rays,operator.wake_strengths(gamma))
                actual=operator.apply(gamma)
                check(f'd={d},k={k},N={N}:field_sum',np.max(abs(actual-actual_bound-actual_wake)),gates['decomposition_absolute'])
                check(f'd={d},k={k},N={N}:planar_xy',max(np.max(abs(actual_bound[:,:2])),np.max(abs(actual_wake[:,:2]))),gates['planar_components_absolute'])
                for i,t in enumerate(angles):
                    coarse=continuum(k,float(t),d,1e-10,B,A)
                    oracle=continuum(k,float(t),d,1e-12,B,A)
                    check(f'd={d},k={k},N={N},i={i}:quadrature_refinement',
                        max(abs(coarse[key]-oracle[key])/(1+abs(oracle[key])) for key in ('bound','wake','total','half_wake')),gates['quadrature_refinement_scaled'])
                    check(f'd={d},k={k},N={N},i={i}:half_wake_oracle',
                        abs(oracle['half_wake']-oracle['exact_half_wake'])/(1+abs(oracle['exact_half_wake'])),gates['pure_half_wake_scaled'])
                    values=dict(bound=float(actual_bound[i,2]),wake=float(actual_wake[i,2]),total=float(actual[i,2]))
                    errors={key:abs(values[key]-oracle[key])/(1+abs(oracle[key])) for key in values}
                    absolute={key:abs(values[key]-oracle[key]) for key in values}
                    row=dict(offset=d,mode=k,panels=N,receiver_index=int(indices[i]),theta=float(t),y=float(points[i,1]),
                        discrete=values,continuum=oracle,coarse_quadrature=coarse,scaled_errors=errors,absolute_errors=absolute,
                        prandtl_leading=-A*math.sin(k*t)/(2*math.pi*d)+oracle['exact_half_wake'])
                    rows.append(row);case_rows.append(row)
            worst={N:{key:max(row['absolute_errors'][key] for row in case_rows if row['panels']==N)/(abs(A)/B)
                      for key in ('bound','wake','total')} for N in protocol['counts']}
            first,mid,last=protocol['counts'];floor=gates['reference_floor']
            for key in ('bound','wake','total'):
                check(f'd={d},k={k}:fine_{key}',worst[last][key],gates['fine_component_characteristic_error'])
                check(f'd={d},k={k}:first_refinement_{key}',worst[mid][key],worst[first][key]+floor)
                check(f'd={d},k={k}:final_refinement_{key}',worst[last][key],gates['final_refinement_ratio']*worst[mid][key]+floor)
            summary=dict(offset=d,mode=k,max_characteristic_errors_by_count=worst)
            summaries.append(summary);print(json.dumps(summary),flush=True)
    verify()
    report=dict(format='finite-wing-mode-continuum-report-v1',protocol=pin(out/'protocol.json'),rows=rows,summaries=summaries,
        checks=checks,passed=sum(c['passed'] for c in checks),required=len(checks),all_passed=all(c['passed'] for c in checks),
        nonlinear_solves=0,production_edits=0,field_configurations=18,receiver_rows=len(rows),source_pins_unchanged=True,scope=protocol['scope'])
    write(out/'report.json',report)
    print(json.dumps({k:report[k] for k in ('passed','required','all_passed','nonlinear_solves','field_configurations','receiver_rows')}),flush=True)
    if not report['all_passed']: raise SystemExit('At least one predeclared field check failed; all results are retained.')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('mode',choices=['prepare','run'])
    p.add_argument('--output',type=Path,default=ROOT/'artifacts/isae/finite-wing-mode-oracle-20261029')
    args=p.parse_args()
    prepare(args.output.resolve()) if args.mode=='prepare' else run(args.output.resolve())
