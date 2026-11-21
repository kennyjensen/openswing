"""Exact Newton elimination, owned factors, and full-physics retry policy."""
from pathlib import Path
import numpy as np
import pytest
from scipy.linalg import solve
from openswing.network import StaticNetwork
from openswing.aero import FlightCondition
from openswing.asw import parse_asw
from openswing.operating import time_load_constraints
from openswing.newton_structure import NewtonBeamFactor,StructureUnavailable
from openswing.structured_static import equilibrate,block_solve
from test_direct_circulation import model_for,state_for


CASES=[('flexible','prescribed',{}),('wing-body','free',{'ground_effect':1}),
       ('torsion-joint','prescribed',{}),('powered','mixed',{'powers':{1:30}}),
       ('dae','prescribed',{})]


def fixture(example,frame,extra,panels=4):
    targets={'force.x':.1,'moment.y':.2} if frame=='mixed' else None
    n=StaticNetwork(model_for(example),panels,
        FlightCondition(speed=30,alpha=5,mach=.1,position_earth=[0,0,30],**extra),
        None,[],operating_constraints=time_load_constraints(frame,targets))
    n._frequency_local_geometry=True
    return n,state_for(n)


@pytest.mark.parametrize('example,frame,extra',CASES)
def test_owned_factors_solve_original_full_matrix_for_multiple_rhs(example,frame,extra):
    n,x=fixture(example,frame,extra);j=n.jacobian(x,.6);original=j.copy()
    factor=NewtonBeamFactor(n,j)
    assert factor.report['beam_reduced_dimension']<n.size
    assert factor.report['additional_factor_bytes']<=128*1024**2
    assert not j.flags.writeable
    for b in [n.residual(x,.6),*np.random.default_rng(819).normal(size=(2,n.size))]:
        actual=block_solve(j,b,factorization=factor)
        expected=solve(original,b)
        np.testing.assert_allclose(actual,expected,rtol=1e-8,atol=1e-8)
        assert np.max(abs(original@actual-b))<1e-8*max(1.,np.max(abs(b)))
    np.testing.assert_array_equal(j,original)
    with pytest.raises(ValueError,match='different matrix'):
        block_solve(original,b,factorization=factor)


def test_storage_and_corrupt_factor_guards_retain_original_equations(monkeypatch):
    n,x=fixture(*CASES[0]);j=n.jacobian(x,.6)
    with pytest.raises(StructureUnavailable,match='storage budget'):
        NewtonBeamFactor(n,j,byte_budget=1)
    assert j.flags.writeable
    factor=NewtonBeamFactor(n,j);b=n.residual(x,.6)
    monkeypatch.setattr(factor.factor,'solve',lambda rhs:np.zeros_like(rhs,dtype=complex))
    with pytest.raises(StructureUnavailable,match='full-equation residual'):
        factor.solve(b)


@pytest.mark.parametrize('failure',['budget','factor','direction'])
def test_full_factor_failure_recovers_and_preserves_cold_equilibrium(failure,monkeypatch):
    import openswing.structured_static as static
    import openswing.newton_structure as full
    n,_=fixture('flexible','prescribed',{},panels=24)
    control,_=fixture('flexible','prescribed',{},panels=24)
    assert n.size>256
    expected,steps=equilibrate(control,full_structure=False)
    original=static.block_solve;calls=[];failed=[];full_factors=[]
    # Force the supported full fallback once at the first nonzero load, then
    # exercise its own unavailable/stale recovery using the real equations.
    def force_full(matrix,rhs,*args,**kwargs):
        factor=kwargs['factorization'];calls.append(type(factor).__name__)
        if len(calls)==1:raise ValueError('deliberate approximate direction failure')
        if isinstance(factor,NewtonBeamFactor):
            full_factors.append(factor)
            if failure in ('factor','direction') and not failed:
                failed.append(True)
                if failure=='factor':raise ValueError('deliberate stale full factor failure')
                return np.zeros_like(rhs)
        return original(matrix,rhs,*args,**kwargs)
    monkeypatch.setattr(static,'block_solve',force_full)
    if failure=='budget':
        def unavailable(*args,**kwargs):raise StructureUnavailable('deliberate full-factor storage limit')
        monkeypatch.setattr(full,'NewtonBeamFactor',unavailable)
    actual,actual_steps=equilibrate(n)
    assert actual_steps==steps==4
    assert any(r.get('exact_fallback') for r in n.structured_iterations)
    assert np.max(abs(n.residual(actual)))<=1e-12
    np.testing.assert_allclose(actual,expected,rtol=1e-8,atol=2e-9)
    if failure=='budget':assert any(r.get('full_structure_fallback')=='deliberate full-factor storage limit' for r in n.structured_iterations)
    else:
        assert failed and full_factors
        assert any(r.get('reuse_failed') for r in n.structured_iterations)
    for record in n.structured_iterations:
        assert record.get('matrix_age',0)<=6
    assert n.iteration_fields is None and n.tangent_influences is None
