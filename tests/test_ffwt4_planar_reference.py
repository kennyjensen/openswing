"""Independent Biot–Savart line quadrature for the planar diagnostic formula."""
import importlib.util
from pathlib import Path
import numpy as np
import pytest

spec=importlib.util.spec_from_file_location('planar_reference',Path(__file__).resolve().parents[1]/'scripts/isae_ffwt4_planar_reference.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)


def integrated_velocity(x,y,a,b,order):
    z,w=np.polynomial.legendre.leggauss(order)
    point=np.array([x,y,0.])
    value=np.zeros(3)
    # Split at closest approach so the two quadrature orders resolve a long
    # segment's narrow kernel peak without weakening the comparison gate.
    ends=np.unique([a,np.clip(y,a,b),b])
    for start,stop in zip(ends,ends[1:]):
        source=np.stack([np.zeros_like(z),(start+stop)/2+(stop-start)/2*z,np.zeros_like(z)],axis=1)
        r=point-source;dl=np.broadcast_to([0,(stop-start)/2,0],r.shape)
        value+=np.sum(w[:,None]*np.cross(dl,r)/np.linalg.norm(r,axis=1)[:,None]**3,axis=0)
    for endpoint,sign in [(b,1),(a,-1)]:
        # Exact change of integration variable, while integrating the vector
        # line kernel numerically: u=x+h*tan(theta), u in [0,infinity).
        h=abs(y-endpoint);lo=np.arctan(-x/h);hi=np.pi/2
        theta=(hi+lo)/2+(hi-lo)/2*z;u=x+h*np.tan(theta)
        source=np.stack([u,np.full_like(u,endpoint),np.zeros_like(u)],axis=1)
        r=point-source;du=h/np.cos(theta)**2*(hi-lo)/2
        dl=np.stack([du,np.zeros_like(u),np.zeros_like(u)],axis=1)
        value+=sign*np.sum(w[:,None]*np.cross(dl,r)/np.linalg.norm(r,axis=1)[:,None]**3,axis=0)
    return value/(4*np.pi)


@pytest.mark.parametrize('x,y,a,b',[
    (.039,0.,-.364,.364),(.039,-.363,-.364,-.358375),
    (.039,-.36401,-.364,-.358375),(.039,-.36399,-.5,-.364),
    (.039,.49999,.499125,.5),(.039,-.49,.2,.3),
    (.039,.01,-.5,-.4),(.039,.2,.19999,.20001),
])
def test_planar_matrix_entry_matches_two_line_quadratures(x,y,a,b):
    actual=m.planar_columns([x],[y],[a],[b])[0,0]
    for order in (128,256):
        expected=integrated_velocity(x,y,a,b,order)
        np.testing.assert_allclose(expected[:2],0,atol=1e-13,rtol=0)
        assert abs(actual-expected[2])/(1+abs(expected[2]))<1e-11


def test_constant_gamma_refinement_cancels_internal_wake_and_preserves_bound():
    x=np.array([.039,.039,.039]);y=np.array([-.37,.03,.43])
    whole=m.planar_columns(x,y,[-.5],[.5])[:,0]
    parts=m.planar_columns(x,y,[-.5,-.364,0.,.364],[ -.364,0.,.364,.5]).sum(axis=1)
    np.testing.assert_allclose(parts,whole,rtol=1e-13,atol=1e-13)
