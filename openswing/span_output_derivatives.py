"""Additional span-plot outputs from the existing physical output stencil.

No extra residual evaluations or solves. Signed strain/load outputs remain
those of the retained section C matrix; the UI forms absolute-value bounds
from their phase-dependent signed values.
"""


def add_span_outputs(output, snapshots, delta):
    for i, strip in enumerate(output['strips']):
        for key in ('length', 'normal_speed', 'normal_mach', 'relative_velocity'):
            strip[key] = delta([s['strips'][i].get(key) for s in snapshots])
    for i, section in enumerate(output['sections']):
        # moment_local is about the reference axis, whereas the 2D plot uses
        # bending about the tension axis and torsion about the elastic axis.
        section['moment_axes'] = delta([s['elements'][i].get('moment_axes') for s in snapshots])
        section['distributed_gravity_normal'] = delta([
            (s['elements'][i].get('distributed_gravity') or {}).get('normal') for s in snapshots])
    output['body_shoulders'] = [dict(beam=row['beam'], t=row['t'],
        force=delta([s['body_shoulders'][i]['force'] for s in snapshots]))
        for i, row in enumerate(snapshots[0].get('body_shoulders', []))]
