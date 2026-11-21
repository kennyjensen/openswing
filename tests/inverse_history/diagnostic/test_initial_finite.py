"""Finite residual samples must not become NaN-derived initial witnesses."""
import numpy as np
import pytest
from openswing.initial_diagnostics import controller_initial_alternatives
from openswing.nonlinear_initial import consistent_initial


@pytest.mark.parametrize('overflow',['array','side'])
def test_finite_samples_with_overflowed_derived_arithmetic_skip_and_restore(overflow):
    probing=False;cache={}
    def residual(x,d,t):
        cache['state']=x.copy();cache['rate']=d.copy();cache['time']=t
        value=np.array([d[0]-x[1],x[1]-np.clip(x[1],0,1)])
        off_grid=abs(t/.01-round(t/.01))>1e-8
        if probing and x[1]>1e-8 and t!=0 and (overflow=='array' or off_grid):value[0]=1e308
        return value
    guard=controller_initial_alternatives([1],[1],residual,1e-8)
    def diagnostic(**context):
        nonlocal probing
        probing=True
        return guard(**context)
    # The accepted root/Jacobian use the same regular small DAE. The optional
    # probes deliberately enter a domain where finite samples overflow a
    # derivative stencil; this supplies no accepted alternative-state witness.
    with np.errstate(over='ignore',invalid='ignore'):
        state,rate,report=consistent_initial(residual,np.zeros(2),[0,1],np.zeros(2),
            fixed_state_indices=[0],accepted_initial_diagnostic=diagnostic)
    assert report['accepted_initial_diagnostic']['witness'] is False
    assert report['accepted_initial_diagnostic']['domain_skips']>=1
    np.testing.assert_array_equal(cache['state'],state)
    np.testing.assert_array_equal(cache['rate'],rate)
    assert cache['time']==0.
