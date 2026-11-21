"""Distributed elastic wing + fin + live aero + six released frame motions.

Expected data are independent continuous-rod/filament-quadrature results. This
is a controlled component regression, not a claim of Daedalus/ASWING parity.
"""
import hashlib
import json

import numpy as np

import free_elastic_adapter as adapter
from free_elastic_comparison import errors
from openswing.frequency_response import harmonic_solve
from openswing.linear_dynamics import linearize


def test_loaded_free_elastic_wing_fin_response():
    data = adapter.DATA
    provenance = json.loads((data/'provenance.json').read_text())
    for name, expected in provenance['files'].items():
        raw = (data/name).read_bytes()
        assert dict(bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest()) == expected
    fixture = adapter.load_fixture()
    with np.load(data/'manufacture-16.npz', allow_pickle=False) as saved:
        manufacture = {k: saved[k].copy() for k in saved.files}
    with np.load(data/'expected-16.npz', allow_pickle=False) as saved:
        reference = {k: saved[k].copy() for k in saved.files}
    assert provenance['relative_limit'] == .01
    count = 0
    def observe():
        nonlocal count
        count += 1
        assert count <= 5000
    prepared = adapter.build_network(fixture, 16, manufacture['counterloads'], residual_observer=observe)
    seed, packet, _ = adapter.seed_packet(prepared, manufacture['gamma'])
    assert count == 0
    np.testing.assert_allclose(prepared['network'].residual(seed), 0., atol=1e-9, rtol=0.)
    system, _, _ = adapter.correct_base(prepared, packet, tolerance=1e-9)
    A, M = linearize(system, step=1e-5, sparse=True)
    B, forcings, metadata = adapter.input_rhs(system, step=1e-5)
    criteria = []
    for i, frequency in enumerate(provenance['frequencies_Hz']):
        omega = 2*np.pi*frequency
        Z, _ = harmonic_solve(A, M, B, omega)
        actual, _ = adapter.directional_outputs(system, Z, omega, forcings, metadata,
                                                step=2.5e-6, include_baseline=i == 0)
        np.testing.assert_allclose(actual['physical_global_balance_body'], 0., atol=2e-6, rtol=0.)
        actual.update(adapter.selected_outputs(system, Z, omega))
        prefix = 'f'+str(i)+'__'
        expected = {k[len(prefix):]: v for k, v in reference.items() if k.startswith(prefix)}
        rows = errors(actual, expected, 16, fixture['normalization']['motion_length'])
        for row in rows:
            if row['relative'] is None:
                assert row['absolute'] <= 1e-8, (frequency, row)
            else:
                assert row['relative'] <= .01, (frequency, row)
        criteria.extend(rows)
    assert len(criteria) == 186
