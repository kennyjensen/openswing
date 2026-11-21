"""Lossless, private wire storage for repeated time-result metadata.

Physics and standalone checkpoints keep their existing schemas. References
are separate from the data, so a user-supplied dictionary cannot accidentally
be interpreted as a reference. Pool entries contain complete JSON values,
including any internal BDF midpoint or Radau seed absent from public snapshots.
"""
import json

FORMAT = 'openswing-time-result'
VERSION = 1
# Small values cost less inline than a path plus a pool reference.
MINIMUM_BYTES = 192
SNAPSHOT_METADATA = (
    'section_output_definitions', 'coefficient_definitions', 'aerodynamic_lag',
    'mesh_discretization', 'sensor_metadata', 'limitations', 'restart_context',
)


def pack_time_result(result):
    """Return a wire packet without mutating the ordinary result.

    Exact JSON text is the intern key, rather than numeric equality, a hash,
    timestamp or snapshot index. Signed zero, bool/int distinctions, all
    captured charts and old-method metadata are therefore retained. The pool
    temporarily borrows its input values; serialize before modifying either.
    """
    if not isinstance(result, dict) or result.get('analysis') != 'time_response':
        return result
    out = dict(result)
    out['snapshots'] = [dict(snapshot) for snapshot in result['snapshots']]
    values, references, lookup = [], [], {}

    def intern(parent, name, prefix):
        value = parent.get(name)
        if not isinstance(value, (dict, list)):
            return
        encoded = json.dumps(value, allow_nan=False, separators=(',', ':'))
        if len(encoded) < MINIMUM_BYTES:
            return
        index = lookup.get(encoded)
        if index is None:
            index = len(values)
            lookup[encoded] = index
            values.append(value)
        parent[name] = None
        references.append([prefix + [name], index])

    intern(out, 'restart_context', [])
    for i, snapshot in enumerate(out['snapshots']):
        path = ['snapshots', i]
        for name in SNAPSHOT_METADATA:
            intern(snapshot, name, path)
        if not isinstance(snapshot.get('restart'), dict):
            continue
        record = snapshot['restart'] = dict(snapshot['restart'])
        path = path + ['restart']
        for name in ('state', 'older', 'options', 'validation_loads'):
            intern(record, name, path)
        if not isinstance(record.get('accepted_method'), dict):
            continue
        accepted = record['accepted_method'] = dict(record['accepted_method'])
        path = path + ['accepted_method']
        for name in ('previous', 'previous2', 'seed', 'accepted_inputs', 'layout'):
            intern(accepted, name, path)
        if isinstance(accepted.get('endpoint'), dict):
            endpoint = accepted['endpoint'] = dict(accepted['endpoint'])
            for name in ('state', 'options'):
                intern(endpoint, name, path + ['endpoint'])
    return dict(format=FORMAT, version=VERSION, result=out, values=values, references=references)


def unpack_time_result(packet):
    """Consume a decoded wire packet, restoring shared ordinary JSON values.

    This only checks storage structure, not physical checkpoint validity. Use
    the normal checkpoint validator before resuming. References never escape
    into the result or standalone checkpoint schema.
    """
    if not isinstance(packet, dict) or packet.get('format') != FORMAT:
        return packet

    def fail():
        raise ValueError('Invalid compact time result.')

    if (type(packet.get('version')) is not int or packet['version'] != VERSION
            or not isinstance(packet.get('result'), dict)
            or packet['result'].get('analysis') != 'time_response'
            or not isinstance(packet['result'].get('snapshots'), list)
            or not isinstance(packet.get('values'), list)
            or not isinstance(packet.get('references'), list)):
        fail()
    result, values = packet['result'], packet['values']
    seen, writes = set(), []
    for ref in packet['references']:
        if not isinstance(ref, list) or len(ref) != 2:
            fail()
        path, index = ref
        if (not isinstance(path, list) or not 1 <= len(path) <= 6
                or type(index) is not int or not 0 <= index < len(values)
                or not isinstance(values[index], (dict, list))):
            fail()
        parent = result
        for j, key in enumerate(path):
            if isinstance(parent, list):
                if type(key) is not int or not 0 <= key < len(parent):
                    fail()
            elif isinstance(parent, dict):
                if not isinstance(key, str) or key in ('__proto__', 'constructor', 'prototype') or key not in parent:
                    fail()
            else:
                fail()
            if j == len(path) - 1:
                name = tuple(path)
                if name in seen or parent[key] is not None:
                    fail()
                seen.add(name)
                writes.append((parent, key, values[index]))
            else:
                parent = parent[key]
    # Validate the whole packet before materializing any reference. Overlapping
    # paths cannot traverse a null hole, and duplicate targets are rejected.
    for parent, key, value in writes:
        parent[key] = value
    return result
