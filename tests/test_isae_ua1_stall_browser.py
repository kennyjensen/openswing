"""Reject hidden physical discrepancies in the browser stall audit."""
from copy import deepcopy
import math
from pathlib import Path
import sys

import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
from isae_ua1_stall_browser import difference, physical_row


def sample():
    a = math.radians(9.)
    h = [-math.sin(a), 0., math.cos(a)]
    w = [math.cos(a), 0., math.sin(a)]
    qs = .5*1.225*100*200000
    return dict(time=.1, force=[qs*x for x in h], CDp=.2,
        operating_values=dict(speed=math.sqrt(125)),
        strips=[dict(circulation=2., cl=1.6) for _ in range(4)],
        circulation_rate=[3.]*4, residual=1e-12, order=2,
        frame=dict(attitude=[0.]*3, rates_body=[0.]*3,
            velocity_origin_body=[-10*x+5*y for x,y in zip(w,h)],
            position_earth=[.25*x for x in h], acceleration_reference_body=[-4*x for x in h]))


def test_fixed_speed_drag_and_fixed_axis_lift_and_motion():
    row = physical_row(sample(), dict(alpha_deg=9., speed=10.))
    assert row['CL'] == pytest.approx(1.)
    assert row['CDp_fixed'] == pytest.approx(.25)
    assert row['velocity'] == pytest.approx(5.)
    assert row['position'] == pytest.approx(.25)
    assert row['acceleration'] == pytest.approx(-4.)
    assert row['section_cl'] == [1.6]*4


@pytest.mark.parametrize('bad', [float('nan'), float('inf'), -float('inf')])
def test_nonfinite_values_rejected_even_against_themselves(bad):
    with pytest.raises(AssertionError): difference([1., bad], [1., bad])
    raw = sample(); raw['circulation_rate'][3] = bad
    with pytest.raises(AssertionError): physical_row(raw, dict(alpha_deg=9., speed=10.))


@pytest.mark.parametrize('a,b', [([1.,2.],[1.]), ([1.,2.],[[1.,2.]]), (1.,[1.])])
def test_missing_or_reshaped_fields_rejected(a,b):
    with pytest.raises(AssertionError): difference(a,b)


def test_individual_strip_error_is_not_averaged_and_signed_zero_is_equal():
    expected = [0.,2.,3.,4.]; actual = deepcopy(expected)
    actual[3] += .04
    assert difference(actual,expected) == pytest.approx(.01)
    assert difference([0.,-0.],[-0.,0.]) == 0.
    assert difference(1e-7,0.) > 2e-8


def test_incorrect_frame_or_strip_count_rejected():
    for change in ('frame','strips'):
        raw = sample()
        if change == 'frame': raw['frame']['rates_body'][0] = .01
        else: raw['strips'].pop()
        with pytest.raises(AssertionError): physical_row(raw, dict(alpha_deg=9., speed=10.))
