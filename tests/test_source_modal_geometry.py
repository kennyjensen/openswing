"""Local source geometry supports against complete, independently probed rows."""
import numpy as np
import pytest

import openswing.linear_dynamics as dynamics
from openswing.asw import parse_asw
from openswing.inertia import Motion
from test_source_modal_mechanical_tangent import fixture
from test_source_moving_system import beam_source


@pytest.mark.parametrize('kind',['vacuum','still_air','moving','fuselage'])
def test_supports_cover_every_full_residual_row_at_curved_loaded_states(kind):
    # Nonzero loads, offsets, finite rotations and a distant sprung joint.
    # Moving case also has centrifugal/Coriolis terms in the physical residual.
    system=fixture(kind);n=system.network
    supports=dynamics.source_geometry_supports(system)
    assert supports is not None and len(supports)==6*n.nn
    zero=np.zeros(system.size)
    rate=np.random.default_rng(842).normal(0,1e-3,system.size)
    original=system.residual(zero,rate).copy()
    for j,rows in enumerate(supports):
        outside=np.ones(system.size,dtype=bool);outside[rows]=False
        for h in (1e-5,3e-6):
            direction=zero.copy();direction[j]=h
            plus=system.residual(direction,rate)
            minus=system.residual(-direction,rate)
            # Rows outside the graph must stay physically unchanged, not
            # merely small relative to the largest structural stiffness.
            np.testing.assert_array_equal(plus[outside],original[outside])
            np.testing.assert_array_equal(minus[outside],original[outside])
    np.testing.assert_array_equal(system.residual(zero,rate),original)


@pytest.mark.parametrize('kind',['vacuum','still_air','moving'])
def test_grouped_complete_pencil_matches_individual_columns_at_loaded_base(kind,monkeypatch):
    operator=dict(vacuum='drela-fixed-vacuum-v1',still_air='drela-fixed-still-air-v1',
                  moving='drela-moving-vacuum-v1')[kind]
    options=dict(quiescent_density=1.2) if kind=='still_air' else {}
    if kind=='moving':
        options['motion']=Motion(rates=[.02,-.01,.03],acceleration=[.1,.2,-.1])
    model=parse_asw(beam_source(),beam_interpolation='drela-segspl-v1')
    system,_=dynamics.make_system(model,panels=8,gravity=[.4,-.3,-1.1],
        structural_operator=operator,tolerance=1e-10,**options)
    before=system.network.nfev
    actual=dynamics.linearize(system,sparse=True)
    grouped_evaluations=system.network.nfev-before
    report=system.state_derivative_diagnostics.copy()
    assert report['grouped_geometry_columns']==6*system.network.nn
    assert report['geometry_column_groups']<report['grouped_geometry_columns']
    monkeypatch.setattr(dynamics,'source_geometry_supports',lambda system:None)
    before=system.network.nfev
    expected=dynamics.linearize(system,sparse=True)
    original_evaluations=system.network.nfev-before
    assert original_evaluations-grouped_evaluations==4*(
        report['grouped_geometry_columns']-report['geometry_column_groups'])
    np.testing.assert_allclose(actual[0].toarray(),expected[0].toarray(),rtol=2e-10,atol=2e-10)
    np.testing.assert_array_equal(actual[1].toarray(),expected[1].toarray())


@pytest.mark.parametrize('frame',['prescribed','free'])
def test_global_frame_equations_keep_individual_geometry_columns(frame):
    assert dynamics.source_geometry_supports(fixture('moving',frame)) is None


def test_airflow_keeps_its_complete_moving_field_derivatives():
    assert dynamics.source_geometry_supports(fixture('airflow')) is None


@pytest.mark.parametrize('name',['external','constitutive_response','constitutive_motion','residual'])
def test_unknown_load_or_residual_override_keeps_individual_columns(name):
    system=fixture('vacuum');original=getattr(system.network,name)
    setattr(system.network,name,lambda *args,**kwargs:original(*args,**kwargs))
    assert dynamics.source_geometry_supports(system) is None


def test_controller_keeps_complete_global_equations():
    system=fixture('vacuum');system.feedback=object()
    assert dynamics.source_geometry_supports(system) is None
