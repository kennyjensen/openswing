"""Read SA-11 paper curves and archived numbers; no solver or test runner.

The PDF is pinned because vector-path indices are document-specific. Axis
calibration comes from the figure's labeled grid lines, never the archive.
"""
import argparse
import bisect
import csv
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path

import pymupdf

ROOT = Path(__file__).resolve().parents[1]
REVISION = 'f62943df20e9e4d7d9f50e070477b22426b5f865'
CASE = ('1 - Aerodynamics/SA - Steady Aerodynamics Cases/'
        'SA - 11 - Swept Back Wing with Whitcomb Winglet - Transoninc Lift and Drag')
CONFIGS = [('wing_alone', 'W-A'), ('Wing_tip_up', 'WT-U'),
           ('wing_extension', 'W-E'), ('Wing_tip_up_and_down', 'WT-U&D')]
COLORS = [(0., 0., 1.), (1., 0., 0.), (0., 0., 0.), (0., .5019530057907104, 0.)]
# Path ids were inspected against the rendered Figure 22, PDF/printed p. 39.
# Each axis lists three independently labeled grid lines (id, value).
PANELS = [
    dict(name='a', mach='70', kind='lift', curves=[37, 38, 39, 40],
         x=[(4, 0.), (5, 2.), (7, 6.)], y=[(8, .3), (11, .6), (14, .9)],
         samples=[1., 3., 5.], offset=0.),
    dict(name='b', mach='80', kind='lift', curves=[340, 341, 342, 343],
         x=[(305, 0.), (306, 2.), (308, 6.)], y=[(309, .3), (311, .5), (314, .8)],
         samples=[1., 3., 5.], offset=0.),
    dict(name='c', mach='70', kind='drag', curves=[644, 645, 646, 647],
         x=[(610, .2), (611, .4), (613, .8)], y=[(614, .01), (616, .03), (619, .06)],
         samples=[.3, .5, .7], offset=.0064),
    dict(name='d', mach='80', kind='drag', curves=[771, 772, 773, 774],
         x=[(728, .2), (730, .4), (734, .8)], y=[(735, .01), (737, .03), (740, .06)],
         samples=[.3, .5, .7], offset=.0075),
]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def interpolate(points, x):
    xs = [point[0] for point in points]
    assert all(a < b for a, b in zip(xs, xs[1:])), 'non-monotone curve'
    assert xs[0] <= x <= xs[-1], 'no extrapolation'
    index = min(max(bisect.bisect_right(xs, x), 1), len(xs) - 1)
    (x0, y0), (x1, y1) = points[index - 1:index + 1]
    return y0 + (y1 - y0) * (x - x0) / (x1 - x0)


def calibration(drawings, ticks, axis):
    coordinates = []
    for index, value in ticks:
        item = drawings[index]['items']
        assert len(item) == 1 and item[0][0] == 'l'
        p, q = item[0][1:]
        assert abs(p[axis] - q[axis]) < 1e-5
        coordinates.append((p[axis], value))
    (p0, v0), (_, _), (p1, v1) = coordinates
    scale = (v1 - v0) / (p1 - p0)
    origin = v0 - scale * p0
    residual_points = max(abs((scale * p + origin - v) / scale) for p, v in coordinates)
    assert residual_points < .005, 'independent middle grid tick disagrees'
    return scale, origin, residual_points


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit('Use a new output directory; prior evidence is retained.')
    catalog = json.loads((ROOT / 'docs/validation/aswing-authoritative-sources.json').read_text())
    reference = next(item for item in catalog['files'] if item['id'] == 'isae-part-1')
    pdf = ROOT / reference['local_pdf']
    assert sha(pdf) == reference['sha256']
    pins = {str(pdf.relative_to(ROOT)): sha(pdf)}
    manifest = json.loads((ROOT / 'docs/validation/isae-sa11-sources.json').read_text())['sources']
    base = ROOT / 'reference/isae-validation' / REVISION / CASE
    tables = {}
    for folder, label in CONFIGS:
        for mach in ['70', '80']:
            file = next((base / 'Aswing_Simulations' / folder).glob(f'*Ma_0_{mach}.txt'))
            key = str(file.relative_to(ROOT / 'reference/isae-validation' / REVISION))
            assert sha(file) == manifest[key]['sha256']
            pins[str(file.relative_to(ROOT))] = sha(file)
            rows = []
            for line in file.read_text().splitlines():
                try:
                    row = list(map(float, line.split()))
                except ValueError:
                    continue
                if len(row) >= 81:
                    rows.append(row)
            assert len(rows) == 41
            tables[label, mach] = rows
    script = base / 'Post_traitement.m'
    assert sha(script) == manifest[f'{CASE}/Post_traitement.m']['sha256']
    pins[str(script.relative_to(ROOT))] = sha(script)
    with pymupdf.open(pdf) as document:
        drawings = document[38].get_drawings()
    comparisons, vertices, axes = [], [], []
    for panel in PANELS:
        sx, ox, rx = calibration(drawings, panel['x'], 0)
        sy, oy, ry = calibration(drawings, panel['y'], 1)
        axes.append(dict(panel=panel['name'], x=panel['x'], y=panel['y'],
                         x_grid_residual_points=rx, y_grid_residual_points=ry))
        for (_, label), index, color in zip(CONFIGS, panel['curves'], COLORS):
            drawing = drawings[index]
            assert max(abs(a - b) for a, b in zip(drawing['color'], color)) < 1e-6
            assert len(drawing['items']) > 10
            assert all(item[0] == 'l' for item in drawing['items'])
            points = [drawing['items'][0][1], *(item[2] for item in drawing['items'])]
            points = [(sx * p.x + ox, sy * p.y + oy) for p in points]
            vertices.extend(dict(panel=panel['name'], configuration=label, x=x, y=y) for x, y in points)
            rows = tables[label, panel['mach']]
            archive = ([(r[74], r[77]) for r in rows] if panel['kind'] == 'lift'
                       else [(r[77], r[78] + panel['offset']) for r in rows])
            for x in panel['samples']:
                figure = interpolate(points, x)
                archived = interpolate(archive, x)
                comparisons.append(dict(panel=panel['name'], configuration=label, x=x,
                    figure=figure, archive_postprocessed=archived, difference=figure-archived,
                    line_half_width_y_units=.5 * drawing['width'] * abs(sy)))
    printed = {'70': [4.70, 4.94, 4.95, 5.34], '80': [5.02, 5.16, 5.19, 5.74]}
    slopes = []
    for mach, values in printed.items():
        for (_, label), paper in zip(CONFIGS, values):
            rows = tables[label, mach]
            xs, ys = [r[74] for r in rows], [r[77] for r in rows]
            xm, ym = sum(xs) / len(xs), sum(ys) / len(ys)
            slope = (sum((x-xm)*(y-ym) for x, y in zip(xs, ys))
                     / sum((x-xm)**2 for x in xs) * 180 / math.pi)
            slopes.append(dict(mach_label=mach, configuration=label,
                               printed_per_radian=paper, archive_per_radian=slope,
                               agrees_at_printed_precision=abs(slope-paper) < .005))
    result = dict(observed_utc=datetime.now(timezone.utc).isoformat(),
                  status='SOURCE_COMPARISON_ONLY_NO_SOLVER_RUN', source_pins=pins,
                  script_sha256=sha(Path(__file__)), pymupdf_version=pymupdf.VersionBind,
                  figure=22, pdf_page=39, axes=axes, slopes=slopes, comparisons=comparisons,
                  max_abs_lift_difference=max(abs(r['difference']) for r in comparisons if r['panel'] in 'ab'),
                  max_abs_drag_difference=max(abs(r['difference']) for r in comparisons if r['panel'] in 'cd'))
    args.output.mkdir(parents=True)
    (args.output / 'comparison.json').write_text(json.dumps(result, indent=2) + '\n')
    with (args.output / 'paper-vector-curves.csv').open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=['panel', 'configuration', 'x', 'y'])
        writer.writeheader(); writer.writerows(vertices)
    print(json.dumps({key: result[key] for key in ['status', 'max_abs_lift_difference', 'max_abs_drag_difference']}, indent=2))
    print(f'{len(comparisons)} figure/archive samples; {len(vertices)} retained vector vertices; no ISAE scoring')


if __name__ == '__main__':
    main()
