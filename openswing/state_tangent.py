"""Analytic prescribed-geometry flight-state columns of the steady flow.

The six coordinates are fractional speed, alpha/beta in radians, and the
three normalized rates in BASE stability axes (steady eqs. 218–229).
Current-wind source/receiver locations, wakes, volume fields and PG tensors
are differentiated. K/F retains its declared zero-angle influence geometry.
"""
import numpy as np
from .aero import AnalysisError
from .circulation_tangent import cross
from .derivatives import stability_rotation
from .geometry import surface_frame
from .ground import GroundPlane, body_to_earth
from .gust import gust_field
from .volume_state_tangent import VolumeStateTangent
from .vortex_state_tangent import vortex_state_columns


STATE_PARAMETERS = ('u', 'alpha', 'beta', 'p', 'q', 'r')
STATE_UNITS = ('fractional speed V/V0', 'rad', 'rad',
               'p b/(2 V0)', 'q c/(2 V0)', 'r b/(2 V0)')


def lifting_wind_columns(meshes, direction, columns):
    """Differentiate all force/control points and bound endpoints, eqs.155–157."""
    arrays = {name: [] for name in ('a', 'b', 'hv', 'cp')}

    def offset(coefficient, span):
        parallel = span@direction
        transverse = direction-parallel[:, None]*span
        across = np.linalg.norm(np.cross(direction, span), axis=1)
        if np.any(across < 1e-6):
            raise AnalysisError('Lifting geometry aligns with the influence wind.')
        dacross = transverse@columns/across[:, None]
        return coefficient[:, None, None]*(columns[None, :, :]/across[:, None, None]
            -direction[None, :, None]*dacross[:, None, :]/across[:, None, None]**2)

    for mesh in meshes:
        beam = mesh.beam
        if not beam.lifting:
            continue
        t = mesh.tm
        chord = beam.value('chord', t)
        quarter = (.25-beam.value('Xax', t))*chord
        arrays['hv'].append(offset(quarter, mesh.frames[..., 1]))
        arrays['cp'].append(offset(quarter+beam.value('dCLda', t)*chord/(4*np.pi), mesh.frames[..., 1]))
        for name, tn, side, frame in (('a', mesh.t0, 'right', mesh.frame0),
                                       ('b', mesh.t1, 'left', mesh.frame1)):
            span = (surface_frame(beam, tn, side) if frame is None else frame)[..., 1]
            coefficient = (.25-beam.value('Xax', tn, side=side))*beam.value('chord', tn, side=side)
            arrays[name].append(offset(coefficient, span))
    return {name: np.concatenate(values) if values else np.empty((0, 3, columns.shape[1]))
            for name, values in arrays.items()}


def gust_spatial_columns(gust, positions, columns, condition):
    """Exact sampling derivative of the smooth prescribed gust primitives."""
    if not np.any(columns) or gust.kind in ('none', 'uniform'):
        return np.zeros_like(columns)
    rotation = body_to_earth(condition.attitude)
    earth = positions@rotation.T+condition.position_earth
    spatial = np.einsum('ij,njk->nik', rotation, columns)

    def gradient(field):
        if field.kind in ('none', 'uniform'):
            return np.zeros_like(columns)
        if field.kind == 'sum':
            return sum((gradient(child) for child in field.children), np.zeros_like(columns))
        if field.kind == 'cosine':
            s = ((earth-field.origin)@field.normal-field.speed*condition.time)/field.length
            slope = np.where((s > 0) & (s < 2), .5*np.pi*np.sin(np.pi*s)/field.length, 0.)
            phase = np.einsum('i,nik->nk', field.normal, spatial)*slope[:, None]
        elif field.kind == 'sinusoid':
            angle = earth@field.wavevector-field.omega*condition.time+field.phase
            phase = np.einsum('i,nik->nk', field.wavevector, spatial)*np.cos(angle)[:, None]
        else:
            raise AnalysisError('Analytic flight-state derivatives do not yet include spatial expression-gust gradients.')
        return field.amplitude[None, :, None]*phase[:, None, :]

    return np.einsum('ji,njk->nik', rotation, gradient(gust))


class StateFlow:
    """Direct flight-state columns, with geometry/material and Gamma fixed."""
    def __init__(self, model, meshes, fields, parameters):
        if (not isinstance(parameters, (list, tuple)) or not parameters or
                any(not isinstance(p, str) or p not in STATE_PARAMETERS for p in parameters)
                or len(set(parameters)) != len(parameters)):
            raise AnalysisError('State parameters must be distinct names from u, alpha, beta, p, q, r.')
        self.model, self.fields = model, fields
        self.data = data = fields.circulation_aero
        self.condition = condition = data['condition']
        count = len(parameters)
        self.sample = np.zeros((len(data['gamma']), count))
        self.speed_partial = np.zeros(count)
        self.direction_columns = np.zeros((3, count))
        self.rate_columns = np.zeros((3, count))
        a, b = np.deg2rad([condition.alpha, condition.beta])
        rate_map = stability_rotation(condition.alpha).T*(2*condition.speed/model.reference[0, [2, 1, 2]])
        for j, parameter in enumerate(parameters):
            if parameter == 'u':
                self.speed_partial[j] = condition.speed
            elif parameter == 'alpha':
                self.direction_columns[:, j] = [-np.sin(a)*np.cos(b), 0., np.cos(a)*np.cos(b)]
            elif parameter == 'beta':
                self.direction_columns[:, j] = [-np.cos(a)*np.sin(b), -np.cos(b), -np.sin(a)*np.sin(b)]
            else:
                self.rate_columns[:, j] = rate_map[:, 'pqr'.index(parameter)]
        self.wind = np.array([1., 0., 0.]) if condition.freeze_influences else data['direction']
        wind_columns = np.zeros_like(self.direction_columns) if condition.freeze_influences else self.direction_columns
        mach = condition.speed/data['sound_speed'] if condition.mach is None else condition.mach
        dmach = self.speed_partial/data['sound_speed'] if condition.mach is None else np.zeros(count)
        factor = 1/np.sqrt(1-mach**2)-1
        outer = np.outer(self.wind, self.wind)
        self.pg = np.eye(3)+factor*outer
        self.pg_columns = (outer[:, :, None]*(mach/(1-mach**2)**1.5*dmach)[None, None, :]
            +factor*(wind_columns[:, None, :]*self.wind[None, :, None]
                     +self.wind[:, None, None]*wind_columns[None, :, :]))
        self.wind_columns = wind_columns
        self.geometry_columns = lifting_wind_columns(meshes, self.wind, wind_columns)
        self.ground = GroundPlane.from_condition(condition)
        self.volume = VolumeStateTangent(model, meshes, self.wind, self.pg,
                                        wind_columns, self.pg_columns, self.ground)
        self.gust = gust_field(condition.gust)
        p = data['p']
        self.source_core = np.maximum(condition.wake_core_ratio*p['chord'], p['ds'])
        self.engines = []
        self.cache = {}

    def velocity(self, name, points):
        points = np.asarray(points)
        if name in self.cache:
            saved_points, result = self.cache[name]
            if not np.array_equal(points, saved_points):
                raise AnalysisError('Changed receiver layout in analytic state columns.')
            return result
        data, condition = self.data, self.condition
        count = self.sample.shape[1]
        movement = self.geometry_columns[name] if name in ('cp', 'hv') else np.zeros(points.shape+(count,))
        free = (data['direction'][:, None]*self.speed_partial[None, :]
                +condition.speed*self.direction_columns)
        result = np.broadcast_to(free, points.shape+(count,)).copy()
        result += cross(points-self.model.reference[3], self.rate_columns)
        result -= cross(np.asarray(condition.rates), movement)
        result += gust_spatial_columns(self.gust, points, movement, condition)
        p = data['p']
        physical = p['physical'] if name in ('cp', 'hv', 'axis') else None
        if isinstance(name, tuple) and name[0] in ('body', 'shoulder'):
            beam = next(b for b in self.model.beams if b.index == name[1])
            physical = np.full(len(points), beam.physical_index)
        core = self.source_core[None, :] if physical is None else np.where(
            physical[:, None] == p['physical'][None, :], 0., self.source_core[None, :])
        excluded = np.eye(len(p['t']), dtype=bool) if name in ('hv', 'axis') else None
        result += vortex_state_columns(points, p['a'], p['b'], self.wind, self.pg, core,
            data['gamma'], movement, self.geometry_columns['a'], self.geometry_columns['b'],
            self.wind_columns, self.pg_columns, self.ground, exclude_bound=excluded,
            baseline=self.fields.values['vortex', name])
        exclusions = {}
        if isinstance(name, tuple) and name[0] in ('body', 'shoulder'):
            exclusions['exclude_body'] = physical[0]
        if isinstance(name, tuple) and name[0] == 'point':
            exclusions['exclude_point'] = name[1]
        volume_columns = self.volume.velocity_columns(points, movement, **exclusions)
        result += condition.speed*volume_columns
        result += self.fields.values['volume', name].reshape(-1, 3)[:, :, None]*self.speed_partial[None, None, :]
        if not np.all(np.isfinite(result)):
            raise AnalysisError('Nonfinite analytic flight-state flow derivative.')
        self.cache[name] = (points.copy(), result)
        return result
