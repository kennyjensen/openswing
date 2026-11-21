"""Independent lifting-flow/virtual-work map for free elastic lifting branches.

Uses the previously checked independent section force equations, not production
physics. This extension adds distinct physical surfaces (steady Eq. 161) and
separates origin-relative influence wind from fixed Galilean atmospheric flow.
All nodal motion inputs are ABSOLUTE in that translating inertial frame.
No model construction, equilibrium solve or linearization occurs at import.
"""
import numpy as np

from elastic_fin_aero import AeroMap, norm
from elastic_fin_kinematics import exponential


class MultiSurfaceAero(AeroMap):
    def __init__(self, material, flow, physical, quadrature=32, **kwargs):
        super().__init__(material, flow, quadrature, **kwargs)
        self.physical = np.asarray(physical, dtype=int).copy()
        if self.physical.shape != (self.n,) or np.any(self.physical <= 0):
            raise ValueError('Each panel requires a positive physical surface ID')
        self.core_ratio = float(flow['wake_core_ratio'])
        if not np.isfinite(self.core_ratio) or self.core_ratio < 0:
            raise ValueError('Invalid declared core ratio')

    def geometry(self, sections, freestream=None):
        # Superclass geometry uses relative flow only to place the virtual
        # points, orient the wake and PG map, and normalize circulation rows.
        g = super().geometry(sections, freestream)
        g['influence_free'] = g['free']
        # Receiver equations subtract ABSOLUTE section velocities, so adding
        # the origin-relative flow here would subtract translation twice.
        g['free'] = self.free
        chord_core = self.core_ratio*self.material['chord']
        g['source_core'] = np.where(g['ds'].real >= chord_core.real,
                                    g['ds'], chord_core)
        return g

    def _regularized_integral(self, relative, direction, length, cores, diag):
        result = np.zeros_like(relative, dtype=np.result_type(
            relative, direction, cores, 1. if length is None else length))
        smooth = np.asarray(cores).real > 0
        if np.any(~smooth):
            result[~smooth] = self._line_integral(relative[~smooth], direction,
                                                length, diag)
        if np.any(smooth):
            r = relative[smooth]
            z = np.sum(r*direction, axis=1)
            radial = r-z[:, None]*direction
            q2 = np.sum(radial*radial, axis=1)+cores[smooth]**2
            q = np.sqrt(q2)
            lo = np.arctan(-z/q)
            hi = np.full(len(z), np.pi/2) if length is None else np.arctan((length-z)/q)
            half = (hi-lo)/2
            theta = (hi+lo)[:, None]/2+half[:, None]*self.nodes
            integral = np.sum(np.cos(theta)*self.weights, axis=1)*half/q2
            result[smooth] = np.cross(direction, radial)*integral[:, None]/(4*np.pi)
            diag['regularized_integrals'] += int(np.sum(smooth))
        return result

    def _field(self, g, receiver):
        self.field_integrations += 1
        pg, targets = g['pg'], g[receiver]
        H = np.zeros((self.n, self.n, 3), dtype=np.result_type(
            targets, g['a'], g['b'], pg, g['wind'], g['source_core']))
        diag = dict(own_bound_excluded=0, direct_disjoint_finite=0,
                    direct_upstream_wake=0, theta_integrals=0,
                    minimum_direct_clearance=float('inf'),
                    minimum_theta_radius=float('inf'), regularized_integrals=0,
                    same_physical_surface_core=0.)
        wake = pg@g['wind']; wake = wake/norm(wake)
        for j in range(self.n):
            segment = pg@(g['b'][j]-g['a'][j]); length = norm(segment)
            if length.real <= 0:
                raise ValueError('Zero-length bound segment')
            tangent = segment/length
            for kind, origin, direction, extent, sign in (
                    ('bound', g['a'][j], tangent, length, 1.),
                    ('wake', g['b'][j], wake, None, 1.),
                    ('wake', g['a'][j], wake, None, -1.)):
                ids = np.arange(self.n)
                if kind == 'bound' and receiver in ('hv', 'axis'):
                    ids = ids[ids != j]; diag['own_bound_excluded'] += 1
                if not len(ids):
                    continue
                cores = np.where(self.physical[ids] == self.physical[j],
                                 0., g['source_core'][j])
                relative = (targets[ids]-origin)@pg.T
                value = self._regularized_integral(relative, direction, extent, cores, diag)
                H[ids, j] += sign*(value@pg)
        for name in ('minimum_direct_clearance', 'minimum_theta_radius'):
            if not np.isfinite(diag[name]):
                diag[name] = None
        return H, diag

    def fields(self, g):
        # Unlike the single-surface cache, the spacing-limited core is live.
        keys = ('a', 'b', 'cp', 'hv', 'axis', 'pg', 'wind', 'source_core')
        key = tuple((k, np.asarray(g[k], dtype=np.complex128).shape,
                     np.asarray(g[k], dtype=np.complex128).tobytes()) for k in keys)
        if key in self.cache:
            self.cache.move_to_end(key)
            return self.cache[key]
        self.field_sets += 1
        fields, diagnostics = {}, {}
        for receiver in ('cp', 'hv', 'axis'):
            fields[receiver], diagnostics[receiver] = self._field(g, receiver)
        entry = dict(fields=fields, diagnostics=diagnostics)
        self.cache[key] = entry
        while len(self.cache) > self.cache_entries:
            self.cache.popitem(last=False)
        if self.recorder is not None:
            self.recorder(g, fields, diagnostics)
        return entry


class FreeFeedback:
    """x=[carrier translation/rotation, absolute nodal displacement/rotation].

    Nodal wrench used for mechanics is inertial. Reported strip forces/couples
    and wing/fin/global wrenches are in carrier body axes, moments about its
    current origin. That output transformation retains the loaded-base terms.
    """
    def __init__(self, sampler, aero, gamma, *, lag=True):
        self.sampler, self.aero = sampler, aero
        self.gamma = np.asarray(gamma, dtype=float)
        self.nn, self.ng = sampler.nn, len(self.gamma)
        self.size = 6*(1+self.nn)
        self.lag = bool(lag)
        self.calls = 0

    def evaluate(self, q, v, a, gamma, gamma_dot, control):
        self.calls += 1
        q, v, a = (np.asarray(x).reshape(self.size) for x in (q, v, a))
        section = self.sampler.sample(q[6:], v[6:], a[6:])
        value = self.aero.evaluate(section, gamma, gamma_dot, control, lag=self.lag,
                                   freestream=self.aero.free-v[:3])
        R = exponential(q[3:6])
        forces = value['family_forces']@R
        moments = value['family_moments_axis']@R
        positions = (section['rm']-q[:3])@R
        w = np.concatenate((forces, moments+np.cross(positions, forces)), axis=2)
        ids = sorted(set(self.aero.physical))
        groups = [np.sum(w[:, self.aero.physical == i], axis=1) for i in ids]
        groups.append(np.sum(w, axis=1))
        output = dict(residual=value['residual'],
                      nodal_wrench=self.sampler.transfer(section, value['strip_force'],
                                                         value['strip_moment_axis']),
                      wrenches=np.stack(groups, axis=1),
                      family_forces=forces, family_moments_axis=moments,
                      cp_velocity=value['cp_velocity']@R,
                      velocity=value['velocity']@R,
                      axis_velocity=value['axis_velocity']@R)
        return output

    def base(self):
        zero = np.zeros(self.size)
        return self.evaluate(zero, zero, zero, self.gamma, np.zeros(self.ng), 0.)

    def derivatives(self, epsilon):
        if not 0 < epsilon < 1e-6:
            raise ValueError('Complex-step width must be frozen and positive')
        baseline, blocks = self.base(), {}
        sizes = dict(q=self.size, v=self.size, a=self.size,
                     gamma=self.ng, gamma_dot=self.ng, control=1)
        for name, size in sizes.items():
            outputs = {k: np.zeros((value.size, size)) for k, value in baseline.items()}
            # Absolute nodal inputs carry all motion. Only output frame pose
            # and influence-wind origin velocity add carrier dependencies.
            active = (list(range(6, size))+list(range(6)) if name == 'q' else
                      list(range(6, size))+list(range(3)) if name == 'v' else
                      range(6, size) if name == 'a' else range(size))
            for j in active:
                args = dict(q=np.zeros(self.size, complex), v=np.zeros(self.size, complex),
                            a=np.zeros(self.size, complex), gamma=self.gamma.astype(complex),
                            gamma_dot=np.zeros(self.ng, complex), control=np.zeros(1, complex))
                args[name][j] += 1j*epsilon
                value = self.evaluate(args['q'], args['v'], args['a'], args['gamma'],
                                      args['gamma_dot'], args['control'][0])
                for key in outputs:
                    outputs[key][:, j] = np.imag(value[key]).ravel()/epsilon
            blocks[name] = outputs
        return dict(blocks=blocks, shapes={k: v.shape for k, v in baseline.items()},
                    base=baseline, epsilon=epsilon, evaluations=self.calls,
                    fields=self.aero.field_integrations, field_sets=self.aero.field_sets)
