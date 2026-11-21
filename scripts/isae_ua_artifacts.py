"""Bounded-memory, complete-or-partial persistence of UA validation trajectories."""
import gzip
import json
from pathlib import Path


def write_trajectory(path, result):
    """Use the C JSON encoder once per snapshot, preserving every field.

    json.dump's Python iterator makes millions of tiny writes for checkpointed
    histories. Encoding one snapshot at a time avoids that overhead without
    constructing a second full-history string. An interrupted file keeps the
    explicit .partial suffix; the final name is published only after gzip closes.
    """
    path = Path(path)
    partial = path.with_name(path.name+'.partial')
    if path.exists() or partial.exists():
        raise FileExistsError('Preserve existing trajectory evidence')
    def encode(value):
        return json.dumps(value,separators=(',',':'),allow_nan=False)
    with gzip.open(partial,'wt',compresslevel=1,encoding='utf-8') as stream:
        stream.write('{')
        for index,(key,value) in enumerate(result.items()):
            if index:
                stream.write(',')
            stream.write(encode(key)+':')
            if key == 'snapshots':
                stream.write('[')
                for ordinal,snapshot in enumerate(value):
                    if ordinal:
                        stream.write(',')
                    stream.write(encode(snapshot))
                stream.write(']')
            else:
                stream.write(encode(value))
        stream.write('}')
    partial.replace(path)
