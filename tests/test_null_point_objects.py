"""Null Weight elimination is equation invariance, not historical solver parity."""
from pathlib import Path
import hashlib

import numpy as np
import pytest

from openswing.aero import FlightCondition, evaluate_aerodynamics
from openswing.asw import parse_asw
from openswing.circulation_tangent import circulation_columns
from openswing.discretization import requirements
from openswing.dynamic_inertia import moving_mass_loads
from openswing.geometry import attachment_geometry, model_meshes
from openswing.geometry_partials import GeometryPartials
from openswing.geometry_tangent import GeometryFields
from openswing.inertia import Motion, InertiaModel
from openswing.local_motion import NetworkMotion
from openswing.network import StaticNetwork
from openswing.point_objects import active_weights, null_weight
from openswing.source_coupled import SourceCoupledNetwork
from openswing.source_dynamics import SourceDynamicNetwork
from openswing.structured_static import linearization
from openswing.volume import VolumeField
from test_source_coupled import source, trial


NULLS = 'Weight\n1 99 1 -4 -20 0\n1 1.37 -.8 7 -30 -0\nEnd\n'
ACTIVE = 'Weight\n1 2 .4 1 .3 2 .002 .003 .01 -.02 .03 .2 .3 .4 .01 -.02 .03\nEnd\n'
REV = 'f62943df20e9e4d7d9f50e070477b22426b5f865'
CACHE = Path('.reference/isae-validation') / REV


def parsed(extra=''):
    return parse_asw(source()+extra, beam_interpolation='drela-segspl-v1')


def flight(**kwargs):
    return FlightCondition(speed=8, alpha=4, beta=2, density=1.2, mach=0,
                           controls={1:.15}, position_earth=[0,0,30], **kwargs)


def network(extra='', kind=SourceCoupledNetwork, condition=None):
    return kind(parsed(extra), 4, flight() if condition is None else condition, [1,-2,-10], [])


def test_null_filter_preserves_source_rows_and_does_not_insert_in_range_or_invalid_anchors():
    m = parsed(NULLS+ACTIVE)
    text, original = m.dumps(), [r.copy() for r in m.records['weight']]
    rows = active_weights(m)
    assert len(rows) == 1 and rows[0] is m.records['weight'][2]
    assert [r['kind'] for r in requirements(m)[1] if r['kind'].startswith('weight')] == ['weight 3']
    assert len([x for x in attachment_geometry(m) if x['kind']=='weight']) == 1
    other = parsed(ACTIVE)
    for a,b in zip(model_meshes(m,4),model_meshes(other,4)):
        for name in ('t0','t1','tm','length','r0','r1','frames'):
            np.testing.assert_array_equal(getattr(a,name),getattr(b,name))
    assert m.dumps() == text and m.source == text
    for a,b in zip(original,m.records['weight']):
        np.testing.assert_array_equal(a,b)


@pytest.mark.parametrize('field', range(5,17), ids=['Weight','CDA','Vol','Hx','Hy','Hz','Ixx','Iyy','Izz','Ixy','Ixz','Iyz'])
@pytest.mark.parametrize('value',[1e-200,-1e-200])
def test_every_nonzero_physical_field_keeps_invalid_anchor_rejection(field,value):
    m = parsed(NULLS)
    row = m.records['weight'][0]
    assert null_weight(row)
    row[field] = value
    assert not null_weight(row) and active_weights(m)[0] is row
    with pytest.raises(ValueError,match='outside.*parameter range'):
        model_meshes(m,4)
    message = 'must be nonnegative' if field in (6,7) and value < 0 else 'outside.*parameter range'
    with pytest.raises(ValueError,match=message):
        SourceCoupledNetwork(m,4,flight(),None,[])


def test_scaled_and_omitted_fields_determine_nullity_without_a_cached_zero_label():
    null = parsed('Weight\n* 1 1 1 1 0\n1 99 4 5 6 9\nEnd\n')
    assert null_weight(null.records['weight'][0])
    active = parsed('Weight\n+ 0 0 0 0 1\n1 99 4 5 6 0\nEnd\n')
    assert not null_weight(active.records['weight'][0])
    with pytest.raises(ValueError,match='outside.*parameter range'):
        model_meshes(active,4)
    # Nullity is not a permanent parser flag: property editing activates it.
    null.records['weight'][0][7] = .01
    with pytest.raises(ValueError,match='outside.*parameter range'):
        model_meshes(null,4)
    # Nonfinite/malformed arrays never certify a null object.
    bad = np.zeros(17);bad[1]=np.nan
    assert not null_weight(bad) and not null_weight(np.zeros(6))


@pytest.mark.parametrize('kind',[StaticNetwork,SourceCoupledNetwork])
@pytest.mark.parametrize('frozen',[False,True])
def test_complete_residual_and_aero_inertia_indexing_ignore_nulls(kind,frozen):
    c=flight(freeze_influences=frozen,ground_effect=1)
    a,b=[network(extra,kind,c) for extra in (ACTIVE,NULLS+ACTIVE+NULLS)]
    x=trial(a)
    assert a.size==b.size and len(b.weights)==1
    np.testing.assert_array_equal(a.residual(x,.6),b.residual(x,.6))
    for n in (a,b):
        r,q,*_=n.unpack(x)
        pos=n.point_positions(r,q)
        assert len(pos)==1
        np.testing.assert_array_equal(n.inertia_model.rows[0],n.weights[0])
        objects=attachment_geometry(n.model,[dict(beam=beam,t=t,position=r[i],rotation=q[i])
            for beam,(stations,ids) in n.station_nodes.items() for t,i in zip(stations,ids)])
        assert len([o for o in objects if o['kind']=='weight'])==1
    assert b.inertia_model.source_point_indices==[2]


def test_geometry_and_circulation_derivatives_keep_active_point_order():
    outputs=[]
    for extra in (ACTIVE,NULLS+ACTIVE):
        n=network(extra)
        x=trial(n)
        with linearization(n,x,.6,capture_circulation=True) as (fields,_):
            columns=circulation_columns(n,fields,.6)
            evaluator=GeometryFields(n,fields)
            partials=GeometryPartials(evaluator,x,chart='absolute').columns([0,2,4,6*n.nn-1])
            queries=evaluator.prepare(x)['queries']
            assert [key for key in queries if isinstance(key,tuple) and key[0]=='point']==[('point',0)]
        outputs.append((columns,partials))
    np.testing.assert_array_equal(outputs[0][0],outputs[1][0])
    def compare(a,b):
        if isinstance(a,dict):
            assert a.keys()==b.keys()
            for key in a:compare(a[key],b[key])
        elif isinstance(a,tuple):
            for x,y in zip(a,b):compare(x,y)
        elif a is None:assert b is None
        else:np.testing.assert_array_equal(a,b)
    compare(outputs[0][1],outputs[1][1])


def test_unsteady_inertia_and_flap_controls_cannot_activate_zero_constants():
    values=[]
    for extra in (ACTIVE,NULLS+ACTIVE):
        n=network(extra,StaticNetwork)
        x=trial(n);r,q,*_=n.unpack(x)
        rng=np.random.default_rng(517)
        local=NetworkMotion(n,r,q,*rng.normal(0,.1,(4,n.nn,3)))
        position=n.point_positions(r,q)
        rotation=[q[n.node(*row[:2])] for row in n.weights]
        force,moment,_,_=moving_mass_loads(n,local,n.deformed_meshes(r,q,n.geometry(r,q)),
            Motion([.2,-.3,.1],[.4,.2,-.1],[.1,-.2,.3]),[0,0,-10],position,rotation)
        values.append((force,moment))
    for a,b in zip(*values):np.testing.assert_array_equal(a,b)
    # The control changes distributed aerodynamic loads; Weight constants stay zero.
    controlled=[]
    for extra in ('',NULLS):
        m=parsed(extra);meshes=model_meshes(m,4)
        result=[]
        for setting in (-.1,.25):
            c=flight();c.controls={1:setting}
            result.append(evaluate_aerodynamics(m,c,meshes,np.full(sum(len(z.tm) for z in meshes),.03))['force'])
        controlled.append(np.asarray(result))
        assert all(null_weight(row) for row in m.records.get('weight',[]))
    np.testing.assert_array_equal(*controlled)
    assert np.linalg.norm(controlled[0][1]-controlled[0][0])>0


def test_supplied_raw_point_arrays_cannot_silently_shift_active_point_indices():
    m=parsed(NULLS+ACTIVE);meshes=model_meshes(m,4)
    positions=[r[2:5] for r in m.records['weight']]
    for call in [lambda:evaluate_aerodynamics(m,flight(),meshes,np.zeros(sum(len(x.tm) for x in meshes)),positions),
                 lambda:VolumeField(m,meshes,np.array([1.,0,0]),np.eye(3),positions),
                 lambda:InertiaModel(m,meshes).point_elements(positions)]:
        with pytest.raises(ValueError,match='per active Weight'):
            call()


def test_separate_external_load_sensor_and_engine_anchors_are_not_eliminated():
    m=parsed(NULLS)
    with pytest.raises(ValueError,match='outside.*parameter range'):
        model_meshes(m,4,[dict(beam=1,t=99,force=[0,0,1])])
    for extra in ('Sensor\n2 1 99 0 0 0\nEnd\n',
                  'Engine\n1 0 1 99 0 0 0 1 0 0 1\nEnd\n'):
        with pytest.raises(ValueError,match='outside.*parameter range|outside.*beam'):
            model_meshes(parsed(NULLS+extra),4)


def test_engine_power_control_preserves_null_weight_invariance():
    engine='Engine\n1 0 1 1 -.4 0 0 1 0 0 .2\nEnd\n'
    force=[]
    for extra in (engine,NULLS+engine):
        m=parsed(extra);meshes=model_meshes(m,4)
        pair=[]
        for power in (0.,20.):
            c=flight(powers={1:power})
            pair.append(evaluate_aerodynamics(m,c,meshes,np.full(sum(len(z.tm) for z in meshes),.03))['force'])
        force.append(np.asarray(pair))
        assert active_weights(m)==[]
    np.testing.assert_array_equal(*force)
    assert np.linalg.norm(force[0][1]-force[0][0])>0


def test_signed_weight_diagnostic_retains_original_record_number():
    m=parsed(NULLS+'Weight\n1 2 .4 1 .3 -2\nEnd\n')
    mass=InertiaModel(m,model_meshes(m,4),allow_signed_point_weights=True)
    assert mass.signed_point_weights==[3] and mass.source_point_indices==[2]


def original(relative, expected):
    path=CACHE/relative
    if not path.exists():pytest.skip('Pinned optional ISAE cache is unavailable.')
    assert hashlib.sha256(path.read_bytes()).hexdigest()==expected
    return parse_asw(path.read_text(),beam_interpolation='drela-segspl-v1')


def test_literal_ae1_original_constructs_and_evaluates_without_moving_its_null_anchors():
    m=original('4 - Aeroelasticity/AE - Aeroelastic Cases/AE-1-S Pazy Wing - Steady Deflection/Pazy_wing.asw',
        '5086107d412ebf8f43ef75173fe553914fb074dd7dca3b93f7bd56ab365c17c8')
    text=m.dumps()
    assert [r[1] for r in m.records['weight']]==[.558,.558]
    assert all(null_weight(r) for r in m.records['weight'])
    meshes=model_meshes(m,{'default':80,'beams':{'1':{'count':80,'spacing':'uniform'}}})
    assert meshes[0].t1[-1]==.55 and .52 in meshes[0].t1
    n=SourceCoupledNetwork(m,4,FlightCondition(speed=10,alpha=5,density=1.23,mach=0),None,[])
    assert n.weights==[]
    assert np.all(np.isfinite(n.residual(np.zeros(n.size),1.)))
    assert m.dumps()==text and [r[1] for r in m.records['weight']]==[.558,.558]


@pytest.mark.parametrize('directory,sha',[('01_Modal_Undeformed','ad2dccabfc2d527781a97c883f4c6dcda6fd8bb643a06a6768efda3ddc258395'),
    ('02_Modal_Gravity','031df5465100c9776e52b58bc745280f56d2426f55109b04037e087208ac12de')])
def test_literal_st2_modal_zero_objects_allow_source_dynamic_setup(directory,sha):
    m=original(f'3 - Structure/CASE - ST2 Pazy_Wing/{directory}/Pazy_wing.asw',sha)
    text=m.dumps()
    n=SourceDynamicNetwork(m,4,None,[0,0,0],[])
    assert n.weights==[] and m.dumps()==text


@pytest.mark.parametrize('file,sha',[('Pazy_wing_bending_bench.asw','63050f789d1c17bb7d61c2a9c10b30d0bfc2c7ef58b75c443fba817d6b1cf1c1'),
    ('Pazy_wing_torsion_bench.asw','c180191f4d3ce2169d3829d85073b0277d6ce6699257a071c7abe58904335aab'),
    ('03_Static_Structural/Pazy_wing_bending_bench.asw','63050f789d1c17bb7d61c2a9c10b30d0bfc2c7ef58b75c443fba817d6b1cf1c1'),
    ('03_Static_Structural/Pazy_wing_torsion_bench.asw','46cb60472c7803f33a4329d3e20d9d2eee66771de2f362e120a76f22c46a158d')])
def test_literal_st2_static_active_anchors_still_reject(file,sha):
    m=original(f'3 - Structure/CASE - ST2 Pazy_Wing/{file}',sha)
    assert all(not null_weight(r) for r in m.records['weight'])
    with pytest.raises(ValueError,match='outside.*parameter range'):
        model_meshes(m,4)
