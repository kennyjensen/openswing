"""Pointwise or sine-series circulation, ASWING steady eqs. 63, 150, 201.

The basis and test functions use the undeformed material Glauert coordinate.
Physical horseshoes and loads retain one sample per structural interval.
"""
from copy import deepcopy
import numpy as np


def mode_settings(modes):
    if modes is None:modes = {}
    if not isinstance(modes, dict):raise ValueError('Circulation modes must map lifting-beam indices to integer counts; zero selects pointwise values.')
    requested = {}
    for key, count in modes.items():
        if isinstance(key, str) and key.isdecimal():key = int(key)
        if isinstance(key, (bool, np.bool_)) or not isinstance(key, (int, np.integer)) or key <= 0:
            raise ValueError('Circulation-mode keys must be positive lifting-beam indices.')
        if key in requested:raise ValueError('A circulation beam is specified more than once.')
        if isinstance(count, (bool, np.bool_)) or not isinstance(count, (int, np.integer)) or count < 0:
            raise ValueError('Circulation-mode counts must be nonnegative integers; zero selects pointwise values.')
        requested[int(key)] = int(count)
    return requested


class CirculationBasis:
    def __init__(self, meshes, modes=None):
        lifting = [m for m in meshes if m.beam.lifting]
        requested = mode_settings(modes)
        self.indices = {m.beam.index for m in lifting}
        if set(requested)-self.indices:raise ValueError('Circulation modes reference a missing or nonlifting beam.')
        for mesh in lifting:
            if requested.get(mesh.beam.index, 0) > len(mesh.tm):
                raise ValueError(f'Beam {mesh.beam.index}: Fourier mode count exceeds the {len(mesh.tm)} lifting intervals.')
        self.modes = {k: v for k, v in requested.items() if v}
        self.panels = sum(len(m.tm) for m in lifting)
        self.size = sum(requested.get(m.beam.index, 0) or len(m.tm) for m in lifting)
        self.sample = np.zeros((self.panels, self.size))
        self.test = np.zeros((self.size, self.panels))
        self.encoder = np.zeros((self.size, self.panels))
        self.beams = []
        p0 = k0 = 0
        for mesh in lifting:
            count = requested.get(mesh.beam.index, 0); panels = len(mesh.tm)
            width = count or panels
            ps, ks = slice(p0, p0+panels), slice(k0, k0+width)
            condition = 1.
            if count:
                theta = np.asarray(mesh.theta)
                if theta.shape != (panels+1,) or np.any(np.diff(theta) >= 0):
                    raise ValueError('Fourier circulation requires ordered material Glauert node angles.')
                middle = .5*(theta[:-1]+theta[1:]); weights = -np.diff(theta)
                basis = np.sin(middle[:, None]*np.arange(1, count+1))
                weighted = np.sqrt(weights)[:, None]*basis
                u, singular, vt = np.linalg.svd(weighted, full_matrices=False)
                if singular[-1] <= 1e-10*singular[0]:
                    raise ValueError(f'Beam {mesh.beam.index}: Fourier sampling is ill-conditioned; reduce the mode count or change the mesh.')
                condition = float(singular[0]/singular[-1])
                encoder = (vt.T/singular)@u.T*np.sqrt(weights)[None, :]
                test = 2/np.pi*basis.T*weights
            else:
                basis = encoder = test = np.eye(panels)
                middle = weights = np.empty(0)
            self.sample[ps, ks], self.test[ks, ps], self.encoder[ks, ps] = basis, test, encoder
            self.beams.append(dict(beam=mesh.beam.index, representation='fourier' if count else 'pointwise',
                panels=panels, unknowns=width, panel_start=p0, coefficient_start=k0,
                theta_midpoint=middle.tolist(), theta_width=weights.tolist(), sampling_condition=condition))
            p0 += panels; k0 += width

    def validate_settings(self, modes):
        requested = mode_settings(modes)
        if set(requested)-self.indices or {k: v for k, v in requested.items() if v} != self.modes:
            raise ValueError('The circulation representation cannot change inside an existing dynamic or equilibrium system; construct a new system.')

    def decode(self, coefficients):
        return self.sample@coefficients if self.modes else np.asarray(coefficients)

    def encode(self, values, *, strict=True):
        values = np.asarray(values)
        if values.shape != (self.panels,) or not np.all(np.isfinite(values)):
            raise ValueError('Physical circulation must have one finite value per lifting panel.')
        result = self.encoder@values if self.modes else values.copy()
        if strict and self.modes and np.linalg.norm(self.decode(result)-values) > 1e-9*max(np.linalg.norm(values), np.finfo(float).tiny):
            raise ValueError('Physical circulation is outside the selected Fourier space; use the same circulation representation as the saved state.')
        return result

    def report(self, circulation=None):
        result = dict(lifting_panels=self.panels, independent_unknowns=self.size, beams=deepcopy(self.beams),
            convention='Material arc coordinate s in [-L/2,L/2]; theta=acos(2*arc/L-1), decreasing pi to zero. Gamma=sum A_k sin(k theta). Weighted residual=(2/pi) sum R_i sin(k theta_i) delta_theta_i.',
            scope='Fourier modes are per logical lifting beam; refine mode count and structural intervals independently. Local flow defects need not vanish in a truncated series.')
        if circulation is not None:result['coefficients'] = self.encode(circulation).tolist()
        return result
