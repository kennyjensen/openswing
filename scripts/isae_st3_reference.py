"""Independent centered Rayleigh beam reference for the literal ST-3 inputs.

No OpenSwing imports. Cubic Hermite normal bending and linear spanwise twist
minimize strain/kinetic energy. Material numbers are transcribed from the three
pinned ASW files, not fitted to either frequency table. Axes coincide at the
section centroid in these files; the native adapter separately verifies that.
"""
import numpy as np
from scipy.linalg import eigh
from scipy.optimize import linear_sum_assignment

MATERIALS={
 '0_3_90':dict(EI=1.41,GJ=1.2,coupling=0.,mass=.283,offset=0.,EInn=1.85e4),
 'p15_0':dict(EI=1.2947,GJ=1.2,coupling=.5151,mass=.231,offset=.07,EInn=2.2775e4),
 'm15_0':dict(EI=1.29,GJ=1.2,coupling=-.5151,mass=.231,offset=.07,EInn=0.),
}
LENGTH=.558
ICC=9.2385e-7
INN=3.4623e-4


def element_fields(x,length):
    """[h,h',h'',phi,phi'] on [h0,h0',phi0,h1,h1',phi1]."""
    a=np.zeros((5,6));i=[0,1,3,4]
    a[0,i]=[1-3*x*x+2*x**3,length*(x-2*x*x+x**3),3*x*x-2*x**3,length*(-x*x+x**3)]
    a[1,i]=[(-6*x+6*x*x)/length,1-4*x+3*x*x,(6*x-6*x*x)/length,-2*x+3*x*x]
    a[2,i]=[(-6+12*x)/length**2,(-4+6*x)/length,(6-12*x)/length**2,(-2+6*x)/length]
    a[3,[2,5]]=[1-x,x];a[4,[2,5]]=[-1/length,1/length]
    return a


def modes(name,elements=96,gravity=0.,air_density=0.,count=5,material=None):
    """Gravity adds the compressive geometric stiffness of an upright beam.

    Finite axial shortening is neglected in this independent small-strain
    reference. Optional apparent mass is an explicit two-dimensional strip
    sensitivity, not a full finite-wing or matched experimental model.
    """
    p=dict(MATERIALS[name] if material is None else material)
    size=3*(elements+1);K,M,Kb,Kt=[np.zeros((size,size)) for _ in range(4)]
    nodes=np.linspace(0,LENGTH,elements+1);gx,gw=np.polynomial.legendre.leggauss(4)
    added=air_density*np.pi*.14**2/4
    for j,(left,right) in enumerate(zip(nodes[:-1],nodes[1:])):
        length=right-left;ids=np.arange(3*j,3*j+6);ix=np.ix_(ids,ids)
        for x,weight in zip((gx+1)/2,gw*length/2):
            h,dh,bh,phi,dp=element_fields(x,length)
            bending=p['EI']*np.outer(bh,bh);torsion=p['GJ']*np.outer(dp,dp)
            # theta_x=-h', theta_z=phi in this vertical straight-wing frame.
            coupling=-p['coupling']*(np.outer(bh,dp)+np.outer(dp,bh))
            axial=-p['mass']*gravity*(LENGTH-(left+x*length))
            K[ix]+=weight*(bending+torsion+coupling+axial*np.outer(dh,dh))
            Kb[ix]+=weight*bending;Kt[ix]+=weight*torsion
            M[ix]+=weight*((p['mass']+added)*np.outer(h,h)+p.get('Icc',ICC)*np.outer(dh,dh)
                           +(p.get('Ip',ICC+INN)+added*.14**2/32)*np.outer(phi,phi))
    values,vectors=eigh(K[3:,3:],M[3:,3:],subset_by_index=[0,count-1])
    assert np.all(values>0)
    shapes=np.vstack([np.zeros((3,count)),vectors]).T
    diagonal_energies=np.array([[v@Kb@v,v@Kt@v] for v in shapes])
    return dict(elements=elements,gravity=gravity,air_density=air_density,
        frequencies_Hz=(np.sqrt(values)/(2*np.pi)).tolist(),nodes=nodes.tolist(),
        shapes=shapes.reshape(count,elements+1,3).tolist(),
        diagonal_energy_fractions=(diagonal_energies/diagonal_energies.sum(axis=1)[:,None]).tolist(),
        stiffness_positive=True,mass_positive=True)


def weighted_shapes(nodes,shapes,mass,grid=None):
    """Common physical [centroid h,h',phi] samples with kinetic-energy weights."""
    if grid is None:grid=np.linspace(0,LENGTH,257)
    weights=np.ones(len(grid));weights[[0,-1]]=.5
    scale=np.sqrt(weights[:,None]*np.array([mass,ICC,ICC+INN]))
    return np.asarray([np.column_stack([np.interp(grid,nodes,s[:,j]) for j in range(3)])*scale for s in np.asarray(shapes)]).reshape(len(shapes),-1)


def assurance(a,b):
    return abs(a.conj()@b.T)**2/np.outer(np.sum(abs(a)**2,axis=1),np.sum(abs(b)**2,axis=1))


def branch_labels(name,gravity=0.,elements=48,steps=48):
    """Follow shapes from zero coupling; never choose labels by measured roots."""
    p=MATERIALS[name];old=modes(name,elements,gravity,material=dict(p,coupling=0.))
    counts={'B':0,'T':0};labels=[]
    for e in old['diagonal_energy_fractions']:
        kind='B' if e[0]>.999 else 'T';assert max(e)>.999
        counts[kind]+=1;labels.append(str(counts[kind])+kind)
    history=[]
    for fraction in np.linspace(0,1,steps+1)[1:]:
        new=modes(name,elements,gravity,material=dict(p,coupling=p['coupling']*fraction))
        matrix=assurance(weighted_shapes(old['nodes'],old['shapes'],p['mass']),weighted_shapes(new['nodes'],new['shapes'],p['mass']))
        a,b=linear_sum_assignment(-matrix);assert min(matrix[a,b])>.8,(name,gravity,fraction,float(min(matrix[a,b])))
        updated=['']*len(labels)
        for i,j in zip(a,b):updated[j]=labels[i]
        labels=updated
        history.append(dict(coupling_fraction=float(fraction),labels=labels,frequencies_Hz=new['frequencies_Hz'],minimum_shape_assurance=float(min(matrix[a,b]))))
        old=new
    return dict(labels=labels,history=history,meaning='Numerical branch labels followed by kinetic-energy-weighted physical shapes from zero coupling. Primary experimental labels remain approximate for coupled modes.')
