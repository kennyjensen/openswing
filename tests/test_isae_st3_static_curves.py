"""Source/load conventions most likely to reverse a coupled ST-3 comparison."""
import pytest
from verify_st3_static_curves import load_masses, loaded_source, plotted


def test_force_and_moment_script_units_and_shared_zero():
    assert load_masses('F',3.924)==[.2,.2]
    assert load_masses('M',.5433114878849045)==[.54331,-.54331]
    assert repr(load_masses('F',0.))==repr(load_masses('M',0.))


def test_signed_load_update_preserves_multiplier_and_unrelated_text():
    source='Name\noriginal\nEnd\nWeight\n* 1 1 1 1 9.81\n#  MASS1\nold a\n#  MASS2\nold b\nend\nBeam\nuntouched\n'
    changed=loaded_source(source,[.5433114878849045,-.5433114878849045])
    assert '* 1 1 1 1 9.81' in changed
    assert '  1  0.558  -0.07  0.558  0.0  0.54331' in changed
    assert '  1  0.558  0.07  0.558  0.0  -0.54331' in changed
    assert changed.startswith('Name\noriginal\nEnd\n') and changed.endswith('end\nBeam\nuntouched\n')


def test_missing_weight_marker_is_rejected():
    with pytest.raises(AssertionError):loaded_source('Weight\n#  MASS1\na\nEnd\n',[0,0])


@pytest.mark.parametrize('kind,quantity,name,expected',[
    ('F','Z','p15_0',2),('M','Z','0_3_90',2),('M','Z','p15_0',-2),
    ('M','Z','m15_0',-2),('F','T','p15_0',3),('M','T','p15_0',-3)])
def test_original_plot_signs(kind,quantity,name,expected):
    assert plotted(dict(h_m=2,twist_asw_deg=3),kind,quantity,name)==expected
