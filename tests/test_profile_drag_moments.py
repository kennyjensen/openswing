"""Exact uniform distributed-drag first moments, independent of archived data.

At zero incidence these unswept, untwisted beams have Gamma=0 and constant
profile force per unit arc (theory Eq. 70), no intrinsic drag couple (Eq. 74),
and an analytically integrable first moment (Eq. 188). The Glauert sample is
deliberately noncentral; conserving a point wrench there is not this oracle.
"""
from copy import deepcopy

import numpy as np
import pytest

from openswing.aero import FlightCondition, evaluate_aerodynamics, solve_rigid
from openswing.asw import parse_asw
from openswing.geometry import model_meshes
from openswing.network import StaticNetwork
from openswing.source_coupled import SourceCoupledNetwork


RHO, SPEED, CHORD = 1.1, 13., .8
REFERENCE = np.array([.2, -.3, .5])


def fixture_model(kind, cdf=.012, cdp=.021):
    # Each straight half has displacement (0,2,1.5), length 2.5, and
    # geometric centroid (.35,1,1.15). Starting at t=0 adds its mirror.
    t0, t1 = (0, 2) if kind == 'dihedral' else (1, 3)
    text = (
        'Name\nSynthetic uniform profile force\nEnd\n'
        'Unit\nL 1 m\nT 1 s\nF 1 N\nEnd\n'
        f'Constant\n9.81 {RHO} 340\nEnd\n'
        'Reference\n2 .8 4\n.2 -.3 .5\nEnd\n'
        f'Ground\n1 {t0} 0\nEnd\n'
        'Beam 1\nStraight profile-drag beam\n'
        't x y z chord Xax alpha Cm Cdf Cdp\n'
        f'{t0} .35 0 .4 {CHORD} .4 0 0 {cdf} {cdp}\n'
        f'{t1} .35 2 1.9 {CHORD} .4 0 0 {cdf} {cdp}\nEnd\n')
    model = parse_asw(text, beam_interpolation='drela-segspl-v1')
    assert not model.diagnostics
    return model


def flight():
    return FlightCondition(speed=SPEED, alpha=0., beta=0., density=RHO, mach=0.)


def exact_wrench(kind, cdf=.012, cdp=.021, reference=REFERENCE):
    length = 5. if kind == 'dihedral' else 2.5
    centroid = np.array([.35, 0. if kind == 'dihedral' else 1., 1.15])
    force = np.array([.5 * RHO * SPEED**2 * CHORD * (cdf + cdp) * length, 0., 0.])
    return force, np.cross(centroid - reference, force)


def zero_circulation_evaluation(model, panels):
    meshes = model_meshes(model, panels)
    gamma = np.zeros(sum(len(mesh.tm) for mesh in meshes))
    result = evaluate_aerodynamics(model, flight(), meshes, gamma)
    np.testing.assert_allclose(result['circulation_residual'], 0., rtol=0, atol=2e-14)
    assert result['residual'] < 2e-14
    assert result['converged']
    return meshes, result


@pytest.mark.parametrize('kind', ['dihedral', 'cantilever'])
@pytest.mark.parametrize('panels', [4, 8])
@pytest.mark.parametrize('cdf,cdp', [(.012, 0.), (0., .021), (.012, .021)])
def test_uniform_profile_force_and_first_moment_are_exact(kind, panels, cdf, cdp):
    model = fixture_model(kind, cdf, cdp)
    meshes, result = zero_circulation_evaluation(model, panels)
    force, moment = exact_wrench(kind, cdf, cdp)
    np.testing.assert_allclose(result['force'], force, rtol=2e-14, atol=2e-14)
    np.testing.assert_allclose(result['moment'], moment, rtol=2e-14, atol=2e-14)
    np.testing.assert_allclose(result['CL'], 0., rtol=0, atol=2e-14)
    assert all(strip['circulation'] == 0. for strip in result['strips'])
    # The bent V-wing distinguishes a distributed force from the old point
    # quadrature. On the single straight cantilever the symmetric cosine grid
    # cancels the old interval-arm errors globally, making it a useful control.
    old_point_moment = np.zeros(3)
    for mesh in meshes:
        per_length = .5 * RHO * SPEED**2 * CHORD * (cdf + cdp)
        strip_force = mesh.length[:, None] * [per_length, 0., 0.]
        old_point_moment += np.cross(mesh.rm - REFERENCE, strip_force).sum(axis=0)
    if kind == 'dihedral':
        assert np.linalg.norm(old_point_moment - moment) > 1e-3


@pytest.mark.parametrize('kind', ['dihedral', 'cantilever'])
def test_profile_moment_reference_shift_is_covariant(kind):
    model = fixture_model(kind)
    _, original = zero_circulation_evaluation(model, 4)
    shift = np.array([1.7, -.6, .9])
    moved = deepcopy(model)
    moved.reference[1] += shift
    _, result = zero_circulation_evaluation(moved, 4)
    force, moment = exact_wrench(kind, reference=REFERENCE + shift)
    np.testing.assert_allclose(result['force'], force, rtol=2e-14, atol=2e-14)
    np.testing.assert_allclose(result['moment'], moment, rtol=2e-14, atol=2e-14)
    np.testing.assert_allclose(result['moment'], np.array(original['moment']) - np.cross(shift, force),
                               rtol=2e-14, atol=2e-14)


@pytest.mark.parametrize('kind', ['dihedral', 'cantilever'])
def test_cold_zero_incidence_circulation_has_fresh_zero_residual(kind):
    model = fixture_model(kind)
    solved = solve_rigid(model, flight(), panels=4)
    gamma = np.array([strip['circulation'] for strip in solved['strips']])
    np.testing.assert_allclose(gamma, 0., rtol=0, atol=2e-14)
    fresh = evaluate_aerodynamics(model, flight(), model_meshes(model, 4), gamma)
    np.testing.assert_allclose(fresh['circulation_residual'], 0., rtol=0, atol=2e-14)
    assert solved['converged'] and fresh['converged']
    force, moment = exact_wrench(kind)
    for result in (solved, fresh):
        np.testing.assert_allclose(result['force'], force, rtol=2e-14, atol=2e-14)
        np.testing.assert_allclose(result['moment'], moment, rtol=2e-14, atol=2e-14)


@pytest.mark.parametrize('network_class', [StaticNetwork, SourceCoupledNetwork])
def test_structural_nodal_wrenches_retain_exact_distributed_first_moment(network_class):
    model = fixture_model('cantilever')
    network = network_class(model, 4, flight(), [0., 0., 0.], [])
    r, q, _, _, _, gamma = network.unpack(np.zeros(network.size))
    force, moment = exact_wrench('cantilever')
    # Both compact residual evaluation and detailed output must use the same
    # physical resultant. This is load assembly, not an equilibrium claim.
    for compact in (False, True):
        nodal_force, nodal_moment, aero, *_ = network.external(
            r, q, network.meshes, gamma, network.condition, network.motion,
            ('uniform-profile-check',), _loads_only=compact)
        np.testing.assert_allclose(aero['circulation_residual'], 0., rtol=0, atol=2e-14)
        total_moment = (nodal_moment + np.cross(r - REFERENCE, nodal_force)).sum(axis=0)
        np.testing.assert_allclose(nodal_force.sum(axis=0), force, rtol=2e-14, atol=2e-14)
        np.testing.assert_allclose(total_moment, moment, rtol=2e-14, atol=2e-14)
