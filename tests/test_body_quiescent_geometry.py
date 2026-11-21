"""Curved/tapered endpoint pressure loads and mixed wing/body zero-flow loads."""
import numpy as np
import pytest
from openswing.asw import parse_asw
from openswing.source_quiescent import SourceQuiescentNetwork
from openswing.source_dynamics import SourceDynamicNetwork
from test_body_quiescent import SOURCE,RHO,panels
from test_source_quiescent import rotation


def pair(text,factor):
    model=parse_asw(text,beam_interpolation='drela-segspl-v1')
    return (SourceQuiescentNetwork(model,panels(4),None,[0,0,0],[],quiescent_density=RHO,
                quiescent_body_added_mass_factor=factor),
            SourceDynamicNetwork(model,panels(4),None,[0,0,0],[]))


@pytest.mark.parametrize('factor',[1.,2.])
def test_tapered_curved_source_body_matches_endpoint_pressure_quadrature(factor):
    wet,dry=pair(SOURCE.replace('3 2 0 0 .2','3 2 0 0 .5'),factor)
    r=wet.rj.copy();r[:,1]=[0,.02,.05,.03,-.01];r[:,2]=[0,.01,.04,.08,.1]
    turns=np.array([[.1,-.2,.1],[.2,.1,-.1],[-.1,.15,.2],[.1,.05,-.2],[-.05,.1,.1]])
    q=np.array([rotation(v) for v in turns]);x=np.zeros(wet.size)
    x[:6*wet.nn].reshape(-1,6)[:,:3]=(r-wet.rj)/wet.L
    x[:6*wet.nn].reshape(-1,6)[:,3:]=turns
    zero=np.zeros_like(r);a=np.array([[.2,-.3,.7],[-.1,.4,.2],[.7,.1,-.3],[-.3,.5,.6],[.2,-.4,.8]])
    _,fw=wet.residual(x,detail=True,elastic_motion=(zero,zero,a,zero))
    _,fd=dry.residual(x,detail=True,elastic_motion=(zero,zero,a,zero))
    # Integrate actual circular-section pressure, independently of the
    # production transverse projector and coefficient-sampling arrays.
    theta=2*np.pi*np.arange(128)/128
    frames=q@np.array([[0.,1.,0.],[-1.,0.,0.],[0.,0.,1.]])
    radius=.2+.15*wet.rj[:,0]
    normals=np.cos(theta)[None,:,None]*frames[:,None,:,0]+np.sin(theta)[None,:,None]*frames[:,None,:,2]
    pressure=RHO*radius[:,None]*np.einsum('nki,ni->nk',normals,a)
    density=-factor*radius[:,None]*(2*np.pi/128)*np.sum(pressure[:,:,None]*normals,axis=1)
    expected=np.zeros_like(r)
    for j in range(4):expected[j:j+2]+=.5*(density[j]+density[j+1])/4
    np.testing.assert_allclose(fw['force']-fd['force'],expected,rtol=3e-13,atol=3e-13)
    np.testing.assert_allclose(fw['moment']-fd['moment'],0.,atol=3e-13)


@pytest.mark.parametrize('factor',[1.,2.])
def test_mixed_wing_body_transfer_applies_body_coefficient_only_to_body(factor):
    wet,dry=pair(SOURCE+'''Beam 2
Rigid wing on body tip
t x y z chord
1 2 0 0 .3
3 2 2 0 .3
End
Joint
1 2 3 1 0
End
''',factor)
    zero=np.zeros((wet.nn,3));a=zero.copy();a[:,2]=1.;x=np.zeros(wet.size)
    _,fw=wet.residual(x,detail=True,elastic_motion=(zero,zero,a,zero))
    _,fd=dry.residual(x,detail=True,elastic_motion=(zero,zero,a,zero))
    f,m=fw['force']-fd['force'],fw['moment']-fd['moment']
    body=np.array([0.,0.,-factor*RHO*np.pi*.2**2*2])
    wing=np.array([0.,0.,-RHO*np.pi*.3**2/4*2])
    np.testing.assert_allclose(f.sum(axis=0),body+wing,atol=4e-12)
    np.testing.assert_allclose((m+np.cross(wet.rj,f)).sum(axis=0),
        np.cross([1,0,0],body)+np.cross([2,1,0],wing),atol=5e-12)
    assert len(wet.source_body_fluid_samples)==len(wet.source_fluid_samples)==2
