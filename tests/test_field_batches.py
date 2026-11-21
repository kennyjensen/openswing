"""Batched field actions retain every original stencil and physical guard."""
import numpy as np
import pytest
from openswing.geometry_stencil import GeometryStencil
from openswing.geometry_tangent import GeometryFields
from openswing.vortex_tangent import VortexSourceTangent,VortexDerivativeUnavailable
from openswing.volume_tangent import VolumeSourceTangent,VolumeDerivativeUnavailable
from test_geometry_stencil import context,CASES,equal
from field_product_assertions import operators_close


def samples(example='wing-body',extra=None):
    n,s,e,base,state,zero,scales=context(example,extra)
    plan=GeometryStencil(e,base,4);plan.build(state,zero,scales,1e-5,(1.,-1.,2.,-2.))
    return n,s,e,plan


@pytest.mark.parametrize('example,extra',CASES)
def test_every_batched_field_sample_equals_original_evaluation(example,extra):
    n,s,e,plan=samples(example,extra)
    try:
        for j in range(6*n.nn):
            geometries=[plan.sample(j,phase) for phase in range(4)]
            actual=e.evaluate_many(geometries);expected=[e.evaluate(g) for g in geometries]
            for a,b in zip(actual,expected):
                assert a.keys()==b.keys()
                for key in a:equal(a[key],b[key])
        if not e.frozen and e.vortex_sources is not None and e.volume_sources is not None:
            assert e.field_batches>0 and e.field_batch_queries>0
        assert e.field_batch_budget_fallbacks==0
    finally:plan.close()


def test_storage_limit_and_missing_query_maps_keep_individual_paths():
    n,s,e,plan=samples()
    geometries=[plan.sample(7,phase) for phase in range(4)]
    try:
        old=e.direct_volume_bytes;e.direct_volume_bytes=128*1024**2
        actual=e.evaluate_many(geometries);expected=[e.evaluate(g) for g in geometries]
        assert e.field_batch_budget_fallbacks==1 and e.field_batches==0
        e.direct_volume_bytes=old
        for a,b in zip(actual,expected):
            for key in a:equal(a[key],b[key])
        e.direct_vortex['cp']=None
        actual=e.evaluate_many(geometries);expected=[e.evaluate(g) for g in geometries]
        for a,b in zip(actual,expected):
            for key in a:equal(a[key],b[key])
        assert e.field_batches==1
    finally:plan.close()


def test_batch_length_source_identity_and_receiver_layout_guards():
    n,s,e,plan=samples();g=plan.sample(0,0)
    try:
        vortex=e.direct_vortex['engine'];volume=e.direct_volume['engine'];points=g['queries']['engine'][0]
        vc=e.vortex_sources.difference(g['p']['a'],g['p']['b'],g['cores'],g['p']['physical'])
        bc=e.volume_sources.difference(g['volume']);physical=g['queries']['engine'][2]
        def rejected(call,kind):
            try:call()
            except kind:return
            raise AssertionError('Invalid batch was accepted')
        assert vortex.values_shared([],[],[])==[] and volume.values_shared([],[],[])==[]
        rejected(lambda:vortex.values_shared([],[vc],[]),VortexDerivativeUnavailable)
        rejected(lambda:volume.values_shared([g['volume']],[],[]),VolumeDerivativeUnavailable)
        rejected(lambda:vortex.values_shared([points,points],[vc],[physical]),VortexDerivativeUnavailable)
        rejected(lambda:volume.values_shared([g['volume']],[points,points],[bc]),VolumeDerivativeUnavailable)
        wrong=VortexSourceTangent(g['p']['a'],g['p']['b'],g['cores'],g['p']['physical'])
        rejected(lambda:vortex.values_shared([points],[wrong.difference(g['p']['a'],g['p']['b'],g['cores'],g['p']['physical'])],[physical]),VortexDerivativeUnavailable)
        wrong=VolumeSourceTangent(g['volume'])
        rejected(lambda:volume.values_shared([g['volume']],[points],[wrong.difference(g['volume'])]),VolumeDerivativeUnavailable)
        bad=np.zeros((len(points)+1,3))
        rejected(lambda:vortex.values_shared([bad],[vc],[physical]),VortexDerivativeUnavailable)
        rejected(lambda:volume.values_shared([g['volume']],[bad],[bc]),VolumeDerivativeUnavailable)
    finally:plan.close()


def test_nonzero_elastic_motion_and_negative_zero_keep_individual_physics():
    n,s,e,plan=samples('powered',{'powers':{1:7}})
    try:
        originals=e.local_values
        for moving in (False,True):
            e.local_values=tuple(np.full_like(v,.013*(i+1) if moving else -0.) for i,v in enumerate(originals))
            geometries=[plan.sample(5,phase) for phase in range(4)]
            actual=e.evaluate_many(geometries);expected=[e.evaluate(g) for g in geometries]
            for a,b in zip(actual,expected):
                for key in a:equal(a[key],b[key])
    finally:plan.close()


@pytest.mark.parametrize('example,extra',[('flexible',{'circulation_modes':{1:3}}),
    ('wing-body',{'ground_effect':1}),('wing-body',{'ground_effect':-1}),
    ('wing-body',{'freeze_influences':True}),('powered',{'powers':{1:7}})])
def test_complete_operators_equal_individual_field_application(example,extra,monkeypatch):
    from openswing.aero import FlightCondition
    from openswing.linear_dynamics import make_system,linearize
    from test_direct_circulation import model_for
    s,_=make_system(model_for(example),FlightCondition(speed=20,alpha=3,mach=.1,
        position_earth=[0.,0.,30.],**extra),4,structured_base=True)
    a,m=linearize(s,sparse=True,_output_fields=True);g=s._output_field_tangent.matrix.copy()
    monkeypatch.setattr(GeometryFields,'evaluate_many',lambda self,geometries:[self.evaluate(q) for q in geometries])
    aa,mm=linearize(s,sparse=True,_output_fields=True);gg=s._output_field_tangent.matrix
    for name,actual,expected in [('A',a,aa),('M',m,mm),('G',g,gg)]:
        operators_close(actual,expected,6*s.network.nn,mass=name=='M')
