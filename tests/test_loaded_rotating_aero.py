"""Independent finite-base angular circulation and load transfer.

Two lag settings share seven independent Q32 fields and one circulation base.
Each case adds one small reference transfer solve and five prescribed-Gamma
production evaluations. This checks the declared wind-projected receiver
convention, not mesh convergence or external aerodynamic fidelity.
"""
from dataclasses import replace
import importlib.util
from pathlib import Path

import numpy as np
import pytest
from scipy.spatial.transform import Rotation

from openswing.aero import FlightCondition, evaluate_aerodynamics
from openswing.asw import parse_asw
from openswing.geometry import model_meshes, surface_frame
from openswing.local_motion import LocalMotion


ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location(
    'rotating_wing_fin_reference', ROOT/'scripts/rotating_wing_fin_reference.py')
reference = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(reference)

PIVOT = np.array([2., 0., .4])
AXIS = np.array([1., 2., 3.])/np.sqrt(14.)
STEP = 5e-6
OMEGA = 2*np.pi  # One hertz, unit angular-displacement phasor [rad].


def _rotated(mesh, matrix):
    first = (surface_frame(mesh.beam, mesh.t0, 'right')
             if mesh.frame0 is None else mesh.frame0)
    last = (surface_frame(mesh.beam, mesh.t1, 'left')
            if mesh.frame1 is None else mesh.frame1)
    return replace(mesh,
        r0=PIVOT+(mesh.r0-PIVOT)@matrix.T,
        r1=PIVOT+(mesh.r1-PIVOT)@matrix.T,
        rm=PIVOT+(mesh.rm-PIVOT)@matrix.T,
        frames=matrix@mesh.frames, frame0=matrix@first, frame1=matrix@last)


class _SurfaceMotion:
    def __init__(self, meshes, rate, acceleration):
        origins = np.concatenate([mesh.rm for mesh in meshes])
        velocity, rates, linear_acceleration, angular_acceleration = (
            np.zeros_like(origins) for _ in range(4))
        start = 0
        for mesh in meshes:
            stop = start+len(mesh.rm)
            if mesh.beam.index == 2:
                arm = mesh.rm-PIVOT
                velocity[start:stop] = rate*np.cross(AXIS, arm)
                rates[start:stop] = rate*AXIS
                linear_acceleration[start:stop] = (
                    acceleration*np.cross(AXIS, arm)
                    + rate**2*np.cross(AXIS, np.cross(AXIS, arm)))
                angular_acceleration[start:stop] = acceleration*AXIS
            start = stop
        self.motion = LocalMotion(origins, velocity, rates,
                                  linear_acceleration, angular_acceleration)

    def surface(self):
        return self.motion


def _wrenches(packet, meshes):
    """Aggregate production outputs independently of reference.aggregate."""
    strips = packet['strips']
    beams = np.array([row['beam'] for row in strips])
    position = np.array([row['position'] for row in strips])
    force = np.array([row['force'] for row in strips])
    moment = np.array([row['moment'] for row in strips])+np.cross(position, force)
    rate = np.array([row['circulation_rate_force'] for row in strips])
    apparent = np.array([row['apparent_force'] for row in strips])
    chord = np.concatenate([mesh.beam.value('chord', mesh.tm) for mesh in meshes])
    axis = np.concatenate([mesh.beam.value('Xax', mesh.tm) for mesh in meshes])
    c = np.concatenate([mesh.frames[..., 0] for mesh in meshes])
    quarter = position+((.25-axis)*chord)[:, None]*c
    rate_moment = np.cross(quarter, rate)
    apparent_moment = (np.array([row['apparent_moment'] for row in strips])
                       + np.cross(position, apparent))

    def summed(f, m):
        return np.array([np.r_[f[mask].sum(0), m[mask].sum(0)] for mask in
                         (beams == 1, beams == 2, np.ones(len(beams), dtype=bool))])

    total = summed(force, moment)
    rate = summed(rate, rate_moment)
    apparent = summed(apparent, apparent_moment)
    for value, prefix in ((total, ''), (rate, 'circulation_rate_'),
                          (apparent, 'apparent_')):
        np.testing.assert_allclose(value[-1],
            np.r_[packet[prefix+'force'], packet[prefix+'moment']],
            atol=1e-12, rtol=1e-12)
    return np.stack([total, rate, apparent, total-rate-apparent])


@pytest.fixture(scope='module')
def rotating_case():
    counts = dict(fields=0, solves=0, aerodynamic_evaluations=0)

    def field(geometry, receiver):
        counts['fields'] += 1
        return reference.field(geometry, 32, receiver)[0]

    def solve(matrix, rhs):
        assert matrix.shape == (8, 8) and rhs.shape == (8,)
        counts['solves'] += 1
        return np.linalg.solve(matrix, rhs)

    geometry = reference.geometry(4)
    hcp, hhv, haxis = (field(geometry, receiver) for receiver in ('cp', 'hv', 'axis'))
    base = reference.base(geometry, hcp, hhv, haxis, solve)
    plus = reference.geometry(4, STEP)
    minus = reference.geometry(4, -STEP)
    dcp = (field(plus, 'cp')-field(minus, 'cp'))/(2*STEP)
    dhv = (field(plus, 'hv')-field(minus, 'hv'))/(2*STEP)
    assert counts == dict(fields=7, solves=1, aerodynamic_evaluations=0)
    assert np.min(abs(base['gamma'])) > 1e-8
    np.testing.assert_allclose(base['residual'], 0., atol=1e-10, rtol=0.)

    model = parse_asw((ROOT/'docs/validation/rotating-wing-fin.asw').read_text())
    initial = model_meshes(model, 4)
    q0 = (Rotation.from_rotvec([0., np.deg2rad(7.), 0.])
          * Rotation.from_rotvec([0., 0., np.deg2rad(5.)])).as_matrix()
    meshes = [_rotated(mesh, q0) if mesh.beam.index == 2 else mesh for mesh in initial]
    for key in ('r0', 'r1', 'rm'):
        np.testing.assert_allclose(np.concatenate([getattr(mesh, key) for mesh in meshes]),
                                   geometry[key], atol=1e-12, rtol=1e-12)
    for key, column in (('c', 0), ('s', 1), ('normal', 2)):
        np.testing.assert_allclose(np.concatenate([mesh.frames[..., column] for mesh in meshes]),
                                   geometry[key], atol=1e-12, rtol=1e-12)
    return dict(geometry=geometry, base=base, hhv=hhv, dcp=dcp, dhv=dhv,
                solve=solve, model=model, meshes=meshes, counts=counts)


@pytest.mark.parametrize('lag', [False, True], ids=['lag-off', 'lag-on'])
def test_loaded_oblique_rotation_matches_independent_transfer(rotating_case, lag, record_property):
    case = rotating_case
    before = case['counts'].copy()
    expected = reference.transfer(case['geometry'], case['base'], case['hhv'],
        case['dcp'], case['dhv'], OMEGA, lag, case['solve'])
    np.testing.assert_allclose(expected['full_residual'], 0., atol=1e-10, rtol=0.)
    condition = FlightCondition(speed=10., alpha=0., beta=0., density=1.225,
        mach=0., altitude_m=0., stall=False, aero_lag=lag,
        freeze_influences=False, controls={3: 0.})

    def evaluate(gamma, gamma_rate, angle, rate, acceleration):
        q = Rotation.from_rotvec(angle*AXIS).as_matrix()
        meshes = [_rotated(mesh, q) if mesh.beam.index == 2 else mesh
                  for mesh in case['meshes']]
        case['counts']['aerodynamic_evaluations'] += 1
        result = evaluate_aerodynamics(case['model'], condition, meshes,
            circulation=gamma, circulation_rate=gamma_rate,
            local_motion=_SurfaceMotion(meshes, rate, acceleration))
        return result, _wrenches(result, meshes)

    base, base_wrenches = evaluate(case['base']['gamma'], np.zeros(8), 0., 0., 0.)
    assert base['atmosphere']['sound_speed'] == base['lifting_airflow']['sound_speed'] == reference.SOUND
    np.testing.assert_allclose(base['circulation_local_residual'], 0., atol=1e-10, rtol=0.)
    np.testing.assert_allclose(base_wrenches[0], reference.aggregate(case['geometry'],
        case['base']['force'], case['base']['moment']), atol=2e-8, rtol=2e-8)
    assert base['CDp'] > 0 and all(abs(strip['cm']) > .01 for strip in base['strips'])

    derivatives, residuals = [], []
    for component in (np.real, np.imag):
        values, raw_residuals = [], []
        for sign in (1, -1):
            amplitude = sign*STEP
            packet, wrench = evaluate(
                case['base']['gamma']+amplitude*component(expected['gamma']),
                amplitude*component(1j*OMEGA*expected['gamma']),
                amplitude*component(1+0j), amplitude*component(1j*OMEGA),
                amplitude*component(-OMEGA**2+0j))
            values.append(wrench)
            raw_residuals.append(np.asarray(packet['circulation_local_residual']))
        derivatives.append((values[0]-values[1])/(2*STEP))
        residuals.append((raw_residuals[0]-raw_residuals[1])/(2*STEP))
    actual = derivatives[0]+1j*derivatives[1]
    circulation_residual = residuals[0]+1j*residuals[1]
    np.testing.assert_allclose(circulation_residual, 0., atol=2e-8, rtol=2e-8)
    np.testing.assert_allclose(actual, expected['wrenches'], atol=2e-8, rtol=2e-8)
    for name in ('moving_field', 'induced_by_gamma', 'rotating_span', 'moving_lift_arm',
                 'profile_force', 'profile_couple', 'apparent_force', 'apparent_couple'):
        assert np.max(abs(expected['terms'][name])) > 1e-8, name
    if lag:
        assert np.max(abs(expected['terms']['rate_lift'])) > 1e-8
    else:
        np.testing.assert_array_equal(actual[1], 0.)
    assert case['counts']['fields'] == before['fields'] == 7
    assert case['counts']['solves']-before['solves'] == 1
    assert case['counts']['aerodynamic_evaluations']-before['aerodynamic_evaluations'] == 5
    record_property('maximum_circulation_residual', float(np.max(abs(circulation_residual))))
    record_property('maximum_wrench_gate_fraction', float(np.max(
        abs(actual-expected['wrenches'])/(2e-8+2e-8*abs(expected['wrenches'])))))
    record_property('production_calls', 5)
    record_property('reference_transfer_solves', 1)
