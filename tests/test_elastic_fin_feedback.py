"""Loaded distributed-elastic boom/fin feedback at one hertz.

One fine68-element/38-circulation case exercises native F3 and a physical
upper-tip Mz input. Expected arrays are the accepted independent continuum /
aerodynamic response, not a stored native solution. The 26 original grouped
complex criteria remain1%; this is not full-aircraft or experimental validation.
"""
import hashlib
import json
from pathlib import Path
import time

import numpy as np
from scipy import sparse

import elastic_fin_adapter as adapter
from openswing.frozen_influence import lifting_geometry


DATA = Path(__file__).parent/'data'/'elastic-fin'
FAMILIES = ('total', 'rate', 'apparent', 'remainder')
INPUTS = ('control.3', 'upper_tip_physical_Mz')
GEOMETRY = ('r0', 'r1', 'rm', 'frame0', 'frame1', 'frames', 'ds',
            'wind', 'a', 'b', 'hv', 'cp')


def _identity(actual, expected, name):
    actual, expected = np.asarray(actual), np.asarray(expected)
    assert actual.shape == expected.shape, name
    assert np.isfinite(actual).all() and np.isfinite(expected).all(), name
    np.testing.assert_allclose(actual, expected, atol=2e-11, rtol=2e-11,
                               err_msg=name)


def _load_data():
    provenance = json.loads((DATA/'provenance.json').read_text())
    for name, expected in provenance['files'].items():
        content = (DATA/name).read_bytes()
        assert dict(bytes=len(content), sha256=hashlib.sha256(content).hexdigest()) == expected, name
    request = json.loads((DATA/'request.json').read_text())
    assert request['fixture_file'] == 'fixture.json'
    fixture = json.loads((DATA/'fixture.json').read_text())
    arrays = {}
    for name in ('seed-geometry', 'expected'):
        with np.load(DATA/(name+'.npz'), allow_pickle=False) as saved:
            arrays[name] = {key: saved[key].copy() for key in saved.files}
        for value in arrays[name].values():
            assert not value.dtype.hasobject and np.isfinite(value).all()
            value.setflags(write=False)
    assert provenance['criterion'] == dict(groups=13, inputs_per_group=2,
        relative_scaled_complex_infinity_limit=.01,
        exact_zero_reference_scaled_absolute_limit=1e-10,
        motion_length_scale=20., wrench_moment_scale=20.)
    return request, fixture, arrays['seed-geometry'], arrays['expected'], provenance


def _seed_geometry(network, seed, independent, reference, counts):
    """The original geometry gate, before the first native residual."""
    assert network.nfev == counts['network_residuals'] == 0
    r, Q, *_ = network.unpack(seed)
    meshes = network.deformed_meshes(r, Q, network.geometry(r, Q))
    lifting = [mesh for mesh in meshes if mesh.beam.lifting]
    assert len(lifting) == 1 and lifting[0].beam.index == 3
    mesh = lifting[0]
    assert np.all(np.diff(mesh.tm) > 0) and np.all(mesh.t1 > mesh.t0)
    np.testing.assert_array_equal(mesh.t1[:-1], mesh.t0[1:])
    _identity(mesh.tm, independent['gamma_tm'], 'independent material receiver ordering')
    wind = network.condition.vectors()[0]
    virtual = lifting_geometry(meshes, wind)
    native = {name: getattr(mesh, name) for name in
              ('r0', 'r1', 'rm', 'frame0', 'frame1', 'frames')}
    native.update(ds=mesh.length, wind=wind,
                  **{name: virtual[name] for name in ('a', 'b', 'hv', 'cp')})
    metrics = {}
    for name in GEOMETRY:
        assert reference[name].dtype == np.dtype('float64')
        _identity(native[name], reference[name], 'independent seed '+name)
        metrics[name] = float(np.max(abs(native[name]-reference[name]) /
                                    (2e-11+2e-11*abs(reference[name]))))
    np.testing.assert_array_equal(independent['gamma'], reference['gamma'])
    assert network.nfev == counts['network_residuals'] == 0
    return metrics


def _packet_arrays(aero, tm):
    """Original saved-comparison reduction of complete physical strip arrays."""
    strips = [strip for strip in aero['strips'] if strip.get('lifting')]
    assert strips and all(strip['beam'] == 3 for strip in strips)
    _identity([strip['t'] for strip in strips], tm, 'output receiver ordering')

    def vector(key):
        value = np.asarray([strip[key] for strip in strips], dtype=float)
        assert value.shape == (len(tm), 3) and np.isfinite(value).all(), key
        return value

    position = vector('position')
    # Literal Xax=.25: the rate force acts at the axis and has no intrinsic
    # couple. Its moment about the gauge origin is still retained below.
    np.testing.assert_array_equal(vector('velocity_position'), position)
    total = np.concatenate((vector('force'), vector('moment')), axis=1)
    rate = np.concatenate((vector('circulation_rate_force'), np.zeros_like(position)), axis=1)
    apparent = np.concatenate((vector('apparent_force'), vector('apparent_moment')), axis=1)
    strip = np.stack((total, rate, apparent, total-rate-apparent))
    net_total = np.r_[aero['force'], aero['moment']]
    net_rate = np.r_[aero['circulation_rate_force'], aero['circulation_rate_moment']]
    net_apparent = np.r_[aero['apparent_force'], aero['apparent_moment']]
    net = np.stack((net_total, net_rate, net_apparent, net_total-net_rate-net_apparent))
    _identity(np.cross(position, rate[:, :3]).sum(axis=0), net_rate[3:],
              'rate moment about gauge origin')
    return dict(strip=strip, net=net, velocity=vector('relative_velocity'))


def _snapshot(system, z, zdot, forcing, tm, counts, budget):
    """One original snapshot, intercepting its existing detailed residual."""
    budget()
    network = system.network
    original = network.residual
    had_override = 'residual' in network.__dict__
    prior = network.__dict__.get('residual')
    raw = []

    def observe(*args, **kwargs):
        value = original(*args, **kwargs)
        assert isinstance(value, tuple) and len(value) == 2
        raw.append(value)
        return value

    network.residual = observe
    before = network.nfev
    try:
        counts['output_snapshots'] += 1
        assert counts['output_snapshots'] <= 9
        system.snapshot(z, zdot, forcing=forcing)
    finally:
        if had_override:
            network.residual = prior
        else:
            network.__dict__.pop('residual', None)
    assert len(raw) == 1 and network.nfev-before == 1
    return _packet_arrays(raw[0][1]['aero'], tm)


def _outputs(system, Z, control_forcing, input_diagnostics, request, counts, budget):
    tm = np.asarray(request['independent']['gamma_tm'])
    zero = np.zeros(system.size)
    _snapshot(system, zero, zero, None, tm, counts, budget)
    response = {key: [] for key in ('net', 'strip', 'velocity')}
    steps = []
    for column in range(2):
        vector = Z[:, column]
        rate = 2j*np.pi*vector
        width = request['output_step']
        if column == 0:
            h = min(width*input_diagnostics['input']['scale'],
                    width/max(float(np.max(abs(vector))), 1e-30))
        else:
            norm = max(float(np.max(abs(vector))),
                       min(float(np.max(abs(rate)))/system.W, 1.))
            h = width/(norm if norm else 1.)
        assert np.isfinite(h) and h > 0
        steps.append(h)
        values = []
        for component, part in enumerate((np.real, np.imag)):
            for sign in (1, -1):
                forcing = control_forcing(component, sign*h) if column == 0 else None
                values.append(_snapshot(system, sign*h*part(vector), sign*h*part(rate),
                                        forcing, tm, counts, budget))
        for name in response:
            response[name].append((values[0][name]-values[1][name]
                                  +1j*(values[2][name]-values[3][name]))/(2*h))
    assert counts['output_snapshots'] == 9
    return {name: np.stack(value, axis=-1) for name, value in response.items()}, steps


def test_loaded_elastic_fin_matches_independent_feedback(record_property):
    request, fixture, geometry, expected, provenance = _load_data()
    assert request['subdivisions'] == 2 and request['frequencies'] == [1.]
    assert request['equilibrium_tolerance'] == 1e-9
    assert request['derivative_step'] == 1e-5 and request['output_step'] == 2.5e-6
    assert request['maximum_seconds'] == 300 and request['maximum_residual_calls'] == 10000
    assert request['flight'] == dict(speed=6.7/.3048, density=.002378, mach=.1,
        physical_wind=[1., 0., 0.], aero_lag=True, stall=False, wake_core_ratio=0.)
    counts = dict(network_constructions=0, network_residuals=0, base_corrections=0,
                  linearizations=0, input_partials=0, harmonic_calls=0, output_snapshots=0)
    start = time.monotonic()

    def budget(*_):
        assert time.monotonic()-start < 300, '300-second case budget exhausted'

    def before_residual():
        budget()
        assert counts['network_residuals'] < 10000, 'residual cap reached before next call'
        counts['network_residuals'] += 1

    counts['network_constructions'] += 1
    network, _ = adapter.build_network(fixture, 2, request['independent_counterloads'],
                                      request['flight'], residual_observer=before_residual)
    assert (network.nn, network.ne, network.ng) == (70, 68, 38)
    np.testing.assert_array_equal(network.model.constants, [32.18, .002378, 1115.])
    seed, packet, mapping = adapter.seed_packet(network, request['independent'])
    assert mapping['independently_calculated_coordinates_retained']
    assert mapping['maximum_tolerance_ratio'] <= 1
    geometry_metrics = _seed_geometry(network, seed, request['independent'], geometry, counts)
    # Same descriptive seed evaluation as the accepted case; no load tuning.
    seed_residual = network.residual(seed)
    assert np.isfinite(seed_residual).all()
    counts['base_corrections'] += 1
    system, _, _ = adapter.correct_base(network, packet, tolerance=1e-9, progress=budget)
    assert system.size == 1298
    zero = np.zeros(system.size)
    fresh = system.residual(zero, zero)
    assert np.isfinite(fresh).all() and np.max(abs(fresh)) <= 1e-8
    equilibrium = network.equilibrium_diagnostics
    rank = equilibrium.get('column_scaled_reciprocal_condition')
    if rank is None:
        rank = equilibrium.get('column_scaled_reciprocal_condition_lower_bound')
    assert rank is not None and np.isfinite(rank) and rank > 1e-10
    counts['linearizations'] += 1
    A, M, _ = adapter.assemble(system, fixture, step=1e-5, progress=budget, output_fields=False)
    assert sparse.issparse(A) and sparse.issparse(M)
    assert A.shape == M.shape == (1298, 1298)
    assert np.isfinite(A.data).all() and np.isfinite(M.data).all()
    counts['input_partials'] += 1
    B, input_diagnostics, input_packets, forcing = adapter.input_rhs(system, fixture, step=1e-5)
    assert B.shape == (1298, 2) and np.isfinite(B).all()
    assert len(input_packets) == input_diagnostics['residual_calls'] == 5
    assert input_diagnostics['columns'] == list(INPUTS)
    assert np.any(B[:, 0] != 0) and np.any(B[:, 1] != 0)
    counts['harmonic_calls'] += 1
    Z, harmonic = adapter.harmonic(A, M, B, 1.)
    assert Z.shape == (1298, 2) and np.isfinite(Z).all()
    assert harmonic['reciprocal_condition'] >= 1e-12
    assert max(harmonic['scaled_residuals']) <= 1e-7
    assert max(harmonic['backward_errors']) <= 1e-9
    assert harmonic['factor_dimension'] == 1298 and harmonic['beam_equations_eliminated'] == 0
    np.testing.assert_array_equal(network.model.reference[1], [0., 0., 0.])
    response, steps = _outputs(system, Z, forcing, input_diagnostics, request, counts, budget)
    ids = [network.node(row['beam'], row['t']) for row in request['independent']['nodes']]
    assert sorted(ids) == list(range(network.nn))
    reactions = adapter.reaction_response(system, fixture, Z)
    assert len(reactions) == 2 and {row['kind'] for row in reactions} == {'ground', 'joint'}
    reactions = {row['kind']: row for row in reactions}
    groups = dict(all_node_motion=adapter.nodal_response(system, fixture, Z)[ids],
        circulation=network.gamma_scale*Z[network.gamma_start:network.operating_start],
        clamp_reaction=np.concatenate((reactions['ground']['force'], reactions['ground']['moment'])),
        fin_joint_reaction=np.concatenate((reactions['joint']['other_force'], reactions['joint']['other_moment'])),
        HV_relative_velocity=response['velocity'])
    for i, name in enumerate(FAMILIES):
        groups['net_aero_'+name] = response['net'][i]
        groups['strip_aero_'+name] = response['strip'][i]
    assert set(groups) == {group['name'] for group in provenance['groups']}
    metrics = []
    for group in provenance['groups']:
        name = group['name']
        actual, reference, scale = groups[name], expected[name+'__reference'], expected[name+'__scale']
        assert list(actual.shape) == group['shape'] and actual.shape == reference.shape
        assert np.isfinite(actual).all() and np.all(scale > 0)
        assert scale.shape == actual.shape[:-1]
        delta = actual/scale[..., None]-reference/scale[..., None]
        scaled_reference = reference/scale[..., None]
        for column, input_name in enumerate(INPUTS):
            error = float(np.max(abs(delta[..., column])))
            norm = float(np.max(abs(scaled_reference[..., column])))
            ratio = None if norm == 0 else error/norm
            passed = error <= 1e-10 if norm == 0 else ratio <= .01
            metrics.append(dict(group=name, input=input_name, complex_scaled_infinity_error=error,
                                reference_infinity_norm=norm, relative_error=ratio, passed=passed))
    assert counts['network_residuals'] == network.nfev <= 10000
    assert all(counts[key] == 1 for key in ('network_constructions', 'base_corrections',
                                           'linearizations', 'input_partials', 'harmonic_calls'))
    assert counts['output_snapshots'] == 9 and len(metrics) == 26
    assert all(getattr(network, key, None) is None for key in
               ('tangent_influences', 'iteration_fields', '_tangent_loads'))
    budget()
    record_property('operations', json.dumps(counts, sort_keys=True))
    record_property('geometry_gate_fractions', json.dumps(geometry_metrics, sort_keys=True))
    record_property('native_output_steps', json.dumps(steps))
    record_property('response_criteria', json.dumps(metrics))
    record_property('fresh_residual_max', float(np.max(abs(fresh))))
    record_property('elapsed_seconds', time.monotonic()-start)
    assert all(item['passed'] for item in metrics), metrics
