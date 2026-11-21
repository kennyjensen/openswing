"""Retained derivatives of the physical source/doublet volume field.

These maps belong only to geometry derivative assembly at fixed PG tensor,
source layout and material core radii. Source positions, strengths, doublets
and receivers all vary. Nonlinear loads still use VolumeField directly.
"""
import numpy as np
from .vector_ops import dot3
from .volume import source_doublet


class VolumeDerivativeUnavailable(ValueError):
    pass


class VolumeSourceTangent:
    """Owned baseline shared by receiver maps from one geometry assembly."""
    names = ('pg', 'cores', 'owners', 'points', 'is_image',
             'positions', 'sources', 'doublets')

    def __init__(self, volume, *, limit=128*1024**2):
        self.bytes = sum(getattr(volume, name).nbytes for name in self.names)
        if self.bytes > limit:
            raise VolumeDerivativeUnavailable('Retained volume sources exceed their storage budget.')
        for name in self.names:
            value = getattr(volume, name).copy()
            if not np.all(np.isfinite(value)):
                raise VolumeDerivativeUnavailable('Nonfinite retained volume sources.')
            value.flags.writeable = False
            setattr(self, name, value)

    def difference(self, volume):
        """Check once per field evaluation; the volume stays fixed during its queries.

        This short-lived snapshot is never reused for a subsequent evaluation,
        even if that evaluation receives the same mutable VolumeField object.
        """
        for name in self.names[:5]:
            if not np.array_equal(getattr(volume, name), getattr(self, name)):
                raise VolumeDerivativeUnavailable('Changed retained volume-field layout, PG tensor or core radii.')
        for name in self.names[5:]:
            if getattr(volume, name).shape != getattr(self, name).shape:
                raise VolumeDerivativeUnavailable('Changed retained volume-field source layout.')
        return _VolumeSourceChange(self, volume)


class _VolumeSourceChange:
    def __init__(self, source, volume):
        self.source, self.volume = source, volume
        self.positions = volume.positions-source.positions
        self.strength = volume.sources-source.sources
        self.doublets = volume.doublets-source.doublets
        self.changed = (np.any(self.positions != 0., axis=1) | (self.strength != 0.)
                        | np.any(self.doublets != 0., axis=1))
        self.any_changed = bool(np.any(self.changed))
        for value in (self.positions, self.strength, self.doublets, self.changed):
            value.flags.writeable = False


def source_doublet_partials(displacement, source, doublet, core=0.):
    """Fixed-core partials with (..., output_xyz, input_xyz) vector axes."""
    d, sigma, mu, core = [np.asarray(v, dtype=float) for v in
                          (displacement, source, doublet, core)]
    r2 = dot3(d, d)
    den = r2+core**2
    if np.any(den <= 0):
        raise VolumeDerivativeUnavailable('Singular source/doublet derivative; use physical differences.')
    md = dot3(mu, d)
    numerator = mu*r2[..., None]-3*md[..., None]*d
    outer = lambda a, b: a[..., :, None]*b[..., None, :]
    identity = np.eye(3)
    inv3, inv5, inv7 = den**-1.5, den**-2.5, den**-3.5
    position = sigma[..., None, None]*(identity*inv3[..., None, None]
                -3*outer(d, d)*inv5[..., None, None])
    position += (2*outer(mu, d)-3*outer(d, mu)-3*md[..., None, None]*identity)*inv5[..., None, None]
    position -= 5*outer(numerator, d)*inv7[..., None, None]
    result = dict(displacement=position/(4*np.pi),
                  source=d*inv3[..., None]/(4*np.pi),
                  doublet=(r2[..., None, None]*identity-3*outer(d, d))*inv5[..., None, None]/(4*np.pi))
    if not all(np.all(np.isfinite(v)) for v in result.values()):
        raise VolumeDerivativeUnavailable('Nonfinite source/doublet derivative.')
    return result


class VolumeFieldTangent:
    """Owned first-order field for one query; shoulders remain fully physical."""
    def __init__(self, volume, locations, *, exclude_body=None, exclude_point=None,
                 limit=128*1024**2, _source=None):
        locations = np.asarray(locations, dtype=float)
        if locations.ndim != 2 or locations.shape[1] != 3:
            raise VolumeDerivativeUnavailable('Invalid retained volume-field receiver layout.')
        count = len(locations)
        self.exclude_body = None if exclude_body is None else np.asarray(exclude_body).copy()
        selected = np.ones(len(volume.sources), dtype=bool)
        for exclusion, owner in [(exclude_body, volume.owners), (exclude_point, volume.points)]:
            if exclusion is not None and np.ndim(exclusion) == 0:
                selected &= (owner != exclusion) | volume.is_image
        sources = int(selected.sum())
        # Includes both PG receiver storage and all selected source maps, plus
        # full layout guards. Vortex maps share the caller's storage budget.
        required = 8*(count*sources*21+count*15+sources*8+4*len(selected)+12)
        if required > limit:
            raise VolumeDerivativeUnavailable('Retained volume-field derivatives exceed their storage budget.')
        self.selected = selected
        self._source = _source
        if _source is not None:
            if not all(np.array_equal(getattr(volume, name), getattr(_source, name))
                       for name in _source.names):
                raise VolumeDerivativeUnavailable('Mismatched shared volume-source baseline.')
            self.source_indices = np.flatnonzero(selected).copy()
        self.pg = np.asarray(volume.pg).copy()
        self.receivers = locations@self.pg.T
        self.positions = volume.positions[selected].copy()
        self.sources = volume.sources[selected].copy()
        self.doublets = volume.doublets[selected].copy()
        self.cores = volume.cores.copy()
        self.owners, self.points, self.is_image = [v.copy() for v in
                                                  (volume.owners, volume.points, volume.is_image)]
        excluded = np.zeros((count, sources), dtype=bool)
        for exclusion, owner in [(exclude_body, volume.owners), (exclude_point, volume.points)]:
            if exclusion is not None:
                excluded |= (np.broadcast_to(exclusion, (count,))[:, None] == owner[None, selected]) & ~volume.is_image[None, selected]
        delta = self.receivers[:, None, :]-self.positions[None, :, :]
        arguments = (self.sources[None, :], self.doublets[None, :, :], self.cores[None, selected])
        base = source_doublet(delta, *arguments)
        self.base = np.where(excluded[..., None], 0., base).sum(axis=1)
        # Permanently excluded physical sources may coincide with receivers.
        # Their arbitrary evaluation point is masked out of every partial.
        partials = source_doublet_partials(np.where(excluded[..., None], np.array([1., 0., 0.]), delta), *arguments)
        position = np.where(excluded[..., None, None], 0., partials['displacement'])
        self.receiver = position.sum(axis=1)
        self.source_position = -position
        self.source_strength = np.where(excluded[..., None], 0., partials['source'])
        self.source_doublet = np.where(excluded[..., None, None], 0., partials['doublet'])
        arrays = [v for v in vars(self).values() if isinstance(v, np.ndarray)]
        self.bytes = sum(v.nbytes for v in arrays)
        if self.bytes > limit:
            raise VolumeDerivativeUnavailable('Retained volume-field derivatives exceed their storage budget.')
        for value in arrays:
            if not np.all(np.isfinite(value)):
                raise VolumeDerivativeUnavailable('Nonfinite retained volume-field derivative.')
            value.flags.writeable = False

    def value(self, volume, locations, *, _change=None):
        locations = np.asarray(locations, dtype=float)
        if locations.shape != self.receivers.shape:
            raise VolumeDerivativeUnavailable('Changed retained volume-field receiver layout.')
        if _change is None:
            for name in ('pg', 'cores', 'owners', 'points', 'is_image'):
                if not np.array_equal(getattr(volume, name), getattr(self, name)):
                    raise VolumeDerivativeUnavailable('Changed retained volume-field layout, PG tensor or core radii.')
            if volume.positions.shape != (len(self.selected), 3) or volume.doublets.shape != volume.positions.shape or volume.sources.shape != self.selected.shape:
                raise VolumeDerivativeUnavailable('Changed retained volume-field source layout.')
            ds = volume.positions[self.selected]-self.positions
            strength = volume.sources[self.selected]-self.sources
            doublet = volume.doublets[self.selected]-self.doublets
            sources = np.flatnonzero(np.any(ds != 0., axis=1) | (strength != 0.) | np.any(doublet != 0., axis=1))
            ds, strength, doublet = ds[sources], strength[sources], doublet[sources]
        else:
            if self._source is None or _change.source is not self._source or _change.volume is not volume:
                raise VolumeDerivativeUnavailable('Mismatched shared volume-source change.')
            sources = np.flatnonzero(_change.changed[self.selected]) if _change.any_changed else ()
            if len(sources):
                indices = self.source_indices[sources]
                ds, strength, doublet = (_change.positions[indices], _change.strength[indices], _change.doublets[indices])
        dp = locations@self.pg.T-self.receivers
        receivers = np.flatnonzero(np.any(dp != 0., axis=1))
        result = self.base.copy()
        if len(receivers):
            result[receivers] += np.einsum('iab,ib->ia', self.receiver[receivers], dp[receivers])
        if len(sources):
            result += np.einsum('ijab,jb->ia', self.source_position[:, sources], ds)
            result += np.einsum('ija,j->ia', self.source_strength[:, sources], strength)
            result += np.einsum('ijab,jb->ia', self.source_doublet[:, sources], doublet)
        return result@self.pg+volume.shoulder_velocity(locations, self.exclude_body)

    def values_shared(self, volumes, locations, changes, *, _packed=False):
        """Batched original field applications on identical changing supports."""
        if len(locations)!=len(changes) or len(locations)!=len(volumes):
            raise VolumeDerivativeUnavailable('Changed batched volume-field layout.')
        if len(locations)==0:return []
        arrays=[np.asarray(p,dtype=float) for p in locations]
        if any(p.shape!=self.receivers.shape for p in arrays):
            raise VolumeDerivativeUnavailable('Changed batched volume-field layout.')
        selected=[];receivers=[];displacements=[]
        for volume,p,change in zip(volumes,arrays,changes):
            if self._source is None or change.source is not self._source or change.volume is not volume:
                raise VolumeDerivativeUnavailable('Mismatched shared volume-source change.')
            sources=np.flatnonzero(change.changed[self.selected]) if change.any_changed else np.empty(0,dtype=int)
            selected.append(sources);dp=p@self.pg.T-self.receivers;displacements.append(dp)
            receivers.append(np.flatnonzero(np.any(dp!=0.,axis=1)))
        if any(not np.array_equal(selected[0],s) or not np.array_equal(receivers[0],q)
               for s,q in zip(selected[1:],receivers[1:])):
            return [self.value(v,p,_change=c) for v,p,c in zip(volumes,arrays,changes)]
        sources=selected[0];moved=receivers[0]
        result=np.broadcast_to(self.base,(len(arrays),)+self.base.shape).copy()
        if len(moved):
            dp=np.array([p[moved] for p in displacements])
            result[:,moved]+=np.einsum('iab,sib->sia',self.receiver[moved],dp)
        if len(sources):
            indices=self.source_indices[sources]
            ds=np.array([c.positions[indices] for c in changes]);strength=np.array([c.strength[indices] for c in changes])
            doublets=np.array([c.doublets[indices] for c in changes])
            if _packed:
                from .field_products import source_product
                result+=source_product(self.source_position[:,sources],self.source_doublet[:,sources],
                    self.source_strength[:,sources],ds,doublets,strength)
            else:
                result+=np.einsum('ijab,sjb->sia',self.source_position[:,sources],ds)
                result+=np.einsum('ija,sj->sia',self.source_strength[:,sources],strength)
                result+=np.einsum('ijab,sjb->sia',self.source_doublet[:,sources],doublets)
        return [value@self.pg+volume.shoulder_velocity(p,self.exclude_body) for value,volume,p in zip(result,volumes,arrays)]
