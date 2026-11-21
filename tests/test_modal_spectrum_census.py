"""Complete finite-root metadata, independently of selected modal vectors.

These are small analytic descriptor pencils. No model, equilibrium, physical
residual, or modal-output computation is involved.
"""
import json

import numpy as np
import pytest

from openswing.linear_dynamics import eigensystem


def census(report):
    packet = report['finite_spectrum']
    assert packet is not None
    assert packet['scope'] == (
        'Complete numerically reduced finite spectrum, including deflated zero roots.')
    # A portable diagnostic contains eigenvalues, not unrequested mode fields.
    assert set(packet) == {'scope', 'eigenvalues'}
    json.dumps(packet, allow_nan=False)
    values = np.asarray(packet['eigenvalues'], dtype=float)
    assert values.shape == (report['finite_dimension'], 2)
    return values[:, 0] + 1j*values[:, 1]


def assert_roots(actual, expected):
    """Match multiplicities one-to-one without relying on solver order."""
    remaining = list(actual)
    assert len(remaining) == len(expected)
    for value in expected:
        index = int(np.argmin(abs(np.asarray(remaining) - value)))
        assert remaining.pop(index) == pytest.approx(value, rel=2e-10, abs=2e-10)
    assert not remaining


def test_shifted_single_selection_keeps_both_complete_oscillator_pairs():
    # qdd + omega^2 q = 0, for independent omega=2 and omega=7.
    a = np.array([[0., 1., 0., 0.], [-4., 0., 0., 0.],
                  [0., 0., 0., 1.], [0., 0., -49., 0.]])
    modes, report = eigensystem(a, np.eye(4), count=1,
                               shift=(-.1, 6.7), time_scale=3.25, method='dense')
    assert len(modes) == 1
    assert complex(*modes[0]['eigenvalue']) == pytest.approx(7j, abs=2e-10)
    assert report['finite_dimension'] == 4
    assert_roots(census(report), [2j, -2j, 7j, -7j])


@pytest.mark.parametrize('other_roots', [(-3., -5.), ()])
def test_deflated_zero_multiplicity_is_included_even_without_a_dynamic_quotient(other_roots):
    roots = [0., 0., *other_roots]
    modes, report = eigensystem(np.diag(roots), np.eye(len(roots)), count=1,
                               shift=(-2.9, .1), time_scale=2.5, method='dense')
    assert len(modes) == 1
    assert report['integrator_deflation']['count'] == 2
    assert report['finite_dimension'] == len(roots)
    assert_roots(census(report), roots)


def test_algebraic_direction_is_excluded_from_census_after_constraint_reduction():
    # zdot=v, vdot=-9*z-2*v+3*reaction, and 7*reaction=0.
    # The two finite poles solve lambda^2+2*lambda+9=0. The
    # reaction equation has no derivative and contributes no finite pole.
    a = np.array([[0., 1., 0.], [-9., -2., 3.], [0., 0., 7.]])
    m = np.diag([1., 1., 0.])
    rows, columns = np.array([.25, 3., 7.]), np.array([2., .4, 5.])
    modes, report = eigensystem(rows[:, None]*a*columns,
                               rows[:, None]*m*columns, count=1,
                               shift=(-1., 3.), time_scale=4., method='dense')
    assert len(modes) == 1
    assert report['full_dimension'] == 3
    assert report['finite_dimension'] == 2
    assert report['eliminated_dimension'] == 1
    assert_roots(census(report), [-1.+1j*np.sqrt(8), -1.-1j*np.sqrt(8)])


@pytest.mark.parametrize('method', ['shift_invert', 'full_shift_invert'])
def test_actual_arnoldi_search_does_not_claim_complete_census(method):
    # Analytic diagonal poles keep this a deterministic local-search check.
    roots = -np.arange(1., 9.)
    modes, report = eigensystem(np.diag(roots), np.eye(8), count=2,
                               shift=(-4.4, .1), method=method)
    assert report['method'] == method
    assert_roots([complex(*mode['eigenvalue']) for mode in modes], [-4., -5.])
    assert report['finite_spectrum'] is None


def test_dense_fallback_reports_complete_census_even_if_arnoldi_was_requested():
    roots = -np.arange(1., 5.)
    modes, report = eigensystem(np.diag(roots), np.eye(4), count=4,
                               shift=(-2.2, .1), method='shift_invert')
    assert report['requested_method'] == 'shift_invert'
    assert report['method'] == 'dense'
    assert len(modes) == 4
    assert_roots(census(report), roots)
