"""Compact adapter for the current source half-wing equations, not an oracle.

Retains production Euler section maps and literal SEGSPL material values.
Its 14-element result must reproduce the extracted full-aircraft mechanical
operator before refinement is interpreted. Fixed root, dead nodal loads.
"""
import numpy as np
from scipy.spatial.transform import Rotation,Slerp
from openswing.asw import parse_asw
from openswing.local_motion import rotation_matrix
from openswing.source_discrete import angles_from_frame,angle_matrix,_increments
from daedalus_wing_root_reference import hat,brace_state


class Discrete:
    L=56.
    F=100.
    def __init__(self,fixture,state,asw_text):
        self.fixture=fixture;self.state=state;self.t=state['stations'];self.ne=len(self.t)-1;self.nn=len(self.t)
        self.size=12*self.ne;self.a=np.arange(self.ne);self.b=self.a+1;self.ds=np.diff(self.t)
        model=parse_asw(asw_text,beam_interpolation='drela-segspl-v1');beam=model.beams[0]
        self.ends=[{key:beam.value(key,t,side=side) for key in ('EIcc','GJ','EInn','mg','Ccg')}
                   for t,side in ((self.t[:-1],'right'),(self.t[1:],'left'))]
        self.compliance=np.column_stack([2/(self.ends[0][key]+self.ends[1][key]) for key in ('EIcc','GJ','EInn')])
        self.force=np.zeros((self.nn,3));self.moment=np.zeros_like(self.force)
        for t,f,m in zip(fixture['stations'],fixture['dead_force'],fixture['dead_moment']):
            j,=np.flatnonzero(self.t==t);self.force[j]=f;self.moment[j]=m
        self.brace_node,=np.flatnonzero(self.t==fixture['brace']['station'])

    def unpack(self,z):
        pose=np.r_[z[self.size:self.size+6][None,:],z[:6*self.ne].reshape(self.ne,6)]
        r=self.state['positions']+self.L*pose[:,:3];q=rotation_matrix(pose[:,3:])@self.state['frames']
        internal=z[6*self.ne:self.size].reshape(self.ne,6)
        N=self.state['force']+self.F*internal[:,:3];M=self.state['moment']+self.F*self.L*internal[:,3:]
        return r,q,N,M

    def evaluate(self,z,*,brace=True):
        r,q,N,M=self.unpack(z);a,b=self.a,self.b;dr=r[b]-r[a]
        tavg=(q[a].transpose(0,2,1)+q[b].transpose(0,2,1))/2
        curvature=self.compliance*np.einsum('nij,nj->ni',tavg,M)
        qa,qb=angles_from_frame(q[a]),angles_from_frame(q[b]);k=(angle_matrix(qa)+angle_matrix(qb))/2
        translation=dr-(q[a,:,1]+q[b,:,1])*self.ds[:,None]/2
        rotation=np.einsum('nij,nj->ni',k,_increments(qa,qb))-curvature*self.ds[:,None]
        force=self.force.copy();moment=self.moment.copy()
        force[a]+=N;force[b]-=N
        moment[a]+=M+np.cross(dr,N)/2;moment[b]+=-M+np.cross(dr,N)/2
        if brace:
            spring=brace_state(r[self.brace_node],q[self.brace_node],self.fixture['brace'])
            force[self.brace_node]+=spring['force'];moment[self.brace_node]+=spring['moment']
        return np.r_[np.c_[translation/self.L,rotation].ravel(),(force[1:]/self.F).ravel(),
                     (moment[1:]/(self.F*self.L)).ravel(),force[0]/self.F,moment[0]/(self.F*self.L)]

    def derivative(self,step=1e-5,fourth=False):
        z=np.zeros(self.size+6);out=np.empty((self.size+6,self.size+6))
        for j in range(self.size+6):
            d=z.copy();d[j]=step
            if fourth:out[:,j]=(8*(self.evaluate(d,brace=False)-self.evaluate(-d,brace=False))-(self.evaluate(2*d,brace=False)-self.evaluate(-2*d,brace=False)))/(12*step)
            else:out[:,j]=(self.evaluate(d,brace=False)-self.evaluate(-d,brace=False))/(2*step)
        # The stiff axial brace loses precision when its two large endpoint
        # forces are subtracted. Insert its exact spatial force/couple tangent.
        node=self.brace_node;assert node>0
        spring=brace_state(self.state['positions'][node],self.state['frames'][node],self.fixture['brace'])
        rows=np.r_[6*self.ne+3*(node-1)+np.arange(3),9*self.ne+3*(node-1)+np.arange(3)]
        cols=6*(node-1)+np.arange(6)
        out[np.ix_(rows,cols)]+=spring['tangent']*np.r_[[self.L]*3,[1.]*3][None,:]/np.r_[[self.F]*3,[self.F*self.L]*3][:,None]
        return out

    def mass(self):
        out=np.zeros((self.size+6,self.size+6));g=self.fixture['gravity_constant']
        for end,fields in enumerate(self.ends):
            for e in range(self.ne):
                src=e+end;q=self.state['frames'][src];m=fields['mg'][e]*self.ds[e]/(2*g)
                arm=hat(q@np.array([fields['Ccg'][e],0.,0.]));diag=m*self.ds[e]**2/12*np.array([1.,0.,1.])
                I=(q*diag)@q.T;physical=np.block([[m*np.eye(3),-m*arm],[m*arm,I-m*arm@arm]])
                physical=physical*np.r_[[self.L]*3,[1.]*3][None,:]/np.r_[[self.F]*3,[self.F*self.L]*3][:,None]
                cols=6*(src-1)+np.arange(6) if src else self.size+np.arange(6)
                for dst in (e,e+1):
                    rows=(np.r_[6*self.ne+3*(dst-1)+np.arange(3),9*self.ne+3*(dst-1)+np.arange(3)]
                          if dst else self.size+np.arange(6))
                    out[np.ix_(rows,cols)]+=physical/2
        return out


def initial_state(fixture,original,factor):
    old=np.array(fixture['stations']);t=np.r_[np.concatenate([np.linspace(a,b,factor+1)[:-1] for a,b in zip(old[:-1],old[1:])]),old[-1]]
    r=np.column_stack([np.interp(t,old,np.array(fixture['positions'])[:,j]) for j in range(3)])
    q=Slerp(old,Rotation.from_matrix(fixture['material_frames']))(t).as_matrix()
    midpoint=(r[:-1]+r[1:])/2;old_r=np.array(fixture['positions']);oldmid=(old_r[:-1]+old_r[1:])/2
    idx=np.searchsorted(old,(t[:-1]+t[1:])/2)-1
    N=original['internal_force'][idx];M=original['internal_moment'][idx]+np.cross(oldmid[idx]-midpoint,N)
    if factor==1:
        r=np.array(fixture['positions']);q=np.array(fixture['material_frames'])
        N=original['internal_force'].copy();M=original['internal_moment'].copy()
    return dict(stations=t,positions=r,frames=q,force=N,moment=M)
