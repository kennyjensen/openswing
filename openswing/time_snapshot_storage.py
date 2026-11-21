"""Lossless browser history storage; native callers keep ordinary lists.

Only the latest report remains mutable during integration. Completed reports
are gzip-compressed separately, including every physical and restart field.
No time samples, precision or integration settings are changed.
"""
from collections.abc import Sequence
from contextlib import contextmanager
from contextvars import ContextVar
import gzip
import json

_browser_storage = ContextVar('browser_time_snapshot_storage', default=False)


@contextmanager
def browser_time_storage():
    token = _browser_storage.set(True)
    try:
        yield
    finally:
        _browser_storage.reset(token)


def snapshot_history(first):
    return SnapshotHistory(first) if _browser_storage.get() else [first]


class SnapshotHistory(Sequence):
    def __init__(self, first):
        self._records = []
        self._latest = first

    def __len__(self):
        return len(self._records) + (self._latest is not None)

    def _seal(self):
        if self._latest is not None:
            data = json.dumps(self._latest, allow_nan=False, separators=(',', ':')).encode('utf-8')
            self._records.append(gzip.compress(data, compresslevel=1, mtime=0))
            self._latest = None

    def append(self, snapshot):
        self._seal()
        self._latest = snapshot

    def __getitem__(self, index):
        if isinstance(index, slice):
            return [self[i] for i in range(*index.indices(len(self)))]
        if index < 0:
            index += len(self)
        if not 0 <= index < len(self):
            raise IndexError('Time snapshot index out of range.')
        if index == len(self._records):
            return self._latest
        return json.loads(gzip.decompress(self._records[index]))

    def take_compressed(self, index):
        """Transfer ownership after integration; release each sent record."""
        self._seal()
        data = self._records[index]
        self._records[index] = None
        return data

    @property
    def compressed_bytes(self):
        return sum(len(value) for value in self._records if value is not None)

    def close(self):
        self._records.clear()
        self._latest = None
