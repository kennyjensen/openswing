"""Independent limiting identities and accuracy checks for the stall supplement."""
from dataclasses import replace
import math
from pathlib import Path
import sys

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
from isae_ua_stall_reference import Section, trajectory
from isae_ua_incidence_reference import fields as attached_fields, trajectory as attached_trajectory


def test_zero_strength_recovers_attached_equations_and_cold_history():
    section = Section(stall_factor=0.)
    times = np.linspace(0, section.period, 65)
    old = attached_trajectory(times, alpha_deg=9., boundary='steady', method='quadrature')
    new = trajectory(section, times)
    for key in ('circulation', 'circulation_rate', 'CL', 'CF'):
        np.testing.assert_allclose([r[key] for r in new['rows']], [r[key] for r in old['rows']], atol=2e-9, rtol=1e-9)
    result = section.fields(3., -4.7, 20., rate=12.)
    prior = attached_fields(3., -4.7, 20., alpha_deg=9., rate=12.)
    np.testing.assert_allclose(result['CF'], prior['CF'], atol=1e-14, rtol=0)
    assert result['circulation_rate'] == 12.


@pytest.mark.parametrize('alpha', [-30., -9., 0., 9., 30.])
def test_steady_root_and_pressure_drag_identity(alpha):
    section = Section(alpha_deg=alpha)
    gamma = section.steady_circulation()
    row = section.fields(gamma, 0., 0., rate=0.)
    assert abs(section.rate(gamma, 0.)) < 1e-10
    assert abs(row['residual']) < 1e-13
    assert row['CDp_fixed'] == pytest.approx(4*(row['leakage_velocity']/section.speed)**2, abs=1e-13)
    assert row['CD'] == pytest.approx(row['CDp_fixed'], abs=1e-13)


@pytest.mark.parametrize('cl', [-100., -1.6, -1.5, 0., 1.5, 1.6, 100.])
def test_leakage_symmetry_and_nonlinear_tangent(cl):
    section = Section()
    assert section.leakage_function(-cl) == -section.leakage_function(cl)
    gamma, w, epsilon = cl*section.speed/2, -4.7, 1e-4
    numeric = (section.rate(gamma+epsilon, w)-section.rate(gamma-epsilon, w))/(2*epsilon)
    assert section.rate_derivative(gamma, w) == pytest.approx(numeric, rel=2e-7, abs=2e-8)
    assert section.rate_derivative(gamma, w) < 0


def test_reflection_preserves_drag_and_reverses_lift():
    section = Section()
    positive = section.fields(8., -4.7, -20.)
    negative = replace(section, alpha_deg=-9.).fields(-8., 4.7, 20.)
    for key in ('CL', 'circulation_rate', 'leakage_velocity'):
        assert positive[key] == pytest.approx(-negative[key], abs=1e-13)
    for key in ('CD', 'CDp_fixed'):
        assert positive[key] == pytest.approx(negative[key], abs=1e-13)


def test_independent_integrators_resolve_actual_stall_transition():
    section = Section()
    times = np.linspace(0, section.period, 161)
    explicit, implicit = trajectory(section, times), trajectory(section, times, 'Radau')
    for key in ('circulation', 'circulation_rate', 'CL', 'CDp_fixed'):
        a, b = [np.array([r[key] for r in result['rows']]) for result in (explicit, implicit)]
        assert np.max(abs(a-b))/np.max(abs(b)) < 1e-9
    cl = [r['section_cl'] for r in explicit['rows']]
    assert min(cl) < section.clmax-.1 and max(cl) > section.clmax
    assert max(r['CDp_fixed'] for r in explicit['rows']) > .01
    assert max(abs(r['residual']) for r in explicit['rows']) < 1e-14


def test_invalid_parameters_are_rejected():
    for changes in ({'stall_width':0.}, {'stall_factor':-1.}, {'clmin':2.}, {'alpha_deg':math.nan}):
        with pytest.raises(ValueError):
            Section(**changes)
