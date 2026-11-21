"""Actual Fourier solves must use the setup written in the diagnostic row."""
from pathlib import Path
import importlib.util
import json
import numpy as np
import pytest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('sa11_circulation', ROOT/'scripts/verify-isae-sa11-circulation.py')
CHECK = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CHECK)
SOURCE = (ROOT/'examples/isae-sa11-wing-alone.asw').read_text()
CASE = dict(source=SOURCE)


@pytest.mark.parametrize('frozen', [False, True])
@pytest.mark.parametrize('pg', ['speed', 'zero'])
def test_declared_settings_reach_actual_fourier_influences(frozen, pg):
    request = dict(case='wing_alone_literal', panels=8, modes_per_beam=3,
                   alpha=1., speed=240., frozen=frozen, pg=pg)
    row = CHECK.run(CASE, request)
    assert row['status'] == 'computed'
    assert row['specification'] == request
    applied = row['applied_condition']
    assert applied['freeze_influences'] is frozen
    assert applied['mach'] == (None if pg == 'speed' else 0.)
    assert applied['circulation_modes'] == {1: 3}
    actual = row['result']['aerodynamic_influences']
    assert actual['frozen'] is frozen
    assert actual['wind_angles'] == ([0., 0.] if frozen else [1., 0.])
    assert actual['pg_mach'] == pytest.approx(240./340.21 if pg == 'speed' else 0.)
    assert row['result']['circulation_discretization']['independent_unknowns'] == 3
    assert row['weighted_residual'] < 1e-8
    # The record must survive normal JSON persistence, including complete setup.
    assert json.loads(json.dumps(row))['applied_condition']['freeze_influences'] is frozen


def test_local_mach_rejection_keeps_the_applied_current_geometry():
    request = dict(case='wing_alone_literal', panels=100, modes_per_beam=19,
                   alpha=5., speed=240., frozen=False, pg='speed')
    row = CHECK.run(CASE, request)
    assert row['status'] == 'rejected'
    assert row['applied_condition']['freeze_influences'] is False
    assert row['applied_condition']['mach'] is None
    details = row['details']
    assert details['kind'] == 'section_normal_mach'
    assert details['maximum']['normal_mach'] >= 1
    breakdown = details['vortex_breakdown']
    assert breakdown['influence_geometry'] == 'current'
    np.testing.assert_allclose(breakdown['direction'],
                               [np.cos(np.deg2rad(5)),0.,np.sin(np.deg2rad(5))], atol=1e-14)
    assert row['weighted_residual'] < 1e-8


@pytest.mark.parametrize('key,value', [('pg','unknown'),('frozen','False')])
def test_unknown_settings_fail_before_a_solve(key,value):
    request = dict(case='wing_alone_literal',panels=8,modes_per_beam=3,
                   alpha=1.,speed=240.,frozen=False,pg='speed')
    request[key] = value
    with pytest.raises(ValueError, match='setting must be'):
        CHECK.run(CASE,request)
