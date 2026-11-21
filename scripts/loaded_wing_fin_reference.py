"""Independent quadrature and small-disturbance equations; no production imports."""
import numpy as np

def geometry(n):
    edges = []; mids = []; spans = []; chords = []; beams = []; lengths = []
    for beam,lo,hi,chord in [(1,-2.,2.,1.),(2,.4,2.4,.75)]:
        t=(lo+hi)/2-(hi-lo)/2*np.cos(np.arange(n+1)*np.pi/n)
        tm=(lo+hi)/2-(hi-lo)/2*np.cos((np.arange(n)+.5)*np.pi/n)
        t[0],t[-1]=lo,hi
        def position(values):
            a=np.zeros((len(values),3))
            if beam==1:a[:,1]=values
            else:a[:,0]=2.;a[:,2]=values
            return a
        r=position(t);rm=position(tm)
        edges.append((r[:-1],r[1:]));mids.append(rm)
        spans.append(np.tile([0.,1.,0.] if beam==1 else [0.,0.,1.],(n,1)))
        chords.extend([chord]*n);beams.extend([beam]*n);lengths.extend(np.diff(t))
    chord=np.array(chords);rm=np.concatenate(mids);s=np.concatenate(spans)
    a=np.concatenate([x[0] for x in edges]);b=np.concatenate([x[1] for x in edges])
    # Xax=.5, so quarter chord lies .25*c upstream of the beam axis.
    a[:,0]-=.25*chord;b[:,0]-=.25*chord
    hv=rm.copy();hv[:,0]-=.25*chord
    cp=hv.copy();cp[:,0]+=.5*chord
    return dict(a=a,b=b,rm=rm,hv=hv,cp=cp,s=s,normal=np.cross([1.,0.,0.],s),
                chord=chord,beam=np.array(beams),ds=np.array(lengths))

def moved(g,displacement):
    result={k:v.copy() for k,v in g.items()}
    for key in ['a','b','rm','hv','cp']:result[key][g['beam']==2,1]+=displacement
    return result

def field(g,degree,receiver):
    """Independent Eq161 quadrature at CP or force points.

    Own bound omitted only at hv. Other exactly collinear bound segments
    give zero only if the receiver lies strictly outside that segment.
    No artificial core, denominator floor or endpoint antiderivative.
    """
    nodes,weights=np.polynomial.legendre.leggauss(degree)
    targets=g[receiver];a=g['a'];b=g['b'];N=len(a)
    core=np.where(g['beam'][:,None]==g['beam'][None,:],0.,np.maximum(.25*g['chord'],g['ds'])[None,:])
    result=np.zeros((N,N,3));collinear=0;own_excluded=0
    for j in range(N):
        for kind,origin,tangent,length,sign in [
            ('bound',a[j],b[j]-a[j],float(np.linalg.norm(b[j]-a[j])),1.),
            ('wake',b[j],np.array([1.,0.,0.]),None,1.),
            ('wake',a[j],np.array([1.,0.,0.]),None,-1.)]:
            active=np.ones(N,dtype=bool)
            if receiver=='hv' and kind=='bound':active[j]=False;own_excluded+=1
            u=tangent/np.linalg.norm(tangent);r=targets-origin;z=np.sum(r*u,axis=1);h=r-z[:,None]*u
            q2=np.sum(h*h,axis=1)+core[:,j]**2
            singular=active&(q2==0)
            if np.any(singular):
                allowed=(kind=='bound') & ((z<0)|(z>length)) if length is not None else np.zeros(N,dtype=bool)
                if np.any(singular&~allowed) or np.any(np.cross(u,h[singular])!=0):raise ValueError('Singular reference receiver')
                collinear+=int(singular.sum());active[singular]=False
            ids=np.flatnonzero(active);q=np.sqrt(q2[ids]);lo=np.arctan2(-z[ids],q)
            hi=np.full(len(ids),np.pi/2) if length is None else np.arctan2(length-z[ids],q)
            half=(hi-lo)/2;theta=(hi+lo)[:,None]/2+half[:,None]*nodes
            integral=np.sum(np.cos(theta)*weights,axis=1)*half/q2[ids]
            result[ids,j,:]+=sign*np.cross(u,h[ids])*integral[:,None]/(4*np.pi)
    return result,dict(own_bound_excluded=own_excluded,collinear_outside_bound_zero=collinear)

def normals(g):
    incidence=2*np.pi/180
    return np.sin(incidence)*np.array([1.,0.,0.])+np.cos(incidence)*g['normal']

def apply(H,gamma):return np.einsum('ijk,j->ik',H,gamma)

def base(g,Hcp,Hhv,solve):
    nc=normals(g);W=np.sum(Hcp*nc[:,None,:],axis=2)
    gamma=solve(W,-10*nc[:,0]);v=10*np.array([1.,0.,0.])+apply(Hhv,gamma)
    vp=v-np.sum(v*g['s'],axis=1)[:,None]*g['s'];speed=np.sqrt(np.sum(vp*vp,axis=1))
    f=1.225*g['ds'][:,None]*gamma[:,None]*np.cross(v,g['s'])
    return dict(W=W,gamma=gamma,velocity=v,perp_speed=speed,force=f,
                residual=np.sum((10*np.array([1.,0.,0.])+apply(Hcp,gamma))*nc,axis=1)/10)

def aggregate(g,forces,moments):
    return np.array([np.r_[forces[mask].sum(0),moments[mask].sum(0)] for mask in
        [g['beam']==1,g['beam']==2,np.ones(len(g['beam']),dtype=bool)]])

def transfer(g,b,Hhv,dHcp,dHhv,omega,lag,solve):
    """Unit physical lateral fin displacement; exp(i omega t)."""
    N=len(g['beam']);moving=np.zeros((N,3));moving[g['beam']==2,1]=1.
    forcing=np.sum(apply(dHcp,b['gamma'])*normals(g),axis=1)-1j*omega*np.sum(moving*normals(g),axis=1)
    D=np.diag(2/(np.pi*b['perp_speed']) if lag else np.zeros(N))
    gamma=solve(b['W']-1j*omega*D,-forcing)
    factor=1.225*g['ds'][:,None]
    forces={
        'circulation_response':factor*gamma[:,None]*np.cross(b['velocity'],g['s']),
        'induced_by_gamma':factor*b['gamma'][:,None]*np.cross(apply(Hhv,gamma),g['s']),
        'moving_field':factor*b['gamma'][:,None]*np.cross(apply(dHhv,b['gamma']),g['s']),
        'kinematic_velocity':factor*b['gamma'][:,None]*np.cross(-1j*omega*moving,g['s']),
        'rate_lift':factor*g['chord'][:,None]*(1j*omega*gamma/b['perp_speed'])[:,None]*np.cross(b['velocity'],g['s']) if lag else np.zeros((N,3),complex),
        'apparent':(1.225*np.pi/4*g['chord']**2*g['ds']*omega**2*np.sum(moving*g['normal'],axis=1))[:,None]*g['normal'],
        'moving_lever':np.zeros((N,3),complex)}
    terms={}
    for name,f in forces.items():
        arm=g['rm'] if name=='apparent' else g['hv']
        moment=np.cross(arm,f)
        if name=='moving_lever':moment=np.cross(moving,b['force'])
        terms[name]=aggregate(g,f,moment)
    total=sum(terms.values());rate=terms['rate_lift'];apparent=terms['apparent']
    return dict(gamma=gamma,forcing=forcing,D=D,terms=terms,
                wrenches=np.stack([total,rate,apparent,total-rate-apparent]),
                full_residual=(b['W']-1j*omega*D)@gamma+forcing)
