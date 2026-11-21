"""ST-2 plan-local sharing must never accept stale production source bytes."""
from copy import deepcopy
import hashlib
import os
from pathlib import Path

import pytest

from scripts import isae_suite_st2 as st2


def sources(root):
    folder = root/'openswing'
    folder.mkdir()
    (folder/'a.py').write_text('old=1\n')
    (folder/'b.py').write_text('old=2\n')
    return folder


def test_one_snapshot_and_one_final_rehash_per_plan_with_no_cross_call_cache(tmp_path, monkeypatch):
    folder = sources(tmp_path)
    paths = []
    pin = st2._pin
    def observed(path):
        paths.append(Path(path).name)
        return pin(path)
    def record(root, spec, *, kernel_pins):
        return dict(spec=spec, kernel_pins=deepcopy(kernel_pins))
    monkeypatch.setattr(st2, '_pin', observed)
    monkeypatch.setattr(st2, '_make_record', record)
    first = st2._build_records(tmp_path, list(range(8)))
    assert paths == ['a.py', 'b.py']*2
    first[0]['kernel_pins'][0]['sha256'] = 'changed result'
    assert first[1]['kernel_pins'][0]['sha256'] == hashlib.sha256(b'old=1\n').hexdigest()
    stamp = (folder/'a.py').stat()
    (folder/'a.py').write_text('new=1\n')
    os.utime(folder/'a.py', ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
    paths.clear()
    second = st2._build_records(tmp_path, list(range(8)))
    assert paths == ['a.py', 'b.py']*2
    assert second[0]['kernel_pins'][0]['sha256'] == hashlib.sha256(b'new=1\n').hexdigest()


@pytest.mark.parametrize('change', ['same_size_and_mtime', 'add', 'remove', 'retarget_symlink'])
def test_source_changes_during_registration_reject_the_complete_plan(tmp_path, monkeypatch, change):
    folder = sources(tmp_path)
    if change == 'retarget_symlink':
        (tmp_path/'first').write_text('first\n')
        (tmp_path/'other').write_text('other\n')
        (folder/'a.py').unlink()
        (folder/'a.py').symlink_to(tmp_path/'first')
    def record(root, spec, *, kernel_pins):
        if spec == 0:
            if change == 'same_size_and_mtime':
                stamp = (folder/'a.py').stat()
                (folder/'a.py').write_text('new=1\n')
                os.utime(folder/'a.py', ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
            elif change == 'add':
                (folder/'c.py').write_text('extra=1\n')
            elif change == 'remove':
                (folder/'b.py').unlink()
            else:
                (folder/'a.py').unlink()
                (folder/'a.py').symlink_to(tmp_path/'other')
        return dict(spec=spec, kernel_pins=deepcopy(kernel_pins))
    monkeypatch.setattr(st2, '_make_record', record)
    with pytest.raises(ValueError, match='production sources changed during registration'):
        st2._build_records(tmp_path, [0, 1])


def test_failed_registration_leaves_no_cached_snapshot(tmp_path, monkeypatch):
    folder = sources(tmp_path)
    def record(root, spec, *, kernel_pins):
        raise ValueError('invalid source input')
    monkeypatch.setattr(st2, '_make_record', record)
    with pytest.raises(ValueError, match='invalid source input'):
        st2._build_records(tmp_path, [0])
    (folder/'a.py').write_text('changed=1\n')
    monkeypatch.setattr(st2, '_make_record',
                        lambda root, spec, *, kernel_pins: dict(kernel_pins=deepcopy(kernel_pins)))
    jobs = st2._build_records(tmp_path, [0])
    assert jobs[0]['kernel_pins'][0]['sha256'] == hashlib.sha256(b'changed=1\n').hexdigest()
