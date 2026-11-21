"""Independent volume-field derivatives and complete coupled residual checks."""
from copy import deepcopy
from decimal import Decimal, localcontext
import math
from pathlib import Path
import numpy as np
import pytest
from openswing.volume import VolumeField
from openswing.volume_tangent import source_doublet_partials, VolumeFieldTangent, VolumeDerivativeUnavailable
from openswing.ground import GroundPlane
from openswing.network import StaticNetwork
from openswing.aero import FlightCondition
from test_direct_circulation import model_for


def decimal_velocity(d, s, m, core):
    r2 = sum(v*v for v in d); den = r2+core*core
    projection = sum(a*b for a, b in zip(m, d))
    return [(s*x/den+(u*r2-3*projection*x)/(den*den))/den.sqrt()/(4*Decimal.from_float(math.pi))
            for x, u in zip(d, m)]


def test_partials_against_110_digit_independent_differences():
    with localcontext() as context:
        context.prec = 110
        for core in [0., 1e-12, .13, 2.]:
            for d in [[.2, -.1, .4], [1e-12, -2e-12, 3e-12], [1e6, -.1, .3]]:
                source = .17; doublet = [-.3, .1, .2]
                actual = source_doublet_partials(d, source, doublet, core)
                base = [list(map(Decimal.from_float, d)), Decimal.from_float(source), list(map(Decimal.from_float, doublet))]
                for index, name in enumerate(['displacement', 'source', 'doublet']):
                    columns = []
                    for axis in range(1 if name == 'source' else 3):
                        step = Decimal('1e-30')
                        samples = []
                        for sign in [1, -1]:
                            args = deepcopy(base)
                            if name == 'source': args[index] += sign*step
                            else: args[index][axis] += sign*step
                            samples.append(decimal_velocity(*args, Decimal.from_float(core)))
                        columns.append([float((a-b)/(2*step)) for a, b in zip(*samples)])
                    expected = np.array(columns)[0] if name == 'source' else np.array(columns).T
                    np.testing.assert_allclose(actual[name], expected,
                        atol=3e-14*np.max(abs(expected)), rtol=2e-12, err_msg=str((core, d, name)))


def field_fixture(flag, example='wing-body'):
    model = model_for(example)
    n = StaticNetwork(model, 8, FlightCondition(mach=.3), None, [])
    volume = VolumeField(model, n.meshes, np.array([1., .13, -.04]),
        np.array([[1.2, .01, .03], [.01, 1.03, -.01], [.03, -.01, 1.02]]),
        ground=GroundPlane(flag, [0., 0., 20.], [10., 20., 30.]))
    points = np.random.default_rng(9401).normal(size=(11, 3))+[0., 0., 3.]
    return volume, points


@pytest.mark.parametrize('flag', [-1, 0, 1])
@pytest.mark.parametrize('exclusion', ['none', 'body', 'bodies', 'point', 'points', 'both'])
def test_retained_field_matches_complete_source_and_receiver_motion(flag, exclusion):
    volume, points = field_fixture(flag)
    options = {}
    if exclusion in ('body', 'bodies', 'both'):
        options['exclude_body'] = 2 if exclusion == 'body' else np.where(np.arange(len(points))%2, 2, -1)
    if exclusion in ('point', 'points', 'both'):
        options['exclude_point'] = 0 if exclusion == 'point' else np.where(np.arange(len(points))%2, 0, -1)
    tangent = VolumeFieldTangent(volume, points, **options)
    np.testing.assert_array_equal(tangent.value(volume, points), volume.velocity(points, **options))
    rng = np.random.default_rng(1803)
    for change in ['receivers', 'positions', 'sources', 'doublets', 'all']:
        directions = {name:np.zeros_like(value) for name, value in
            [('receivers', points), ('positions', volume.positions), ('sources', volume.sources), ('doublets', volume.doublets)]}
        for name in directions:
            if change in (name, 'all'):
                directions[name][1] = rng.normal(size=directions[name][1].shape)
        step = 1e-4; physical = []; retained = []
        for multiplier in [1., -1., 2., -2.]:
            current = deepcopy(volume); p = points+multiplier*step*directions['receivers']
            for name in ['positions', 'sources', 'doublets']:
                setattr(current, name, getattr(volume, name)+multiplier*step*directions[name])
            physical.append(current.velocity(p, **options)); retained.append(tangent.value(current, p))
        def fourth(v): return (8*(v[0]-v[1])-(v[2]-v[3]))/(12*step)
        np.testing.assert_allclose(fourth(retained), fourth(physical), atol=2e-11, rtol=2e-9)
    assert tangent.bytes < 128*1024**2
    for value in vars(tangent).values():
        if isinstance(value, np.ndarray): assert value.flags.owndata and not value.flags.writeable


def test_singular_excluded_sources_empty_queries_ownership_and_guards():
    volume, points = field_fixture(0)
    def rejected(function):
        try: function()
        except VolumeDerivativeUnavailable: return
        raise AssertionError('Unavailable derivative was not rejected')
    rejected(lambda: VolumeFieldTangent(volume, points, limit=1))
    tangent = VolumeFieldTangent(volume, points)
    for name in ['pg', 'cores', 'owners', 'points', 'is_image']:
        changed = deepcopy(volume)
        value = getattr(changed, name)
        value.flat[0] = not value.flat[0] if name == 'is_image' else value.flat[0]+.1 if value.dtype.kind == 'f' else value.flat[0]+1
        rejected(lambda: tangent.value(changed, points))
    rejected(lambda: tangent.value(volume, points[:1]))
    rejected(lambda: source_doublet_partials(np.zeros(3), 1., np.ones(3)))
    # A permanently excluded source remains harmless at zero core/coincidence.
    volume.cores[0] = 0.
    coincident = (volume.positions[:1]@np.linalg.inv(volume.pg).T).copy()
    # PG roundoff can prevent exact coincidence; use identity for this check.
    volume.pg = np.eye(3); coincident = volume.positions[:1].copy()
    rejected(lambda: VolumeFieldTangent(volume, coincident))
    excluded = VolumeFieldTangent(volume, coincident, exclude_body=volume.owners[:1])
    np.testing.assert_array_equal(excluded.value(volume, coincident), volume.velocity(coincident, exclude_body=volume.owners[:1]))
    empty = points[:0].copy(); no_receivers = VolumeFieldTangent(volume, empty)
    np.testing.assert_array_equal(no_receivers.value(volume, empty), volume.velocity(empty))
    empty_volume, points = field_fixture(0, 'rectangular')
    no_sources = VolumeFieldTangent(empty_volume, points)
    np.testing.assert_array_equal(no_sources.value(empty_volume, points), empty_volume.velocity(points))


from test_geometry_tangent import CASES


@pytest.mark.parametrize('example,frame,extra,circulation', CASES)
def test_complete_coupled_columns_with_both_retained_maps(example, frame, extra, circulation, monkeypatch):
    import test_geometry_tangent as reference
    original = reference.geometry_columns
    def retained(*args, **kwargs):
        result, diagnostics = original(*args, **kwargs, _direct_vortex=True, _direct_volume=True)
        assert diagnostics['direct_vortex_bytes']+diagnostics['direct_volume_bytes'] <= 128*1024**2
        if not extra.get('freeze_influences'): assert diagnostics['direct_volume_queries'] > 0
        return result, diagnostics
    monkeypatch.setattr(reference, 'geometry_columns', retained)
    reference.test_complete_geometry_columns_match_refined_full_residual(example, frame, extra, circulation)


def test_storage_limit_keeps_complete_physical_stencils(monkeypatch):
    import openswing.volume_tangent as volume_module
    from openswing.geometry_tangent import geometry_columns
    from openswing.linear_dynamics import DynamicSystem
    from test_direct_circulation import state_for
    n = StaticNetwork(model_for('wing-body'), 4, FlightCondition(speed=30, alpha=7, mach=.2), None, [])
    s = DynamicSystem(n, state_for(n), 'fixed'); zero = np.zeros(s.size)
    scales = np.r_[np.maximum(1., abs(s.base)), np.ones(s.size-n.size)]
    def assemble(direct):
        return geometry_columns(n, lambda d:s.residual(d, zero), lambda d:s.unpack(d, zero)[0].x,
                                scales, _direct_vortex=True, _direct_volume=direct)
    expected, _ = assemble(False)
    original = volume_module.VolumeFieldTangent
    def limited(*args, **kwargs):
        kwargs['limit'] = 1
        return original(*args, **kwargs)
    monkeypatch.setattr(volume_module, 'VolumeFieldTangent', limited)
    actual, diagnostics = assemble(True)
    np.testing.assert_array_equal(actual.toarray(), expected.toarray())
    assert diagnostics['direct_volume_queries'] == diagnostics['direct_volume_bytes'] == 0
    assert diagnostics['direct_volume_fallbacks']
    assert all('budget' in reason for reason in diagnostics['direct_volume_fallbacks'].values())
    assert diagnostics['direct_vortex_queries'] > 0
