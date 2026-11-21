"""Local geometry Jacobians for composition with the physical flow maps.

Differentiate current endpoints, interpolated rotations, lifting-line points,
source/doublet strengths and ground images. Material coordinates and the
aircraft condition stay fixed. Columns use either spatial nodal rotations or
the steady solver's absolute rotation-vector chart. No perturbed aerodynamic
evaluation is needed to construct these local partials.
"""
import numpy as np
from .local_motion import left_jacobian,rotation_weights,checked_rotation_arc
from .volume import body_quadrature


class GeometryPartialsUnavailable(ValueError):
    pass


def cross(a,b):
    """Cross product with xyz next-to-last and derivative columns last."""
    return np.moveaxis(np.cross(np.moveaxis(a,-2,-1),np.moveaxis(b,-2,-1)),-1,-2)


def rotate(rate,frame):
    return np.stack([cross(rate,frame[...,j,None]) for j in range(3)],axis=-2)


def unit_direction(value,derivative):
    length=np.linalg.norm(value,axis=-1)
    if np.any(length<=0) or not np.all(np.isfinite(length)):
        raise GeometryPartialsUnavailable('Degenerate local geometry has no unique direction derivative.')
    unit=value/length[...,None]
    dl=np.einsum('...i,...ik->...k',unit,derivative)
    return (derivative-unit[...,None]*dl[...,None,:])/length[...,None,None],dl


class GeometryPartials:
    def __init__(self,evaluator,state,*,chart='spatial',limit=64*1024**2):
        if chart not in ('spatial','absolute'):
            raise ValueError('Geometry chart must be spatial or absolute.')
        self.evaluator,self.chart=evaluator,chart
        self.state=np.asarray(state).copy()
        self.base=evaluator.prepare(self.state)
        n=evaluator.net;r=self.base['r'];q=self.base['q']
        self.endpoints=n.geometry(r,q)
        self.meshes=n.deformed_meshes(r,q,self.endpoints)
        checked_rotation_arc(q[n.a],q[n.b])
        checked_rotation_arc(self.endpoints[2],self.endpoints[3])
        self.weights={}
        for mesh in self.meshes:
            sl=n.beam_elements[mesh.beam.index]
            self.weights[mesh.beam.index]=rotation_weights(q[n.a[sl]],q[n.b[sl]],n.fractions[mesh.beam.index])
        self.chart_map=(np.broadcast_to(np.eye(3),(n.nn,3,3)).copy() if chart=='spatial'
                        else left_jacobian(self.state[:6*n.nn].reshape(n.nn,6)[:,3:]))
        from .geometry_stencil import payload
        self.limit=limit
        self.base_bytes=payload(self.base)
        self.bytes=self.base_bytes+payload(self.endpoints)+payload(self.weights)+self.state.nbytes+self.chart_map.nbytes
        if self.bytes>limit:raise GeometryPartialsUnavailable('Local geometry Jacobians exceed their storage budget.')

    def budget(self,width):
        # Bound returned local derivatives and simultaneous geometric work
        # arrays separately from the already owned nonlocal flow matrices.
        if self.bytes+3*width*self.base_bytes>self.limit:
            raise GeometryPartialsUnavailable('Local geometry columns exceed their working storage budget.')

    def columns(self,columns):
        n=self.evaluator.net;columns=np.asarray(columns,dtype=int)
        if columns.ndim!=1 or not 0<len(columns)<=32 or np.any((columns<0)|(columns>=6*n.nn)):
            raise ValueError('Request at most 32 valid nodal geometry columns at once.')
        self.budget(len(columns))
        width=len(columns);dr=np.zeros((n.nn,3,width));omega=np.zeros_like(dr)
        for k,j in enumerate(columns):
            node,component=divmod(int(j),6)
            if component<3:dr[node,component,k]=n.L
            else:omega[node,:,k]=self.chart_map[node,:,component-3]
        return self.direction(dr,omega)

    def direction(self,dr,omega):
        """Physical nodal position and spatial rotation directions, xyz × k."""
        e=self.evaluator;n=e.net;base=self.base;q=base['q'];pg=e.pg
        dr,omega=np.asarray(dr),np.asarray(omega)
        if dr.shape!=omega.shape or dr.ndim!=3 or dr.shape[:2]!=(n.nn,3) or not 0<dr.shape[-1]<=32:
            raise ValueError('Geometry directions must have shape (nodes,3,k), k <= 32.')
        if not np.all(np.isfinite(dr)) or not np.all(np.isfinite(omega)):
            raise ValueError('Geometry directions must be finite.')
        width=dr.shape[-1]
        self.budget(width)
        pa,pb,ra,rb,oa,ob=self.endpoints
        da=dr[n.a]+cross(omega[n.a],oa[...,None])
        db=dr[n.b]+cross(omega[n.b],ob[...,None])
        dra,drb=rotate(omega[n.a],ra),rotate(omega[n.b],rb)
        interval_derivative=getattr(n,'deformed_interval_length_columns',None)
        source_lengths=(interval_derivative(self.endpoints,da,db,dra,drb)
                        if interval_derivative is not None else None)
        dpoints=[]
        for row in n.weights:
            node=n.node(*row[:2]);offset=q[node]@(row[2:5]-n.rj[node])
            dpoints.append(dr[node]+cross(omega[node],offset[:,None]))
        dengine=[]
        for row,node in zip(n.engines,e.engine_nodes):
            offset=q[node]@(row[4:7]-n.rj[node])
            dengine.append(dr[node]+cross(omega[node],offset[:,None]))
        engine=np.asarray(dengine).reshape(-1,3,width)
        result=dict(r=dr.copy(),q=rotate(omega,q),engines_at=engine,p={},queries={})
        pieces={key:[] for key in ('a','b','hv','cp','rm','ds')};frames=[]
        volume_positions=[];volume_sources=[];volume_doublets=[];body_shoulders={}
        xi=pg@e.direction
        def projected(point,dpoint,span,dspan,coefficient):
            transverse=np.cross(e.wind,span);across=np.linalg.norm(transverse,axis=-1)
            if np.any(across<1e-6):raise GeometryPartialsUnavailable('Lifting-line wind projection is singular.')
            dt=cross(e.wind[:,None],dspan)
            dacross=np.einsum('ni,nik->nk',transverse,dt)/across[:,None]
            return dpoint-e.wind[None,:,None]*(coefficient/across**2)[:,None,None]*dacross[:,None,:]
        for original,mesh in zip(n.meshes,self.meshes):
            beam=mesh.beam;sl=n.beam_elements[beam.index]
            fraction=n.fractions[beam.index];wa,wb=self.weights[beam.index]
            rate=np.einsum('nij,njk->nik',wa,omega[n.a[sl]])+np.einsum('nij,njk->nik',wb,omega[n.b[sl]])
            dframe=rotate(rate,mesh.frames)
            dmid=da[sl]+fraction[:,None,None]*(db[sl]-da[sl])
            if source_lengths is not None:
                dlength=source_lengths[sl]
            else:
                dlength=np.einsum('ni,nik->nk',mesh.r1-mesh.r0,db[sl]-da[sl])/np.linalg.norm(mesh.r1-mesh.r0,axis=1)[:,None]
                dlength*= (original.length/np.linalg.norm(original.r1-original.r0,axis=1))[:,None]
            if beam.lifting:
                chord=beam.value('chord',mesh.tm)
                middle=(.25-beam.value('Xax',mesh.tm))*chord
                for name,point,dpoint,span,dspan,coefficient in [
                    ('a',mesh.r0,da[sl],mesh.frame0[...,1],dra[sl,:,1,:],(.25-beam.value('Xax',mesh.t0,side='right'))*beam.value('chord',mesh.t0,side='right')),
                    ('b',mesh.r1,db[sl],mesh.frame1[...,1],drb[sl,:,1,:],(.25-beam.value('Xax',mesh.t1,side='left'))*beam.value('chord',mesh.t1,side='left')),
                    ('hv',mesh.rm,dmid,mesh.frames[...,1],dframe[:,:,1,:],middle),
                    ('cp',mesh.rm,dmid,mesh.frames[...,1],dframe[:,:,1,:],middle+beam.value('dCLda',mesh.tm)*chord/(4*np.pi))]:
                    pieces[name].append(projected(point,dpoint,span,dspan,coefficient))
                pieces['rm'].append(dmid);pieces['ds'].append(dlength);frames.append(dframe)
                continue
            t,position,radius,weights=body_quadrature(mesh)
            u=(t-mesh.t0[:,None])/(mesh.t1-mesh.t0)[:,None]
            material_weights=weights/mesh.length[:,None]
            dposition=da[sl,None]+(db[sl]-da[sl])[:,None]*u[...,None,None]
            result['queries']['body',beam.index]=(dposition.reshape(-1,3,width),None)
            if np.any(radius):
                axis=(mesh.r1-mesh.r0)@pg.T
                daxis=np.einsum('ij,njk->nik',pg,db[sl]-da[sl])
                dell,dl=unit_direction(axis,daxis);length=np.linalg.norm(axis,axis=1);ell=axis/length[:,None]
                dot=ell@xi;ddot=np.einsum('i,nik->nk',xi,dell)
                material=2*np.pi*radius*beam.value('radius',t,derivative=1)*(mesh.t1-mesh.t0)[:,None]*material_weights
                volume_sources.append((material[:,:,None]*ddot[:,None,:]).reshape(-1,width))
                transverse=xi-dot[:,None]*ell
                dtransverse=-ddot[:,None,:]*ell[:,:,None]-dot[:,None,None]*dell
                material=2*np.pi*radius**2*material_weights
                dd=(transverse[:,:,None]*dl[:,None,:]+length[:,None,None]*dtransverse)
                volume_doublets.append((material[:,:,None,None]*dd[:,None]).reshape(-1,3,width))
                volume_positions.append(np.einsum('ij,ngjk->ngik',pg,dposition).reshape(-1,3,width))
            entries=[]
            source=base['volume'].body_shoulders if base['volume'] is not None else e.frozen.volume_field.body_shoulders
            for shoulder in source[beam.index]:
                station=shoulder['t'];i=int(np.flatnonzero(mesh.t1==station)[0]);j=int(np.flatnonzero(mesh.t0==station)[0])
                ds=dra[sl][j,:,1,:]+drb[sl][i,:,1,:]
                tangent,_=unit_direction(mesh.frame0[j,:,1]+mesh.frame1[i,:,1],ds)
                derivative=dict(position=(db[sl][i]+da[sl][j])/2,tangent=tangent)
                entries.append(derivative)
                result['queries']['shoulder',beam.index,station]=(derivative['position'][None],None)
            body_shoulders[beam.index]=entries
        for key,values in pieces.items():
            result['p'][key]=np.concatenate(values) if values else np.empty((0,width) if key=='ds' else (0,3,width))
        result['frames']=np.concatenate(frames) if frames else np.empty((0,3,3,width))
        result['p']['chord']=np.zeros((len(base['p']['chord']),width))
        if e.frozen:result['cores']=np.zeros((len(base['cores']),width))
        else:
            threshold=e.condition.wake_core_ratio*base['p']['chord']
            if np.any(base['p']['ds']==threshold):raise GeometryPartialsUnavailable('Wake-core maximum is at a nondifferentiable tie.')
            result['cores']=np.where((base['p']['ds']>threshold)[:,None],result['p']['ds'],0.)
        for name in ['cp','hv']+(['axis'] if e.axis else []):
            values=result['p']['rm' if name=='axis' else name]
            result['queries'][name]=(values,np.zeros_like(values) if e.frozen else values.copy())
        result['queries']['engine']=(engine,np.zeros_like(engine))
        for i,values in enumerate(dpoints):result['queries']['point',i]=(values[None],np.zeros_like(values[None]))
        for name,(physical,reference) in list(result['queries'].items()):
            if reference is None:result['queries'][name]=(physical,np.zeros_like(physical) if e.frozen else physical.copy())
        if e.frozen:result['volume']=None
        else:
            for row,position in zip(n.weights,dpoints):
                if row[6]==row[7]==0:continue
                volume_positions.append((pg@position)[None]);volume_sources.append(np.zeros((1,width)))
                volume_doublets.append(np.zeros((1,3,width)))
            def cat(values,shape):return np.concatenate(values) if values else np.empty(shape)
            positions=cat(volume_positions,(0,3,width));sources=cat(volume_sources,(0,width));doublets=cat(volume_doublets,(0,3,width))
            if e.ground.flag:
                reflected=pg@e.ground.reflection@np.linalg.inv(pg)
                positions=np.concatenate([positions,np.einsum('ij,njk->nik',reflected,positions)])
                sources=np.concatenate([sources,e.ground.flag*sources])
                doublets=np.concatenate([doublets,e.ground.flag*np.einsum('ij,njk->nik',reflected,doublets)])
            shoulders=[]
            for mesh in self.meshes:
                if mesh.beam.lifting:continue
                for original,derivative in zip(base['volume'].body_shoulders[mesh.beam.index],body_shoulders[mesh.beam.index]):
                    ell,_=unit_direction(pg@original['tangent'],pg@derivative['tangent'])
                    shoulders.append(dict(derivative,position_pg=pg@derivative['position'],coefficient=xi@ell))
            if e.ground.flag:
                shoulders += [dict(s,position_pg=pg@e.ground.reflection@s['position'],coefficient=e.ground.flag*s['coefficient']) for s in shoulders]
            result['volume']=dict(positions=positions,sources=sources,doublets=doublets,body_shoulders=body_shoulders,shoulders=shoulders)
        return result


def shoulder_columns(volume,derivative,locations,dlocations,exclude_body):
    """Exact derivative of the integrated radius-jump source kernel."""
    result=np.zeros_like(dlocations);pg=volume.pg
    for entry,dentry in zip(volume.shoulders,derivative['shoulders']):
        enabled=np.ones(len(locations),dtype=bool)
        if exclude_body is not None and not entry['image']:
            enabled=np.broadcast_to(exclude_body,(len(locations),))!=entry['physical_index']
        if not np.any(enabled):continue
        delta=locations[enabled]@pg.T-entry['position_pg']
        ddelta=np.einsum('ij,njk->nik',pg,dlocations[enabled])-dentry['position_pg']
        r2=np.sum(delta**2,axis=-1)
        a=np.sqrt(r2+(entry['radius_left']/2)**2);b=np.sqrt(r2+(entry['radius_right']/2)**2)
        denominator=2*a*b*(a+b)
        if np.any(denominator<=0):
            raise GeometryPartialsUnavailable('Unregularized coincident shoulder source has no unique derivative.')
        scale=(entry['radius_right']-entry['radius_left'])*(entry['radius_right']+entry['radius_left'])/denominator
        value=entry['coefficient']*scale
        scalar=np.einsum('ni,nik->nk',delta,ddelta)*(1/a**2+1/b**2+1/(a*b))[:,None]
        gradient=value[:,None,None]*(ddelta-delta[:,:,None]*scalar[:,None,:])
        gradient+=scale[:,None,None]*delta[:,:,None]*dentry['coefficient']
        result[enabled]+=np.einsum('ij,njk->nik',pg.T,gradient)
    return result


def induced_columns(evaluator,base,derivative):
    """Compose local geometry columns with the same owned flow Jacobians.

    The caller must have initialized the maps by evaluating this base geometry.
    No threshold discards nonzero geometry or flow derivatives. This function
    returns induced vortex plus volume velocity; engine-jet composition is a
    separate physical derivative.
    """
    e=evaluator;result={};width=derivative['r'].shape[-1]
    for name,query in base['queries'].items():
        locations=query[0];dp=derivative['queries'][name][0]
        value=np.zeros((len(locations),3,width))
        if e.frozen:
            result[name]=value;continue
        if len(base['p']['chord']):
            vortex=None if e.direct_vortex is None else e.direct_vortex.get(name)
            if vortex is None:
                raise GeometryPartialsUnavailable('No owned vortex Jacobian for '+str(name))
            physical=query[2]
            core=np.broadcast_to(base['cores'],(len(locations),len(base['cores'])))
            if physical is not None:core=np.where(np.asarray(physical)[:,None]==base['p']['physical'][None,:],0.,core)
            if not (np.array_equal(locations,vortex.points) and np.array_equal(base['p']['a'],vortex.a)
                    and np.array_equal(base['p']['b'],vortex.b) and np.array_equal(core,vortex.core)):
                raise GeometryPartialsUnavailable('Vortex Jacobian belongs to a different geometry state.')
            value+=np.einsum('nij,njk->nik',vortex.receiver,dp)
            da,db,dc=derivative['p']['a'],derivative['p']['b'],derivative['cores']
            selected=np.flatnonzero(np.any(da!=0,axis=(1,2))|np.any(db!=0,axis=(1,2))|np.any(dc!=0,axis=1))
            if len(selected):
                active=np.ones((len(locations),len(selected)),dtype=bool) if query[2] is None else np.asarray(query[2])[:,None]!=base['p']['physical'][None,selected]
                value+=vortex.source_columns(selected,da[selected],db[selected],dc[selected],core_active=active)
        volume=None if e.direct_volume is None else e.direct_volume.get(name)
        if volume is None:
            raise GeometryPartialsUnavailable('No owned volume Jacobian for '+str(name))
        current=base['volume']
        if not (np.array_equal(locations@e.pg.T,volume.receivers)
                and np.array_equal(current.positions[volume.selected],volume.positions)
                and np.array_equal(current.sources[volume.selected],volume.sources)
                and np.array_equal(current.doublets[volume.selected],volume.doublets)
                and all(np.array_equal(getattr(current,k),getattr(volume,k)) for k in ['pg','cores','owners','points','is_image'])):
            raise GeometryPartialsUnavailable('Volume Jacobian belongs to a different geometry state.')
        dv=derivative['volume'];indices=np.flatnonzero(volume.selected)
        ds,dm,dq=[dv[key][indices] for key in ['positions','doublets','sources']]
        selected=np.flatnonzero(np.any(ds!=0,axis=(1,2))|np.any(dm!=0,axis=(1,2))|np.any(dq!=0,axis=1))
        field=np.einsum('nij,njk->nik',volume.receiver,np.einsum('ij,njk->nik',e.pg,dp))
        if len(selected):
            field+=np.einsum('ijab,jbk->iak',volume.source_position[:,selected],ds[selected])
            field+=np.einsum('ija,jk->iak',volume.source_strength[:,selected],dq[selected])
            field+=np.einsum('ijab,jbk->iak',volume.source_doublet[:,selected],dm[selected])
        field=np.einsum('ij,njk->nik',e.pg.T,field)
        field+=shoulder_columns(base['volume'],dv,locations,dp,volume.exclude_body)
        result[name]=value+e.condition.speed*field
    return result
