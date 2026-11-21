"""Loaded Daedalus half-wing/brace dynamics against an independent continuum.

One restored 68-element base and one full A/M pair serve three frequencies and
three physical tip inputs. The nine original all-node [u/56, theta] criteria
remain 1%. This component check excludes live gravity, aero and damping.
"""
import hashlib
import json
from pathlib import Path
import time

import numpy as np
from scipy import sparse

import openswing
from openswing.asw import parse_asw
from openswing.frequency_response import harmonic_solve
from openswing.geometry import surface_frame
from openswing.linear_dynamics import DynamicSystem, linearize, state_layout
from openswing.network import StaticNetwork


DATA = Path(__file__).parent / 'data' / 'daedalus-wing-brace-dynamic'
FREQUENCIES = (.1, 1., 1.15737773741517)
INPUTS = ('tip_Fx', 'tip_Fz', 'tip_My')


def _load_inputs():
    provenance = json.loads((DATA / 'provenance.json').read_text())
    for name, expected in provenance['files'].items():
        content = (DATA / name).read_bytes()
        assert dict(bytes=len(content), sha256=hashlib.sha256(content).hexdigest()) == expected, name
    request = json.loads((DATA / 'request.json').read_text())
    arrays = {}
    for name in ('accepted-base', 'independent-motion'):
        with np.load(DATA / (name + '.npz'), allow_pickle=False) as saved:
            arrays[name] = {key: saved[key].copy() for key in saved.files}
        for value in arrays[name].values():
            assert not value.dtype.hasobject and np.isfinite(value).all()
            value.setflags(write=False)
    base, expected = arrays['accepted-base'], arrays['independent-motion']
    assert base['unknowns'].shape == (828,) and base['unknowns'].dtype == np.dtype('float64')
    assert expected['motion_physical'].shape == (3, 69, 6, 3)
    assert expected['motion_physical'].dtype == np.dtype('complex128')
    np.testing.assert_array_equal(expected['stations'], base['stations'])
    np.testing.assert_array_equal(expected['frequencies_Hz'], FREQUENCIES)
    assert request['frequencies_Hz'] == list(FREQUENCIES) and request['inputs'] == list(INPUTS)
    assert request['elements'] == 68 and request['model_file'] == 'wing-strut.asw'
    assert request['units'] == dict(length='ft', time='s', force='lb', rotation='rad')
    assert request['derivative_step'] == 1e-5 and request['fresh_residual_max'] == 1e-8
    assert request['equilibrium_rank_min'] == 1e-10
    assert request['harmonic'] == dict(reciprocal_condition_min=1e-12,
        scaled_residual_max=1e-7, backward_error_max=1e-9)
    assert request['limits'] == dict(seconds=300, network_residuals=10000,
        external_calls=11000, standalone_external_calls=1000)
    assert request['criterion'] == provenance['criterion'] == dict(cases=9,
        scaled_complex_infinity_relative_limit=.01, motion_length_scale=56.)
    return request, base, expected


def test_loaded_wing_brace_dynamics_matches_independent_continuum(record_property):
    # Ordinary repository imports: no frozen kernel, external stage or /tmp input.
    repository = Path(__file__).resolve().parents[1]
    assert Path(openswing.__file__).resolve().parent == repository / 'openswing'
    request, base, expected = _load_inputs()
    counts = dict(network_constructions=0, network_residuals=0, equilibrium_calls=0,
        full_linearizations=0, harmonic_three_rhs_calls=0,
        external_calls=0, residual_external_calls=0, standalone_external_calls=0)
    started = time.monotonic()

    def budget(*_):
        assert time.monotonic() - started < 300, '300-second case cap reached'

    class CountedNetwork(StaticNetwork):
        """Count the accepted full native path without changing its equations."""
        _residual_depth = 0

        def residual(self, *args, **kwargs):
            budget()
            assert counts['network_residuals'] < 10000, 'pre-call residual cap reached'
            counts['network_residuals'] += 1
            self._residual_depth += 1
            try:
                return super().residual(*args, **kwargs)
            finally:
                self._residual_depth -= 1

        def external(self, *args, **kwargs):
            budget()
            assert counts['external_calls'] < 11000, 'pre-call external-load cap reached'
            key = 'residual_external_calls' if self._residual_depth else 'standalone_external_calls'
            if not self._residual_depth:
                assert counts[key] < 1000, 'pre-call standalone-load cap reached'
            counts['external_calls'] += 1
            counts[key] += 1
            return super().external(*args, **kwargs)

    model = parse_asw((DATA / request['model_file']).read_text())
    assert model.units.declarations == {'L': (1., 'ft'), 'T': (1., 's'), 'F': (1., 'lb')}
    np.testing.assert_array_equal(model.constants, [32.18, .002378, 1115.])
    counts['network_constructions'] += 1
    network = CountedNetwork(model, request['mesh'], None, [0., 0., 0.],
                             request['frozen_dead_loads'], strut_mode='bilateral')
    assert (network.nn, network.ne, network.ng, network.size) == (69, 68, 0, 828)
    stations = network.station_nodes[1][0]
    np.testing.assert_array_equal(stations, request['mesh']['beams']['1']['nodes'])
    np.testing.assert_array_equal(stations, base['stations'])
    assert np.all(np.diff(stations) > 0)
    assert network.condition is None and network.operating.count == 0
    assert not network.engines and not network.hinges and not network.weights
    assert len(model.beams) == 1 and not model.beams[0].lifting
    assert len(network.struts) == 1 and not network.tension_only
    assert network.gravity_override and not np.any(network.gravity)
    assert len(network.constraints) == 1
    clamp = network.constraints[0]
    assert clamp['kind'] == 'ground' and clamp['type'] == 0
    assert clamp['a'] == network.node(1, 0.) and clamp['b'] is None
    assert not np.any(network.offa) and not np.any(network.offb)
    row = network.struts[0]
    np.testing.assert_array_equal(row, request['brace']['gauge_row'])
    assert float(np.linalg.norm(row[5:8] - row[2:5])) + float(row[8]) == request['brace']['rest_length']
    Rj = surface_frame(model.beams[0], stations)
    assert np.max(abs(Rj - request['brace']['jig_material_rotation'])) <= 1e-14
    assert counts['network_residuals'] == network.nfev == 0

    scales = request['scales']
    assert network.L == scales['L'] == 56. and network.F == scales['F']
    x = base['unknowns'].copy()
    r, Q, *_ = network.unpack(x)
    cut = request['gauge']['cut']
    Qcut = np.array(cut['rotation'])
    physical_r = np.array(cut['position']) + np.einsum('ij,nj->ni', Qcut, r - cut['jig_position'])
    physical_Q = np.einsum('ij,njk->nik', Qcut, Q)
    physical_R = np.einsum('nij,njk->nik', physical_Q, Rj)
    # Exact saved geometry is checked before the first physical residual.
    for actual, name in ((r, 'positions_gauge'), (Q, 'rotations_gauge'),
                         (physical_r, 'positions_physical'), (physical_R, 'material_rotations_physical')):
        np.testing.assert_array_equal(actual, base[name], err_msg=name)
    assert counts['network_residuals'] == network.nfev == 0
    accepted_rank = request['accepted_equilibrium_diagnostics']
    rank = accepted_rank.get('column_scaled_reciprocal_condition')
    if rank is None:
        rank = accepted_rank.get('column_scaled_reciprocal_condition_lower_bound')
    assert rank is not None and np.isfinite(rank) and rank >= 1e-10
    fresh = network.residual(x)
    assert np.isfinite(fresh).all() and np.max(abs(fresh)) <= 1e-8

    system = DynamicSystem(network, x, 'fixed')
    assert state_layout(system) == request['layout']
    assert system.size == scales['descriptor_size'] == 1242
    assert system.V == scales['V'] and system.W == scales['W'] and system.L == 56.
    zero = np.zeros(system.size)
    state, _, options = system.physical_state(zero, zero)
    assert all(not np.any(v) for v in (state.u, state.w, system.U0, system.Omega0,
        system.Udot0, system.Omegadot0, system.angle_dot0))
    assert all(not np.any(v) for v in options['elastic_motion'])
    assert network.quiescent_density is None and not np.any(network.damping_times)
    full_fresh = system.residual(zero, zero)
    assert np.isfinite(full_fresh).all() and np.max(abs(full_fresh)) <= 1e-8
    assert not np.any(full_fresh[network.size:])

    counts['full_linearizations'] += 1
    before_mass = counts['standalone_external_calls']
    A, M = linearize(system, step=1e-5, sparse=True, progress=budget)
    assert sparse.issparse(A) and sparse.issparse(M)
    assert A.shape == M.shape == (1242, 1242)
    assert np.isfinite(A.data).all() and np.isfinite(M.data).all()
    assert counts['standalone_external_calls'] - before_mass == system.derivative_diagnostics['load_evaluations']
    # Positive physical forces/couple enter the native residual. With A=R_z
    # and M=-R_zdot, the source harmonic solver uses (i*omega*M-A) Z = B.
    B = np.zeros((system.size, 3))
    tip = network.node(1, 56.)
    force = 6 * network.ne + 3 * tip
    moment = 6 * network.ne + 3 * network.nn + 3 * tip
    B[force:force + 3, 0] = Qcut.T @ np.array([1., 0., 0.]) / network.F
    B[force:force + 3, 1] = Qcut.T @ np.array([0., 0., 1.]) / network.F
    B[moment:moment + 3, 2] = Qcut.T @ np.array([0., 1., 0.]) / (network.F * network.L)
    assert not np.any(B[network.size:]) and np.isfinite(B).all()

    criteria, harmonic_records, kinematics = [], [], []
    for index, frequency in enumerate(FREQUENCIES):
        budget()
        omega = 2 * np.pi * frequency
        counts['harmonic_three_rhs_calls'] += 1
        Z, diagnostics = harmonic_solve(A, M, B, omega)
        assert Z.shape == (1242, 3) and np.isfinite(Z).all()
        assert diagnostics['reciprocal_condition'] >= 1e-12
        assert max(diagnostics['scaled_residuals']) <= 1e-7
        assert max(diagnostics['backward_errors']) <= 1e-9
        assert diagnostics['factor_dimension'] == 1242
        assert diagnostics['beam_equations_eliminated'] == 0
        harmonic_records.append(dict(frequency_Hz=frequency, **diagnostics))
        q = Z[:6 * network.nn].reshape(network.nn, 6, 3)
        u = np.einsum('ij,njk->nik', Qcut, system.L * q[:, :3])
        theta = np.einsum('ij,njk->nik', Qcut, q[:, 3:])
        velocity = system.V * Z[system.velocity_start:system.velocity_start + 3 * network.nn].reshape(69, 3, 3)
        rates = system.W * Z[system.velocity_start + 3 * network.nn:system.frame_start].reshape(69, 3, 3)
        velocity = np.einsum('ij,njk->nik', Qcut, velocity)
        rates = np.einsum('ij,njk->nik', Qcut, rates)
        assert all(np.isfinite(v).all() for v in (u, theta, velocity, rates))
        # Descriptive kinematic defects; the original full-equation gates above
        # already include every kinematic row. No extra agreement gate is added.
        kinematics.append(dict(frequency_Hz=frequency,
            velocity_defect_max=float(np.max(abs(velocity - 1j * omega * u))),
            rate_defect_max=float(np.max(abs(rates - 1j * omega * theta)))))
        actual = np.concatenate((u / 56., theta), axis=1)
        reference = expected['motion_physical'][index].copy()
        reference[:, :3] /= 56.
        for column, name in enumerate(INPUTS):
            error = float(np.max(abs(actual[:, :, column] - reference[:, :, column])))
            norm = float(np.max(abs(reference[:, :, column])))
            assert np.isfinite(norm) and norm > 0, 'nonzero independent full-motion reference'
            ratio = error / norm
            criteria.append(dict(frequency_Hz=frequency, input=name,
                absolute_scaled_complex_error=error, reference_infinity_norm=norm,
                relative_error=ratio, passed=ratio <= .01))

    assert len(criteria) == 9
    assert counts['network_constructions'] == counts['full_linearizations'] == 1
    assert counts['harmonic_three_rhs_calls'] == 3 and counts['equilibrium_calls'] == 0
    assert counts['network_residuals'] == network.nfev <= 10000
    assert counts['external_calls'] == counts['residual_external_calls'] + counts['standalone_external_calls']
    assert all(getattr(network, key, None) is None for key in
               ('tangent_influences', 'iteration_fields', '_tangent_loads'))
    budget()
    record_property('operations', json.dumps(counts, sort_keys=True))
    record_property('harmonic_diagnostics', json.dumps(harmonic_records))
    record_property('response_criteria', json.dumps(criteria))
    record_property('kinematics', json.dumps(kinematics))
    record_property('fresh_residual_max', float(np.max(abs(fresh))))
    record_property('fresh_descriptor_residual_max', float(np.max(abs(full_fresh))))
    record_property('elapsed_seconds', time.monotonic() - started)
    assert all(item['passed'] for item in criteria), criteria
