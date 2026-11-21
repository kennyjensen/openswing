"""Fixed-time-grid spatial extension of the verified inclined UA-2 periodic case."""
from pathlib import Path
from isae_ua2_incidence_periodic import (
    CYCLES, PERIOD, GATES as TIME_GATES, grid as time_grid,
    full_request as request20,
)

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'artifacts/isae/ua2-incidence-periodic-n40-20261101'
OLD=ROOT/'artifacts/isae/ua2-incidence-periodic-20261101-r1'
SEED=ROOT/'artifacts/isae/ua2-incidence-20261101-r3/reference-n40-a9-k0950/report.json'
STEPS=640
MAX_STEPS_PER_JOB=16
REFERENCE_INTERVALS_PER_FILE=256
# This study changes the spatial mesh at fixed temporal resolution. It does not
# claim a new 40-strip temporal-order test; that needs two 40-strip time grids.
GATES={k:v for k,v in TIME_GATES.items() if k!='fine_to_coarse_ratio'}
GATES['mesh_lift_fraction']=.001


def grid():return time_grid(STEPS)


def windows():
    end=len(grid())-1
    return [(a,min(a+MAX_STEPS_PER_JOB,end)) for a in range(0,end,MAX_STEPS_PER_JOB)]


def full_request():
    result=request20(STEPS)
    result['panels']=40
    return result
