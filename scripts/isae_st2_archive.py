"""Strict, stdlib-only reader for the original ST-2 nine-column span export.

Rows begin after the recognized header and separator, not a fixed line count.
Raw display values are retained alongside independently scaled resultants.
"""
from decimal import Decimal
import math
from pathlib import Path
import re


COLUMNS = ('t', 'y', 'z-z0', 'tw-tw0', "Mc'/10", "Ms'/10", 'Fn/10', 'cl', 'a_flap')
RESULTANTS = COLUMNS[4:7]
NUMBER = re.compile(r'[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[EeDd][+-]?\d+)?\Z')


def _field(token, exponent, line):
    if not NUMBER.fullmatch(token):
        raise ValueError(f'Line {line}: invalid finite numeric token {token!r}.')
    value = Decimal(token.replace('D', 'E').replace('d', 'e'))
    tolerance = Decimal(5).scaleb(value.as_tuple().exponent - 1)
    scale = Decimal(10) ** exponent
    numbers = [float(value), float(tolerance), float(value * scale), float(tolerance * scale)]
    if not all(math.isfinite(v) for v in numbers) or numbers[1] <= 0 or numbers[3] <= 0:
        raise ValueError(f'Line {line}: numeric value or printed precision is unrepresentable.')
    return dict(token=token, value=numbers[0], tolerance=numbers[1], power10=exponent,
                physical_value=numbers[2], physical_tolerance=numbers[3])


def decode_archive_profile(text):
    """Retain every row and token; reject malformed data instead of skipping it."""
    lines = text.splitlines()
    headers = [i for i, line in enumerate(lines) if tuple(line.split()) == COLUMNS]
    if len(headers) != 1:
        raise ValueError('Expected exactly one ST-2 nine-column span header.')
    header = headers[0]
    if header == 0:
        raise ValueError('Missing resultant exponent line before the span header.')
    tokens = lines[header - 1].split()
    if len(tokens) != 3 or any(re.fullmatch(r'[+-]?\d+', token) is None for token in tokens):
        raise ValueError('Expected three integer resultant exponents before the span header.')
    exponents = dict(zip(RESULTANTS, map(int, tokens)))
    if header + 1 >= len(lines):
        raise ValueError('Missing span table separator.')
    separator = lines[header + 1].split()
    if len(separator) != len(COLUMNS) or any(re.fullmatch(r'-{2,}', token) is None for token in separator):
        raise ValueError('Expected one separator field per span column.')
    rows = []
    for index, line in enumerate(lines[header + 2:], header + 3):
        if not line.strip():
            continue
        tokens = line.split()
        if len(tokens) != len(COLUMNS):
            raise ValueError(f'Line {index}: expected exactly nine span columns, got {len(tokens)}.')
        fields = {name: _field(token, exponents.get(name, 0), index)
                  for name, token in zip(COLUMNS, tokens)}
        rows.append(dict(row_index=len(rows), line_number=index, tokens=tokens, fields=fields))
    if not rows:
        raise ValueError('Span table has no numeric rows.')
    return dict(columns=list(COLUMNS), header_line=header + 1, separator_line=header + 2,
                resultant_exponents=exponents, rows=rows,
                values=[[row['fields'][name]['value'] for name in COLUMNS] for row in rows],
                physical_values=[[row['fields'][name]['physical_value'] for name in COLUMNS] for row in rows])


def read_archive_profile(path):
    return decode_archive_profile(Path(path).read_text())
