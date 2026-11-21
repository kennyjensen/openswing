"""Pressure, beam-mass, mode-refinement and saved-state oracles for still air."""
import numpy as np
import pytest
from scipy.linalg import eigh
from scipy.optimize import brentq

from openswing.aero import AnalysisError, FlightCondition
from openswing.body_apparent import acceleration_force
from openswing.asw import parse_asw
from openswing.linear_dynamics import make_system, linearize, eigensystem
from openswing.source_quiescent import FLUID_POLICY, SourceQuiescentNetwork
from openswing.source_dynamics import SourceDynamicNetwork
from openswing.network import StaticNetwork
from openswing.bridge import dispatch
from test_source_fuselage import BODY_SOURCE
from test_source_quiescent import rotation


SOURCE = BODY_SOURCE.replace('0 .1', '0 .2').replace('200 0 0 0 0 0', '0 0 0 0 0 200')
RHO = 10.


def model():
    return parse_asw(SOURCE, beam_interpolation='drela-segspl-v1')


def panels(count):
    return {'default': count, 'beams': {'1': {'count': count, 'spacing': 'uniform'}}}


def beam_matrices(count, factor, source):
    """Independent shear-spring and consistent/lumped-box fluid mass assembly."""
    h = 2/count; mu = factor*RHO*np.pi*.2**2
    k, m = np.zeros((count+1, count+1)), np.zeros((count+1, count+1))
    for i in range(count):
        k[i:i+2, i:i+2] += 200/h*np.array([[1., -1.], [-1., 1.]])
        m[i:i+2, i:i+2] += mu*h*(np.ones((2, 2))/4 if source else np.array([[2., 1.], [1., 2.]])/6)
    m[-1, -1] += 3.
    return k[1:, 1:], m[1:, 1:]


def frequency_request(factor=1.):
    values, vectors = eigh(*beam_matrices(4, factor, True))
    mode = vectors[:, 0]/vectors[-1, 0]*.001
    profile = [[1., 0., 0., 0.]]+[[1+(j+1)/2, 0., 0., float(v)] for j, v in enumerate(mode)]
    return dict(action='frequency',mode='frequency',source=SOURCE,panels=panels(4),
        numerics=dict(beam_interpolation='drela-segspl-v1',structural_operator=FLUID_POLICY),
        frequency=dict(frame='fixed',vacuum=False,quiescent_density=RHO,
            quiescent_body_added_mass_factor=factor,gravity_magnitude=0.,initial_shift=.3,
            frequencies=[1.,4.,8.,15.],inputs=[dict(kind='initial',name='Released body shear',
                state=dict(beam_fields=[dict(beam=1,displacement=profile)]))]))


@pytest.mark.parametrize('factor', [1., 2.])
def test_body_initial_spectrum_matches_independent_mode_and_preserves_coefficient(factor):
    result=dispatch(frequency_request(factor));assert result['converged']
    omega_squared=eigh(*beam_matrices(4,factor,True),eigvals_only=True)[0]
    assert result['base']['fluid']['body_added_mass_factor']==factor
    for row in result['samples']:
        s=.3+1j*row['omega'];expected=.001*s/(s*s+omega_squared)
        output=row['responses'][0]['output']['nodes'][-1]
        for key,value in [('displacement',expected),('velocity',s*expected-.001)]:
            actual=complex(output[key]['real'][2],output[key]['imag'][2])
            np.testing.assert_allclose(actual,value,rtol=4e-7,atol=3e-10)


@pytest.mark.parametrize('factor', [1., 2.])
def test_body_force_matches_independent_circumference_pressure_integral(factor):
    r = rotation([.4, -.2, .7]); radius = .37; acceleration = np.array([.3, -.8, 1.2])
    # Cylinder acceleration potential gives pressure proportional to a dot n.
    points, weights = np.polynomial.legendre.leggauss(96)
    theta = np.pi*(points+1)
    normals = np.cos(theta)[:, None]*r[:, 0]+np.sin(theta)[:, None]*r[:, 2]
    pressure = RHO*radius*(normals@acceleration)
    expected = -factor*np.pi*radius*np.sum(weights[:, None]*pressure[:, None]*normals, axis=0)
    actual = acceleration_force(r[:, 1], radius, RHO, acceleration, factor)
    np.testing.assert_allclose(actual, expected, rtol=3e-14, atol=3e-14)
    np.testing.assert_allclose(actual@r[:, 1], 0, atol=2e-15)
    np.testing.assert_array_equal(acceleration_force(r[:, 1], 0., RHO, acceleration, factor), np.zeros(3))


@pytest.mark.parametrize('source', [False, True])
@pytest.mark.parametrize('factor', [1., 2.])
def test_actual_nodal_fluid_matrix_and_rigid_report_match_independent_integrals(source, factor):
    cls = SourceQuiescentNetwork if source else StaticNetwork
    dry_cls = SourceDynamicNetwork if source else StaticNetwork
    wet = cls(model(), panels(4), None, [0, 0, 0], [], quiescent_density=RHO,
              quiescent_body_added_mass_factor=factor)
    dry = dry_cls(model(), panels(4), None, [0, 0, 0], [])
    x = np.zeros(wet.size); zero = np.zeros((wet.nn, 3)); measured = np.zeros((4, 4))
    for j in range(1, 5):
        a = zero.copy(); a[j, 2] = 1.
        _, fluid = wet.residual(x, detail=True, elastic_motion=(zero, zero, a, zero))
        _, vacuum = dry.residual(x, detail=True, elastic_motion=(zero, zero, a, zero))
        measured[:, j-1] = -(fluid['force']-vacuum['force'])[1:, 2]
    _, expected = beam_matrices(4, factor, source); expected[-1, -1] -= 3.
    np.testing.assert_allclose(measured, expected, rtol=3e-13, atol=3e-13)
    reference = np.array([.3, -.2, .4]); matrix = np.zeros((6, 6))
    for j, impulse in enumerate(np.eye(6)):
        alpha = np.broadcast_to(impulse[3:], zero.shape)
        a = impulse[:3]+np.cross(alpha, wet.rj-reference)
        _, fluid = wet.residual(x, detail=True, elastic_motion=(zero, zero, a, alpha))
        _, vacuum = dry.residual(x, detail=True, elastic_motion=(zero, zero, a, alpha))
        f, m = fluid['force']-vacuum['force'], fluid['moment']-vacuum['moment']
        matrix[:, j] = -np.r_[f.sum(axis=0), (m+np.cross(wet.rj-reference, f)).sum(axis=0)]
    if source:
        report = wet.rigid_acceleration_report(reference=reference)
        np.testing.assert_allclose(report['matrix'], matrix, rtol=3e-13, atol=3e-13)
    else:
        from openswing.inertia import apparent_properties
        report = apparent_properties(wet.meshes, RHO, reference, factor)
        np.testing.assert_allclose(report['spatial_matrix'], matrix, rtol=3e-13, atol=3e-13)


@pytest.mark.parametrize('source', [False, True])
@pytest.mark.parametrize('factor', [1., 2.])
def test_body_shear_modes_match_discrete_mass_and_refine_to_continuum(source, factor):
    mu = factor*RHO*np.pi*.2**2
    lam = brentq(lambda v: 1/np.tan(v)-3*v/(mu*2), 1e-8, np.pi/2-1e-8)
    continuum = lam/2*np.sqrt(200/mu); errors = []
    for count in (4, 8, 16):
        expected = np.sqrt(eigh(*beam_matrices(count, factor, source), eigvals_only=True)[0])
        system, _ = make_system(model(), panels=panels(count), gravity=[0, 0, 0],
            quiescent_density=RHO, quiescent_body_added_mass_factor=factor,
            structural_operator=FLUID_POLICY if source else None)
        modes, _ = eigensystem(*linearize(system), time_scale=system.W, count=1,
                              method='full_shift_invert', shift=(-.1, expected))
        omega = complex(*modes[0]['eigenvalue'])
        np.testing.assert_allclose(omega, 1j*expected, rtol=2e-7, atol=2e-8)
        errors.append(abs(omega.imag-continuum)/continuum)
    assert errors[1] < .3*errors[0] and errors[2] < .3*errors[1]
    assert errors[2] < .002


def test_body_coefficient_is_binding_in_saved_equilibrium_and_zero_flow_has_no_wind(monkeypatch):
    def forbidden(*args):raise AssertionError('Still air must not choose a wind direction.')
    monkeypatch.setattr(FlightCondition, 'vectors', forbidden)
    options = dict(panels=panels(4), gravity=[0, 0, 0], quiescent_density=RHO,
                   structural_operator=FLUID_POLICY)
    first, _ = make_system(model(), quiescent_body_added_mass_factor=2., **options)
    saved = first.equilibrium_state
    assert saved['identity']['quiescent_body_added_mass_factor'] == 2.
    assert saved['launch']['quiescent_body_added_mass_factor'] == 2.
    again, _ = make_system(model(), initial_state=saved, quiescent_body_added_mass_factor=2., **options)
    np.testing.assert_allclose(again.base, first.base, atol=1e-12)
    with pytest.raises(AnalysisError, match='does not match'):
        make_system(model(), initial_state=saved, quiescent_body_added_mass_factor=1., **options)


@pytest.mark.parametrize('value', [True, False, 0., 1.5, 3., np.nan, '2'])
def test_invalid_body_coefficients_are_not_silently_ignored(value):
    with pytest.raises(AnalysisError, match='coefficient'):
        make_system(model(), panels=4, quiescent_density=RHO, quiescent_body_added_mass_factor=value)
