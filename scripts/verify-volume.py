"""Reproduce mixed-volume mesh sensitivity and official-input convergence.

Fetch reference inputs separately with fetch-references.py. These are internal
OpenSwing calculations, not reference ASWING outputs or experimental validation.
"""
import hashlib
import json
from pathlib import Path
import sys
import time
import numpy as np
import scipy

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from openswing.asw import parse_asw
from openswing.aero import FlightCondition, solve_rigid
from openswing.network import solve_static


def case(path, speed, panels, coupled):
    source=Path(path).read_bytes()
    model=parse_asw(source.decode())
    start=time.monotonic()
    result=(solve_static if coupled else solve_rigid)(model,FlightCondition(speed=speed,alpha=5,mach=0),panels=panels)
    keys=('CL','CD','Cm','panels','lifting_panels','residual','body_force','apparent_mass')
    if coupled:
        keys+=('structural_nodes','max_displacement','force_balance','moment_balance')
    record=dict(source=path,source_sha256=hashlib.sha256(source).hexdigest(),
                condition=dict(speed=speed,alpha=5,beta=0,mach=0,body_added_mass_factor=1),
                requested_panels_per_beam=panels,coupled=coupled,
                values={key:result[key] for key in keys})
    if coupled:
        fs=max(1.,np.linalg.norm(result['applied_force']),np.linalg.norm(result['support_force']))
        ms=max(1.,np.linalg.norm(result['applied_moment']),np.linalg.norm(result['support_moment']))
        record['relative_force_balance']=float(np.linalg.norm(result['force_balance'])/fs)
        record['relative_moment_balance']=float(np.linalg.norm(result['moment_balance'])/ms)
        assert record['relative_force_balance']<1e-8 and record['relative_moment_balance']<1e-8
    assert result['converged'] and result['residual']<1e-8
    print(f'{path}, {panels} panels, coupled={coupled}: CL={result["CL"]:.9f}, {time.monotonic()-start:.1f}s',flush=True)
    return record


records=[case('examples/wing-body.asw',30,n,True) for n in (8,16,32)]
for name,speed in [('fw',50),('usa',60),('dae',20)]:
    path=f'.reference/{name}.asw'
    if not Path(path).exists():
        raise SystemExit('Missing official inputs; first run scripts/fetch-references.py.')
    for coupled,panels in [(False,12),(True,4)]:
        records.append(case(path,speed,panels,coupled))
output=dict(description='Internal mesh sensitivity and official-input convergence only; no numerical ASWING comparison.',
            units='All dimensional values use each input file\'s consistent units; official inputs are not relabeled SI.',
            reference_base='https://web.mit.edu/drela/Public/web/aswing/',
            python=sys.version.split()[0],numpy=np.__version__,scipy=scipy.__version__,cases=records)
Path('docs/validation/volume-and-official-inputs.json').write_text(json.dumps(output,indent=2)+'\n')
