"""Independent straight-wing nonlinear heave reference from Drela's equations.

No OpenSwing parser, mesh, vortex kernel, residual, load or time-integrator
code is imported. Full-span cosine nodes and Glauert midpoint samples define
this explicit AR10 reconstruction. Mach, mean incidence and stall are zero.
Steady Eqs155-160 and unsteady Eqs34-35,43,49 determine the equations.
This is an equation reference, not a recovered native ASWING trajectory.
"""
import math
import numpy as np
from scipy.integrate import solve_ivp


class StraightWing:
    def __init__(self, panels, *, span=10., chord=1.):
        if type(panels) is not int or panels<4 or not span>0 or not chord>0:
            raise ValueError('Positive geometry and at least four panels required')
        self.panels,self.span,self.chord=panels,float(span),float(chord)
        self.nodes=-span/2*np.cos(np.pi*np.arange(panels+1)/panels)
        self.stations=-span/2*np.cos(np.pi*(np.arange(panels)+.5)/panels)
        self.widths=np.diff(self.nodes)
        left=self.stations[:,None]-self.nodes[None,:-1]
        right=self.stations[:,None]-self.nodes[None,1:]
        h=chord/2  # dCL/dalpha=2*pi, Eq157.
        # At the bound line, all collinear bound-segment contributions vanish.
        # The two semi-infinite legs give H. At the downstream control point,
        # integrating the finite segment and both rays gives C. Both act in
        # the direction (e_z,0,-e_x); this scalar representation rotates with
        # instantaneous incident wind instead of freezing its direction.
        self.H=(1/left-1/right)/(4*np.pi)
        self.C=((h+np.hypot(h,left))/left-(h+np.hypot(h,right))/right)/(4*np.pi*h)

    def fields(self,gamma,velocity,acceleration,*,speed=10.,rate=None):
        gamma=np.asarray(gamma,dtype=float)
        if gamma.shape!=(self.panels,) or not np.isfinite(gamma).all() or not speed>0:
            raise ValueError('One finite circulation per strip and positive speed required')
        incident=math.hypot(speed,velocity)
        ex,ez=speed/incident,-velocity/incident
        wake=self.H@gamma
        vx,vz=speed+ez*wake,-velocity-ex*wake
        local_speed=np.hypot(vx,vz)
        tangency=-velocity-ex*(self.C@gamma)
        required_rate=np.pi/2*local_speed*tangency
        actual_rate=required_rate if rate is None else np.asarray(rate,dtype=float)
        if actual_rate.shape!=gamma.shape or not np.isfinite(actual_rate).all():
            raise ValueError('One finite circulation rate per strip required')
        residual=(tangency-2/np.pi*actual_rate/local_speed)/incident
        scale=2/(speed**2*self.span*self.chord)
        circulatory=scale*np.dot(self.widths,gamma*vx)
        rate_lift=scale*np.dot(self.widths,self.chord*actual_rate*vx/local_speed)
        added=-np.pi*self.chord*acceleration/(2*speed**2)
        # The tangency-squared profile term is zero on an ODE solution. Retain
        # it for arbitrary-rate residual/load identity checks (steady Eq73).
        profile=scale*np.dot(self.widths,2*self.chord*vz/local_speed*(incident*residual)**2)
        return dict(circulation_rate=required_rate,relative_velocity=np.column_stack((vx,np.zeros_like(vx),vz)),
            local_speed=local_speed,tangency=tangency,residual=residual,
            CL_circulation=float(circulatory),CL_rate=float(rate_lift),CL_added=float(added),
            CL_profile=float(profile),CL=float(circulatory+rate_lift+added+profile))

    def trajectory(self,times,*,amplitude_ratio,k,speed=10.,rtol=1e-11,atol=1e-13,method='DOP853'):
        times=np.asarray(times,dtype=float)
        if times.ndim!=1 or len(times)<2 or times[0]!=0 or np.any(np.diff(times)<=0):
            raise ValueError('Increasing times from the cold initial state required')
        if not amplitude_ratio>0 or not k>0:
            raise ValueError('Positive peak-to-peak amplitude and reduced frequency required')
        omega=2*speed*k/self.chord;h=amplitude_ratio*self.chord/2
        def rhs(t,gamma):
            return self.fields(gamma,-h*omega*math.sin(omega*t),0.,speed=speed)['circulation_rate']
        if method not in ('DOP853','Radau'):
            raise ValueError('Use one of the two declared independent time methods')
        result=solve_ivp(rhs,(0,float(times[-1])),np.zeros(self.panels),t_eval=times,
            method=method,rtol=rtol,atol=atol)
        if not result.success:raise RuntimeError(result.message)
        rows=[]
        for t,gamma in zip(times,result.y.T):
            velocity=-h*omega*math.sin(omega*t);acceleration=-h*omega**2*math.cos(omega*t)
            fields=self.fields(gamma,velocity,acceleration,speed=speed)
            rows.append(dict(time=float(t),velocity=velocity,acceleration=acceleration,
                circulation=gamma.tolist(),circulation_rate=fields['circulation_rate'].tolist(),
                CL=fields['CL'],CL_circulation=fields['CL_circulation'],CL_rate=fields['CL_rate'],
                CL_added=fields['CL_added'],maximum_residual=float(np.max(np.abs(fields['residual'])))))
        return dict(rows=rows,evaluations=result.nfev,rtol=rtol,atol=atol,method=method,
            native_ASWING_comparison=False,independent_spatial_implementation=True,
            qualifications='Straight rigid wing, wind-aligned zero-core horseshoes on one physical beam, Mach=0, mean incidence=0, stall disabled.')
