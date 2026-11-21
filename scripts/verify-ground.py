"""Reproduce image-plane height/mesh sensitivity; not an ASWING benchmark."""
import hashlib
import json
from pathlib import Path
import sys
import numpy as np
import scipy

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from openswing.asw import parse_asw
from openswing.aero import FlightCondition,solve_rigid
from openswing.network import solve_static


def case(path,flag,height,panels,coupled=False):
    source=Path(path).read_bytes()
    condition=FlightCondition(alpha=5,mach=0,ground_effect=flag,
                              position_earth=(0,0,height),attitude=(0,5,0))
    result=(solve_static if coupled else solve_rigid)(parse_asw(source.decode()),condition,panels=panels)
    keys=['CL','CD','CDi','CDbody','Cm','residual','panels','ground_plane','earth_state']
    if coupled:keys+=['max_displacement','gravity_body','force_balance','moment_balance']
    assert result['residual']<1e-8
    if coupled:
        assert np.linalg.norm(result['force_balance'])<1e-5
        assert np.linalg.norm(result['moment_balance'])<1e-5
    print(f'{path}, flag={flag}, h={height}, panels={panels}: CL={result["CL"]:.9f}, CDi={result["CDi"]:.9f}',flush=True)
    return dict(source=path,source_sha256=hashlib.sha256(source).hexdigest(),coupled=coupled,
                condition=dict(speed=30,alpha=5,beta=0,mach=0,attitude=[0,5,0],position_earth=[0,0,height],ground_effect=flag,ground_normal=[0,0,1]),
                requested_panels_per_beam=panels,values={key:result[key] for key in keys})


rows=[]
for panels in (12,24,48):
    for flag,height in [(0,2),(1,1),(1,2),(1,5),(1,20),(-1,1)]:
        rows.append(case('examples/rectangular.asw',flag,height,panels))
for panels in (8,16):
    rows.append(case('examples/wing-body.asw',1,2,panels,True))
output=dict(description='Internal height/mesh sensitivity and equilibrium checks, not comparison with ASWING or experiment.',
            units='Original examples use m, s, N. Positions are in Earth axes; aircraft loads remain body-axis values.',
            python=sys.version.split()[0],numpy=np.__version__,scipy=scipy.__version__,cases=rows)
Path('docs/validation/ground-images.json').write_text(json.dumps(output,indent=2)+'\n')
