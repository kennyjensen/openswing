"""Independent loaded propulsive-jet/fin residual and harmonic reference.

No production imports. Filament and radial-profile integrals use quadrature.
Analytic continuation within declared real branches permits complex-step
derivatives without subtractive cancellation. This is a model-equation check,
not a claim of original-ASWING or experimentally exact jet fidelity.
"""
import json
from pathlib import Path
import numpy as np


def norm(value, axis=-1):
    return np.sqrt(np.sum(np.asarray(value)**2, axis=axis))


def unit(value):
    value = np.asarray(value, dtype=float)
    return value/norm(value)


def rotation(axis, angle):
    x,y,z=axis
    k=np.array([[0.,-z,y],[z,0.,-x],[-y,x,0.]])
    return np.eye(3)+np.sin(angle)*k+(1-np.cos(angle))*(k@k)


class Reference:
    def __init__(self, n, degree, fixture, solve):
        self.p=fixture; self.f=fixture['fin']; self.eng=fixture['engine']
        self.n=n; self.degree=degree; self.solve=solve
        self.fields=0; self.evaluations=0; self.cache={}
        self.rho=fixture['density']; self.speed=fixture['speed']; self.sound=fixture['sound_speed']
        self.nodes,self.weights=np.polynomial.legendre.leggauss(degree)
        f=self.f; lo,hi=f['z_min'],f['z_max']
        ends=(lo+hi)/2-(hi-lo)/2*np.cos(np.arange(n+1)*np.pi/n)
        ends[0],ends[-1]=lo,hi
        middle=(lo+hi)/2-(hi-lo)/2*np.cos((np.arange(n)+.5)*np.pi/n)
        self.ds=np.diff(ends); self.chord=f['chord']; self.xax=f['Xax']
        self.rm=np.column_stack([np.full(n,f['x']),np.full(n,f['y']),middle])
        self.a=np.column_stack([np.full(n,f['x']+(.25-self.xax)*self.chord),np.full(n,f['y']),ends[:-1]])
        self.b=self.a.copy(); self.b[:,2]=ends[1:]
        self.hv=self.rm+np.array([(.25-self.xax)*self.chord,0.,0.])
        self.cp=self.hv+np.array([f['CLa']/(4*np.pi)*self.chord,0.,0.])
        self.c=np.array([1.,0.,0.]); self.span=np.array([0.,0.,1.]); self.normal=np.cross(self.c,self.span)
        alpha=np.deg2rad(f['alpha_degrees'])
        self.nc=np.sin(alpha)*self.c+np.cos(alpha)*self.normal
        self.ep=np.asarray(self.eng['position']); self.ea=unit(self.eng['downstream_axis'])
        self.pivot=np.asarray(fixture['engine_rotation']['pivot']); self.k=unit(fixture['engine_rotation']['axis'])
        self.translation=unit(fixture['fin_translation']['direction'])
        self.Hcp=self.field(self.cp, 'cp'); self.Hhv=self.field(self.hv, 'hv')
        self.W=np.einsum('ijk,k->ij',self.Hcp,self.nc)
        self.engine_field('engine_rotation',0.)

    def field(self, targets, kind):
        self.fields+=1
        targets=np.atleast_2d(targets)
        result=np.zeros((len(targets),self.n,3),dtype=np.result_type(targets,float))
        core=np.maximum(.25*self.chord,self.ds) if kind=='engine' else np.zeros(self.n)
        for j in range(self.n):
            segments=[(self.b[j],np.array([1.,0.,0.]),None,1.),
                      (self.a[j],np.array([1.,0.,0.]),None,-1.)]
            # Every hv bound contribution vanishes on this straight bound line:
            # own segment excluded, all others collinear and disjoint.
            if kind!='hv':segments.append((self.a[j],self.span,self.ds[j],1.))
            for origin,direction,length,sign in segments:
                relative=targets-origin
                axial=relative@direction
                radial=relative-axial[:,None]*direction
                q2=np.sum(radial**2,axis=1)+core[j]**2
                if np.any(q2.real<=0):raise ValueError('Singular reference filament')
                q=np.sqrt(q2)
                lo=np.arctan(-axial/q)
                hi=np.full(len(targets),np.pi/2) if length is None else np.arctan((length-axial)/q)
                half=(hi-lo)/2
                theta=(hi+lo)[:,None]/2+half[:,None]*self.nodes
                integral=np.sum(np.cos(theta)*self.weights,axis=1)*half/q2
                result[:,j,:]+=sign*np.cross(direction,radial)*integral[:,None]/(4*np.pi)
        return result

    def geometry(self, motion, h, hd=0., hdd=0.):
        dtype=np.result_type(h,hd,hdd,float)
        offset=np.zeros(3,dtype=dtype); velocity=offset.copy(); acceleration=offset.copy()
        ep=self.ep.astype(dtype); ea=self.ea.astype(dtype); ev=offset.copy()
        if motion=='engine_rotation':
            r=rotation(self.k,h)
            ep=self.pivot+r@(self.ep-self.pivot); ea=r@self.ea
            ev=hd*np.cross(self.k,ep-self.pivot)
        elif motion=='fin_translation':
            offset=h*self.translation; velocity=hd*self.translation; acceleration=hdd*self.translation
        else:raise ValueError(motion)
        return dict(offset=offset,velocity=velocity,acceleration=acceleration,ep=ep,ea=ea,ev=ev)

    def engine_field(self, motion, h):
        # At zero displacement both inputs share the same geometric field.
        key=('base',0.) if h==0 else (motion,h)
        if key not in self.cache:
            g=self.geometry(motion,h)
            self.cache[key]=self.field(g['ep']-g['offset'],'engine')[0]
        return self.cache[key]

    def jet(self, points, ep, ea, axial):
        rho=self.rho; thrust=self.eng['thrust']; torque=self.eng['torque']; radius=self.eng['radius']
        delta=np.sqrt(axial**2+2*thrust/(rho*np.pi*radius**2))-axial
        relative=points-ep
        downstream=relative[:,0]
        radial=relative-downstream[:,None]*np.array([1.,0.,0.])
        distance=norm(radial)
        x=np.where(downstream.real>0,downstream,0.)
        contracted=radius*np.sqrt((axial+delta/2)/(axial+delta))
        # The fixture has positive thrust, hence delta>0. No abs(complex).
        raw_inner=contracted-.11*delta/(axial+delta)*x
        inner=np.where(raw_inner.real>0,raw_inner,0.)
        outer=contracted+.11*delta/(axial+delta/2)*x
        width=outer-inner
        # Integrate r=c+w*t², q=(1-t³)². All four integrands are polynomials.
        t=(self.nodes+1)/2; wt=self.weights/2
        r=inner[:,None]+width[:,None]*t**2
        dr=2*width[:,None]*t
        q=(1-t**3)**2
        k1=inner**2+2*np.sum(wt*r*dr*q,axis=1)
        k2=inner**2+2*np.sum(wt*r*dr*q**2,axis=1)
        k3=2/3*inner**3+2*np.sum(wt*r**2*dr*q,axis=1)
        k4=2/3*inner**3+2*np.sum(wt*r**2*dr*q**2,axis=1)
        center=2*thrust/(np.pi*rho)/(k1*axial+np.sqrt((k1*axial)**2+4*k2*thrust/(np.pi*rho)))
        swirl=-torque/(np.pi*rho*(k3*axial+k4*center))
        fraction=np.zeros(distance.shape,dtype=np.result_type(distance,axial))
        mixing=(distance.real>inner.real)&(distance.real<outer.real)&(width.real>0)
        fraction[mixing]=(distance[mixing]-inner[mixing])/width[mixing]
        profile=(1-fraction**1.5)**2
        active=(downstream.real>0)&(distance.real<outer.real)
        profile=np.where(active,profile,0.)
        if np.any(distance.real<=0):raise ValueError('Fixture touches the swirl centerline')
        vector=profile[:,None]*(center[:,None]*ea+swirl[:,None]*np.cross(radial/distance[:,None],ea))
        branches=np.column_stack([downstream.real>0,raw_inner.real>0,distance.real<inner.real,distance.real<outer.real])
        clearance=np.min(np.stack([abs(downstream.real),abs(raw_inner.real),distance.real,
                                  abs(distance.real-inner.real),abs(distance.real-outer.real)]),axis=0)
        return vector,dict(branches=branches,clearance=clearance,inner=inner,outer=outer,
                           center=center,swirl=swirl,delta=delta,axial=axial)

    def evaluate(self, gamma, gamma_rate=None, motion='engine_rotation', h=0., hd=0., hdd=0., lag=False):
        self.evaluations+=1
        if gamma_rate is None:gamma_rate=np.zeros(self.n)
        g=self.geometry(motion,h,hd,hdd)
        ve=self.speed*self.c+self.engine_field(motion,h).T@gamma-g['ev']
        axial=ve@g['ea']
        if axial.real<=0:raise ValueError('Reverse engine inlet')
        cp=self.cp+g['offset']; hv=self.hv+g['offset']; rm=self.rm+g['offset']
        jcp,dc=self.jet(cp,g['ep'],g['ea'],axial)
        jhv,dh=self.jet(hv,g['ep'],g['ea'],axial)
        vc=self.speed*self.c+np.einsum('ijk,j->ik',self.Hcp,gamma)-g['velocity']+jcp
        v=self.speed*self.c+np.einsum('ijk,j->ik',self.Hhv,gamma)-g['velocity']+jhv
        vp=v-(v@self.span)[:,None]*self.span; speed=norm(vp); total_speed=norm(v)
        gd=gamma_rate if lag else np.zeros_like(gamma_rate)
        tangency=vc@self.nc-2/np.pi*gd/speed
        factor=self.rho*self.ds[:,None]
        lift=factor*gamma[:,None]*np.cross(v,self.span)
        rate=factor*(self.chord*gd/speed)[:,None]*np.cross(v,self.span)
        drag=.5*factor*self.chord*(self.f['Cdf']*total_speed[:,None]*v+self.f['Cdp']*speed[:,None]*vp)
        drag+=2*factor*self.chord*(tangency**2/speed)[:,None]*vp
        couple=(.5*self.rho*self.ds*self.chord**2*self.f['Cm']*speed**2/np.sqrt(1-(speed/self.sound)**2))[:,None]*self.span
        apparent=(-self.rho*np.pi/4*self.chord**2*self.ds*(g['acceleration']@self.normal))[:,None]*self.normal
        quarter=rm+(.25-self.xax)*self.chord*self.c
        half=rm+(.5-self.xax)*self.chord*self.c
        total=lift+rate+drag+apparent
        moment=np.cross(quarter,lift+rate)+np.cross(rm,drag)+couple+np.cross(half,apparent)
        engine_force=-self.eng['thrust']*g['ea']
        engine_moment=-self.eng['torque']*g['ea']+np.cross(g['ep'],engine_force)
        ew=np.r_[engine_force,engine_moment]
        def aggregate(force,moment,engine=None):
            fin=np.r_[force.sum(axis=0),moment.sum(axis=0)]
            en=np.zeros(6,dtype=fin.dtype) if engine is None else engine
            return np.array([fin,en,fin+en])
        tw=aggregate(total,moment,ew)
        rw=aggregate(rate,np.cross(quarter,rate))
        aw=aggregate(apparent,np.cross(half,apparent))
        return dict(residual=tangency/self.speed,wrenches=np.stack([tw,rw,aw,tw-rw-aw]),
                    axial=axial,engine_velocity=ve,velocity=v,cp_velocity=vc,
                    normal_speed=speed,jet_cp=jcp,jet_hv=jhv,cp_diagnostics=dc,hv_diagnostics=dh)

    def linearize(self, gamma, motion, lag, epsilon=1e-24):
        columns=[]
        for k in range(self.n):
            probe=np.array(gamma,dtype=complex);probe[k]+=1j*epsilon
            columns.append(self.evaluate(probe,lag=lag)['residual'].imag/epsilon)
        J=np.array(columns).T
        base=self.evaluate(gamma,lag=lag)
        Q=np.diag(-2/(np.pi*base['normal_speed']*self.speed)) if lag else np.zeros_like(J)
        B=[]
        for key in ('h','hd','hdd'):
            B.append(self.evaluate(gamma,motion=motion,lag=lag,**{key:1j*epsilon})['residual'].imag/epsilon)
        return dict(J=J,Q=Q,B=np.array(B))

    def base(self):
        gamma=self.solve(self.W,-self.speed*np.full(self.n,self.nc[0]))
        history=[]
        for iteration in range(9):
            result=self.evaluate(gamma)
            error=float(np.max(abs(result['residual'])))
            history.append(error)
            if error<1e-12:return dict(gamma=gamma,result=result,history=history)
            if iteration==8:break
            J=self.linearize(gamma,'engine_rotation',False)['J']
            gamma=gamma+self.solve(J,-result['residual'])
        raise ValueError('Independent nonlinear circulation root did not converge within eight Newton steps')

    def transfer(self, gamma0, motion, omega, lag, epsilon=1e-24):
        linear=self.linearize(gamma0,motion,lag,epsilon)
        lam=1j*omega
        rhs=-(linear['B'][0]+lam*linear['B'][1]+lam**2*linear['B'][2])
        gamma=self.solve(linear['J']+lam*linear['Q'],rhs)
        phases=[]
        for component in (np.real,np.imag):
            probe=self.evaluate(gamma0+1j*epsilon*component(gamma),
                1j*epsilon*component(lam*gamma),motion=motion,
                h=1j*epsilon*component(1+0j),hd=1j*epsilon*component(lam),
                hdd=1j*epsilon*component(lam**2),lag=lag)
            phases.append(probe['wrenches'].imag/epsilon)
        return dict(gamma=gamma,wrenches=phases[0]+1j*phases[1],linear=linear,
                    full_residual=(linear['J']+lam*linear['Q'])@gamma-rhs)
