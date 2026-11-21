"""Numeric input checked against a Fortran list-directed READ, not a repair."""
from pathlib import Path
import re
import numpy as np
import pytest
from openswing.asw import AswError, numbers, parse_asw
from openswing.aero import FlightCondition, solve_rigid


def test_implicit_exponents_match_fortran_read_values():
    values = numbers('6.2832+00, 2.1-6 -1.25-3 +.5+2 1-3 1.0D2', 17)
    np.testing.assert_array_equal(values, [6.2832, 2.1e-6, -.00125, 50., .001, 100.])


@pytest.mark.parametrize('token', ['1+-3', '1.2.3-4', '1e2-3', '1-', '--1',
                                  '1+2+3', '1e', 'nan', 'inf', '1.0+999'])
def test_malformed_or_nonfinite_numbers_still_report_the_source_line(token):
    with pytest.raises(AswError, match='Line 23:'):
        numbers(token, 23)


def test_literal_and_canonical_save_preserve_the_same_physical_model():
    original = Path('examples/rectangular.asw').read_text()
    # Constants and dimensional reference values pass through the same input
    # grammar as local material properties, multipliers and adders.
    implicit = re.sub(r'(?<!\S)(9\.80665|6\.28[0-9]*)(?!\S)', r'\1+00', original)
    assert implicit != original
    a, b = parse_asw(original), parse_asw(implicit)
    assert b.dumps() == implicit
    c = parse_asw(b.dumps(canonical=True))
    for name in a.beams[0].distributions:
        for model in [b, c]:
            np.testing.assert_array_equal(a.beams[0].distributions[name].values,
                                          model.beams[0].distributions[name].values)
    condition = FlightCondition(speed=30., alpha=4., mach=0.)
    results = [solve_rigid(model, condition, panels=12) for model in [a, b, c]]
    for result in results[1:]:
        np.testing.assert_array_equal([result[k] for k in ['CL', 'CD', 'Cm']],
                                      [results[0][k] for k in ['CL', 'CD', 'Cm']])
