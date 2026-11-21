"""Independent discrete lifting-flow map on nonuniform elastic sections.

SOURCE ONLY until an enclosing frozen study authorizes execution. No production
imports, structural interpolation, load splitting, equilibrium or solve occurs
here. All positions, material triads and absolute section kinematics are inputs.

Primary equations: Drela steady 146--161, 62--74; unsteady 22--27, 34--36,
41--44, 48--49. See derivation.md for the finite-array contract and explicitly
retained virtual-motion-point and own-bound-exclusion conventions.
"""
from collections import OrderedDict
import numpy as np


def norm(x, axis=-1):
    """Bilinear analytic continuation of Euclidean norm, without conjugation."""
    x=np.asarray(x)
    return np.sqrt(np.sum(x*x,axis=axis))


def rows(value, size, name):
    value=np.asarray(value)
    if value.shape!=(size,) or not np.all(np.isfinite(value)):
        raise ValueError(name+' requires one finite scalar per panel')
    return value


class AeroMap:
    """One physical fin, with fixed material sampling and live elastic geometry.

    material: panel arrays chord, Xax, alpha_radians, CLa, dCLdF3, Cdf, Cdp,
      Cm, dCMdF3, dCDdF3; endpoint arrays chord0/chord1 and Xax0/Xax1.
      No interpolation or default coefficient is inferred by this module.
    flow: freestream[3] in the SAME fixed physical/gauge axes as all positions,
      density, sound_speed, pg_mach; moment_origin[3]. There is no body/volume,
      ground image, jet, stall, gravity, or fixed-influence approximation.
    sections: r0/r1/rm[N,3], R0/R1/Rm[N,3,3] with columns c,s,n,
      ds[N]; velocity/omega/acceleration/alpha[N,3] about rm.
      These are absolute kinematics in the fixed Galilean gauge. Velocity of a
      point rm+d is velocity+omega cross d. Its acceleration is acceleration
      +angular_acceleration cross d+omega cross(omega cross d).
    Material coordinates must increase in the original fin's +span convention
      even on a branch integrated downward by the mechanical reference.
    """
    scalar_material=('chord','Xax','alpha_radians','CLa','dCLdF3','Cdf','Cdp',
                     'Cm','dCMdF3','dCDdF3','chord0','chord1','Xax0','Xax1')

    def __init__(self, material, flow, quadrature=32, *, field_recorder=None,
                 cache_entries=2):
        if int(quadrature)!=quadrature or quadrature<1:
            raise ValueError('Quadrature degree must be a positive integer')
        self.n=len(np.asarray(material['chord']));self.degree=int(quadrature)
        if self.n<1:raise ValueError('At least one lifting panel is required')
        self.material={k:rows(material[k],self.n,k).copy() for k in self.scalar_material}
        for k in ('chord','chord0','chord1','CLa'):
            if np.any(self.material[k].real<=0):raise ValueError(k+' must be positive')
        self.rho=float(flow['density']);self.sound=float(flow['sound_speed']);self.mach=float(flow['pg_mach'])
        self.free=np.asarray(flow['freestream'],dtype=float).copy()
        self.origin=np.asarray(flow['moment_origin'],dtype=float).copy()
        if self.free.shape!=(3,) or self.origin.shape!=(3,) or not np.all(np.isfinite(self.free)) or not np.all(np.isfinite(self.origin)):
            raise ValueError('Flow and moment origin require finite xyz vectors')
        if not np.isfinite(self.rho) or not np.isfinite(self.sound) or min(self.rho,self.sound)<=0 or not 0<=self.mach<1 or norm(self.free)<=0:
            raise ValueError('Invalid density, sound speed, speed or PG Mach')
        if int(cache_entries)!=cache_entries or cache_entries<1:raise ValueError('Positive integer cache size required')
        self.cache_entries=int(cache_entries);self.cache=OrderedDict();self.recorder=field_recorder
        self.nodes,self.weights=np.polynomial.legendre.leggauss(self.degree)
        self.evaluations=0;self.field_sets=0;self.field_integrations=0

    def geometry(self, sections, freestream=None):
        """Build virtual vortex/receiver points from explicit section geometry."""
        p=self.material;n=self.n;g={}
        for key in ('r0','r1','rm'):
            value=np.asarray(sections[key])
            if value.shape!=(n,3) or not np.all(np.isfinite(value)):raise ValueError('Invalid '+key)
            g[key]=value
        for key,source_key in (('frame0','R0'),('frame1','R1'),('frames','Rm')):
            value=np.asarray(sections[source_key])
            if value.shape!=(n,3,3) or not np.all(np.isfinite(value)):raise ValueError('Invalid '+key)
            # Complex-safe orthonormality, checked only; do not repair frames.
            gram=np.einsum('nji,njk->nik',value,value)
            if np.max(abs(gram-np.eye(3)))>2e-10:raise ValueError('Nonorthonormal '+key)
            if np.max(abs(np.cross(value[:,:,0],value[:,:,1])-value[:,:,2]))>2e-10:
                raise ValueError('Incorrect c,s,n handedness in '+key)
            g[key]=value
        g['ds']=rows(sections['ds'],n,'ds')
        if np.any(g['ds'].real<=0):raise ValueError('Positive current strip lengths required')
        free=self.free if freestream is None else np.asarray(freestream)
        if free.shape!=(3,) or not np.all(np.isfinite(free)):raise ValueError('Invalid freestream')
        speed=norm(free)
        if speed.real<=0:raise ValueError('Positive free-stream speed required')
        wind=free/speed;pg=np.eye(3)+(1/np.sqrt(1-self.mach**2)-1)*np.outer(wind,wind)
        g.update(free=free,speed=speed,wind=wind,pg=pg,c=g['frames'][:,:,0],span=g['frames'][:,:,1],normal=g['frames'][:,:,2])
        across=norm(np.cross(wind,g['span']))
        a0=norm(np.cross(wind,g['frame0'][:,:,1]));a1=norm(np.cross(wind,g['frame1'][:,:,1]))
        if min(np.min(across.real),np.min(a0.real),np.min(a1.real))<1e-6:
            raise ValueError('Section or endpoint span aligns with the influence wind')
        g['a']=g['r0']+((.25-p['Xax0'])*p['chord0']/a0)[:,None]*wind
        g['b']=g['r1']+((.25-p['Xax1'])*p['chord1']/a1)[:,None]*wind
        g['hv']=g['rm']+((.25-p['Xax'])*p['chord']/across)[:,None]*wind
        g['cp']=g['hv']+(p['CLa']*p['chord']/(4*np.pi*across))[:,None]*wind
        g['axis']=g['rm']
        g['quarter_arm']=((.25-p['Xax'])*p['chord'])[:,None]*g['c']
        g['half_arm']=((.5-p['Xax'])*p['chord'])[:,None]*g['c']
        return g

    def _line_integral(self, relative, direction, length, diagnostic):
        """Integrate Biot--Savart independently in transformed PG space.

        Normally substitute line coordinate ell=z+q*tan(theta). At exactly
        or nearly collinear but disjoint receivers, use smooth direct Gauss
        quadrature instead; no division by q and no artificial core/floor.
        The real geometry chooses the branch, retained under complex steps.
        """
        z=np.sum(relative*direction,axis=1);radial=relative-z[:,None]*direction
        radial_real=np.sum(radial.real*radial.real,axis=1)
        scale=np.maximum(1.,np.sum(relative.real*relative.real,axis=1))
        near=radial_real<=1e-24*scale
        value=np.zeros_like(relative,dtype=np.result_type(relative,direction,float))
        for i in range(len(relative)):
            if near[i]:
                # A disjoint collinear segment has a regular physical integral.
                if length is not None:
                    if 0<=z[i].real<=length.real:raise ValueError('Non-excluded receiver meets a bound filament')
                    ell=.5*length*(self.nodes+1);jac=.5*length*np.ones(self.degree)
                    diagnostic['direct_disjoint_finite']+=1
                    clearance=min(abs(z[i].real),abs(z[i].real-length.real))
                else:
                    if z[i].real>=0:raise ValueError('Receiver meets a downstream wake filament')
                    # ell=a*t/(1-t); upstream z<0 gives a nonsingular finite interval.
                    t=.5*(self.nodes+1);a=-z[i].real
                    ell=a*t/(1-t);jac=.5*a/(1-t)**2
                    diagnostic['direct_upstream_wake']+=1;clearance=-z[i].real
                if clearance<=0:raise ValueError('Zero disjoint-filament clearance')
                d=relative[i]-ell[:,None]*direction
                integral=np.sum(self.weights*jac/norm(d)**3)
                value[i]=np.cross(direction,relative[i])*integral/(4*np.pi)
                diagnostic['minimum_direct_clearance']=min(diagnostic['minimum_direct_clearance'],clearance)
            else:
                q2=np.sum(radial[i]*radial[i]);q=np.sqrt(q2)
                lo=np.arctan(-z[i]/q);hi=np.pi/2 if length is None else np.arctan((length-z[i])/q)
                half=(hi-lo)/2;theta=(hi+lo)/2+half*self.nodes
                integral=np.sum(self.weights*np.cos(theta))*half/q2
                value[i]=np.cross(direction,radial[i])*integral/(4*np.pi)
                diagnostic['theta_integrals']+=1
                diagnostic['minimum_theta_radius']=min(diagnostic['minimum_theta_radius'],float(np.sqrt(radial_real[i])))
        return value

    def _field(self,g,receiver):
        self.field_integrations+=1;n=self.n;pg=g['pg'];targets=g[receiver]
        H=np.zeros((n,n,3),dtype=np.result_type(targets,g['a'],g['b'],pg))
        diagnostic=dict(own_bound_excluded=0,direct_disjoint_finite=0,direct_upstream_wake=0,
            theta_integrals=0,minimum_direct_clearance=float('inf'),minimum_theta_radius=float('inf'),same_physical_surface_core=0.)
        wake=pg@g['wind'];wake/=norm(wake)
        for j in range(n):
            # Transform relative vectors, so translations cancel before PG.
            segment=pg@(g['b'][j]-g['a'][j]);length=norm(segment)
            if length.real<=0:raise ValueError('Zero-length bound segment')
            tangent=segment/length
            for kind,origin,direction,extent,sign in [('bound',g['a'][j],tangent,length,1.),('wake',g['b'][j],wake,None,1.),('wake',g['a'][j],wake,None,-1.)]:
                ids=np.arange(n)
                if kind=='bound' and receiver in ('hv','axis'):
                    ids=ids[ids!=j];diagnostic['own_bound_excluded']+=1
                if not len(ids):continue
                relative=(targets[ids]-origin)@pg.T
                transformed=self._line_integral(relative,direction,extent,diagnostic)
                # Eq160: velocity is P^T times transformed velocity, not P^-1.
                H[ids,j]+=sign*(transformed@pg)
        for k in ('minimum_direct_clearance','minimum_theta_radius'):
            if not np.isfinite(diagnostic[k]):diagnostic[k]=None
        return H,diagnostic

    def fields(self,g):
        """Exact array-keyed cache; rates/accelerations/Gamma never set geometry."""
        key=tuple((k,np.asarray(g[k],dtype=np.complex128).shape,np.asarray(g[k],dtype=np.complex128).tobytes())
                  for k in ('a','b','cp','hv','axis','pg','wind'))
        if key in self.cache:
            self.cache.move_to_end(key);return self.cache[key]
        self.field_sets+=1;result={};diagnostics={}
        for receiver in ('cp','hv','axis'):result[receiver],diagnostics[receiver]=self._field(g,receiver)
        entry=dict(fields=result,diagnostics=diagnostics)
        self.cache[key]=entry
        while len(self.cache)>self.cache_entries:self.cache.popitem(last=False)
        if self.recorder is not None:self.recorder(g,result,diagnostics)
        return entry

    def _kinematics(self,sections):
        out={}
        for k,source_key in (('velocity','velocity'),('omega','omega'),('acceleration','acceleration'),('angular_acceleration','alpha')):
            v=np.asarray(sections[source_key])
            if v.shape!=(self.n,3) or not np.all(np.isfinite(v)):raise ValueError('Invalid section '+k)
            out[k]=v
        return out

    def base_system(self,sections,control=0.,*,freestream=None):
        """Return finite-geometry steady linear circulation W*Gamma=rhs; no solve.

        Use only for the declared zero-rate base. Coupled motion and Gamma-dot
        must be evaluated through evaluate(), not hidden in this base system.
        """
        kin=self._kinematics(sections)
        if any(np.any(v!=0) for v in kin.values()):raise ValueError('Base system requires zero section motion')
        g=self.geometry(sections,freestream);field=self.fields(g);p=self.material
        alpha=p['alpha_radians']+control*p['dCLdF3']/p['CLa']
        normal=np.sin(alpha)[:,None]*g['c']+np.cos(alpha)[:,None]*g['normal']
        W=np.einsum('ijk,ik->ij',field['fields']['cp'],normal)
        rhs=-np.sum(g['free']*normal,axis=1)
        return dict(W=W,rhs=rhs,geometry=g,control_normal=normal,**field)

    def evaluate(self,sections,gamma,gamma_dot=None,control=0.,*,lag=True,freestream=None):
        """Complete finite residual and physical strip force/couple, no solve.

        Return strip_force and strip_moment_axis at rm; the mechanical bridge
        must apply its own exact transpose interpolation once. Apparent loads
        are already included. No additional fluid mass is to be added there.
        """
        self.evaluations+=1;g=self.geometry(sections,freestream);kin=self._kinematics(sections)
        gamma=rows(gamma,self.n,'Gamma')
        gamma_dot=np.zeros_like(gamma) if gamma_dot is None else rows(gamma_dot,self.n,'Gamma_dot')
        if not isinstance(lag,(bool,np.bool_)):raise ValueError('Lag must be Boolean')
        field=self.fields(g);p=self.material
        alpha=p['alpha_radians']+control*p['dCLdF3']/p['CLa']
        nc=np.sin(alpha)[:,None]*g['c']+np.cos(alpha)[:,None]*g['normal']
        velocities={}
        for name in ('cp','hv','axis'):
            material_v=kin['velocity']+np.cross(kin['omega'],g[name]-g['rm'])
            velocities[name]=g['free']+np.einsum('ijk,j->ik',field['fields'][name],gamma)-material_v
        v,vc,va=velocities['hv'],velocities['cp'],velocities['axis'];s=g['span'];normal=g['normal']
        vp=v-np.sum(v*s,axis=1)[:,None]*s;S=norm(vp);V=norm(v)
        if np.any(S.real<=g['speed'].real*1e-12):raise ValueError('Section normal speed reaches the production floor')
        if np.any((S/self.sound).real>=1):raise ValueError('Local section normal Mach reaches unity')
        gd=gamma_dot if lag else np.zeros_like(gamma_dot)
        tangency=np.sum(vc*nc,axis=1)-2/np.pi*gd/S
        coeff=self.rho*g['ds'];chord=p['chord']
        lift=(coeff*gamma)[:,None]*np.cross(v,s)
        rate=(coeff*chord*gd/S)[:,None]*np.cross(v,s)
        cdp=p['Cdp']+control*p['dCDdF3'];cm=p['Cm']+control*p['dCMdF3']
        if np.any(cdp.real<0) or np.any(p['Cdf'].real<0):raise ValueError('Negative declared profile coefficient')
        profile=.5*(coeff*chord)[:,None]*(p['Cdf'][:,None]*V[:,None]*v+cdp[:,None]*S[:,None]*vp)
        profile+=2*(coeff*chord*tangency*tangency/S)[:,None]*vp
        cm_couple=(.5*coeff*chord**2*cm*S*S/np.sqrt(1-(S/self.sound)**2))[:,None]*s
        arm=g['half_arm'];omega=kin['omega'];angular=kin['angular_acceleration']
        half_acceleration=kin['acceleration']+np.cross(angular,arm)+np.cross(omega,np.cross(omega,arm))
        rate_scalar=np.sum(np.cross(va,omega)*normal,axis=1);ma=self.rho*np.pi/4*chord**2*g['ds']
        apparent=(ma*(rate_scalar-np.sum(half_acceleration*normal,axis=1)))[:,None]*normal
        pitch=(-ma*(chord/4*rate_scalar+chord**2/32*np.sum(angular*s,axis=1)))[:,None]*s
        zeros=np.zeros_like(lift);quarter=g['quarter_arm']
        terms=dict(circulatory_lift=dict(force=lift,moment_axis=np.cross(quarter,lift)),
            circulation_rate_lift=dict(force=rate,moment_axis=np.cross(quarter,rate)),
            profile_drag=dict(force=profile,moment_axis=zeros),profile_couple=dict(force=zeros,moment_axis=cm_couple),
            apparent_force=dict(force=apparent,moment_axis=np.cross(arm,apparent)),
            apparent_pitch_couple=dict(force=zeros,moment_axis=pitch))
        force=lift+rate+profile+apparent;moment=np.cross(quarter,lift+rate)+cm_couple+np.cross(arm,apparent)+pitch
        rate_m=np.cross(quarter,rate);apparent_m=np.cross(arm,apparent)+pitch
        forces=np.stack([force,rate,apparent,force-rate-apparent]);moments=np.stack([moment,rate_m,apparent_m,moment-rate_m-apparent_m])
        wrenches=np.concatenate([forces.sum(axis=1),(moments+np.cross(g['rm']-self.origin,forces)).sum(axis=1)],axis=1)
        return dict(residual=tangency/g['speed'],tangency=tangency,control_normal=nc,
            strip_force=force,strip_moment_axis=moment,strip_terms=terms,
            family_forces=forces,family_moments_axis=moments,wrenches=wrenches,
            geometry=g,kinematics=kin,**field,cp_velocity=vc,velocity=v,axis_velocity=va,
            normal_speed=S,total_speed=V,half_acceleration=half_acceleration,apparent_rate_scalar=rate_scalar)
