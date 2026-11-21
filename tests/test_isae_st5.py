"""Independent checks of the explicit ST-5 load reconstruction."""
from pathlib import Path
import importlib.util
import numpy as np
import pytest

spec = importlib.util.spec_from_file_location('isae_st5', Path(__file__).parents[1]/'scripts/verify-isae-st5.py')
study = importlib.util.module_from_spec(spec)
spec.loader.exec_module(study)


def cantilever():
    return study.parse_asw('''Name
Uniform independent load check
End
Units
L 1 ft
F 1 lb
T 1 s
End
Constant
32.18 .002378 1115
End
Reference
1 1 1
End
Ground
1 1 0
End
Beam 1
Cantilever
t x y z chord EIcc EInn GJ EA Dmg
1 0 0 0 1 1000 0 0 0 -4
2 0 1 0 1 1000 0 0 0 -4
End
''')


def test_constant_load_integrates_analytic_force_and_first_moment():
    original = cantilever()
    source = original.dumps()
    for n in [4,8,16]:
        derived, settings, loads, checks = study.reconstruct(original,n)
        np.testing.assert_allclose(np.sum([r['force'] for r in loads],axis=0),[0,0,4],atol=1e-14)
        np.testing.assert_allclose(checks[0]['nodal_jig_moment_lbft'],[2,0,0],atol=1e-14)
        np.testing.assert_allclose(checks[0]['continuous_jig_moment_lbft'],[2,0,0],atol=1e-14)
        assert not np.any(derived.beams[0].value('Dmg',[1,1.5,2]))
        assert original.dumps()==source
        assert np.all(original.beams[0].value('Dmg',[1,1.5,2])==-4)


def test_uniform_load_converges_to_independent_nonlinear_beam_solution():
    # Independent planar elastica BVP: EI theta''=-w(L-s)cos(theta),
    # theta(0)=0, theta'(L)=0, y'=cos(theta), z'=sin(theta).
    # Linear theory leaves a physical nonlinear error floor and is unsuitable
    # for asserting asymptotic convergence to a nonlinear solution.
    from scipy.integrate import solve_bvp
    weight, stiffness=400.,1000.
    s=np.linspace(0,1,61)
    guess=np.vstack([weight/stiffness*(s/2-s*s/2+s**3/6),
                     weight/stiffness*(1-s)**2/2,s,
                     weight/stiffness*(s*s/4-s**3/6+s**4/24)])
    reference=solve_bvp(lambda s,u:np.vstack([u[1],-weight/stiffness*(1-s)*np.cos(u[0]),np.cos(u[0]),np.sin(u[0])]),
                        lambda a,b:np.array([a[0],a[2],a[3],b[1]]),s,guess,tol=1e-11,max_nodes=2000)
    assert reference.success
    expected=reference.sol(1)[3]
    model=cantilever()
    model.beams[0].distributions['Dmg']=study.Distribution('Dmg',[1,2],[-weight,-weight],0)
    errors=[]
    for n in [8,16,32]:
        result=study.run_model(model,n)['result']
        tip=result['nodes'][-1]['position'][2]
        errors.append(abs(tip-expected))
        np.testing.assert_allclose(result['support_force'],[0,0,-weight],atol=1e-8)
        assert result['residual']<1e-8
    assert errors[1]<.3*errors[0]
    assert errors[2]<.3*errors[1]
    assert errors[-1]<1e-6


def test_reconstruction_does_not_silently_drop_offset_loads():
    model=cantilever()
    model.beams[0].distributions['DCcg']=study.Distribution('DCcg',[1,2],[.1,.1],0)
    with pytest.raises(AssertionError,match='DCcg'):
        study.reconstruct(model,8)
