"""Archived ST-3 table coverage and malformed-row rejection; no solvers."""
from pathlib import Path
import runpy

import numpy as np
import pytest


ROOT = Path(__file__).resolve().parents[1]
parse = runpy.run_path(str(ROOT/'scripts/summarize-isae-st3-static.py'))['parse_archived_span_table']

# Selected literal rows (root, interior, both repeated stations, tip) from
# ISAE revision f62943df20e9e4d7d9f50e070477b22426b5f865, ST-3
# Static_Deflection_analysis/temp.txt. The complete 45-row file is audited
# separately; no source download or physical calculation is needed here.
HEADER = """   Surface  Beam  1:  Beam
                                        -2            0            0
      t        y           z-z0        tw-tw0      Mc'/10       Ms'/10        Fn/10          cl        a_flap
  --------- ------------ ------------ ------------ ------------ ------------ ------------ ------------ ------------
"""
ROWS = """  0.100E-03    0.000E+00    0.000E+00    0.000E+00   -0.207E+01    0.694E+00    0.000E+00    0.000E+00    0.000E+00
  0.133E-02    0.123E-02    0.196E-06    0.486E-01   -0.207E+01    0.694E+00    0.000E+00    0.000E+00    0.000E+00
  0.335E+00    0.334E+00    0.145E-01    0.132E+02   -0.132E+01    0.691E+00    0.000E+00    0.000E+00    0.000E+00
  0.335E+00    0.334E+00    0.145E-01    0.132E+02   -0.132E+01    0.691E+00    0.000E+00    0.000E+00    0.000E+00
  0.558E+00    0.556E+00    0.400E-01    0.220E+02    0.559E-06    0.686E+00    0.000E+00    0.000E+00    0.000E+00
"""


@pytest.mark.parametrize('preamble', ['', '\n'*50, '1 2 3 4 5 6 7 8 9\nVelocity: 0\n'])
def test_root_and_duplicate_stations_do_not_depend_on_header_offset(preamble):
    table = parse(preamble+HEADER+ROWS)
    assert table.shape == (5, 9)
    np.testing.assert_array_equal(table[:, 0], [.0001, .00133, .335, .335, .558])
    np.testing.assert_array_equal(table[0], [.0001, 0, 0, 0, -2.07, .694, 0, 0, 0])
    np.testing.assert_array_equal(table[2], table[3])
    # Values stay in the printed scale; decoding preserves the moment sign.
    assert table[0, 4]*1e-2 == pytest.approx(-.0207)
    assert table[0, 5] == .694
    assert table[-1, 4]*1e-2 == pytest.approx(5.59e-9)


@pytest.mark.parametrize('replacement', [
    '0 0 0 0 0 0 0 0',
    '0 0 0 0 0 0 0 0 0 0',
    '0 0 0 broken 0 0 0 0 0',
    '0 0 0 NaN 0 0 0 0 0',
    '0 0 0 Inf 0 0 0 0 0',
])
def test_bad_numeric_row_is_rejected_instead_of_skipped(replacement):
    lines = ROWS.splitlines()
    lines[1] = replacement
    with pytest.raises(ValueError, match='Line .*ST-3 span-table'):
        parse(HEADER+'\n'.join(lines))


@pytest.mark.parametrize('text, message', [
    (ROWS, 'exactly one'),
    (HEADER+ROWS+HEADER+ROWS, 'exactly one'),
    (HEADER.replace('-2            0            0', '-1            0            0')+ROWS, 'scale exponents'),
    (HEADER.rsplit('\n', 2)[0]+'\n'+ROWS, 'separator'),
    (HEADER, 'no numeric rows'),
    (HEADER+'\n'.join(reversed(ROWS.splitlines())), 'nondecreasing'),
])
def test_wrong_table_layout_or_station_order_is_rejected(text, message):
    with pytest.raises(ValueError, match=message):
        parse(text)
