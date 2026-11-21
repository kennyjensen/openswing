"""Independent Rayleigh-beam modes for the simplified Pazy modal inputs.

No OpenSwing imports. Cubic Hermite bending in two planes and linear torsion
use direct strain/kinetic-energy integrals. The common elastic, torsion and
mass-axis offset is removed by changing to that axis. Axial shortening is
neglected; optional upright gravity enters as compressive geometric stiffness.
Optional still-air inertia is integrated independently about the midchord,
including its offset from the common elastic/CG axis and flat-plate pitch term.
"""
import numpy as np
from scipy.sparse import csc_matrix
from scipy.sparse.linalg import eigsh

LENGTH = .55
MASS = .6787
ICC = 6.9567e-5
INN = 4.2793e-4


def fields(x, length):
    h = np.array([1-3*x*x+2*x**3, length*(x-2*x*x+x**3), 3*x*x-2*x**3, length*(-x*x+x**3)])
    dh = np.array([(-6*x+6*x*x)/length, 1-4*x+3*x*x, (6*x-6*x*x)/length, -2*x+3*x*x])
    ddh = np.array([(-6+12*x)/length**2, (-4+6*x)/length, (6-12*x)/length**2, (-2+6*x)/length])
    return h, dh, ddh


def matrices(elements=96, gravity=0., *, density=0.):
    """Independent strain/kinetic-energy matrices, with the root still present."""
    if not np.isfinite(density) or density < 0:
        raise ValueError('Fluid density must be finite and nonnegative.')
    if not isinstance(elements, int) or isinstance(elements, bool) or elements < 2:
        raise ValueError('At least two integer elements are required.')
    # Align the two material intervals without inserting a nearly coincident
    # node into a uniform grid. Such tiny cells unnecessarily magnify the
    # stiffness condition number and contaminate the lowest frequencies.
    left_count = min(elements-1, max(1, round(elements*.52/LENGTH)))
    nodes = np.r_[np.linspace(0., .52, left_count+1),
                  np.linspace(.52, LENGTH, elements-left_count+1)[1:]]
    size = 5*len(nodes)
    k = np.zeros((size,size)); m = np.zeros_like(k)
    gx, gw = np.polynomial.legendre.leggauss(4)
    for j, (a,b) in enumerate(zip(nodes[:-1], nodes[1:])):
        length = b-a; ids = np.arange(5*j,5*j+10); ix=np.ix_(ids,ids)
        for x,weight in zip((gx+1)/2,gw*length/2):
            s = a+x*length
            inn = INN if s <= .52 else INN+(.0041-INN)*(s-.52)/.03
            gj = 6.5 if s <= .52 else 6.5*2.6
            h,dh,ddh = fields(x,length)
            n = np.zeros((5,10)); d=np.zeros((3,10)); c=np.zeros((3,10))
            n[0,[0,1,5,6]]=h; n[1,[0,1,5,6]]=dh
            n[2,[2,3,7,8]]=h; n[3,[2,3,7,8]]=dh
            n[4,[4,9]]=[1-x,x]
            c[0,[0,1,5,6]]=ddh
            c[1,[4,9]]=[-1/length,1/length]
            c[2,[2,3,7,8]]=-ddh
            e=np.array([[4.4,0.,-.12],[0.,gj,0.],[-.12,0.,3300.]])
            axial=-MASS*gravity*(LENGTH-s)
            k[ix]+=weight*(c.T@e@c+axial*(np.outer(n[1],n[1])+np.outer(n[3],n[3])))
            m[ix]+=weight*(n.T@np.diag([MASS,ICC,MASS,inn,ICC+inn])@n)
            if density:
                # T_fluid = 1/2 mu (wdot - arm*phidot)^2 + 1/2 J phidot^2.
                # The literal model has 0.1 m chord, midchord at x=0 and
                # common elastic/CG axis at x=-0.005 m. In right-handed
                # c/s/n axes, rotation about +s moves +c toward -n.
                mu = density*np.pi*.1**2/4
                normal = n[0]-.005*n[4]
                m[ix] += weight*mu*(np.outer(normal,normal)+.1**2/32*np.outer(n[4],n[4]))
    return nodes,k,m


def modes(elements=96, gravity=0., count=8, *, density=0.):
    nodes,k,m = matrices(elements,gravity,density=density)
    stiffness, inertia = csc_matrix(k[5:,5:]), csc_matrix(m[5:,5:])
    # The low frequencies are far below the highest mesh-scale stiffness.
    # Direct spectral bisection loses small physical changes at that scale.
    # Shift-invert solves the same full energy matrices without truncation.
    values,vectors=eigsh(stiffness,k=count,M=inertia,sigma=0.,which='LM',tol=1e-12,
                        v0=np.random.default_rng(732).normal(size=stiffness.shape[0]))
    order=np.argsort(values);values=values[order];vectors=vectors[:,order]
    assert np.all(values>0)
    residual=stiffness@vectors-(inertia@vectors)*values
    scale=(np.linalg.norm(k[5:,5:],ord=np.inf)+values*np.linalg.norm(m[5:,5:],ord=np.inf))*np.max(abs(vectors),axis=0)
    backward=np.max(abs(residual),axis=0)/scale
    assert np.max(backward)<1e-10
    shapes=np.vstack([np.zeros((5,count)),vectors]).T.reshape(count,len(nodes),5)
    branches=[];counts={'OOP':0,'IP':0,'T':0}
    for shape in shapes:
        energy=np.array([np.trapezoid(abs(shape[:,0])**2,nodes),np.trapezoid(abs(shape[:,2])**2,nodes),LENGTH**2*np.trapezoid(abs(shape[:,4])**2,nodes)])
        kind=['OOP','IP','T'][int(np.argmax(energy))];counts[kind]+=1;branches.append(kind+str(counts[kind]))
    return dict(elements=len(nodes)-1,gravity=gravity,fluid_density=density,nodes=nodes.tolist(),
        frequencies_Hz=(np.sqrt(values)/(2*np.pi)).tolist(),labels=branches,shapes=shapes.tolist(),
        eigen_backward_errors=backward.tolist(),eigensolver='Full energy matrices, symmetric shift-invert at zero',
        approximation='Linear Rayleigh beam about the common elastic/CG axis; upright geometric stiffness, no finite axial shortening.')


def assurance(reference, nodes, shapes):
    grid=np.linspace(0.,LENGTH,301);weights=np.ones(len(grid));weights[[0,-1]]=.5
    # Common physical [normal displacement, chord displacement, span rotation].
    scale=np.sqrt(weights[:,None]*np.array([MASS,MASS,ICC+INN]))
    a=np.array([(np.column_stack([np.interp(grid,reference['nodes'],np.array(s)[:,i]) for i in [0,2,4]])*scale).ravel() for s in reference['shapes']])
    b=np.array([(np.column_stack([np.interp(grid,nodes,s[:,i].real)+1j*np.interp(grid,nodes,s[:,i].imag) for i in range(3)])*scale).ravel() for s in shapes])
    return abs(a.conj()@b.T)**2/np.outer(np.sum(abs(a)**2,axis=1),np.sum(abs(b)**2,axis=1))
