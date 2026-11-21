"""Build a finite-amplitude UA-2 reference with two independent ODE methods."""
import argparse
from hashlib import sha256
import json
import math
from pathlib import Path
import time

import numpy as np
from isae_ua_startup import heave_grid
from isae_ua_wing_nonlinear import StraightWing

ROOT=Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--panels',type=int,choices=(20,40),required=True)
    parser.add_argument('--amplitude-ratio',type=float,choices=(.05,.1,.3,.5),default=.5)
    parser.add_argument('--k',type=float,choices=(.475,.95),default=.95)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();plan_path=args.output.with_suffix('.plan.json')
    if args.output.exists() or plan_path.exists():parser.error('Preserve reference evidence; use a fresh path')
    args.output.parent.mkdir(parents=True,exist_ok=True)
    period=math.pi/(10*args.k)
    grids={str(n):heave_grid(period,n,256,1.125) for n in (80,160)}
    times=sorted(set(t for grid in grids.values() for t in grid))
    paths=[Path(__file__).resolve(),ROOT/'scripts/isae_ua_wing_nonlinear.py',ROOT/'scripts/isae_ua_startup.py',
        ROOT/'.reference/asw_theory.txt',ROOT/'.reference/asw_uns_theory.txt']
    pins={str(p.relative_to(ROOT)):sha256(p.read_bytes()).hexdigest() for p in paths}
    plan=dict(panels=args.panels,span=10.,chord=1.,speed=10.,k=args.k,amplitude_ratio=args.amplitude_ratio,
        grids=grids,source_sha256=pins,reference_methods=['DOP853','Radau'],rtol=1e-11,atol=1e-13,
        gate='Methods must agree within 1e-8 of peak for lift, circulation and each strip circulation rate.',
        native_ASWING_comparison=False,independent_spatial_implementation=True)
    plan_path.write_text(json.dumps(plan,indent=2)+'\n')
    wing=StraightWing(args.panels);results={};durations={}
    for method in plan['reference_methods']:
        start=time.monotonic()
        results[method]=wing.trajectory(times,amplitude_ratio=args.amplitude_ratio,k=args.k,method=method)
        durations[method]=time.monotonic()-start
        print(json.dumps(dict(method=method,seconds=durations[method],evaluations=results[method]['evaluations'])),flush=True)
    a,b=results['DOP853']['rows'],results['Radau']['rows']
    errors={}
    for key in ('CL','circulation','circulation_rate'):
        x,y=np.array([r[key] for r in a]),np.array([r[key] for r in b])
        peak=np.max(np.abs(y),axis=0)
        errors[key]=float(np.max(np.abs(x-y)/peak))
    passed=max(errors.values())<1e-8
    assert all(sha256((ROOT/n).read_bytes()).hexdigest()==h for n,h in pins.items())
    output=dict(plan=plan,reference=results,seconds=durations,method_difference_fractions=errors,
        numerical_passed=passed,grids=grids,native_ASWING_comparison=False,independent_spatial_implementation=True)
    args.output.write_text(json.dumps(output,indent=2,allow_nan=False)+'\n')
    print(json.dumps(dict(panels=args.panels,unique_times=len(times),difference_fractions=errors,passed=passed)),flush=True)
    if not passed:raise SystemExit(1)


if __name__=='__main__':main()
