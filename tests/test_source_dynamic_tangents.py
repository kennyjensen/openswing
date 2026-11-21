"""Source operators must not silently use midpoint dynamic tangent shortcuts.

The fixture permits zero-rate stationary probes only. It does not implement
dynamic inertia, and these tests perform no equilibrium or modal solves.
"""
from types import SimpleNamespace

import numpy as np
import pytest

from openswing.asw import parse_asw
from openswing.linear_dynamics import DynamicSystem, linearize
from openswing.mechanical_tangent import mechanical_columns, MechanicalDerivativeUnavailable
from openswing.source_discrete import SourceSectionNetwork
from openswing.structural_outputs import (StructuralOutputTangent,
    StructuralOutputUnavailable, compatibility_columns, structural_outputs)


class StationarySourceProbe(SourceSectionNetwork):
    """Only remove the static guard for identically zero dynamic arguments."""
    def residual(self, x, *args, **kwargs):
        motion = kwargs.pop('elastic_motion', None)
        if motion is not None:
            assert all(np.count_nonzero(v) == 0 for v in motion)
        rate = kwargs.pop('circulation_rate', None)
        assert rate is None or np.size(rate) == 0
        return super().residual(x, *args, **kwargs)

    def external(self, *args, **kwargs):
        rate = kwargs.pop('circulation_rate', None)
        assert rate is None or np.size(rate) == 0
        return super().external(*args, **kwargs)


def system():
    # EA = 100 + 100*(t-1)^2. Endpoint averages differ from
    # midpoint values; this detects wrong-operator substitution.
    model = parse_asw('Name\nSource tangent guard fixture\nEnd\n'
        'Unit\nL 1 m\nT 1 s\nF 1 N\nEnd\n'
        'Constant\n10 1.225 340\nEnd\nReference\n2 1 2\nEnd\n'
        'Ground\n1 1 0\nEnd\nBeam 1\nStraight beam\n'
        't x y z chord\n1 0 0 0 .2\n3 0 2 0 .2\n'
        't EA EIcc GJ EInn\n1 100 80 60 90\n2 200 80 60 90\n3 500 80 60 90\nEnd\n',
        beam_interpolation='drela-segspl-v1')
    net = StationarySourceProbe(model, {'default':4, 'beams':{'1':{'nodes':[1.,1.5,2.,2.5,3.]}}},
                               None, [0.,0.,0.], [])
    return DynamicSystem(net, np.zeros(net.size), frame='fixed')


def test_source_direct_tangent_helpers_reject_before_midpoint_access():
    # A minimal owner proves rejection happens before touching midpoint fields.
    owner = SimpleNamespace(network=SimpleNamespace(analytic_mechanics=False))
    with pytest.raises(MechanicalDerivativeUnavailable, match='selected structural operator'):
        mechanical_columns(owner, {}, None, 1e-5)
    with pytest.raises(StructuralOutputUnavailable, match='selected structural operator'):
        compatibility_columns(owner)
    with pytest.raises(StructuralOutputUnavailable, match='selected structural operator'):
        StructuralOutputTangent(owner)
    assert structural_outputs(owner, None, 1e-5, []) is None
    assert owner.structural_output_diagnostics['method'] == 'physical output stencils'


def test_source_dense_and_sparse_stationary_tangents_keep_source_equations():
    s = system()
    n = s.network
    z = np.zeros(s.size)
    assert np.max(np.abs(s.residual(z, z))) < 1e-14
    h = 1e-5
    # Separate complete-residual stencil: no production derivative helper.
    expected = []
    for j in range(n.size):
        d = z.copy(); d[j] = h
        values = [s.residual(k*d, z) for k in (1., -1., 2., -2.)]
        expected.append((8*(values[0]-values[1])-(values[2]-values[3]))/(12*h))
    expected = np.column_stack(expected)
    dense = linearize(s, h, _stationary=True)
    sparse = linearize(s, h, sparse=True, _stationary=True).toarray()
    np.testing.assert_allclose(dense, expected, rtol=2e-10, atol=2e-10)
    np.testing.assert_allclose(sparse, expected, rtol=2e-10, atol=2e-10)
    for e, ea in enumerate((112.5, 162.5, 262.5, 412.5)):
        row, column = 6*e+1, 6*n.nn+6*e+1
        exact = -n.F*n.ds[e]/(n.L*ea)
        # Subtracting O(1) positions in the finite stencil costs a few e-12;
        # the wrong midpoint coefficient differs by more than 9e-6.
        assert dense[row,column] == pytest.approx(exact, abs=2e-11, rel=1e-12)
        assert sparse[row,column] == pytest.approx(exact, abs=2e-11, rel=1e-12)
        midpoint = -n.F*n.ds[e]*n.S[e,1,1]/n.L
        assert abs(exact-midpoint) > 9e-6
    assert s.state_derivative_diagnostics['mechanical_fallback'] is None
    assert s.state_derivative_diagnostics['direct_mechanical_columns'] == n.gamma_start-6*n.nn
    assert s.state_derivative_diagnostics['mechanical_assembly']['method'].startswith('direct source endpoint-average')
    assert 'selected structural operator' in s.state_derivative_diagnostics['compatibility_fallback']


@pytest.mark.parametrize('options', [
    {'frame':'prescribed'}, {'condition':object()}, {'quiescent_density':1.},
    {'controller':{}}, {'operating_constraints':[object()]},
    {'load_targets':{'force.x':0.}}, {'velocity':[1.,0.,0.]},
    {'strut_mode':'unknown'},
])
def test_source_factory_rejects_unsupported_context_before_construction(options, monkeypatch):
    from openswing.aero import AnalysisError
    from openswing.linear_dynamics import make_system
    import openswing.source_dynamics as source
    # Load subclasses before replacing their base with a construction sentinel.
    # Otherwise this focused test depends on earlier tests importing them.
    import openswing.source_quiescent
    import openswing.source_airflow
    def forbidden(*args, **kwargs):
        pytest.fail('Unsupported context reached network construction')
    monkeypatch.setattr(source, 'SourceDynamicNetwork', forbidden)
    model = SimpleNamespace(beam_interpolation='drela-segspl-v1')
    message = 'Strut mode' if 'strut_mode' in options else 'Source vacuum dynamics'
    with pytest.raises(AnalysisError, match=message):
        make_system(model, structural_operator=source.DYNAMIC_POLICY, **options)


def test_factory_default_identity_and_explicit_source_selection(monkeypatch):
    import openswing.linear_dynamics as linear
    import openswing.source_dynamics as source
    from openswing.aero import AnalysisError
    selected=[]
    class Selected(Exception):
        pass
    def old(*args, **kwargs):
        selected.append('old'); raise Selected
    def new(*args, **kwargs):
        selected.append('source'); raise Selected
    monkeypatch.setattr(linear, 'StaticNetwork', old)
    monkeypatch.setattr(source, 'SourceDynamicNetwork', new)
    model=SimpleNamespace(beam_interpolation='drela-segspl-v1')
    for policy in (None, 'midpoint-v1', source.DYNAMIC_POLICY):
        with pytest.raises(Selected):
            linear.make_system(model, structural_operator=policy)
    assert selected == ['old','old','source']
    with pytest.raises(AnalysisError, match='Unknown or unsupported'):
        linear.make_system(model, structural_operator='drela-steady-section-v1')
    with pytest.raises(AnalysisError, match='requires drela-segspl-v1'):
        linear.make_system(SimpleNamespace(beam_interpolation='natural-v1'),
                           structural_operator=source.DYNAMIC_POLICY)
