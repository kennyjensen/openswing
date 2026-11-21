"""Exact wire round trips; no equation or tolerance changes are involved."""
from copy import deepcopy
from pathlib import Path
import json
import math
import pytest
from openswing.time_result_storage import pack_time_result, unpack_time_result


def encode(value):
    return json.dumps(value, allow_nan=False, separators=(',', ':'))


@pytest.mark.parametrize('name', [
    'tests/inverse_history/radau/inputs/step-checkpoint.json',
    'tests/inverse_history/radau/inputs/initial-checkpoint.json',
    'tests/inverse_history/events/inputs/left-checkpoint.json',
    'tests/inverse_history/events/inputs/right-checkpoint.json',
    'tests/inverse_history/spline/inputs/legacy-linear-checkpoint.json',
    'tests/inverse_history/saved/position/initial-checkpoint.json',
])
def test_saved_checkpoint_metadata_survives_exact_wire_round_trip(name):
    saved = json.loads(Path(name).read_text())
    record = {k: v for k, v in saved.items() if k not in ('format', 'context')}
    result = dict(analysis='time_response', restart_context=saved['context'],
                  snapshots=[dict(time=saved['state']['time'], restart=record)])
    before = encode(result)
    packet = pack_time_result(result)
    assert encode(result) == before  # Packing never edits the public result.
    restored = unpack_time_result(json.loads(encode(packet)))
    assert encode(restored) == before


def test_internal_midpoints_same_time_events_and_signed_zero_are_not_coalesced():
    def state(time, value):
        return dict(time=time, network=dict(positions=[[value, 0., 0.]] * 30),
                    hinge_charts=[6.3], commands={'F1': value})
    before, after = state(.2, -0.), state(.2, 0.)
    midpoint = state(.19, 1.)  # Internal adaptive midpoint, not a public snapshot.
    options = dict(charts=[1.] * 50, flag=True)
    restart = dict(state=after, older=midpoint, options=options, accepted_method=dict(
        previous=midpoint, previous2=before, scheme='old-scheme',
        endpoint=dict(state=deepcopy(after), options=deepcopy(options))))
    result = dict(analysis='time_response', snapshots=[dict(time=.2, restart=dict(state=before)),
        dict(time=.2, restart=restart)])
    reference = encode(result)
    restored = unpack_time_result(json.loads(encode(pack_time_result(result))))
    assert encode(restored) == reference
    a, b = [s['restart'] for s in restored['snapshots']]
    assert a['state'] is not b['state']
    assert math.copysign(1., a['state']['commands']['F1']) == -1
    assert math.copysign(1., b['state']['commands']['F1']) == 1
    assert b['older'] is b['accepted_method']['previous']
    assert b['state'] is b['accepted_method']['endpoint']['state']
    assert b['accepted_method']['scheme'] == 'old-scheme'
    assert 'nonlinear_policy' not in b['accepted_method']


def test_browser_opt_in_preserves_default_boundary_and_reports_output_stage(monkeypatch):
    from openswing import bridge
    value = dict(analysis='time_response', end_time=.1,
        snapshots=[dict(restart=dict(state=dict(data=[1.] * 100)))])
    monkeypatch.setattr(bridge, 'dispatch', lambda request, progress: value)
    assert bridge.run_json('{}') == json.dumps(value, allow_nan=False)
    events = []
    wire = json.loads(bridge.run_json('{}', lambda *args: events.append(args), compact_time=True))
    assert wire['format'] == 'openswing-time-result'
    assert unpack_time_result(wire) == value
    assert events == [('time_reporting', .1, 1)]
    # Opt-in does not alter non-time result serialization or emit time progress.
    value = dict(analysis='mounted_static', nodes=[])
    events.clear()
    assert bridge.run_json('{}', lambda *args: events.append(args), compact_time=True) == json.dumps(value, allow_nan=False)
    assert not events


@pytest.mark.parametrize('modify', [
    lambda p: p.update(version=True),
    lambda p: p['references'][0].__setitem__(1, True),
    lambda p: p['references'][0].__setitem__(1, -1),
    lambda p: p['references'][0].__setitem__(0, ['snapshots', 10, 'restart', 'state']),
    lambda p: p['references'][0].__setitem__(0, ['__proto__']),
    lambda p: p['references'].append(deepcopy(p['references'][0])),
])
def test_malformed_references_fail_before_any_writes(modify):
    packet = pack_time_result(dict(analysis='time_response',
        snapshots=[dict(restart=dict(state=dict(data=[1.] * 100)))]))
    modify(packet)
    before = encode(packet)
    with pytest.raises(ValueError, match='Invalid compact time result'):
        unpack_time_result(packet)
    assert encode(packet) == before
