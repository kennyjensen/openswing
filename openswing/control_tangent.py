"""Exact flap-setting partials at fixed geometry, circulation and motion.

Steady theory eqs. 158–159 rotate the tangency normal through dCLdF/dCLda.
The section cl=2 Gamma/(c |Vperp|) has no explicit control partial; leakage
therefore changes only through the implicit circulation/velocity response.
The shared load chain includes direct dCDdF, dCMdF and separation drag.
All partials use the file's control-setting units, without a degree conversion.
"""
from types import SimpleNamespace
import numpy as np
from .circulation_tangent import flow_load_columns, CirculationDerivativeUnavailable


class ControlFlow:
    def __init__(self, model, data, controls):
        if (not controls or any(isinstance(k, (bool, np.bool_)) or
                not isinstance(k, (int, np.integer)) or k not in model.controls for k in controls)
                or len(set(controls)) != len(controls)):
            raise CirculationDerivativeUnavailable('Controls must be distinct declared integer flap indices.')
        if 'cp_velocity' not in data:
            raise CirculationDerivativeUnavailable('Control tangent requires the full captured CP velocity.')
        p = data['p']; count = len(controls)
        self.sample = np.zeros((len(data['gamma']), count))
        self.normal_partial = np.zeros((len(data['gamma']), 3, count))
        self.cdp_partial = np.zeros_like(self.sample)
        self.cm_partial = np.zeros_like(self.sample)
        # The current zero-lift normal already contains every mixed control.
        # Recover its sine/cosine projections in the physical section frame.
        rotation = (np.sum(p['normal']*p['section_normal'], axis=1)[:, None]*p['c']
                    -np.sum(p['normal']*p['c'], axis=1)[:, None]*p['section_normal'])
        for beam in model.beams:
            ids = np.flatnonzero(p['beam'] == beam.index)
            if not len(ids):
                continue
            for column, control in enumerate(controls):
                t = p['t'][ids]
                self.normal_partial[ids, :, column] = rotation[ids]*(
                    beam.value(f'dCLdF{control}', t)/p['slope'][ids])[:, None]
                self.cdp_partial[ids, column] = beam.value(f'dCDdF{control}', t)
                self.cm_partial[ids, column] = beam.value(f'dCMdF{control}', t)
        # Flap settings do not directly alter engine commands, body shapes,
        # point-object areas, velocities or the physical section frame.
        self.engines = [SimpleNamespace(force=np.zeros((3, count)), moment=np.zeros((3, count)))
                        for _ in data['engines']]

    def velocity(self, name, points):
        return np.zeros(np.asarray(points).shape+(self.sample.shape[1],))


def control_columns(network, fields, controls):
    if fields.circulation_aero is None or fields.circulation_mechanics is None:
        raise CirculationDerivativeUnavailable('Missing fixed-geometry control capture.')
    flow = ControlFlow(network.model, fields.circulation_aero, controls)
    return flow_load_columns(network, fields, flow, 1.)
