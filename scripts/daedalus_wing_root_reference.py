"""Independent inextensible spatial rod with a live offset brace.

No OpenSwing imports. Literal property tables, physical nodal dead loads and
the prescribed root pose define the problem. Steady force/moment balance and
unsteady real-mass equations are integrated as continuous spatial ODEs.
"""
import numpy as np
from scipy.interpolate import PPoly
from scipy.integrate import solve_ivp


def hat(v):
    x,y,z=v
    return np.array([[0.,-z,y],[z,0.,-x],[-y,x,0.]])


class Tables:
    """C2 cubics with zero third derivative in end intervals, split at jumps.

    Solve for knot second derivatives, independently of the production
    first-derivative tridiagonal implementation of SEGSPL/SPLIND(-999,-999).
    """
    def __init__(self,properties):
        self.parts={};self.knots=set()
        for name,data in properties.items():
            t=np.array(data['t']);v=np.array(data['values']);self.knots.update(t)
            cuts=np.r_[0,np.flatnonzero(np.diff(t)==0)+1,len(t)];parts=[]
            for lo,hi in zip(cuts[:-1],cuts[1:]):
                x,y=t[lo:hi],v[lo:hi];h=np.diff(x);d=np.diff(y)/h;n=len(x)
                assert n>=2 and np.all(h>0)
                if n==2:second=np.zeros(2)
                else:
                    a=np.zeros((n,n));b=np.zeros(n)
                    a[0,:2]=[1.,-1.];a[-1,-2:]=[1.,-1.]
                    for j in range(1,n-1):
                        a[j,j-1:j+2]=[h[j-1],2*(h[j-1]+h[j]),h[j]]
                        b[j]=6*(d[j]-d[j-1])
                    second=np.linalg.solve(a,b)
                coefficients=np.array([np.diff(second)/(6*h),second[:-1]/2,
                    d-h*(2*second[:-1]+second[1:])/6,y[:-1]])
                parts.append((x[0],x[-1],PPoly(coefficients,x)))
            self.parts[name]=parts

    def select(self,interior):
        selected={}
        for name,parts in self.parts.items():
            candidates=[p for lo,hi,p in parts if lo<interior<hi]
            assert len(candidates)==1,(name,interior)
            selected[name]=candidates[0]
        return selected


def brace_state(position,rotation,brace):
    arm=rotation@np.array(brace['material_arm']);vector=np.array(brace['anchor'])-position-arm
    length=np.linalg.norm(vector);direction=vector/length;stiffness=brace['EA']/brace['rest_length']
    tension=stiffness*(length-brace['rest_length']);force=tension*direction
    k=stiffness*np.outer(direction,direction)+tension/length*(np.eye(3)-np.outer(direction,direction))
    df=-k@np.c_[np.eye(3),-hat(arm)]
    dm=hat(arm)@df;dm[:,3:]+=hat(force)@hat(arm)
    return dict(force=force,moment=np.cross(arm,force),tangent=np.r_[df,dm],tension=tension,length=length)


class Rod:
    def __init__(self,fixture,rtol=1e-9):
        self.fixture=fixture;self.rtol=rtol;self.table=Tables(fixture['properties'])
        self.stations=np.array(fixture['stations']);self.force=np.array(fixture['dead_force']);self.moment=np.array(fixture['dead_moment'])
        assert self.stations[0]==0 and self.stations[-1]==56
        self.rootposition=np.array(fixture['positions'])[0];self.rootrotation=np.array(fixture['material_frames'])[0]
        self.ops=dict(base_rhs=0,dynamic_rhs=0,base_integrations=0,dynamic_integrations=0)

    def intervals(self):
        for node,(a,b) in enumerate(zip(self.stations[:-1],self.stations[1:]),1):
            grid=[a,*sorted(k for k in self.table.knots if a<k<b),b]
            for lo,hi in zip(grid[:-1],grid[1:]):yield lo,hi,node if hi==b else None

    @staticmethod
    def operator(state,s,polynomials):
        q=state[3:12].reshape(3,3);N=state[12:15];M=state[15:18];tangent=q[:,1]
        stiffness=np.array([float(polynomials[key](s)) for key in ('EIcc','GJ','EInn')])
        assert np.all(stiffness>0)
        compliance=(q/stiffness)@q.T
        a=np.zeros((12,12));a[:3,3:6]=-hat(tangent)
        a[3:6,3:6]=compliance@hat(M);a[3:6,9:12]=compliance
        a[9:12,:6]=hat(N)@a[:3,:6];a[9:12,6:9]=-hat(tangent)
        return a,tangent,stiffness

    def base(self,wrench):
        y=np.r_[self.rootposition,self.rootrotation.ravel(),wrench,np.r_[np.zeros((6,6)),np.eye(6)].ravel()]
        before=[y.copy()];after=[y.copy()];segments=[];spring=None
        for lo,hi,node in self.intervals():
            polynomials=self.table.select((lo+hi)/2)
            def ode(s,state):
                a,tangent,k=self.operator(state,s,polynomials);q=state[3:12].reshape(3,3)
                dq=q@hat((q.T@state[15:18])/k)
                return np.r_[tangent,dq.ravel(),np.zeros(3),-np.cross(tangent,state[12:15]),
                             (a@state[18:].reshape(12,6)).ravel()]
            sol=solve_ivp(ode,(lo,hi),y,method='DOP853',rtol=self.rtol,atol=.01*self.rtol,dense_output=True)
            self.ops['base_rhs']+=sol.nfev;self.ops['base_integrations']+=1
            assert sol.success,sol.message
            y=sol.y[:,-1].copy();segments.append(dict(lo=lo,hi=hi,node=node,dense=sol.sol,polynomials=polynomials))
            if node is not None:
                before.append(y.copy());y[12:15]-=self.force[node];y[15:18]-=self.moment[node]
                if node==self.fixture['brace']['node']:
                    spring=brace_state(y[:3],y[3:12].reshape(3,3),self.fixture['brace'])
                    y[12:18]-=np.r_[spring['force'],spring['moment']]
                    derivative=y[18:].reshape(12,6);derivative[6:]-=spring['tangent']@derivative[:6]
                after.append(y.copy())
        assert spring is not None
        return dict(before=np.array(before),after=np.array(after),end=y,segments=segments,brace=spring)

    def harmonic(self,base,frequency):
        omega=2*np.pi*frequency;y=np.eye(12).ravel();before=[y.copy()];after=[y.copy()]
        for segment in base['segments']:
            p=segment['polynomials']
            def ode(s,values):
                state=segment['dense'](s);a,_,_=self.operator(state,s,p)
                q=state[3:12].reshape(3,3);mass=float(p['mg'](s))/self.fixture['gravity_constant']
                arm=hat(q@np.array([float(p['Ccg'](s)),0.,0.]))
                b=np.zeros((12,12));b[6:9,:3]=mass*np.eye(3);b[6:9,3:6]=-mass*arm
                b[9:12,:3]=mass*arm;b[9:12,3:6]=-mass*arm@arm
                return ((a-omega**2*b)@values.reshape(12,12)).ravel()
            sol=solve_ivp(ode,(segment['lo'],segment['hi']),y,method='DOP853',rtol=self.rtol,atol=.01*self.rtol)
            self.ops['dynamic_rhs']+=sol.nfev;self.ops['dynamic_integrations']+=1
            assert sol.success,sol.message
            y=sol.y[:,-1].copy();node=segment['node']
            if node is not None:
                before.append(y.copy())
                if node==self.fixture['brace']['node']:
                    derivative=y.reshape(12,12);derivative[6:]-=base['brace']['tangent']@derivative[:6]
                after.append(y.copy())
        return dict(before=np.array(before).reshape(-1,12,12),after=np.array(after).reshape(-1,12,12),end=y.reshape(12,12))
