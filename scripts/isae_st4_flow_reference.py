"""Independent linear finite-span aeroelastic reference for literal ST4 Weight7a.

No OpenSwing imports. Cubic Hermite transverse displacement h at the elastic
axis, its span derivative, and linear twist phi form a Rayleigh beam. Constant
horseshoe strengths satisfy the published lagged flow equation at material
Glauert midpoints. Lift/rate lift and apparent inertia are integrated by virtual
work, using unsteady technical-description equations 33-36, 43-44 and 48-49.
This reference is limited to the straight, zero-incidence, fixed-frame pilot.
"""
import numpy as np
from scipy.sparse import bmat, csc_matrix, eye, diags
from scipy.sparse.linalg import LinearOperator, eigs, splu

from isae_st4_reference import fields


def normal_influence(nodes, samples, chord):
    """Normal (minus body-y) velocity of unit +z-bound, +x-wake horseshoes.

    Closed-form unsmoothed Biot-Savart in the straight x/z plane; distinct
    from the production vector implementation. All targets are at 3c/4,
    all bound segments at c/4. No images, compressibility or finite core.
    """
    dx = chord / 2
    za = samples[:, None] - nodes[:-1]
    zb = samples[:, None] - nodes[1:]
    ra, rb = np.hypot(dx, za), np.hypot(dx, zb)
    bound_y = (za/ra-zb/rb)/(4*np.pi*dx)
    wake_y = -(1+dx/rb)/(4*np.pi*zb)+(1+dx/ra)/(4*np.pi*za)
    return -(bound_y+wake_y)


def matrices(*, intervals=64, structure_intervals=32, speed=120., density=1.0771417304, gravity=-9.81):
    """Assemble original-dimension M xdot = A x; no fitted constants."""
    length, chord, t0 = 1.2192, .2032, .0001
    mass, icc, ip = 1.2947, .0078, .0078
    ei, gj = 41.1744*9.81, 20.2506*9.81
    ea, cg = .437*chord, .454*chord
    point_t = 17*.0254
    station = (point_t-t0)*length/(length-t0)
    points = [[.7237, -.0709, point_t], [.7237, .0823, point_t]]
    # Independent structural/aerodynamic resolutions. Extremely short cosine
    # beam elements make the fourth-order energy stiffness poorly conditioned.
    # A uniform energy mesh retains the exact weight station; replace a nearby
    # interior node instead of introducing an arbitrarily short extra element.
    uniform = np.linspace(0,length,structure_intervals+1)
    nearest = int(np.argmin(abs(uniform-station)))
    if 0<nearest<len(uniform)-1 and abs(uniform[nearest]-station)<.25*length/structure_intervals:
        uniform = np.delete(uniform,nearest)
    nodes = np.unique(np.r_[uniform,station])
    aero_nodes = np.unique(np.r_[length*(1-np.cos(np.linspace(0,np.pi,intervals+1)))/2,station])
    widths = np.diff(nodes)
    angle = np.arccos(np.clip(2*aero_nodes/length-1,-1,1))
    samples = length*(1+np.cos((angle[:-1]+angle[1:])/2))/2
    size, strips = 3*len(nodes), len(aero_nodes)-1
    stiffness, structural_mass, air_mass, rate = [np.zeros((size,size)) for _ in range(4)]
    lift = np.zeros((size,strips))
    flow_twist, flow_velocity = np.zeros((strips,size)), np.zeros((strips,size))
    gx, gw = np.polynomial.legendre.leggauss(4)
    added_mass = np.pi/4*density*chord**2
    for j,(a,b,ds) in enumerate(zip(nodes[:-1],nodes[1:],widths)):
        indices = np.arange(3*j,3*j+6)
        ix = np.ix_(indices,indices)
        for x,weight in zip((gx+1)/2,gw*ds/2):
            s = a+x*ds
            h,dh,ddh,phi,dp = fields(x,ds)
            centroid = h+(cg-ea)*phi
            half_chord = h+(.5*chord-ea)*phi
            downstream = points if s<station else []
            tension = gravity*(mass*(length-s)+sum(p[0] for p in downstream))
            first_moment = gravity*(mass*(cg-ea)*(length-s)+sum(p[0]*(p[1]-ea) for p in downstream))
            stiffness[ix] += weight*(ei*np.outer(ddh,ddh)+gj*np.outer(dp,dp)
                +tension*np.outer(dh,dh)+first_moment*(np.outer(dh,dp)+np.outer(dp,dh)))
            structural_mass[ix] += weight*(mass*np.outer(centroid,centroid)
                +icc*np.outer(dh,dh)+ip*np.outer(phi,phi))
            air_mass[ix] += weight*added_mass*(np.outer(half_chord,half_chord)
                +chord**2/32*np.outer(phi,phi))
            rate[ix] += weight*added_mass*speed*(np.outer(half_chord,phi)
                +chord/4*np.outer(phi,phi))
        # Integrate each constant strip load exactly across every intersected
        # structural element; no interpolation of discrete forces is used.
        for strip,(start,end) in enumerate(zip(aero_nodes[:-1],aero_nodes[1:])):
            low,high = max(a,start),min(b,end)
            if high<=low:
                continue
            for s,weight in zip(low+(gx+1)*(high-low)/2,gw*(high-low)/2):
                h,_,_,phi,_ = fields((s-a)/ds,ds)
                lift[indices,strip] += weight*(h+(.25*chord-ea)*phi)
    for j,sample in enumerate(samples):
        element = min(np.searchsorted(nodes,sample,side='right')-1,len(nodes)-2)
        indices = np.arange(3*element,3*element+6)
        h,_,_,phi,_ = fields((sample-nodes[element])/widths[element],widths[element])
        flow_twist[j,indices] = phi
        flow_velocity[j,indices] = h+(.75*chord-ea)*phi
    j = int(np.argmin(abs(nodes-station)))
    assert abs(nodes[j]-station)<1e-14
    ix = np.ix_(np.arange(3*j,3*j+3),np.arange(3*j,3*j+3))
    for weight,x,z in points:
        v = np.array([1.,z-station,x-ea])
        structural_mass[ix] += weight*np.outer(v,v)
        stiffness[3*j+1,3*j+1] += weight*gravity*(z-station)
    # Clamped root: h=h'=phi=0; reference-axis h_axis=h-ea*phi.
    cut = np.s_[3:,3:]
    k, ms, ma, ca = [csc_matrix(a[cut]) for a in [stiffness,structural_mass,air_mass,rate]]
    l = csc_matrix(lift[3:])
    h, v = csc_matrix(flow_twist[:,3:]), csc_matrix(flow_velocity[:,3:])
    influence = csc_matrix(normal_influence(aero_nodes,samples,chord))
    nq = size-3
    identity = eye(nq,format='csc')
    aa = bmat([[None,identity,csc_matrix((nq,strips))],[-k,-ca,-density*speed*l],
               [speed*h,v,influence]],format='csc')
    mm = bmat([[identity,None,None],[None,ms+ma,density*chord*l],
               [None,None,eye(strips,format='csc')*(2/(np.pi*speed))]],format='csc')
    return aa,mm,dict(nodes=nodes,aero_nodes=aero_nodes,samples=samples,nq=nq,stiffness=k,
        structural_mass=ms,air_mass=ma,rate=ca,flow_twist=h,flow_velocity=v,
        lift=l,influence=influence,speed=speed,density=density,gravity=gravity)


def modes(**kwargs):
    a,m,parts = matrices(**kwargs)
    # Equilibrate equations and displacement/rate units before factorization.
    # The energy stiffness has large entries on clustered short intervals.
    nq = parts['nq']; length, speed, chord = 1.2192, parts['speed'], .2032
    coordinate_scale = np.tile([length,1.,1.],nq//3)
    scale = np.r_[coordinate_scale,coordinate_scale*speed/length,
                  np.full(a.shape[0]-2*nq,speed*chord)]
    aa,mm = a@diags(scale),m@diags(scale)
    row = np.maximum(np.asarray(abs(aa).sum(axis=1)).ravel(),
                     np.asarray(abs(mm).sum(axis=1)).ravel()*speed/length)
    aa,mm = diags(1/row)@aa,diags(1/row)@mm
    shift = 300j
    factor = splu((aa-shift*mm).tocsc())
    operator = LinearOperator(a.shape,matvec=lambda x:factor.solve(mm@x),dtype=complex)
    inverse,vectors = eigs(operator,k=16,which='LM',tol=1e-11,
        maxiter=10000,v0=np.linspace(1,2,a.shape[0]).astype(complex))
    values = shift+1/inverse
    # Arnoldi is finished. Its LU is not used by the bordered Newton solves;
    # retaining it would needlessly overlap two large sparse factorizations.
    del operator, factor, inverse
    # Refine every Ritz pair in the original equations. Extended-precision
    # residuals prevent cancellation in K*q from hiding the required correction;
    # each bordered Newton factor remains ordinary complex-double sparse LU.
    # All displacement, velocity and circulation unknowns remain present.
    physical_a,physical_m = a.astype(np.clongdouble),m.astype(np.clongdouble)
    vectors = vectors.astype(np.clongdouble)
    checks = []
    refinement = []
    for k,original_value in enumerate(values):
        value=np.clongdouble(original_value);z=vectors[:,k].copy()
        pivot=int(np.argmax(abs(z)));z/=z[pivot]
        for iteration in range(7):
            physical=scale.astype(np.longdouble)*z
            av,mv=physical_a@physical,physical_m@physical
            residual=av-value*mv
            error=float(np.linalg.norm(residual)/(np.linalg.norm(av)+abs(value)*np.linalg.norm(mv)))
            if iteration==0:initial_error=error
            if error<1e-11:break
            column=-(physical_m@physical)/row
            constraint=csc_matrix(([1.],([0],[pivot])),shape=(1,a.shape[0]))
            border=bmat([[aa-complex(value)*mm,csc_matrix(np.asarray(column,dtype=complex)[:,None])],
                         [constraint,csc_matrix((1,1))]],format='csc')
            rhs=np.r_[np.asarray(-residual/row,dtype=complex),0j]
            correction=splu(border).solve(rhs)
            z+=correction[:-1].astype(np.clongdouble);value+=np.clongdouble(correction[-1])
        values[k]=complex(value);vectors[:,k]=scale.astype(np.longdouble)*z
        av,mv=physical_a@vectors[:,k],physical_m@vectors[:,k]
        error=float(np.linalg.norm(av-values[k]*mv)/(np.linalg.norm(av)+abs(values[k])*np.linalg.norm(mv)))
        checks.append(error)
        refinement.append(dict(initial_relative_residual=initial_error,final_relative_residual=error,
            corrections=iteration,scaled_root_change=float(abs(value-original_value)/(1+abs(value)))))
    assert max(checks)<1e-8,max(checks)
    parts['eigen_refinement']=refinement
    return values,vectors,parts,checks
