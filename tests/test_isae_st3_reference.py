"""Analytic waves, sign symmetry and gravity check the independent harness."""
from pathlib import Path
import sys
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from isae_st3_reference import MATERIALS,LENGTH,ICC,INN,modes


def test_reference_bending_recovers_euler_bernoulli_limit():
    p=dict(MATERIALS['0_3_90'],Icc=0.)
    exact=np.array([1.875104068711961,4.694091132974175,7.854757438237613])**2/(2*np.pi*LENGTH**2)*np.sqrt(p['EI']/p['mass'])
    errors=[]
    for n in [12,24]:
        r=modes('0_3_90',n,count=8,material=p)
        bending=[f for f,e in zip(r['frequencies_Hz'],r['diagonal_energy_fractions']) if e[0]>.999]
        errors.append(abs(np.array(bending[:3])/exact-1))
    assert max(errors[1])<1e-4
    assert np.all(errors[1]<.08*errors[0])


def test_reference_torsion_matches_analytic_waves_and_refines():
    exact=np.arange(1,6,2)/(4*LENGTH)*np.sqrt(1.2/(ICC+INN))
    errors=[]
    for n in [32,64]:
        r=modes('0_3_90',n,count=8)
        torsion=[f for f,e in zip(r['frequencies_Hz'],r['diagonal_energy_fractions']) if e[1]>.999]
        assert len(torsion)>=3
        errors.append(abs(np.array(torsion[:3])/exact-1))
    assert max(errors[1])<.001
    assert np.all(errors[1]<.26*errors[0])


def test_coupling_sign_preserves_frequencies_and_reverses_twist():
    positive=MATERIALS['p15_0'];negative=dict(positive,coupling=-positive['coupling'])
    a=modes('p15_0',32,material=positive);b=modes('p15_0',32,material=negative)
    np.testing.assert_allclose(a['frequencies_Hz'],b['frequencies_Hz'],rtol=1e-10,atol=1e-9)
    for x,y in zip(np.asarray(a['shapes']),np.asarray(b['shapes'])):
        pivot=np.argmax(abs(x[:,0]));scale=x[pivot,0]/y[pivot,0]
        np.testing.assert_allclose(x[:,:2],scale*y[:,:2],rtol=1e-7,atol=1e-7)
        np.testing.assert_allclose(x[:,2],-scale*y[:,2],rtol=1e-7,atol=1e-7)


def test_upright_self_weight_lowers_bending_and_preserves_uncoupled_torsion():
    a=modes('0_3_90',32);b=modes('0_3_90',32,gravity=9.81)
    assert b['frequencies_Hz'][0]<a['frequencies_Hz'][0]
    torsion=lambda r:[f for f,e in zip(r['frequencies_Hz'],r['diagonal_energy_fractions']) if e[1]>.999]
    np.testing.assert_allclose(torsion(a),torsion(b),rtol=1e-8)


def test_centered_still_air_recovers_analytic_added_mass_limits():
    # Drela unsteady Eqs.41–44: centered normal inertia pi*rho*c^2/4
    # and spanwise rotary inertia pi*rho*c^4/128. These have independent
    # cantilever wave solutions when bending rotary inertia and gravity vanish.
    rho, chord = 1.23, .14
    added = np.pi*rho*chord**2/4
    p = dict(MATERIALS['0_3_90'], Icc=0.)
    result = modes('0_3_90', 64, air_density=rho, count=8, material=p)
    bending = [f for f,e in zip(result['frequencies_Hz'], result['diagonal_energy_fractions']) if e[0]>.999]
    torsion = [f for f,e in zip(result['frequencies_Hz'], result['diagonal_energy_fractions']) if e[1]>.999]
    exact_b = np.array([1.875104068711961,4.694091132974175,7.854757438237613])**2/(2*np.pi*LENGTH**2)*np.sqrt(p['EI']/(p['mass']+added))
    exact_t = np.arange(1,6,2)/(4*LENGTH)*np.sqrt(p['GJ']/(ICC+INN+added*chord**2/32))
    np.testing.assert_allclose(bending[:3], exact_b, rtol=2e-6)
    np.testing.assert_allclose(torsion[:3], exact_t, rtol=.001)


def test_fluid_inertia_is_not_added_to_self_weight():
    rho, chord = 1.23, .14
    added = np.pi*rho*chord**2/4
    equivalent = dict(MATERIALS['0_3_90'], mass=MATERIALS['0_3_90']['mass']+added,
                      Ip=ICC+INN+added*chord**2/32)
    # At zero gravity, moving centered fluid inertia into real mass gives the
    # same equations. With gravity it adds fictitious weight and must differ.
    air = modes('0_3_90', 32, air_density=rho)
    vacuum = modes('0_3_90', 32, material=equivalent)
    np.testing.assert_allclose(air['frequencies_Hz'], vacuum['frequencies_Hz'], rtol=1e-9)
    physical = modes('0_3_90', 32, gravity=9.81, air_density=rho)
    extra_weight = modes('0_3_90', 32, gravity=9.81, material=equivalent)
    assert physical['frequencies_Hz'][0] > extra_weight['frequencies_Hz'][0]
