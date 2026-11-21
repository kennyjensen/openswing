import json
from pathlib import Path
import numpy as np
import pytest
from scipy.spatial.transform import Rotation
from openswing.asw import parse_asw
from openswing.aero import FlightCondition
from openswing.network import solve_static
from openswing.recovery import recover_section
from openswing.structure import Section, solve_cantilever
from test_network import model, beam


def shell_beam(stiffness='100 200 80 1000 900 700', extra=''):
    return beam(stiffness=stiffness).replace('End',
        't Cshell Nshell Atshell\n0 .2 .1 .003\n2 .2 .1 .003\n'+extra+'End')


def test_material_strain_integrates_back_to_force_and_moments_in_offset_rotated_section():
    # Independently integrate E*epsilon over a rotated, nonuniform-E rectangle.
    # Its weighted centroid and nonzero product of inertia exercise axis offsets.
    g,w=np.polynomial.legendre.leggauss(5)
    u,v=np.meshgrid(g*.3,g*.12); weights=np.outer(w,w).ravel()*.3*.12
    a=.47;c=.15+u.ravel()*np.cos(a)-v.ravel()*np.sin(a)
    n=-.08+u.ravel()*np.sin(a)+v.ravel()*np.cos(a)
    E=2e7*(1+.3*u.ravel()/.3); ew=E*weights; EA=ew.sum()
    cta,nta=ew@c/EA,ew@n/EA
    section=Section(EA=EA,EIcc=ew@(n-nta)**2,EInn=ew@(c-cta)**2,
                    EIcn=-ew@((c-cta)*(n-nta)),Cta=cta,Nta=nta,Cea=-.2,Nea=.3)
    force=[0,150,0];moment=[12,0,-7]
    stress=np.array([E[i]*recover_section(section,force,moment,cshell=c[i]-cta,nshell=n[i]-nta)['shell']['axial_strain'] for i in range(len(c))])
    np.testing.assert_allclose([stress@weights,-(stress*n)@weights,(stress*c)@weights],[150,12,-7],rtol=2e-14)


@pytest.mark.parametrize('torque',[-3.,3.])
def test_uniform_closed_shell_torsion_and_shear_center_transfer(torque):
    area, perimeter, thickness, shear_modulus=.06,1.1,.002,8e6
    gj=4*shear_modulus*area**2*thickness/perimeter
    sec=Section(GJ=gj,Cea=.14,Nea=-.03)
    force=np.array([7.,0,-4.]);ms=torque+sec.Nea*force[0]-sec.Cea*force[2]
    result=recover_section(sec,force,[0,ms,0],atshell=area*thickness)
    tau=result['shell']['shear_stress']
    # Bredt shear flow integrates to torque; wall shear energy equals twist work.
    assert 2*area*thickness*tau==pytest.approx(torque)
    assert tau**2/(2*shear_modulus)*perimeter*thickness==pytest.approx(torque*result['curvature_change'][1]/2)
    assert result['shell']['shear_stress_abs']==abs(tau)


def test_all_stiffness_couplings_and_signed_point_versus_strain_bound():
    matrix=np.array([[100,8,-13],[8,75,9],[-13,9,150.]])
    k=np.array([.03,-.02,.04]);force=np.array([3,-12,5.])
    sec=Section(EIcc=100,GJ=75,EInn=150,EIcs=8,EIcn=-13,EIsn=9,EA=800,GKc=300,GKn=400,Cta=.3,Nta=-.2,Cea=-.1,Nea=.07)
    shift=np.array([sec.Nta*force[1],-sec.Nea*force[0]+sec.Cea*force[2],-sec.Cta*force[1]])
    r=recover_section(sec,force,matrix@k-shift,cshell=.4,nshell=.2,atshell=.01)
    np.testing.assert_allclose(r['curvature_change'],k,atol=1e-17)
    assert r['shell']['axial_strain']==pytest.approx(-.015+.4*.04-.2*.03)
    assert r['shell']['axial_strain_bound']==pytest.approx(.015+.4*.04+.2*.03)
    assert r['strain'][1]==pytest.approx(-.015+sec.Nta*k[0]-sec.Cta*k[2])


@pytest.mark.parametrize('area,status',[(0,'missing'),(-.01,'invalid_negative_area_thickness')])
def test_missing_or_invalid_shell_is_null_without_fabricated_zero(area,status):
    r=recover_section(Section(),[1,2,3],[4,5,6],atshell=area)
    assert r['shell']['axial_strain'] is None
    assert r['shell']['axial_strain_bound'] is None
    assert r['shell']['shear_stress'] is None
    assert r['shell']['shear_status']==status
    json.dumps(r,allow_nan=False)


def test_rigid_limit_can_carry_stress_with_zero_strain_and_explicit_zero_shell_point():
    r=recover_section(Section(),[1,2,3],[4,5,6],cshell=0,nshell=0,atshell=.01)
    np.testing.assert_array_equal(r['strain'],0)
    np.testing.assert_array_equal(r['curvature_change'],0)
    assert r['shell']['axial_strain']==0
    assert r['shell']['shear_stress']==250


def test_unloaded_curved_twisted_jig_has_zero_mechanical_strain():
    b=shell_beam().replace('2 0 2 0','1 .3 1 .5 100 200 80 1000 900 700\n2 .7 2 1.5')
    b=b.replace('End','t twist\n0 15\n2 60\nEnd')
    r=solve_static(model(b),panels=6,gravity=[0,0,0])
    for e in r['elements']:
        np.testing.assert_allclose(e['curvature_change'],0,atol=1e-12)
        assert abs(e['shell']['axial_strain'])<1e-12
    assert r['structure']['summary']['strain_sections']==6


def test_large_rotation_pure_bending_reports_constant_material_strain():
    r=solve_static(model(shell_beam('100 0 0 0 0 0')),panels=8,gravity=[0,0,0],
                   loads=[dict(beam=1,t=2,moment=[50*np.pi,0,0])])
    for e in r['elements']:
        np.testing.assert_allclose(e['curvature_change'],[np.pi/2,0,0],atol=1e-10)
        assert e['shell']['axial_strain']==pytest.approx(-.1*np.pi/2,abs=1e-11)
        assert e['shell']['axial_strain_bound']==pytest.approx(.1*np.pi/2,abs=1e-11)


def test_section_recovery_is_covariant_under_rigid_rotation():
    force,moment=np.array([1.,.5,2.]),np.array([2.,1.,.3])
    q=Rotation.from_rotvec([0,.7,0]).as_matrix()
    b=shell_beam()
    br=b.replace('End',f't twist\n0 {np.rad2deg(.7)}\n2 {np.rad2deg(.7)}\nEnd')
    r=solve_static(model(b),panels=6,gravity=[0,0,0],loads=[dict(beam=1,t=2,force=force,moment=moment)])
    s=solve_static(model(br),panels=6,gravity=[0,0,0],loads=[dict(beam=1,t=2,force=q@force,moment=q@moment)])
    for x,y in zip(r['elements'],s['elements']):
        for key in ['force_local','moment_local','moment_axes','strain','curvature_change']:
            np.testing.assert_allclose(x[key],y[key],atol=1e-10)
        assert x['shell']['axial_strain']==pytest.approx(y['shell']['axial_strain'],abs=1e-11)
        assert x['shell']['shear_stress']==pytest.approx(y['shell']['shear_stress'],abs=1e-9)


def test_nonuniform_shell_and_doubled_station_use_material_midpoints():
    b='Beam 1\nStepped shell\nt y\n0 0\n2 2\nt EA Cshell Nshell Atshell\n0 1000 .2 .1 .002\n1 1000 .2 .1 .002\n1 2000 .3 .15 .004\n2 2000 .3 .15 .004\nEnd'
    r=solve_static(model(b),panels=6,gravity=[0,0,0],loads=[dict(beam=1,t=2,force=[0,10,0],moment=[0,2,0])])
    for e in r['elements']:
        assert e['t']==pytest.approx((e['t0']+e['t1'])/2)
        assert e['shell']['axial_strain']==pytest.approx(.01 if e['t']<1 else .005)
        assert e['shell']['shear_stress']==pytest.approx(500 if e['t']<1 else 250)


def test_concentrated_load_jump_is_not_averaged_between_elements():
    r=solve_static(model(shell_beam('0 0 0 1000 0 0')),panels=6,gravity=[0,0,0],
                   loads=[dict(beam=1,t=1,force=[0,10,0],moment=[0,2,0])])
    for e in r['elements']:
        assert e['t1']<=1 or e['t0']>=1
        assert e['axial_strain_tension']==pytest.approx(.01 if e['t']<1 else 0,abs=1e-12)
        assert e['shell']['shear_stress']==pytest.approx(2/.006 if e['t']<1 else 0,abs=1e-10)


def test_solved_response_matches_independent_beam_collocation_and_refines():
    sec=Section(EIcc=100,EInn=200,GJ=80,EA=1000,GKc=900,GKn=700)
    f,m=[1.,.5,2.],[2.,1.,.3]
    errors=[]
    for panels in [6,12]:
        r=solve_static(model(shell_beam()),panels=panels,gravity=[0,0,0],loads=[dict(beam=1,t=2,force=f,moment=m)])
        ref=solve_cantilever(2,sec,tip_force=f,tip_moment=m,samples=2001,tolerance=1e-9)
        ref_local_m=np.einsum('nji,nj->ni',ref.rotation,ref.moment)
        ref_local_f=np.einsum('nji,nj->ni',ref.rotation,ref.force)
        eps=ref_local_f[:,1]/1000+.2*ref_local_m[:,2]/200-.1*ref_local_m[:,0]/100
        expected=np.interp([e['t'] for e in r['elements']],ref.s,eps)
        errors.append(max(abs(expected-np.array([e['shell']['axial_strain'] for e in r['elements']]))))
    assert errors[1]<.3*errors[0]
    assert errors[1]<2e-6


def test_shell_metadata_does_not_change_equilibrium_and_stress_units_are_explicit():
    base=Path('examples/flexible.asw').read_text()
    b=base.rsplit('End',1)[0]+'t Cshell Nshell Atshell\n0 .2 .1 .003\n8 .1 .05 -.001\nEnd\n'
    c=FlightCondition(alpha=5,mach=0)
    r=solve_static(parse_asw(base),c,panels=4)
    s=solve_static(parse_asw(b.replace('L 1 m','L 1 ft').replace('F 1 N','F 1 lb')),c,panels=4)
    np.testing.assert_array_equal([n['position'] for n in r['nodes']],[n['position'] for n in s['nodes']])
    assert s['structure']['units']['stress_to_pa']==pytest.approx(4.4482216152605/.3048**2)
    assert s['structure']['summary']['invalid_stress_sections']>0
    assert r['structure']['summary']['max_abs_shell_strain'] is None
    assert all(e['shell']['axial_strain'] is not None for e in s['elements'])
    json.dumps(s,allow_nan=False)
