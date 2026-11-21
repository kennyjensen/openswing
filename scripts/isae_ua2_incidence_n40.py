"""Use the verified inclined time grids on the finer, 40-strip spatial mesh."""
from isae_ua2_incidence_nested import full_request as request20,grid,PERIOD,CYCLES
from isae_ua2_incidence_nested import GATES as TIME_GATES

GATES={**TIME_GATES,'mesh_lift_fraction':.001}


def full_request(steps):
    request=request20(steps)
    request['panels']=40
    return request
