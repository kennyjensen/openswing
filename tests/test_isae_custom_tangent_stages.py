from copy import deepcopy
from types import SimpleNamespace
import numpy as np
import pytest
from openswing.custom_constraints import check_custom_tangent
from scripts.isae_custom_tangent_stages import columns, assemble, conclude


def operating(count=1):
    constraints=[SimpleNamespace(quantity=f'user.r{i}',target=0.,residual_scale=1.) for i in range(count)]
    return SimpleNamespace(constraints=constraints,custom={c.quantity:True for c in constraints},initial_values=None)


def test_split_stencils_match_original_and_analytic_complete_tangent():
    op=operating(2);x=np.array([.2,-.1,.4,.6])
    def residual(v):
        a,b,c,d=v
        return np.array([a*a+2*b,3*b+c,np.sin(c)+d,a+4*d])
    expected=np.array([[.4,2,0,0],[0,3,1,0],[0,0,np.cos(.4),1],[1,0,0,4]])
    whole=check_custom_tangent(op,residual,x,2)
    blocks=[columns(op,residual,x,2,a,b) for a,b in ((0,1),(1,3),(3,4))]
    jac,_=assemble(blocks,len(x));np.testing.assert_allclose(jac,expected,rtol=1e-9,atol=1e-10)
    split=conclude(blocks,len(x))
    for key in ('one_sided_tangent_ratio','column_scaled_reciprocal_condition'):
        assert split[key] == pytest.approx(whole[key],abs=1e-14,rel=1e-12)
    assert sum(b['residual_evaluations'] for b in blocks)==3+4*len(x)


@pytest.mark.parametrize('fault',['missing','duplicate','overlap','shape','nonfinite'])
def test_incomplete_or_corrupt_columns_cannot_be_accepted(fault):
    op=operating();x=np.array([.2,.4]);residual=lambda v:np.array([2*v[0]+v[1],v[0]+3*v[1]])
    blocks=[columns(op,residual,x,1,a,b) for a,b in ((0,1),(1,2))]
    if fault=='missing':blocks.pop()
    elif fault=='duplicate':blocks.append(deepcopy(blocks[0]))
    elif fault=='overlap':blocks[1]['first']=0
    elif fault=='shape':blocks[0]['jacobian']=blocks[0]['jacobian'][:1]
    else:blocks[0]['jacobian'][0,0]=np.nan
    with pytest.raises(ValueError):conclude(blocks,2)


@pytest.mark.parametrize('kind',['nonsmooth','singular'])
def test_original_failure_gates_are_preserved(kind):
    op=operating();x=np.zeros(2)
    residual=(lambda v:np.array([v[0],abs(v[1])])) if kind=='nonsmooth' else (lambda v:np.array([v[0]+v[1],2*(v[0]+v[1])]))
    with pytest.raises(ValueError):check_custom_tangent(op,residual,x,1)
    blocks=[columns(op,residual,x,1,a,b) for a,b in ((0,1),(1,2))]
    with pytest.raises(ValueError):conclude(blocks,2)
