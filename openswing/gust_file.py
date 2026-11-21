"""Documented/public-example gust-file interoperability.

Type 5 with zero y slope is established by the ASWING v5.77 notes and the
published Avoni/WingLoop inputs. Other catalog maps and slant signs are not
inferred. Conversion changes the representation, not the gust equations.
"""
import hashlib
import json
import re
import numpy as np
from .gust import gust_field

MAX_TEXT = 32768
_NUMBER = re.compile(r'^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eEdD][+-]?\d+)?$')
SCOPE = ('ASWING type 5, zero spanwise slope, frozen vertical one-minus-cosine gust. '
         'The onset is Earth X=x0; the peak is at x0-H and the end at x0-2H. '
         'Values use the aircraft input L and T units. Other catalog types and nonzero slope conventions remain unverified.')


def parse_legacy_gust(text):
    if not isinstance(text, str) or len(text) > MAX_TEXT:
        raise ValueError(f'Gust files must be text of at most {MAX_TEXT} characters.')
    rows = []
    for number, line in enumerate(text.lstrip('\ufeff').splitlines(), 1):
        value = re.split(r'[!#]', line, maxsplit=1)[0].strip()
        if value:
            rows.append((number, value))
    if not rows or not re.fullmatch(r'[+-]?\d+', rows[0][1]):
        raise ValueError('A numeric .gust file starts with an integer gust type; use one value per line.')
    kind = int(rows[0][1])
    if kind != 5:
        raise ValueError(f'ASWING gust type {kind} has no verified parameter map yet; supported legacy input is type 5 with zero spanwise slope.')
    if len(rows) not in (6, 7):
        raise ValueError('Type 5 requires the gust index, onset X, y slope, gradient H, peak W and one or two trailing zero parameters, one value per line.')
    parameters = []
    for number, token in rows[1:]:
        if not _NUMBER.fullmatch(token):
            raise ValueError(f'Gust line {number}: expected one finite numeric value.')
        value = float(token.replace('D', 'e').replace('d', 'e'))
        if not np.isfinite(value):
            raise ValueError(f'Gust line {number}: expected one finite numeric value.')
        parameters.append(value)
    x0, slope, length, amplitude, *unused = parameters
    if slope != 0:
        raise ValueError('Type 5 nonzero y slope has no verified ASWING sign/length convention yet; define its leading plane explicitly in the cosine field editor.')
    if length <= 0:
        raise ValueError('Type 5 gradient length H must be positive.')
    if any(value != 0 for value in unused):
        raise ValueError('Nonzero trailing type-5 parameters are not documented by the supported public inputs; they cannot be silently ignored.')
    spec = dict(type='cosine', amplitude=[0., 0., amplitude], origin=[x0, 0., 0.],
                normal=[-1., 0., 0.], length=length, speed=0.)
    gust_field(spec)
    return dict(format='aswing-gust', gust=spec, legacy=dict(type=kind, parameters=parameters,
                source_sha256=hashlib.sha256(text.encode('utf-8')).hexdigest(), scope=SCOPE))


def import_gust(text):
    """Read an OpenSwing JSON field or the verified numeric type-5 layout."""
    if not isinstance(text, str) or len(text) > MAX_TEXT:
        raise ValueError(f'Gust files must be text of at most {MAX_TEXT} characters.')
    stripped = text.lstrip('\ufeff \t\r\n')
    if stripped.startswith(('{', '[')) or stripped == 'null':
        try:
            spec = json.loads(stripped)
        except (ValueError, RecursionError) as exc:
            raise ValueError('Invalid JSON gust field.') from exc
        if spec is None:
            spec = dict(type='none')
        gust_field(spec)
        return dict(format='openswing-json', gust=spec)
    return parse_legacy_gust(text)


def export_legacy_gust(spec):
    """Canonical numeric export only when its entire field is representable."""
    field = gust_field(spec)
    if field.kind != 'cosine':
        raise ValueError('Legacy .gust export requires a frozen, straight, vertical one-minus-cosine field; use JSON for other fields.')
    if (field.speed != 0 or np.any(field.amplitude[:2] != 0)
            or np.any(field.normal != [-1., 0., 0.])):
        raise ValueError('Legacy type-5 export requires zero propagation speed, vertical velocity and onset-to-peak direction along negative Earth X; use JSON for other fields.')
    values = [field.origin[0], 0., field.length, field.amplitude[2], 0.]
    comments = ['Earth X at onset [input L]', 'spanwise slope', 'onset-to-peak H [input L]',
                'peak Earth-Z velocity [input L/T]', 'unused parameter']
    text = '5 ! vertical one-minus-cosine gust\n'+''.join(f'{value:.17g} ! {comment}\n' for value, comment in zip(values, comments))
    return dict(format='aswing-gust', text=text, scope=SCOPE)
