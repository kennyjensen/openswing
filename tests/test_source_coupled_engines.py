"""Mounted-source engine checks from steady Eqs. 89–90 and 97–105.

The exact point-wrench targets do not use engine_load or StaticNetwork's load
transfer. Disk/jet checks exercise the shared model at a moved pylon; complete
residual stencils check the composed derivatives. These are implementation
checks, not an archived ASWING or experimental comparison.
"""
from copy import deepcopy
from dataclasses import replace

import numpy as np
import pytest
from scipy.spatial.transform import Rotation

from openswing.aero import AnalysisError
from openswing.circulation_tangent import circulation_columns
from openswing.equilibrium_state import capture, restore
from openswing.geometry_tangent import geometry_columns
from openswing.source_coupled import SourceCoupledNetwork, solve_source_coupled
from openswing.source_discrete import COUPLED_POLICY, SourceSectionNetwork
from openswing.structured_static import linearization
from test_source_coupled import condition, model, trial, assert_balanced


def powered_model(typ=0, *, jet=False, rigid=False, mass=True, shared=False):
    value = model(rigid=rigid, mass=mass)
    row = np.zeros(25)
    row[:4] = [1, typ, 1, 2.]
    row[4:7] = value.beams[0].position(2.) + [-.7, .08, -.07]
    row[7:15] = [-1., .08, .12, 1.7, -.23,
                  .45 if jet else -.45, 80., .0004]
    row[15:] = [.6, 5.8, .4, .3, .25, .15, .18, .1, .12, .07]
    value.records['engine'] = [row]
    if shared:
        other = row.copy()
        other[3] = 2.65
        other[4:7] = value.beams[0].position(other[3]) + [-.3, -.04, .13]
        other[7:12] = [-.9, -.2, .3, .6, .11]
        value.records['engine'].append(other)
    return value


def network(typ=0, *, jet=False, frozen=False, rigid=False, mass=True, shared=False):
    return SourceCoupledNetwork(
        powered_model(typ, jet=jet, rigid=rigid, mass=mass, shared=shared), 4,
        condition(powers={1: 3. if typ == 0 else 40.}, freeze_influences=frozen),
        [1., -2., -10.] if mass else [0., 0., 0.], [])


def external(n, r, q, gamma, *, power=None):
    c = n.condition if power is None else replace(n.condition, powers={1: power})
    meshes = n.deformed_meshes(r, q, n.geometry(r, q))
    return n.external(r, q, meshes, gamma, c, c.motion(), ('test', repr(c)))


def proportional_target(n, r, q, power):
    force, moment = np.zeros_like(r), np.zeros_like(r)
    states = []
    for row in n.engines:
        j = n.node(*row[2:4])
        axis = q[j] @ (row[7:10] / np.linalg.norm(row[7:10]))
        arm = q[j] @ (row[4:7] - n.rj[j])
        f, m = power * row[10] * axis, power * row[11] * axis
        force[j] += f
        moment[j] += m + np.cross(arm, f)
        states.append((r[j] + arm, f, m))
    return force, moment, states


def test_shared_power_rotated_pylons_are_concentrated_and_reference_covariant():
    n = network(shared=True)
    r, q, *_, gamma = n.unpack(trial(n))
    # A finite common rotation and translation checks objectivity of the point
    # loads; differences at zero power remove all unrelated air/gravity loads.
    rotation = Rotation.from_rotvec([.13, -.09, .07]).as_matrix()
    shift = np.array([.4, -.6, .3])
    reference = np.array([-.2, .1, .5])
    first = None
    for rotated in (False, True):
        position = r @ rotation.T + shift if rotated else r
        orient = rotation @ q if rotated else q
        off = external(n, position, orient, gamma, power=0.)
        mass_before = deepcopy(n.mass_cached)
        on = external(n, position, orient, gamma)
        df, dm = on[0] - off[0], on[1] - off[1]
        target_f, target_m, states = proportional_target(n, position, orient, 3.)
        np.testing.assert_allclose(df, target_f, rtol=0, atol=3e-14)
        np.testing.assert_allclose(dm, target_m, rtol=0, atol=3e-14)
        for got, (p, f, m) in zip(on[2]['engines'], states):
            np.testing.assert_allclose(got['position'], p, atol=3e-15)
            np.testing.assert_allclose(got['force'], f, atol=3e-15)
            np.testing.assert_allclose(got['moment'], m, atol=3e-15)
        # Engines have no mass. Their point loads must not enter distributed
        # endpoint forces/couples or the source gravity cache.
        for j in (4, 5):
            np.testing.assert_array_equal(on[j], off[j])
        for j in (0, 1, 3, 4):
            np.testing.assert_array_equal(n.mass_cached[j], mass_before[j])
        for before, after in zip(mass_before[2], n.mass_cached[2]):
            for key in ('mass', 'position', 'inertia', 'spin'):
                np.testing.assert_array_equal(before[key], after[key])
        total_f = df.sum(axis=0)
        ref = rotation @ reference + shift if rotated else reference
        total_m = (dm + np.cross(position-ref, df)).sum(axis=0)
        direct_m = sum((m + np.cross(p-ref, f) for p, f, m in states), np.zeros(3))
        np.testing.assert_allclose(total_m, direct_m, atol=4e-14)
        if rotated:
            np.testing.assert_allclose(total_f, rotation @ first[0], atol=4e-14)
            np.testing.assert_allclose(total_m, rotation @ first[1], atol=4e-14)
        else:
            first = total_f, total_m
        other_ref = ref + [.3, -.2, .1]
        other_m = (dm + np.cross(position-other_ref, df)).sum(axis=0)
        np.testing.assert_allclose(other_m, total_m-np.cross(other_ref-ref, total_f), atol=4e-14)


@pytest.mark.parametrize('typ,frozen', [(1, False), (2, False), (2, True)])
def test_disk_inflow_and_jet_use_current_pylon_pose(typ, frozen):
    n = network(typ, jet=True, frozen=frozen)
    x = trial(n)
    r, q, *_, gamma = n.unpack(x)
    with linearization(n, x, 1., capture_circulation=True) as (fields, _):
        data = deepcopy(fields.circulation_aero)
    engine = data['engines'][0]
    row = n.engines[0]; node = n.node(*row[2:4])
    xe = -row[7:10]/np.linalg.norm(row[7:10])
    ye = np.cross([0., 0., 1.], xe); ye /= np.linalg.norm(ye)
    axes = q[node] @ np.column_stack([xe, ye, np.cross(xe, ye)])
    expected_p = r[node]+q[node]@(row[4:7]-n.rj[node])
    np.testing.assert_allclose(engine['position'], expected_p, atol=2e-15)
    np.testing.assert_allclose(engine['axes'], axes, atol=2e-15)
    local_v = axes.T @ data['engine_velocity'][0]
    assert engine['axial_velocity'] == pytest.approx(local_v[0], abs=2e-14)
    assert np.linalg.norm(expected_p-row[4:7]) > .005
    assert np.linalg.norm(axes-np.column_stack([xe, ye, np.cross(xe, ye)])) > .01
    rho, radius, omega, dv = data['rho'], abs(row[12]), row[13], engine['delta_velocity']
    v = local_v[0]
    thrust = rho*np.pi*radius**2*(v+dv/2)*dv
    np.testing.assert_allclose(axes[:, 0] @ engine['force'], -thrust, atol=3e-13)
    assert axes[:, 0] @ engine['moment'] == pytest.approx(40./omega, abs=2e-14)
    viscous = rho/8*np.sqrt(v*v+(omega*radius)**2)*(v*v+3*(omega*radius)**2)*row[14]
    swirl = 1+5*(v/(omega*radius))**2
    assert (v+swirl*dv/2)*thrust+viscous == pytest.approx(40., abs=2e-11)
    assert not engine['power_clipped']
    if typ == 2:
        cl, cla, s0, c0, s1, c1, _, c2, _, _ = row[15:]
        vd, tip = v+dv/2, abs(omega)*radius
        fv = rho*radius**2/4*((cla*s0-cl*c0)*vd+2*cl*s1*tip)
        mv = -rho*radius**3/4*((cla*c1+cl*s1)*vd+2*cl*c2*tip)
        np.testing.assert_allclose((axes.T@engine['force'])[1:], fv*local_v[1:], atol=3e-14)
        np.testing.assert_allclose((axes.T@engine['moment'])[1:], -np.sign(omega)*mv*local_v[1:], atol=3e-14)
        assert np.linalg.norm((axes.T@engine['force'])[1:]) > 1e-4
    with_jet = external(n, r, q, gamma)
    without = network(typ, jet=False, frozen=frozen)
    without_jet = external(without, r, q, gamma)
    # Sign of Rdisk disables only the downstream jet. It cannot change the
    # current engine inflow, disk force or rigid-pylon pose at fixed circulation.
    np.testing.assert_allclose(with_jet[2]['engines'][0]['force'], without_jet[2]['engines'][0]['force'], atol=2e-14)
    np.testing.assert_allclose(with_jet[2]['engines'][0]['moment'], without_jet[2]['engines'][0]['moment'], atol=2e-14)
    assert np.linalg.norm(np.array(with_jet[2]['circulation_residual'])-without_jet[2]['circulation_residual']) > 1e-4
    assert np.linalg.norm(with_jet[5]-without_jet[5]) > 1e-4
    zero_gamma = external(n, r, q, gamma*0.)
    assert abs(with_jet[2]['engines'][0]['thrust']-zero_gamma[2]['engines'][0]['thrust']) > 1e-6


@pytest.mark.parametrize('frozen', [False, True])
def test_powered_circulation_and_geometry_columns_match_full_residual(frozen):
    n = network(2, jet=True, frozen=frozen)
    x = trial(n); factor = .63
    baseline = n.residual(x, factor).copy()
    with linearization(n, x, factor, capture_circulation=True) as (fields, _):
        circulation = circulation_columns(n, fields, factor)
    scales = np.maximum(1., abs(x))
    geometry, report = geometry_columns(
        n, lambda delta: n.residual(x+delta, factor), lambda delta: x+delta,
        scales, factor=factor)
    assert report['geometry_columns'] == 6*n.nn
    for step in (1e-5, 3e-6):
        for j in list(range(6*n.nn))+list(range(n.gamma_start, n.operating_start)):
            h = step*scales[j]; delta = np.zeros(n.size); delta[j] = h
            plus, minus, twice, neg_twice = [n.residual(x+k*delta, factor) for k in (1., -1., 2., -2.)]
            expected = (8*(plus-minus)-(twice-neg_twice))/(12*h)
            actual = (geometry[:, j].toarray().ravel() if j < 6*n.nn
                      else circulation[:, j-n.gamma_start])
            error = np.max(abs(actual-expected)/(1+abs(expected)))
            assert error < 2e-8, (frozen, step, j, error)
    np.testing.assert_array_equal(n.residual(x, factor), baseline)
    detailed, _ = n.residual(x, factor, detail=True)
    np.testing.assert_allclose(detailed, baseline, atol=2e-14, rtol=0)
    assert n.iteration_fields is None and n.tangent_influences is None


@pytest.mark.parametrize('rigid', [False, True])
def test_powered_source_equilibrium_balances_and_restores_same_operator(rigid):
    n = network(rigid=rigid, mass=False)
    result = solve_source_coupled(n.model, n.condition, panels=4, gravity=[0., 0., 0.])
    assert_balanced(result)
    assert len(result['engines']) == 1
    engine = result['engines'][0]
    node = next(row for row in result['nodes'] if row['beam'] == 1 and row['t'] == engine['t'])
    r, q = np.asarray(node['position']), np.asarray(node['rotation'])
    axis = q @ (n.engines[0][7:10]/np.linalg.norm(n.engines[0][7:10]))
    np.testing.assert_allclose(engine['force'], 3.*n.engines[0][10]*axis, atol=3e-13)
    np.testing.assert_allclose(engine['moment'], 3.*n.engines[0][11]*axis, atol=3e-13)
    np.testing.assert_allclose(engine['position'], r+q@(n.engines[0][4:7]-node['jig_position']), atol=3e-13)
    if rigid:
        assert result['max_displacement'] < 1e-9
    else:
        assert 1e-5 < result['max_displacement'] < .1
    saved = result['equilibrium_state']
    x = restore(n, saved)
    assert np.max(abs(n.residual(x))) < 1e-8
    assert capture(n, x, include_launch=False)['identity'] == saved['identity']
    assert saved['identity']['structural_operator'] == COUPLED_POLICY
    assert 'launch' not in saved
    # Supporting an engine must not opt the source operator into dynamics or
    # the unpowered structural-only operator.
    with pytest.raises(AnalysisError, match='dynamic'):
        n.residual(x, circulation_rate=np.zeros(n.ng))
    with pytest.raises(AnalysisError, match='FlightCondition'):
        SourceCoupledNetwork(n.model, 4, None, [0., 0., 0.], [])
    with pytest.raises(AnalysisError, match='airflow|engines'):
        SourceSectionNetwork(n.model, 4, n.condition, [0., 0., 0.], [])
