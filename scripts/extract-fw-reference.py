"""Digitize numerical facts from MIT's pinned flying-wing root-map PDF.

Fetch the publication separately with fetch-references.py. Its text consists
of vector paths: the trim table below was transcribed by visual inspection.
Root centers and plot calibration are extracted from the original paths, not
an image or OpenSwing results. Requires the optional test dependency pypdf.
"""
import hashlib
import json
from pathlib import Path
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
PDF = ROOT/'.reference/root_map_fw.pdf'
HASH = '5ed25ae70f30df3846fc7959175da349566ee1d4211658982f8a5ea3c2c331e5'
# point, elevation, F2, beta, alpha, ft/s, CL, CD, span efficiency
TABLE = '''
1   1.83  3.5 0  3.30 38 .956 .0245 1.036
2    .32  2.0 0  1.88 42 .783 .0214 1.042
3   -.89   .9 0   .82 46 .653 .0195 1.040
4  -1.91   .1 0  -.01 50 .552 .0183 1.030
5  -2.79  -.5 0  -.67 54 .473 .0175 1.010
6  -3.58 -1.0 0 -1.21 58 .410 .0169  .979
7  -3.94 -1.2 0 -1.44 60 .383 .0167  .959
8  -4.30 -1.4 0 -1.66 62 .359 .0166  .937
9  -4.64 -1.6 0 -1.85 64 .337 .0164  .913
10 -4.98 -1.7 0 -2.03 66 .317 .0163  .886
11 -5.31 -1.8 0 -2.20 68 .298 .0162  .858
12 -5.63 -2.0 0 -2.35 70 .281 .0161  .827
'''


def extract():
    if hashlib.sha256(PDF.read_bytes()).hexdigest() != HASH:
        raise ValueError('Reference PDF changed; inspect the figure and extraction layout again.')
    pages = PdfReader(PDF).pages
    assert len(pages) == 1
    groups, lines, transforms = [], [], []
    for args, operator in pages[0].get_contents().operations:
        if operator == b'cm':
            transforms.append(list(map(float, args)))
        elif operator == b'm':
            point = tuple(map(float, args))
        elif operator == b'l':
            end = tuple(map(float, args)); lines.append((point, end)); point = end
        elif operator == b'S':
            groups.append(lines); lines = []
    assert transforms == [[.1, 0., 0., .1, 0., 0.]] and len(groups) == 68
    assert groups[3] == [((820., 640.), (5140., 640.)), ((4275., 640.), (4275., 5824.))]
    horizontal = [a[1] for a, b in groups[0] if a[1] == b[1]]
    vertical = [a[0] for a, b in groups[0] if a[0] == b[0]]
    assert len(horizontal) == 13 and len(vertical) == 11
    # Successive dotted grid lines are 2.5/s apart. The first interval is
    # quantized by one stream unit; all remaining intervals are exactly 432.
    assert all(b-a == 432. for a, b in zip(horizontal[1:], horizontal[2:]))
    assert all(b-a == 432. for a, b in zip(vertical[1:], vertical[2:]))
    scale = 432./2.5
    rows = []
    for index, row in enumerate(TABLE.strip().splitlines()):
        values = list(map(float, row.split()))
        trim = dict(zip(('point', 'elevation_deg', 'control_2_deg', 'beta_deg', 'alpha_deg',
                         'speed_ft_s', 'CL', 'CD', 'efficiency'), values))
        trim['point'] = int(trim['point'])
        # Endpoints have separate marker and label strokes. Intermediate
        # speeds group nine markers into one stroke; each marker has ten lines.
        if index in (0, 11):
            first = 5 if index == 0 else 33
            markers = [groups[j] for j in range(first, first+17, 2)]
        else:
            path = groups[22+index]
            assert len(path) == 90
            markers = [path[k:k+10] for k in range(0, 90, 10)]
        centers = []
        for marker in markers:
            assert len(marker) == 10
            # The first line begins at the center and runs up to the polygon.
            start, end = marker[0]
            assert start[0] == end[0] and 10. < end[1]-start[1] < 13.
            centers.append(start)
        roots = [[(x-4275.)/scale, (y-640.)/scale] for x, y in centers]
        bff = [z for z in roots if z[0] > -3 and 15 < z[1] < 24]
        assert len(bff) == 1
        rows.append(dict(**trim, plotted_roots_per_s=roots, bff_root_per_s=bff[0],
                         marker_centers_stream_units=centers))
    return dict(
        description='Published flying-wing trim and selected root-map points; numerical facts digitized from the cited figure.',
        source=dict(url='https://web.mit.edu/drela/Public/web/aswing/root_map_fw.pdf',
                    sha256=HASH, bytes=PDF.stat().st_size, page=1),
        aircraft=dict(url='https://web.mit.edu/drela/Public/web/aswing/fw.asw',
                      sha256='a78626fa79b3f035b72c10512933e75c997b3ac6f884a5d401eacce2d29c7a5b'),
        extraction=dict(method='pypdf path centers; visually transcribed trim table',
                        origin_stream_units=[4275., 640.], units_per_inverse_second=scale,
                        estimated_root_digitization_uncertainty_per_s=.01,
                        trim_rounding_half_interval=dict(elevation_deg=.005, control_2_deg=.05,
                            beta_deg=.005, alpha_deg=.005, CL=.0005, CD=.00005, efficiency=.0005)),
        interpretation=dict(annotated_flutter_onset_ft_s=64.,
                            trim='Steady straight unpowered glide, inferred from elevation-alpha and CD/CL; not specified in the caption.',
                            limitations=['Only plotted roots are available; this is not a complete eigenspectrum.',
                                         'Mesh, interpolation, discretization, Mach setting and executable version are not specified.',
                                         'Digitization uncertainty does not include those configuration differences.']),
        points=rows)


if __name__ == '__main__':
    destination = ROOT/'docs/validation/fw-reference.json'
    destination.write_text(json.dumps(extract(), indent=2, allow_nan=False)+'\n')
    print(destination.relative_to(ROOT))
