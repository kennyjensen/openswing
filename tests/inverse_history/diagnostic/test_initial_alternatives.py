"""Independent force balance and continuous-DAE oracles for finite witnesses."""
import numpy as np
import pytest
from openswing.aero import AnalysisError
from openswing.initial_diagnostics import controller_initial_alternatives, UnresolvedInitialControllerAuthority
from openswing.nonlinear_initial import consistent_initial


def spring_case(law, split=0., physical_hook=None, guard=True):
    # q'=v; 2(v'+U')=-500q; F1+F2=-500q; U=.4t.
    # The last state is a held controller IC with allowed nonzero rate.
    cache={}
    def residual(x,d,t):
        cache['local']=(x.copy(),d.copy(),t)
        return np.array([d[0]-x[1],2*(d[1]+d[2])+500*x[0],x[3]+x[4]+500*x[0],
                         x[2]-.4*t,law(x[4]),d[5]-.1])
    def physical(x,d,t):
        cache['physical']=(x.copy(),d.copy(),t)
        if physical_hook is not None:physical_hook(x,d,t)
        return residual(x,d,t)
    initial=np.array([-.0016,0.,0.,.8-split,split,.2]);rate=np.array([0.,0.,.4,0.,0.,.1])
    diagnostic=controller_initial_alternatives([4],[4],physical,1e-8) if guard else None
    def solve():
        return consistent_initial(residual,initial,[0,1,2,5],rate,
            fixed_state_indices=[1,2,5],fixed_rates={1:0.},accepted_initial_diagnostic=diagnostic)
    return solve,cache,initial,rate,residual


@pytest.mark.parametrize('boundary',[0.,1.])
def test_root_root_force_family_rejects_only_with_full_physical_witnesses(boundary):
    solve,cache,initial,rate,_=spring_case(lambda s:s-np.clip(s,0,1),boundary)
    with pytest.raises(UnresolvedInitialControllerAuthority) as caught:solve()
    witness=caught.value.accepted_initial_witness
    assert len(witness['alternatives'])==3
    assert witness['centered_first_change']>32e-8
    assert witness['controller_rows']==[4] and witness['controller_state_indices']==[4]
    for trial in witness['alternatives']:
        x,d=trial['state'],trial['physical_rate']
        assert trial['accepted'] and trial['held_coordinates_unchanged'] and trial['prescribed_rates_unchanged']
        assert abs(x[4]-boundary)>1e-6
        assert x[3]+x[4]==pytest.approx(.8,abs=1e-9)
        assert x[0]==pytest.approx(-.0016,abs=1e-10)
        np.testing.assert_array_equal(x[[1,2,5]],initial[[1,2,5]])
        assert d[1]==0. and d[2]==pytest.approx(.4,abs=1e-9) and d[5]==pytest.approx(.1,abs=1e-9)
        assert max(abs(trial['physical_anchor_residual']))<=1e-8
        assert [r['scaled_time_spacing'] for r in trial['refinements']]==[.01,.005]
        assert all(r['derivative_residual']<=1e-8 and r['one_sided_derivative_defect']<=1e-6 for r in trial['refinements'])
    np.testing.assert_allclose(cache['physical'][0],initial,rtol=0,atol=1e-12)
    np.testing.assert_allclose(cache['physical'][1],rate,rtol=0,atol=1e-12)
    assert cache['physical'][2]==0.


@pytest.mark.parametrize('law,split',[
    (lambda s:s-np.clip(-.5*s,0,1),0.),
    (lambda s:s-np.clip(1.5-.5*s,0,1),1.),
    (lambda s:s-.3,.3),
    (lambda s:s-abs(s)**2,0.),
])
def test_unique_regular_and_saturated_endpoints_preserve_complete_initial_state(law,split):
    solve,cache,initial,rate,_=spring_case(law,split)
    state,actual_rate,report=solve()
    np.testing.assert_allclose(state,initial,rtol=0,atol=1e-12)
    np.testing.assert_allclose(actual_rate,rate,rtol=0,atol=1e-12)
    assert report['accepted_initial_diagnostic']['witness'] is False
    assert all(r['rank']<r['unknowns'] for r in report['refinements']) # Auxiliary freedom is retained.
    np.testing.assert_array_equal(cache['physical'][0],state)
    np.testing.assert_array_equal(cache['physical'][1],actual_rate)


def test_fixed_rate_excludes_actuator_family_without_freeing_the_prescription():
    def residual(x,d,t):return np.array([d[0]-x[1],x[1]-np.clip(x[1],0,1)])
    diagnostic=controller_initial_alternatives([1],[1],residual,1e-8)
    state,rate,report=consistent_initial(residual,np.zeros(2),[0],np.zeros(2),fixed_rates={0:0.},accepted_initial_diagnostic=diagnostic)
    np.testing.assert_array_equal(state,np.zeros(2));assert rate[0]==0.
    assert report['prescribed_rate_error']==0.
    assert report['accepted_initial_diagnostic']['directions']==0


@pytest.mark.parametrize('ambiguous',[False,True])
def test_wide_array_preserves_auxiliary_nullspace_and_distinguishes_free_physical_rate(ambiguous):
    def residual(x,d,t):return np.array([d[0]-x[1],x[1]-np.clip(x[1] if ambiguous else -.5*x[1],0,1)])
    diagnostic=controller_initial_alternatives([1],[1],residual,1e-8)
    def solve():return consistent_initial(residual,np.zeros(2),[0,1],np.zeros(2),fixed_state_indices=[0],accepted_initial_diagnostic=diagnostic)
    if ambiguous:
        with pytest.raises(UnresolvedInitialControllerAuthority) as caught:solve()
        for trial in caught.value.accepted_initial_witness['alternatives']:
            assert trial['state'][0]==0.
            assert trial['state'][1]>1e-6
            assert trial['physical_rate'][0]==pytest.approx(trial['state'][1],abs=1e-9)
    else:
        state,rate,report=solve()
        np.testing.assert_array_equal(state,np.zeros(2));np.testing.assert_array_equal(rate,np.zeros(2))
        assert all(r['unknowns']>6 for r in report['refinements'])
        assert report['accepted_initial_diagnostic']['witness'] is False


def test_oblique_force_split_keeps_unowned_regular_equation():
    def residual(x,d,t):return np.array([x[0]+2*x[1]-.8,x[1]-np.clip(x[1],0,1),x[2]-.2])
    diagnostic=controller_initial_alternatives([1],[1],residual,1e-8)
    with pytest.raises(UnresolvedInitialControllerAuthority) as caught:
        consistent_initial(residual,np.array([.8,0.,.2]),[],np.zeros(3),accepted_initial_diagnostic=diagnostic)
    for trial in caught.value.accepted_initial_witness['alternatives']:
        x=trial['state'];assert x[0]+2*x[1]==pytest.approx(.8,abs=1e-10);assert x[2]==.2


def test_optional_domain_failure_skips_witness_and_restores_physical_anchor():
    def guard(x,d,t):
        if abs(x[4])>1e-8:raise AnalysisError('Outside declared physical chart.')
    solve,cache,initial,rate,_=spring_case(lambda s:s-np.clip(s,0,1),physical_hook=guard)
    state,actual_rate,report=solve()
    assert report['accepted_initial_diagnostic']['domain_skips']>0
    np.testing.assert_array_equal(cache['physical'][0],state)
    np.testing.assert_array_equal(cache['physical'][1],actual_rate)


def test_programming_error_is_not_hidden_and_restores_physical_anchor():
    def error(x,d,t):
        if abs(x[4])>1e-8:raise RuntimeError('Sentinel programming failure.')
    solve,cache,initial,rate,_=spring_case(lambda s:s-np.clip(s,0,1),physical_hook=error)
    with pytest.raises(RuntimeError,match='Sentinel programming'):solve()
    np.testing.assert_allclose(cache['physical'][0],initial,rtol=0,atol=1e-12)
    np.testing.assert_allclose(cache['physical'][1],rate,rtol=0,atol=1e-12)


def test_ordinary_physical_anchor_must_accept_not_only_stencil_equations():
    solve,cache,initial,rate,residual=spring_case(lambda s:s-np.clip(s,0,1),guard=False)
    def physical(x,d,t):
        values=residual(x,d,t);values[4]=x[4]
        return values
    diagnostic=controller_initial_alternatives([4],[4],physical,1e-8)
    state,actual_rate,report=consistent_initial(residual,initial,[0,1,2,5],rate,fixed_state_indices=[1,2,5],fixed_rates={1:0.},accepted_initial_diagnostic=diagnostic)
    np.testing.assert_allclose(state,initial,atol=1e-12,rtol=0)
    assert report['accepted_initial_diagnostic']['witness'] is False
