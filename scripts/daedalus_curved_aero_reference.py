"""Independent vortex and virtual-work maps at a supplied curved aircraft base.

SOURCE ONLY until the enclosing frozen actual-Daedalus audit authorizes probes.
Importing this module performs no aircraft construction, flow evaluation,
linearization, factorization, or solve. It imports no production physics.

This deliberately narrow map checks the virtual lifting-line geometry, direct
Biot--Savart quadrature, and the transpose of the section kinematic map. It does
not calculate aerodynamic forces, circulation residuals, volume flow, engine
jets, stall leakage, apparent inertia, or an aircraft response. Supplied strip
forces and moments are independent inputs to the geometric transfer check;
their physical provenance is outside this map's validation scope.

The independent components are elastic_fin_kinematics.NodalSampler and
free_elastic_aero.MultiSurfaceAero. Their primary formulas are Drela steady
154--161 for the virtual vortices/receiver points and PG-transformed velocity,
plus the stated SO(3) geodesic interpolation and its virtual-power transpose.

Contract for the extracted actual aircraft:
* All arrays use the same instantaneous body-axis gauge. The caller supplies
  the influence freestream in that gauge, including its own directional change.
* positions and material_frames are the already LOADED node positions and full
  c,s,n material triads. q is an increment from that frozen base, with spatial
  translation followed by a left-applied rotation vector at every node.
* The caller must verify zero endpoint-to-node offsets and a constant jig triad
  along every represented beam. Under that condition interpolation of the full
  material frames equals interpolation of deformation followed by the jig
  triad. Distinct beam nodes must be duplicated when they have different triads.
* fractions are fixed original material sampling fractions. length_scale is
  the explicit original material arc length / original endpoint chord length;
  current ds is length_scale times the current endpoint chord. No equality of
  these two length measures is assumed.
* Material arrays and physical surface IDs follow MultiSurfaceAero's contract.
  All lifting surfaces must be supplied together to retain cross-surface flow.
* force and moment are strip resultants in the same axes; moment is about the
  sampled centerline point rm. Transfer returns nodal [force,couple] arrays.

At q=0, a rotation component of a directional probe is precisely a spatial
nodal rotation. At nonzero q it is a direction in the exponential-coordinate
chart. No finite-difference width, coordinate scale, or response normalization
is inferred by this evaluator.
"""

import numpy as np

from elastic_fin_kinematics import NodalSampler
from free_elastic_aero import MultiSurfaceAero


class CurvedAeroReference:
    """Source-independent curved-geometry vortex and wrench-transfer evaluator.

    evaluate(q, gamma, freestream, force, moment) returns only flat numerical
    arrays, so callers can save and compare complete results without parsing a
    project-specific state format. Optional quadrature changes are made by
    constructing another instance with the same frozen arrays.
    """

    sample_keys = ('r0', 'r1', 'rm', 'R0', 'R1', 'Rm', 'ds')
    geometry_keys = ('a', 'b', 'cp', 'hv', 'axis', 'ds', 'pg', 'wind', 'source_core')
    receivers = ('cp', 'hv', 'axis')

    def __init__(self, positions, material_frames, endpoints, fractions,
                 material, physical, flow, *, length_scale, quadrature=32):
        self.sampler = NodalSampler(positions, material_frames, endpoints,
                                    fractions)
        self.aero = MultiSurfaceAero(material, flow, physical, quadrature)
        self.nn, self.np = self.sampler.nn, self.sampler.np
        if self.aero.n != self.np:
            raise ValueError('Material and endpoint panel counts differ')
        self.length_scale = np.asarray(length_scale, dtype=float).copy()
        if (self.length_scale.shape != (self.np,)
                or not np.all(np.isfinite(self.length_scale))
                or np.any(self.length_scale <= 0)):
            raise ValueError('One positive finite original arc/chord ratio per panel is required')
        self.last_diagnostics = None
        self.evaluations = 0

    def evaluate(self, q, gamma, freestream, force, moment):
        """Evaluate all declared maps, retaining complex perturbations.

        q may have shape (nodes,6) or (6*nodes,); gamma has shape (panels,).
        freestream has shape (3,), and force/moment each have shape (panels,3).
        Neither the force inputs nor their derivatives are recomputed here.
        """
        gamma = np.asarray(gamma)
        if gamma.shape != (self.np,) or not np.all(np.isfinite(gamma)):
            raise ValueError('One finite circulation per panel is required')
        q = np.asarray(q).reshape(self.nn, 6)
        if not np.all(np.isfinite(q)):
            raise ValueError('Finite nodal displacement/rotation is required')
        force, moment = np.asarray(force), np.asarray(moment)
        if (force.shape != (self.np, 3) or moment.shape != force.shape
                or not np.all(np.isfinite(force))
                or not np.all(np.isfinite(moment))):
            raise ValueError('Finite strip forces/moments must have shape (panels,3)')
        section = self.sampler.sample(q)
        section['ds'] = self.length_scale*section['ds']
        geometry = self.aero.geometry(section, freestream)
        fields = self.aero.fields(geometry)
        result = {'sample_'+key: section[key] for key in self.sample_keys}
        result.update({'g_'+key: geometry[key] for key in self.geometry_keys})
        result.update({
            'velocity_'+receiver: np.einsum('ijk,j->ik',
                                            fields['fields'][receiver], gamma)
            for receiver in self.receivers})
        result.update(Wa=section['Wa'], Wb=section['Wb'],
                      transfer=self.sampler.transfer(section, force, moment))
        self.last_diagnostics = fields['diagnostics']
        self.evaluations += 1
        return result

    def directional(self, q, gamma, freestream, force, moment, *, dq, dgamma,
                    dfreestream=None, dforce=None, dmoment=None, width=1e-24):
        """Independent complex-step directional derivative about a REAL base.

        Directions may be real or complex harmonic amplitudes. A complex
        direction is split into its real and imaginary directions, which are
        differentiated independently and then recombined. This avoids treating
        the existing imaginary harmonic amplitude as a complex-step signal.
        Omitted force/moment/flow directions are exactly zero. Width is supplied
        explicitly by the caller and can be varied without changing the base.
        """
        if not np.isfinite(width) or not 0 < width < 1e-6:
            raise ValueError('Complex-step width must be finite, positive and below 1e-6')
        shapes = ((self.nn, 6), (self.np,), (3,), (self.np, 3), (self.np, 3))
        supplied = (q, gamma, freestream, force, moment)
        base = []
        for value, shape in zip(supplied, shapes):
            array = np.asarray(value).reshape(shape)
            if not np.all(np.isfinite(array)) or np.any(np.imag(array) != 0):
                raise ValueError('Complex-step base arrays must be finite and real')
            base.append(np.asarray(array.real, dtype=float))
        supplied_directions = (dq, dgamma, dfreestream, dforce, dmoment)
        directions = []
        for value, shape in zip(supplied_directions, shapes):
            array = np.zeros(shape) if value is None else np.asarray(value).reshape(shape)
            if not np.all(np.isfinite(array)):
                raise ValueError('Directional arrays must be finite')
            directions.append(array)

        def differentiate(part):
            perturbed = [value.astype(complex)+1j*width*part(direction)
                         for value, direction in zip(base, directions)]
            return {key: np.imag(value)/width
                    for key, value in self.evaluate(*perturbed).items()}

        real = differentiate(np.real)
        if any(np.any(np.imag(direction) != 0) for direction in directions):
            imaginary = differentiate(np.imag)
            return {key: value+1j*imaginary[key] for key, value in real.items()}
        return real
