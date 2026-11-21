"""Reproduce local shell strain/stress and mesh studies (no ASWING benchmark)."""
import hashlib
import json
import platform
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
import scipy
from openswing.asw import parse_asw
from openswing.aero import FlightCondition
from openswing.network import solve_static


source=Path('examples/stress-wing.asw')
model=parse_asw(source.read_text())
cases=[]
for panels in [4,8,16,32]:
    result=solve_static(model,FlightCondition(alpha=5,mach=0),panels=panels)
    assert result['residual']<1e-8
    assert result['structure']['summary']['strain_sections']==len(result['elements'])
    assert result['structure']['summary']['stress_sections']==len(result['elements'])
    case=dict(panels_per_beam=panels,residual=result['residual'],max_displacement=result['max_displacement'],
              structure=result['structure'],elements=result['elements'])
    cases.append(case)
    print(panels,result['structure']['summary'],flush=True)
report=dict(description='Internal material-midpoint shell recovery study. Not an ASWING executable or strength validation.',
            source_sha256={str(source):hashlib.sha256(source.read_bytes()).hexdigest()},
            condition=dict(speed=30,alpha=5,mach=0),
            versions=dict(python=platform.python_version(),numpy=np.__version__,scipy=scipy.__version__),cases=cases)
Path('docs/validation/section-recovery.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
