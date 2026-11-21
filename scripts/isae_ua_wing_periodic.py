"""Periodic straight-wing reference and an aligned, smooth startup time grid.

The physics remains in the independent Drela-equation implementation. This
module adds a converged periodic boundary condition, not a fitted response.
"""
import math
import numpy as np
from scipy.integrate import solve_ivp


def cycle_grid(period, steps, cycles=8, subdivisions=256, growth=1.125):
    """Grade startup onto the uniform lattice without tiny cycle-closing steps.

    A geometric ramp spans an integer number of nominal steps. Its first step
    is no larger than dt/subdivisions; the final ramp-to-uniform growth is also
    bounded by growth. Every subsequent cycle uses the same phase samples.
    """
    if not period>0 or type(steps) is not int or steps<16 or type(cycles) is not int or cycles<2:
        raise ValueError('Positive period, integer steps>=16 and cycles>=2 required')
    if subdivisions<2 or not 1<growth<=1.5:
        raise ValueError('Subdivisions>=2 and growth in (1,1.5] required')
    intervals=math.ceil(math.log(subdivisions)/math.log(growth))
    lattice_steps=math.ceil(1/(growth-1))
    first=lattice_steps*(growth-1)/(growth**intervals-1)
    while first>1/subdivisions:
        intervals+=1
        first=lattice_steps*(growth-1)/(growth**intervals-1)
    dt=period/steps
    ramp=[dt*first*(growth**j-1)/(growth-1) for j in range(intervals)]
    times=ramp+[period*j/steps for j in range(lattice_steps,steps*cycles+1)]
    delta=np.diff(times)
    assert np.max(delta)<=dt*(1+1e-11)
    assert np.max(delta[1:]/delta[:-1])<=growth*(1+1e-11)
    return times


def periodic_solution(wing,times,*,amplitude_ratio,k,speed=10.,method='DOP853',initial=None):
    """Converge the nonlinear one-period map, then return one complete cycle.

    DOP853 and Radau can each do this independently. No production solver or
    production matrix is used. The periodic initial state is never supplied
    to the production cold-start trajectories.
    """
    if method not in ('DOP853','Radau') or not amplitude_ratio>0 or not k>0:
        raise ValueError('Positive amplitude/frequency and a declared ODE method required')
    period=math.pi*wing.chord/(speed*k);omega=2*speed*k/wing.chord
    times=np.asarray(times,dtype=float)
    if times[0]!=0 or abs(times[-1]-period)>1e-12 or np.any(np.diff(times)<=0):
        raise ValueError('One increasing complete cycle from zero phase required')
    height=amplitude_ratio*wing.chord/2
    def rhs(t,gamma):
        w=-height*omega*math.sin(omega*t)
        return wing.fields(gamma,w,0.,speed=speed)['circulation_rate']
    state=np.zeros(wing.panels) if initial is None else np.asarray(initial,dtype=float).copy()
    history=[]
    for iteration in range(1,33):
        ode=solve_ivp(rhs,(0,period),state,method=method,rtol=1e-11,atol=1e-13)
        if not ode.success:raise RuntimeError(ode.message)
        end=ode.y[:,-1]
        change=float(np.max(np.abs(end-state))/max(np.max(np.abs(end)),1e-30))
        history.append(change);state=end
        if change<1e-11:break
    else:raise RuntimeError('Periodic boundary failed to converge in 32 cycles')
    ode=solve_ivp(rhs,(0,period),state,t_eval=times,method=method,rtol=1e-11,atol=1e-13)
    if not ode.success:raise RuntimeError(ode.message)
    rows=[]
    for t,gamma in zip(times,ode.y.T):
        w=-height*omega*math.sin(omega*t);a=-height*omega**2*math.cos(omega*t)
        fields=wing.fields(gamma,w,a,speed=speed)
        rows.append(dict(time=float(t),circulation=gamma.tolist(),circulation_rate=fields['circulation_rate'].tolist(),
            CL=fields['CL'],velocity=w,acceleration=a))
    closure=float(np.max(np.abs(ode.y[:,-1]-state))/np.max(np.abs(ode.y)))
    assert closure<1e-11
    return dict(rows=rows,initial_circulation=state.tolist(),closure_fraction=closure,
        boundary_iterations=iteration,boundary_change_fractions=history,method=method,rtol=1e-11,atol=1e-13)
