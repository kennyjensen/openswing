"""Grouped local geometry preparation for otherwise unchanged field stencils.

Only explicitly nodewise state charts may use this plan. A group moves at most
one coordinate in every geometry row's node support. Individual snapshots are
then recovered by copying those rows, before ANY nonlocal field is evaluated.
The complete original field stencil, refinement and branch checks remain live.
"""
from copy import copy
import numpy as np
from .volume import VolumeField, body_quadrature
from .structured_static import coloring


class GeometryStencilUnavailable(ValueError):
    pass


def same(a, b):
    a, b = np.asarray(a), np.asarray(b)
    return a.shape == b.shape and a.dtype == b.dtype and a.tobytes() == b.tobytes()


def payload(value):
    if isinstance(value, np.ndarray):return value.nbytes
    if isinstance(value, VolumeField):return payload(vars(value))
    if isinstance(value, dict):return sum(payload(v) for v in value.values())
    if isinstance(value, (tuple, list)):return sum(map(payload, value))
    return 0


def owned(value):
    if isinstance(value, np.ndarray):
        if not np.all(np.isfinite(value)):
            raise GeometryStencilUnavailable('Nonfinite grouped geometry input.')
        result = value.copy(); result.flags.writeable = False
        return result
    if isinstance(value, VolumeField):
        result = copy(value)
        for key, item in vars(value).items():setattr(result, key, owned(item))
        return result
    if isinstance(value, dict):return {key:owned(item) for key, item in value.items()}
    if isinstance(value, tuple):return tuple(map(owned, value))
    if isinstance(value, list):return list(map(owned, value))
    if value is None or isinstance(value, (str, int, float, bool, np.generic)):return value
    raise GeometryStencilUnavailable('Unsupported grouped geometry value.')


class GeometryStencil:
    """Owned row dependencies and packed local samples in the tangent budget."""
    def __init__(self, evaluator, geometry, sample_count):
        self.evaluator = evaluator
        n = evaluator.net
        self.cache = n.tangent_influences
        if not getattr(self.cache, 'local_geometry', False):
            raise GeometryStencilUnavailable('Grouped geometry requires a bounded local tangent context.')
        element_nodes = np.column_stack((n.a, n.b))
        lifting = []; volume = []; queries = {}; shoulders = {}
        node_rows = [{n.ne+i} for i in range(n.nn)]
        for index, nodes in enumerate(element_nodes):
            for node in nodes:node_rows[node].add(index)
        for mesh in n.meshes:
            nodes = element_nodes[n.beam_elements[mesh.beam.index]]
            if mesh.beam.lifting:
                lifting.extend(map(tuple, nodes));continue
            t, _, radius, _ = body_quadrature(mesh)
            body = [tuple(row) for row in np.repeat(nodes, radius.shape[1], axis=0)]
            queries['body', mesh.beam.index] = body
            if np.any(radius):volume.extend(body)
            for name in geometry['queries']:
                if not isinstance(name, tuple) or name[:2] != ('shoulder', mesh.beam.index):continue
                station = name[2]
                adjacent = np.flatnonzero((mesh.t0 == station) | (mesh.t1 == station))
                support = tuple(np.unique(nodes[adjacent]).tolist())
                shoulders[mesh.beam.index, station] = support
                queries[name] = [support]
                row = n.ne+n.nn+len(shoulders)
                for node in support:node_rows[node].add(row)
        for index, row in enumerate(n.weights):
            node = n.node(*row[:2]); queries['point', index] = [(node,)]
            if row[6] != 0 or row[7] != 0:volume.append((node,))
        if evaluator.ground.flag:volume *= 2
        for name in ('cp', 'hv', 'axis'):
            if name in geometry['queries']:queries[name] = lifting
        queries['engine'] = [(i,) for i in evaluator.engine_nodes]
        self.support = dict(nodes=[(i,) for i in range(n.nn)], lifting=lifting,
                            volume=volume, engine=queries['engine'], queries=queries,
                            shoulders=shoulders)
        self.groups = coloring([node_rows[j//6] for j in range(6*n.nn)])
        self.indices = []
        for node in range(n.nn):
            def rows(support):return np.array([i for i, nodes in enumerate(support) if node in nodes], dtype=int)
            self.indices.append(dict(nodes=np.array([node]), lifting=rows(lifting), volume=rows(volume),
                engine=rows(queries['engine']), queries={key:rows(value) for key, value in queries.items()},
                shoulders={key:node in value for key, value in shoulders.items()}))
        self.base = owned(geometry)
        self.fields = []
        def field(path, selection, single=False):
            original = self._get(self.base, path)
            value = np.asarray(original)
            array = value.reshape((1,)+value.shape) if single else value
            rows = tuple(selection(index) for index in self.indices)
            offsets = np.r_[0, np.cumsum(np.repeat([len(row) for row in rows], 6))]
            offsets.flags.writeable = False
            shape = (sample_count, int(offsets[-1]), *array.shape[1:])
            self.fields.append(dict(path=path, rows=rows, offsets=offsets, shape=shape,
                dtype=array.dtype, single=single, scalar=value.ndim==0))
        for key in ('r', 'q'):field((key,), lambda index:index['nodes'])
        for key in ('cores', 'frames'):field((key,), lambda index:index['lifting'])
        field(('engines_at',), lambda index:index['engine'])
        for key in geometry['p']:
            if key not in ('chord', 'physical'):field(('p',key), lambda index:index['lifting'])
        for key in geometry['queries']:
            for part in (0,1):field(('queries',key,part), lambda index,key=key:index['queries'][key])
        if geometry['volume'] is not None:
            for key in ('positions','sources','doublets'):field(('volume',key), lambda index:index['volume'])
            lists = [(('volume','shoulders'), geometry['volume'].shoulders)]+[
                (('volume','body_shoulders',key), entries) for key,entries in geometry['volume'].body_shoulders.items()]
            for path, entries in lists:
                for i, entry in enumerate(entries):
                    key = (entry['beam'],entry['t'])
                    for variable in ('position','tangent','position_pg','coefficient'):
                        if variable in entry:
                            field((*path,i,variable), lambda index,key=key:np.array([0] if index['shoulders'][key] else [],dtype=int), True)
        # Packed data stores only affected rows, yet lets the original column
        # order and load-recovery chunk widths remain exactly unchanged.
        data_bytes = sum(int(np.prod(f['shape']))*f['dtype'].itemsize for f in self.fields)
        # Baselines/build capture plus up to four reconstructed original
        # samples for a field-application batch remain in this same budget.
        self.bytes = 8*payload(geometry)+payload(self.indices)+payload(self.groups)+payload(self.fields)+data_bytes
        if self.cache.bytes+self.bytes > 64*1024**2:
            raise GeometryStencilUnavailable('Grouped geometry exceeds the shared tangent storage budget.')
        self._check_layout(geometry)
        for field in self.fields:field['values'] = np.empty(field['shape'],dtype=field['dtype'])
        self.cache.bytes += self.bytes
        self.active = True
        self.built = False

    def close(self):
        if self.active:
            self.cache.bytes -= self.bytes
            self.active = False

    @staticmethod
    def _get(value, path):
        for key in path:value = getattr(value,key) if isinstance(value,VolumeField) else value[key]
        return value

    @staticmethod
    def _set(value, path, result):
        parent = GeometryStencil._get(value,path[:-1])
        if isinstance(parent,VolumeField):setattr(parent,path[-1],result)
        else:parent[path[-1]] = result

    def build(self, state_at, zero, scales, step, multipliers):
        if self.built or not self.active:raise GeometryStencilUnavailable('Inactive or repeated grouped geometry preparation.')
        for group in self.groups:
            h = step*np.asarray(scales)[group]
            for phase,multiplier in enumerate(multipliers):
                delta = zero.copy();delta[group] = multiplier*h
                current = self.capture(self.evaluator.prepare(state_at(delta)),group)
                for field in self.fields:
                    values = np.asarray(self._get(current,field['path']))
                    if field['single']:values = values.reshape((1,)+values.shape)
                    for column in group:
                        start,stop = field['offsets'][column:column+2]
                        field['values'][phase,start:stop] = values[field['rows'][column//6]]
        for field in self.fields:field['values'].flags.writeable = False
        self.built = True

    def sample(self, column, phase):
        if not self.built or not self.active:raise GeometryStencilUnavailable('Unprepared grouped geometry sample.')
        base = self.base
        result = dict(base)
        result['p'] = dict(base['p'])
        result['queries'] = {key:list(value) for key,value in base['queries'].items()}
        if base['volume'] is not None:
            volume = copy(base['volume'])
            volume.shoulders = [dict(value) for value in volume.shoulders]
            volume.body_shoulders = {key:[dict(value) for value in values] for key,values in volume.body_shoulders.items()}
            result['volume'] = volume
        for field in self.fields:
            selected = field['rows'][column//6]
            if not len(selected):continue
            start,stop = field['offsets'][column:column+2]
            values = field['values'][phase,start:stop]
            if field['single']:value = values[0].item() if field['scalar'] else values[0]
            else:
                value = self._get(base,field['path']).copy()
                value[selected] = values;value.flags.writeable = False
            self._set(result,field['path'],value)
        return result

    def _check_layout(self, current):
        base = self.base
        if current.keys() != base.keys() or current['p'].keys() != base['p'].keys() or current['queries'].keys() != base['queries'].keys():
            raise GeometryStencilUnavailable('Changed grouped geometry layout.')
        def array(value, expected):
            if value.shape != expected.shape or value.dtype != expected.dtype:
                raise GeometryStencilUnavailable('Changed grouped geometry array layout.')
        for key in ('r', 'q', 'cores', 'frames', 'engines_at'):array(current[key], base[key])
        if len(base['r']) != len(self.support['nodes']) or len(base['p']['a']) != len(self.support['lifting']):
            raise GeometryStencilUnavailable('Unknown grouped geometry node dependencies.')
        for key in base['p']:array(current['p'][key], base['p'][key])
        for key in ('chord', 'physical'):
            if not same(current['p'][key], base['p'][key]):
                raise GeometryStencilUnavailable('Changed grouped geometry material layout.')
        for key, query in current['queries'].items():
            if len(query[0]) != len(self.support['queries'][key]):
                raise GeometryStencilUnavailable('Unknown grouped receiver dependencies.')
            for index in (0, 1):array(query[index], base['queries'][key][index])
            old = base['queries'][key]
            for index in (2, 4):
                if (query[index] is None) != (old[index] is None) or (query[index] is not None and not same(query[index], old[index])):
                    raise GeometryStencilUnavailable('Changed grouped receiver exclusions.')
            if query[3].keys() != old[3].keys() or any(not same(query[3][k], old[3][k]) for k in old[3]):
                raise GeometryStencilUnavailable('Changed grouped receiver exclusions.')
        volume, old = current['volume'], base['volume']
        if (volume is None) != (old is None):
            raise GeometryStencilUnavailable('Changed grouped volume layout.')
        if volume is not None:
            if len(old.sources) != len(self.support['volume']) or vars(volume).keys() != vars(old).keys():
                raise GeometryStencilUnavailable('Unknown grouped volume dependencies.')
            for key in ('positions', 'sources', 'doublets'):array(getattr(volume, key), getattr(old, key))
            for key in ('pg', 'cores', 'owners', 'points', 'is_image'):
                if not same(getattr(volume, key), getattr(old, key)):
                    raise GeometryStencilUnavailable('Changed grouped volume material/PG layout.')
            if volume.body_shoulders.keys() != old.body_shoulders.keys() or len(volume.shoulders) != len(old.shoulders):
                raise GeometryStencilUnavailable('Changed grouped shoulder layout.')
            for entries, originals in [(volume.shoulders, old.shoulders)]+[
                    (volume.body_shoulders[key], old.body_shoulders[key]) for key in old.body_shoulders]:
                if len(entries) != len(originals):raise GeometryStencilUnavailable('Changed grouped shoulder layout.')
                for entry, original in zip(entries, originals):
                    if entry.keys() != original.keys() or (entry['beam'], entry['t']) not in self.support['shoulders']:
                        raise GeometryStencilUnavailable('Unknown grouped shoulder dependencies.')
                    for key in entry:
                        if key not in ('position', 'tangent', 'position_pg', 'coefficient') and not same(entry[key], original[key]):
                            raise GeometryStencilUnavailable('Changed grouped shoulder material layout.')

    def capture(self, geometry, group):
        """Validate unchanged rows before retaining a group's raw geometry."""
        self._check_layout(geometry)
        current = owned(geometry)
        nodes = set(np.asarray(group)//6)
        masks = dict(nodes=np.array(sorted(nodes)), lifting=np.array([i for i,s in enumerate(self.support['lifting']) if nodes.intersection(s)],dtype=int),
            volume=np.array([i for i,s in enumerate(self.support['volume']) if nodes.intersection(s)],dtype=int),
            engine=np.array([i for i,s in enumerate(self.support['engine']) if nodes.intersection(s)],dtype=int),
            queries={key:np.array([i for i,s in enumerate(value) if nodes.intersection(s)],dtype=int) for key,value in self.support['queries'].items()},
            shoulders={key:bool(nodes.intersection(value)) for key,value in self.support['shoulders'].items()})
        self._merge(current, masks, checking=True)
        return current

    def split(self, geometry, column):
        return self._merge(geometry, self.indices[column//6])

    def _merge(self, current, indices, checking=False):
        base = self.base
        def rows(a, b, selected):
            if checking:
                unchanged = np.ones(len(a), dtype=bool); unchanged[selected] = False
                if not same(a[unchanged], b[unchanged]):
                    raise GeometryStencilUnavailable('Geometry changed outside its declared node support.')
                return a
            if not len(selected):return a
            result = a.copy(); result[selected] = b[selected]; result.flags.writeable = False
            return result
        result = dict(base)
        for key in ('r', 'q'):result[key] = rows(base[key], current[key], indices['nodes'])
        for key in ('cores', 'frames'):result[key] = rows(base[key], current[key], indices['lifting'])
        result['engines_at'] = rows(base['engines_at'], current['engines_at'], indices['engine'])
        result['p'] = {key:rows(value, current['p'][key], indices['lifting']) for key,value in base['p'].items()}
        result['queries'] = {key:(rows(value[0], current['queries'][key][0], indices['queries'][key]),
            rows(value[1], current['queries'][key][1], indices['queries'][key]), *value[2:]) for key,value in base['queries'].items()}
        if base['volume'] is not None:
            volume = copy(base['volume']); new = current['volume']
            for key in ('positions', 'sources', 'doublets'):
                setattr(volume, key, rows(getattr(volume,key), getattr(new,key), indices['volume']))
            def shoulder(a, b):
                changed = indices['shoulders'][a['beam'], a['t']]
                if checking and not changed and any(not same(a[k], b[k]) for k in a):
                    raise GeometryStencilUnavailable('Shoulder changed outside its declared node support.')
                return b if changed and not checking else a
            volume.shoulders = [shoulder(a,b) for a,b in zip(volume.shoulders,new.shoulders)]
            volume.body_shoulders = {key:[shoulder(a,b) for a,b in zip(value,new.body_shoulders[key])]
                                    for key,value in volume.body_shoulders.items()}
            result['volume'] = volume
        return result
