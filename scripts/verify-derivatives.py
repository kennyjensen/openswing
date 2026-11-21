"""Reproduce coupled derivative mesh and step studies; no ASWING comparison."""
import hashlib
import json
from pathlib import Path
import platform
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
import scipy
from openswing.asw import parse_asw
from openswing.aero import FlightCondition
from openswing.network import solve_static
from openswing.operating import steady_turn_constraints


cases=[]; sources={}
for name,panels,step in [('flexible',4,1e-5),('flexible',8,1e-5),('flexible',16,1e-5),('flexible',32,1e-5),
                         ('trim-aircraft',4,1e-5),('trim-aircraft',8,1e-5),('trim-aircraft',8,3e-6)]:
    path=Path(f'examples/{name}.asw');source=path.read_bytes();sources[str(path)]=hashlib.sha256(source).hexdigest()
    model=parse_asw(source.decode())
    free=name=='trim-aircraft'
    condition=FlightCondition(alpha=4 if free else 5,mach=0,powers={1:120} if free else {})
    targets=steady_turn_constraints(.04,trim_controls=[2,1,3],engine_control=1) if free else []
    result=solve_static(model,condition,panels=panels,operating_constraints=targets,
                        derivatives=dict(response='free_flight' if free else 'fixed_acceleration',step=step,
                                         parameters=['u','alpha','p','control.1','power.1'] if free else ['u','alpha']))
    d=result['derivatives'];assert max(d['linear_residuals'])<1e-8
    # Global matrices and the full node/rotation/internal-load response are all
    # retained for independent reproduction and follow-up comparison.
    cases.append(dict(source=str(path),panels_per_beam=panels,base_residual=result['residual'],
                      max_displacement=result['max_displacement'],derivatives=d))
    print(name,panels,step,'CL_alpha',d['matrices']['coefficients'][2][1],
          'rcond',d['column_scaled_reciprocal_condition'],flush=True)
report=dict(description='Internal implicit-derivative mesh/step study. Not an ASWING executable or experimental comparison.',
            source_sha256=sources,versions=dict(python=platform.python_version(),numpy=np.__version__,scipy=scipy.__version__),cases=cases)
Path('docs/validation/coupled-derivatives.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
