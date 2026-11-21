"""Reproduce lower-atmosphere states and coupled flight-condition checks."""
import hashlib
import json
from pathlib import Path
import sys
import numpy as np
import scipy

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from openswing.asw import parse_asw
from openswing.atmosphere import standard_atmosphere
from openswing.aero import FlightCondition
from openswing.network import solve_static
from openswing.operating import OperatingConstraint

source = Path('examples/flexible.asw').read_bytes()
model = parse_asw(source.decode())
cases = []
for altitude in (0, 10000, 20000):
    condition = FlightCondition(speed=25, alpha=3, mach=0, altitude_m=altitude,
                                gravity_magnitude=4, load_factor=1.5)
    result = solve_static(model, condition, panels=8,
                          operating_constraints=[OperatingConstraint('speed', 'equivalent_airspeed', 30),
                                                 OperatingConstraint('alpha', 'lift', 1000)])
    assert abs(result['operating_constraints'][1]['actual']-1500) < 1e-6
    assert result['residual'] < 1e-8
    assert np.linalg.norm(result['force_balance']) < 1e-5
    assert np.linalg.norm(result['moment_balance']) < 1e-5
    keys = ['atmosphere', 'operating_values', 'operating_constraints', 'max_displacement', 'residual',
            'force_balance', 'moment_balance', 'mass_properties', 'gravity_body']
    cases.append({key: result[key] for key in keys})
    print(f"{altitude} m: TAS={result['operating_values']['speed']:.9f}, alpha={result['operating_values']['alpha']:.9f}, lift=1500 N", flush=True)
output = dict(description='Published US76 equations and independent coupled operating checks; ASWING table/VIAS parity unverified.',
              reference='https://ntrs.nasa.gov/citations/19770009539',
              source='examples/flexible.asw', source_sha256=hashlib.sha256(source).hexdigest(),
              conditions=dict(panels_per_beam=8, equivalent_airspeed=30, specified_lift=1000,
                              load_factor=1.5, gravity_magnitude=4, pg_mach=0),
              units='Aircraft uses m,s,N; atmospheric altitude uses geometric metres independently of Earth Z.',
              python=sys.version.split()[0], numpy=np.__version__, scipy=scipy.__version__,
              standard_states=[standard_atmosphere(z) for z in (-5000, 0, 5000, 11000, 20000, 50000, 80000, 86000)],
              cases=cases)
Path('docs/validation/atmosphere-and-targets.json').write_text(json.dumps(output, indent=2)+'\n')
