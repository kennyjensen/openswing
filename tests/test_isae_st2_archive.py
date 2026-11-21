"""Original-row coverage and strict portable parsing; no production imports."""
import hashlib
from pathlib import Path
import subprocess
import sys

import pytest

from scripts.isae_st2_archive import COLUMNS, decode_archive_profile, read_archive_profile


ROOT = Path(__file__).resolve().parents[1]
ORIGINAL = ROOT / '.reference/isae-validation/f62943df20e9e4d7d9f50e070477b22426b5f865/3 - Structure/CASE - ST2 Pazy_Wing/03_Static_Structural/temp.txt'
HEADER = ' '.join(COLUMNS)
SEPARATOR = ' '.join(['---------'] * 9)
FIRST = '0.100E-03 0.689E-16 0.000E+00 0.000E+00 -0.140E+01 0.124E+01 -0.315E+01 0.000E+00 0.000E+00'
SECOND = '0.118E-02 0.108E-02 -0.186E-05 0.118E-01 -0.140E+01 0.124E+01 -0.314E+01 0.000E+00 0.000E+00'


def fixture(*rows, leading='original description\n'):
    return leading + '1 0 1\n' + HEADER + '\n' + SEPARATOR + '\n' + '\n'.join(rows) + '\n'


def test_all_original_rows_and_tokens_including_previously_dropped_root():
    if not ORIGINAL.exists():
        pytest.skip('Optional pinned original ISAE archive unavailable.')
    assert hashlib.sha256(ORIGINAL.read_bytes()).hexdigest() == '0f747fa5472ef4acdefde8d4bd9b4874eca3ccbd826b2415ec485e86e2695ec3'
    profile = read_archive_profile(ORIGINAL)
    assert len(profile['rows']) == 46
    assert profile['header_line'] == 31 and profile['separator_line'] == 32
    assert [r['line_number'] for r in profile['rows']] == list(range(33, 79))
    assert profile['rows'][0]['tokens'] == FIRST.split()
    assert profile['rows'][1]['tokens'] == SECOND.split()
    assert profile['values'][0][0] == .0001
    assert profile['values'][1][0] == .00118
    assert profile['values'][-1][:4] == [.55, .456, -.279, 5.11]
    for row, line in zip(profile['rows'], ORIGINAL.read_text().splitlines()[32:]):
        assert row['tokens'] == line.split()
        assert len(row['fields']) == 9
    assert len(profile['values']) * len(COLUMNS) == 414


@pytest.mark.parametrize('leading', ['', '\n', 'title\nsecond header\n\n', '\n'.join(['metadata'] * 45) + '\n'])
def test_header_location_not_fixed_line_offset(leading):
    result = decode_archive_profile(fixture(FIRST, SECOND, leading=leading))
    assert [row['tokens'] for row in result['rows']] == [FIRST.split(), SECOND.split()]
    assert [row[0] for row in result['values']] == [.0001, .00118]


def test_display_tokens_precision_and_resultant_powers_are_separate():
    result = decode_archive_profile(fixture(FIRST))
    assert result['values'][0][4:7] == [-1.4, 1.24, -3.15]
    assert result['physical_values'][0][4:7] == [-14., 1.24, -31.5]
    fields = result['rows'][0]['fields']
    assert fields['t']['token'] == '0.100E-03'
    assert fields['t']['tolerance'] == 5e-7
    assert fields["Mc'/10"]['tolerance'] == .005
    assert fields["Mc'/10"]['physical_tolerance'] == .05
    assert fields['Fn/10']['power10'] == 1


@pytest.mark.parametrize('bad', [
    ' '.join(FIRST.split()[:-1]), FIRST + ' 0', FIRST.replace('0.100E-03', 'NaN'),
    FIRST.replace('0.100E-03', 'inf'), FIRST.replace('0.100E-03', '0.1bad'),
    FIRST.replace('0.100E-03', '1e9999'), '# Unexpected trailing metadata',
])
def test_malformed_row_is_rejected_without_silent_partial_table(bad):
    with pytest.raises(ValueError):
        decode_archive_profile(fixture(FIRST, bad, SECOND))


@pytest.mark.parametrize('change', [
    lambda s: s.replace(HEADER, 't y z theta moment force'),
    lambda s: s.replace(SEPARATOR, '---- ----'),
    lambda s: s.replace('1 0 1\n', '1 0\n'),
    lambda s: s.replace('1 0 1\n', '1 0 not-an-exponent\n'),
    lambda s: s + HEADER + '\n',
])
def test_schema_conflicts_fail_explicitly(change):
    with pytest.raises(ValueError):
        decode_archive_profile(change(fixture(FIRST)))


def test_blank_lines_preserve_rows_and_source_line_numbers():
    result = decode_archive_profile(fixture(FIRST, '', SECOND, ''))
    assert len(result['rows']) == 2
    assert result['rows'][1]['line_number'] - result['rows'][0]['line_number'] == 2


def test_empty_table_rejected():
    with pytest.raises(ValueError, match='no numeric rows'):
        decode_archive_profile(fixture())


def test_import_and_decode_are_stdlib_only():
    code = '''import sys
from scripts.isae_st2_archive import decode_archive_profile
decode_archive_profile(sys.argv[1])
assert not any(n=='openswing' or n.startswith('openswing.') or n in ('numpy','scipy') for n in sys.modules)
'''
    subprocess.run([sys.executable, '-c', code, fixture(FIRST)], cwd=ROOT,
                   check=True, capture_output=True, text=True, timeout=10)
