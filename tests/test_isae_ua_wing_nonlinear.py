"""Independent straight-wing closed integrals and nonlinear source identities."""
import math
from pathlib import Path
import sys

import numpy as np
import pytest
from scipy.integrate import quad

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from isae_ua_wing_nonlinear import StraightWing
from isae_suite_unsteady import model_text


@pytest.mark.parametrize('target,source',((0,0),(0,1),(4,4),(7,2)))
def test_closed_influence_matches_independent_biot_savart_quadrature(target,source):
    wing=StraightWing(8);y=wing.stations[target];a,b=wing.nodes[source:source+2];h=.5
    # Direct integrals of the finite +y segment and each +x ray. Return
    # minus the vertical velocity, consistent with the scalar C/H matrices.
    bound=quad(lambda s:h/(h*h+(y-s)**2)**1.5,a,b,epsabs=1e-13)[0]
    ray=lambda origin,d:quad(lambda x:-(y-origin)/(d*d-2*d*x+x*x+(y-origin)**2)**1.5,
                            0,np.inf,epsabs=1e-12,epsrel=1e-12)[0]
    cp=(bound+ray(b,h)-ray(a,h))/(4*math.pi)
    hv=(ray(b,0)-ray(a,0))/(4*math.pi)
    assert cp==pytest.approx(wing.C[target,source],abs=2e-12)
    assert hv==pytest.approx(wing.H[target,source],abs=2e-12)


@pytest.mark.parametrize('panels,velocity,scale,acceleration',((20,-4.75,2.,90.),(40,3.2,-1.4,-60.),(20,0.,.8,10.)))
def test_nonlinear_reference_matches_production_geometry_residual_and_each_load(panels,velocity,scale,acceleration):
    from openswing.asw import parse_asw
    from openswing.network import StaticNetwork
    from openswing.aero import FlightCondition,evaluate_aerodynamics
    wing=StraightWing(panels)
    gamma=scale*np.sin(np.pi*(np.arange(panels)+.5)/panels)
    reference=wing.fields(gamma,velocity,acceleration)
    condition=FlightCondition(speed=math.hypot(10,velocity),alpha=math.degrees(math.atan2(-velocity,10)),
        mach=0.,stall=False,aero_lag=True,acceleration=(0,0,acceleration))
    net=StaticNetwork(parse_asw(model_text(10.)),panels,condition,[0,0,0],[])
    rotations=np.broadcast_to(np.eye(3),(net.nn,3,3))
    meshes=net.deformed_meshes(net.rj,rotations,net.geometry(net.rj,rotations))
    mesh=meshes[0]
    np.testing.assert_allclose(mesh.r0[:,1],wing.nodes[:-1],atol=2e-13,rtol=0)
    np.testing.assert_allclose(mesh.r1[:,1],wing.nodes[1:],atol=2e-13,rtol=0)
    np.testing.assert_allclose(mesh.rm[:,1],wing.stations,atol=2e-13,rtol=0)
    qs=.5*1.225*100*10
    # Include an off-solution rate to check the exact residual sign and its
    # tangency-squared force, rather than only checking a zero residual.
    for offset in (0.,.13):
        rate=reference['circulation_rate']+offset
        expected=wing.fields(gamma,velocity,acceleration,rate=rate)
        actual=evaluate_aerodynamics(net.model,condition,meshes,
            point_positions=net.point_positions(net.rj,rotations),circulation=gamma,circulation_rate=rate)
        np.testing.assert_allclose(actual['circulation_residual'],expected['residual'],rtol=0,atol=2e-12)
        assert actual['force'][2]/qs==pytest.approx(expected['CL'],abs=2e-12)
        assert actual['circulation_rate_force'][2]/qs==pytest.approx(expected['CL_rate'],abs=2e-12)
        assert actual['apparent_force'][2]/qs==pytest.approx(expected['CL_added'],abs=2e-12)


def test_speed_uses_induced_bound_velocity_and_small_signal_reduces_to_prior_matrices():
    import json
    wing=StraightWing(20);gamma=2*np.sin(np.pi*(np.arange(20)+.5)/20)
    fields=wing.fields(gamma,-4.75,0.)
    # The piecewise-constant elliptical samples converge to constant
    # downwash Gamma_peak/(2*span), rather than equalling that continuum
    # limit on a finite grid. Check convergence without correcting H.
    errors=[]
    for n in (20,40):
        grid=StraightWing(n);g=2*np.sin(np.pi*(np.arange(n)+.5)/n)
        downwash=grid.H@g
        assert np.ptp(downwash)<2e-12
        errors.append(float(np.max(abs(downwash-.1))))
    assert errors[1]<.26*errors[0]
    downwash=wing.H@gamma
    np.testing.assert_allclose(fields['local_speed'],np.sqrt(10**2+4.75**2+downwash**2),atol=2e-13,rtol=0)
    ref=json.loads((ROOT/'artifacts/isae/ua2-time-20261101/reference-n20.json').read_text())
    np.testing.assert_allclose(-wing.C/10,ref['matrices']['K'],atol=2e-12,rtol=0)
    np.testing.assert_allclose(-2/(np.pi*100)*np.eye(20),ref['matrices']['M'],atol=2e-12,rtol=0)
