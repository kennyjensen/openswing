"""Biot--Savart kernels against high-precision closed forms and quadrature."""
from decimal import Decimal,localcontext
import math
import numpy as np
import pytest
from openswing.aero import finite_vortex,semi_infinite_vortex,horseshoe_velocity


def exact_axis(point,core,finite):
    with localcontext() as ctx:
        ctx.prec=90
        x,y,z=map(Decimal.from_float,map(float,point));c=Decimal.from_float(float(core))
        denominator=y*y+z*z+c*c
        # Only points on/near the physical filament use the existing singular
        # convention. Its upstream/finite-segment extensions are nonsingular.
        outside=x<0 or (finite and x>1)
        if denominator==0 or (float(denominator)<=1e-26 and not outside):return np.zeros(3)
        radius=(x*x+denominator).sqrt()
        coefficient=(x/radius-(x-1)/((x-1)**2+denominator).sqrt() if finite else 1+x/radius)/denominator
        coefficient/=4*Decimal.from_float(math.pi)
        return np.array([0.,float(-z*coefficient),float(y*coefficient)])


@pytest.mark.parametrize('finite',[False,True])
@pytest.mark.parametrize('core',[0.,1e-12,.003])
def test_near_axis_and_far_fields_retain_small_nonzero_velocities(finite,core):
    points=np.array([[x,y,-.3*y] for x in [-1e6,-1000.,-2.,-.1,0.,.5,1.,1.1,2.,1000.,1e6]
                     for y in [1.,.01,1e-6,1e-10,1e-12,1e-14,1e-18]])
    actual=(finite_vortex(points,[0.,0.,0.],[1.,0.,0.],core) if finite else
            semi_infinite_vortex(points,[0.,0.,0.],[1.,0.,0.],core))
    reference=np.array([exact_axis(point,core,finite) for point in points])
    np.testing.assert_allclose(actual,reference,rtol=3e-14,atol=0.)


def test_broadcast_cores_and_existing_principal_value_rule():
    points=np.array([[-2.,0.,0.],[-2.,1e-14,0.],[-2.,1e-12,0.]])
    cores=np.array([[0.],[.01]])
    for finite in [False,True]:
        f=finite_vortex if finite else semi_infinite_vortex
        actual=f(points,[0.,0.,0.],[1.,0.,0.],cores)
        expected=np.array([[exact_axis(p,c,finite) for p in points] for c in cores[:,0]])
        np.testing.assert_allclose(actual,expected,rtol=3e-14,atol=0.)
        np.testing.assert_array_equal(actual[0,0],np.zeros(3))
        assert np.linalg.norm(actual[0,1])>0


@pytest.mark.parametrize('finite',[False,True])
@pytest.mark.parametrize('scale',[1e-12,1e-6,1.,1e6])
def test_nonsingular_axis_extension_obeys_inverse_length_scaling(finite,scale):
    point=np.array([-2.,1e-10,-3e-11])
    function=finite_vortex if finite else semi_infinite_vortex
    end=np.array([scale if finite else 1.,0.,0.])
    actual=function(point*scale,np.zeros(3),end)
    reference=exact_axis(point,0.,finite)/scale
    np.testing.assert_allclose(actual,reference,rtol=3e-14,atol=0.)


def test_sa4_tip_exterior_bound_velocity_is_not_clipped():
    # Recorded SA-4 geometry: point lies 1.25 segment lengths from the start,
    # only 4.25e-14 from the extended axis. No filament crosses the receiver.
    point=[4.778583878246184e-7,1.0276999662551491,2.4794660800517434e-7]
    start=[7.64571130378377e-6,1.0276994600838973,3.967134014850334e-6]
    end=[1.9114324249272537e-6,1.0276998650206752,9.917858500887014e-7]
    # Independent directed-segment integral in 90-digit Decimal arithmetic.
    with localcontext() as ctx:
        ctx.prec=90
        p,a,b=[[Decimal.from_float(float(v)) for v in row] for row in (point,start,end)]
        ra=[x-y for x,y in zip(p,a)];rb=[x-y for x,y in zip(p,b)]
        dot=lambda x,y:sum(v*w for v,w in zip(x,y))
        na,nb=dot(ra,ra).sqrt(),dot(rb,rb).sqrt()
        cross=[ra[1]*rb[2]-ra[2]*rb[1],ra[2]*rb[0]-ra[0]*rb[2],ra[0]*rb[1]-ra[1]*rb[0]]
        factor=(na+nb)/(4*Decimal.from_float(math.pi)*na*nb*(na*nb+dot(ra,rb)))
        reference=np.array([float(v*factor) for v in cross])
    assert np.linalg.norm(reference)>5e-4
    # The rotated input is ill-conditioned in double precision; the axial
    # fixtures above separately require near-machine relative accuracy.
    np.testing.assert_allclose(finite_vortex(point,start,end),reference,rtol=1e-7,atol=1e-11)


def test_regularized_finite_and_wake_segments_match_numerical_integrals():
    from scipy.integrate import quad_vec
    a=np.array([.1,-.2,.3]);b=np.array([1.,.7,-.2]);direction=np.array([1.,.2,.1]);direction/=np.linalg.norm(direction)
    for point in [np.array([-.7,.9,.4]),np.array([1.2,-.8,.5])]:
        for core in [0.,.13]:
            finite=quad_vec(lambda t:np.cross(b-a,point-a-t*(b-a))/(np.linalg.norm(point-a-t*(b-a))**2+core**2)**1.5,0.,1.,epsabs=1e-13,epsrel=1e-13)[0]/(4*np.pi)
            wake=quad_vec(lambda t:np.cross(direction,point-a-t*direction)/(np.linalg.norm(point-a-t*direction)**2+core**2)**1.5,0.,np.inf,epsabs=1e-13,epsrel=1e-13)[0]/(4*np.pi)
            np.testing.assert_allclose(finite_vortex(point,a,b,core),finite,atol=2e-14,rtol=2e-13)
            np.testing.assert_allclose(semi_infinite_vortex(point,a,direction,core),wake,atol=2e-14,rtol=2e-13)
            np.testing.assert_allclose(finite_vortex(point,b,a,core),-finite,atol=2e-14,rtol=2e-13)
