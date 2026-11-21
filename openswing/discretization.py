"""Portable beam-node settings and mandatory attachment stations.

These are OpenSwing analysis settings, not additional ASW geometry properties
or an implementation of the legacy .set file format. Counts mean intervals;
breaks and attachments may increase the final count.
"""
import numpy as np
from .point_objects import active_weight_items, analysis_weight_station


CURRENT_MESH_RECIPE = 'accurate-arc-v2'
CHORDAL_MESH_RECIPE = 'physical-breaks-v1'
LEGACY_MESH_RECIPE = 'all-breaks-v0'
MAX_INTERVALS = 1024


def checked_recipe(recipe):
    if recipe not in (CURRENT_MESH_RECIPE, CHORDAL_MESH_RECIPE, LEGACY_MESH_RECIPE):
        raise ValueError('Unknown mesh recipe; cannot reconstruct the saved discretization.')
    return recipe


def mesh_breaks(beam, recipe=CURRENT_MESH_RECIPE):
    return beam.mesh_breaks(include_shell=checked_recipe(recipe) == LEGACY_MESH_RECIPE)


def count(value):
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, (int, np.integer)) or not 4 <= value <= MAX_INTERVALS:
        raise ValueError(f'Use an integer from 4 to {MAX_INTERVALS} panels per beam.')
    return int(value)


def normalize(panels, model=None):
    if not isinstance(panels, dict):
        return count(panels)
    if set(panels)-{'default', 'beams'} or 'default' not in panels:
        raise ValueError('Mesh settings require default and optional beams fields.')
    default = count(panels['default'])
    beams = panels.get('beams', {})
    if not isinstance(beams, dict):
        raise ValueError('Mesh beams must map logical beam indices to settings.')
    result = {}
    for key, spec in beams.items():
        if isinstance(key, bool) or not str(key).isdigit() or int(key) < 1:
            raise ValueError('Mesh beam indices must be positive integers.')
        key = str(int(key))
        if key in result:
            raise ValueError('Duplicate mesh beam index.')
        if model is not None and int(key) not in {b.index for b in model.beams}:
            raise ValueError(f'Mesh settings reference missing beam {key}.')
        if not isinstance(spec, dict):
            raise ValueError(f'Beam {key}: mesh settings must be an object.')
        if 'nodes' in spec:
            if set(spec) != {'nodes'} or not isinstance(spec['nodes'], (list, tuple, np.ndarray)):
                raise ValueError(f'Beam {key}: explicit nodes cannot be combined with count or spacing.')
            raw = spec['nodes']
            if any(isinstance(v, (bool, np.bool_, str)) for v in raw):
                raise ValueError(f'Beam {key}: node stations must be finite numbers.')
            nodes = np.asarray(raw, dtype=float)
            if nodes.ndim != 1 or not 5 <= len(nodes) <= MAX_INTERVALS+1 or not np.all(np.isfinite(nodes)) or np.any(np.diff(nodes) <= 0):
                raise ValueError(f'Beam {key}: use 5 to {MAX_INTERVALS+1} finite, strictly increasing node stations including both endpoints.')
            result[key] = dict(nodes=nodes.tolist())
        else:
            if set(spec)-{'count', 'spacing', 'min_spacing'} or spec.get('spacing', 'cosine') not in ('cosine', 'modified-cosine', 'uniform', 'uniform-breaks'):
                raise ValueError(f'Beam {key}: use count and cosine, modified-cosine, uniform or uniform-breaks spacing, or explicit nodes.')
            result[key] = dict(count=count(spec.get('count', default)), spacing=spec.get('spacing', 'cosine'))
            if 'min_spacing' in spec:
                minimum = spec['min_spacing']
                if (isinstance(minimum, (bool, np.bool_)) or not isinstance(minimum, (int, float, np.integer, np.floating))
                        or not np.isfinite(minimum) or minimum < 0):
                    raise ValueError(f'Beam {key}: min_spacing must be a finite nonnegative length; zero disables the minimum.')
                result[key]['min_spacing'] = float(minimum)
    return dict(default=default, beams=result)


def beam_settings(beam, panels):
    settings = normalize(panels)
    if isinstance(settings, int):
        return dict(count=settings, spacing='cosine')
    return settings['beams'].get(str(beam.index), dict(count=settings['default'], spacing='cosine'))


def requirements(model, loads=(), *, mesh_recipe=CURRENT_MESH_RECIPE):
    """Keep each reason, including several attachments at the same station."""
    result = {b.index: [dict(t=float(t), kind='endpoint') for t in b.domain] +
              [dict(t=float(t), kind='property break / mirror plane') for t in mesh_breaks(b, mesh_recipe)] for b in model.beams}
    def add(beam, t, kind):
        if int(beam) not in result:
            raise ValueError(f'Attachment references missing beam {int(beam)}.')
        result[int(beam)].append(dict(t=float(t), kind=kind))
    for kind, offset in [('ground', 0), ('weight', 0), ('strut', 0), ('engine', 2), ('sensor', 1)]:
        rows = active_weight_items(model) if kind == 'weight' else enumerate(model.records.get(kind, []))
        for index, row in rows:
            station = analysis_weight_station(model, row) if kind == 'weight' else row[offset+1]
            add(row[offset], station, f'{kind} {index+1}')
    for i, row in enumerate(model.records.get('joint', []), 1):
        add(row[0], row[2], f'joint {i}'); add(row[1], row[3], f'joint {i}')
    for i, load in enumerate(loads, 1):
        add(load['beam'], load['t'], f'load {i}')
    return result


def report(model, meshes, panels, loads=()):
    by_recipe = {}
    beams = []
    for mesh in meshes:
        if mesh.mesh_recipe not in by_recipe:
            by_recipe[mesh.mesh_recipe] = requirements(model, loads, mesh_recipe=mesh.mesh_recipe)
        required = by_recipe[mesh.mesh_recipe]
        t = np.r_[mesh.t0, mesh.t1[-1]]
        s = np.r_[0., np.cumsum(mesh.length)]
        beams.append(dict(beam=mesh.beam.index, name=mesh.beam.name,
            settings=beam_settings(mesh.beam, panels), panels=len(mesh.tm),
            nodes=[dict(t=float(ti), s=float(si), fraction=float(si/s[-1]), theta=float(theta),
                        required=[r['kind'] for r in required[mesh.beam.index] if r['t'] == ti])
                   for ti, si, theta in zip(t, s, mesh.theta)]))
    return dict(settings=normalize(panels, model), beams=beams,
                coordinates='Undeformed material arc length; theta decreases from pi to zero. Rigid position jumps contain no beam material.')
