"""Mass tangents: complete residual identities, hinges and physical controllers."""
from pathlib import Path
import numpy as np
import pytest
from openswing.asw import parse_asw,Distribution
from openswing.aero import FlightCondition
from openswing.linear_dynamics import make_system,linearize,eigensystem,solve_modes
from openswing.initial_response import ConsistentSubspace
from test_joints import linked
from test_feedback import configuration,condition,roots_match


@pytest.fixture(scope='module')
def wing():
    s,_=make_system(parse_asw(Path('examples/flexible.asw').read_text()),
        FlightCondition(alpha=4,mach=0,circulation_modes={1:3}),4,gravity=[0,0,0])
    a,m=linearize(s)
    return s,a,m


def test_loaded_swept_twisted_wing_resolves_without_discarding_weak_inertia(wing):
    s,a,m=wing
    first=None
    for tol in (1e-9,1e-11):
        modes,info=eigensystem(a,m,time_scale=s.W,count=100,rank_tolerance=tol)
        space=ConsistentSubspace(a,m,s.dynamic_indices,s.W,tol)
        assert info['finite_dimension']==space.report['finite_dimension']==35
        values=np.array([complex(*v['eigenvalue']) for v in modes])
        if first is not None:
            for value in values:assert min(abs(first-value))<1e-7
        first=values
        assert max(v['right_backward_error'] for v in modes)<1e-9
        assert max(v['left_backward_error'] for v in modes)<1e-9
    assert s.base_report()['max_displacement']>.01


def test_full_mass_action_matches_odd_part_of_quadratic_loaded_residual(wing):
    s,a,m=wing;zero=np.zeros(s.size);rng=np.random.default_rng(13)
    d=zero.copy();d[s.dynamic_indices]=rng.normal(size=len(s.dynamic_indices))*s.W
    base=s.residual(zero,zero)
    for h in (.1,.7,2.):
        plus,minus=s.residual(zero,h*d),s.residual(zero,-h*d)
        np.testing.assert_allclose((plus-minus)/(2*h),-m@d,atol=2e-12,rtol=2e-12)
    # Circulation-rate drag is quadratic; an affine assumption would be wrong.
    assert np.max(abs(plus+minus-2*base))>1e-5


@pytest.mark.parametrize('reverse',[False,True])
def test_cubic_hinge_rate_chain_rule_matches_converging_full_residual(reverse):
    model=linked(curve='-100 -40\n0 5\n100 140',axis='2 1 3',reverse=reverse,offset=True)
    for name,value in [('mg',19.6133),('mgcc',.3),('mgnn',.5)]:
        model.beams[0].distributions[name]=Distribution(name,np.array([0.,2.]),np.array([value,value]),0)
    s,_=make_system(model,None,4,gravity=[0,0,0],loads=[dict(beam=2,t=2,moment=[4,2,6])])
    _,m=linearize(s);zero=np.zeros(s.size);d=zero.copy()
    rng=np.random.default_rng(41);d[s.velocity_start:s.frame_start]=rng.normal(size=s.frame_start-s.velocity_start)*s.W
    start=6*(s.network.nn+s.network.ne);rows=slice(start,start+s.network.nc)
    hinge_rate=np.linalg.norm((m@d)[rows]);assert hinge_rate>1e-12
    d*=.3/hinge_rate  # Resolve the cubic truncation error above roundoff.
    errors=[]
    for h in (.02,.01,.005):
        actual=(s.residual(zero,h*d)-s.residual(zero,-h*d))/(2*h)
        errors.append(np.max(abs(actual+m@d)))
    assert errors[1]<.27*errors[0] and errors[2]<.27*errors[1],errors
    assert errors[-1]<2e-6


def test_nonlinear_accelerometer_law_has_the_correct_local_added_inertia():
    control=dict(outputs=[dict(actuator='E1',expression="command('E1')-3*tanh(2*error('Ay[2]'))")])
    out=solve_modes(configuration(),condition(),4,count=2,gravity=[0,0,0],controller=control)
    roots_match(out,np.roots([8,10,500]),tolerance=1e-7)
    assert out['diagnostics']['derivative_linearization']['rate_dependent_measurements']==['Ay[2]']


def test_piecewise_composition_between_coincident_sensors_preserves_its_zero_tangent():
    model=configuration();row=model.records['sensor'][1].copy();row[0]=3;model.records['sensor'].append(row)
    control=dict(outputs=[dict(actuator='E1',expression="abs(measurement('Ay[2]')-measurement('Ay[3]'))")])
    out=solve_modes(model,condition(),4,count=2,gravity=[0,0,0],controller=control)
    roots_match(out,np.roots([2,10,500]),tolerance=1e-7)
    assert out['diagnostics']['derivative_linearization']['controller_method'].startswith('composite')


@pytest.mark.parametrize('filename,powers',[('powered.asw',{1:500.}),('wing-body.asw',{})])
def test_polynomial_load_extraction_retains_propulsion_bodies_and_point_objects(filename,powers):
    from openswing.descriptor_mass import mass_matrix
    s,_=make_system(parse_asw(Path('examples',filename).read_text()),
        FlightCondition(speed=20,alpha=3,mach=0,powers=powers),4,gravity=[0,0,0])
    zero=np.zeros(s.size);_,state,options=s.residual(zero,zero,detail=True)
    _,data=s.network.residual(state.x,detail=True,**options)
    m=mass_matrix(s,state,data,1e-5)
    d=zero.copy();d[s.dynamic_indices]=np.random.default_rng(13).normal(size=len(s.dynamic_indices))*s.W
    for h in (.1,.7):
        actual=(s.residual(zero,h*d)-s.residual(zero,-h*d))/(2*h)
        np.testing.assert_allclose(actual,-m@d,atol=2e-12,rtol=2e-12)


def test_tiny_initial_spectral_directions_keep_physical_load_homogeneity(wing):
    from openswing.linear_dynamics import output_perturbation
    s,a,m=wing;modes,_=eigensystem(a,m,time_scale=s.W,count=6)
    mode=next(v for v in modes if v['eigenvalue'][1]>1)
    v=mode['right'];rate=complex(*mode['eigenvalue'])*v
    ordinary=output_perturbation(s,v,rate);amplitude=1e-12
    tiny=output_perturbation(s,amplitude*v,amplitude*rate)
    for group,fields in [('sections',['force_local','moment_local']),('global',['applied_force','applied_moment'])]:
        rows=zip(ordinary[group],tiny[group]) if group=='sections' else [(ordinary[group],tiny[group])]
        for first,second in rows:
            for field in fields:
                for part in ('real','imag'):
                    np.testing.assert_allclose(np.array(second[field][part])/amplitude,first[field][part],rtol=2e-6,atol=2e-6)
