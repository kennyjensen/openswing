"""Independent inclined straight-wing equations for freestream-normal heave.

The analytic spanwise integrals are inherited from the independently verified
straight-wing reference. No production aerodynamics or integrator is imported.
Steady Eqs.155-160 and unsteady Eqs.31-35,43,49 define this specialization.
"""
import math
import numpy as np
from scipy.integrate import solve_ivp

from isae_ua_wing_nonlinear import StraightWing


class InclinedWing(StraightWing):
    def __init__(self,panels,*,alpha_deg,span=10.,chord=1.):
        super().__init__(panels,span=span,chord=chord)
        if not np.isfinite(alpha_deg) or abs(alpha_deg)>=80:
            raise ValueError('Finite forward-flow incidence required')
        self.alpha_deg=float(alpha_deg)
        a=math.radians(alpha_deg)
        self.ca,self.sa=math.cos(a),math.sin(a)
        self.heave=np.array([-self.sa,0.,self.ca])
        self.wind=np.array([self.ca,0.,self.sa])

    def motion(self,t,amplitude_ratio,k,speed):
        omega=2*speed*k/self.chord;height=amplitude_ratio*self.chord/2
        return height*math.cos(omega*t),-height*omega*math.sin(omega*t),-height*omega**2*math.cos(omega*t)

    def state(self,gamma,velocity,*,speed=10.):
        gamma=np.asarray(gamma)
        if gamma.shape!=(self.panels,) or not np.isfinite(gamma).all() or not speed>0:
            raise ValueError('Finite strip circulation and positive speed required')
        ux,uz=speed*self.ca+velocity*self.sa,speed*self.sa-velocity*self.ca
        if ux<=0:raise ValueError('Positive chordwise incident flow required')
        incident=math.hypot(speed,velocity);ex,ez=ux/incident,uz/incident
        downwash=self.H@gamma
        local_speed=np.sqrt(incident**2+downwash**2)
        tangency=uz-ex*(self.C@gamma)
        return downwash,local_speed,tangency,ux+ez*downwash,uz-ex*downwash,ex,incident

    def rates(self,gamma,velocity,*,speed=10.):
        _,u,t,*_=self.state(gamma,velocity,speed=speed)
        return np.pi/2*u*t

    def jacobian(self,gamma,velocity,*,speed=10.):
        d,u,t,_,_,ex,_=self.state(gamma,velocity,speed=speed)
        return np.pi/2*((d*t/u)[:,None]*self.H-ex*u[:,None]*self.C)

    def steady(self,*,speed=10.):
        return np.linalg.solve(self.C,np.full(self.panels,speed*self.sa/self.ca))

    def fields(self,gamma,velocity,acceleration,*,speed=10.,rate=None):
        gamma=np.asarray(gamma,dtype=float)
        _,u,t,vx,vz,_,incident=self.state(gamma,velocity,speed=speed)
        required=np.pi/2*u*t
        actual=required if rate is None else np.asarray(rate,dtype=float)
        if actual.shape!=gamma.shape or not np.isfinite(actual).all():
            raise ValueError('One finite rate per strip required')
        leakage=t-2/np.pi*actual/u
        cross=np.column_stack((-vz,np.zeros(self.panels),vx))
        relative=np.column_stack((vx,np.zeros(self.panels),vz))
        scale=2/(speed**2*self.span*self.chord)
        circulation=scale*np.einsum('i,ij->j',self.widths*gamma,cross)
        unsteady=scale*np.einsum('i,ij->j',self.widths*self.chord*actual/u,cross)
        apparent=np.array([0.,0.,-np.pi*self.chord*acceleration*self.ca/(2*speed**2)])
        profile=scale*np.einsum('i,ij->j',self.widths*2*self.chord/u*leakage**2,relative)
        total=circulation+unsteady+apparent+profile
        return dict(circulation_rate=required,relative_velocity=relative,local_speed=u,
            residual=leakage/incident,CF_circulation=circulation,CF_rate=unsteady,
            CF_apparent=apparent,CF_profile=profile,CF=total,
            CL=float(total@self.heave),CD=float(total@self.wind))

    def integrate(self,times,*,amplitude_ratio,k,speed=10.,method='DOP853',initial=None):
        times=np.asarray(times,dtype=float)
        if times.ndim!=1 or len(times)<2 or times[0]!=0 or np.any(np.diff(times)<=0):
            raise ValueError('Increasing times from zero required')
        if method not in ('DOP853','Radau') or amplitude_ratio<0 or k<=0:
            raise ValueError('Declared integration method and valid motion required')
        initial=self.steady(speed=speed) if initial is None else np.asarray(initial,dtype=float)
        def velocity(t):return self.motion(t,amplitude_ratio,k,speed)[1]
        options={} if method=='DOP853' else dict(jac=lambda t,g:self.jacobian(g,velocity(t),speed=speed))
        period=math.pi*self.chord/(speed*k)
        # At steady startup the derivative is almost zero. An automatic trial
        # at exactly one forcing period can also see zero motion and choose an
        # unstable first step. Bound the first trial by the local Jacobian and
        # resolve the forcing period; adaptive error control remains enabled.
        first_step=min(float(times[-1]),period/160,
            .1/max(1.,float(np.linalg.norm(self.jacobian(initial,velocity(0.),speed=speed),np.inf))))
        result=solve_ivp(lambda t,g:self.rates(g,velocity(t),speed=speed),(0.,float(times[-1])),initial,
            t_eval=times,method=method,rtol=1e-11,atol=1e-13,
            first_step=first_step,max_step=period/40,**options)
        if not result.success:raise RuntimeError(result.message)
        rows=[]
        for t,g in zip(times,result.y.T):
            z,w,a=self.motion(t,amplitude_ratio,k,speed)
            f=self.fields(g,w,a,speed=speed)
            rows.append(dict(time=float(t),displacement=z,velocity=w,acceleration=a,
                circulation=g.tolist(),**{key:(value.tolist() if isinstance(value,np.ndarray) else value)
                    for key,value in f.items()}))
        return dict(rows=rows,evaluations=result.nfev,method=method,rtol=1e-11,atol=1e-13,
                    first_step=first_step,maximum_step=period/40,
                    native_ASWING_comparison=False)

    def periodic(self,times,*,amplitude_ratio,k,speed=10.,method='DOP853'):
        period=math.pi*self.chord/(speed*k)
        times=np.asarray(times,dtype=float)
        if abs(times[-1]-period)>1e-12:raise ValueError('One complete period required')
        g=self.steady(speed=speed);history=[]
        for iteration in range(40):
            result=self.integrate([0.,period],amplitude_ratio=amplitude_ratio,k=k,speed=speed,method=method,initial=g)
            end=np.array(result['rows'][-1]['circulation'])
            closure=float(np.max(abs(end-g))/max(1.,float(np.max(abs(end)))))
            history.append(closure)
            g=end
            if closure<1e-11:break
        else:raise RuntimeError('Independent periodic boundary did not converge')
        result=self.integrate(times,amplitude_ratio=amplitude_ratio,k=k,speed=speed,method=method,initial=g)
        result.update(boundary='periodic',boundary_iterations=iteration+1,closure_history=history)
        return result
