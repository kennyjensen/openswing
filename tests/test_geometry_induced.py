import numpy as np
import pytest
from openswing.aero import horseshoe_velocity
from openswing.geometry_partials import GeometryPartials,GeometryPartialsUnavailable,induced_columns
from test_geometry_partials import CASES,fixture


def resolved_reference(evaluate):
    """Two independently started physical stencils with the established refiner.

    Coarse DAE combines long translation scales with weak angular flow changes.
    Fixed tiny steps are roundoff limited in WASM. Use the existing production
    field-reference refinement and its unchanged 2e-8 error estimate, starting
    at two larger widths. The candidate Jacobian never influences selection.
    """
    from openswing.geometry_tangent import refined_field_column
    result=[]
    for width in [3e-4,1e-4]:
        samples=[evaluate(m*width) for m in [1,-1,2,-2]]
        value,report=refined_field_column(evaluate,width,samples,1.,tolerance=2e-8)
        assert report['error_estimate']<=2e-8
        result.append(value)
    return result


def original(e,g):
    p=g['p'];d=e.data;result={}
    for name,(locations,reference,physical,exclusions,bound) in g['queries'].items():
        if e.frozen:
            vortex=e.frozen.vortex(reference,physical,exclude_bound=bound)
            volume=e.frozen.volume(reference,**exclusions)
        else:
            core=g['cores'][None,:] if physical is None else np.where(np.asarray(physical)[:,None]==p['physical'][None,:],0.,g['cores'][None,:])
            vortex=horseshoe_velocity(locations[:,None,:],p['a'][None,:,:],p['b'][None,:,:],e.direction,e.pg,core,e.ground,exclude_bound=bound)
            volume=g['volume'].velocity(locations,**exclusions)
        result[name]=np.einsum('ijk,j->ik',vortex,d['gamma'])+e.condition.speed*volume
    return result


@pytest.mark.parametrize('name,extra',CASES)
@pytest.mark.parametrize('chart',['spatial','absolute'])
def test_composed_induced_flow_against_original_moving_source_kernels(name,extra,chart):
    n,e,g,state_at=fixture(name,extra,chart)
    e.direct_vortex={};e.direct_volume={}
    e.evaluate(g.base)
    selected=np.unique(np.r_[np.arange(6),np.arange(max(0,6*n.nn-6),6*n.nn),
        [6*node+part for node in e.engine_nodes for part in range(6)]]).astype(int)
    actual=induced_columns(e,g.base,g.columns(selected))
    worst=(0.,'')
    for k,j in enumerate(selected):
        def evaluate(increment):
            d=np.zeros(6*n.nn);d[j]=increment
            return original(e,e.prepare(state_at(d)))
        if name=='dae':references=resolved_reference(evaluate)
        else:
            references=[]
            for step in [1e-5,3e-6]:
                samples=[evaluate(m*step) for m in [1,-1,2,-2]]
                references.append({key:(8*(samples[0][key]-samples[1][key])-(samples[2][key]-samples[3][key]))/(12*step) for key in samples[0]})
        for expected_values in references:
            for key in actual:
                expected=expected_values[key]
                error=float(np.max(abs(actual[key][...,k]-expected)/(1+abs(expected)),initial=0.))
                worst=max(worst,(error,str(key)))
                assert error<2e-7,(name,chart,j,key,error)


def test_missing_or_stale_maps_and_working_budget_fail_explicitly():
    n,e,g,_=fixture('wing-body',{},'spatial')
    with pytest.raises(GeometryPartialsUnavailable,match='storage budget'):GeometryPartials(e,g.state,limit=1)
    with pytest.raises(GeometryPartialsUnavailable,match='owned vortex'):induced_columns(e,g.base,g.columns([0]))
    e.direct_vortex={};e.direct_volume={};e.evaluate(g.base)
    g.base['p']['a'][0,0]+=.01
    with pytest.raises(GeometryPartialsUnavailable,match='different geometry'):induced_columns(e,g.base,g.columns([0]))
