"""Frozen/current infinite-span stall and exact control/state sensitivity checks."""
from dataclasses import asdict
import hashlib
import json
import math
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
from section_stall_reference import section

CONTROLS=(-44.,-40.,-32.,0.,4.,44.)
SPANS=(5900.,59000.,590000.)

def source(span):
    return f'''Name
Frozen/current asymmetric section verification
End
Unit
L 1 m
T 1 s
F 1 N
End
Constant
9.81 1.2256 340.21
End
Reference
{span:.17g} 1 {span:.17g}
End
Ground
1 0 0
End
Beam 1
Uniform controlled wing
t x y z chord Xax twist alpha dCLda CLmin CLmax Cdf Cdp dCLdF1
0 0 0 0 1 0 4 3.7 5.77 -.4 1.4 0 .01364 .071
{span/2:.17g} 0 {span/2:.17g} 0 1 0 4 3.7 5.77 -.4 1.4 0 .01364 .071
End
'''

def reference(control, frozen):
    return section(math.radians(12),math.radians(7.7)+control*.071/5.77,frozen=frozen,twist=math.radians(4))

def compute(control,frozen,span,*,derivatives=False):
    from openswing.asw import parse_asw
    from openswing.aero import FlightCondition,solve_rigid
    model=parse_asw(source(span))
    condition=FlightCondition(speed=20,alpha=12,mach=0,controls={1:control},freeze_influences=frozen)
    result=solve_rigid(model,condition,panels=16)
    assert result['converged'] and result['residual']<=1e-8
    out=dict(condition=asdict(condition),CL=result['CL'],CD=result['CD'],Cm=result['Cm'],
        residual=result['residual'],panels=result['panels'],influences=result['aerodynamic_influences'])
    if derivatives:
        from openswing.rigid_derivatives import rigid_control_derivatives,rigid_state_derivatives
        for name,api in [('control',rigid_control_derivatives(model,condition,16,controls=[1])),
                         ('alpha',rigid_state_derivatives(model,condition,16,parameters=['alpha']))]:
            assert api['base_residual']<=1e-8 and max(api['linear_residuals'])<=1e-8
            out[name]={key:api['coefficients'][i][0] for i,key in enumerate(api['coefficient_rows']) if key in ('CX','CL','Cm')}
    return out

def check(control,frozen):
    expected=reference(control,frozen);assert abs(expected['scalar_residual'])<5e-13
    cases=[];errors=[]
    for span in SPANS:
        actual=compute(control,frozen,span,derivatives=span==SPANS[-1])
        error=max(abs(actual[k]-expected[k]) for k in ('CL','CD','Cm'))
        cases.append(dict(span=span,result=actual,maximum_coefficient_error=error));errors.append(error)
    assert errors[-1]<1e-4,(control,frozen,errors)
    assert all(b<.2*a for a,b in zip(errors,errors[1:])),(control,frozen,errors)
    derivative_errors={name:{key:abs(cases[-1]['result'][name][key]-expected[name][key]) for key in ('CX','CL','Cm')} for name in ('alpha','control')}
    assert max(v for e in derivative_errors.values() for v in e.values())<1e-4,(control,frozen,derivative_errors)
    return dict(control=control,frozen=frozen,reference=expected,cases=cases,derivative_errors=derivative_errors)

def main():
    out=ROOT/'artifacts/isae/frozen-stall-reference-20261107'
    frozen={'frozen':True,'current':False}[sys.argv[1]]
    before={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [*ROOT.glob('openswing/*.py'),Path(__file__),ROOT/'scripts/section_stall_reference.py']}
    results=[]
    for control in CONTROLS:
        result=check(control,frozen);results.append(result)
        print(sys.argv[1],control,[r['maximum_coefficient_error'] for r in result['cases']],flush=True)
    assert all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h for p,h in before.items())
    with (out/(sys.argv[1]+'.json')).open('x') as stream:json.dump(dict(source_sha256=before,results=results),stream,indent=2);stream.write('\n')

if __name__=='__main__':main()
