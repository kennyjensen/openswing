"""Explicit, unfitted reconstructions for the ISAE Pazy structural inputs.

The original files are never edited. An attachment at t=.558 lies beyond their
t=.55 endpoint. Derived static inputs either retain the archived physical mass
position on a rigid tip pylon, or use the measured tip/midchord load locations.
These alternatives do not establish what the archived ASWING executable did.
"""
from pathlib import Path
import hashlib
import re
import sys
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from openswing.asw import parse_asw
from openswing.network import StaticNetwork, network_result
from openswing.structured_static import equilibrate

REVISION = 'f62943df20e9e4d7d9f50e070477b22426b5f865'
CACHE = ROOT / '.reference/isae-validation' / REVISION
FOLDER = '3 - Structure/CASE - ST2 Pazy_Wing'
STATIC = FOLDER + '/03_Static_Structural'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def source(kind):
    assert kind in ('bending', 'torsion')
    return CACHE / STATIC / f'Pazy_wing_{kind}_bench.asw'


def replace_weights(text, rows):
    block = 'Weight\n' + '\n'.join(' '.join(format(v, '.17g') for v in row) for row in rows) + '\nEnd'
    derived, count = re.subn(r'(?ims)^Weight\s*\n.*?^end\s*$', block, text, count=1)
    assert count == 1
    return derived


def static_model(kind, skin, mass, layout):
    assert kind in ('bending', 'torsion') and skin in (0, 1)
    assert layout in ('archive_pylon', 'measured_tip') and mass >= 0
    text = source(kind).read_text()
    model = parse_asw(text)
    assert model.beams[0].domain == (.0001, .55)
    assert len(model.records['weight']) == 2
    assert all(row[1] == .558 and np.all(row[6:] == 0) for row in model.records['weight'])
    x = .05 if kind == 'bending' else (-.09 if skin == 0 else -.13)
    y = .558
    if layout == 'measured_tip':
        x = 0. if kind == 'bending' else (.09 if skin == 0 else .13)
        y = .55
    rows = [[1., .55, x, y, 0., mass * model.constants[0] / 2] for _ in range(2)]
    derived = replace_weights(text, rows)
    parsed = parse_asw(derived)
    # All beam geometry, constitutive properties and distributed inertia stay
    # byte-for-byte identical. Only the explicit Weight block is replaced.
    assert text[text.index('Beam 1'):] == derived[derived.index('Beam 1'):]
    return parsed, derived, dict(source_path=source(kind).relative_to(CACHE).as_posix(),
        source_sha256=sha(source(kind)), source_attachment=.558, derived_attachment=.55,
        mass_kg=mass, point_xyz_m=[x, y, 0.], layout=layout,
        scope='Explicit load/attachment reconstruction; original simplified material properties retained.')


def modal_model(orientation):
    assert orientation in ('upright', 'horizontal')
    path = CACHE / FOLDER / ('01_Modal_Undeformed' if orientation == 'upright' else '02_Modal_Gravity') / 'Pazy_wing.asw'
    text = path.read_text(); model = parse_asw(text)
    assert len(model.records['weight']) == 2
    assert all(row[1] == .558 and np.all(row[5:] == 0) for row in model.records['weight'])
    # These rows have zero mass, all moments of inertia, angular momentum,
    # aerodynamic volume and drag area. Removing them adds no physical load.
    derived = replace_weights(text, [])
    return parse_asw(derived), derived, dict(source_path=path.relative_to(CACHE).as_posix(),
        source_sha256=sha(path), removed_zero_objects=2,
        scope='Remove two exactly zero physical objects with out-of-domain anchors; retain all beam fields.')


def observables(position, rotation):
    """Keep projected chord twist distinct from ASWING's local section angle."""
    r, q = np.asarray(position), np.asarray(rotation)
    span = q[:, 1]
    phi = np.arctan2(span[2], span[1])
    psi = -np.arcsin(np.clip(span[0], -1., 1.))
    c0 = np.array([np.cos(psi), np.sin(psi)*np.cos(phi), np.sin(psi)*np.sin(phi)])
    n0 = np.array([0., -np.sin(phi), np.cos(phi)])
    local = np.arctan2(-q[:, 0] @ n0, q[:, 0] @ c0)
    projected = np.arctan2(-q[2, 0], np.hypot(q[0, 0], q[1, 0]))
    return dict(z_m=float(r[2]), y_m=float(r[1]), x_m=float(r[0]),
        twist_projected_deg=float(np.rad2deg(projected)),
        twist_asw_deg=float(np.rad2deg(local)))


def compute_static(spec):
    model, text, reconstruction = static_model(spec['kind'], spec['skin'], spec['mass_kg'], spec['layout'])
    net = StaticNetwork(model, spec['panels'], None, [0., 0., -9.81], [])
    state, steps = equilibrate(net)
    result = network_result(net, state)
    tip = result['nodes'][-1]
    return dict(specification=spec, derived_source=text, reconstruction=reconstruction,
        observables=observables(tip['position'], tip['rotation']), result=result)


def measurements():
    rows = []
    for kind, folder in [('bending', '05_Experimental_Bending'), ('torsion', '06_Experimental_Torsion')]:
        for p in sorted((CACHE / STATIC / folder).glob('*.txt')):
            skin = int(re.search(r'skin([01])', p.name)[1])
            quantity = 'twist_projected_deg' if '_rot_' in p.name else 'z_m'
            data = np.loadtxt(p)
            assert data.ndim == 2 and data.shape[1] == 2 and np.isfinite(data).all()
            values = data.copy()
            if quantity == 'z_m':
                values[:, 1] *= .55 / 100
            rows.append(dict(kind=kind, skin=skin, quantity=quantity,
                source_path=p.relative_to(CACHE).as_posix(), source_sha256=sha(p),
                original_values=data.tolist(), values=values.tolist(),
                units=['tip_mass_kg', 'degree' if quantity.endswith('_deg') else 'metre'],
                note='Vertical displacement is relative to the zero-tip-load state; twist sign is retained.'))
    assert len(rows) == 6
    return rows
