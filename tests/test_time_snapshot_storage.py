"""Bounded history checks using saved reports, without running the solver."""
import ctypes
from copy import deepcopy
import gzip
import json
from pathlib import Path

import pytest
from openswing import bridge
from openswing.time_snapshot_storage import SnapshotHistory, browser_time_storage, snapshot_history
from openswing.worker_transport import WorkerReply


def encoded(value):
    return json.dumps(value, allow_nan=False, separators=(',', ':'))


def test_latest_report_stays_mutable_and_events_and_restart_history_survive():
    original = json.loads(Path('tests/fixtures/source-moving-time-browser-result.json').read_text())
    reports = deepcopy(original['snapshots'])
    reports[1]['time'] = reports[0]['time']  # Distinct left/right states at one time.
    reports[0]['signed_zero'] = -0.
    reports[1]['signed_zero'] = 0.
    history = SnapshotHistory(reports[0])
    for snapshot in reports[1:]:
        history[-1]['late_restart_field'] = dict(value=1e-100)
        history.append(snapshot)
    assert len(history) == len(reports)
    assert history[-1] is reports[-1]
    assert encoded(list(history)) == encoded(reports)
    assert encoded(history[:2]) == encoded(reports[:2])
    with pytest.raises(IndexError):
        history[len(history)]


def test_worker_storage_is_scoped_and_native_results_remain_lists(monkeypatch):
    def dispatch(request, progress):
        history = snapshot_history(dict(time=0., restart=dict(value=-0.)))
        history.append(dict(time=.01, restart=dict(value=1e-100)))
        return dict(analysis='time_response', end_time=.01, snapshots=history)
    monkeypatch.setattr(bridge, 'dispatch', dispatch)
    assert isinstance(snapshot_history({}), list)
    assert isinstance(json.loads(bridge.run_json('{}'))['snapshots'], list)
    packet = bridge.run_worker_parts('{}')
    try:
        assert packet.part_count == 3
        header = packet.next_part()
        value = json.loads(ctypes.string_at(header.address, header.byte_length))
        assert value['snapshot_encoding'] == 'gzip-json-v1'
        assert value['snapshot_count'] == 2 and 'snapshots' not in value['result']
        for time in [0., .01]:
            part = packet.next_part()
            snapshot = json.loads(gzip.decompress(ctypes.string_at(part.address, part.byte_length)))
            assert snapshot['time'] == time
        assert packet.next_part() is None
    finally:
        packet.close()
    assert isinstance(snapshot_history({}), list)
    with pytest.raises(RuntimeError):
        with browser_time_storage():
            raise RuntimeError('cancelled')
    assert isinstance(snapshot_history({}), list)


def test_1001_reports_keep_one_expanded_state_and_transfer_every_record():
    template = json.loads(Path('tests/fixtures/source-moving-time-browser-result.json').read_text())['snapshots'][-1]
    history = None
    plain_bytes = 0
    for index in range(1001):
        snapshot = deepcopy(template)
        snapshot['time'] = index*.01
        snapshot['signed_zero'] = -0. if index%2 else 0.
        plain_bytes += len(encoded(snapshot).encode())
        if history is None:
            history = SnapshotHistory(snapshot)
        else:
            history.append(snapshot)
    assert len(history) == 1001
    assert all(isinstance(row, bytes) for row in history._records)
    assert isinstance(history._latest, dict)
    assert history.compressed_bytes < plain_bytes / 4
    packet = WorkerReply(dict(result=dict(analysis='time_response', snapshots=history)))
    try:
        assert packet.part_count == 1002
        packet.next_part()
        for index in range(1001):
            part = packet.next_part()
            snapshot = json.loads(gzip.decompress(ctypes.string_at(part.address, part.byte_length)))
            expected = {**template, 'time':index*.01, 'signed_zero':-0. if index%2 else 0.}
            assert encoded(snapshot) == encoded(expected)
            assert history._records[index] is None
        assert history.compressed_bytes == 0
    finally:
        packet.close()
    assert len(history) == 0


def test_invalid_numbers_fail_without_silently_dropping_a_report():
    history = SnapshotHistory(dict(time=0., value=float('nan')))
    with pytest.raises(ValueError, match='Out of range'):
        history.append(dict(time=1.))
    assert len(history) == 1
