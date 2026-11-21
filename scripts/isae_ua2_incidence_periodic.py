"""Eight-cycle UA-2 setup using documented BDF2 and a nested startup grid."""
import math
import numpy as np
from isae_ua_wing_periodic import cycle_grid
from isae_ua2_incidence_time import full_request as first_cycle_request, PERIOD
from isae_ua_incidence_periodic import GATES as PERIODIC_GATES

CYCLES = 8
GATES = {**PERIODIC_GATES, 'reference_agreement_fraction': 1e-8,
         'first_step_rate_fraction': .01, 'velocity_fraction': .001, 'position_fraction': .001}


def grid(steps):
    if steps not in (320, 640):
        raise ValueError('Use nested nominal 320 or 640 steps per cycle')
    times = cycle_grid(PERIOD, 160, CYCLES)
    for _ in range(1 if steps == 320 else 2):
        times = [0., *[t for a, b in zip(times, times[1:]) for t in ((a+b)/2, b)]]
    return times


def windows(steps):
    """Keep expensive startup jobs short; cap later jobs at 128 steps."""
    end = len(grid(steps))-1
    startup = 96 * (steps//320)
    result = []
    start = 0
    while start < end:
        stop = min(start+(16 if start < startup else 128), end)
        result.append((start, stop))
        start = stop
    return result


def full_request(steps):
    request = first_cycle_request(steps)
    direction = np.array([-math.sin(math.radians(9.)), 0., math.cos(math.radians(9.))])
    lines = ['time Ax Az']
    for t in grid(steps):
        acc = -.25*19**2*math.cos(19*t)*direction
        lines.append(f'{t:.17g} {acc[0]:.17g} {acc[2]:.17g}')
    request['time'].update(duration=CYCLES*PERIOD, max_steps=4*CYCLES*steps,
                           forcing='\n'.join(lines)+'\n')
    return request
