"""Independent reference checks against line integrals and exact beam energies."""
from pathlib import Path
import sys

import numpy as np
from numpy.testing import assert_allclose
from scipy.integrate import quad

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from isae_st4_flow_reference import matrices, normal_influence


def test_horseshoes_against_independent_biot_savart_integrals():
    nodes=np.array([0.,.2,.7,1.2192]);samples=np.array([.06,.43,1.05]);chord=.2032
    actual=normal_influence(nodes,samples,chord)
    for i,s in enumerate(samples):
        dx=chord/2
        def wake(z):
            return quad(lambda x:-(s-z)/(4*np.pi*((dx-x)**2+(s-z)**2)**1.5),
                        0,np.inf,epsabs=1e-12,epsrel=1e-12)[0]
        for j,(a,b) in enumerate(zip(nodes[:-1],nodes[1:])):
            bound=quad(lambda z:dx/(4*np.pi*(dx*dx+(s-z)**2)**1.5),
                       a,b,epsabs=1e-12,epsrel=1e-12)[0]
            assert_allclose(actual[i,j],-(bound+wake(b)-wake(a)),atol=2e-12,rtol=2e-12)
    # Infinite-span limit: Gamma=pi*c*U*alpha, hence dCL/dalpha=2*pi.
    a=normal_influence(np.array([-1e7,1e7]),np.array([0.]),chord)[0,0]
    assert_allclose(-2/(chord*a),2*np.pi,atol=0,rtol=2e-8)


def integral_square(coefficients,length):
    square=np.polynomial.polynomial.polymul(coefficients,coefficients)
    return sum(value*length**(i+1)/(i+1) for i,value in enumerate(square))


def test_beam_and_apparent_energies_and_nonsymmetric_pitch_rate_load():
    _,_,p=matrices(intervals=13,structure_intervals=8,gravity=0)
    s=p['nodes'];length=1.2192;chord=.2032;ea=.437*chord;cg=.454*chord
    # Exact admissible fields h=s², h'=2s, phi=s.
    q=np.column_stack([s*s,2*s,s]).ravel()[3:]
    assert_allclose(q@p['stiffness']@q,4*(41.1744*9.81)*length+(20.2506*9.81)*length,
                    rtol=2e-12,atol=1e-9)
    mass=1.2947*integral_square([0,cg-ea,1],length)+.0078*(4*length**3/3+length**3/3)
    station=(17*.0254-.0001)*length/(length-.0001)
    for x in [-.0709,.0823]:
        displacement=station**2+(17*.0254-station)*2*station+(x-ea)*station
        mass+=.7237*displacement**2
    assert_allclose(q@p['structural_mass']@q,mass,rtol=2e-13)
    am=np.pi/4*p['density']*chord**2
    air=am*(integral_square([0,.5*chord-ea,1],length)+chord**2/32*length**3/3)
    assert_allclose(q@p['air_mass']@q,air,rtol=2e-13)
    heave=np.column_stack([s*s,2*s,np.zeros_like(s)]).ravel()[3:]
    twist=np.column_stack([np.zeros_like(s),np.zeros_like(s),s]).ravel()[3:]
    assert_allclose(heave@p['rate']@twist,am*p['speed']*length**4/4,rtol=2e-13)
    assert_allclose(twist@p['rate']@twist,am*p['speed']*(.75*chord-ea)*length**3/3,rtol=2e-13)
    assert_allclose(p['rate']@heave,0,atol=1e-15)


def test_exact_lift_virtual_work_and_control_point_kinematics_across_meshes():
    _,_,p=matrices(intervals=13,structure_intervals=8)
    s=p['nodes'];chord=.2032;ea=.437*chord
    # Cubic bending and linear twist are represented exactly on each element.
    q=np.column_stack([s**3,3*s*s,s]).ravel()[3:]
    a,b=p['aero_nodes'][:-1],p['aero_nodes'][1:]
    expected=(b**4-a**4)/4+(.25*chord-ea)*(b*b-a*a)/2
    assert_allclose(p['lift'].T@q,expected,atol=2e-15,rtol=2e-13)
    sample=p['samples']
    assert_allclose(p['flow_twist']@q,sample,atol=2e-15,rtol=2e-13)
    assert_allclose(p['flow_velocity']@q,sample**3+(.75*chord-ea)*sample,atol=2e-15,rtol=2e-13)


def test_signed_gravity_preload_and_eccentric_weight_second_variation():
    _,_,unloaded=matrices(intervals=13,structure_intervals=8,gravity=0)
    _,_,loaded=matrices(intervals=13,structure_intervals=8,gravity=-9.81)
    s=loaded['nodes'];length=1.2192;ea=.437*.2032;cg=.454*.2032
    q=np.column_stack([s*s,2*s,s]).ravel()[3:]
    station=(17*.0254-.0001)*length/(length-.0001)
    # Exact integrals of T*h'^2 + 2*D*h'*phi', plus pylon-height terms.
    energy=1.2947*length**4/3+1.2947*(cg-ea)*2*length**3/3
    for x in [-.0709,.0823]:
        energy+=.7237*(4*station**3/3+(x-ea)*2*station**2
                      +(17*.0254-station)*4*station**2)
    actual=q@(loaded['stiffness']-unloaded['stiffness'])@q
    assert_allclose(actual,-9.81*energy,atol=1e-8,rtol=1e-9)
