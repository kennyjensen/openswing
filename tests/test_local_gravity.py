"""Local elastic gravity as the gradient of an independent scalar potential.

The five-node, four-element fixture has finite deformation, a rigid shoulder,
two distributed CG offsets, a point-mass pylon, and separate reference points.
V = sum(m*g*Z) uses original material lengths and full material rotation arcs.
Native spatial moments are pulled back to the local SO(3) and Euler coordinate
covectors before comparing -grad(V) and -Hessian(V)*direction.

This prescribed state is not an equilibrium. Fixed 8/16/32-point quadrature,
seven directions, and widths 1e-4/5e-5 reproduce the component validation;
there is no aircraft trim, linearization, or frequency-response calculation.
"""
import json
from pathlib import Path

import numpy as np

import local_gravity_reference as reference


DATA = Path(__file__).parent/'data'/'local-gravity'
COARSE_WIDTH = 1e-4
ATOL = RTOL = 2e-8


def test_gravity_potential_ad_elementary_derivatives(record_property):
    errors = reference.self_checks()
    assert max(errors.values()) <= 1e-12
    for name, value in errors.items():
        record_property(name, value)


def test_local_gravity_potential_and_mixed_tangent(monkeypatch, record_property):
    # Verify the standalone differentiation primitive before native evaluation.
    assert max(reference.self_checks().values()) <= 1e-12
    fixture = json.loads((DATA/'fixture.json').read_text())
    q0 = np.asarray(fixture['base_coordinates'])
    directions = np.asarray(fixture['directions'])
    assert q0.shape == (36,) and directions.shape == (7, 36)
    metrics = []

    def compare(name, actual, expected, atol=ATOL, rtol=RTOL):
        actual, expected = np.asarray(actual), np.asarray(expected)
        assert actual.shape == expected.shape, name
        assert np.isfinite(actual).all() and np.isfinite(expected).all(), name
        difference = abs(actual-expected)
        metrics.append((name, float(np.max(difference)),
                        float(np.max(difference/(atol+rtol*abs(expected))))))
        np.testing.assert_allclose(actual, expected, atol=atol, rtol=rtol,
                                   err_msg=name)

    quadratures, oracles = {}, {}
    for degree in (8, 16, 32):
        x, w = np.polynomial.legendre.leggauss(degree)
        quadratures[degree] = ((x+1)/2, w/2)
        oracles[degree] = reference.potential(
            q0, fixture, quadratures[degree], second=True)
    oracle_calls = 3
    for coarse, fine in ((8, 16), (16, 32)):
        for key in ('value', 'gradient', 'hessian'):
            compare(f'quadrature {coarse} to {fine} {key}',
                    np.atleast_1d(oracles[coarse][key]),
                    np.atleast_1d(oracles[fine][key]))
    hessian = oracles[32]['hessian']
    compare('potential Hessian symmetry', hessian, hessian.T, 1e-12, 1e-12)
    assert abs(sum(oracles[32]['masses'])-8.5) <= 1e-13

    from openswing.asw import parse_asw
    import openswing.network as network_module
    import openswing.linear_dynamics as dynamics_module
    from openswing.operating import free_flight_constraints

    def forbidden(*args, **kwargs):
        raise AssertionError('This gravity regression must not assemble or trim.')

    monkeypatch.setattr(network_module, 'equilibrate', forbidden)
    monkeypatch.setattr(network_module, 'solve_static', forbidden)
    monkeypatch.setattr(dynamics_module, 'make_system', forbidden)
    monkeypatch.setattr(dynamics_module, 'linearize', forbidden)
    model = parse_asw((DATA/'fixture.asw').read_text())
    network = network_module.StaticNetwork(
        model, fixture['panels'], None, None, [],
        operating_constraints=free_flight_constraints())
    monkeypatch.setattr(network, 'jacobian', forbidden)
    assert (network.nn, network.ne, network.nc, network.ng,
            network.operating.count, network.size) == (5, 4, 6, 0, 6, 66)
    compare('jig nodes', network.rj, fixture['jig_nodes'], 2e-12, 2e-12)
    for key, actual in (('material_length', network.ds),
                        ('offset_a', network.offa), ('offset_b', network.offb)):
        compare(key, actual, [e[key] for e in fixture['elements']], 2e-12, 2e-12)
    for side in ('a', 'b'):
        expected = [reference.jig_frame(e['twist_'+side+'_deg'])
                    for e in fixture['elements']]
        compare('material jig frame '+side, getattr(network, 'R0'+side),
                expected, 2e-12, 2e-12)
    assert network.nfev == 0 and network.gravity_override is False

    base = np.zeros(network.size)
    base_pose = base[:6*network.nn].reshape(network.nn, 6)
    base_pose[:, :3] = (np.asarray(fixture['deformed_nodes'])-network.rj)/network.L
    base_pose[:, 3:] = fixture['base_rotation_vectors']
    system = dynamics_module.DynamicSystem(
        network, base, frame='free', position=q0[:3],
        attitude=np.rad2deg(q0[3:6]), velocity=[0, 0, 0])
    assert system.size == 108 and network.nfev == 0
    force_start = 6*network.ne
    moment_start = force_start+3*network.nn
    nodal_stop = 6*(network.ne+network.nn)
    global_start = network.operating_start
    other = np.ones(system.size, dtype=bool)
    other[force_start:nodal_stop] = False
    other[global_start:network.size] = False

    def gravity_off(state, options):
        return {**options, 'gravity_override': np.zeros(3)}

    def produce(q, oracle):
        z = np.zeros(system.size)
        local = z[:6*network.nn].reshape(network.nn, 6)
        local[:, :3] = q[6:21].reshape(5, 3)/network.L
        local[:, 3:] = q[21:36].reshape(5, 3)
        frame = system.frame_start
        z[frame+6:frame+9] = (q[:3]-q0[:3])/network.L
        z[frame+9:frame+12] = q[3:6]-q0[3:6]
        before = network.nfev
        on = system.residual(z, np.zeros(system.size))
        off = system.residual(z, np.zeros(system.size), forcing=gravity_off)
        assert network.nfev-before == 2
        delta = on-off
        force = delta[force_start:moment_start].reshape(5, 3)*network.F
        moment = delta[moment_start:nodal_stop].reshape(5, 3)*network.F*network.L
        global_force = delta[global_start:global_start+3]*network.F
        global_moment = delta[global_start+3:global_start+6]*network.F*network.L
        covector = reference.generalized_load(
            q, force, moment, global_force, global_moment, fixture)
        compare('gravitational covector', covector, -oracle['gradient'])
        compare('unchanged other residual rows', delta[other],
                np.zeros(np.sum(other)))

        # Independent physical centroids also predict the global resultants.
        earth_rotation = np.asarray(reference.earth_rotation(q[3:6]), dtype=float)
        gravity_body = earth_rotation.T@np.array([0., 0., -fixture['gravity']])
        compare('global force', global_force, sum(oracle['masses'])*gravity_body)
        first_moment = np.sum(oracle['masses'][:, None]*(
            oracle['centroids']-fixture['moment_reference']), axis=0)
        compare('global moment', global_moment, np.cross(first_moment, gravity_body))
        nodes = np.asarray(fixture['deformed_nodes'])+q[6:21].reshape(5, 3)
        compare('reference covariance',
                global_moment+np.cross(fixture['moment_reference'], global_force),
                np.sum(moment+np.cross(nodes, force), axis=0))
        return covector, global_force

    produce(q0, oracles[32])
    tangents = []
    for index, direction in enumerate(directions):
        values, forces = [], []
        for factor in (1., -1., .5, -.5):
            q = q0+COARSE_WIDTH*factor*direction
            oracle = reference.potential(q, fixture, quadratures[32], second=False)
            oracle_calls += 1
            value, force = produce(q, oracle)
            values.append(value)
            forces.append(force)
        expected = -hessian@direction
        coarse = (values[0]-values[1])/(2*COARSE_WIDTH)
        fine = (values[2]-values[3])/COARSE_WIDTH
        compare('Hessian coarse '+str(index), coarse, expected)
        compare('Hessian fine '+str(index), fine, expected)
        compare('two-width consistency '+str(index), coarse, fine)
        if index == 2:
            compare('heading derivative zero', fine, np.zeros(reference.DIM))
        if index in (3, 4, 5):
            compare('global shape-force derivative zero',
                    (forces[2]-forces[3])/COARSE_WIDTH, np.zeros(3))
        tangents.append(fine)

    mixed = []
    for frame in (0, 1):
        for shape in (3, 4, 5):
            first = sum(float(directions[frame, k])*float(tangents[shape][k])
                        for k in range(reference.DIM))
            transpose = sum(float(directions[shape, k])*float(tangents[frame][k])
                            for k in range(reference.DIM))
            compare('mixed frame/shape reciprocity', [first], [transpose])
            mixed.append(first)
    assert max(abs(value) for value in mixed) > 1e-4
    assert network.nfev == 58 and oracle_calls == 31
    for label, prefix in (('covector', 'gravitational covector'),
                          ('tangent', 'Hessian'), ('quadrature', 'quadrature'),
                          ('mixed_reciprocity', 'mixed frame/shape')):
        selected = [row for row in metrics if row[0].startswith(prefix)]
        record_property(label+'_maximum_absolute_error', max(row[1] for row in selected))
        record_property(label+'_maximum_gate_fraction', max(row[2] for row in selected))
    record_property('physical_array_comparisons', len(metrics))
    record_property('production_residual_calls', network.nfev)
    record_property('independent_potential_calls', oracle_calls)
    record_property('Hessian_direction_products', len(directions))
