"""Portable reference arrays: explicit JSON descriptors and non-pickle NPZ.

Complex scalars are stored as zero-dimensional arrays. This preserves the
complex-step control input that stopped the original study's first serializer.
Loading these files performs no model construction or numerical evaluation.
"""
import hashlib
import json
from pathlib import Path

import numpy as np


STUDY_HISTORY = {
    'initial_attempt': 'The first subdivision-1 run stopped after its steady '
        'Gamma solve and three aerodynamic outputs because a complex control '
        'scalar was not JSON serializable. All three NPZ packets were retained.',
    'accepted_continuation': 'The corrected study reused the exact saved Gamma '
        'and three output packets, with full stored-input equality guards. The '
        'missing third scalar control was explicitly reconstructed as 0j from '
        'the frozen first-q-column loop. No completed output was reevaluated.',
    'partial_accounting': 'The original incomplete variant reported zero field '
        'work; saved evidence establishes two field sets, six field integrations. '
        'That reporting failure remains separate from numerical acceptance.',
    'portable_reproduction': 'A new invocation computes one fresh loaded rod '
        'base, one Green map and one Gamma base, then the three declared '
        'quadrature/complex-step variants. It does not need or silently replay '
        'the historical staging directories.',
}


def pin(path):
    value = Path(path).read_bytes()
    return {'bytes': len(value), 'sha256': hashlib.sha256(value).hexdigest()}


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False)+'\n')


def save_tree(path, value):
    """Save arrays before metadata; preserve a partial NPZ if metadata fails."""
    arrays = {}

    def pack(item, key):
        if isinstance(item, (complex, np.complexfloating)):
            item = np.asarray(item)
        if isinstance(item, np.ndarray):
            if item.dtype.hasobject:
                raise TypeError('Object arrays are prohibited')
            arrays[key] = item
            return {'array': key, 'shape': list(item.shape), 'dtype': str(item.dtype)}
        if isinstance(item, np.generic):
            return item.item()
        if isinstance(item, dict):
            return {str(k): pack(v, key+'/'+str(k)) for k, v in item.items()}
        if isinstance(item, (tuple, list)):
            return [pack(v, key+'/'+str(i)) for i, v in enumerate(item)]
        return item

    metadata = pack(value, 'root')
    np.savez_compressed(str(path)+'.npz', **arrays)
    write_json(str(path)+'.json', metadata)


def load_tree(path):
    metadata = json.loads(Path(str(path)+'.json').read_text())
    with np.load(str(path)+'.npz', allow_pickle=False) as arrays:
        def unpack(item):
            if isinstance(item, dict) and 'array' in item and 'dtype' in item:
                value = arrays[item['array']].copy()
                if list(value.shape) != item['shape'] or str(value.dtype) != item['dtype']:
                    raise ValueError('Saved array descriptor mismatch: '+item['array'])
                return value
            if isinstance(item, dict):
                return {k: unpack(v) for k, v in item.items()}
            if isinstance(item, list):
                return [unpack(v) for v in item]
            return item
        return unpack(metadata)
