"""Owned sparse local geometry Jacobian, built from disjoint analytic seeds.

The dependency graph is the same conservative graph used by physical geometry
stencils. Every nonzero derivative survives; only exact zeros are omitted.
This is a local geometric map, not a frozen aerodynamic influence model.
"""
from dataclasses import dataclass
import hashlib
import numpy as np
from scipy.sparse import coo_matrix
from .geometry_stencil import GeometryStencil,GeometryStencilUnavailable
from .volume import VolumeField


class LocalGeometryUnavailable(ValueError):
    pass


@dataclass(frozen=True)
class Leaf:
    start: int
    stop: int
    shape: tuple


def _decode_columns(layout,values,width):
    """Return views without a recursive closure retaining the dense buffer.

    A per-call recursive function forms a function/cell cycle. Its captured
    values then survive ordinary reference release until cyclic collection,
    accumulating one dense block per geometry batch. Module-level recursion
    preserves the same views and releases storage when the last view is gone.
    """
    if isinstance(layout,Leaf):
        return values[layout.start:layout.stop].reshape(layout.shape+(width,))
    if isinstance(layout,dict):
        return {key:_decode_columns(item,values,width) for key,item in layout.items()}
    if isinstance(layout,tuple):
        return tuple(_decode_columns(item,values,width) for item in layout)
    if isinstance(layout,list):
        return [_decode_columns(item,values,width) for item in layout]
    return None


def signature(g):
    """Actual inputs of GeometryPartials.direction, including mutable material data."""
    e=g.evaluator;n=e.net;h=hashlib.sha256()
    def add(value):
        if isinstance(value,np.ndarray):
            h.update(repr((value.shape,value.dtype.str)).encode());h.update(value.tobytes())
        elif isinstance(value,VolumeField):add(vars(value))
        elif isinstance(value,dict):
            for key in sorted(value,key=repr):add(key);add(value[key])
        elif isinstance(value,(tuple,list)):
            h.update(str(len(value)).encode())
            for item in value:add(item)
        else:h.update(repr(value).encode())
    def mesh_inputs(mesh):
        beam=mesh.beam
        material={key:(d.name,d.t,d.values,
            [(lo,hi,spline.x,spline.c,spline.extrapolate,spline.axis) for lo,hi,spline in d._segments])
            for key,d in beam.distributions.items() if key in ('chord','Xax','dCLda','radius')}
        arrays={key:item for key,item in vars(mesh).items() if isinstance(item,np.ndarray)}
        return beam.index,beam.physical_index,material,arrays
    add((g.state,g.chart_map,g.base,g.endpoints,g.weights,
        [mesh_inputs(mesh) for mesh in g.meshes],[mesh_inputs(mesh) for mesh in n.meshes],
        n.station_nodes,n.rj,n.a,n.b,n.L,n.fractions,n.beam_elements,n.weights,n.engines,
        e.pg,e.direction,e.wind,e.engine_nodes,e.axis,e.condition.wake_core_ratio,
        e.ground.flag,e.ground.reflection,
        None if e.frozen is None or e.frozen.volume_field is None else e.frozen.volume_field.body_shoulders))
    return h.digest()


class LocalGeometryMatrix:
    def __init__(self,geometry,*,limit=32*1024**2):
        self.owner=g=geometry;n=g.evaluator.net
        self.signature=signature(g);self.applications=0;self.direction_evaluations=0
        try:plan=GeometryStencil(g.evaluator,g.base,0)
        except GeometryStencilUnavailable as exc:raise LocalGeometryUnavailable(str(exc)) from exc
        try:
            if plan.bytes+3*g.base_bytes>limit:
                raise LocalGeometryUnavailable('Local geometry matrix construction exceeds its storage budget.')
            zero=np.zeros((n.nn,3,1));sample=g.direction(zero,zero);self.direction_evaluations+=1
            fields={field['path']:field for field in plan.fields};leaves=[];height=0;entries=0
            def layout(value,path=()):
                nonlocal height,entries
                if isinstance(value,dict):return {key:layout(item,(*path,key)) for key,item in value.items()}
                if isinstance(value,tuple):return tuple(layout(item,(*path,i)) for i,item in enumerate(value))
                if isinstance(value,list):return [layout(item,(*path,i)) for i,item in enumerate(value)]
                if value is None:return None
                value=np.asarray(value);shape=value.shape[:-1];size=int(np.prod(shape))
                if value.shape[-1]!=1 or value.dtype.kind!='f' or np.any(value):
                    raise LocalGeometryUnavailable('Nonlinear or unsupported local derivative layout.')
                leaf=Leaf(height,height+size,shape);height+=size
                field=fields.get(path)
                if field is None:
                    if path!=('p','chord'):raise LocalGeometryUnavailable('Unmapped local geometry dependency: '+str(path))
                else:
                    width=int(np.prod(shape if field['single'] else shape[1:]))
                    entries+=int(field['offsets'][-1])*width
                    leaves.append((path,leaf,field,width))
                return leaf
            self.layout=layout(sample);del sample
            width=min(32,len(plan.groups))
            # Triplet chunks, concatenations, sparse conversion and temporary
            # analytic directions all share this conservative working bound.
            while width and plan.bytes+64*entries+3*width*g.base_bytes>limit:width//=2
            if not width:raise LocalGeometryUnavailable('Local geometry matrix construction exceeds its storage budget.')
            rows=[];columns=[];values=[]
            for start in range(0,len(plan.groups),width):
                groups=plan.groups[start:start+width];count=len(groups)
                dr=np.zeros((n.nn,3,count));omega=np.zeros_like(dr)
                for phase,group in enumerate(groups):
                    if len(np.unique(group//6))!=len(group):
                        raise LocalGeometryUnavailable('Overlapping analytic node seeds.')
                    for column in group:
                        node,component=divmod(int(column),6)
                        if component<3:dr[node,component,phase]=n.L
                        else:omega[node,:,phase]=g.chart_map[node,:,component-3]
                current=g.direction(dr,omega);self.direction_evaluations+=1
                for path,leaf,field,row_width in leaves:
                    value=np.asarray(plan._get(current,path))
                    if value.shape!=leaf.shape+(count,):
                        raise LocalGeometryUnavailable('Changed local geometry derivative layout.')
                    value=value.reshape(-1,row_width,count)
                    for phase,group in enumerate(groups):
                        selections=[field['rows'][column//6] for column in group]
                        selected=np.concatenate(selections)
                        if len(np.unique(selected))!=len(selected):
                            raise LocalGeometryUnavailable('Analytic seeds overlap a declared geometry row.')
                        rr=(leaf.start+selected[:,None]*row_width+np.arange(row_width)).ravel()
                        cc=np.repeat(group,[len(selection)*row_width for selection in selections])
                        vv=value[selected,:,phase].ravel();nonzero=vv!=0
                        rows.append(rr[nonzero]);columns.append(cc[nonzero]);values.append(vv[nonzero])
                        unchanged=np.ones(len(value),dtype=bool);unchanged[selected]=False
                        if np.any(value[unchanged,:,phase]):
                            raise LocalGeometryUnavailable('Derivative lies outside its declared local support.')
            self.matrix=coo_matrix((np.concatenate(values),(np.concatenate(rows),np.concatenate(columns))),
                shape=(height,6*n.nn)).tocsc()
            self.matrix.sum_duplicates();self.matrix.eliminate_zeros()
            arrays=(self.matrix.data,self.matrix.indices,self.matrix.indptr)
            self.bytes=sum(value.nbytes for value in arrays)+128*len(leaves)+len(self.signature)
            if self.bytes>limit or not np.all(np.isfinite(self.matrix.data)) or self.signature!=signature(g):
                raise LocalGeometryUnavailable('Changed, nonfinite or over-budget local geometry matrix.')
            for value in arrays:value.flags.writeable=False
            self.groups=len(plan.groups)
        finally:plan.close()

    def columns(self,columns):
        g=self.owner;columns=np.asarray(columns,dtype=int)
        if columns.ndim!=1 or not 0<len(columns)<=32 or np.any((columns<0)|(columns>=self.matrix.shape[1])):
            raise ValueError('Request at most 32 valid local geometry columns.')
        g.budget(len(columns))
        if self.signature!=signature(g):raise LocalGeometryUnavailable('Local geometry matrix no longer matches its physical inputs.')
        values=self.matrix[:,columns].toarray(order='C');width=len(columns)
        self.applications+=1
        return _decode_columns(self.layout,values,width)

    def report(self):
        return dict(method='retained sparse local geometry Jacobian',rows=self.matrix.shape[0],
            columns=self.matrix.shape[1],nonzeros=self.matrix.nnz,cached_bytes=self.bytes,
            analytic_seed_groups=self.groups,direction_evaluations=self.direction_evaluations,
            applications=self.applications)
