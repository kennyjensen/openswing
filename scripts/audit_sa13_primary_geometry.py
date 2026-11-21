"""Compare published bow radii with the retained SA-13 outline, without solving.

Neither coordinate interpretation recovers an original ASWING input. This
diagnostic has no acceptance gate and never updates the native comparison score.
"""
import argparse
import bisect
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PINS = {
    'reference/isae-sa13/naca-tm-574.pdf':
        'e96868752341afc58ba9c5cff5750ae47b56fb384e7537870bc2f1b629fb5423',
    'docs/validation/isae-sa13-sources.json':
        '439c59ead8599f99417ea53db7d146567cd6f4918e672c339ca0694f76499397',
    'reference/aswing-authoritative-20261108/isae-part-1-aerodynamics.pdf':
        'd610223c623f42b29ac2cc18a35042866a948429853ceae4a43a369bf4f1bc2b',
}
# Visually transcribed from NACA-TM-574, printed p.8 / PDF p.10.
# These are the final column (r_k/a)^2, NOT source strengths from p.9.
RADII_SQUARED = [(180, '0.478'), (170, '0.986'), (160, '1.335'),
                 (150, '1.610'), (140, '1.770'), (130, '1.851')]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    for name, expected in PINS.items():
        if digest(ROOT / name) != expected:
            raise ValueError(f'Source changed: {name}')
    decoded = json.loads((ROOT / 'docs/validation/isae-sa13-sources.json').read_text())
    case = next(c for c in decoded['cases'] if c['name'] == 'pressure')
    figure = (ROOT / 'reference/isae-validation' / decoded['revision'] / case['path'])
    if digest(figure) != case['sha256']:
        raise ValueError('Original pressure figure changed')
    pins = dict(PINS)
    pins[figure.relative_to(ROOT).as_posix()] = case['sha256']
    pins[Path(__file__).resolve().relative_to(ROOT).as_posix()] = digest(Path(__file__))
    table = case['outline']['normalized_table']
    stations = [row[0] for row in table]
    assert all(a < b for a, b in zip(stations, stations[1:]))
    primary = [dict(frame_m=frame, radius_squared_over_a_squared=token,
                    radius_m=10 * math.sqrt(float(token)))
               for frame, token in RADII_SQUARED]
    interpretations = []
    # Preserve both printed coordinates; do not choose an anchor by fit quality.
    for label, nose in [('text_p10_design_nose', 187.4),
                        ('figure3_nose_annotation', 197.5)]:
        stern = -12.5  # Figure 3, PDF p.30.
        length = nose - stern
        rows = []
        for point in primary:
            fraction = (nose - point['frame_m']) / length
            i = bisect.bisect_right(stations, fraction)
            assert 0 < i < len(table)
            left, right = table[i-1:i+1]
            radius = length * (left[1] + (right[1] - left[1])
                               * (fraction - left[0]) / (right[0] - left[0]))
            rows.append(dict(**point, fraction_from_nose=fraction,
                             outline_radius_m=radius,
                             signed_error_percent=100 * (radius / point['radius_m'] - 1)))
        interpretations.append(dict(name=label, nose_frame_m=nose,
                                    stern_frame_m=stern, length_m=length, rows=rows))
    result = dict(
        observed_utc=datetime.now(timezone.utc).isoformat(),
        status='CONDITIONAL_GEOMETRY_DIAGNOSTIC_NOT_NATIVE_VALIDATION',
        primary_radius_table=dict(source='NACA-TM-574', printed_page=8,
                                  pdf_page=10, line_source_length_a_m=10,
                                  rows=primary),
        coordinate_conflict=dict(text_design_nose_m=187.4,
                                 text_computed_nose_m=186.9,
                                 figure3_annotation_m=197.5,
                                 selected_interpretation=None),
        interpretations=interpretations,
        assumptions=[
            'Use the existing closed outline reconstruction; no new cap fit.',
            'Map each declared nose/stern pair to the entire normalized outline.',
            'Use equal scaling for axial and radial coordinates.',
            'Linearly interpolate the plotted radius samples for this diagnostic.',
            'The original ASWING model, sensor locations and exact geometry remain unavailable.',
            'Rounded primary radii and graph interpolation are not exact native inputs.',
        ],
        native_comparisons=dict(passed=0, total=612, unavailable=136,
                                completion_changed=False),
        solver_calls=0, sources=pins)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    # Preserve previous observations instead of silently replacing their date.
    with args.output.open('x') as handle:
        json.dump(result, handle, indent=2, allow_nan=False)
        handle.write('\n')
    print(json.dumps(dict(output=str(args.output), source_pins=len(pins),
                          primary_radius_points=len(primary), solver_calls=0)))


if __name__ == '__main__':
    main()
