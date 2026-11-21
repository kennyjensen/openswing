"""Bounded JSON records for the browser, without changing result values.

Frequency samples and compressed time reports travel separately. The owning
array keeps each byte range alive until JavaScript copies or decodes it. Its
address is a Python integer, avoiding signed wasm32 pointers in getBuffer.
"""
from array import array
import json
from .time_snapshot_storage import SnapshotHistory


class WorkerBytes:
    def __init__(self, value):
        self._data = array('B', json.dumps(value, allow_nan=False).encode('utf-8'))
        self.address, self.byte_length = self._data.buffer_info()

    @classmethod
    def compressed(cls, data):
        record = cls.__new__(cls)
        record._data = array('B', data)
        record.address, record.byte_length = record._data.buffer_info()
        return record


class WorkerReply:
    def __init__(self, reply):
        self._reply = reply
        result = reply.get('result')
        self._samples = (result['samples'] if isinstance(result, dict)
                         and result.get('analysis') == 'frequency_response' else None)
        self._history = result.get('snapshots') if isinstance(result, dict) else None
        if not isinstance(self._history, SnapshotHistory):
            self._history = None
        self.part_count = 1 + (len(self._history) if self._history is not None
                               else len(self._samples) if self._samples is not None else 0)
        self._index = 0

    def next_part(self):
        if self._index >= self.part_count or self._reply is None:
            return None
        index = self._index
        self._index += 1
        if index == 0:
            value = self._reply
            if self._history is not None:
                value = dict(result={k: v for k, v in self._reply['result'].items() if k != 'snapshots'},
                             snapshot_count=len(self._history), snapshot_encoding='gzip-json-v1')
            elif self._samples is not None:
                value = dict(result={**self._reply['result'], 'samples': []},
                             sample_count=len(self._samples))
        else:
            if self._history is not None:
                return WorkerBytes.compressed(self._history.take_compressed(index - 1))
            value = dict(sample=self._samples[index - 1])
        return WorkerBytes(value)

    def close(self):
        if self._history is not None:
            self._history.close()
        self._history = None
        self._reply = self._samples = None
