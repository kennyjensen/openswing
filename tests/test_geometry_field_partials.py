from copy import copy
import numpy as np
import pytest
from openswing.geometry_field_partials import GeometryFieldPartials
from test_geometry_partials import CASES,fixture
from test_geometry_induced import resolved_reference


CASES=CASES+[('jet-0',{'powers':{1:50000.}}),('jet-1',{'powers':{1:50000.}}),
 ('jet-2',dict(powers={1:50000.},ground_effect=1,
    gust=dict(type='sinusoid',amplitude=[.2,.1,.4],wavevector=[.21,.3,-.17],omega=.4)))]


@pytest.mark.parametrize('name,extra',CASES)
@pytest.mark.parametrize('chart',['spatial','absolute'])
def test_complete_field_jacobians_match_original_physical_stencils(name,extra,chart):
    n,e,g,state_at=fixture(name,extra,chart)
    reference=copy(e);reference.direct_vortex=None;reference.direct_volume=None;reference.jet_regions={}
    reference(g.state)
    e.direct_vortex={};e.direct_volume={}
    actual=GeometryFieldPartials(e,g.state,chart=chart)
    selected=np.unique(np.r_[np.arange(6),np.arange(max(0,6*n.nn-6),6*n.nn),
        [6*node+part for node in e.engine_nodes for part in range(6)]]).astype(int)
    values=actual.columns(selected)
    for k,j in enumerate(selected):
        def evaluate(increment):
            d=np.zeros(6*n.nn);d[j]=increment
            return reference(state_at(d))
        if name=='dae':references=resolved_reference(evaluate)
        else:
            references=[]
            for step in [1e-5,3e-6]:
                samples=[evaluate(m*step) for m in [1,-1,2,-2]]
                references.append({key:(8*(samples[0][key]-samples[1][key])-(samples[2][key]-samples[3][key]))/(12*step) for key in samples[0]})
        for expected_values in references:
            for key in values:
                expected=expected_values[key]
                error=float(np.max(abs(values[key][...,k]-expected)/(1+abs(expected)),initial=0.))
                assert error<2e-7,(name,chart,j,key,error)
