"""Tighter adaptive integration for tip-rate reference accuracy; same equations."""
import math
import numpy as np
from scipy.integrate import solve_ivp
from isae_ua_wing_incidence import InclinedWing


class AccurateInclinedWing(InclinedWing):
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
            t_eval=times,method=method,rtol=1e-13,atol=1e-15,
            first_step=first_step,max_step=period/40,**options)
        if not result.success:raise RuntimeError(result.message)
        rows=[]
        for t,g in zip(times,result.y.T):
            z,w,a=self.motion(t,amplitude_ratio,k,speed)
            f=self.fields(g,w,a,speed=speed)
            rows.append(dict(time=float(t),displacement=z,velocity=w,acceleration=a,
                circulation=g.tolist(),**{key:(value.tolist() if isinstance(value,np.ndarray) else value)
                    for key,value in f.items()}))
        return dict(rows=rows,evaluations=result.nfev,method=method,rtol=1e-13,atol=1e-15,
                    first_step=first_step,maximum_step=period/40,
                    native_ASWING_comparison=False)

