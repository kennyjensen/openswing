"""The published beam equation must retain small translations and strains."""
import numpy as np
import pytest

from test_source_discrete import network


@pytest.mark.parametrize('increment', [1e-18, -1e-18, 1e-20])
def test_sub_ulp_translation_changes_both_adjacent_element_equations(increment):
    n = network()
    original = np.zeros(n.size)
    trial = original.copy()
    node = 2
    trial[6*node+1] = increment
    # The public absolute coordinates cannot represent this displacement.
    np.testing.assert_array_equal(n.unpack(trial)[0], n.rj)
    change = (n.residual(trial)-n.residual(original))[:6*n.ne].reshape(n.ne, 6)
    expected = np.zeros_like(change)
    expected[node-1, 1] = increment
    expected[node, 1] = -increment
    np.testing.assert_array_equal(change, expected)


def test_sub_ulp_axial_strain_is_not_lost_when_adding_unit_tangent():
    n = network()
    state = np.zeros(n.size)
    element = 2
    force = 1e-15
    state[6*n.nn+6*element+1] = force/n.F
    strain = force*n.source_axial_compliance[element]
    assert 1.+strain == 1.
    observed = n.residual(state)[:6*n.ne].reshape(n.ne, 6)[element, 1]
    assert observed == -strain*n.ds[element]/n.L
    assert observed != 0.


def test_displacement_form_retains_literal_finite_rotation_and_load_equation():
    n = network()
    rng = np.random.default_rng(3821)
    state = rng.normal(0, .1, n.size)
    actual, data = n.residual(state, detail=True)
    pa, pb, ra, rb, *_ = n.geometry(data['r'], data['Q'])
    transform = (np.swapaxes(ra, -1, -2)+np.swapaxes(rb, -1, -2))/2
    force = np.einsum('nij,nj->ni', transform, data['N'])
    moment = np.einsum('nij,nj->ni', transform, data['M'])
    strain, _ = n.constitutive_response(force, moment)
    strain[:, 1] += 1.
    literal = (pb-pa-np.einsum('nji,nj->ni', transform, strain)*n.ds[:, None])/n.L
    np.testing.assert_allclose(actual[:6*n.ne].reshape(n.ne,6)[:, :3], literal,
                               rtol=3e-15, atol=3e-16)
