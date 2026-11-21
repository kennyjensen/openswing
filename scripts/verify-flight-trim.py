"""Reproduce coupled steady-turn refinement, without claiming ASWING parity."""
import hashlib
import json
from pathlib import Path
import platform
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np
import scipy
from openswing.asw import parse_asw
from openswing.aero import FlightCondition
from openswing.network import solve_static
from openswing.operating import steady_turn_constraints


source = Path('examples/trim-aircraft.asw').read_bytes()
model = parse_asw(source.decode())
cases = []
for panels, rate, path in [(4,0,0),(4,3,0),(8,3,0),(16,3,0),(32,3,0),(4,2,5)]:
    c = FlightCondition(speed=30,alpha=4,mach=0,powers={1:120},attitude=(0,4,57))
    result = solve_static(model,c,panels=panels,operating_constraints=steady_turn_constraints(
        np.deg2rad(rate),path,trim_controls=[2,1,3],engine_control=1))
    assert result['residual'] < 1e-8
    assert np.max(np.abs(result['applied_force'])) < 1e-6
    assert np.max(np.abs(result['applied_moment'])) < 1e-6
    assert np.max(np.abs(result['earth_state']['velocity_derivative_body'])) < 1e-8
    cases.append(dict(requested_panels_per_beam=panels,heading_rate_deg_per_T=rate,flight_path_deg=path,
                      **{key:result[key] for key in ('panels','lifting_panels','structural_nodes','residual',
                          'max_displacement','CL','CDi','operating_values','operating_constraints','earth_state',
                          'applied_force','applied_moment','support_force','support_moment','force_balance','moment_balance')}))
    print(f'{panels} panels/beam, heading rate {rate}, path {path}: alpha={result["operating_values"]["alpha"]:.9f}, '
          f'bank={result["earth_state"]["attitude"][0]:.9f}, displacement={result["max_displacement"]:.9f}',flush=True)
report = dict(description='Internal common-residual flight-trim and mesh study; no ASWING executable or experimental comparison.',
              source='examples/trim-aircraft.asw',source_sha256=hashlib.sha256(source).hexdigest(),
              versions=dict(python=platform.python_version(),numpy=np.__version__,scipy=scipy.__version__),
              condition=dict(speed=30,beta=0,mach=0,heading_deg=57),
              preset=dict(roll_flap=2,pitch_flap=1,yaw_flap=3,engine_control=1),cases=cases)
Path('docs/validation/steady-flight-trim.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
