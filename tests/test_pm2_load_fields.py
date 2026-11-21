"""Sided jumps, component scales and nested circulation cells stay explicit."""
from copy import deepcopy
import importlib.util
import math
from pathlib import Path

import pytest

spec=importlib.util.spec_from_file_location('pm2_load_fields',Path(__file__).resolve().parents[1]/'scripts/isae_pm2_load_fields.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)


def result(stations, *, scales=(1.,100.)):
    nodes=[];elements=[];strips=[]
    for beam,scale in enumerate(scales,1):
        lookup={}
        for t in stations:
            lookup[t]=len(nodes)
            nodes.append(dict(index=len(nodes),beam=beam,t=t,jig_position=[beam,t,0.]))
        for lo,hi in zip(stations,stations[1:]):
            traces=[]
            for side,t in [('right',lo),('left',hi)]:
                # A real jump at t=1: each side is a different value.
                jump=10. if t>1 or (t==1 and side=='right') else 1.
                traces.append(dict(side=side,t=t,node=lookup[t],
                    force=[scale*jump*(1+t),2*scale*jump,3*scale*jump],
                    moment=[.01*scale*jump,.02*scale*jump*(1+t),.03*scale*jump]))
            elements.append(dict(beam=beam,t0=lo,t1=hi,length=hi-lo,endpoint_traces=traces))
            strips.append(dict(beam=beam,lifting=True,t=(lo+hi)/2,circulation=2*scale))
    return dict(converged=True,continuation_status='complete',nodes=nodes,elements=elements,strips=strips)


def pair():return result([0.,1.,2.]),result([0.,.5,1.,1.5,2.])


def trace(r,beam,t,side):
    return next(v for e in r['elements'] if e['beam']==beam for v in e['endpoint_traces'] if v['t']==t and v['side']==side)


def test_identical_sided_fields_pass_without_claiming_other_fields():
    report=m.compare(*pair())
    assert report['passed']==report['required']==12
    assert not report['all_field_accuracy_established'] and report['native_values_added']==0
    for row in report['circulation_cell_diagnostics']:
        assert row['rms_relative_percent']==row['maximum_relative_percent']==0.
        assert row['numerical_gate_assessed'] is False


def test_opposite_errors_on_two_sides_of_jump_cannot_cancel():
    c,f=pair()
    trace(c,1,1.,'left')['force'][0]+=.1
    trace(c,1,1.,'right')['force'][0]-=.1
    row=m.compare(c,f)['checks'][0]
    assert row['maximum_absolute_change']==pytest.approx(.1)
    assert row['maximum_percent']==pytest.approx(100*.1/30.)
    assert not row['passed'] and row['worst_station']==1.


def test_other_beams_and_components_cannot_hide_small_component_error():
    c,f=pair()
    # A tiny z component on beam 1 retains its own scale despite large x/y
    # components and the 100-times larger second beam.
    for r in (c,f):
        for e in r['elements']:
            if e['beam']==1:
                for v in e['endpoint_traces']:v['force'][2]=.001
    trace(c,1,2.,'left')['force'][2]+=.000002
    row=m.compare(c,f)['checks'][2]
    assert row['fine_scale']==.001 and row['maximum_percent']==pytest.approx(.2)
    assert not row['passed']


def test_force_scale_does_not_normalize_moments():
    c,f=pair();trace(c,1,2.,'left')['moment'][0]+=.0002
    row=m.compare(c,f)['checks'][3]
    assert row['fine_scale']==.1 and row['maximum_percent']==pytest.approx(.2)
    assert not row['passed']


def test_zero_component_is_reported_without_fabricating_a_relative_pass():
    c,f=pair()
    for r in (c,f):
        for e in r['elements']:
            for v in e['endpoint_traces']:v['moment'][2]=0.
    rows=[r for r in m.compare(c,f)['checks'] if r['field']=='moment' and r['body_component']=='z']
    assert len(rows)==2 and all(r['maximum_percent'] is None and not r['passed'] for r in rows)


def test_circulation_uses_exact_cell_measure_without_collocation_interpolation():
    c=result([0.,2.],scales=(1.,));f=result([0.,1.,2.],scales=(1.,))
    for strip,gamma in zip(f['strips'],(1.,3.)):strip['circulation']=gamma
    # Different in-cell collocation positions cannot change the cell metric.
    c['strips'][0]['t']=.13;f['strips'][0]['t']=.09;f['strips'][1]['t']=1.91
    row=m.compare(c,f)['circulation_cell_diagnostics'][0]
    assert row['rms_absolute_change']==1. and row['fine_rms']==pytest.approx(math.sqrt(5.))
    assert row['rms_relative_percent']==pytest.approx(100/math.sqrt(5.))
    assert row['maximum_relative_percent']==pytest.approx(100/3)
    assert not row['numerical_gate_assessed']


@pytest.mark.parametrize('kind',['nonfinite_load','nonfinite_circulation','side','node','missing_trace',
    'overlap','material_measure','incomplete','jig','strip_beam','strip_location'])
def test_corrupt_or_incomparable_data_is_rejected(kind):
    c,f=pair()
    if kind=='nonfinite_load':trace(f,1,.5,'left')['force'][0]=float('nan')
    elif kind=='nonfinite_circulation':f['strips'][1]['circulation']=float('inf')
    elif kind=='side':f['elements'][0]['endpoint_traces'][0]['side']='left'
    elif kind=='node':f['elements'][0]['endpoint_traces'][0]['node']=100
    elif kind=='missing_trace':f['elements'][0]['endpoint_traces'].pop()
    elif kind=='overlap':f['elements'][1]['t0']=.49
    elif kind=='material_measure':f['elements'][0]['length']*=1.01
    elif kind=='incomplete':f['converged']=False
    elif kind=='jig':f['nodes'][0]['jig_position'][0]+=.1
    elif kind=='strip_beam':f['strips'][0]['beam']=2
    else:f['strips'][0]['t']=.9
    with pytest.raises(ValueError):m.compare(c,f)


def test_nonnested_cell_partition_cannot_be_silently_interpolated():
    # Keep the coarse station but force a fine element to straddle it.
    c,f=pair();f['elements'][1]['t1']=1.25;f['elements'][2]['t0']=1.25
    with pytest.raises(ValueError):m.compare(c,f)
