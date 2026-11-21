"""Physical ROM outputs with explicit units and mesh-bound sample selections."""
from copy import deepcopy
from numbers import Real
import json
import numpy as np
from .aero import AnalysisError
from .feedback import CHANNELS, ANGLE_CHANNELS, channel, measurements
from .network import network_result


# name, units, component axes. Empty axes denote a scalar.
FIELDS = {
    'nodes': {
        'displacement': ('Displacement', 'input L', 'xyz'),
        'rotation': ('Spatial rotation about loaded base', 'rad', 'xyz'),
        'velocity': ('Local elastic velocity', 'input L/T', 'xyz'),
        'rates': ('Local elastic rotation rate', 'rad/input T', 'xyz'),
    },
    'sections': {
        'force_local': ('Section force', 'input F', 'csn'),
        'moment_local': ('Section moment', 'input F L', 'csn'),
        'strain': ('Mechanical strain', 'dimensionless', 'csn'),
        'curvature_change': ('Curvature change', '1/input L', 'csn'),
        'axial_strain_tension': ('Axial strain at tension axis', 'dimensionless', ''),
        'shell_strain': ('Signed shell strain', 'dimensionless', ''),
        'shell_shear_stress': ('Signed shell shear stress', 'input F/L^2', ''),
    },
    'strips': {
        'force': ('Aerodynamic strip force', 'input F', 'xyz'),
        'moment': ('Aerodynamic strip moment', 'input F L', 'xyz'),
        'circulation': ('Circulation', 'input L^2/T', ''),
        'cl': ('Section lift coefficient', 'dimensionless', ''),
        'apparent_force': ('Strip apparent-mass force', 'input F', 'xyz'),
        'cm': ('Section pitching moment coefficient', 'dimensionless', ''),
        'f_aero': ('Normal aerodynamic load per length', 'input F/L', ''),
        'f_reac': ('Normal distributed inertial load per length', 'input F/L', ''),
        'da_eff': ('Elastic incidence change', 'rad', ''),
    },
    'global': {},
}
for key in ('force', 'moment', 'moment_origin', 'applied_force', 'applied_moment', 'support_force', 'support_moment',
            'surface_force', 'distributed_aero_force', 'distributed_aero_moment', 'circulation_rate_force',
            'distributed_aero_moment_origin', 'circulation_rate_moment', 'body_force', 'engine_force', 'engine_moment', 'apparent_force', 'apparent_moment'):
    FIELDS['global'][key] = (key.replace('_', ' ').capitalize(), 'input F L' if 'moment' in key else 'input F', 'xyz')
for key in ('CL', 'CD', 'CDi', 'CDi_near', 'CLi', 'CYi', 'CDp', 'CDam', 'CDbody', 'CDeng', 'CY', 'Cl', 'Cm', 'Cm_origin', 'Cn'):
    FIELDS['global'][key] = (key, 'dimensionless', '')
FIELDS['global']['Cm'] = ('Pitching moment coefficient about file reference', 'dimensionless', '')
FIELDS['global']['Cm_origin'] = ('Pitching moment coefficient about body origin', 'dimensionless', '')

SAMPLING = {'nodes': 'Material node; rotations are spatial increments about the loaded base, with zero base value.',
            'sections': 'Constitutive material midpoint, local c/s/n axes; no interpolation across load or property jumps.',
            'strips': 'Aerodynamic strip sample; force and moment vectors use body axes. Densities retain the current-length normalization.',
            'global': 'Global report quantity; vectors use body axes. Moment fields use the file moment reference, except fields ending in _origin, which use the body origin.'}


def rows(snapshot, group):
    return snapshot.get('elements' if group == 'sections' else group, [])


def field_value(row, key):
    if key == 'shell_strain':
        return row.get('shell', {}).get('axial_strain')
    if key == 'shell_shear_stress':
        return row.get('shell', {}).get('shear_stress')
    return row.get(key)


def available(value):
    return value is not None and bool(np.all(np.isfinite(value)))


def output_catalog(snapshot):
    """Compact field/station catalog; unavailable base quantities stay absent."""
    fields = [dict(group=group, key=key, label=label, unit=unit, components=list(axes))
              for group, entries in FIELDS.items() for key, (label, unit, axes) in entries.items()]
    stations = {}
    for group in ('nodes', 'sections', 'strips'):
        stations[group] = [dict(index=i, beam=row['beam'], t=row['t'],
            available=list(FIELDS[group]) if group == 'nodes' else
            [key for key in FIELDS[group] if available(field_value(row, key))])
            for i, row in enumerate(rows(snapshot, group))]
    return dict(fields=fields, stations=stations, sampling=SAMPLING.copy(),
                global_available=[key for key in FIELDS['global'] if available(snapshot.get(key))])


def selector(spec, snapshot):
    """Resolve an exact sample. A changed mesh must not retarget a saved output."""
    if not isinstance(spec, dict) or set(spec)-{'group', 'key', 'component', 'index', 'beam', 't'}:
        raise AnalysisError('ROM physical output requires group, key, optional component, and an exact index/beam/t for sampled fields.')
    group, key = spec.get('group'), spec.get('key')
    if not isinstance(group, str) or not isinstance(key, str) or key not in FIELDS.get(group, {}):
        raise AnalysisError('Unknown ROM physical output group or field.')
    label, unit, axes = FIELDS[group][key]
    component = spec.get('component')
    if (axes and (type(component) is not int or not 0 <= component < 3)) or (not axes and component is not None):
        raise AnalysisError('ROM vector outputs require component 0, 1 or 2; scalar outputs have no component.')
    selected = dict(group=group, key=key)
    suffix = '' if component is None else '.'+axes[component]
    if component is not None:
        selected['component'] = component
    name = group+'.'+key+suffix
    if group == 'global':
        if any(k in spec for k in ('index', 'beam', 't')):
            raise AnalysisError('Global ROM outputs do not have a sample index, beam or t.')
        value = snapshot.get(key)
    else:
        index, beam, t = spec.get('index'), spec.get('beam'), spec.get('t')
        samples = rows(snapshot, group)
        if (type(index) is not int or not 0 <= index < len(samples) or type(beam) is not int
                or isinstance(t, bool) or not isinstance(t, Real) or not np.isfinite(t)):
            raise AnalysisError('Sampled ROM output needs a valid zero-based index, integer beam and finite material t.')
        row = samples[index]
        if row['beam'] != beam or abs(row['t']-t) > 64*np.finfo(float).eps*max(1., abs(row['t']), abs(t)):
            raise AnalysisError('ROM output sample no longer matches its beam and material t; reselect it on the current mesh.')
        selected.update(index=index, beam=beam, t=float(row['t']))
        name += f" [{index}] beam {beam} t {row['t']:.17g}"
        value = 0. if group == 'nodes' else field_value(row, key)
    if not available(value):
        raise AnalysisError(f'ROM output {name} is unavailable at the base state; no derivative or zero value is invented.')
    metadata = dict(name=name, unit=unit, selector=selected, label=label+((' '+axes[component]) if axes else ''),
                    sampling=SAMPLING[group])
    if group == 'strips' and key in snapshot.get('section_output_definitions', {}):
        metadata['definition'] = snapshot['section_output_definitions'][key]
    return metadata


class MeasurementOutputs:
    """Legacy named measurements and explicit physical-output selectors."""
    def __init__(self, system, specifications):
        if not isinstance(specifications, (list, tuple)) or not specifications:
            raise AnalysisError('ROM outputs must be a nonempty list of distinct measurements or physical selectors.')
        self.system = system
        self.snapshot = system.base_report() if any(isinstance(s, dict) for s in specifications) else None
        self.specifications = deepcopy(list(specifications))
        self.keys, self.metadata = [], []
        for spec in self.specifications:
            if isinstance(spec, str):
                key = channel(spec, system.network.model)[0]
                self.keys.append(key)
                self.metadata.append(dict(name=spec, unit=CHANNELS[key][2]))
            else:
                self.keys.append(None)
                self.metadata.append(selector(spec, self.snapshot))
        identities = [json.dumps(item.get('selector', item['name']), sort_keys=True) for item in self.metadata]
        if len(set(identities)) != len(identities):
            raise AnalysisError('ROM outputs must be distinct; the same physical sample cannot be selected twice.')
        self.names = [item['name'] for item in self.metadata]
        self.base = self.values(np.zeros(system.size), np.zeros(system.size))

    def values(self, vector, rate, forcing=None):
        system, network = self.system, self.system.network
        _, state, options = system.residual(vector, rate, detail=True, forcing=forcing)
        measured = {}
        if any(key is not None for key in self.keys):
            _, data = network.residual(state.x, detail=True, **options)
            measured = measurements(network, state, data)
        snapshot = None
        if any(item.get('selector', {}).get('group') not in (None, 'nodes') for item in self.metadata):
            snapshot = network_result(network, state.x, sensor_frame=dict(body_to_earth=state.orientation,
                position_earth=state.position, velocity_origin_body=state.U), **options)
        values = []
        for item, key in zip(self.metadata, self.keys):
            if key is not None:
                value = measured.get(item['name'])
            else:
                spec = item['selector'];group = spec['group'];field = spec['key']
                if group == 'global':
                    value = snapshot.get(field)
                elif group == 'nodes':
                    i = self.snapshot['nodes'][spec['index']]['index']
                    value = {'displacement': state.r[i]-network.rj[i],
                             'rotation': vector[:6*network.nn].reshape(network.nn, 6)[i, 3:],
                             'velocity': state.u[i], 'rates': state.w[i]}[field]
                else:
                    value = field_value(rows(snapshot, group)[spec['index']], field)
                if value is not None and 'component' in spec:
                    value = value[spec['component']]
            if value is None or not np.isfinite(value):
                raise AnalysisError(f"ROM output {item['name']} is undefined at this state; check its base availability and physical sample.")
            values.append(value)
        return np.asarray(values)

    def tangent(self, vector, rate, step, forcing=None, input_scale=1.):
        if forcing is None:
            # Homogeneous directions can be rescaled. Keep tiny initial-spectrum
            # outputs and loaded structural increments above cancellation noise.
            norm = max(float(np.max(abs(vector))), min(float(np.max(abs(rate)))/self.system.W, 1.))
            h = step/(norm if norm else 1.)
        else:
            h = min(step*input_scale, step/max(np.max(abs(vector)), np.max(abs(rate))/self.system.W, 1e-30))
        plus = self.values(h*vector, h*rate, None if forcing is None else forcing(0, h))
        minus = self.values(-h*vector, -h*rate, None if forcing is None else forcing(0, -h))
        delta = plus-minus
        for i, key in enumerate(self.keys):
            if key in ANGLE_CHANNELS:
                delta[i] -= 360*np.round(delta[i]/360)
        return delta/(2*h)
