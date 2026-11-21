"""Independent mechanics checks for the tensor comparison evidence."""
import copy
import importlib.util
import json
from pathlib import Path

import numpy as np
import pytest

from openswing.asw import parse_asw
from openswing.geometry import model_meshes

SPEC = importlib.util.spec_from_file_location('sa6_mass_math', 'scripts/isae_suite_sa6_mass_math.py')
MATH = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MATH)
PREFIX = '''Name
Tensor verification
End
Unit
L 1 m
T 1 s
F 1 N
End
Constant
9.81 1.2256 340.21
End
Reference
.3871 .254 1.524
End
'''


def plate(theta=4., weight=0.):
    ic, inn = (0., 0.) if weight == 0 else (.003, .004)
    return parse_asw(PREFIX+f'''Beam 1
Straight twisted plate
t y chord twist Xax mg mgcc mgnn Ccg Ncg
0 0 .254 {theta} 0 {weight} {ic} {inn} .03 .01
.762 .762 .254 {theta} 0 {weight} {ic} {inn} .03 .01
End
''')


def evidence(model=None, center=(0., 0., 0.), factor=1.):
    model = plate() if model is None else model
    return MATH.compute_tensor_evidence(model, model_meshes(model, 8), model.constants[1], center, factor)


def passed(value):
    checks = MATH.validate_tensor_evidence(value)
    assert checks and all(c['passed'] for c in checks), checks


@pytest.mark.parametrize('theta', [4., -27., 43.])
def test_twisted_plate_closed_form_with_actual_discrete_span_moments(theta):
    model = plate(theta)
    meshes = model_meshes(model, 8)
    result = MATH.compute_tensor_evidence(model, meshes, model.constants[1], [0, 0, 0])
    passed(result)
    angle = np.deg2rad(theta)
    c = np.array([np.cos(angle), 0., -np.sin(angle)])
    n = np.array([np.sin(angle), 0., np.cos(angle)])
    s = np.array([0., 1., 0.])
    length, chord, rho = 1.524, .254, 1.2256
    mu = rho*np.pi*chord**2/4
    j1 = sum(np.dot(m.length, m.rm[:, 1]) for m in meshes)
    j2 = sum(np.dot(m.length, m.rm[:, 1]**2) for m in meshes)
    expected_mass = mu*length*np.outer(n, n)
    expected_inertia = mu*(j2*np.outer(c, c)-chord/2*j1*(np.outer(c, s)+np.outer(s, c))
                            +length*9*chord**2/32*np.outer(s, s))
    matrix = np.asarray(result['tensors']['origin']['apparent_spatial_matrix'])
    np.testing.assert_allclose(matrix[:3, :3], expected_mass, atol=2e-16)
    np.testing.assert_allclose(matrix[3:, 3:], expected_inertia, atol=2e-17)
    assert result['physical_real_cg'] is None
    assert len(MATH.tensor_predictions(result)) == 33
    assert result['operations']['aerodynamic_calls'] == result['operations']['nonlinear_solves'] == 0
    assert result['operations']['tensor_reference_evaluations'] == 2
    assert result['operations']['real_matrix_assemblies'] == result['operations']['apparent_matrix_assemblies'] == 2
    # The archived convention can report a numeric reference without defining
    # a physical CG; no pseudoinverse of the rank-deficient mass tensor is used.
    np.testing.assert_array_equal(result['tensors']['origin']['apparent_spatial_matrix'],
                                  result['tensors']['reported_centroid']['apparent_spatial_matrix'])


def test_nonzero_real_mass_uses_physical_cg_and_distinct_report_reference():
    result = evidence(plate(31., 4.2), center=(.2, -.4, .3))
    passed(result)
    c = np.array([np.cos(np.deg2rad(31)), 0, -np.sin(np.deg2rad(31))])
    n = np.array([np.sin(np.deg2rad(31)), 0, np.cos(np.deg2rad(31))])
    np.testing.assert_allclose(result['physical_real_cg'], .03*c+.01*n, atol=1e-15)
    assert result['real_mass'] == pytest.approx(4.2*1.524/9.81)
    assert result['operations']['tensor_reference_evaluations'] == 3
    assert result['reported_centroid'] != result['physical_real_cg']


def test_body_transverse_energy_and_density_factor_binding():
    model = parse_asw(PREFIX+'''Beam 1
Oblique body
t x y z radius
0 0 0 0 .2
2 2 .4 -.3 .1
End
''')
    result = evidence(model, center=(-.2, .4, .7), factor=.7)
    passed(result)
    assert result['geometry']['nonlifting_beams'] == 1
    changed = copy.deepcopy(result)
    changed['body_added_mass_factor'] = .8
    assert not all(c['passed'] for c in MATH.validate_tensor_evidence(changed))


@pytest.fixture(scope='module')
def original():
    return evidence()


@pytest.mark.parametrize('corruption', [
    'density', 'normal', 'chord', 'arm', 'rotational_mass', 'empty_apparent',
    'origin_inertia_sign', 'coupling_sign', 'nan_matrix', 'invented_cg',
    'zero_probe', 'moved_report_reference', 'false_operations', 'false_assemblies',
])
def test_saved_evidence_detects_geometry_mapping_and_scope_corruption(original, corruption):
    value = copy.deepcopy(original)
    if corruption == 'density': value['density'] *= 1.1
    if corruption == 'normal': value['apparent_records'][0]['normal'][0] = [0., 0., 1.]
    if corruption == 'chord': value['geometry']['lifting_panels'][0]['chord'][0] *= 2
    if corruption == 'arm': value['apparent_records'][0]['position'][0][0] += .1
    if corruption == 'rotational_mass': value['apparent_records'][0]['rotational_mass'][0] *= 2
    if corruption == 'empty_apparent': value['apparent_records'] = []
    if corruption == 'origin_inertia_sign': value['tensors']['origin']['apparent_spatial_matrix'][3][3] *= -1
    if corruption == 'coupling_sign': value['tensors']['origin']['apparent_spatial_matrix'][2][4] *= -1
    if corruption == 'nan_matrix': value['tensors']['origin']['apparent_spatial_matrix'][2][2] = float('nan')
    if corruption == 'invented_cg': value['physical_real_cg'] = [0., 0., 0.]
    if corruption == 'zero_probe': value['tensors']['probe'] = copy.deepcopy(value['tensors']['origin'])
    if corruption == 'moved_report_reference': value['reported_centroid'][0] = .1
    if corruption == 'false_operations': value['operations']['nonlinear_solves'] = 1
    if corruption == 'false_assemblies': value['operations']['apparent_matrix_assemblies'] += 1
    checks = MATH.validate_tensor_evidence(value)
    assert any(not c['passed'] for c in checks), corruption


def test_json_roundtrip_preserves_tensors_and_massless_reference(original):
    saved = json.loads(json.dumps(original, allow_nan=False))
    passed(saved)
    assert MATH.tensor_predictions(saved) == MATH.tensor_predictions(original)
    assert saved['physical_real_cg'] is None


@pytest.mark.parametrize('density,center', [(float('nan'), [0, 0, 0]), (-1, [0, 0, 0]), (1., [0, 0])])
def test_invalid_physical_inputs_rejected(density, center):
    model = plate()
    with pytest.raises(ValueError):
        MATH.compute_tensor_evidence(model, model_meshes(model, 8), density, center)
