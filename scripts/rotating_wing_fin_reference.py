"""Independent filament quadrature and loaded rigid-rotation perturbation.

No production imports. Wind-aligned vortex/motion sampling and axis own-bound
exclusion are explicit model conventions; this does not identify legacy ASWING.
"""
import numpy as np

RHO=1.225
SPEED=10.
SOUND=340.294
XAX=.35
CDF=.01
CDP=.02
CM=.02
PIVOT=np.array([2.,0.,.4])
AXIS=np.array([1.,2.,3.])/np.sqrt(14.)


def rotation(axis,angle):
    axis=np.asarray(axis,dtype=float);axis=axis/np.linalg.norm(axis)
    x,y,z=axis;K=np.array([[0.,-z,y],[z,0.,-x],[-y,x,0.]])
    return np.eye(3)+np.sin(angle)*K+(1-np.cos(angle))*(K@K)


def geometry(n,h=0.):
    Q0=rotation([0,1,0],7*np.pi/180)@rotation([0,0,1],5*np.pi/180)
    Q=rotation(AXIS,h)@Q0
    result={k:[] for k in ['r0','r1','rm','c','s','normal','chord','beam','ds','t0','t1','tm']}
    for beam,lo,hi,chord in [(1,-2.,2.,1.),(2,.4,2.4,.75)]:
        t=(lo+hi)/2-(hi-lo)/2*np.cos(np.arange(n+1)*np.pi/n)
        tm=(lo+hi)/2-(hi-lo)/2*np.cos((np.arange(n)+.5)*np.pi/n)
        t[0],t[-1]=lo,hi
        def position(values):
            points=np.zeros((len(values),3))
            if beam==1:points[:,1]=values
            else:points[:,0]=2.;points[:,2]=values
            return points if beam==1 else PIVOT+(points-PIVOT)@Q.T
        r=position(t);rm=position(tm)
        c=np.tile([1.,0.,0.],(n,1));s=np.tile([0.,1.,0.] if beam==1 else [0.,0.,1.],(n,1))
        if beam==2:c=c@Q.T;s=s@Q.T
        for key,value in dict(r0=r[:-1],r1=r[1:],rm=rm,c=c,s=s,normal=np.cross(c,s),chord=np.full(n,chord),beam=np.full(n,beam),ds=np.diff(t),t0=t[:-1],t1=t[1:],tm=tm).items():result[key].append(value)
    g={k:np.concatenate(v) for k,v in result.items()}
    wind=np.array([1.,0.,0.]);across=np.linalg.norm(np.cross(wind,g['s']),axis=1)
    quarter=((.25-XAX)*g['chord']/across)[:,None]*wind
    g.update(a=g['r0']+quarter,b=g['r1']+quarter,hv=g['rm']+quarter,
             cp=g['rm']+quarter+(.5*g['chord']/across)[:,None]*wind,
             axis=g['rm'].copy())
    return g


def normals(g):
    incidence=2*np.pi/180
    return np.sin(incidence)*g['c']+np.cos(incidence)*g['normal']


def geometry_variation(g):
    k=np.zeros_like(g['rm']);k[g['beam']==2]=AXIS
    return dict(k=k,rm=np.cross(k,g['rm']-PIVOT),c=np.cross(k,g['c']),
                s=np.cross(k,g['s']),normal=np.cross(k,g['normal']),ncp=np.cross(k,normals(g)))


def field(g,degree,receiver):
    """Numerical Biot-Savart integration, with theta substitution on each line.

    The straight constant-section fixture guarantees all same-beam hv targets
    are on the bound line. Other segments contribute exactly zero there, as
    certified by their disjoint material intervals, without a q² epsilon floor.
    At axis targets only the own physical bound is excluded; CP keeps all bounds.
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
            if kind=='bound' and receiver in ('hv','axis'):
                active[j]=False;own_excluded+=1
            if kind=='bound' and receiver=='hv':
                other=(g['beam']==g['beam'][j]) & (np.arange(N)!=j)
                if not np.all((g['tm'][other]<g['t0'][j])|(g['tm'][other]>g['t1'][j])):
                    raise ValueError('Same-beam force receiver overlaps a different bound segment')
                collinear+=int(np.sum(other));active[other]=False
            u=tangent/np.linalg.norm(tangent);r=targets-origin;z=np.sum(r*u,axis=1);h=r-z[:,None]*u
            q2=np.sum(h*h,axis=1)+core[:,j]**2
            if np.any(active & (q2<=0)):raise ValueError('Undeclared singular reference receiver')
            ids=np.flatnonzero(active);q=np.sqrt(q2[ids]);lo=np.arctan2(-z[ids],q)
            hi=np.full(len(ids),np.pi/2) if length is None else np.arctan2(length-z[ids],q)
            half=(hi-lo)/2;theta=(hi+lo)[:,None]/2+half[:,None]*nodes
            integral=np.sum(np.cos(theta)*weights,axis=1)*half/q2[ids]
            result[ids,j,:]+=sign*np.cross(u,h[ids])*integral[:,None]/(4*np.pi)
    return result,dict(own_bound_excluded=own_excluded,collinear_outside_bound_zero=collinear)


def apply(H,gamma):return np.einsum('ijk,j->ik',H,gamma)


def aggregate(g,forces,moments):
    return np.array([np.r_[forces[mask].sum(0),moments[mask].sum(0)] for mask in
        [g['beam']==1,g['beam']==2,np.ones(len(g['beam']),dtype=bool)]])


def base(g,Hcp,Hhv,Haxis,solve):
    ncp=normals(g);W=np.sum(Hcp*ncp[:,None,:],axis=2)
    gamma=solve(W,-SPEED*ncp[:,0]);U=SPEED*np.array([1.,0.,0.])
    v=U+apply(Hhv,gamma);vcp=U+apply(Hcp,gamma);va=U+apply(Haxis,gamma)
    vp=v-np.sum(v*g['s'],axis=1)[:,None]*g['s']
    speed=np.linalg.norm(vp,axis=1);total_speed=np.linalg.norm(v,axis=1)
    factor=RHO*g['ds'][:,None];chord=g['chord'];quarter=g['rm']+((.25-XAX)*chord)[:,None]*g['c']
    lift=factor*gamma[:,None]*np.cross(v,g['s'])
    drag=.5*factor*chord[:,None]*(CDF*total_speed[:,None]*v+CDP*speed[:,None]*vp)
    scalar=.5*RHO*g['ds']*chord**2*CM*speed**2/np.sqrt(1-(speed/SOUND)**2)
    couple=scalar[:,None]*g['s']
    force=lift+drag;moment=np.cross(quarter,lift)+np.cross(g['rm'],drag)+couple
    return dict(W=W,gamma=gamma,velocity=v,cp_velocity=vcp,axis_velocity=va,perp=vp,
                perp_speed=speed,total_speed=total_speed,lift=lift,drag=drag,couple=couple,
                couple_scalar=scalar,force=force,moment=moment,residual=np.sum(vcp*ncp,axis=1)/SPEED)


def forcing_columns(g,b,dHcp):
    dg=geometry_variation(g);ncp=normals(g)
    theta=np.sum(dg['ncp']*b['cp_velocity'],axis=1)+np.sum(apply(dHcp,b['gamma'])*ncp,axis=1)
    rate=-np.sum(np.cross(dg['k'],g['cp']-PIVOT)*ncp,axis=1)
    return np.array([theta,rate,np.zeros(len(theta))])


def transfer(g,b,Hhv,dHcp,dHhv,omega,lag,solve):
    """Unit angular displacement around AXIS, exp(iωt), at the declared base."""
    lam=1j*omega;N=len(g['beam']);chord=g['chord'];dg=geometry_variation(g)
    columns=forcing_columns(g,b,dHcp);forcing=columns[0]+lam*columns[1]+lam**2*columns[2]
    D=np.diag(2/(np.pi*b['perp_speed']) if lag else np.zeros(N))
    gamma=solve(b['W']-lam*D,-forcing)
    vg=apply(Hhv,gamma);vh=apply(dHhv,b['gamma']);vk=-lam*np.cross(dg['k'],g['hv']-PIVOT)
    dv=vg+vh+vk;v=b['velocity'];span=g['s'];vspan=np.sum(v*span,axis=1)
    dvp=dv-(np.sum(dv*span+v*dg['s'],axis=1))[:,None]*span-vspan[:,None]*dg['s']
    du=np.sum(b['perp']*dvp,axis=1)/b['perp_speed'];dtotal=np.sum(v*dv,axis=1)/b['total_speed']
    factor=RHO*g['ds'][:,None]
    quarter=g['rm']+((.25-XAX)*chord)[:,None]*g['c']
    dquarter=dg['rm']+((.25-XAX)*chord)[:,None]*dg['c']
    half=g['rm']+((.5-XAX)*chord)[:,None]*g['c']
    forces={
        'circulation_response':factor*gamma[:,None]*np.cross(v,span),
        'induced_by_gamma':factor*b['gamma'][:,None]*np.cross(vg,span),
        'moving_field':factor*b['gamma'][:,None]*np.cross(vh,span),
        'kinematic_velocity':factor*b['gamma'][:,None]*np.cross(vk,span),
        'rotating_span':factor*b['gamma'][:,None]*np.cross(v,dg['s']),
        'rate_lift':factor*chord[:,None]*(lam*gamma/b['perp_speed'])[:,None]*np.cross(v,span) if lag else np.zeros((N,3),complex)}
    terms={name:aggregate(g,f,np.cross(quarter,f)) for name,f in forces.items()}
    zeros=np.zeros((N,3),complex)
    terms['moving_lift_arm']=aggregate(g,zeros,np.cross(dquarter,b['lift']))
    drag=.5*factor*chord[:,None]*(CDF*(b['total_speed'][:,None]*dv+dtotal[:,None]*v)+CDP*(b['perp_speed'][:,None]*dvp+du[:,None]*b['perp']))
    terms['profile_force']=aggregate(g,drag,np.cross(g['rm'],drag))
    terms['moving_drag_arm']=aggregate(g,zeros,np.cross(dg['rm'],b['drag']))
    dscalar=b['couple_scalar']*(2/b['perp_speed']+b['perp_speed']/(SOUND**2-b['perp_speed']**2))*du
    couple=dscalar[:,None]*span+b['couple_scalar'][:,None]*dg['s']
    terms['profile_couple']=aggregate(g,zeros,couple)
    mass=RHO*np.pi/4*chord**2*g['ds']
    tau=lam*np.sum(np.cross(b['axis_velocity'],dg['k'])*g['normal'],axis=1)
    acceleration=lam**2*np.cross(dg['k'],half-PIVOT)
    apparent=(mass*(tau-np.sum(acceleration*g['normal'],axis=1)))[:,None]*g['normal']
    pitch=(-mass*(chord/4*tau+chord**2/32*lam**2*np.sum(dg['k']*span,axis=1)))[:,None]*span
    terms['apparent_force']=aggregate(g,apparent,np.cross(half,apparent))
    terms['apparent_couple']=aggregate(g,zeros,pitch)
    total=sum(terms.values());rate=terms['rate_lift'];app=terms['apparent_force']+terms['apparent_couple']
    return dict(gamma=gamma,forcing=forcing,forcing_columns=columns,D=D,terms=terms,
                wrenches=np.stack([total,rate,app,total-rate-app]),
                full_residual=(b['W']-lam*D)@gamma+forcing)
