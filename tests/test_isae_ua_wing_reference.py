"""Independent integration and force identities for the coupled 3D UA reference."""
import importlib.util
import json
import math
from pathlib import Path
import sys

import numpy as np
import pytest
from scipy.integrate import solve_ivp

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
from isae_ua_wing_reference import arrays, assemble, harmonic, response
from isae_suite_unsteady import harmonic_response


@pytest.fixture(scope='module')
def reference():
    return assemble(4)


def test_coupled_operator_preserves_documented_lag_and_force_terms(reference):
    K, M, rv, ra, fg, fd, fv, fa = arrays(reference)
    speed = reference['settings']['speed']
    assert reference['numerical_passed']
    # Eq49 b=2/pi, with the residual normalized by incident speed.
    np.testing.assert_allclose(M, -2/(math.pi*speed**2)*np.eye(len(K)), atol=1e-14, rtol=0)
    assert np.max(np.abs(K-np.diag(np.diag(K)))) > 1e-4
    np.testing.assert_allclose(rv, -np.ones(len(K))/speed, atol=1e-10, rtol=0)
    np.testing.assert_allclose(ra, 0, atol=1e-14, rtol=0)
    # Uniform Gamma/Gamma-dot and unit chord: unsteady Eqs34,35,43.
    # Prescribed off-equilibrium Gamma also creates a cubic profile-force
    # term. Verify the O(step^2) central-difference error independently;
    # the analytic force identity applies to its zero-step limit.
    half = assemble(4, step=reference['settings']['derivative_step']/2)
    fine_fg = np.asarray(half['matrices']['fg'])
    assert abs(sum(fine_fg)-2/speed) < .35*abs(sum(fg)-2/speed)
    assert (4*sum(fine_fg)-sum(fg))/3 == pytest.approx(2/speed, abs=2e-14, rel=0)
    assert sum(fd) == pytest.approx(2/speed**2, abs=1e-12)
    assert fa == pytest.approx(-math.pi/(2*speed**2), abs=1e-12)


@pytest.mark.parametrize('k', [.475, .95])
def test_exact_matrix_heave_matches_separate_ODE_integration(reference, k):
    K, M, rv, ra, fg, fd, fv, fa = arrays(reference)
    amplitude, speed = .001, reference['settings']['speed']
    omega, h = 2*speed*k, amplitude/2
    times = np.linspace(0, 2*math.pi/omega, 17)
    expected = response(reference, times, amplitude_ratio=amplitude, k=k)
    def derivative(t, gamma):
        w, a = -h*omega*math.sin(omega*t), -h*omega**2*math.cos(omega*t)
        return np.linalg.solve(M, -K@gamma-rv*w-ra*a)
    result = solve_ivp(derivative, (0,times[-1]), np.zeros(len(K)), t_eval=times,
        method='DOP853', rtol=1e-12, atol=1e-14)
    assert result.success
    for t, gamma, row in zip(times, result.y.T, expected):
        np.testing.assert_allclose(gamma, row['circulation'], atol=2e-12, rtol=0)
        rate = derivative(t,gamma)
        cl = fg@gamma+fd@rate-fv*h*omega*math.sin(omega*t)-fa*h*omega**2*math.cos(omega*t)
        assert cl == pytest.approx(row['CL'], abs=2e-12, rel=0)
        assert row['residual'] < 1e-14
    assert expected[0]['CL'] == pytest.approx(math.pi*amplitude*k*k, abs=1e-14)


def test_frame_and_nodal_motion_linearizations_give_the_same_harmonic_response(reference):
    frequencies = (.475,.95)
    old = harmonic_response(ROOT, reference['settings'], frequencies=frequencies)
    new = harmonic(reference, frequencies)
    for p,q in zip(old['response'],new):
        for field in ('CL_real','CL_imag','amplitude','phase_deg'):
            assert p[field] == pytest.approx(q[field], abs=1e-8, rel=0)


@pytest.mark.parametrize('panels,amplitude', [('40','.001'),('4','.05')])
def test_time_verifier_rejects_a_mismatched_reference_before_starting(reference, tmp_path, monkeypatch, panels, amplitude):
    ref_path = tmp_path/'reference.json'
    ref_path.write_text(json.dumps(dict(reference, unchanged_code=True, source_sha256={})))
    spec = importlib.util.spec_from_file_location('ua_time_guard', ROOT/'scripts/verify-isae-ua-time.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    destination = tmp_path/'must-not-start'
    monkeypatch.setattr(sys,'argv',['verify-isae-ua-time.py','--steps','40',
        '--panels',panels,'--amplitude-ratio',amplitude,'--aspect-ratio','10',
        '--linear-wing-reference',str(ref_path),'--output-dir',str(destination)])
    with pytest.raises(SystemExit) as error:
        module.main()
    assert error.value.code == 2
    assert not destination.exists()
