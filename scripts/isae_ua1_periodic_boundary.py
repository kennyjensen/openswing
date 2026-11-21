"""Audit a resumed record separately from its first newly integrated step."""
import math

from isae_ua1_periodic_study import check_restart_join


def check_boundary(saved, samples):
    initial, first = samples[:2]
    assert initial['order'] == 0  # A presentation record, not a new Euler step.
    assert initial['time'] == saved['state']['time']
    assert initial['restart']['accepted_method']['effective_order'] == 2
    rounding = check_restart_join(saved['state'], initial['restart']['state'])
    rounding += check_restart_join(saved['older'], initial['restart']['older'])
    accepted = first['restart']['accepted_method']
    assert first['order'] == accepted['effective_order'] == 2
    assert accepted['kind'] == 'bdf' and accepted['scheme'] == 'drela-euler-bdf-v1'
    assert accepted['endpoint']['state'] == first['restart']['state']
    assert accepted['end_time'] == first['time']
    rounding += check_restart_join(saved['state'], accepted['previous'])
    rounding += check_restart_join(saved['older'], accepted['previous2'])
    step = first['time']-saved['state']['time']
    previous_step = saved['state']['time']-saved['older']['time']
    assert step > 0 and previous_step > 0
    assert accepted['step'] == first['step'] == step
    ratio = step/previous_step
    coefficients = [(1+2*ratio)/(step*(1+ratio)), -(1+ratio)/step, ratio**2/(step*(1+ratio))]
    assert len(accepted['coefficients']) == 3
    assert all(math.isclose(a, b, rel_tol=1e-12, abs_tol=1e-12)
               for a, b in zip(accepted['coefficients'], coefficients))
    return rounding
