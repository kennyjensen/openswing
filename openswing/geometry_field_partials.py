"""Composition of local geometry and retained aerodynamic field Jacobians.

The geometric/induced derivatives are analytic. Powered wakes additionally use
the existing refined axial-inflow derivative and small, refined, point-local
jet derivatives. Full physical stencils remain necessary at unsupported or
unresolved branches. This does not supply the separate local residual partial.
"""
import numpy as np
from .geometry_partials import GeometryPartials,GeometryPartialsUnavailable,induced_columns,cross
from .circulation_tangent import EngineDerivative,resolved,dot,norm_gradient
from .propulsion import jet_profile,jet_velocity
from .ground import body_to_earth
from .structure import skew


def gust_gradient(gust,points,condition):
    """Smooth declared gust gradients, in the current fixed body frame."""
    rotation=body_to_earth(condition.attitude)
    earth=points@rotation.T+condition.position_earth
    def gradient(field):
        if field.kind in ('none','uniform'):return np.zeros((len(points),3,3))
        if field.kind=='sum':return sum((gradient(child) for child in field.children),np.zeros((len(points),3,3)))
        if field.kind=='sinusoid':
            phase=earth@field.wavevector-field.omega*condition.time+field.phase
            scalar=np.cos(phase);direction=field.wavevector
        elif field.kind=='cosine':
            phase=((earth-field.origin)@field.normal-field.speed*condition.time)/field.length
            scalar=np.where((phase>0)&(phase<2),.5*np.pi/field.length*np.sin(np.pi*phase),0.)
            direction=field.normal
        else:raise GeometryPartialsUnavailable('Expression gusts require the original physical geometry stencil.')
        return scalar[:,None,None]*np.outer(field.amplitude,direction)
    return np.einsum('ia,nab,bj->nij',rotation.T,gradient(gust),rotation)


class GeometryFieldPartials:
    def __init__(self,evaluator,state,*,chart='spatial',limit=64*1024**2,_cache_geometry=True):
        self.evaluator=e=evaluator;n=e.net;data=e.data
        # Current steady Newton and loaded Bode bases both have zero local
        # elastic rates. Arbitrary moving local bases retain the original path
        # until the derivative of their interpolation maps is included here.
        if any(np.any(value) for value in e.local_values):
            raise GeometryPartialsUnavailable('Moving local-rate geometry requires the original physical stencil.')
        self.geometry=GeometryPartials(e,state,chart=chart,limit=limit)
        self.base=g=self.geometry.base
        self.fields=e.evaluate(g)
        self.gust={name:gust_gradient(e.gust,g['queries'][name][0],e.condition) for name in ('engine','cp','hv')}
        self.jets={name:[] for name in g['queries'] if name!='engine'}
        self.engines=[]
        for i,engine in enumerate(data['engines']):
            if not engine['jet_enabled'] or (engine['thrust']==engine['torque']==engine['delta_velocity']==0):
                self.engines.append(None);continue
            axial=EngineDerivative(data,i,engine['axes'][:,0,None]);self.engines.append(axial)
            for name,terms in self.jets.items():
                points=g['queries'][name][0]
                guard=('local_jet_derivative',name,i)
                e.check_jet_regions(guard,points,[engine])
                for pair in axial.states:
                    for state in pair:e.check_jet_regions(guard,points,[state])
                inflow=axial.jet(points)[...,0]
                # Point-local jet velocity has no cross-receiver coupling.
                # Differentiate its three coordinates simultaneously at every
                # receiver, with the same physical clipping/axis guards.
                jac=np.empty((len(points),3,3));h=1e-5*max(n.L,1.)
                for component in range(3):
                    derivatives=[]
                    for width in (h,h/3):
                        samples=[]
                        for multiplier in (1,-1,2,-2):
                            trial=points.copy();trial[:,component]+=multiplier*width
                            e.check_jet_regions(guard,trial,[engine])
                            samples.append(jet_velocity(trial,[engine],e.direction,data['rho']))
                        derivatives.append((8*(samples[0]-samples[1])-(samples[2]-samples[3]))/(12*width))
                    jac[:,:,component]=resolved(*derivatives,'Jet position derivative')
                relative=points-engine['position'];downstream=relative@e.direction
                radial=relative-downstream[:,None]*e.direction;distance=np.linalg.norm(radial,axis=1)
                inner,outer,speed,swirl=jet_profile(engine,downstream,data['rho']);width=outer-inner
                fraction=np.divide(distance-inner,width,out=np.zeros_like(distance),where=width>0)
                shape=(1-np.clip(fraction,0,1)**1.5)**2
                shape=np.where((downstream>0)&(distance<outer),shape,0.)
                unit=np.divide(radial,distance[:,None],out=np.zeros_like(radial),where=distance[:,None]>0)
                axis=shape[:,None,None]*(speed[:,None,None]*np.eye(3)+swirl[:,None,None]*skew(unit))
                terms.append((i,jac,axis,inflow))
        self.bytes=self.geometry.bytes+sum(v.nbytes for v in self.gust.values())
        self.bytes+=sum(j.nbytes+a.nbytes+v.nbytes for terms in self.jets.values() for _,j,a,v in terms)
        if self.bytes>limit:raise GeometryPartialsUnavailable('Geometry/jet partials exceed their storage budget.')
        self.local_matrix=None;self.local_matrix_fallback=None
        if _cache_geometry:
            from .local_geometry_matrix import LocalGeometryMatrix,LocalGeometryUnavailable
            try:self.local_matrix=LocalGeometryMatrix(self.geometry,limit=limit-self.bytes)
            except LocalGeometryUnavailable as exc:self.local_matrix_fallback=str(exc)
            else:
                self.bytes+=self.local_matrix.bytes
                self.geometry.bytes+=self.local_matrix.bytes


    def columns(self,columns):
        e=self.evaluator;g=self.base;n=e.net;data=e.data;c=e.condition
        if self.local_matrix is None:local=self.geometry.columns(columns)
        else:
            from .local_geometry_matrix import LocalGeometryUnavailable
            try:local=self.local_matrix.columns(columns)
            except LocalGeometryUnavailable as exc:
                self.local_matrix_fallback=str(exc)
                self.bytes-=self.local_matrix.bytes;self.geometry.bytes-=self.local_matrix.bytes
                self.local_matrix=None
                local=self.geometry.columns(columns)
        result=induced_columns(e,g,local)
        omega=np.zeros((n.nn,3,len(columns)))
        for k,j in enumerate(columns):
            node,component=divmod(int(j),6)
            if component>=3:omega[node,:,k]=self.geometry.chart_map[node,:,component-3]
        dp=local['engines_at']
        wind=result['engine']-cross(np.asarray(c.rates)[:,None],dp)+np.einsum('nij,njk->nik',self.gust['engine'],dp)
        daxes=[cross(omega[node],data['engines'][i]['axes'][:,0,None]) for i,node in enumerate(e.engine_nodes)]
        axial=[data['engines'][i]['axes'][:,0]@wind[i]+data['engine_velocity'][i]@daxes[i] for i in range(len(e.engine_nodes))]
        for name,terms in self.jets.items():
            for i,jac,axis,inflow in terms:
                relative=local['queries'][name][0]-dp[i]
                result[name]+=np.einsum('nij,njk->nik',jac,relative)
                result[name]+=np.einsum('nij,jk->nik',axis,daxes[i])
                result[name]+=inflow[:,:,None]*axial[i]
        # Full circulation feedback, including moving section normals and
        # spans, local background wind, stall leakage and circulation lag.
        velocities={};derivatives={}
        for name in ('cp','hv'):
            points=g['p'][name];dpoints=local['p'][name]
            velocities[name]=c.speed*e.direction-np.cross(np.asarray(c.rates),points-n.model.reference[3])+e.gust.body_velocity(points,c)+self.fields[name]
            derivatives[name]=result[name]-cross(np.asarray(c.rates)[:,None],dpoints)+np.einsum('nij,njk->nik',self.gust[name],dpoints)
        frame=g['frames'];dframe=local['frames']
        normal=e.sin_alpha[:,None]*frame[:,:,0]+e.cos_alpha[:,None]*frame[:,:,2]
        dn=e.sin_alpha[:,None,None]*dframe[:,:,0,:]+e.cos_alpha[:,None,None]*dframe[:,:,2,:]
        span=frame[:,:,1];ds=dframe[:,:,1,:];v=velocities['hv'];dv=derivatives['hv']
        along=np.sum(v*span,axis=1);dalong=dot(span,dv)+dot(v,ds)
        vp=v-along[:,None]*span
        dvp=dv-span[:,:,None]*dalong[:,None,:]-along[:,None,None]*ds
        floor=c.speed*1e-12;speed=np.maximum(np.linalg.norm(vp,axis=1),floor)
        dspeed=norm_gradient(vp,dvp,floor)
        cl=2*data['gamma']/(g['p']['chord']*speed)
        dcl=-cl[:,None]*(local['p']['chord']/g['p']['chord'][:,None]+dspeed/speed[:,None])
        from .aero import _stall_leakage
        stall,dstall=_stall_leakage(cl,data['p']['clmin'],data['p']['clmax'],c.stall_width)
        leakage=(c.stall_factor/data['p']['slope'])[:,None]*(stall[:,None]*dspeed+speed[:,None]*dstall[:,None]*dcl) if c.stall else 0.
        residual=(dot(normal,derivatives['cp'])+dot(velocities['cp'],dn)-leakage
            +(2/np.pi*data['lag_rate']/speed**2)[:,None]*dspeed)/c.speed
        result['circulation_residual']=data['basis'].test@residual if data['basis'].modes else residual
        if not all(np.all(np.isfinite(value)) for value in result.values()):
            raise GeometryPartialsUnavailable('Nonfinite composed geometry field derivative.')
        return result
