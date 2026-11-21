"""Guide-defined input warnings must not become unsupported-input errors."""
from pathlib import Path

import numpy as np
import pytest

from openswing.aero import AnalysisError, FlightCondition, solve_rigid
from openswing.asw import parse_asw
from openswing.asw_edit import edit_distribution, signature
from openswing.bridge import dispatch


WING = Path('examples/rectangular.asw').read_text()


def with_table(table):
    return WING.replace('t Cdf', table + '\nt Cdf')


def test_guide_mass_jump_warns_without_blocking_or_modifying_model():
    source = with_table('t mg\n0 1\n3 1\n3 2\n6 2')
    model = parse_asw(source)
    original_signature = signature(model)
    note, = model.compatibility_notes
    assert note['code'] == 'aswing-default-kbreak'
    assert (note['beam'], note['property']) == (1, 'mg')
    assert note['stations'] == [3.]
    assert note['left'] == [1.] and note['right'] == [2.]
    assert note['mirrored'] is True
    assert source.splitlines()[note['line'] - 1] == 't mg'
    assert not model.diagnostics
    assert model.dumps() == source and signature(model) == original_signature
    result = solve_rigid(model, FlightCondition(alpha=3, mach=0), panels=12)
    assert result['converged'] and result['residual'] < 1e-8
    assert result['CL'] > 0


def test_slope_break_without_value_jump_is_not_a_warning():
    model = parse_asw(with_table('t mg\n0 1\n3 1\n3 1\n6 2'))
    assert model.beams[0].value('mg', 3, derivative=1, side='left') == 0
    assert model.beams[0].value('mg', 3, derivative=1, side='right') > 0
    assert not model.compatibility_notes


def test_documented_break_properties_and_lift_moment_controls_are_exempt():
    # Literal list from the guide, independent of the implementation constant.
    model = parse_asw(WING)
    for name in 'x y z twist Dmgcc Dmgnn Dmg DCcg DNcg chord alpha dCLdF1 dCMdF1 dCLdF12 dCMdF12'.split():
        model = edit_distribution(model, 1, name, points=[[0, 1], [3, 1], [3, 2], [6, 2]])
    assert not model.compatibility_notes


@pytest.mark.parametrize('name', ['GJ', 'Cshell', 'CLmax', 'dCDdF12'])
def test_other_supported_properties_retain_nonfatal_notes(name):
    model = edit_distribution(parse_asw(WING), 1, name,
                              points=[[0, 1], [3, 1], [3, 2], [6, 2]])
    assert [n['property'] for n in model.compatibility_notes] == [name]
    assert not model.diagnostics


def test_scaled_reversed_input_reports_increasing_physical_t_and_sided_values():
    model = parse_asw(with_table('t mg\n* -2 3\n+ 0 10\n0 1\n1 1\n1 2\n3 2'))
    note, = model.compatibility_notes
    assert note['stations'] == [-2.]
    assert note['left'] == [16.] and note['right'] == [13.]
    assert note['mirrored'] is False
    assert not parse_asw(with_table('t mg\n* 1 0\n0 1\n3 1\n3 2\n6 2')).compatibility_notes


def test_coincident_enabled_break_does_not_hide_native_property_warning():
    model = parse_asw(with_table('t mg alpha\n0 1 0\n3 1 0\n3 2 1\n6 2 1'))
    assert [n['property'] for n in model.compatibility_notes] == ['mg']
    # Existing sided-value/mesh behavior is preserved, including the mirror.
    np.testing.assert_array_equal(model.beams[0].breaks, [-3., -2., 0., 2., 3.])
    assert model.beams[0].value('mg', -3, side='left') == 2
    assert model.beams[0].value('mg', -3, side='right') == 1


def test_editing_and_canonical_roundtrip_refresh_notes():
    model = parse_asw(with_table('t mg\n0 1\n3 1\n3 2\n6 2'))
    out = parse_asw(model.dumps(canonical=True))
    assert out.compatibility_notes[0]['stations'] == [3.]
    fixed = edit_distribution(model, 1, 'mg', points=[[0, 1], [3, 1], [3, 1], [6, 2]])
    assert not fixed.compatibility_notes
    assert model.compatibility_notes


def test_inspection_exposes_notes_separately_from_fatal_unknown_input():
    source = with_table('t mg\n0 1\n3 1\n3 2\n6 2')
    result = dispatch(dict(action='inspect', source=source, panels=8))
    assert result['compatibility_notes'][0]['property'] == 'mg'
    assert not result['diagnostics']
    unknown = parse_asw(with_table('t alien\n0 1\n3 1\n3 2\n6 2'))
    assert unknown.diagnostics and not unknown.compatibility_notes
    with pytest.raises(AnalysisError, match='unrecognized input'):
        solve_rigid(unknown, FlightCondition(alpha=3, mach=0), panels=8)
