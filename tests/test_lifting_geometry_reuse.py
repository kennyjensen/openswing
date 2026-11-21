"""Exact geometry reuse, including changed material samples and rejection gates."""
from copy import copy
import numpy as np
import pytest
from openswing.frozen_influence import lifting_geometry
from openswing.tangent_influences import TangentInfluences
from openswing.network import StaticNetwork
from openswing.aero import FlightCondition
from test_direct_circulation import model_for, state_for


def cloned_meshes(meshes):
    # A mesh owns geometry arrays; its immutable beam/splines stay shared.
    # This also avoids trying to pickle SciPy's array module in WebAssembly.
    result = []
    for mesh in meshes:
        current = copy(mesh)
        for key, value in vars(mesh).items():
            if isinstance(value, np.ndarray): setattr(current, key, value.copy())
        result.append(current)
    return result


def assert_geometry(actual, expected):
    assert actual.keys() == expected.keys()
    for key in actual:
        assert actual[key].shape == expected[key].shape
        assert actual[key].dtype == expected[key].dtype
        np.testing.assert_array_equal(actual[key], expected[key], err_msg=key)
        # Numeric equality alone does not compare signed zero.
        assert actual[key].tobytes() == expected[key].tobytes(), key


def test_array_map_owns_exact_typed_keys_and_results():
    cache = TangentInfluences(local_geometry=True)
    base = np.arange(18, dtype=float).reshape(6, 3); calls = []
    def run(value):
        def compute():
            calls.append(1)
            return (value.copy(), value.sum(axis=1))
        result = cache.array_map('test', (value,), compute)
        np.testing.assert_array_equal(result[0], value)
        assert result[0].tobytes() == value.tobytes()
        result[0][:] = 900
        return result
    run(base); run(base)
    assert len(calls) == 1
    for changed in [base.copy(), base.astype(np.float32), base.reshape(3, 6), base[:2]]:
        if changed.shape == base.shape and changed.dtype == base.dtype: changed[0, 0] = -0.
        before = len(calls); run(changed)
        assert len(calls) == before+1
    # Only the original owned key is retained; caller edits cannot rewrite it.
    base[0, 0] = 3.; run(base); base[0, 0] = 0.
    before = len(calls); run(base); assert len(calls) == before
    for value in cache.array_maps['test'][1]:
        assert not value.flags.writeable and value.flags.owndata


def test_array_map_nonfinite_inputs_keep_physical_evaluation():
    for value in [np.nan, np.inf, -np.inf]:
        cache = TangentInfluences(local_geometry=True)
        a = np.array([value]); calls = []
        def compute():
            calls.append(1); return (a.copy(),)
        for _ in range(2):
            np.testing.assert_array_equal(cache.array_map('invalid', (a,), compute)[0], a)
        assert len(calls) == 2 and not cache.array_maps


@pytest.mark.parametrize('example', ['rectangular', 'flexible', 'wing-body', 'articulated', 'dae', 'stepped-body'])
def test_each_geometry_dependency_preserves_complete_uncached_values(example):
    n = StaticNetwork(model_for(example), 16, FlightCondition(mach=.2), None, [])
    x = state_for(n)
    r, q, *_ = n.unpack(x)
    meshes = n.deformed_meshes(r, q, n.geometry(r, q))
    wind = np.array([1., .17, -.09])
    cache = TangentInfluences(local_geometry=True)
    lifting_geometry(meshes, wind, _material=cache)
    rows = [m for m in meshes if m.beam.lifting]
    for change in ['base', 'r0', 'r1', 'rm', 'frame0', 'frame1', 'frames', 'direction',
                   'stations', 'length', 'all', 'missing-end-frames', 'float32', 'signed-zero', 'base']:
        current = cloned_meshes(meshes)
        direction = wind.copy()
        selected = next((m for m in current if m.beam.lifting), None)
        if change == 'direction': direction += [.03, -.01, .02]
        if selected is not None:
            for key in ['r0', 'r1', 'rm', 'frame0', 'frame1', 'frames']:
                if change in (key, 'all'): getattr(selected, key)[2] += .013
            if change == 'stations':
                selected.tm = (2*selected.t0+selected.t1)/3
            if change == 'length': selected.length[2] += .1
            if change == 'missing-end-frames': selected.frame0 = selected.frame1 = None
            if change == 'float32':
                for key in ['r0', 'r1', 'rm', 'frame0', 'frame1', 'frames']:
                    setattr(selected, key, getattr(selected, key).astype(np.float32))
                direction = direction.astype(np.float32)
            if change == 'signed-zero':
                selected.r0[2, 0] = -0.; direction[2] = -0.
        expected = lifting_geometry(current, direction)
        actual = lifting_geometry(current, direction, _material=cache)
        assert_geometry(actual, expected)
        # Returned arrays cannot overwrite retained values or the meshes.
        for value in actual.values(): value[:] = 97
        assert_geometry(lifting_geometry(current, direction, _material=cache), expected)
    if rows: assert any(key[0] == 'lifting_geometry' for key in cache.array_maps)
    assert cache.bytes <= 64*1024**2


def test_whole_surface_reuse_and_storage_fallback(monkeypatch):
    n = StaticNetwork(model_for('flexible'), 24, FlightCondition(), None, [])
    meshes = n.meshes; wind = np.array([1., .1, .03])
    cache = TangentInfluences(local_geometry=True)
    original = cache.array_map; work = []
    def counted(name, arrays, compute):
        def evaluate():
            work.append(len(arrays[0]))
            return compute()
        return original(name, arrays, evaluate)
    monkeypatch.setattr(cache, 'array_map', counted)
    reference = lifting_geometry(meshes, wind)
    assert_geometry(lifting_geometry(meshes, wind, _material=cache), reference)
    assert sum(work) == sum(len(m.tm) for m in meshes if m.beam.lifting)
    work.clear()
    assert_geometry(lifting_geometry(meshes, wind, _material=cache), reference)
    assert not work
    changed = cloned_meshes(meshes)
    m = next(m for m in changed if m.beam.lifting)
    m.r0[2, 0] += .01
    assert_geometry(lifting_geometry(changed, wind, _material=cache), lifting_geometry(changed, wind))
    assert work == [len(m.tm)]
    exhausted = TangentInfluences(local_geometry=True); exhausted.bytes = 64*1024**2
    assert_geometry(lifting_geometry(changed, wind, _material=exhausted), lifting_geometry(changed, wind))
    assert not exhausted.array_maps


@pytest.mark.parametrize('location', ['frames', 'frame0', 'frame1'])
def test_changed_wind_alignment_keeps_original_rejection(location):
    n = StaticNetwork(model_for('flexible'), 16, FlightCondition(), None, [])
    r, q, *_ = n.unpack(state_for(n))
    meshes = n.deformed_meshes(r, q, n.geometry(r, q))
    cache = TangentInfluences(local_geometry=True); wind = np.array([1., 0., 0.])
    lifting_geometry(meshes, wind, _material=cache)
    selected = next(m for m in meshes if m.beam.lifting)
    getattr(selected, location)[2, :, 1] = wind
    messages = []
    for material in (None, cache):
        try: lifting_geometry(meshes, wind, _material=material)
        except ValueError as exc: messages.append(str(exc))
        else: raise AssertionError('The original alignment rejection was bypassed')
    assert len(messages) == 2 and messages[0] == messages[1]


@pytest.mark.parametrize('example,extra', [('flexible', {'circulation_modes':{1:3}}),
    ('wing-body', {'ground_effect':1}), ('wing-body', {'ground_effect':-1}),
    ('wing-body', {'freeze_influences':True}), ('powered', {'powers':{1:7}})])
def test_complete_pencil_and_output_fields_equal_full_recomputation(example, extra, monkeypatch):
    from openswing.linear_dynamics import make_system, linearize
    import openswing.frozen_influence as module
    condition = FlightCondition(speed=20, alpha=3, mach=.1, position_earth=[0.,0.,30.], **extra)
    system, _ = make_system(model_for(example), condition, 4, structured_base=True)
    a, m = linearize(system, sparse=True, _output_fields=True)
    fields = system._output_field_tangent
    assert fields is not None and fields.active
    g = fields.matrix.copy()
    monkeypatch.setattr(TangentInfluences, 'array_map', lambda self, name, arrays, compute:compute())
    expected, mass = linearize(system, sparse=True, _output_fields=True)
    for value, reference in [(a, expected), (m, mass), (g, system._output_field_tangent.matrix)]:
        np.testing.assert_array_equal(value.toarray(), reference.toarray())
