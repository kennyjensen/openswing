"""Prototype support, linear solves, and isolation; not a release claim."""
from pathlib import Path
import numpy as np
import pytest
from scipy.linalg import solve
from openswing.asw import parse_asw
from openswing.aero import FlightCondition
from openswing.network import StaticNetwork
from openswing.structured_static import jacobian, block_solve, linearization


@pytest.mark.parametrize('example,extra', [
    ('rectangular', {}), ('flexible', {}), ('wing-body', {}),
    ('powered', {'powers': {1: 50.}}), ('articulated', {}), ('dae', {}),
    ('flexible', {'circulation_modes': {1: 3}}),
    ('wing-body', {'freeze_influences': True}),
])
def test_grouped_structural_columns_equal_the_entire_lagged_linearization(example, extra):
    model = parse_asw(Path(f'examples/{example}.asw').read_text())
    net = StaticNetwork(model, 4, FlightCondition(mach=.2, beta=2, rates=[.01, -.02, .03],
                        ground_effect=1, position_earth=[0, 0, 30], **extra), None, [])
    rng = np.random.default_rng(435)
    x = rng.normal(0, .0001, net.size)
    x[net.gamma_start:net.operating_start] += .04
    before = net.residual(x, .6).copy()
    # Preserve the original forward-difference control separately from the
    # new direct blocks, which are checked against refined centered columns.
    actual, counts = jacobian(net, x, .6, direct_circulation=False,direct_mechanics=False)
    expected, dense_counts = jacobian(net, x, .6, grouped=False, direct_circulation=False,direct_mechanics=False)
    dense = actual.toarray()
    np.testing.assert_array_equal(dense, expected.toarray())
    assert counts['evaluations'] < dense_counts['evaluations']
    assert net.iteration_fields is None and net.tangent_influences is None
    np.testing.assert_array_equal(net.residual(x, .6), before)
    # Circulation columns retain the full, freshly updated field equations,
    # including nonlinear engine-jet feedback.
    for j in [net.gamma_start, net.size-1]:
        trial = x.copy(); trial[j] += 1e-6
        np.testing.assert_array_equal(dense[:, j], (net.residual(trial, .6)-before)/1e-6)
    rhs = rng.normal(size=net.size)
    step = block_solve(actual, rhs, net.gamma_start)
    reference = solve(dense, rhs)
    np.testing.assert_allclose(step, reference, rtol=1e-8, atol=1e-8)
    backward = np.linalg.norm(dense@step-rhs)/(np.linalg.norm(dense)*np.linalg.norm(step)+np.linalg.norm(rhs))
    assert backward < 1e-12
    # At zero external load, lagging changes only the lower-left block. The
    # rank certificate must see the exact mechanical and circulation blocks.
    initial = np.zeros(net.size)
    initial[net.gamma_start:] = .04
    zero, _ = jacobian(net, initial, 0., direct_circulation=False,direct_mechanics=False)
    full = net.jacobian(initial, 0., _direct_mechanics=False)
    split = net.gamma_start
    np.testing.assert_array_equal(zero.mechanical.toarray(), full[:split, :split])
    np.testing.assert_array_equal(zero.force_circulation, full[:split, split:])
    assert not np.any(zero.force_circulation)
    np.testing.assert_array_equal(zero.circulation, full[split:, split:])


def test_failed_linearization_restores_full_fields():
    net = StaticNetwork(parse_asw(Path('examples/flexible.asw').read_text()),4,FlightCondition(),None,[])
    x = np.zeros(net.size)
    expected = net.residual(x, .5)
    with pytest.raises(RuntimeError, match='deliberate'):
        with linearization(net, x, .5): raise RuntimeError('deliberate')
    assert net.iteration_fields is None and net.tangent_influences is None
    np.testing.assert_array_equal(net.residual(x, .5), expected)


def test_failed_sparse_direction_retries_the_full_physical_tangent(monkeypatch):
    import openswing.structured_static as module
    from openswing.network import _equilibrate_full
    model = parse_asw(Path('examples/flexible.asw').read_text())
    net = StaticNetwork(model,4,FlightCondition(mach=0),None,[])
    reference = StaticNetwork(model,4,FlightCondition(mach=0),None,[])
    expected, _ = _equilibrate_full(reference,tolerance=1e-12)
    original = module.block_solve
    calls = []
    def fail_once(*args,**kwargs):
        calls.append(True)
        if len(calls) == 1: raise RuntimeError('simulated sparse factorization failure')
        return original(*args,**kwargs)
    monkeypatch.setattr(module,'block_solve',fail_once)
    actual, _ = module.equilibrate(net)
    assert any(r.get('exact_fallback') for r in net.structured_iterations)
    assert np.max(abs(net.residual(actual))) <= 1e-12
    np.testing.assert_allclose(actual,expected,rtol=1e-8,atol=1e-8)
    assert net.iteration_fields is None and net.tangent_influences is None


def test_field_budget_failure_restores_physics_before_full_solver_fallback(monkeypatch):
    import openswing.structured_static as module
    from openswing.network import equilibrate
    net = StaticNetwork(parse_asw(Path('examples/flexible.asw').read_text()),4,FlightCondition(),None,[])
    def exhausted(*args,**kwargs):
        raise module.StructuredTangentUnavailable('simulated field storage budget')
    monkeypatch.setattr(module.IterationFields,'get',exhausted)
    state, _ = equilibrate(net)
    assert net.iteration_fields is None and net.tangent_influences is None
    assert np.max(abs(net.residual(state))) <= 1e-8


@pytest.mark.parametrize('example', ['flexible', 'wing-body'])
@pytest.mark.parametrize('asymmetric', [False,True])
def test_nonlinear_prototype_converges_to_full_physical_equilibrium(example, asymmetric):
    from openswing.structured_static import equilibrate as structured_equilibrate
    from openswing.network import _equilibrate_full as equilibrate, network_result
    model = parse_asw(Path(f'examples/{example}.asw').read_text())
    extra = dict(beta=2,rates=[.003,-.002,.001]) if asymmetric else {}
    original = StaticNetwork(model,4,FlightCondition(mach=0,**extra),None,[])
    faster = StaticNetwork(model,4,FlightCondition(mach=0,**extra),None,[])
    # Use the same final residual accuracy for the reference: a looser
    # reference's remaining force imbalance is not an exact physical target.
    reference, _ = equilibrate(original,tolerance=1e-12)
    actual, _ = structured_equilibrate(faster)
    assert np.max(abs(faster.residual(actual))) <= 1e-12
    assert faster.iteration_fields is None and faster.tangent_influences is None
    first, second = network_result(original,reference), network_result(faster,actual)
    # Symmetric aircraft can have equally fast left/right strips. Each
    # diagnostic must still name an actual maximizer and reproduce its values;
    # all strip fields and geometry remain covered by the complete comparison.
    def validate_maximum(result):
        maximum = result['lifting_airflow']['maximum']
        lifting = [s for s in result['strips'] if s['lifting']]
        strip = next(s for s in lifting if s['beam']==maximum['beam'] and s['t']==maximum['t'])
        assert maximum['normal_mach'] == max(s['normal_mach'] for s in lifting)
        for name in ('normal_mach','normal_speed','relative_velocity'):
            assert maximum[name] == strip[name]
        assert maximum['position'] == strip['velocity_position']
    validate_maximum(first); validate_maximum(second)
    def compare(a,b,path=''):
        if path == '/evaluations': return
        if path == '/lifting_airflow/maximum' and not asymmetric:
            for name in ('normal_mach','normal_speed'): compare(a[name],b[name],path+'/'+name)
            return
        if isinstance(a,dict):
            assert a.keys()==b.keys(),path
            for k in a: compare(a[k],b[k],path+'/'+k)
        elif isinstance(a,list):
            assert len(a)==len(b),path
            for i,v in enumerate(a): compare(v,b[i],path+'/'+str(i))
        elif isinstance(a,(int,float)) and not isinstance(a,bool):
            assert abs(a-b) <= 1e-8+1e-8*abs(a),(path,a,b)
        else: assert a==b,path
    compare(first,second)
