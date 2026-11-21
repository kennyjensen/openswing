"""Eight-cycle inclined-heave setup and independent transient reconstruction."""
import math
import numpy as np

from isae_suite_unsteady import model_text
from isae_ua_incidence_reference import fields, kinematics, steady_circulation, trajectory

ALPHA=9.
K=.94
AMPLITUDE=.5
SPEED=10.
CYCLES=8
PERIOD=math.pi/(SPEED*K)
GATES=dict(periodic_CL_fraction=.001,periodic_circulation_fraction=.001,
    periodic_rate_fraction=.001,cold_CL_fraction=.001,cold_circulation_fraction=.001,
    cold_rate_fraction=.001,fine_to_coarse_ratio=.35,amplitude_fraction=.001,
    phase_deg=.1,mean_CL_dynamic_fraction=.001,last_cycle_change_fraction=.0001,
    normalized_residual=1e-10,reference_agreement_fraction=1e-9)


def full_request(steps):
    alpha=math.radians(ALPHA)
    heave=np.array([-math.sin(alpha),0.,math.cos(alpha)])
    rows=[]
    for i in range(CYCLES*steps+1):
        t=PERIOD*i/steps
        acceleration=kinematics(t,amplitude_ratio=AMPLITUDE,k=K,speed=SPEED)[2]*heave
        rows.append(f'{t:.17g} {acceleration[0]:.17g} {acceleration[2]:.17g}')
    return dict(action='time',mode='time',source=model_text(),panels=4,
        numerics=dict(beam_interpolation='drela-segspl-v1',structural_operator='drela-moving-airflow-v1'),
        condition=dict(speed=SPEED,alpha=ALPHA,mach=0.,stall=False,aero_lag=True,
            gravity_magnitude=0.,position_earth=(AMPLITUDE/2*heave).tolist()),
        time=dict(frame='prescribed',duration=CYCLES*PERIOD,dt=PERIOD/steps,order=2,
            tolerance=1e-10,max_steps=4*CYCLES*steps,forcing='time Ax Az\n'+'\n'.join(rows)+'\n'))


def reference_history(steps,cycles=CYCLES):
    """Periodic quadrature plus the exact homogeneous transient from steady state."""
    phase_times=np.array([PERIOD*i/steps for i in range(steps+1)])
    periodic=trajectory(phase_times,alpha_deg=ALPHA,k=K,amplitude_ratio=AMPLITUDE,boundary='periodic')
    initial=steady_circulation(alpha_deg=ALPHA)
    difference=initial-periodic['initial_circulation']
    alpha=math.radians(ALPHA)
    rows=[]
    for i in range(cycles*steps+1):
        t=PERIOD*i/steps
        phase_index=(i-1)%steps+1 if i else 0
        z,w,a=kinematics(t,amplitude_ratio=AMPLITUDE,k=K,speed=SPEED)
        primitive=(SPEED*math.cos(alpha)*t+math.sin(alpha)*(z-AMPLITUDE/2))/2
        gamma=periodic['rows'][phase_index]['circulation']+difference*math.exp(-primitive)
        rows.append(dict(time=t,displacement=z,velocity=w,acceleration=a,
                         **fields(gamma,w,a,alpha_deg=ALPHA)))
    return dict(period=PERIOD,nominal_steps=steps,cycles=cycles,periodic=periodic,
                steady_initial_circulation=initial,cold_rows=rows,
                transient='(Gamma_steady-Gamma_periodic(0))*exp(-[V*cos(alpha)*t+sin(alpha)*(z(t)-z(0))]/(2*c))')
