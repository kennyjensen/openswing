"""Actual corrected C16 compatibility versus independently derived saved data.

The oracle retains loaded N0/M0 transport and full material SO(3) interpolation.
This tests the current compatibility map only: no trim, aero residual, full
linearization, harmonic solve or historical ASWING parity is implied.
"""
import hashlib
import json
from pathlib import Path

import numpy as np
from scipy.sparse import csr_matrix, hstack, load_npz

from openswing.asw import parse_asw
from openswing.equilibrium_state import restore, warm_start_recipe
from openswing.linear_dynamics import DynamicSystem, state_layout
from openswing.network import StaticNetwork
from openswing.operating import time_load_constraints
from openswing.structural_outputs import compatibility_columns
from openswing.time_state import read_condition


DATA = Path(__file__).parent / 'data' / 'daedalus-curved-mechanics'


def test_loaded_c16_compatibility_matches_independent_matrix_and_objectivity(record_property):
    root = Path(__file__).resolve().parents[1]
    provenance = json.loads((DATA / 'provenance.json').read_text())
    for name, expected in provenance['files'].items():
        content = (DATA / name).read_bytes()
        assert dict(bytes=len(content), sha256=hashlib.sha256(content).hexdigest()) == expected, name
    request = json.loads((DATA / 'request.json').read_text())
    project = json.loads((root / request['project']).read_text())
    config = project['cases'][request['case_index']]['configuration']
    packet = config['equilibrium']['state']
    launch = packet['launch']

    class NoResidualNetwork(StaticNetwork):
        def residual(self, *args, **kwargs):
            raise AssertionError('This compatibility regression must not evaluate an aircraft residual')

    model = parse_asw(config['source'])
    network = NoResidualNetwork(model, launch['panels'], read_condition(launch['condition']),
        launch['gravity'], launch['loads'], operating_constraints=time_load_constraints('free'),
        strut_mode=launch['strut_mode'], mesh_recipe=warm_start_recipe(model, launch['panels'], packet))
    assert network.mesh_recipe == 'physical-breaks-v1'
    assert len(launch['released_constraints']) == 7 and network.operating.count == 6
    base = restore(network, packet)
    system = DynamicSystem(network, base, 'free')
    assert [network.nn, network.ne, network.ng, network.nc, network.size, system.size] == request['dimensions']
    assert state_layout(system) == request['layout']
    assert dict(L=network.L, F=network.F, V=system.V, W=system.W,
                Gamma_scale=network.gamma_scale) == request['scales']
    assert np.all(network.damping_times == 0)
    assert network.nfev == 0

    with np.load(DATA / 'independent-directions.npz', allow_pickle=False) as data:
        expected_base = data['base'].copy()
        directions = data['directions'].copy()
        expected_action = data['expected_action'].copy()
        moment_transport = data['loaded_moment_action'].copy()
    assert directions.shape == (2044, 10) and expected_action.shape == (618, 10)
    assert all(np.isfinite(v).all() for v in (expected_base, directions, expected_action, moment_transport))
    np.testing.assert_allclose(base, expected_base, atol=2e-13, rtol=2e-13)
    # Nonzero M0 transport makes this fixture exercise a term absent from the
    # straight tensile free-carrier benchmark. Stored directions use spatial
    # left increments, and rigid rotations also rotate loaded resultants.
    assert np.max(abs(moment_transport[:, :4])) > .007
    assert np.max(abs(base[6 * network.nn:6 * (network.nn + network.ne)].reshape(-1, 6)[:, 3:])) > 0

    expected = load_npz(DATA / 'independent-compatibility.npz').tocsr()
    assert expected.shape == (618, 2044) and expected[:, network.size:].nnz == 0
    current = compatibility_columns(system).tocsr()
    assert current.shape == (618, network.size)
    # Material damping was guarded zero; all local-rate and frame columns in
    # this compatibility block are consequently zero.
    current = hstack([current, csr_matrix((618, system.size - network.size))], format='csr')
    got, want = current.toarray(), expected.toarray()
    np.testing.assert_allclose(got, want, atol=2e-10, rtol=2e-10)
    action = current @ directions
    np.testing.assert_allclose(action, expected_action, atol=2e-10, rtol=2e-10)
    np.testing.assert_allclose(action[:, 4:], 0., atol=2e-10, rtol=0.)
    assert network.nfev == 0
    record_property('compatibility_maximum_absolute_difference', float(np.max(abs(got - want))))
    record_property('direction_maximum_absolute_difference', float(np.max(abs(action - expected_action))))
    record_property('rigid_objectivity_maximum_absolute', float(np.max(abs(action[:, 4:]))))
    record_property('operations', json.dumps(dict(network_constructors=1, public_restore_calls=1,
        dynamic_system_constructors=1, current_compatibility_maps=1, direction_products=1,
        native_residuals=0, linearizations=0, aircraft_solves=0, harmonic_solves=0)))
