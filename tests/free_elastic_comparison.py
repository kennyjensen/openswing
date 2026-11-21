"""Complete physical output groups for the independent free-elastic fixture."""
import numpy as np


def groups(outputs, intervals, length_scale):
    """31 groups, preserving every component and complex phase in each group.

    Translations are divided by one declared length before grouping with
    rotations. Moments are divided by that same length before grouping with
    forces. No component is dropped because its reference response is small.
    """
    o, n, L = outputs, intervals, length_scale
    result = {}
    for field in ('node_body_motion', 'node_absolute_motion'):
        for j, name in enumerate(('wing', 'fin')):
            value = o[field][j*(n+1):(j+1)*(n+1)].copy()
            value[:, :3] /= L
            result[field+'_'+name] = value
    value = o['frame_motion'].copy(); value[:3] /= L
    result['frame_motion'] = value
    for key in ('frame_velocity', 'frame_rates'):
        result[key] = o[key]
    for j, name in enumerate(('wing', 'fin')):
        for key in ('gamma', 'velocity'):
            result[key+'_'+name] = o[key][j*n:(j+1)*n]
    for k, family in enumerate(('total', 'rate', 'apparent', 'remainder')):
        for j, name in enumerate(('wing', 'fin', 'global')):
            value = o['wrenches'][k, j].copy(); value[3:] /= L
            result['wrench_'+family+'_'+name] = value
        for j, name in enumerate(('wing', 'fin')):
            force = o['family_forces'][k, j*n:(j+1)*n]
            moment = o['family_moments_axis'][k, j*n:(j+1)*n]/L
            result['strip_'+family+'_'+name] = np.concatenate((force, moment), axis=1)
    return result


def errors(actual, expected, intervals, length_scale):
    left, right = (groups(value, intervals, length_scale) for value in (actual, expected))
    if left.keys() != right.keys() or len(left) != 31:
        raise ValueError('Expected all 31 physical groups')
    records = []
    for name, reference in right.items():
        candidate = left[name]
        if candidate.shape != reference.shape or not np.all(np.isfinite(candidate)):
            raise ValueError('Invalid physical group '+name)
        for column in range(2):
            scale = float(np.max(abs(reference[..., column])))
            absolute = float(np.max(abs(candidate[..., column]-reference[..., column])))
            records.append(dict(group=name, input=column, absolute=absolute,
                                relative=None if scale == 0 else absolute/scale))
    return records
