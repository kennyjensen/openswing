"""Worker transfer preserves every field; fixtures require no numerical solve."""
import ctypes
import json
from pathlib import Path
import pytest
from openswing import bridge
from openswing.aero import AnalysisError
from openswing.worker_transport import WorkerReply


def read(reply):
    parts = []
    try:
        for _ in range(reply.part_count):
            part = reply.next_part()
            parts.append(json.loads(ctypes.string_at(part.address, part.byte_length)))
        assert reply.next_part() is None
    finally:
        reply.close()
    assert reply.next_part() is None
    header = parts[0]
    if 'sample_count' in header:
        assert header.pop('sample_count') == len(parts)-1
        header['result']['samples'] = [p['sample'] for p in parts[1:]]
    return header


@pytest.mark.parametrize('frame', ['fixed', 'free'])
def test_recorded_daedalus_all_outputs_round_trip_exactly(frame, monkeypatch):
    value = json.loads(Path('tests/data/daedalus-frame-response.json').read_text())['results'][frame]
    before = json.dumps(value, allow_nan=False)
    calls = []
    def dispatch(request, progress, *, _copy_frequency_result=True):
        assert _copy_frequency_result is False
        calls.append(request)
        return value
    monkeypatch.setattr(bridge, 'dispatch', dispatch)
    packet = bridge.run_worker_parts('{"action":"frequency"}')
    assert calls == [dict(action='frequency')]  # Solve precedes transfer, once.
    assert packet.part_count == len(value['samples'])+1
    assert json.dumps(read(packet)['result'], allow_nan=False) == before
    assert json.dumps(value, allow_nan=False) == before


def test_gaps_empty_grid_unicode_and_signed_zero():
    for samples in [[], [dict(omega=-0., converged=False, error='Γ · unavailable')]]:
        result = dict(analysis='frequency_response', samples=samples, unknown=dict(real=-0., imag=1e-100))
        assert json.dumps(read(WorkerReply(dict(result=result)))) == json.dumps(dict(result=result))


def test_nonfrequency_envelopes_errors_and_compact_time_are_preserved(monkeypatch):
    for value in [[], [dict(variable='alpha')], dict(analysis='steady', value=-0.),
                  dict(analysis='time_response', end_time=.1, snapshots=[dict(time=.1)])]:
        monkeypatch.setattr(bridge, 'dispatch', lambda request, progress: value)
        assert read(bridge.run_worker_parts('{}')) == json.loads(bridge.run_worker_json('{}'))
    def reject(request, progress):
        raise AnalysisError('Rejected section', details=dict(normal_mach=1.1))
    monkeypatch.setattr(bridge, 'dispatch', reject)
    assert read(bridge.run_worker_parts('{}')) == json.loads(bridge.run_worker_json('{}'))
    with pytest.raises(json.JSONDecodeError):
        bridge.run_worker_parts('{invalid')


def test_nonfinite_values_still_reject_transfer():
    reply = WorkerReply(dict(result=dict(analysis='frequency_response', samples=[dict(value=float('nan'))])))
    try:
        assert reply.next_part() is not None
        with pytest.raises(ValueError, match='Out of range'):
            reply.next_part()
    finally:
        reply.close()


def test_borrowed_sweep_header_and_refinement_preserve_old_records_and_native_ownership():
    from types import SimpleNamespace
    from openswing.frequency_sweep import FrequencySweep
    value = json.loads(Path('tests/data/daedalus-frame-response.json').read_text())['results']['free']
    value['frequency_refinement'] = dict(revision=0)
    sweep = FrequencySweep.__new__(FrequencySweep)
    sweep.result = value
    before = json.dumps(value)
    borrowed = sweep.report(_copy=False)
    assert borrowed is not value and borrowed['samples'] is value['samples']
    borrowed['transport_metadata'] = True
    assert 'transport_metadata' not in value
    addition = dict(omega=1000., converged=False, responses=[], error='reference gap')
    sweep.analysis = SimpleNamespace(solve=lambda *args: dict(samples=[addition]))
    refined = sweep.extend([1000.], _copy_result=False)
    assert refined['samples'] is sweep.result['samples']
    assert refined['samples'][0] is value['samples'][0]
    assert refined['base'] is value['base']
    assert json.dumps(value) == before
    assert read(WorkerReply(dict(result=borrowed)))['result'] == borrowed
    native = sweep.report()
    native['samples'][0]['omega'] = -999.
    native['base']['changed_by_caller'] = True
    assert sweep.result['samples'][0]['omega'] != -999.
    assert 'changed_by_caller' not in sweep.result['base']
