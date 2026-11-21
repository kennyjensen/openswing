"""Local ASW table edits which retain comments and unrelated source verbatim."""
from difflib import SequenceMatcher
import re

import numpy as np

from .asw import AswError, Block, Distribution, _table, canonical, numbers, weight_station


def _parts(line):
    end = re.search(r'[!#%\r\n]', line)
    return (line[:end.start()], line[end.start():]) if end else (line, '')


def _fields(line, replacements, *, directive=False):
    """Replace selected tokens, retaining whitespace, separators and inline notes."""
    code, tail = _parts(line)
    start = len(code)-len(code.lstrip())+1 if directive else 0
    tokens = list(re.finditer(r'[^\s,]+', code[start:]))
    for index, value in sorted(replacements.items(), reverse=True):
        if index >= len(tokens):
            continue  # Omitted scaling coefficients already have identity values.
        token = tokens[index]
        left, right = start+token.start(), start+token.end()
        if value is None:
            replacement = ''
        elif isinstance(value, str):
            replacement = value
        else:
            if numbers(token.group(), 0)[0] == value:
                continue
            replacement = format(float(value), '.17g')
        code = code[:left]+replacement.rjust(right-left)+code[right:]
    return code+tail


def _comment_only(line):
    code, tail = _parts(line)
    return re.sub(r'\S', ' ', code)+tail if tail.startswith(('!', '#', '%')) else ''


def _normalise_scaling(lines, entries, columns):
    for ln, body in entries:
        if body[0] in '*+':
            lines[ln-1] = _fields(lines[ln-1], {c: 1. if body[0] == '*' else 0. for c in columns}, directive=True)


def resolve_weight_aliases(model):
    """Keep the existing exact attachment rule without canonicalizing the file."""
    lines = model.source.splitlines(keepends=True)
    offset = 0
    for block in model.blocks:
        if block.kind != 'weight':
            continue
        entries = [(ln, body) for ln, body in block.lines if body[0] not in '*+']
        rows = model.records['weight'][offset:offset+len(entries)]
        offset += len(entries)
        stations = [weight_station(model, row) for row in rows]
        if all(t == row[1] for t, row in zip(stations, rows)):
            continue
        # Integer beam IDs do not have scaling coefficients: station is the
        # first scale column but the second numeric data column.
        _normalise_scaling(lines, block.lines, [0])
        for (ln, _), t in zip(entries, stations):
            lines[ln-1] = _fields(lines[ln-1], {1: t})
    return ''.join(lines)


def _unscale(value, multiplier, adder):
    """Encode a new value under the existing row's scaling without changing it."""
    if multiplier == 0 and value == adder:
        return 0., float(adder)
    with np.errstate(over='ignore', invalid='ignore', divide='ignore'):
        raw = np.float64(value-adder)/multiplier
        actual = raw*multiplier+adder
    if not np.isfinite(raw) or not np.isclose(actual, value, rtol=8*np.finfo(float).eps, atol=0):
        raise AswError('The new station cannot be represented with this table\'s scaling.')
    return float(raw), float(actual)


def _shared_insertion(model, beam, lines, group, data, numeric, target, column, newline):
    """A single added point is a row insertion for every column in its table.

    Return the source insertion and expected distributions for the caller's
    independent round-trip check. Existing rows and scaling stay byte-for-byte.
    """
    if target is None or len(target) != len(data)+1:
        return None
    original = data[:, [0, column]]
    different = np.flatnonzero(np.any(target[:-1] != original, axis=1))
    index = int(different[0]) if len(different) else len(data)
    if not np.array_equal(target[index+1:], original[index:]):
        return None  # A broader grid/value replacement remains independent.
    header, names, entries = group
    first_anchor = max([header, *[ln for ln, _ in entries if ln-1 < numeric[0]]])
    at = numeric[index-1]+1 if index else first_anchor
    multiplier, adder = np.ones(len(names)+1), np.zeros(len(names)+1)
    for ln, body in entries:
        if ln > at:
            break
        if body[0] in '*+':
            coefficients = numbers(body[1:], ln)
            scaling = multiplier if body[0] == '*' else adder
            scaling[:] = 1 if body[0] == '*' else 0
            scaling[:len(coefficients)] = coefficients
    raw_t, station = _unscale(target[index, 0], multiplier[0], adder[0])
    raw, actual = [raw_t], [station]
    for c, name in enumerate(names, 1):
        value = target[index, 1] if c == column else beam.distributions[name].evaluate(station)
        encoded, decoded = _unscale(float(value), multiplier[c], adder[c])
        raw.append(encoded)
        actual.append(decoded)
    updated = np.insert(data, index, actual, axis=0)
    expected = {name: Distribution(name, updated[:, 0], updated[:, c], header,
                                  interpolation=model.beam_interpolation)
                for c, name in enumerate(names, 1)}
    # Reuse the neighboring row's layout, but never copy its inline annotation.
    template = _parts(lines[numeric[max(0, index-1)]])[0].rstrip()+newline
    return at, _fields(template, dict(enumerate(raw))), expected


def _shared_deletion(model, group, data, numeric, target, column, index=None):
    """Remove the same source row from every column, without resampling."""
    explicit = index is not None
    if target is None or len(target) != len(data)-1:
        if explicit:
            raise AswError('Station deletion must remove exactly the selected row.')
        return None
    original = data[:, [0, column]]
    if index is None:
        different = np.flatnonzero(np.any(original[:-1] != target, axis=1))
        index = int(different[0]) if len(different) else len(data)-1
    if not np.array_equal(np.delete(original, index, axis=0), target):
        if explicit:
            raise AswError('Station deletion must leave the other rows unchanged.')
        return None
    if not explicit and index > 0 and np.array_equal(original[index-1], original[index]):
        raise AswError('Specify which doubled station row to delete.')
    header, names, _ = group
    updated = np.delete(data, index, axis=0)
    expected = {name: Distribution(name, updated[:, 0], updated[:, c], header,
                                  interpolation=model.beam_interpolation)
                for c, name in enumerate(names, 1)}
    return numeric[index], expected


def distribution_source(model, beam_index, name, *, delete_station=None):
    """Return local source and any shared-row distribution updates.

    Value changes and single-station insertion/deletion retain a shared table.
    Broader independent grid changes split just the edited column into an
    adjacent table. Explicit deletion indices use the editor's ascending order.
    """
    beam = next(b for b in model.beams if b.index == beam_index)
    block = next(b for b in model.blocks if b.kind == 'beam' and b.line == beam.line)
    lines = model.source.splitlines(keepends=True)
    newline = '\r\n' if '\r\n' in model.source else '\n'
    groups = []
    for ln, body in block.lines[1:]:
        if body.split()[0].lower() == 't':
            groups.append((ln, [canonical(v) for v in body.split()[1:]], []))
        else:
            groups[-1][2].append((ln, body))
    group = next((g for g in groups if name in g[1]), None)
    replacement = beam.distributions.get(name)
    insertions = {}

    def insert(at, text):
        insertions[at] = insertions.get(at, '')+text

    def table_text():
        return 't '+name+newline+''.join(format(float(t), '.17g')+' '+format(float(v), '.17g')+newline
                                       for t, v in zip(replacement.t, replacement.values))

    if group is None:
        # Before trailing beam notes / End, after the last existing table.
        insert(block.lines[-1][0], table_text())
    else:
        header, names, entries = group
        column = names.index(name)+1
        data = np.asarray(_table(Block('distribution', entries, header), len(names)+1))
        numeric = [ln-1 for ln, body in entries if body[0] not in '*+']
        descending = len(data)>1 and data[-1, 0]<data[0, 0]
        target = None if replacement is None else np.column_stack((replacement.t, replacement.values))
        if target is not None and descending:
            target = target[::-1]
        if delete_station is not None or len(names)>1:
            index = len(data)-1-delete_station if descending and delete_station is not None else delete_station
            deleted = _shared_deletion(model, group, data, numeric, target, column, index)
            if deleted is not None:
                line, expected = deleted
                lines[line] = _comment_only(lines[line])
                return ''.join(lines), expected
        same_grid = target is not None and np.array_equal(target[:, 0], data[:, 0])
        if same_grid and np.array_equal(target[:, 1], data[:, column]):
            return model.source, {}
        if same_grid:
            # Flatten only this value column's scaling. Station tokens (and
            # their exact-decimal provenance), other columns and notes survive.
            _normalise_scaling(lines, entries, [column])
            for line, value in zip(numeric, target[:, 1]):
                lines[line] = _fields(lines[line], {column: value})
        elif len(names)>1:
            inserted = _shared_insertion(model, beam, lines, group, data, numeric, target, column, newline)
            if inserted is not None:
                at, row, expected = inserted
                return ''.join(lines[:at])+row+''.join(lines[at:]), expected
            lines[header-1] = _fields(lines[header-1], {column: None})
            for ln, body in entries:
                lines[ln-1] = _fields(lines[ln-1], {column: None}, directive=body[0] in '*+')
            if replacement is not None:
                insert(entries[-1][0], table_text())
        elif replacement is None:
            for ln in [header, *[ln for ln, _ in entries]]:
                lines[ln-1] = _comment_only(lines[ln-1])
        else:
            # Retain row annotations with matching stations. A deleted
            # row's inline note becomes a standalone note at that same place.
            _normalise_scaling(lines, entries, [0, 1])
            old = [tuple(row) for row in data[:, [0, column]]]
            new = [tuple(row) for row in target]
            indent = re.match(r'\s*', lines[numeric[0]]).group()
            first_anchor = max([header, *[ln for ln, _ in entries if ln-1<numeric[0]]])
            # Match by station, so changing a value while inserting a neighbor
            # cannot transfer the original row's annotation to the new station.
            for _, a, b, c, d in SequenceMatcher(a=[r[0] for r in old], b=[r[0] for r in new], autojunk=False).get_opcodes():
                paired = min(b-a, d-c)
                for i in range(paired):
                    line = numeric[a+i]
                    lines[line] = _fields(lines[line], dict(enumerate(new[c+i])))
                for i in range(a+paired, b):
                    lines[numeric[i]] = _comment_only(lines[numeric[i]])
                if c+paired<d:
                    at = numeric[b-1]+1 if b else first_anchor
                    insert(at, ''.join(indent+' '.join(format(float(v), '.17g') for v in row)+newline for row in new[c+paired:d]))
    return ''.join(insertions.get(i, '')+line for i, line in enumerate(lines))+insertions.get(len(lines), ''), {}
