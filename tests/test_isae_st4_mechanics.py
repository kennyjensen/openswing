import pytest
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from isae_st4_mechanics import classify


@pytest.mark.parametrize('fractions,indices',[
    ([.01,.9,.1],dict(fb1=0,fb2=2,ft=1)),
    ([.01,.1,.9],dict(fb1=0,fb2=1,ft=2)),
    ([.8,.01,.1],dict(fb1=1,fb2=2,ft=0)),
])
def test_energy_labels_follow_shapes_not_frequency_targets(fractions,indices):
    result=classify(fractions)
    assert result['valid'] and result['indices']==indices


@pytest.mark.parametrize('fractions',[[.1,.5,.5],[.1,.2,.3],[.1,.8,.9]])
def test_ambiguous_or_missing_families_are_not_accepted(fractions):
    assert not classify(fractions)['valid']
