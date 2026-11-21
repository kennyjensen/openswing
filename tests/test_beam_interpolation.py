"""Opt-in beam cubics, independent coefficient oracle, and saved identity."""
from copy import copy, deepcopy
from dataclasses import replace
from fractions import Fraction as F
from pathlib import Path

import numpy as np
import pytest
from scipy.interpolate import CubicSpline

from openswing.asw import AswError, Distribution, parse_asw
from openswing.asw_edit import edit_distribution, model_data, signature
from openswing.beam_spline import NATURAL, DRELA_SEGSPL
from openswing.distribution_curve import graft, symmetry
from openswing.discretization import CURRENT_MESH_RECIPE, CHORDAL_MESH_RECIPE, LEGACY_MESH_RECIPE
from openswing.equilibrium_state import capture, identity, restore
from openswing.aero import AnalysisError, FlightCondition
from openswing.forcing import TimeForcing
from openswing.joints import hinge_laws
from openswing.network import StaticNetwork
from test_joints import linked
from test_network import beam, model


def primary_coefficients(knots, values):
    """Independent exact polynomial system, not the slope/Thomas algorithm.

    Unknowns are local [constant, linear, quadratic, cubic] coefficients.
    Interpolation, C1/C2 continuity, and zero first/last cubic terms fully
    specify the primary SEGSPL equations. Dense rational elimination is used
    only for these small tests; no production helper constructs the oracle.
    """
    x=list(map(F,knots)); y=list(map(F,values)); n=len(x)-1
    if n==1:
        return [[y[0],(y[1]-y[0])/(x[1]-x[0]),F(0),F(0)]]
    a=[]; b=[]
    def equation(entries,rhs=0):
        row=[F(0)]*(4*n)
        for j,v in entries:row[j]+=v
        a.append(row);b.append(F(rhs))
    for i in range(n):
        h=x[i+1]-x[i]
        equation([(4*i,F(1))],y[i])
        equation([(4*i+j,h**j) for j in range(4)],y[i+1])
        if i<n-1:
            equation([(4*i+1,F(1)),(4*i+2,2*h),(4*i+3,3*h*h),(4*i+5,F(-1))])
            equation([(4*i+2,F(2)),(4*i+3,6*h),(4*i+6,F(-2))])
    equation([(3,F(1))]);equation([(4*n-1,F(1))])
    for j in range(4*n):
        p=next(i for i in range(j,4*n) if a[i][j])
        a[j],a[p]=a[p],a[j];b[j],b[p]=b[p],b[j]
        pivot=a[j][j];a[j]=[v/pivot for v in a[j]];b[j]/=pivot
        for i in range(4*n):
            if i==j:continue
            multiplier=a[i][j]
            a[i]=[u-multiplier*v for u,v in zip(a[i],a[j])];b[i]-=multiplier*b[j]
    return [b[i:i+4] for i in range(0,4*n,4)]


@pytest.mark.parametrize('x,y',[
    ([0,2],[3,-1]),
    ([0,F(1,3),2],[1,-2,3]),
    ([-2,F(-1,2),F(1,4),2,5],[3,1,4,-2,1]),
])
def test_primary_zero_third_coefficients_against_independent_polynomial_system(x,y):
    d=Distribution('alpha',x,y,0,interpolation=DRELA_SEGSPL)
    expected=np.array(primary_coefficients(x,y),float).T[::-1]
    np.testing.assert_allclose(d._segments[0][2].c,expected,rtol=2e-13,atol=2e-13)
    spline=d._segments[0][2]
    assert abs(spline(x[0],3))<2e-12
    assert abs(spline(x[-1],3))<2e-12
    if len(x)>3:
        natural=CubicSpline(np.array(x,float),y,bc_type='natural')
        notaknot=CubicSpline(np.array(x,float),y)
        assert np.max(abs(natural.c-spline.c))>.01
        assert np.max(abs(notaknot.c-spline.c))>.01


def test_default_cubic_coefficients_are_bit_identical_to_old_natural_construction():
    x=[0,.3,1.2,3.];y=[2.,-1.,4.,.5]
    original=CubicSpline(x,y,bc_type='natural')
    samples=np.linspace(-1,4,31)
    expected=original(samples)
    expected[samples==x[-1]]=y[-1]  # existing exact terminal value safeguard
    for d in (Distribution('alpha',x,y,0),Distribution('alpha',x,y,0,interpolation=NATURAL)):
        np.testing.assert_array_equal(d._segments[0][2].c,original.c)
        np.testing.assert_array_equal(d.evaluate(samples),expected)


def test_reversed_segment_jumps_mirror_derivatives_and_extrapolation():
    x=[0,1,2,2,3,4];y=[0,1,4,10,11,14]
    d=Distribution('alpha',x[::-1],y[::-1],0,interpolation=DRELA_SEGSPL)
    assert d.evaluate(2,side='left')==4
    assert d.evaluate(2,side='right')==10
    assert d.evaluate(-2,mirror=True,side='left')==10
    assert d.evaluate(-2,mirror=True,side='right')==4
    assert d.evaluate(2,side='left',derivative=1)==pytest.approx(4)
    assert d.evaluate(2,side='right',derivative=1)==pytest.approx(0,abs=1e-14)
    assert d.evaluate(-2,mirror=True,side='right',derivative=1)==pytest.approx(-4)
    assert d.evaluate(-1)==pytest.approx(1)  # extrapolate first quadratic
    assert d.evaluate(5)==pytest.approx(19)
    mirrored=Distribution('y',[0,1,2],[5,6,9],0,interpolation=DRELA_SEGSPL)
    assert mirrored.evaluate(-1.5,mirror=True)==pytest.approx(2.75)
    assert mirrored.evaluate(-1.5,mirror=True,derivative=1)==pytest.approx(3)


SOURCE=Path('examples/rectangular.asw').read_text()


def test_lossless_text_copy_and_explicit_policy_roundtrip():
    text=SOURCE.replace('\n','\r\n')+'! keep exact bytes\r\n'
    m=parse_asw(text,beam_interpolation=DRELA_SEGSPL)
    for clone in (copy(m),deepcopy(m),replace(m)):
        assert clone.beam_interpolation==DRELA_SEGSPL
        assert clone.dumps()==text
    assert parse_asw(text).beam_interpolation==NATURAL  # text is not policy metadata
    assert signature(parse_asw(text))!=signature(m)
    canonical=m.dumps(canonical=True)
    reloaded=parse_asw(canonical,beam_interpolation=m.beam_interpolation)
    assert model_data(m)==model_data(reloaded)
    assert reloaded.dumps(canonical=True)==canonical
    assert all(d.interpolation==DRELA_SEGSPL for b in reloaded.beams for d in b.distributions.values())


@pytest.mark.parametrize('policy',['unknown','NATURAL-V1',None,True,{},['natural-v1']])
def test_unknown_policy_is_rejected_before_parsing(policy):
    with pytest.raises(AswError,match='interpolation policy'):parse_asw('',beam_interpolation=policy)
    with pytest.raises(AswError,match='interpolation policy'):Distribution('x',[0,1],[0,1],0,interpolation=policy)


def test_policy_is_immutable_and_mixed_distribution_edits_fail_closed():
    m=parse_asw(SOURCE,beam_interpolation=DRELA_SEGSPL)
    with pytest.raises(AswError,match='immutable'):m.beam_interpolation=NATURAL
    d=m.beams[0].distributions['chord']
    with pytest.raises(AswError,match='immutable'):d.interpolation=NATURAL
    with pytest.raises(AswError,match='policy'):replace(m,beam_interpolation=NATURAL)
    m.beams[0].distributions['chord']=Distribution('chord',d.t,d.values,0)
    with pytest.raises(AswError,match='interpolation'):m.dumps()


def test_edits_symmetry_and_free_graft_preserve_policy_and_reloaded_curve():
    m=parse_asw(SOURCE,beam_interpolation=DRELA_SEGSPL)
    changed=edit_distribution(m,1,'alpha',points=[[0,0],[3,9],[6,36]])
    assert changed.beam_interpolation==DRELA_SEGSPL and m.dumps()==SOURCE
    d=changed.beams[0].distributions['alpha']
    assert d.evaluate(1.5)==pytest.approx(2.25)
    expanded=symmetry(d,'independent',True)
    assert expanded.interpolation==DRELA_SEGSPL
    assert expanded.evaluate(-1.5)==pytest.approx(2.25)
    folded=symmetry(expanded,'positive',True)
    assert folded.interpolation==DRELA_SEGSPL
    g,report=graft(d,dict(points=[[0,1],[3,10],[6,37]],tangent=False),[0,6])
    assert g.interpolation==DRELA_SEGSPL
    assert g.evaluate(1.5)==pytest.approx(3.25)
    assert report['maximum_relative_value_error']<1e-12
    edited=edit_distribution(changed,1,'alpha',graft=dict(points=[[0,1],[3,10],[6,37]],tangent=False))
    assert edited.beam_interpolation==DRELA_SEGSPL
    assert edited.beams[0].value('alpha',1.5)==pytest.approx(3.25)
    reloaded=parse_asw(edited.dumps(),beam_interpolation=edited.beam_interpolation)
    assert model_data(edited)==model_data(reloaded)


def test_tangent_graft_refits_using_selected_policy():
    d=Distribution('alpha',[0,2,4,6],[0,1,-1,0],0,interpolation=DRELA_SEGSPL)
    out,report=graft(d,dict(points=[[1,0],[2,2],[3,0]],tangent=True,tolerance=1e-4),[0,6])
    assert out.interpolation==DRELA_SEGSPL
    assert report['maximum_relative_value_error']<=1e-4
    assert report['maximum_relative_slope_error']<=1e-4
    for t in [1.,3.]:
        assert out.evaluate(t)==pytest.approx(d.evaluate(t),abs=1e-12)
        assert out.evaluate(t,derivative=1)==pytest.approx(d.evaluate(t,derivative=1),abs=5e-5)


def test_beam_option_does_not_change_jangle_or_forcing_cubics():
    source=linked(curve='0 0\n1 1\n2 0').dumps()
    m=parse_asw(source,beam_interpolation=DRELA_SEGSPL)
    law=hinge_laws(m.records)[1]
    assert law.spline.interpolation==NATURAL
    assert np.rad2deg(law.angle(.5))==pytest.approx(.6875)
    c=FlightCondition()
    f=TimeForcing('time Gz\n0 0\n1 1\n2 0\n',m,c,c.motion(),2.,'prescribed')
    d=f.channels[0]['distribution']
    assert d.interpolation==NATURAL
    assert d.evaluate(.5)==pytest.approx(.6875)


@pytest.mark.parametrize('recipe',[LEGACY_MESH_RECIPE,CHORDAL_MESH_RECIPE,CURRENT_MESH_RECIPE])
def test_same_source_property_only_policy_change_rejects_saved_restore(recipe):
    # Straight two-knot geometry is identical; only an independent stiffness
    # table changes. Mesh and text cannot detect this semantic difference.
    source=model(beam().replace('End\n','t Cshell\n0 .1\n2 .1\nEnd\n')).dumps()
    m0=parse_asw(source)
    m0=edit_distribution(m0,1,'EIcc',points=[[0,100],[1,200],[2,150]])
    source=m0.dumps()
    m1=parse_asw(source,beam_interpolation=DRELA_SEGSPL)
    n0=StaticNetwork(m0,4,None,[0,0,0],(),mesh_recipe=recipe)
    n1=StaticNetwork(m1,4,None,[0,0,0],(),mesh_recipe=recipe)
    i0,i1=identity(n0),identity(n1)
    assert 'beam_interpolation' not in i0
    assert i1.pop('beam_interpolation')==DRELA_SEGSPL
    assert i0==i1
    assert not np.array_equal(n0.S,n1.S)
    for n,other in [(n0,n1),(n1,n0)]:
        saved=capture(n,np.zeros(n.size),residual=0.)
        np.testing.assert_array_equal(restore(n,saved),np.zeros(n.size))
        with pytest.raises(AnalysisError,match='does not match'):restore(other,saved)
        bad=deepcopy(saved);bad['identity']['beam_interpolation']='unknown'
        with pytest.raises(AnalysisError,match='does not match'):restore(n,bad)


def test_structural_operator_identity_is_conditional_and_rejects_other_equations():
    n=StaticNetwork(model(),4,None,[0,0,0],())
    saved=capture(n,np.zeros(n.size))
    assert 'structural_operator' not in saved['identity']
    n.structural_operator='drela-steady-zero-offset-v1'
    assert identity(n)['structural_operator']==n.structural_operator
    with pytest.raises(AnalysisError,match='does not match'):restore(n,saved)
