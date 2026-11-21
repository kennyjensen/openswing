"""Inclined UA-2 startup refinement using the existing documented variable grid."""
import math
import numpy as np
from isae_ua2_incidence_time import full_request as uniform_request,PERIOD,CYCLES,ALPHA,K,SPEED,GATES as TIME_GATES
from isae_ua_startup import heave_grid

GATES={**TIME_GATES,'first_step_rate_fraction':.01,'velocity_fraction':.001,'position_fraction':.001}


def grid(steps):return heave_grid(PERIOD,steps,256,1.125)


def full_request(steps):
    request=uniform_request(steps)
    a=math.radians(ALPHA);direction=np.array([-math.sin(a),0.,math.cos(a)])
    omega=2*SPEED*K;rows=[]
    for t in grid(steps):
        acc=-.25*omega**2*math.cos(omega*t)*direction
        rows.append(f'{t:.17g} {acc[0]:.17g} {acc[2]:.17g}')
    request['time']['forcing']='time Ax Az\n'+'\n'.join(rows)+'\n'
    return request
