"""Display projection checks against the FAQ conversion and section planes."""
from dataclasses import replace
from pathlib import Path
import numpy as np
import pytest

from openswing.asw import parse_asw
from openswing.geometry import model_meshes, geometry_summary

HEADER='Name\nDisplay projection\nEnd\nUnit\nL 1 m\nT 1 s\nF 1 N\nEnd\nConstant\n9.80665 1.225 340.294\nEnd\nReference\n2 1 2\nEnd\n'

def wing(sweep=35., dihedral=0., twist=0.):
    x=2*np.tan(np.deg2rad(sweep))
    z=2*np.tan(np.deg2rad(dihedral))
    return parse_asw(HEADER+f'''Beam 1
Wing
t x y z twist chord Xax
1 0 0 0 {twist} .4 .25
2 {x} 2 {z} {twist} .2 .25
End
''')


def test_streamwise_plot_obeys_drela_normal_chord_conversion_and_preserves_axis():
    model=wing();mesh=model_meshes(model,4)[0]
    data=geometry_summary(model,meshes=[mesh])[0]
    normal=np.asarray(data['quads']);projected=np.asarray(data['streamwise_quads'])
    for end,(t,origin) in enumerate(((mesh.t0,mesh.r0),(mesh.t1,mesh.r1))):
        le,te=(0,3) if end==0 else (1,2)
        chord=mesh.beam.value('chord',t)
        np.testing.assert_allclose(projected[:,te]-projected[:,le],
            np.stack([chord/np.cos(np.deg2rad(35)),chord*0,chord*0],axis=1),atol=2e-15)
        np.testing.assert_allclose(.75*projected[:,le]+.25*projected[:,te],origin,atol=2e-15)
        np.testing.assert_allclose(np.linalg.norm(normal[:,te]-normal[:,le],axis=1),chord,atol=2e-15)
    assert not np.array_equal(projected,normal)


@pytest.mark.parametrize('twist,dihedral', [(12.,0.),(-8.,7.),(20.,65.)])
def test_projection_retains_twist_plane_and_normal_chord_when_shape_changes(twist,dihedral):
    model=wing(dihedral=dihedral,twist=twist);mesh=model_meshes(model,4)[0]
    # Give endpoints genuine changed frames, independently of beam-axis samples.
    angle=.13;rotation=np.array([[np.cos(angle),0,np.sin(angle)],[0,1,0],[-np.sin(angle),0,np.cos(angle)]])
    moved=replace(mesh,frame0=rotation@mesh.frames,frame1=rotation@mesh.frames)
    data=geometry_summary(model,meshes=[moved])[0]
    normal=np.asarray(data['quads']);projected=np.asarray(data['streamwise_quads'])
    for frame,le,te in ((moved.frame0,0,3),(moved.frame1,1,2)):
        before,after=normal[:,te]-normal[:,le],projected[:,te]-projected[:,le]
        span=frame[...,1];surface_normal=frame[...,2]
        # Only the component along s changes, hence the physical section's
        # chord projection and surface-plane normal are retained.
        recovered=after-np.einsum('ij,ij->i',after,span)[:,None]*span
        np.testing.assert_allclose(recovered,before,atol=2e-15)
        np.testing.assert_allclose(np.einsum('ij,ij->i',after,surface_normal),0,atol=2e-15)
        np.testing.assert_allclose(np.sum(after[:,1:]*span[:,1:],axis=1),0,atol=2e-15)


def test_singular_streamwise_projection_keeps_finite_normal_section():
    model=parse_asw(HEADER+'Beam 1\nWing\nt x y chord\n1 0 0 .4\n2 2 0 .4\nEnd\n')
    data=geometry_summary(model,panels=4)[0]
    assert data['streamwise_quads']==data['quads']
    assert np.all(np.isfinite(data['quads']))


def test_sa11_raw_geometry_and_vortex_preview_are_independent_of_plot_projection():
    from openswing.bridge import dispatch
    source=Path('examples/isae-sa11-wing-alone.asw').read_text()
    model=parse_asw(source);mesh=model_meshes(model,8)[0]
    data=geometry_summary(model,meshes=[mesh])[0]
    assert np.asarray(data['streamwise_quads']).shape==np.asarray(data['quads']).shape
    # Plot projection is obtained after meshing, without changing beam inputs.
    before=dispatch(dict(action='vortex_preview',source=source,panels=8))
    geometry_summary(model,meshes=[mesh])
    after=dispatch(dict(action='vortex_preview',source=source,panels=8))
    assert before==after
    assert source==Path('examples/isae-sa11-wing-alone.asw').read_text()


def test_projected_geometry_output_derivative_in_body_and_earth_frames():
    from openswing.linear_dynamics import make_system, output_perturbation
    model=wing();model.records['ground']=[[1,1.,0]]
    system,_=make_system(model,panels=4,gravity=[0,0,0],
                         position=[10,20,30],attitude=[15,-7,20])
    vector=np.zeros(system.size,dtype=complex)
    displacement=vector[:6*system.network.nn].reshape(-1,6)
    displacement[:,0]=1
    displacement[:,2]=.3j
    result=output_perturbation(system,vector,np.zeros_like(vector))
    expected=np.array([system.L,0,.3j*system.L])
    for key,translation in (('geometry',expected),('earth_geometry',system.R0@expected)):
        data=result[key][0]['streamwise_quads']
        actual=np.asarray(data['real'])+1j*np.asarray(data['imag'])
        np.testing.assert_allclose(actual,np.broadcast_to(translation,actual.shape),atol=3e-10)
