"""Internal articulated-wing mesh study; no ASWING/experimental parity claim."""
import hashlib
import json
from pathlib import Path
import sys
import numpy as np
import scipy

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from openswing.asw import parse_asw
from openswing.aero import FlightCondition, solve_rigid
from openswing.network import solve_static

source = Path('examples/articulated.asw').read_bytes()
model = parse_asw(source.decode())
condition = FlightCondition(alpha=5, mach=0)
rows = []
for panels in (4, 8, 16):
    rigid = solve_rigid(model, condition, panels=panels)
    result = solve_static(model, condition, panels=panels)
    assert result['residual'] < 1e-8
    assert np.linalg.norm(result['force_balance']) < 1e-5
    assert np.linalg.norm(result['moment_balance']) < 1e-5
    assert abs(result['hinges'][0]['angle_deg']+result['hinges'][1]['angle_deg']) < 1e-7
    keys = ['CL', 'CD', 'CDi', 'residual', 'max_displacement', 'hinges', 'force_balance', 'moment_balance']
    rows.append(dict(requested_panels_per_beam=panels, rigid_CL=rigid['CL'],
                     values={key: result[key] for key in keys}))
    print(f"{panels} panels per beam: CL={result['CL']:.9f}, angle={result['hinges'][0]['angle_deg']:.9f} deg", flush=True)
output = dict(description='Independent coupled mesh sensitivity, not an ASWING or experimental comparison.',
              source='examples/articulated.asw', source_sha256=hashlib.sha256(source).hexdigest(),
              condition=dict(speed=30, alpha=5, beta=0, mach=0), units='m, s, N; hinge angles in degrees.',
              python=sys.version.split()[0], numpy=np.__version__, scipy=scipy.__version__, cases=rows)
Path('docs/validation/sprung-hinges.json').write_text(json.dumps(output, indent=2)+'\n')
