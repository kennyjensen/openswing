"""Sparse warm correction preserves moving-frame equations and acceptance."""
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import replace

import numpy as np
import pytest

from openswing.equilibrium_state import restore
from openswing.source_airflow import SourceAirflowNetwork,solve_source_airflow_steady
import openswing.seeded_corrector as seeded
from test_source_coupled import model,condition


@pytest.mark.parametrize('frozen',[False,True])
@pytest.mark.parametrize('mass',[False,True])
def test_sparse_airflow_warm_matches_cold_and_original_dense_path(frozen,mass,monkeypatch):
    m=model(mass=mass)
    c=condition(freeze_influences=frozen,rates=[.1,-.05,.07],
                acceleration=[.3,-.2,.1],angular_acceleration=[.4,-.1,.2])
    gravity=[1.,-2.,-10.]
    target=replace(c,beta=c.beta+.02,controls={1:.16})
    first=solve_source_airflow_steady(m,c,4,gravity=gravity,tolerance=1e-10)
    seed=first['equilibrium_state'];unchanged=deepcopy(seed)
    cold=solve_source_airflow_steady(m,target,4,gravity=gravity,tolerance=1e-10)
    warm=solve_source_airflow_steady(m,target,4,gravity=gravity,tolerance=1e-10,initial_state=seed)
    report=warm['equilibrium_initialization']['seeded_corrector']
    assert report['enabled'] and report['eligible'] and report['builder_detached']
    assert report['factor_wrappers_alive_before_final_tangent']==0
    assert report['builds'] and all(r['status']=='BUILT' for r in report['builds'])
    assert report['dense_tangent_builds']==0 and report['complete_residual_acceptance_unchanged']
    assert report['rank_acceptance_threshold_unchanged']
    @contextmanager
    def original_dense(*args,**kwargs):
        yield None
    monkeypatch.setattr(seeded,'attach',original_dense)
    dense=solve_source_airflow_steady(m,target,4,gravity=gravity,tolerance=1e-10,initial_state=seed)
    assert seed==unchanged
    for reference in (cold,dense):
        for key in ('positions','rotations','internal_force','internal_moment','reactions','circulation'):
            np.testing.assert_allclose(warm['equilibrium_state'][key],reference['equilibrium_state'][key],
                                       rtol=2e-7,atol=2e-9)
        for key in ('distributed_aero_force','distributed_aero_moment','applied_force','applied_moment'):
            np.testing.assert_allclose(warm[key],reference[key],rtol=2e-7,atol=2e-9)
    net=SourceAirflowNetwork(m,4,target,gravity,(),steady_trim=True)
    x=restore(net,warm['equilibrium_state'])
    assert np.max(abs(net.residual(x)))<1e-10
    assert net.iteration_fields is None and net.tangent_influences is None and net._tangent_loads is None


@pytest.mark.parametrize('frozen',[False,True])
def test_airflow_sparse_failure_uses_wall_safe_dense_recovery(frozen,monkeypatch):
    from openswing.asw import parse_asw
    from openswing.ground import GroundIntersectionError
    from test_wall_root import configuration,flight
    original,panels=configuration(False)
    m=parse_asw(original.dumps(),beam_interpolation='drela-segspl-v1')
    previous=replace(flight(),speed=8.,freeze_influences=frozen)
    # The stationary wall-root policy rejects all imposed frame motion;
    # nonzero frame motion is exercised by the separate mounted tests above.
    target=replace(previous,speed=10.)
    seed=solve_source_airflow_steady(m,previous,panels)['equilibrium_state']
    cold=solve_source_airflow_steady(m,target,panels)
    attempts=[]
    def unavailable(*args,**kwargs):
        attempts.append(True)
        raise RuntimeError('Injected sparse factor unavailability')
    monkeypatch.setattr(seeded,'NewtonBeamFactor',unavailable)
    warm=solve_source_airflow_steady(m,target,panels,initial_state=seed)
    report=warm['equilibrium_initialization']['seeded_corrector']
    assert attempts==[True] and report['enabled'] and report['dense_tangent_builds']>=1
    for key in ('positions','rotations','internal_force','internal_moment','reactions','circulation'):
        np.testing.assert_allclose(warm['equilibrium_state'][key],cold['equilibrium_state'][key],rtol=2e-7,atol=2e-9)
    net=SourceAirflowNetwork(m,panels,target,None,(),steady_trim=True)
    x=restore(net,warm['equilibrium_state']);assert np.max(abs(net.residual(x)))<=1e-8
    root=next(c['a'] for c in net.constraints if c['kind']=='ground')
    x[6*root+1]-=1e-3/net.L
    with pytest.raises(GroundIntersectionError):net.residual(x)


def test_time_network_and_custom_subclass_do_not_gain_steady_solver():
    class Custom(SourceAirflowNetwork):
        pass
    for cls,steady in ((SourceAirflowNetwork,False),(Custom,True)):
        net=cls(model(),4,condition(),[0.,0.,0.],(),steady_trim=steady)
        f=lambda x:x
        before=net.nfev;report={}
        with seeded.attach(net,f,{}, {},final_tangent=None,report=report) as builder:
            assert builder is None and not report['enabled'] and report['decline_reasons']
        assert net.nfev==before and not hasattr(f,'factorization_builder')
