"""Derivative-local cache ownership, cleanup and conservative fallbacks."""
from copy import copy
from types import SimpleNamespace

import pytest

from openswing.derivative_cache import DerivativeTangentCache, derivative_probe_cache


def network():
    return SimpleNamespace(iteration_fields=None, tangent_influences=None,
        _tangent_loads=None, aero_key=object(), aero_cached=object())


@pytest.mark.parametrize('fail', [False, True])
def test_probe_cache_preserves_parent_and_clears_trial_fields(fail):
    parent = network()
    before = vars(parent).copy()
    probe, report = copy(parent), {}
    failure = RuntimeError('probe failed')
    try:
        with derivative_probe_cache(probe, response='fixed_acceleration', feedback=None, report=report):
            assert isinstance(probe.tangent_influences, DerivativeTangentCache)
            assert probe.iteration_fields is None and probe._tangent_loads is None
            assert probe.aero_key is None and probe.aero_cached is None
            probe.aero_key, probe.aero_cached = object(), object()
            if fail:
                raise failure
    except RuntimeError as error:
        assert fail and error is failure
    else:
        assert not fail
    assert vars(parent) == before
    assert probe.tangent_influences is None
    assert probe.aero_key is None and probe.aero_cached is None
    assert report['enabled'] and report['owner_restored']


@pytest.mark.parametrize('response,feedback,owner', [
    ('free_flight', None, None),
    ('fixed_acceleration', object(), None),
    ('fixed_acceleration', None, 'iteration_fields'),
    ('fixed_acceleration', None, 'tangent_influences'),
    ('fixed_acceleration', None, '_tangent_loads'),
])
def test_unsupported_or_nested_context_keeps_existing_owners(response, feedback, owner):
    probe, report = network(), {}
    if owner:
        setattr(probe, owner, object())
    before = vars(probe).copy()
    with derivative_probe_cache(probe, response=response, feedback=feedback, report=report):
        assert vars(probe) == before
    assert vars(probe) == before
    assert not report['enabled'] and report['fallback_reasons']
