"""Independent source beam compatibility and its complete local tangent.

Drela steady Eqs.3/10 supply rotation products; curvature maps are derived as
vee(R.T dR/dq), rather than importing or copying native Euler/curvature code.
Eqs.18--19 and 48/50--54 supply the section law and endpoint discretization.
Parsed endpoint materials and the declared fixed unloaded interval lengths
are inputs. The actual case has no material damping or stepped reference axes.
"""
import numpy as np
from scipy.spatial.transform import Rotation


GENERATORS=np.array([[[0,0,0],[0,0,-1],[0,1,0]],
                     [[0,0,1],[0,0,0],[-1,0,0]],
                     [[0,-1,0],[1,0,0],[0,0,0]]],dtype=float)


def vee(m):
    return np.array([m[2,1]-m[1,2],m[0,2]-m[2,0],m[1,0]-m[0,1]])/2


def composed(angles,body=False):
    # q=[phi,theta,psi]. Local-to-body is the transpose of printed T.
    axes,indices=([2,0,1],[2,0,1]) if body else ([0,2,1],[0,2,1])
    pieces=[]
    for axis,index in zip(axes,indices):
        g=GENERATORS[axis];angle=angles[index]
        pieces.append(np.eye(3)+np.sin(angle)*g+(1-np.cos(angle))*(g@g))
    frame=pieces[0]@pieces[1]@pieces[2]
    columns=np.zeros((3,3),dtype=np.result_type(angles,float))
    for j,(axis,index) in enumerate(zip(axes,indices)):
        factors=pieces.copy();factors[j]=GENERATORS[axis]@factors[j]
        derivative=factors[0]@factors[1]@factors[2]
        columns[:,index]=vee(frame.T@derivative)
    return frame,columns


def recovered(frame,body):
    # SciPy supplies an independent Euler decomposition. Each result is checked
    # by multiplying the three printed rotations back together.
    sequence='ZXY' if body else 'XZY';indices=[2,0,1] if body else [0,2,1]
    angles=np.empty(3);angles[indices]=Rotation.from_matrix(frame).as_euler(sequence)
    reconstructed,k=composed(angles,body)
    assert np.max(abs(reconstructed-frame))<2e-12
    assert np.linalg.cond(k)<1e6
    return angles,k


def material_law(properties):
    """Solve the translated moment law on finite-stiffness directions."""
    p=properties
    e=np.array([[p['EIcc'],p['EIcs'],p['EIcn']],
                [p['EIcs'],p['GJ'],p['EIsn']],[p['EIcn'],p['EIsn'],p['EInn']]])
    finite=np.flatnonzero(np.isfinite(np.diag(e)));inverse=np.zeros((3,3))
    sub=e[np.ix_(finite,finite)]
    if len(finite):
        assert np.min(np.linalg.eigvalsh(sub))>0
        inverse[np.ix_(finite,finite)]=np.linalg.solve(sub,np.eye(len(finite)))
    h=np.array([[0,p['Nta'],0],[-p['Nea'],0,p['Cea']],[0,-p['Cta'],0]])
    direct=np.diag([1/p['GKc'],1/p['EA'],1/p['GKn']])
    return np.block([[direct+h.T@inverse@h,h.T@inverse],[inverse@h,inverse]])


class Compatibility:
    def __init__(self,fixture):
        self.fixture=fixture;self.a,self.b=fixture['ends'].T
        self.length=fixture['length'];self.L=fixture['L'];self.F=fixture['F'];self.ML=fixture['ML']
        self.frame=fixture['frames'];self.force=fixture['force'];self.moment=fixture['moment']
        self.angles=np.empty((len(self.a),2,3));self.K=np.empty((len(self.a),2,3,3))
        self.K_partial=np.empty((len(self.a),2,3,3,3));rest=[];partials=[]
        self.reconstruction_error=0.;self.k_partial_step_error=0.
        for i,body in enumerate(fixture['body']):
            jig_angles=[];jig_maps=[]
            for end in range(2):
                q,k=recovered(self.frame[i,end],body);self.angles[i,end]=q;self.K[i,end]=k
                self.reconstruction_error=max(self.reconstruction_error,float(np.max(abs(composed(q,body)[0]-self.frame[i,end]))))
                derivatives=[]
                for step in (1e-24,1e-20):
                    derivatives.append(np.stack([composed(q.astype(complex)+1j*step*np.eye(3)[j],body)[1].imag/step for j in range(3)],axis=-1))
                self.K_partial[i,end]=derivatives[-1]
                self.k_partial_step_error=max(self.k_partial_step_error,float(np.max(abs(derivatives[0]-derivatives[1]))))
                q0,k0=recovered(fixture['jig_frames'][i,end],body);jig_angles.append(q0);jig_maps.append(k0)
            delta0=jig_angles[1]-jig_angles[0];assert max(abs(delta0))<np.pi
            rest.append((jig_maps[0]+jig_maps[1])@delta0/2)
        self.rest=np.array(rest)
        self.delta_angles=self.angles[:,1]-self.angles[:,0]
        assert np.max(abs(self.delta_angles))<np.pi
        self.mean_frame=self.frame.mean(axis=1);self.mean_K=self.K.mean(axis=1)
        self.local_force=np.einsum('nji,nj->ni',self.mean_frame,self.force)
        self.local_moment=np.einsum('nji,nj->ni',self.mean_frame,self.moment)
        self.law=np.array([material_law({k:(v[i,0]+v[i,1])/2 for k,v in fixture['material'].items()}) for i in range(len(self.a))])
        strain=np.einsum('nij,nj->ni',self.law,np.c_[self.local_force,self.local_moment])
        self.strain,self.curvature=strain[:,:3],strain[:,3:]
        self.direction=self.strain+np.array([0.,1.,0.])

    def residual(self):
        r=self.fixture['positions'];delta=r[self.b]-r[self.a]
        translation=delta-np.einsum('nij,nj->ni',self.mean_frame,self.direction)*self.length[:,None]
        rotation=np.einsum('nij,nj->ni',self.mean_K,self.delta_angles)-self.rest-self.curvature*self.length[:,None]
        return np.c_[translation/self.L,rotation].ravel()

    def tangent(self,displacement,angle,dforce,dmoment):
        """Physical endpoint translation/spatial rotation, body N/M amplitudes."""
        theta=angle[[self.a,self.b]].transpose(1,0,2)
        skew=np.einsum('nej,jkl->nekl',theta,GENERATORS)
        drframes=skew@self.frame;dmean=drframes.mean(axis=1)
        localtheta=np.einsum('neji,nej->nei',self.frame,theta)
        dq=np.linalg.solve(self.K,localtheta[...,None])[...,0]
        dk=np.einsum('neijk,nek->neij',self.K_partial,dq).mean(axis=1)
        df=np.einsum('nji,nj->ni',dmean,self.force)+np.einsum('nji,nj->ni',self.mean_frame,dforce)
        dm=np.einsum('nji,nj->ni',dmean,self.moment)+np.einsum('nji,nj->ni',self.mean_frame,dmoment)
        strains=np.einsum('nij,nj->ni',self.law,np.c_[df,dm]);deps,dkappa=strains[:,:3],strains[:,3:]
        translation=(displacement[self.b]-displacement[self.a]
            -(np.einsum('nij,nj->ni',dmean,self.direction)+np.einsum('nij,nj->ni',self.mean_frame,deps))*self.length[:,None])
        changing_K=np.einsum('nij,nj->ni',dk,self.delta_angles)
        changing_angles=np.einsum('nij,nj->ni',self.mean_K,dq[:,1]-dq[:,0])
        constitutive=-dkappa*self.length[:,None]
        rotation=changing_K+changing_angles+constitutive
        return np.c_[translation/self.L,rotation].ravel(),dict(changing_K=changing_K,changing_angles=changing_angles,constitutive=constitutive)

    def matrix(self,size):
        """Local assembly of all beam-compatibility derivatives; no physics probes."""
        nn=len(self.fixture['positions']);ne=len(self.a)
        output=np.zeros((6*ne,size))
        # Independent local fixtures avoid simultaneous neighbouring-node
        # perturbations leaking into the wrong element's column assignment.
        rows=np.arange(6*ne).reshape(ne,6)
        for j in range(nn):
            touching=np.flatnonzero((self.a==j)|(self.b==j))
            if not len(touching):continue
            for axis in range(6):
                dr=np.zeros((nn,3));theta=np.zeros_like(dr);dN=np.zeros((ne,3));dM=np.zeros_like(dN)
                if axis<3:dr[j,axis]=self.L
                else:theta[j,axis-3]=1.
                value,_=self.tangent(dr,theta,dN,dM)
                output[rows[touching].ravel(),6*j+axis]=value[rows[touching].ravel()]
        # Force/moment coordinates are independent between intervals.
        for axis in range(6):
            dr=np.zeros((nn,3));theta=np.zeros_like(dr);dN=np.zeros((ne,3));dM=np.zeros_like(dN)
            if axis<3:dN[:,axis]=self.F
            else:dM[:,axis-3]=self.ML
            value,_=self.tangent(dr,theta,dN,dM)
            for i in range(ne):output[rows[i],6*nn+6*i+axis]=value[rows[i]]
        return output
