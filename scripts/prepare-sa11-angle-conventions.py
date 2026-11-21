"""Prepare explicit SA-11 incidence interpretations using scalar geometry only.

This is a source/geometry audit. It imports no OpenSwing, numerical libraries,
solver or test runner and never changes the original or bundled examples.
"""
import argparse
import difflib
import hashlib
import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REVISION = 'f62943df20e9e4d7d9f50e070477b22426b5f865'
CACHE = ROOT / 'reference/isae-validation' / REVISION
CASE = ('1 - Aerodynamics/SA - Steady Aerodynamics Cases/'
        'SA - 11 - Swept Back Wing with Whitcomb Winglet - Transoninc Lift and Drag')
SOURCE = CACHE / CASE / 'Aswing_Simulations/Wing_tip_up/wingtip_up.asw'
GEOMETRY = ['t', 'x', 'y', 'z', 'twist', 'chord', 'Xax']


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dot(a, b):
    return sum(x*y for x, y in zip(a, b))


def cross(a, b):
    return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])


def unit(a):
    length = math.sqrt(dot(a, a))
    assert length > 0
    return tuple(x/length for x in a)


def geometry_blocks(text):
    """Strict scanner for this pinned two-station fixture, not an ASW parser."""
    beams, beam, active, scales = {}, None, False, None
    for index, line in enumerate(text.splitlines(keepends=True)):
        tokens = line.split('#', 1)[0].split('!', 1)[0].split()
        if not tokens:
            continue
        if tokens[0] == 'Beam':
            beam = int(tokens[1]); beams[beam] = []; active = False
        elif tokens[0] == 'End':
            beam = None; active = False
        elif beam is not None and tokens[0] == 't':
            active = tokens == GEOMETRY; scales = None
        elif active and tokens[0] == '*':
            scales = list(map(float, tokens[1:])); assert len(scales) == 7
        elif active:
            assert scales is not None and len(tokens) == 7
            values = [float(v)*scale for v, scale in zip(tokens, scales)]
            beams[beam].append(dict(zip(GEOMETRY, values), line=index))
    assert set(beams) == {1, 2, 3} and all(len(rows) == 2 for rows in beams.values())
    return beams


def basis(rows):
    lo, hi = sorted(rows, key=lambda row: row['t'])
    s = unit(tuple(hi[k]-lo[k] for k in ['x', 'y', 'z']))
    a = math.hypot(s[1], s[2])
    c0 = (a, -s[0]*s[1]/a, -s[0]*s[2]/a)
    n0 = (0., -s[2]/a, s[1]/a)
    return s, c0, n0, a


def orientations(rows, theta):
    s, c0, n0, a = basis(rows)
    radians = math.radians(theta)
    c = tuple(math.cos(radians)*x-math.sin(radians)*y for x, y in zip(c0, n0))
    n = tuple(math.sin(radians)*x+math.cos(radians)*y for x, y in zip(c0, n0))
    # Independent construction: form the section normal by crossing its axes.
    error = max(abs(x-y) for x, y in zip(cross(c, s), n))
    assert error < 1e-14 and abs(dot(n, s)) < 1e-14
    side = math.copysign(1., rows[0]['y'])
    horizontal = math.degrees(math.atan(-n[0]/n[1]*side))
    # Shear the normal chord along the span into the unswept section plane.
    transverse = (0., s[1], s[2])
    shear = -dot(c, transverse)/dot(transverse, transverse)
    d = tuple(x+shear*y for x, y in zip(c, s))
    unswept = math.degrees(math.atan2(-dot(d, n0), d[0]))
    formula = math.degrees(math.atan(a*math.tan(radians)))
    assert abs(unswept-formula) < 1e-12
    return dict(beam_twist_deg=theta, horizontal_cut_toe_deg=horizontal,
                unswept_section_incidence_deg=unswept, section_normal=list(n),
                independent_normal_error=error)


def target_twists(rows):
    _, c0, n0, a = basis(rows)
    angle = math.radians(-4.)
    side = math.copysign(1., rows[0]['y'])
    direction = (math.cos(angle), side*math.sin(angle), 0.)
    horizontal = math.degrees(math.atan2(-dot(n0, direction), dot(c0, direction)))
    unswept = math.degrees(math.atan(math.tan(angle)/a))
    return dict(source_plus4=4., report_minus4=-4.,
                horizontal_toe_minus4=horizontal, unswept_incidence_minus4=unswept)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    out = parser.parse_args().output
    if out.exists():
        raise SystemExit('Use a new output directory; do not overwrite prior evidence.')
    source_catalog = json.loads((ROOT/'docs/validation/isae-sa11-sources.json').read_text())
    key = str(SOURCE.relative_to(CACHE))
    assert sha(SOURCE) == source_catalog['sources'][key]['sha256']
    pins = {str(SOURCE.relative_to(ROOT)): sha(SOURCE)}
    nasa = ROOT/'reference/isae-sa11/NASA-TN-D-8473.pdf'
    assert sha(nasa) == source_catalog['primary']['sha256']
    pins[str(nasa.relative_to(ROOT))] = sha(nasa)
    catalog = json.loads((ROOT/'docs/validation/aswing-authoritative-sources.json').read_text())
    for item in catalog['files']:
        if item['id'] in ['isae-part-1', 'drela-steady']:
            file = ROOT/item['local_pdf']
            assert sha(file) == item['sha256']; pins[str(file.relative_to(ROOT))] = sha(file)
    original = SOURCE.read_text()
    old_joint = '*     1      1       0.1            0.1        1'
    assert original.count(old_joint) == 1
    joint_only = original.replace(old_joint, '*     0.1      0.1')
    blocks = geometry_blocks(joint_only)
    targets = {beam: target_twists(blocks[beam]) for beam in [2, 3]}
    files, variants = {}, []
    for name in targets[2]:
        lines = joint_only.splitlines(keepends=True)
        for beam in [2, 3]:
            theta = targets[beam][name]
            for row in blocks[beam]:
                assert row['twist'] == 4.
                index = row['line']; tokens = list(re.finditer(r'\S+', lines[index]))
                start, stop = tokens[4].span()
                lines[index] = lines[index][:start] + f'{theta:.15g}' + lines[index][stop:]
        body = ''.join(lines)
        changed = geometry_blocks(body)
        audit = []
        for beam in blocks:
            for before, after in zip(blocks[beam], changed[beam]):
                for key in GEOMETRY:
                    if beam == 1 or key != 'twist':
                        assert before[key] == after[key], (name, beam, key)
        # Verify that only the four winglet twist tokens differ from joint-only.
        restored = body.splitlines(keepends=True)
        for beam in [2, 3]:
            for row in changed[beam]:
                index = row['line']; token = list(re.finditer(r'\S+', restored[index]))[4]
                restored[index] = restored[index][:token.start()] + '4' + restored[index][token.end():]
            audit.append(dict(beam=beam, **orientations(changed[beam], changed[beam][0]['twist'])))
        assert ''.join(restored) == joint_only
        assert abs(audit[0]['beam_twist_deg']-audit[1]['beam_twist_deg']) < 1e-12
        assert max(abs(a-b) for a, b in zip(audit[0]['section_normal'],
                   [audit[1]['section_normal'][0], -audit[1]['section_normal'][1], audit[1]['section_normal'][2]])) < 1e-14
        if name == 'horizontal_toe_minus4':
            assert all(abs(row['horizontal_cut_toe_deg']+4) < 1e-12 for row in audit)
        if name == 'unswept_incidence_minus4':
            assert all(abs(row['unswept_section_incidence_deg']+4) < 1e-12 for row in audit)
        header = (f'# SA-11 diagnostic: {name}. Not an authenticated native generating input.\n'
                  '# Only the disclosed Joint scale repair and upper-winglet twist differ.\n'
                  '# Geometry checked with scalar algebra; aerodynamic result not computed.\n')
        files[f'{name}.asw'] = header + body
        files[f'{name}.diff'] = ''.join(difflib.unified_diff(original.splitlines(True), body.splitlines(True),
                                     fromfile='original/wingtip_up.asw', tofile=f'{name}.asw'))
        variants.append(dict(name=name, beams=audit))
    root = min(blocks[2], key=lambda row: abs(row['t']))
    tip = max(blocks[2], key=lambda row: abs(row['t']))
    _, _, _, across = basis(blocks[2])
    span = math.hypot(tip['y']-root['y'], tip['z']-root['z'])
    main_tip = max(blocks[1], key=lambda row: row['t'])
    main_across = basis(blocks[1])[3]
    offset = (root['x']+.25*root['chord']/across
              -main_tip['x']-.25*main_tip['chord']/main_across)
    planform_area = .5*(root['chord']+tip['chord'])*span/across
    geometry = dict(upper_frontal_span_m=span, nasa_nominal_planform_span_m=.2032,
        span_difference_percent=100*(span/.2032-1),
        leading_edge_sweep_in_unswept_plane_deg=math.degrees(math.atan((tip['x']-root['x'])/span)),
        nasa_nominal_leading_edge_sweep_deg=38.,
        area_from_normal_chord_and_beam_length_m2=planform_area,
        aspect_ratio_using_frontal_span=span**2/planform_area,
        nasa_quoted_aspect_ratio=2.33,
        frozen_body_x_quarter_chord_root_offset_m=offset,
        note='These dimensions are retained in every angle variant. Their interpretation is separate from the incidence diagnostic.')
    files['source-original.asw'] = original
    files['prepare-used.py'] = Path(__file__).read_text()
    out.mkdir(parents=True)
    for name, content in files.items():
        (out/name).write_text(content)
    result = dict(observed_utc=datetime.now(timezone.utc).isoformat(),
        status='PREPARED_GEOMETRY_ONLY_NO_AERODYNAMIC_RUN', native_run_performed=False,
        primary_passes_added=0, source_pins=pins, variants=variants, retained_geometry=geometry,
        file_sha256={name: sha(out/name) for name in files},
        source_basis=['Jan Part I Figure 40, p68: upper twist -4 degrees',
                      'NASA TN D-8473, printed p4/PDF p6 and Fig2b printed p17/PDF p19: upper incidence/toe-out -4 degrees',
                      'Drela steady theory section 1.1 and section 1.5: local frames and distinction between twist and airfoil zero-lift line'],
        limits='Two angle interpretations are explicit alternatives, not recovered native settings. Original axis/chord/airfoil data and shared physical index remain. No smoothing, core, mesh, solver or guard change. No production-parser/browser verification.')
    (out/'geometry-audit.json').write_text(json.dumps(result, indent=2, allow_nan=False)+'\n')
    print(json.dumps(dict(status=result['status'], variants=[dict(name=x['name'], **x['beams'][0]) for x in variants], retained_geometry=geometry), indent=2))


if __name__ == '__main__':
    main()
