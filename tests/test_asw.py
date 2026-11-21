from pathlib import Path
import numpy as np
import pytest
from openswing.asw import AswError, Distribution, parse_asw

EXAMPLE = Path("examples/rectangular.asw").read_text()


def test_lossless_roundtrip():
    text = EXAMPLE.replace("\n", "\r\n") + "! extra comment\r\n"
    assert parse_asw(text).dumps() == text


def test_mirror_is_per_distribution_and_y_reflects():
    model = parse_asw(EXAMPLE)
    b = model.beams[0]
    assert b.domain == (-6, 6)
    assert b.value("chord", -4) == b.value("chord", 4) == 1
    assert b.value("y", -4) == -4
    assert b.value("y", -4, derivative=1) == 1
    assert b.value("dCLdF1", -4) == -.05
    assert b.value("dCLdF1", 4) == .05
    assert b.value("dCLdF1", 0) == 0
    assert model.controls == [1]


def test_doubled_stations_retain_jump_and_side_after_mirroring():
    d = Distribution("alpha", np.array([0, 1, 1, 2]), np.array([0, 0, 4, 4]), 1)
    assert d.evaluate(1, side="left") == 0
    assert d.evaluate(1, side="right") == 4
    assert d.evaluate(-1, mirror=True, side="left") == 4
    assert d.evaluate(-1, mirror=True, side="right") == 0


def test_swept_mirrored_center_has_correct_one_sided_tangents():
    d = Distribution("x", [0, 1], [0, .5], 1)
    assert d.evaluate(0, mirror=True, derivative=1, side="left") == -.5
    assert d.evaluate(0, mirror=True, derivative=1, side="right") == .5


def test_scaling_and_fortran_exponent():
    text = EXAMPLE.replace("0 0 0 0 1 .25\n6 0 6 0 1 .25", "* 1 1 2 1 3D0 1\n+ 0 0 1 0 .5 0\n0 0 0 0 1 .25\n6 0 6 0 1 .25")
    b = parse_asw(text).beams[0]
    assert b.value("chord", 3) == 3.5
    assert b.value("y", 6) == 13
    assert b.value("y", -6) == -11


def test_negative_station_multiplier_reverses_order():
    d = Distribution("y", [0, -1, -2], [0, -1, -2], 1)
    np.testing.assert_array_equal(d.t, [-2, -1, 0])
    assert d.evaluate(-1.5) == -1.5


def test_zero_stiffness_means_rigid():
    text = EXAMPLE.replace("t Cdf", "t GJ\n0 0\n6 0\nt Cdf")
    assert np.isinf(parse_asw(text).beams[0].value("GJ", 3))
    assert np.isinf(parse_asw(text).beams[0].value("EA", 3))


def test_units_are_magnitude_times_named_unit_and_mass_derived():
    a = parse_asw(EXAMPLE.replace("L 1 m", "L 1 ft").replace("F 1 N", "F 1 lb")).units.si_scales()
    b = parse_asw(EXAMPLE.replace("L 1 m", "L .3048 m").replace("F 1 N", "F 4.4482216152605 N")).units.si_scales()
    assert a == b
    assert a["M"] == pytest.approx(14.5939029372064)


def test_mass_unit_can_replace_force():
    s = parse_asw(EXAMPLE.replace("F 1 N", "M 1 kg")).units.si_scales()
    assert s == dict(L=1, T=1, F=1, M=1)


def test_integer_global_columns_are_not_scaled():
    text = EXAMPLE + "\nWeight\n* 2 3 4 5 6\n+ 1 1 1 1 1\n1 2 3 4 5 6\nEnd\n"
    row = parse_asw(text).records["weight"][0]
    np.testing.assert_allclose(row[:6], [1, 5, 10, 17, 26, 37])
    assert not row[6:].any()


@pytest.mark.parametrize("change", [lambda s: s.replace("Beam 1", "Beam x"),
                                      lambda s: s[:-4],
                                      lambda s: s.replace("6 .008", "2 .008 6.28 1.2 -1.2\n1 .008"),
                                      lambda s: s.replace("9.80665", "NaN"),
                                      lambda s: s.replace("1 0 0\nEnd\nBeam", "2 0 0\nEnd\nBeam")])
def test_invalid_files_raise_actionable_errors(change):
    with pytest.raises(AswError):
        parse_asw(change(EXAMPLE))


@pytest.mark.parametrize("name,beams", [("dae", 5), ("usa", 4), ("fw", 1)])
def test_bundled_official_sample(name, beams):
    file = Path(f"examples/{name}.asw")
    model = parse_asw(file.read_text())
    assert len(model.beams) == beams
    assert not model.diagnostics
    assert model.dumps() == file.read_text()


def test_flying_wing_zero_tip_weight_is_not_a_signed_load():
    model = parse_asw(Path("examples/fw.asw").read_text(), beam_interpolation="drela-segspl-v1")
    wing = model.beams[0]
    left, right = wing.domain
    assert wing.value("mg", left, side="right") == 0
    assert wing.value("mg", right, side="left") == 0
    assert wing.value("mg", right - 0.01) > 0
    assert wing.value("mg", right + 0.01) < 0
