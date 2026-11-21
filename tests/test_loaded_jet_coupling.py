"""Independent loaded circulation/jet feedback under prescribed 3D motion.

Four n=4, one-hertz cases share a Q32 nonlinear base and five reference fields.
Each uses one reference transfer solve and five production residual/load calls.
This is a component model check, not aircraft or experimental validation.
"""
import importlib.util
import json
from pathlib import Path

import numpy as np
import pytest

import loaded_jet_adapter as adapter
from openswing.aero import FlightCondition
from openswing.asw import parse_asw
from openswing.geometry import model_meshes


ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location(
    'loaded_jet_fin_reference', ROOT/'scripts/loaded_jet_fin_reference.py')
reference = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(reference)

STEP = 5e-6
EPSILON = 1e-24
OMEGA = 2*np.pi
MOTIONS = ('engine_rotation', 'fin_translation')


def _motion_arguments(motion, displacement, velocity, acceleration):
    if motion == 'engine_rotation':
        return dict(engine_angle=displacement, engine_rate=velocity,
                    engine_acceleration=acceleration)
    if motion == 'fin_translation':
        return dict(fin_displacement=displacement, fin_velocity=velocity,
                    fin_acceleration=acceleration)
    raise ValueError(motion)


def _check_branches(packet, meshes, ref, base, counts):
    """Independent profile/mask check at actual production inlet and geometry."""
    engine = packet['engines'][0]
    position = np.asarray(engine['position'])
    axis = np.asarray(engine['axes'])[:, 0]
    inlet = engine['axial_velocity']
    assert np.isfinite(inlet) and inlet > 0
    mesh = meshes[0]
    chord = mesh.beam.value('chord', mesh.tm)
    xax = mesh.beam.value('Xax', mesh.tm)
    slope = mesh.beam.value('dCLda', mesh.tm)
    hv = mesh.rm+((.25-xax)*chord)[:, None]*np.array([1., 0., 0.])
    cp = hv+(slope*chord/(4*np.pi))[:, None]*np.array([1., 0., 0.])
    minimum = np.inf
    for receiver, points in (('cp', cp), ('hv', hv)):
        counts['branch_guard_jet_calls'] += 1
        _, diagnostic = ref.jet(points, position, axis, inlet)
        np.testing.assert_array_equal(diagnostic['branches'],
                                      base[receiver+'_diagnostics']['branches'])
        clearance = np.asarray(diagnostic['clearance'])
        assert np.all(np.isfinite(clearance)) and np.min(clearance) >= 1e-4
        minimum = min(minimum, float(np.min(clearance)))
        flags = diagnostic['branches']
        assert np.count_nonzero(flags[:, 0] & ~flags[:, 2] & flags[:, 3]) >= 1
    speeds = np.array([row['normal_speed'] for row in packet['strips']])
    assert np.all(np.isfinite(speeds)) and np.all((speeds > 0) & (speeds < ref.sound))
    return minimum


@pytest.fixture(scope='module')
def loaded_jet_case():
    fixture = json.loads((ROOT/'docs/validation/loaded-jet-fixture.json').read_text())
    counts = dict(fields=0, base_solves=0, harmonic_solves=0,
                  reference_evaluations=0, reference_jet_calls=0,
                  branch_guard_jet_calls=0, production_evaluations=0)
    solve_mode = ['base_solves']

    def solve(matrix, rhs):
        assert matrix.shape == (4, 4) and rhs.shape == (4,)
        counts[solve_mode[0]] += 1
        assert counts['base_solves'] <= 9 and counts['harmonic_solves'] <= 4
        return np.linalg.solve(matrix, rhs)

    class CountedReference(reference.Reference):
        def field(self, targets, kind):
            counts['fields'] += 1
            assert counts['fields'] <= 5
            return super().field(targets, kind)

        def evaluate(self, *args, **kwargs):
            counts['reference_evaluations'] += 1
            return super().evaluate(*args, **kwargs)

        def jet(self, *args, **kwargs):
            counts['reference_jet_calls'] += 1
            return super().jet(*args, **kwargs)

    ref = CountedReference(4, 32, fixture, solve)
    base = ref.base()
    np.testing.assert_allclose(base['result']['residual'], 0., atol=1e-10, rtol=0.)
    assert np.max(abs(base['gamma'])) > 1e-8
    engine_field = ref.engine_field('engine_rotation', 0.)
    assert engine_field.shape == (4, 3)
    # One three-vector per circulation panel; contract the panel axis explicitly.
    induced = np.einsum('j,jk->k', base['gamma'], engine_field)
    assert abs(induced @ ref.ea) > 1e-8
    np.testing.assert_allclose(base['result']['engine_velocity'],
                               ref.speed*ref.c+induced, atol=1e-12, rtol=1e-12)
    # Prime exactly the two complex-displacement fields used by the four cases.
    for motion in MOTIONS:
        ref.engine_field(motion, 1j*EPSILON)
    assert counts['fields'] == 5
    assert 1 <= counts['base_solves'] <= 9

    model = parse_asw((ROOT/'docs/validation/loaded-jet-fixture.asw').read_text())
    meshes = model_meshes(model, 4)
    assert len(meshes) == 1 and len(meshes[0].rm) == 4
    np.testing.assert_array_equal(model.reference[1:], 0.)
    np.testing.assert_allclose(meshes[0].rm, ref.rm, atol=1e-12, rtol=1e-12)
    np.testing.assert_allclose(meshes[0].length, ref.ds, atol=1e-12, rtol=1e-12)
    np.testing.assert_allclose(meshes[0].frames,
        np.broadcast_to(np.column_stack([ref.c, ref.span, ref.normal]), (4, 3, 3)),
        atol=1e-12, rtol=1e-12)
    row = model.records['engine'][0]
    assert len(row) == 25 and int(row[1]) == 0
    np.testing.assert_array_equal(row[4:7], fixture['engine']['position'])
    np.testing.assert_array_equal(row[10:13], [80., -2., .6])
    assert fixture['engine']['setting'] == 1.
    return dict(fixture=fixture, ref=ref, base=base, model=model, meshes=meshes,
                parameters=adapter.MotionParameters.from_fixture(fixture),
                counts=counts, solve_mode=solve_mode, setup_counts=counts.copy())


@pytest.mark.parametrize('lag', [False, True], ids=['lag-off', 'lag-on'])
@pytest.mark.parametrize('motion', MOTIONS)
def test_loaded_moving_jet_matches_independent_transfer(
        loaded_jet_case, motion, lag, record_property):
    case = loaded_jet_case
    ref, base, counts = case['ref'], case['base'], case['counts']
    before = counts.copy()
    case['solve_mode'][0] = 'harmonic_solves'
    expected = ref.transfer(base['gamma'], motion, OMEGA, lag, EPSILON)
    np.testing.assert_allclose(expected['full_residual'], 0., atol=1e-10, rtol=0.)
    assert np.max(abs(expected['linear']['J']-ref.W/ref.speed)) > 1e-8
    f = case['fixture']
    condition = FlightCondition(speed=f['speed'], alpha=0., beta=0.,
        mach=f['mach'], density=f['density'], altitude_m=f['altitude_m'],
        stall=False, aero_lag=lag, freeze_influences=False,
        powers={f['engine']['index']: f['engine']['setting']})
    minimum_clearance = np.inf

    def evaluate(gamma, gamma_rate, displacement, velocity, acceleration):
        nonlocal minimum_clearance
        counts['production_evaluations'] += 1
        assert counts['production_evaluations'] <= 20
        packet, current = adapter.evaluate(case['model'], condition, case['meshes'],
            case['parameters'], gamma, gamma_rate,
            **_motion_arguments(motion, displacement, velocity, acceleration))
        minimum_clearance = min(minimum_clearance,
            _check_branches(packet, current, ref, base['result'], counts))
        wrench = adapter.outputs(packet, case['model'], current)
        for family, prefix in ((0, ''), (1, 'circulation_rate_'), (2, 'apparent_')):
            np.testing.assert_allclose(wrench[family, -1],
                np.r_[packet[prefix+'force'], packet[prefix+'moment']],
                atol=1e-12, rtol=1e-12)
        return packet, wrench

    packet, base_wrench = evaluate(base['gamma'], np.zeros(4), 0., 0., 0.)
    np.testing.assert_allclose(adapter.residual(packet), 0., atol=1e-10, rtol=0.)
    np.testing.assert_allclose(base_wrench, base['result']['wrenches'], atol=2e-8, rtol=2e-8)
    np.testing.assert_allclose(packet['engines'][0]['axial_velocity'],
                               base['result']['axial'], atol=2e-8, rtol=2e-8)
    assert packet['atmosphere']['sound_speed'] == packet['lifting_airflow']['sound_speed'] == f['sound_speed']
    assert packet['CDp'] > 0 and all(abs(row['cm']) > .01 for row in packet['strips'])
    derivatives, residuals = [], []
    for component in (np.real, np.imag):
        wrenches, raw_residuals = [], []
        for sign in (1, -1):
            amplitude = sign*STEP
            packet, wrench = evaluate(
                base['gamma']+amplitude*component(expected['gamma']),
                amplitude*component(1j*OMEGA*expected['gamma']),
                amplitude*component(1+0j), amplitude*component(1j*OMEGA),
                amplitude*component(-OMEGA**2+0j))
            wrenches.append(wrench)
            raw_residuals.append(adapter.residual(packet))
        derivatives.append((wrenches[0]-wrenches[1])/(2*STEP))
        residuals.append((raw_residuals[0]-raw_residuals[1])/(2*STEP))
    actual = derivatives[0]+1j*derivatives[1]
    complete_residual = residuals[0]+1j*residuals[1]
    np.testing.assert_allclose(complete_residual, 0., atol=2e-8, rtol=0.)
    np.testing.assert_allclose(actual, expected['wrenches'], atol=2e-8, rtol=2e-8)
    if not lag:
        np.testing.assert_array_equal(actual[1], 0.)
    np.testing.assert_array_equal(actual[1:3, 1], 0.)  # No type0 rate/apparent wrench.
    assert counts['fields'] == before['fields'] == 5
    assert counts['harmonic_solves']-before['harmonic_solves'] == 1
    assert counts['production_evaluations']-before['production_evaluations'] == 5
    assert counts['branch_guard_jet_calls']-before['branch_guard_jet_calls'] == 10
    assert counts['reference_jet_calls'] == 2*counts['reference_evaluations']+counts['branch_guard_jet_calls']
    record_property('maximum_circulation_residual', float(np.max(abs(complete_residual))))
    record_property('maximum_wrench_gate_fraction', float(np.max(
        abs(actual-expected['wrenches'])/(2e-8+2e-8*abs(expected['wrenches'])))))
    record_property('minimum_branch_clearance_m', minimum_clearance)
    for name, value in counts.items():
        record_property('case_'+name, value-before[name])
        record_property('shared_setup_'+name, case['setup_counts'][name])
