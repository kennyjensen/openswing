"""Source descriptor response against independent scalar mechanics.

The oracles use mass/spring balance and the published endpoint-average shear
dispersion, not another call to the dynamic matrix builder.
"""
from copy import deepcopy
import json
import numpy as np
import pytest

from openswing.bridge import dispatch
from openswing.numerical_policy import SOURCE_DYNAMIC, SOURCE_QUIESCENT, SOURCE_MOVING
from test_source_moving_system import AXIAL_SOURCE, PANELS
from test_source_quiescent import scalar_text


def z(value):
    return np.asarray(value['real']) + 1j*np.asarray(value['imag'])


def request(operator=SOURCE_MOVING, frame='prescribed', **options):
    return dict(action='frequency', mode='frequency', source=AXIAL_SOURCE, panels=deepcopy(PANELS),
        numerics=dict(beam_interpolation='drela-segspl-v1', structural_operator=operator),
        frequency=dict(frame=frame, gravity_magnitude=0., frequencies=[1., 4., 9., 15.],
            inputs=['acceleration.y'], **options))


@pytest.mark.parametrize('count', [4, 14])  # Dense and sparse full pencils.
@pytest.mark.parametrize('frame', ['prescribed', 'free', 'mixed'])
def test_frame_input_matches_two_mass_mechanics_and_original_equations(frame, count):
    value = request(frame=frame, matrices=True)
    value['panels'] = {'default': count, 'beams': {'1': {'count': count, 'spacing': 'uniform'}}}
    if frame != 'prescribed':
        value['frequency']['inputs'] = ['target.force.y']
    if frame == 'mixed':
        value['frequency']['load_targets'] = {'force.y': 0.}
    before = deepcopy(value)
    out = dispatch(value)
    assert value == before and out['converged'] and out['vacuum']
    assert out['base']['structural_operator'] == SOURCE_MOVING
    assert ('sparse' in out['diagnostics']['matrix_storage']) == (count == 14)
    a, m = (np.array(out['matrices'][key]) for key in ('A', 'M'))
    for sample in out['samples']:
        s = 1j*sample['omega']
        # m1(qddot + a_origin) + k q = 0; net target includes -sum(m*a).
        q = -3/(100+3*s*s) if frame == 'prescribed' else .6/(100+1.2*s*s)
        response = sample['responses'][0]
        tip = response['output']['nodes'][-1]
        assert z(tip['displacement'])[1] == pytest.approx(q, rel=3e-8, abs=2e-10)
        assert z(tip['velocity'])[1] == pytest.approx(s*q, rel=3e-8, abs=2e-10)
        residual = (s*m-a)@z(response['state'])-z(sample['B'])[:, 0]
        assert max(abs(residual)) < 2e-8
    json.dumps(out, allow_nan=False)


@pytest.mark.parametrize('operator', [SOURCE_DYNAMIC, SOURCE_MOVING, SOURCE_QUIESCENT])
def test_fixed_initial_shear_spectrum_and_apparent_mass(operator):
    density = 1.225
    n = 4
    theta = np.arange(n+1)*np.pi/(2*n)
    profile = [[1+j, 0., 0., .001*float(np.sin(t))] for j, t in enumerate(theta)]
    value = request(operator, 'fixed', initial_shift=.3)
    value['source'] = scalar_text('shear')
    value['frequency']['inputs'] = [dict(kind='initial', name='Released shear',
        state=dict(beam_fields=[dict(beam=1, displacement=profile)]))]
    if operator == SOURCE_QUIESCENT:
        value['frequency'].update(vacuum=False, quiescent_density=density)
    out = dispatch(value)
    assert out['converged']
    mass_per_length = .4 + (np.pi*density*1.2**2/4 if operator == SOURCE_QUIESCENT else 0.)
    omega = 2*np.sqrt(20/mass_per_length)*np.tan(np.pi/(4*n))
    for sample in out['samples']:
        s = .3+1j*sample['omega']
        q = .001*s/(s*s+omega*omega)
        response = sample['responses'][0]
        tip = response['output']['nodes'][-1]
        assert z(tip['displacement'])[2] == pytest.approx(q, rel=3e-8, abs=2e-11)
        assert z(tip['velocity'])[2] == pytest.approx(s*q-.001, rel=3e-8, abs=2e-11)
        np.testing.assert_allclose(z(response['state_rate']), s*z(response['state'])-
            out['inputs'][0]['resolved_state'], atol=1e-13)
    assert out['vacuum'] == (operator != SOURCE_QUIESCENT)
    if operator == SOURCE_QUIESCENT:
        assert out['fluid']['density'] == density
        assert out['base']['fluid']['mean_velocity_body'] == [0., 0., 0.]


def test_retained_refinement_reuses_exact_matrices_and_rejects_policy_changes(monkeypatch):
    from openswing import frequency_response, frequency_sweep
    value = request()
    value['retain_frequency'] = True
    out = dispatch(value)
    session = out['frequency_session']
    analysis = frequency_sweep._active.analysis
    a, m = analysis.a, analysis.m
    def forbidden(*args, **kwargs):
        raise AssertionError('Refinement must reuse the loaded operator')
    monkeypatch.setattr(frequency_response, 'linearize', forbidden)
    monkeypatch.setattr(frequency_response, 'make_system', forbidden)
    refine = dict(action='extend_frequency', source=value['source'], numerics=value['numerics'],
        session=session, frequencies=[2., 4., 8.])
    refined = dispatch(refine)
    assert refined['frequency_refinement']['added_frequencies'] == [2., 8.]
    assert refined['frequency_refinement']['linearization_reused']
    assert analysis.a is a and analysis.m is m
    assert [s for s in refined['samples'] if s['omega'] in [1., 4., 9., 15.]] == out['samples']
    for operator in (SOURCE_DYNAMIC, SOURCE_QUIESCENT, 'midpoint-v1'):
        wrong = deepcopy(refine)
        wrong['numerics'] = dict(beam_interpolation='natural-v1' if operator == 'midpoint-v1' else 'drela-segspl-v1', structural_operator=operator)
        with pytest.raises(ValueError, match='session numerical policy'):
            dispatch(wrong)
    released = dispatch(dict(action='discard_frequency', session=session, numerics=value['numerics'], retain_model=True))
    assert released['released']
    again = dispatch(value)
    assert again['diagnostics']['loaded_matrices_reused']
    assert frequency_sweep._active.analysis.a is a
    dispatch(dict(action='discard_frequency', session=again['frequency_session'], numerics=value['numerics']))


@pytest.mark.parametrize('operator,change', [
    (SOURCE_DYNAMIC, {'frame': 'free'}),
    (SOURCE_QUIESCENT, {'quiescent_density': 0}),
    (SOURCE_MOVING, {'inputs': ['control.1']}),
    (SOURCE_MOVING, {'inputs': [dict(kind='gust')]}),
    (SOURCE_MOVING, {'controller': {}}),
    (SOURCE_MOVING, {'structural_operator': 'midpoint-v1'}),
])
def test_unsupported_source_frequency_physics_rejects_before_model_parse(operator, change):
    value = request(operator)
    value['source'] = 'intentionally not an ASW model'
    value['frequency'].update(change)
    with pytest.raises(ValueError):
        dispatch(value)
