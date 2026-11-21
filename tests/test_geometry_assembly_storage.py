"""Consumed derivative workspaces must expire before sparse concatenation."""
import gc
import weakref
import numpy as np
import pytest
from openswing.aero import FlightCondition
from openswing.network import StaticNetwork
from openswing.tangent_influences import TangentInfluences
from test_direct_circulation import model_for,state_for


@pytest.mark.parametrize('direct',[False,True])
@pytest.mark.parametrize('order',[1,4])
def test_consumed_workspaces_release_before_sparse_join(monkeypatch,direct,order):
    import openswing.geometry_tangent as geometry
    import openswing.geometry_field_partials as partials
    import openswing.geometry_stencil as stencil
    n=StaticNetwork(model_for('wing-body'),4,FlightCondition(mach=.2,alpha=7,beta=3,
        ground_effect=1,position_earth=[0,0,30]),None,[])
    state=state_for(n,.3);baseline=n.residual(state).copy()
    cache=TangentInfluences(local_geometry=True);n.tangent_influences=cache
    references=[];retained=[];capture={};joins=[]
    def watch(constructor):
        class Watched(constructor):
            def __init__(self,*args,**kwargs):
                super().__init__(*args,**kwargs)
                references.append(weakref.ref(self))
        return Watched
    for module,name in [(geometry,'GeometryFields'),(partials,'GeometryFieldPartials'),(stencil,'GeometryStencil')]:
        monkeypatch.setattr(module,name,watch(getattr(module,name)))
    original=geometry.hstack
    def join(*args,**kwargs):
        assert references and all(ref() is None for ref in references)
        assert n.iteration_fields is None and n.tangent_influences is cache
        assert 'fields' not in capture  # publish only after assembly succeeds
        for arrays,copies in retained:
            for key in arrays:np.testing.assert_array_equal(arrays[key],copies[key])
        joins.append(True)
        return original(*args,**kwargs)
    monkeypatch.setattr(geometry,'hstack',join)
    def retain(selected,arrays):
        # Output-field callers are allowed to own these views beyond assembly.
        retained.append((arrays,{key:value.copy() for key,value in arrays.items()}))
    enabled=gc.isenabled();gc.disable()
    try:
        matrix,report=geometry.geometry_columns(n,lambda d:n.residual(state+d),lambda d:state+d,
            np.maximum(1.,abs(state)),difference_order=order,_nodewise_state=True,
            _direct_geometry=direct,_direct_vortex=True,_direct_volume=True,
            _field_columns=retain,_captured_fields=capture)
        assert len(joins)==1 and matrix.shape==(n.size,6*n.nn)
        assert report['direct_geometry_columns']==(6*n.nn if direct else 0)
        assert report['geometry_groups']>0 if not direct else report['geometry_groups']==0
        assert capture['fields'].circulation_aero is not None
        assert all(ref() is None for ref in references)
        np.testing.assert_array_equal(n.residual(state),baseline)
    finally:
        n.tangent_influences=None
        if enabled:gc.enable()
