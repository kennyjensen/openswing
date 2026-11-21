"""Exact reuse of unchanged vortex pairs during one numerical tangent.

A nodal perturbation moves only adjoining elements. Every changed source or
receiver still uses the original Biot--Savart kernel, including physical-bound
exclusions, wake cores, PG and ground images. This is not frozen aerodynamics.
"""
import numpy as np


class TangentInfluences:
    def __init__(self, *, local_geometry=False):
        self.entries = {}
        self.bytes = 0
        self.material = {}
        self.static_state = None
        self.static_bytes = 0
        self.static_limit = 16*1024**2
        self.local_geometry = local_geometry
        self.local_entries = {}
        self.array_maps = {}
        self.factored_entries = {}
        self.factored_operators = {}

    def array_map(self, name, arrays, compute):
        """One exact whole-array map per name within this tangent's budget.

        A perturbation often leaves an entire surface unchanged. Byte keys
        preserve dtype, shape and signed zero without repeated NumPy row
        comparisons. Nonfinite inputs always use the physical computation.
        The enclosing tangent already owns a fixed material model.
        """
        if not self.local_geometry:
            return compute()
        key = tuple(self.key(value) for value in arrays)
        saved = self.array_maps.get(name)
        if saved is not None and key == saved[0]:
            return tuple(value.copy() for value in saved[1])
        result = compute()
        size = sum(len(k[2]) for k in key if k is not None)+sum(v.nbytes for v in result)
        if (saved is None and self.bytes+size <= 64*1024**2
                and all(a is None or np.all(np.isfinite(a)) for a in arrays)):
            owned = tuple(value.copy() for value in result)
            for value in owned:value.flags.writeable = False
            self.array_maps[name] = (key, owned)
            self.bytes += size
        return result

    def local_rows(self, name, arrays, compute):
        """Exact elementwise maps, keyed by every rotation/rate/sample input.

        Only the frequency path enables this cache. Outputs must be tuples of
        row-separable arrays; applied loads are never cached. Storage shares
        the existing 64 MiB tangent budget and expires with this context.
        """
        if not self.local_geometry or len(arrays[0]) == 0:
            return compute(slice(None))
        signature=tuple((a.shape,a.dtype.str) for a in arrays)
        saved=self.local_entries.get(name)
        if saved is None or saved[0]!=signature:
            result=compute(slice(None))
            size=sum(a.nbytes for a in (*arrays,*result))
            if saved is None and self.bytes+size<=64*1024**2:
                self.local_entries[name]=(signature,tuple(a.copy() for a in arrays),tuple(a.copy() for a in result))
                self.bytes+=size
            return result
        _,previous,original=saved
        changed=np.zeros(len(arrays[0]),dtype=bool)
        for a,b in zip(arrays,previous):
            different = a != b
            # Signed zero can affect principal rotation branches. Preserve the
            # original operation even when numeric equality hides that change.
            if a.dtype.kind == 'f' and a.dtype.itemsize in (2,4,8):
                bits = np.dtype('u'+str(a.dtype.itemsize))
                different |= a.view(bits) != b.view(bits)
            changed |= np.any(different.reshape(len(a),-1),axis=1)
        if np.count_nonzero(changed)*2>=len(changed):return compute(slice(None))
        result=tuple(a.copy() for a in original)
        if np.any(changed):
            update=compute(changed)
            for a,b in zip(result,update):a[changed]=b
        return result

    def steady_geometry(self, network, r, q, compute):
        """One exact geometry state, owned by this tangent's lifetime.

        Mechanical/circulation perturbations often leave r and Q identical.
        Count retained array storage conservatively, including repeated views;
        motion sampling maintains its own separately bounded cache.
        """
        key = (id(network), self.key(r), self.key(q))
        if self.static_state is not None and self.static_state[0] == key and self.static_bytes <= self.static_limit:
            return self.static_state[1]
        value = compute()
        geometry, dr, rotation, frame, meshes, motion = value
        arrays = [*geometry, dr, rotation, frame]
        arrays += [v for mesh in meshes for v in vars(mesh).values() if isinstance(v,np.ndarray)]
        arrays += [v for v in vars(motion).values() if isinstance(v,np.ndarray)]
        arrays += list(motion.values)
        size = sum(v.nbytes for v in arrays) + r.nbytes + q.nbytes
        self.static_state = (key, value) if size <= self.static_limit else None
        self.static_bytes = size if self.static_state is not None else 0
        return value

    def material_array(self, key, compute):
        if key in self.material:
            return self.material[key]
        value = compute()
        if self.bytes+value.nbytes <= 64*1024**2:
            self.material[key] = value
            self.bytes += value.nbytes
        return value

    def value(self, beam, name, t, *, side="right", derivative=0):
        # The model and material stations are fixed during this one tangent.
        # Return an independent array because callers may apply controls.
        key = (id(beam), name, self.key(t), side, derivative)
        return self.material_array(key, lambda: beam.value(name, t, side=side, derivative=derivative)).copy()

    def frame(self, beam, t):
        from .geometry import surface_frame
        key = (id(beam), 'surface_frame', self.key(t))
        return self.material_array(key, lambda: surface_frame(beam, t))

    @staticmethod
    def key(value):
        if value is None:
            return None
        value = np.asarray(value)
        return value.shape, value.dtype.str, value.tobytes()

    def factored_vortex(self, name, points, a, b, direction, pg, core, ground, exclude_bound=None):
        """Reuse one immutable operator per query when every input is identical.

        Coefficient-pair reuse alone still rebuilds endpoint incidence and core
        groups. Byte keys avoid that work without sharing a perturbed source's
        motion with an adjacent source. Changed inputs use the usual pair cache
        and rebuild their own grouping. Keys own their bytes, including shape,
        dtype, strides and signed zero; caller mutations cannot change the
        stored state. Strides can affect the kernel's floating-point rounding.
        """
        from .factored_influence import FactoredInfluence
        inputs = (points, a, b, direction, pg, core, exclude_bound)
        if ground is not None and ground.flag:
            inputs += (ground.flag, ground.reflection, ground.normal, ground.offset)
        key = tuple(None if value is None else (*self.key(value), np.asarray(value).strides)
                    for value in inputs)
        saved = self.factored_operators.get(name)
        if saved is not None and saved[0] == key:
            return saved[1]
        result = FactoredInfluence(points, a, b, direction, pg, core, ground,
                                   exclude_bound=exclude_bound, _pairs=self, _name=name)
        # Conservatively count all operator storage, even coefficients already
        # retained by the pair cache. Keep only the first state for each query
        # and expire it with the enclosing tangent's shared 64 MiB budget.
        size = sum(len(k[2]) for k in key if k is not None) + result.nbytes
        if saved is None and self.bytes + size <= 64*1024**2:
            self.factored_operators[name] = (key, result)
            self.bytes += size
        return result

    def factored_pairs(self, name, global_key, points, a, b, cores, excluded, compute):
        """Reuse unchanged finite-bound or grouped-ray pairs in one tangent.

        The caller rebuilds exact endpoint groups for each geometry, so a split
        or merged junction never acquires the other endpoint's derivative.
        Pair arrays use their current layout and every effective core value.
        """
        shape = (len(points), len(a))
        key = (global_key, shape, b is None, excluded is None)
        cached = self.factored_entries.get(name)
        reuse = cached is not None and cached[0] == key
        if reuse:
            _, old, original = cached
            old_points, old_a, old_b, old_cores, old_excluded = old
            rows = np.any(points != old_points, axis=1)
            columns = np.any(a != old_a, axis=1) | np.any(cores != old_cores, axis=0)
            if b is not None:
                columns |= np.any(b != old_b, axis=1)
            if excluded is not None:
                columns |= np.any(excluded != old_excluded, axis=0)
            nr, nc = np.count_nonzero(rows), np.count_nonzero(columns)
            if not nr and not nc:
                return original
            if nr*shape[1] + (shape[0]-nr)*nc < shape[0]*shape[1]/2:
                result = original.copy(order='K')
                if nr:
                    result[rows] = compute(rows)
                if nc:
                    result[np.ix_(~rows, columns)] = compute(~rows, columns)
                return result
        result = compute()
        if cached is None:
            inputs = (points, a, b, cores, excluded)
            size = result.nbytes + sum(v.nbytes for v in inputs if v is not None)
            if self.bytes + size <= 64*1024**2:
                owned = tuple(None if v is None else v.copy() for v in inputs)
                result.setflags(write=False)
                self.factored_entries[name] = (key, owned, result)
                self.bytes += size
        return result

    def vortex(self, name, points, a, b, direction, pg, core, ground, exclude_bound=None):
        from .aero import _relative_pg, _relative_horseshoe, horseshoe_velocity
        points, a, b = map(np.asarray, (points, a, b))
        # Retain narrow engine/point queries too: one receiver may still see
        # hundreds of mostly unchanged sources during a nodal perturbation.
        # Tiny queries keep the original direct evaluation.
        if len(points)*len(a) < 64:
            return horseshoe_velocity(points[:, None, :], a[None, :, :], b[None, :, :],
                direction, pg, core, ground, exclude_bound=exclude_bound)
        shape = (len(points), len(a))
        cores = np.broadcast_to(core, shape)
        excluded = None if exclude_bound is None else np.broadcast_to(exclude_bound, shape)
        global_key = (shape, tuple(v.dtype.str for v in (points, a, b, cores)), self.key(direction), self.key(pg),
                      None if ground is None or not ground.flag else
                      (ground.flag, self.key(ground.reflection), self.key(ground.normal), ground.offset),
                      excluded is None)

        cached = self.entries.get(name)
        reuse = cached is not None and cached[0] == global_key
        if reuse:
            _, (old_points, old_a, old_b, old_cores), old_excluded, original = cached
            changed_rows = np.any(points != old_points, axis=1)
            changed_columns = np.any(a != old_a, axis=1) | np.any(b != old_b, axis=1) | np.any(cores != old_cores, axis=0)
            if excluded is not None:
                changed_columns |= np.any(excluded != old_excluded, axis=0)
            nr, nc = np.count_nonzero(changed_rows), np.count_nonzero(changed_columns)
            # Circulation and mechanical perturbations often leave every
            # pair unchanged. Skip relative-coordinate allocations as well
            # as kernel evaluation, retaining independent output ownership.
            if nr == 0 and nc == 0:
                return original.copy()

        # Transform complete relative arrays before slicing: BLAS can round a
        # one-row matrix product differently. Match the direct kernel exactly.
        first, second, segment = _relative_pg(points[:, None, :], a[None, :, :], b[None, :, :], pg)
        dd = np.asarray(direction)@pg.T
        images = ground is not None and ground.flag
        if images:
            image_first, image_second, image_segment = _relative_pg(points[:, None, :],
                ground.reflect_points(a[None, :, :]), ground.reflect_points(b[None, :, :]), pg)
            di = ground.reflect_vectors(direction)@pg.T

        def compute(rows=slice(None), columns=slice(None)):
            selected = cores[rows][:, columns]
            value = _relative_horseshoe(first[rows][:, columns], second[rows][:, columns], segment[:, columns], dd, selected,
                exclude_bound=None if excluded is None else excluded[rows][:, columns])
            if images:
                value -= ground.flag*_relative_horseshoe(image_first[rows][:, columns], image_second[rows][:, columns], image_segment[:, columns], di, selected)
            # Retain physical coefficients, including their PG transform.
            # Unchanged pairs need neither a new kernel nor another transform.
            return value@pg

        if not reuse:
            value = compute()
            if cached is None:
                saved = tuple(v.copy() for v in (points, a, b, cores))
                mask = None if excluded is None else excluded.copy()
                size = sum(v.nbytes for v in saved) + value.nbytes + (0 if mask is None else mask.nbytes)
                if self.bytes + size <= 64*1024**2:
                    self.entries[name] = (global_key, saved, mask, value.copy())
                    self.bytes += size
            return value
        if nr*shape[1] + (shape[0]-nr)*nc >= shape[0]*shape[1]/2:
            return compute()
        result = original.copy()
        if nr:
            result[changed_rows] = compute(changed_rows)
        if nc:
            unchanged = ~changed_rows
            result[np.ix_(unchanged, changed_columns)] = compute(unchanged, changed_columns)
        return result

    def volume_pairs(self, name, points, positions, sources, doublets, cores):
        """Reuse unchanged source/doublet pairs before the original ordered sum.

        Coordinates and singularity strengths already include PG and image
        transforms. Selection, exclusions, shoulder terms and the final
        physical velocity transform remain in VolumeField.velocity.
        """
        from .volume import source_doublet
        arrays = tuple(np.asarray(v) for v in (points, positions, sources, doublets, cores))
        points, positions, sources, doublets, cores = arrays

        def compute(rows=slice(None), columns=slice(None)):
            delta = points[rows, None, :]-positions[None, columns, :]
            return source_doublet(delta, sources[None, columns], doublets[None, columns, :], cores[None, columns])

        if len(points)*len(positions) < 64:
            return compute()
        key = ('volume', name)
        signature = tuple((v.shape, v.dtype.str) for v in arrays)
        cached = self.entries.get(key)
        if cached is None or cached[0] != signature:
            result = compute()
            size = result.nbytes+sum(v.nbytes for v in arrays)
            if cached is None and self.bytes+size <= 64*1024**2:
                self.entries[key] = (signature, tuple(v.copy() for v in arrays), result.copy())
                self.bytes += size
            return result
        _, old, original = cached
        changed_rows = np.any(points != old[0], axis=1)
        changed_columns = (np.any(positions != old[1], axis=1) | (sources != old[2])
                           | np.any(doublets != old[3], axis=1) | (cores != old[4]))
        nr, nc = np.count_nonzero(changed_rows), np.count_nonzero(changed_columns)
        if nr*len(positions)+(len(points)-nr)*nc >= len(points)*len(positions)/2:
            return compute()
        result = original.copy()
        if nr:
            result[changed_rows] = compute(changed_rows)
        if nc:
            unchanged = ~changed_rows
            result[np.ix_(unchanged, changed_columns)] = compute(unchanged, changed_columns)
        return result


class TangentLoads:
    """Bounded exact load values shared by the rank and first load tangents."""
    def __init__(self, limit=32*1024**2):
        self.entries = {}
        self.bytes = 0
        self.limit = limit

    def put(self, key, value):
        import sys
        def size(obj):
            if isinstance(obj, dict):
                return sys.getsizeof(obj)+sum(size(k)+size(v) for k, v in obj.items())
            if isinstance(obj, (list, tuple)):
                return sys.getsizeof(obj)+sum(map(size, obj))
            # getsizeof includes owned NumPy storage. Views may retain a larger
            # parent, so count the complete parent allocation conservatively.
            if isinstance(obj, np.ndarray) and obj.base is not None:
                return sys.getsizeof(obj)+size(obj.base)
            return sys.getsizeof(obj)
        amount = size(key)+size(value)
        if self.bytes+amount <= self.limit:
            self.entries[key] = value
            self.bytes += amount
