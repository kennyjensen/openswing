"""Analytic state columns of the fixed-material source/doublet field.

The body mesh, material radii, point objects and ground plane are fixed. The
incident direction, PG tensor and receiver locations may vary. Values are per
unit freestream speed, just as in VolumeField; callers differentiate the
external speed multiplier separately. No finite differences are used here.
"""
import operator
import numpy as np

from .point_objects import active_weights
from .volume import VolumeField, body_quadrature, body_quadrature_count, source_doublet
from .volume_tangent import source_doublet_partials, VolumeDerivativeUnavailable


def _finite_array(value, shape, name):
    result = np.asarray(value, dtype=float).copy()
    if result.shape != shape or not np.all(np.isfinite(result)):
        raise VolumeDerivativeUnavailable(f'{name} must have finite shape {shape}.')
    return result


def _normalized_columns(vector, columns):
    length = np.linalg.norm(vector, axis=-1)
    if np.any(length <= 0) or not np.all(np.isfinite(length)):
        raise VolumeDerivativeUnavailable('A transformed body axis must have nonzero finite length.')
    unit = vector/length[..., None]
    dlength = np.einsum('...i,...ik->...k', unit, columns)
    dunit = (columns-unit[..., :, None]*dlength[..., None, :])/length[..., None, None]
    return length, unit, dlength, dunit


class VolumeStateTangent:
    """Fixed-material volume field with direction/PG state derivatives.

    Direction columns have shape (3,k), PG columns (3,3,k), and receiver
    columns (n,3,k). ``volume`` exposes the unchanged physical base evaluator.
    Point indices follow active Weight ordering, including active rows that
    have no aerodynamic field. Exclusions suppress physical sources only;
    their ground images remain active, matching VolumeField. Pairwise work is
    blocked independently of receiver count; storage_limit bounds the source
    arrays and unavoidable receiver/output work arrays before allocation.
    """
    def __init__(self, model, meshes, direction, pg, direction_columns,
                 pg_columns, ground=None, *, pair_limit=4096, storage_limit=64*1024**2):
        try:
            self.pair_limit = operator.index(pair_limit)
            self.storage_limit = operator.index(storage_limit)
        except TypeError as exc:
            raise VolumeDerivativeUnavailable('Volume storage and pair limits must be positive integers.') from exc
        if (isinstance(pair_limit, bool) or isinstance(storage_limit, bool)
                or self.pair_limit < 1 or self.storage_limit < 1):
            raise VolumeDerivativeUnavailable('Volume storage and pair limits must be positive integers.')
        direction_columns = np.asarray(direction_columns, dtype=float)
        if direction_columns.ndim != 2 or direction_columns.shape[0] != 3:
            raise VolumeDerivativeUnavailable('Direction columns must have shape (3,k).')
        self.count = direction_columns.shape[1]
        meshes = list(meshes)
        # A conservative count includes null body quadrature samples, since
        # VolumeField retains them whenever any radius on that body is nonzero.
        source_count = sum(body_quadrature_count(mesh) for mesh in meshes if not mesh.beam.lifting)
        source_count += sum(row[6] != 0 or row[7] != 0 for row in active_weights(model))
        shoulder_count = sum(np.count_nonzero(np.diff(mesh.beam.distributions['radius'].t) == 0)
                             for mesh in meshes if not mesh.beam.lifting and 'radius' in mesh.beam.distributions)
        images = 2 if ground is not None and ground.flag else 1
        self.storage_bytes = (images*source_count*(96+56*self.count)
                              +images*shoulder_count*(256+32*self.count)+8*(12+12*self.count))
        self._check_storage(self.storage_bytes, 'sources')
        direction = _finite_array(direction, (3,), 'Direction')
        self.pg = _finite_array(pg, (3, 3), 'PG tensor')
        direction_columns = _finite_array(direction_columns, (3, self.count), 'Direction columns')
        self.pg_columns = _finite_array(pg_columns, (3, 3, self.count), 'PG columns')
        try:
            inverse = np.linalg.inv(self.pg)
        except np.linalg.LinAlgError as exc:
            raise VolumeDerivativeUnavailable('PG tensor must be nonsingular.') from exc
        if not np.all(np.isfinite(inverse)):
            raise VolumeDerivativeUnavailable('PG inverse must be finite.')
        self.volume = VolumeField(model, meshes, direction, self.pg, ground=ground)
        xi = self.pg@direction
        dxi = self.pg@direction_columns+np.einsum('abk,b->ak', self.pg_columns, direction)
        positions, sources, doublets = [], [], []
        for mesh in meshes:
            if mesh.beam.lifting:
                continue
            t, points, radius, weights = body_quadrature(mesh)
            material_weights = weights/mesh.length[:, None]
            if not np.any(radius):
                continue
            physical_dr = mesh.r1-mesh.r0
            dr = physical_dr@self.pg.T
            ddr = np.einsum('abk,nb->nak', self.pg_columns, physical_dr)
            length, ell, dlength, dell = _normalized_columns(dr, ddr)
            along = ell@xi
            dalong = np.einsum('nik,i->nk', dell, xi)+ell@dxi
            transverse = xi-along[:, None]*ell
            dtransverse = (dxi[None, :, :]-ell[:, :, None]*dalong[:, None, :]
                           -along[:, None, None]*dell)
            drdt = mesh.beam.value('radius', t, derivative=1)
            dt = mesh.t1-mesh.t0
            # The PG length cancels exactly between dA/ds and quadrature ds.
            source_factor = 2*np.pi*radius*drdt*dt[:, None]*material_weights
            dsigma = source_factor[..., None]*dalong[:, None, :]
            doublet_factor = 2*np.pi*radius**2*material_weights
            dmu = doublet_factor[..., None, None]*(
                length[:, None, None, None]*dtransverse[:, None, :, :]
                +transverse[:, None, :, None]*dlength[:, None, None, :])
            dp = np.einsum('abk,nqb->nqak', self.pg_columns, points)
            positions.extend(dp.reshape(radius.size, 3, self.count))
            sources.extend(dsigma.reshape(radius.size, self.count))
            doublets.extend(dmu.reshape(radius.size, 3, self.count))
        for row in active_weights(model):
            if row[6] == row[7] == 0:
                continue
            positions.append(np.einsum('abk,b->ak', self.pg_columns, row[2:5]))
            sources.append(np.zeros(self.count))
            doublets.append(row[7]*dxi)
        physical_count = len(sources)
        self.position_columns = np.asarray(positions).reshape(physical_count, 3, self.count)
        self.source_columns = np.asarray(sources).reshape(physical_count, self.count)
        self.doublet_columns = np.asarray(doublets).reshape(physical_count, 3, self.count)
        if ground is not None and ground.flag:
            # A PG-space doublet image is P R P^-1 mu; differentiate all
            # three factors, not just the physical reflection or the source.
            transform = self.pg@ground.reflection@inverse
            dtransform = (np.einsum('abk,bc->ack', self.pg_columns, ground.reflection@inverse)
                          -np.einsum('ab,bck,cd->adk', transform, self.pg_columns, inverse))
            mu = self.volume.doublets[:physical_count]
            dmu_image = ground.flag*(
                np.einsum('ab,nbk->nak', transform, self.doublet_columns)
                +np.einsum('abk,nb->nak', dtransform, mu))
            physical = self.volume.positions[:physical_count]@inverse.T
            image_position = ground.reflect_points(physical)
            dp_image = np.einsum('abk,nb->nak', self.pg_columns, image_position)
            self.position_columns = np.concatenate([self.position_columns, dp_image])
            self.source_columns = np.concatenate([self.source_columns, ground.flag*self.source_columns])
            self.doublet_columns = np.concatenate([self.doublet_columns, dmu_image])
        if len(self.volume.sources) != len(self.source_columns):
            raise VolumeDerivativeUnavailable('Volume source ordering changed during state assembly.')
        self.shoulders = []
        for entries in self.volume.body_shoulders.values():
            for entry in entries:
                axis = self.pg@entry['tangent']
                daxis = np.einsum('abk,b->ak', self.pg_columns, entry['tangent'])
                _, ell, _, dell = _normalized_columns(axis, daxis)
                coefficient = float(xi@ell)
                dcoefficient = xi@dell+ell@dxi
                for image in range(2 if ground is not None and ground.flag else 1):
                    point = ground.reflect_points(entry['position']) if image else entry['position']
                    sign = ground.flag if image else 1
                    self.shoulders.append(dict(
                        **entry, position_pg=self.pg@point,
                        position_columns=np.einsum('abk,b->ak', self.pg_columns, point),
                        coefficient=sign*coefficient, coefficient_columns=sign*dcoefficient,
                        image=bool(image)))
        for value in (self.volume.positions, self.volume.sources, self.volume.doublets,
                      self.volume.cores, self.position_columns, self.source_columns,
                      self.doublet_columns):
            if not np.all(np.isfinite(value)):
                raise VolumeDerivativeUnavailable('Nonfinite volume state sources or columns.')

    def _check_storage(self, required, kind):
        if required > self.storage_limit:
            raise VolumeDerivativeUnavailable(f'Volume state {kind} exceed the storage budget.')

    def velocity_columns(self, points, point_columns, exclude_body=None, exclude_point=None):
        points = np.asarray(points, dtype=float)
        if points.ndim != 2 or points.shape[1] != 3 or not np.all(np.isfinite(points)):
            raise VolumeDerivativeUnavailable('Volume receivers must have finite shape (n,3).')
        # Includes copies, transformed receivers, accumulators and the returned
        # columns, with room for the shoulder and final-transform work arrays.
        self._check_storage(self.storage_bytes+8*len(points)*(24*self.count+24), 'receiver/output arrays')
        point_columns = _finite_array(point_columns, (len(points), 3, self.count), 'Receiver columns')
        field = self.volume
        transformed = points@self.pg.T
        receiver_columns = (np.einsum('ab,nbk->nak', self.pg, point_columns)
                            +np.einsum('abk,nb->nak', self.pg_columns, points))
        base = np.zeros_like(points)
        columns = np.zeros((len(points), 3, self.count))
        if len(field.sources) and len(points):
            # A zero-radius quadrature sample can be identically null. It has
            # no singular derivative even when its receiver is coincident.
            null = ((field.sources == 0) & np.all(field.doublets == 0, axis=1)
                    & np.all(self.source_columns == 0, axis=1)
                    & np.all(self.doublet_columns == 0, axis=(1, 2)))
            exclusions = [(np.broadcast_to(exclusion, (len(points),)), owner)
                          for exclusion, owner in ((exclude_body, field.owners), (exclude_point, field.points))
                          if exclusion is not None]
            source_block = min(len(field.sources), self.pair_limit)
            receiver_block = max(1, self.pair_limit//source_block)
            # Usually every source remains in each receiver block, retaining
            # its original sum. Source blocking also bounds the one-receiver
            # case when the source count alone exceeds the pair limit. Every
            # source is included exactly once, in original contiguous order;
            # no cutoff, threshold or approximate field is introduced.
            for first in range(0, len(points), receiver_block):
                receivers = slice(first, first+receiver_block)
                for start in range(0, len(field.sources), source_block):
                    sources = slice(start, start+source_block)
                    excluded = np.broadcast_to(null[sources], (len(points[receivers]), len(field.sources[sources]))).copy()
                    for exclusion, owner in exclusions:
                        excluded |= ((exclusion[receivers, None] == owner[None, sources])
                                     & ~field.is_image[None, sources])
                    delta = transformed[receivers, None, :]-field.positions[None, sources, :]
                    safe = np.where(excluded[..., None], [1., 0., 0.], delta)
                    args = (field.sources[None, sources], field.doublets[None, sources, :], field.cores[None, sources])
                    values = np.where(excluded[..., None], 0., source_doublet(safe, *args))
                    partials = source_doublet_partials(safe, *args)
                    for value in partials.values():
                        value[excluded] = 0.
                    ddelta = receiver_columns[receivers, None, :, :]-self.position_columns[None, sources, :, :]
                    columns[receivers] += np.einsum('nsab,nsbk->nak', partials['displacement'], ddelta)
                    columns[receivers] += np.einsum('nsa,sk->nak', partials['source'], self.source_columns[sources])
                    columns[receivers] += np.einsum('nsab,sbk->nak', partials['doublet'], self.doublet_columns[sources])
                    base[receivers] += values.sum(axis=1)
        for entry in self.shoulders:
            enabled = np.ones(len(points), dtype=bool)
            if exclude_body is not None and not entry['image']:
                enabled &= np.broadcast_to(exclude_body, (len(points),)) != entry['physical_index']
            if not np.any(enabled):
                continue
            delta = transformed[enabled]-entry['position_pg']
            ddelta = receiver_columns[enabled]-entry['position_columns']
            r2 = np.sum(delta*delta, axis=1)
            left, right = entry['radius_left'], entry['radius_right']
            if min(left, right) == 0 and np.any(r2 == 0):
                raise VolumeDerivativeUnavailable('Coincident zero-radius shoulder has no unique state derivative.')
            a, b = np.sqrt(r2+(left/2)**2), np.sqrt(r2+(right/2)**2)
            unit_factor = (right-left)*(right+left)/(2*a*b*(a+b))
            factor = entry['coefficient']*unit_factor
            radial = -.5*factor*(1/a**2+1/b**2+1/(a*b))
            dfactor = (2*radial[:, None]*np.einsum('na,nak->nk', delta, ddelta)
                       +unit_factor[:, None]*entry['coefficient_columns'])
            base[enabled] += factor[:, None]*delta
            columns[enabled] += factor[:, None, None]*ddelta+delta[:, :, None]*dfactor[:, None, :]
        # VolumeField returns the covector transform v_P^T P, not P v_P.
        result = (np.einsum('nbk,ba->nak', columns, self.pg)
                  +np.einsum('nb,bak->nak', base, self.pg_columns))
        if not np.all(np.isfinite(result)):
            raise VolumeDerivativeUnavailable('Nonfinite volume state derivative.')
        return result
