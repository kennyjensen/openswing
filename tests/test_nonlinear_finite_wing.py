"""Finite-chord, nonlinear continuum oracle independent of horseshoe assembly.

The reference integrates continuous bound/trailing vorticity and solves the
documented section equations. It is not an archived ASWING result. Its modal
refinement, off-grid residuals and independent whole-loading integrals are
recorded with the fixture provenance. The 0.05% gate allows the finite N128
cosine-grid error and is separate from the native ISAE comparison tolerance.
"""
import json
from pathlib import Path

import numpy as np
import pytest

from openswing.asw import parse_asw
from openswing.aero import FlightCondition, solve_rigid


REFERENCE = json.loads((Path(__file__).parent/'data'/'nonlinear-finite-wing.json').read_text())


@pytest.mark.parametrize('case', REFERENCE['rows'], ids=lambda c:f"alpha-{c['alpha']:g}")
def test_full_polar_against_independent_nonlinear_continuum(case):
    p=REFERENCE['inputs']
    model=parse_asw(f"""Name
Finite-chord continuum regression
End
Unit
L 1 m
T 1 s
F 1 N
End
Constant
9.81 {p['density']} {p['sound_speed']}
End
Reference
{p['area']} {p['chord']} {p['span']}
End
Beam 1
Rigid rectangular wing
t y chord Xax dCLda CLmin CLmax
{-p['halfspan']} {-p['halfspan']} {p['chord']} 0 {p['slope']} {p['lower']} {p['upper']}
{p['halfspan']} {p['halfspan']} {p['chord']} 0 {p['slope']} {p['lower']} {p['upper']}
End
""")
    actual=solve_rigid(model,FlightCondition(speed=47.9,density=p['density'],alpha=case['alpha'],mach=0,
        freeze_influences=False,stall=True,stall_factor=p['stall_factor'],stall_width=p['stall_width']),panels=128)
    assert actual['converged'] and actual['residual']<=1e-8
    assert np.max(np.abs(actual['circulation_local_residual']))<=1e-8
    assert actual['lifting_airflow']['maximum']['normal_mach']<1
    for key in ('CLi','CDi','efficiency'):
        assert actual[key]==pytest.approx(case[key],rel=5e-4,abs=1e-14),key
