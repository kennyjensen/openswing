"""Physical fields for the corrected, rigid UA-1 full-history comparison.

Same scales and 2e-8 limits as the preceding expanded short-runtime study.
The independently prescribed rigid wing must have zero local nodal motion.
"""
from isae_ua1_stall_browser import physical_row as aerodynamic_row, flatten

LOCAL_FIELDS = ('local_velocity', 'local_rates', 'local_acceleration',
                'local_rate_derivative')
RIGID_LIMIT = 2e-8


def divide(value, scale):
    return [divide(v, scale) for v in value] if isinstance(value, list) else value/scale


def physical_row(sample, section):
    row = aerodynamic_row(sample, section)
    qs = .5*1.225*section['speed']**2*200000
    qm = qs*200000  # Structural moment scale: qS times span, unit chord.
    network = sample['restart']['state']['network']
    row.update(moment_coefficient=divide(sample['moment'], qm),
        node_positions=network['positions'], node_rotations=network['rotations'],
        internal_force_coefficient=divide(network['internal_force'], qs),
        internal_moment_coefficient=divide(network['internal_moment'], qm),
        reactions=[v/(qs if i < 3 else qm) for i, v in enumerate(network['reactions'])])
    row.update({key: sample[key] for key in LOCAL_FIELDS})
    row.update({'frame_'+key: value for key, value in sample['frame'].items()})
    for value in row.values():
        list(flatten(value))
    for key in LOCAL_FIELDS:
        maximum = max(map(abs, flatten(row[key])), default=0.)
        assert maximum <= RIGID_LIMIT, ('Rigid local motion', sample['time'], key, maximum)
    return row


def comparison_fields(row):
    return tuple(k for k in row if k not in ('time', 'order', 'residual'))
