"""Reproduce a complete nonlinear response with source pins and optional profiling.

Use separate output directories for the baseline and candidate. For example:
OPENBLAS_NUM_THREADS=1 .venv/bin/python scripts/benchmark-time-startup.py \
    --model examples/dae.asw --output /tmp/time-dae --profile
"""
import argparse
import cProfile
import hashlib
import json
from pathlib import Path
import pstats
import sys
import time

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--model',type=Path,default=Path('examples/rectangular.asw'))
parser.add_argument('--kernel-root',type=Path,default=Path(__file__).resolve().parents[1])
parser.add_argument('--output',type=Path,required=True)
parser.add_argument('--panels',type=int,default=48)
parser.add_argument('--duration',type=float,default=.2)
parser.add_argument('--dt',type=float,default=.01)
parser.add_argument('--speed',type=float,default=30)
parser.add_argument('--alpha',type=float,default=5)
parser.add_argument('--mach',type=float)
parser.add_argument('--frame',choices=('prescribed','free','mixed'),default='prescribed')
parser.add_argument('--load-targets',type=json.loads,help='JSON object of mixed/free net force and moment targets')
parser.add_argument('--forcing',type=Path,help='Optional ASWING time-forcing table')
parser.add_argument('--profile',action='store_true')
args=parser.parse_args()
args.output.mkdir(parents=True,exist_ok=True)
if (args.output/'measurement.json').exists():parser.error('Use a new output directory to preserve the previous measurement.')
sys.path.insert(0,str(args.kernel_root.resolve()))
from openswing.asw import parse_asw
from openswing.aero import FlightCondition
from openswing.time_integration import solve_time

source=args.model.read_text()
condition=dict(speed=args.speed,alpha=args.alpha)
if args.mach is not None:condition['mach']=args.mach
forcing='' if args.forcing is None else args.forcing.read_text()
report=dict(model=str(args.model),model_sha256=hashlib.sha256(source.encode()).hexdigest(),
    panels=args.panels,duration=args.duration,dt=args.dt,order=2,frame=args.frame,load_targets=args.load_targets,
    condition=condition,forcing=forcing,tolerance=1e-8,profiled=args.profile,
    modules={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((args.kernel_root/'openswing').glob('*.py'))})
last=-float('inf')
def progress(*event):
    global last
    now=time.monotonic()
    if event[0]=='time_step' and 'initial_seconds' not in report:
        report['initial_seconds']=now-start
        report['initial_cpu_seconds']=time.process_time()-cpu
    if now-last>=2 or not isinstance(event[0],str):
        print(json.dumps(dict(progress=event,elapsed=now-start)),flush=True)
        last=now

profile=cProfile.Profile()
start=time.monotonic();cpu=time.process_time()
try:
    if args.profile:profile.enable()
    result=solve_time(parse_asw(source),FlightCondition(**condition),panels=args.panels,
        duration=args.duration,dt=args.dt,order=2,frame=args.frame,load_targets=args.load_targets,forcing=forcing,progress=progress)
    report.update(status='PASS',evaluations=result['evaluations'],accepted_steps=result['accepted_steps'],
        rejected_steps=result['rejected_steps'],jacobian_builds=result['jacobian_builds'],
        maximum_residual=max(s['residual'] for s in result['snapshots']))
except BaseException as exc:
    report.update(status='INTERRUPTED' if isinstance(exc,KeyboardInterrupt) else 'FAIL',error=str(exc))
    raise
finally:
    profile.disable()
    report.update(monotonic_seconds=time.monotonic()-start,cpu_seconds=time.process_time()-cpu)
    (args.output/'measurement.json').write_text(json.dumps(report,indent=2)+'\n')
    if args.profile:
        profile.dump_stats(str(args.output/'profile.prof'))
        with (args.output/'profile.txt').open('w') as stream:pstats.Stats(profile,stream=stream).sort_stats('cumulative').print_stats(40)
    print(json.dumps(report),flush=True)
(args.output/'response.json').write_text(json.dumps(result,allow_nan=False))
