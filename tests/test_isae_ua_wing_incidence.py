"""Limiting equations, Jacobian and full-vector inclined production identities."""
from pathlib import Path
import sys
import numpy as np
import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from isae_ua_wing_incidence import InclinedWing
from isae_ua_wing_nonlinear import StraightWing
from isae_ua_incidence_reference import fields as section_fields
from isae_ua_wing_incidence_production import evaluate


def test_zero_incidence_reduces_to_independent_existing_wing_equations():
    old=StraightWing(20);new=InclinedWing(20,alpha_deg=0.)
    g=2*np.sin(np.pi*(np.arange(20)+.5)/20)
    for w in (-4.75,0.,3.2):
        ref=old.fields(g,w,75.)
        for rate in (ref['circulation_rate'],ref['circulation_rate']+.13):
            a=old.fields(g,w,75.,rate=rate);b=new.fields(g,w,75.,rate=rate)
            for key in ('circulation_rate','relative_velocity','local_speed','residual','CL'):
                np.testing.assert_allclose(a[key],b[key],rtol=0,atol=2e-12)


@pytest.mark.parametrize('alpha',(-9.,5.,9.))
def test_exact_steady_circulation_and_analytic_jacobian(alpha):
    wing=InclinedWing(20,alpha_deg=alpha)
    steady=wing.steady()
    np.testing.assert_allclose(wing.rates(steady,0.),0.,atol=2e-13,rtol=0)
    g=steady+.4*np.sin(3*np.pi*(np.arange(20)+.5)/20)
    actual=wing.jacobian(g,-4.75)
    columns=[]
    for i in range(20):
        z=g.astype(complex);z[i]+=1e-25j
        columns.append(wing.rates(z,-4.75).imag/1e-25)
    np.testing.assert_allclose(actual,np.column_stack(columns),rtol=2e-13,atol=2e-12)


def test_large_span_limit_recovers_independent_inclined_section_vector_loads():
    wing=InclinedWing(4,span=1e10,alpha_deg=9.)
    for g,w,a in ((4.,-4.75,80.),(-2.,3.2,-60.)):
        ref=section_fields(g,w,a,alpha_deg=9.)
        actual=wing.fields(np.full(4,g),w,a,rate=np.full(4,ref['circulation_rate']))
        for key in ('CF','CF_rate','CF_apparent','CL','CD'):
            np.testing.assert_allclose(actual[key],ref[key],rtol=0,atol=2e-9)


def test_inclined_nonuniform_state_matches_production_in_both_coordinate_frames():
    wing=InclinedWing(20,alpha_deg=9.)
    g=wing.steady()+2*np.sin(3*np.pi*(np.arange(20)+.5)/20)
    rate=wing.rates(g,-4.75)+.13
    ref=wing.fields(g,-4.75,80.,rate=rate)
    for representation in ('body','wind'):
        actual=evaluate(g,rate,-4.75,80.,alpha_deg=9.,representation=representation)
        for key in ('CF','CF_rate','CF_apparent','residual'):
            np.testing.assert_allclose(actual[key],ref[key],rtol=0,atol=2e-11)
        np.testing.assert_allclose(actual['stations'],wing.stations,rtol=0,atol=2e-13)
        np.testing.assert_allclose(actual['nodes'],wing.nodes,rtol=0,atol=2e-13)


def test_steady_startup_does_not_alias_a_full_forcing_period_in_step_selection():
    wing=InclinedWing(20,alpha_deg=9.)
    times=np.linspace(0,np.pi/9.5,81)
    a=wing.integrate(times,amplitude_ratio=.5,k=.95,method='DOP853')
    b=wing.integrate(times,amplitude_ratio=.5,k=.95,method='Radau')
    assert a['first_step']<=times[-1]/160
    for key in ('circulation','circulation_rate','CL'):
        x,y=(np.array([r[key] for r in result['rows']]) for result in (a,b))
        assert np.max(abs(x-y))/np.max(abs(y))<1e-8
