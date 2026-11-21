"""One-cycle inclined UA-2 production setup; full forcing exists at startup."""
import math
import numpy as np
from isae_suite_unsteady import model_text

ALPHA=9.
K=.95
SPEED=10.
CYCLES=1
PERIOD=math.pi/(SPEED*K)
GATES=dict(cold_CL_fraction=.001,cold_circulation_fraction=.001,cold_rate_fraction=.001,
           fine_to_coarse_ratio=.35,normalized_residual=1e-10)


def full_request(steps):
    a=math.radians(ALPHA);direction=np.array([-math.sin(a),0.,math.cos(a)])
    omega=2*SPEED*K
    rows=[]
    for i in range(steps+1):
        t=PERIOD*i/steps;acc=-.25*omega**2*math.cos(omega*t)*direction
        rows.append(f'{t:.17g} {acc[0]:.17g} {acc[2]:.17g}')
    return dict(action='time',mode='time',source=model_text(10.),panels=20,
        numerics=dict(beam_interpolation='drela-segspl-v1',structural_operator='drela-moving-airflow-v1'),
        condition=dict(speed=SPEED,alpha=ALPHA,mach=0.,stall=False,aero_lag=True,
            gravity_magnitude=0.,position_earth=(.25*direction).tolist()),
        time=dict(frame='prescribed',duration=PERIOD,dt=PERIOD/steps,order=2,
            tolerance=1e-10,max_steps=4*steps,forcing='time Ax Az\n'+'\n'.join(rows)+'\n'))
