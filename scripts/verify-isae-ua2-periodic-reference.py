"""Two-method cold and periodic UA-2 reference for the largest-amplitude pilot."""
import argparse
from hashlib import sha256
import json
import math
from pathlib import Path
import time
import numpy as np
from isae_ua_wing_nonlinear import StraightWing
from isae_ua_wing_periodic import cycle_grid,periodic_solution
from isae_ua_periodic import fourier

ROOT=Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--panels',type=int,choices=(20,40),required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();plan_path=args.output.with_suffix('.plan.json')
    if args.output.exists() or plan_path.exists():parser.error('Use a fresh reference path')
    args.output.parent.mkdir(parents=True,exist_ok=True)
    period=math.pi/9.5;grids={str(n):cycle_grid(period,n) for n in (80,160)}
    times=sorted(set(t for grid in grids.values() for t in grid))
    paths=[Path(__file__).resolve(),*[ROOT/'scripts'/n for n in (
        'isae_ua_wing_nonlinear.py','isae_ua_wing_periodic.py','isae_ua_periodic.py','isae_ua_section_reference.py')],
        ROOT/'.reference/asw_theory.txt',ROOT/'.reference/asw_uns_theory.txt']
    pins={str(p.relative_to(ROOT)):sha256(p.read_bytes()).hexdigest() for p in paths}
    plan=dict(panels=args.panels,span=10.,chord=1.,speed=10.,k=.95,amplitude_ratio=.5,cycles=8,
        grids=grids,source_sha256=pins,reference_methods=['DOP853','Radau'],rtol=1e-11,atol=1e-13,
        periodic_quadrature_steps=5120,reference_agreement_gate_fraction=1e-8,
        native_ASWING_comparison=False,independent_spatial_implementation=True)
    plan_path.write_text(json.dumps(plan,indent=2)+'\n')
    wing=StraightWing(args.panels);results={};durations={}
    for method in plan['reference_methods']:
        start=time.monotonic()
        cold=wing.trajectory(times,amplitude_ratio=.5,k=.95,method=method)
        periodic=periodic_solution(wing,period*np.arange(5121)/5120,amplitude_ratio=.5,k=.95,
            method=method,initial=cold['rows'][-1]['circulation'])
        dense=periodic['rows'];cl=np.array([r['CL'] for r in dense])
        measured=fourier(period*np.arange(5121)/5120,cl,period)
        assert abs(measured['mean'])<1e-10
        antisymmetry=float(np.max(abs(cl[:2561]+cl[2560:]))/np.max(abs(cl)))
        assert antisymmetry<1e-9
        periodic.update(rows=dense[::32],dense_lift=cl.tolist(),measurements=measured,
            half_cycle_lift_symmetry_error_fraction=antisymmetry)
        results[method]=dict(cold=cold,periodic=periodic)
        durations[method]=time.monotonic()-start
        print(json.dumps(dict(method=method,seconds=durations[method],periodic_iterations=periodic['boundary_iterations'],
            closure_fraction=periodic['closure_fraction'])),flush=True)
    differences={}
    for kind in ('cold','periodic'):
        for key in ('CL','circulation','circulation_rate'):
            x,y=(np.array([r[key] for r in results[m][kind]['rows']]) for m in plan['reference_methods'])
            differences[kind+'_'+key]=float(np.max(abs(x-y)/np.max(abs(y),axis=0)))
    passed=max(differences.values())<1e-8
    assert all(sha256((ROOT/n).read_bytes()).hexdigest()==h for n,h in pins.items())
    output=dict(plan=plan,reference=results,seconds=durations,method_difference_fractions=differences,
        numerical_passed=passed,grids=grids,native_ASWING_comparison=False,independent_spatial_implementation=True)
    args.output.write_text(json.dumps(output,indent=2,allow_nan=False)+'\n')
    print(json.dumps(dict(panels=args.panels,cold_times=len(times),differences=differences,passed=passed)),flush=True)
    if not passed:raise SystemExit(1)


if __name__=='__main__':main()
