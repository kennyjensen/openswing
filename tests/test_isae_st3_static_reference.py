"""Independent analytic limits and signed-load reconstruction for ST-3."""
from pathlib import Path
import runpy
import sys
import numpy as np
import pytest
from scipy.optimize import brentq
from scipy.spatial.transform import Rotation

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
from isae_st3_static_reference import solve, stiffness, LENGTH, PROPERTIES


@pytest.mark.parametrize('moment', [-.75, -.55, .55, .75])
def test_uncoupled_dead_couple_has_exact_scalar_equation(moment):
    result = solve('0_3_90', couple=moment)
    theta = brentq(lambda t: t-moment*LENGTH/1.2*np.cos(t), -1., 1., xtol=1e-14)
    assert np.deg2rad(result['observables']['theta_dunn_deg']) == pytest.approx(theta, abs=2e-11)
    np.testing.assert_allclose(result['positions'][-1], [0., LENGTH, 0.], atol=2e-12)


@pytest.mark.parametrize('name', PROPERTIES)
@pytest.mark.parametrize('kind', ['force', 'couple'])
def test_small_load_matches_coupled_beam_compliance(name, kind):
    load = 1e-5
    c = np.linalg.inv(stiffness(name))
    actual = solve(name, **{kind: load})['observables']
    expected = (load*LENGTH**3/3*c[0, 0], load*LENGTH**2/2*c[1, 0]) if kind == 'force' else (
        load*LENGTH**2/2*c[0, 1], load*LENGTH*c[1, 1])
    np.testing.assert_allclose([actual['h_m'], np.deg2rad(actual['theta_dunn_deg'])], expected, rtol=1e-8, atol=2e-13)


@pytest.mark.parametrize('name', PROPERTIES)
def test_integration_refinement_and_load_reversal(name):
    before = solve(name, force=3.924, couple=.55)
    tighter = solve(name, force=3.924, couple=.55, rtol=2e-13, atol=2e-15)
    reverse = solve(name, force=-3.924, couple=-.55)
    np.testing.assert_allclose(before['positions'], tighter['positions'], rtol=0, atol=2e-10)
    np.testing.assert_allclose(before['rotations'], tighter['rotations'], rtol=0, atol=2e-10)
    for key in ['h_m', 'theta_dunn_deg']:
        assert before['observables'][key] == pytest.approx(-reverse['observables'][key], abs=1e-9)


@pytest.mark.parametrize('name', PROPERTIES)
@pytest.mark.parametrize('force,couple', [(-4.905, 0), (0, .75), (3.924, -.55)])
def test_reflected_positive_weights_have_identical_wrench_at_arbitrary_rotations(name, force, couple):
    ns = runpy.run_path(str(ROOT/'scripts/verify-isae-st3-static.py'))
    text = (ns['CACHE']/ns['source_path'](name)).read_text()
    model, derived, loads, proof = ns['reconstruct'](text, name, force, couple)
    # Whole-sphere random orientations, independent of the equilibrium solver.
    rotations = Rotation.random(20, random_state=1972).as_matrix()
    for q in rotations:
        old_f = np.zeros(3); old_m = np.zeros(3)
        new_f = np.sum([r['force'] for r in loads], axis=0) if loads else np.zeros(3)
        new_m = np.zeros(3)
        for p in proof:
            anchor = np.array(p['anchor'])
            of = np.array([0., 0., -p['original_weight_N']])
            nf = np.array([0., 0., -p['derived_weight_N']])
            old_f += of; new_f += nf
            old_m += np.cross(q@(np.array(p['original_point'])-anchor), of)
            new_m += np.cross(q@(np.array(p['derived_point'])-anchor), nf)
        np.testing.assert_allclose(new_f, old_f, atol=2e-14)
        np.testing.assert_allclose(new_m, old_m, atol=2e-14)
    # Every field outside the Weight section is byte-for-byte retained.
    strip = lambda s: ns['re'].sub(r'(?ims)^Weight\s*\n.*?^end\s*$', '', s, count=1)
    assert strip(text) == strip(derived)
