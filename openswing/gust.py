"""Prescribed Earth-coordinate gusts (unsteady formulation, equations 66–68).

Fields are data, not executable user code. Coordinates use the .asw input L
and T units; velocities use L/T. This JSON format is an OpenSwing extension.
gust_file converts the verified straight type-5 numeric input layout into it;
the remaining VGUSTE parameter catalog is not inferred.
"""
import ast
from functools import lru_cache
import json
import operator
import numpy as np
from .ground import vector3, body_to_earth


_FUNCTIONS = dict(sin=np.sin, cos=np.cos, tanh=np.tanh, exp=np.exp,
                  sqrt=np.sqrt, abs=np.abs, minimum=np.minimum,
                  maximum=np.maximum, clip=np.clip, where=np.where)
_ARITY = dict(sin=1, cos=1, tanh=1, exp=1, sqrt=1, abs=1,
              minimum=2, maximum=2, clip=3, where=3)
_BINARY = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
           ast.Div: np.divide, ast.Pow: np.power}
_COMPARE = {ast.Lt: operator.lt, ast.LtE: operator.le, ast.Gt: operator.gt,
            ast.GtE: operator.ge, ast.Eq: operator.eq, ast.NotEq: operator.ne}


def _expression(source):
    if not isinstance(source, str) or len(source) > 2048:
        raise ValueError('Gust expressions must be strings of at most 2048 characters.')
    try:
        tree = ast.parse(source, mode='eval')
    except (SyntaxError, RecursionError) as exc:
        raise ValueError('Invalid gust expression.') from exc
    if sum(1 for _ in ast.walk(tree)) > 256:
        raise ValueError('Gust expression is too complex.')

    def compile_node(n):
        if isinstance(n, ast.Constant) and type(n.value) in (int, float):
            value = float(n.value)
            if not np.isfinite(value):
                raise ValueError('Gust constants must be finite.')
            return lambda env: value
        if isinstance(n, ast.Name) and n.id in ('x', 'y', 'z', 't', 'pi', 'e'):
            return lambda env: env[n.id]
        if isinstance(n, ast.UnaryOp) and isinstance(n.op, (ast.UAdd, ast.USub)):
            a = compile_node(n.operand)
            return (lambda env: -a(env)) if isinstance(n.op, ast.USub) else a
        if isinstance(n, ast.BinOp) and type(n.op) in _BINARY:
            a, b, op = compile_node(n.left), compile_node(n.right), _BINARY[type(n.op)]
            return lambda env: op(a(env), b(env))
        if isinstance(n, ast.Compare) and len(n.ops) == 1 and type(n.ops[0]) in _COMPARE:
            a, b, op = compile_node(n.left), compile_node(n.comparators[0]), _COMPARE[type(n.ops[0])]
            return lambda env: op(a(env), b(env))
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in _FUNCTIONS:
            if n.keywords or len(n.args) != _ARITY[n.func.id]:
                raise ValueError(f'Gust function {n.func.id} requires {_ARITY[n.func.id]} positional arguments.')
            args, fn = [compile_node(a) for a in n.args], _FUNCTIONS[n.func.id]
            return lambda env: fn(*(a(env) for a in args))
        raise ValueError('Unsupported gust expression: use x, y, z, t, numeric arithmetic and the documented functions.')
    return compile_node(tree.body)


def _scalar(value, name):
    if isinstance(value, bool) or not np.isscalar(value):
        raise ValueError(f'Gust {name} must be a finite number.')
    value = float(value)
    if not np.isfinite(value):
        raise ValueError(f'Gust {name} must be a finite number.')
    return value


class GustField:
    def __init__(self, spec, depth=0):
        if not isinstance(spec, dict) or depth > 4:
            raise ValueError('Gust must be a JSON object with at most four nested sums.')
        self.spec = spec
        self.kind = spec.get('type', 'none')
        allowed = dict(none=(), uniform=('velocity',),
                       cosine=('amplitude', 'origin', 'normal', 'length', 'speed'),
                       sinusoid=('amplitude', 'mean', 'wavevector', 'omega', 'phase'),
                       expression=('components',), sum=('fields',))
        if self.kind not in allowed:
            raise ValueError(f'Unsupported gust type: {self.kind}.')
        extra = set(spec)-{'type'}-set(allowed[self.kind])
        if extra:
            raise ValueError('Unrecognized gust parameters: '+', '.join(sorted(extra)))
        self.children = []
        if self.kind == 'uniform':
            self.mean = vector3(spec.get('velocity'), 'Gust velocity')
        elif self.kind in ('cosine', 'sinusoid'):
            self.amplitude = vector3(spec.get('amplitude'), 'Gust amplitude')
            if self.kind == 'cosine':
                self.origin = vector3(spec.get('origin', (0, 0, 0)), 'Gust origin')
                self.normal = vector3(spec.get('normal', (-1, 0, 0)), 'Gust normal')
                norm = np.linalg.norm(self.normal)
                if norm < 1e-12:
                    raise ValueError('Gust normal must be nonzero.')
                self.normal = self.normal/norm
                self.length = _scalar(spec.get('length'), 'gradient length')
                if self.length <= 0:
                    raise ValueError('Gust gradient length must be positive.')
                self.speed = _scalar(spec.get('speed', 0), 'propagation speed')
            else:
                self.mean = vector3(spec.get('mean', (0, 0, 0)), 'Gust mean')
                self.wavevector = vector3(spec.get('wavevector'), 'Gust wavevector')
                self.omega = _scalar(spec.get('omega', 0), 'angular frequency')
                self.phase = _scalar(spec.get('phase', 0), 'phase')
        elif self.kind == 'expression':
            components = spec.get('components')
            if not isinstance(components, list) or len(components) != 3:
                raise ValueError('Gust components must be three expression strings.')
            self.functions = [_expression(s) for s in components]
        elif self.kind == 'sum':
            fields = spec.get('fields')
            if not isinstance(fields, list) or not 1 <= len(fields) <= 16:
                raise ValueError('A gust sum requires 1 to 16 fields.')
            self.children = [GustField(s, depth+1) for s in fields]

    def velocity(self, positions, time=0.):
        p = np.asarray(positions, dtype=float)
        if p.ndim == 0 or p.shape[-1] != 3 or not np.all(np.isfinite(p)):
            raise ValueError('Gust sample positions must be finite xyz vectors.')
        time = _scalar(time, 'time')
        with np.errstate(all='ignore'):
            if self.kind == 'none':
                value = np.zeros(p.shape)
            elif self.kind == 'uniform':
                value = np.broadcast_to(self.mean, p.shape).copy()
            elif self.kind == 'cosine':
                s = ((p-self.origin)@self.normal-self.speed*time)/self.length
                # Zero outside the compact slab; maximum at distance H.
                value = (.5*(1-np.cos(np.pi*np.clip(s, 0, 2))))[..., None]*self.amplitude
            elif self.kind == 'sinusoid':
                phase = p@self.wavevector-self.omega*time+self.phase
                value = self.mean+np.sin(phase)[..., None]*self.amplitude
            elif self.kind == 'expression':
                env = dict(x=p[..., 0], y=p[..., 1], z=p[..., 2], t=time, pi=np.pi, e=np.e)
                value = np.stack([np.broadcast_to(f(env), p.shape[:-1]) for f in self.functions], axis=-1)
            else:
                value = sum((f.velocity(p, time) for f in self.children), np.zeros(p.shape))
        if not np.all(np.isfinite(value)):
            raise ValueError('Gust expression or field produced a nonfinite velocity at an aircraft/sample location.')
        return np.asarray(value, dtype=float)

    def phase_change(self, before, after, step):
        """Largest resolved phase travel, even when both endpoints are outside.

        This is a sampling guard, not an integration-error estimate. Expressions
        have no known length scale and require user time/mesh refinement.
        """
        delta = np.asarray(after)-before
        if self.kind == 'cosine':
            return float(np.max(abs(delta@self.normal-self.speed*step), initial=0)*np.pi/self.length)
        if self.kind == 'sinusoid':
            return float(np.max(abs(delta@self.wavevector-self.omega*step), initial=0))
        return max((f.phase_change(before, after, step) for f in self.children), default=0.)

    def body_velocity(self, positions, condition):
        rotation = body_to_earth(condition.attitude)
        earth = np.asarray(positions)@rotation.T+condition.position_earth
        return self.velocity(earth, condition.time)@rotation

    def report(self, condition, reference):
        rotation = body_to_earth(condition.attitude)
        point = rotation@np.asarray(reference)+condition.position_earth
        velocity = self.velocity(point, condition.time)
        return dict(type=self.kind, time=condition.time, specification=json.loads(json.dumps(self.spec)),
                    reference_position_earth=point.tolist(), reference_velocity_earth=velocity.tolist(),
                    reference_velocity_body=(rotation.T@velocity).tolist())


@lru_cache(maxsize=32)
def _cached(specification):
    return GustField(json.loads(specification))


def gust_field(spec=None):
    try:
        key = json.dumps({'type': 'none'} if spec is None else spec, sort_keys=True, allow_nan=False)
    except (ValueError, TypeError, RecursionError) as exc:
        raise ValueError('Gust specification must contain finite JSON data.') from exc
    if len(key) > 32768:
        raise ValueError('Gust specification exceeds 32768 characters.')
    return _cached(key)


LIMITATIONS = [
    'Gusts are prescribed Earth-coordinate velocities. Coefficients and PG/wake alignment retain the still-atmosphere aircraft-velocity reference.',
    'The published local apparent-mass formulas use aircraft acceleration; no additional ambient-pressure-gradient term is included. Circulation lag is empirical, not an exact Sears gust transfer function.',
    'Volume-source strengths remain based on the reference freestream; gust scattering by bodies, wall correction of the gust itself, and gust-driven wake convection are not modeled.',
    'Cosine/sinusoid time steps limit sampled phase travel to pi/8. Expressions require explicit time and mesh refinement; this guard is not a temporal error estimate.'
]
