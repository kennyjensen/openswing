"""Decode archived Cairo EPS curves as data, without executing PostScript.

Tick values were checked visually against ISAE Part 3, PDF page 39, Figure 25.
In T(F) and Z(M) the saved EPS limits differ from the final Analysis.m limits;
therefore the actual tick positions, not that script's requested limits, set y.
"""
from pathlib import Path
import hashlib, json, re, runpy, sys
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
ns = runpy.run_path(str(ROOT/'scripts/verify-isae-st3-static.py'))
DEST = ROOT/'docs/validation'
NAMES = list(ns['LAYUPS'])
NUMBER = r'[-+]?(?:\d+\.?\d*|\.\d+)'
LINE = rf'({NUMBER})\s+({NUMBER})\s+m\s+({NUMBER})\s+({NUMBER})\s+l\s+S Q'
POINT = rf'({NUMBER})\s+({NUMBER})\s+([ml])'


def extract(path):
    text = path.read_text()
    kind = 'F' if '(F)' in path.name else 'M'
    quantity = 'Z' if '_Z' in path.name else 'T'
    split_axes = (quantity, kind) in [('Z', 'F'), ('T', 'M')]
    rects = [list(map(float, match)) for match in re.findall(rf'1 g\s+({NUMBER}) ({NUMBER}) ({NUMBER}) ({NUMBER}) re f', text)]
    grids = re.findall(r'0\.87451 g(.*?)0\.14902 g', text, re.S)
    count = 3 if split_axes else 1
    assert len(grids) == count
    ticks = {('Z', 'F'): [0., .05, .1, .15], ('T', 'M'): [0., 5., 10., 15., 20., 25.],
             ('T', 'F'): [-10., -5., 0., 5., 10.], ('Z', 'M'): np.arange(-4, 5)*.01}[(quantity, kind)]
    axes = []
    for rectangle, grid in zip(rects[:count], grids):
        horizontal = [list(map(float, p)) for p in re.findall(LINE, grid) if p[1] == p[3]]
        yp = [-p[1] for p in horizontal]
        assert len(yp) == len(ticks)
        calibration = np.polyfit(yp, ticks, 1)
        axes.append(dict(rectangle=rectangle, y_tick_pixels=yp, y_tick_values=list(ticks),
                         y_affine=calibration.tolist(), max_tick_fit_error=float(max(abs(np.polyval(calibration, yp)-ticks)))))
    xmax = {('Z', 'F'): 5., ('T', 'F'): 4., ('Z', 'M'): .55, ('T', 'M'): .6}[(quantity, kind)]
    curves = []
    # Graphics-state color changes partition the stroke data. Closed marker
    # paths, Bezier glyphs, rectangles and legend strokes are excluded.
    colors = list(re.finditer(r'(?m)^((?:[-\d.]+ ){2}[-\d.]+ rg|[-\d.]+ g)\s*$', text))
    for index, color in enumerate(colors):
        if color[1] != '1 0 0 rg':
            continue
        stop = colors[index+1].start() if index+1 < len(colors) else len(text)
        segment = text[color.end():stop]
        for match in re.finditer(r'q 1 0 0 -1 0 0 cm\s+(.*?)\s+S Q', segment, re.S):
            content = match[1]
            parsed = re.findall(POINT, content)
            if len(parsed) < 2 or re.sub(POINT, '', content).strip():
                continue
            assert parsed[0][2] == 'm' and all(p[2] == 'l' for p in parsed[1:])
            pixels = np.array([[float(p[0]), -float(p[1])] for p in parsed])
            hits = []
            for ai, axis in enumerate(axes):
                x, y, w, h = axis['rectangle']
                if np.all((pixels[:, 0] >= x-.1) & (pixels[:, 0] <= x+w+.1) & (pixels[:, 1] >= y-.1) & (pixels[:, 1] <= y+h+.1)):
                    hits.append(ai)
            if len(hits) != 1:
                continue
            axis = axes[hits[0]]; x, y, w, h = axis['rectangle']
            values = np.c_[(pixels[:, 0]-x)/w*xmax, np.polyval(axis['y_affine'], pixels[:, 1])]
            curves.append(dict(name=NAMES[hits[0] if split_axes else len(curves)],
                               pixel_vertices=pixels.tolist(), values=values.tolist(), axis=hits[0]))
    assert len(curves) == 3, (path.name, len(curves))
    return dict(path=path.relative_to(ns['CACHE']).as_posix(), sha256=ns['sha'](path), kind=kind,
                quantity=quantity, axes=axes, x_range=[0., xmax], curves=curves,
                columns=['plotted_load_N' if kind == 'F' else 'plotted_torque_Nm', 'plotted_h_m' if quantity == 'Z' else 'plotted_theta_deg'])


def main():
    data = ns['measurements']()
    figures = [extract(p) for p in sorted((ns['CACHE']/ns['STATIC']).glob('*.eps'))]
    cache = ROOT/'.reference/isae-st3-static-eps-runs'; cache.mkdir(exist_ok=True)
    modules = {p.name: ns['sha'](p) for p in sorted((ROOT/'openswing').glob('*.py'))}
    scripts = {name: ns['sha'](ROOT/'scripts'/name) for name in ['extract-isae-st3-static.py', 'verify-isae-st3-static.py', 'isae_st3_static_reference.py']}
    rows = []
    for figure in figures:
        for curve in figure['curves']:
            name = curve['name']
            if figure['kind'] == 'F':
                original = np.arange(6 if name == '0_3_90' else 5)*.981
            else:
                dataset = next(d for d in data if d['name'] == name and d['kind'] == 'M' and d['quantity'] == 'THETA' and d['category'] == 'experiment_digitization')
                original = np.array(dataset['values'])[:, 1]*(1 if name == '0_3_90' else -1)
                original[len(original)//2] = 0.  # reproduce archived postprocessing only
            for load, plotted in curve['values']:
                nearest = float(original[np.argmin(abs(original-load))])
                if abs(nearest-load) > (2e-4 if figure['kind'] == 'M' else 5e-4):
                    rows.append(dict(figure=figure['path'], name=name, decoded_load=load,
                                     plotted=plotted, status='clipped_line_endpoint_not_sample'))
                    continue
                # MATLAB default conversion is consistent with 5 significant
                # digits for these scalar values <1. All three saved final
                # Weight rows independently confirm this rounding. The exact
                # MATLAB version and intermediate files were not archived.
                force = nearest if figure['kind'] == 'F' else 0.
                couple = float(format(nearest, '.5g'))*ns['TORQUE_FACTOR'] if figure['kind'] == 'M' else 0.
                spec = dict(name=name, force_N=force, couple_Nm=couple, panels=64)
                identity = dict(specification=spec, modules=modules, scripts=scripts,
                                input_sha256=ns['sha'](ns['CACHE']/ns['source_path'](name)))
                digest = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
                path = cache/(digest+'.json')
                if path.exists():
                    run = json.loads(path.read_text()); assert run['identity'] == identity
                else:
                    run = dict(identity=identity, result=ns['compute']((ns['CACHE']/ns['source_path'](name)).read_text(), spec))
                    path.write_text(json.dumps(run, indent=2)+'\n')
                obs = run['result']['observables']
                if figure['quantity'] == 'Z':
                    predicted = obs['h_m']*(-1 if figure['kind'] == 'M' and name != '0_3_90' else 1)
                else:
                    predicted = obs['twist_asw_deg']*(-1 if figure['kind'] == 'M' else 1)
                rows.append(dict(figure=figure['path'], name=name, decoded_load=load, matched_script_load=nearest,
                                 plotted=plotted, predicted=predicted, difference=predicted-plotted,
                                 status='compared', cache_identity=digest, native=run))
                print(Path(figure['path']).name, name, nearest, predicted, plotted, flush=True)
    output = dict(status='ARCHIVED_CURVES_COMPARED_WITH_RETAINED_SETUP_LIMITATIONS', figures=figures, comparisons=rows,
                  modules=modules, scripts=scripts, upstream_revision=ns['REVISION'],
                  calibration='Actual vector grid positions with Figure 25 tick labels; no PostScript execution.',
                  matlab_rounding_assumption='5 significant digits for scalar |M|<1, confirmed by all three saved final input rows; intermediate files/version unavailable.',
                  full_suite_validated=False)
    (DEST/'isae-st3-static-eps.json').write_text(json.dumps(output, indent=2)+'\n')
    print('DONE', len(rows), flush=True)


if __name__ == '__main__':
    main()
