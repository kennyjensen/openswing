from pathlib import Path
import json
import numpy as np
from openswing.bridge import run_json


def test_browser_json_boundary_returns_finite_results_with_control_keys():
    source = Path('examples/rectangular.asw').read_text()
    model = json.loads(run_json(json.dumps(dict(action='inspect', source=source))))
    assert model['controls'] == [1]
    assert model['beams'][0]['lifting']
    request = dict(action='solve', source=source, panels=24, condition=dict(alpha=3, controls={'1':2}))
    result = json.loads(run_json(json.dumps(request)))
    assert result['converged'] and result['residual'] < 1e-8
    assert np.isfinite(result['CL'])
    assert result['Cl'] < 0


def test_browser_json_boundary_includes_coupled_geometry_and_reactions():
    source = Path('examples/flexible.asw').read_text()
    request = dict(action='solve', mode='mounted', source=source, panels=8, condition=dict(alpha=5, mach=0))
    result = json.loads(run_json(json.dumps(request)))
    assert result['analysis'] == 'mounted_static'
    assert result['max_displacement'] > 1
    assert result['geometry'][0]['panels'] == result['structural_elements']
    assert result['reactions'][0]['kind'] == 'ground'
    assert max(abs(v) for v in result['force_balance']) < 1e-6


def test_free_flight_json_boundary_returns_accelerations_and_zero_net_loads():
    source = Path('examples/inertial.asw').read_text()
    request = dict(action='solve', mode='free', source=source, panels=8,
                   condition=dict(alpha=5, mach=0, rates=[0, 0, .03]))
    result = json.loads(run_json(json.dumps(request)))
    assert result['analysis'] == 'constrained_static'
    assert len(result['operating_constraints']) == 6
    assert result['mass_properties']['mass'] == 100
    assert np.linalg.norm(result['apparent_force']) > 1
    assert max(abs(v) for v in result['applied_force']) < 1e-5
    assert max(abs(v) for v in result['applied_moment']) < 1e-5
