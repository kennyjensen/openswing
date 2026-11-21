from field_product_assertions import operators_close
"""Shared source changes preserve every receiver map and all physical guards."""
from copy import deepcopy
import numpy as np
import pytest
from openswing.volume_tangent import VolumeFieldTangent, VolumeSourceTangent, VolumeDerivativeUnavailable
from test_volume_tangent import field_fixture


def equal(actual, expected):
    np.testing.assert_array_equal(actual, expected)
    assert actual.dtype == expected.dtype and actual.tobytes() == expected.tobytes()


@pytest.mark.parametrize('flag', [-1, 0, 1])
@pytest.mark.parametrize('exclusion', ['none', 'body', 'bodies', 'point', 'points', 'both'])
def test_shared_changes_equal_separate_queries(flag, exclusion):
    volume, points = field_fixture(flag)
    options = {}
    if exclusion in ('body', 'bodies', 'both'):
        options['exclude_body'] = 2 if exclusion == 'body' else np.where(np.arange(len(points))%2, 2, -1)
    if exclusion in ('point', 'points', 'both'):
        options['exclude_point'] = 0 if exclusion == 'point' else np.where(np.arange(len(points))%2, 0, -1)
    source = VolumeSourceTangent(volume)
    shared = VolumeFieldTangent(volume, points, _source=source, **options)
    separate = VolumeFieldTangent(volume, points, **options)
    rng = np.random.default_rng(8214)
    current = deepcopy(volume)
    for change in ['base', 'receivers', 'positions', 'sources', 'doublets', 'all', 'base']:
        p = points.copy()
        for name in ['positions', 'sources', 'doublets']:
            value = getattr(volume, name).copy()
            if change in (name, 'all'): value[::3] += rng.normal(size=value[::3].shape)*1e-4
            setattr(current, name, value)
        if change in ('receivers', 'all'): p[::2] += rng.normal(size=p[::2].shape)*1e-4
        delta = source.difference(current)
        equal(shared.value(current, p, _change=delta), separate.value(current, p))
        for array in (delta.positions, delta.strength, delta.doublets, delta.changed):
            assert array.flags.owndata and not array.flags.writeable
    assert source.bytes == sum(getattr(source, name).nbytes for name in source.names)
    for name in source.names:
        value = getattr(source, name)
        assert value.flags.owndata and not value.flags.writeable
        assert not np.shares_memory(value, getattr(volume, name))
    # A different perturbation of the very same volume object gets a fresh delta.
    current.positions[1] += .02
    equal(shared.value(current, points, _change=source.difference(current)), separate.value(current, points))


def test_shared_source_guards_and_owned_baseline():
    volume, points = field_fixture(1)
    source = VolumeSourceTangent(volume)
    tangent = VolumeFieldTangent(volume, points, _source=source)
    def rejected(fn):
        try:fn()
        except VolumeDerivativeUnavailable:return
        raise AssertionError('Invalid shared source context was accepted')
    rejected(lambda: VolumeSourceTangent(volume, limit=1))
    for name in source.names[:5]:
        current = deepcopy(volume); value = getattr(current, name)
        value.flat[0] = not value.flat[0] if value.dtype.kind == 'b' else value.flat[0]+1
        rejected(lambda:source.difference(current))
    for name in source.names[5:]:
        current = deepcopy(volume);setattr(current, name, getattr(current, name)[:-1])
        rejected(lambda:source.difference(current))
    other = VolumeSourceTangent(volume)
    rejected(lambda:tangent.value(volume, points, _change=other.difference(volume)))
    rejected(lambda:tangent.value(deepcopy(volume), points, _change=source.difference(volume)))
    rejected(lambda:VolumeFieldTangent(volume, points).value(volume, points, _change=source.difference(volume)))
    rejected(lambda:tangent.value(volume, points[:1], _change=source.difference(volume)))
    volume.positions[0, 0] += .1
    rejected(lambda:VolumeFieldTangent(volume, points, _source=source))
    assert source.positions[0, 0] != volume.positions[0, 0]
    for bad in (np.inf, -np.inf, np.nan):
        current=deepcopy(volume);current.sources[0]=bad
        rejected(lambda:VolumeSourceTangent(current))


def test_empty_receivers_sources_and_live_shoulders():
    for example in ['rectangular', 'stepped-body', 'wing-body']:
        volume, points = field_fixture(0, example)
        for p in [points, points[:0]]:
            source=VolumeSourceTangent(volume)
            shared=VolumeFieldTangent(volume,p,_source=source)
            separate=VolumeFieldTangent(volume,p)
            current=deepcopy(volume)
            for entry in current.shoulders:entry['position_pg'] += [.03,-.01,.02]
            equal(shared.value(current,p,_change=source.difference(current)), separate.value(current,p))


@pytest.mark.parametrize('example,extra', [('flexible', {'circulation_modes':{1:3}}),
    ('wing-body', {'ground_effect':1}), ('wing-body', {'ground_effect':-1}),
    ('wing-body', {'freeze_influences':True}), ('powered', {'powers':{1:7}})])
def test_complete_operators_equal_separate_source_calculations(example, extra, monkeypatch):
    from openswing.aero import FlightCondition
    from openswing.linear_dynamics import make_system, linearize
    import openswing.volume_tangent as module
    from test_direct_circulation import model_for
    condition=FlightCondition(speed=20,alpha=3,mach=.1,position_earth=[0.,0.,30.],**extra)
    system,_=make_system(model_for(example),condition,4,structured_base=True)
    a,m=linearize(system,sparse=True,_output_fields=True)
    g=system._output_field_tangent.matrix.copy()
    def unavailable(*args,**kwargs):raise VolumeDerivativeUnavailable('Shared source storage unavailable')
    monkeypatch.setattr(module,'VolumeSourceTangent',unavailable)
    expected,mass=linearize(system,sparse=True,_output_fields=True)
    for name,actual,reference in [('A',a,expected),('M',m,mass),('G',g,system._output_field_tangent.matrix)]:
        operators_close(actual,reference,6*system.network.nn,mass=name=='M')


def test_one_source_change_per_field_and_complete_budget_accounting(monkeypatch):
    from openswing.aero import FlightCondition
    from openswing.network import StaticNetwork
    from openswing.structured_static import linearization
    from openswing.geometry_tangent import GeometryFields
    from test_direct_circulation import model_for,state_for
    n=StaticNetwork(model_for('wing-body'),8,FlightCondition(mach=.2,alpha=7,beta=3),None,[])
    x=state_for(n,.3);calls=[]
    original=VolumeSourceTangent.difference
    def counted(self,volume):calls.append(1);return original(self,volume)
    monkeypatch.setattr(VolumeSourceTangent,'difference',counted)
    with linearization(n,x,.6,capture_circulation=True) as (fields,baseline):
        evaluator=GeometryFields(n,fields,direct_vortex=True,direct_volume=True)
        for offset in [0.,1e-5,-1e-5]:
            current=x.copy();current[0]+=offset;evaluator(current)
            assert len(calls)==evaluator.evaluations
        assert len(evaluator.direct_volume)>1
        assert evaluator.direct_volume_bytes == evaluator.volume_sources.bytes+sum(
            t.bytes for t in evaluator.direct_volume.values() if t is not None)
        assert evaluator.direct_volume_bytes+evaluator.direct_vortex_bytes<=128*1024**2
        assert all(t._source is evaluator.volume_sources for t in evaluator.direct_volume.values() if t is not None)
