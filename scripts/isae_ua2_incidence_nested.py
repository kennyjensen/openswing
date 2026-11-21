"""Control time refinement by bisecting every original startup-grid interval."""
import math
import numpy as np
from isae_ua2_incidence_startup import GATES,grid as startup_grid
from isae_ua2_incidence_time import full_request as uniform_request,PERIOD,CYCLES,ALPHA,K,SPEED


def grid(steps):
    coarse=startup_grid(160)
    if steps==160:return coarse
    if steps!=320:raise ValueError('Use coarse160 or nested320')
    return [0.,*[t for a,b in zip(coarse,coarse[1:]) for t in ((a+b)/2,b)]]


def full_request(steps):
    request=uniform_request(steps)
    a=math.radians(ALPHA);direction=np.array([-math.sin(a),0.,math.cos(a)])
    omega=2*SPEED*K;rows=[]
    for t in grid(steps):
        acc=-.25*omega**2*math.cos(omega*t)*direction
        rows.append(f'{t:.17g} {acc[0]:.17g} {acc[2]:.17g}')
    request['time']['forcing']='time Ax Az\n'+'\n'.join(rows)+'\n'
    return request
