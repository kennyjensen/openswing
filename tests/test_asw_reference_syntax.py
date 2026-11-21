"""Published zero-origin shorthand must preserve the documented reference state."""
from pathlib import Path
import re
import numpy as np
import pytest
from openswing.asw import AswError, parse_asw
from openswing.asw_edit import model_data
from openswing.aero import FlightCondition, solve_rigid

BASE=Path('examples/rectangular.asw').read_text()


def source(rows):
    result,n=re.subn(r'(?im)^Reference\s*\n.*?^End\s*$', 'Reference\n'+rows+'\nEnd', BASE, flags=re.S)
    assert n==1
    return result


@pytest.mark.parametrize('rows',[
    '12 1 12 0 0 0',
    '12 1 12 -0.0 0D0 0+00',
    '* 2 .5 3\n6 2 4 0 0 0',
    '* 2 .5 3 4 5 6\n+ 2 0 0 0 0 0\n5 2 4 0 0 0',
])
def test_zero_origin_shorthand_is_lossless_and_has_the_documented_reference_state(rows):
    original=source(rows)
    legacy=parse_asw(original)
    modern=parse_asw(source('12 1 12\n0 0 0\n0 0 0\n0 0 0'))
    assert legacy.dumps()==original
    assert model_data(legacy)==model_data(modern)
    assert model_data(parse_asw(legacy.dumps(canonical=True)))==model_data(modern)
    legacy.reference[3]=[.5,.25,-.125]
    edited=parse_asw(legacy.dumps())
    np.testing.assert_array_equal(edited.reference,legacy.reference)


@pytest.mark.parametrize('rows',[
    '12 1 12 1 0 0','12 1 12 0 -1 0','12 1 12 0 0 1',
    '+ 0 0 0 .5\n12 1 12 0 0 0',
])
def test_nonzero_legacy_reference_does_not_guess_the_coordinate_mapping(rows):
    with pytest.raises(AswError,match='Line .*Nonzero coordinates'):
        parse_asw(source(rows))


@pytest.mark.parametrize('rows',[
    '12 1 12 0','12 1 12 0 0','12 1 12 0 0 0 0',
    '12 1 12 0 0 0\n0 0 0','12 1 12\n0 0 0 0 0 0',
    '12 1 12 0 0 nan','12 1 12 0 0 inf',
    '0 1 12 0 0 0','12 -1 12 0 0 0',
])
def test_ambiguous_malformed_and_invalid_reference_inputs_remain_rejected(rows):
    with pytest.raises(AswError):parse_asw(source(rows))


def test_origin_reference_gives_identical_rigid_loads_with_nonzero_rates():
    models=[parse_asw(source(rows)) for rows in ['12 1 12','12 1 12 0 0 0']]
    condition=FlightCondition(speed=30,alpha=4,beta=2,rates=(.1,-.2,.3),mach=0)
    results=[solve_rigid(model,condition,panels=12) for model in models]
    for key in ['CL','CD','CY','Cm','Cl','Cn']:
        assert results[0][key]==results[1][key]
    assert results[0]['strips']==results[1]['strips']
