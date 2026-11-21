"""Original output inventory must follow driver paths and preserve every row."""
from decimal import Decimal
import importlib.util
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
spec = importlib.util.spec_from_file_location('ffwt4_sources', ROOT/'scripts/assess-isae-ffwt4-sources.py')
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


def driver(beta=''):
    return ('#!/bin/sh\n/native/bin/aswing FFWT_Flare20_PM2 <<EOF\nnodes\nB 1\nI 100\n'
            '\nGMOD\n5\n-10.9366 0 10.9366 .6978\noper\n!A 6\n!V 22\n'+beta+
            '\n%\na\n13 13\nd\nx\nr\n%\n.\nd\nx\n0.0149 200\np\ns\n25 1\nw\n'
            'FFWT_Flare20/FFWT_Flare20-1.txt\nO\n\nGMOD\n5\n-5.6786 0 5.6786 .8751\n'
            'oper\n1\n%\n.\nd\nx\n0.0077 200\np\nw\nFFWT_Flare20/FFWT_Flare20-2.txt\nO\nEOF\n')


def native():
    return '# FFWT Flare 20\n# Operating point sequence...\n# i t Mc` mom[ 1]\n'+'\n'.join(
        f'{i+1} {i*Decimal(".0149"):.6f} 0.530039' for i in range(200))+'\n'


def test_driver_selects_pm2_and_retains_explicit_sideslip_and_reset():
    data = audit.driver_contract(driver('!B 16'))
    assert data['requested_model'] == 'FFWT_Flare20_PM2'
    assert data['conditions']['B']['value'] == '16'
    assert data['histories'][0]['gust_parameters'] == ['-10.9366', '0', '10.9366', '0.6978']
    assert [h['dt'] for h in data['histories']] == ['0.0149', '0.0077']
    assert [h['output'] for h in data['histories']] == [f'FFWT_Flare20/FFWT_Flare20-{i}.txt' for i in (1,2)]


def test_unspecified_sideslip_is_not_invented_as_zero():
    assert 'B' not in audit.driver_contract(driver())['conditions']


@pytest.mark.parametrize('before,after', [
    ('\n1\n%','\n2\n%'), ('0.0149 200','0.0149 201'),
    ('FFWT_Flare20/FFWT_Flare20-2.txt','FFWT_Flare20/FFWT_Flare20-1.txt'),
    ('!V 22','!V 22\n!V 23'), ('GMOD\n5','GMOD\n4'),
])
def test_ambiguous_or_changed_driver_contract_is_rejected(before,after):
    with pytest.raises(ValueError):
        audit.driver_contract(driver().replace(before,after,1))


def test_native_rows_preserve_startup_and_exact_physical_times():
    data = audit.native_rows(native(), '0.0149')
    assert len(data['rows']) == 200
    assert data['rows'][0]['exact_time'] == '0.0000'
    assert data['rows'][-1]['exact_time'] == '2.9651'
    assert data['rows'][0]['printed_half_interval'] == '5E-7'
    assert data['rows'][0]['moment_token'] == '0.530039'


@pytest.mark.parametrize('fault', ['missing_tail','duplicate_index','time_shift','nan','wrong_channel'])
def test_incomplete_or_mispaired_native_output_cannot_enter_full_scope(fault):
    text = native()
    if fault == 'missing_tail':
        text = '\n'.join(text.splitlines()[:-1])
    elif fault == 'duplicate_index':
        text = text.replace('2 0.014900', '1 0.014900')
    elif fault == 'time_shift':
        text = text.replace('0.014900', '0.015900')
    elif fault == 'nan':
        text = text.replace('0.530039', 'NaN', 1)
    else:
        text = text.replace('mom[ 1]', 'mom[ 2]')
    with pytest.raises(ValueError):
        audit.native_rows(text, '0.0149')


def test_case_only_filename_difference_is_disclosed_and_unique():
    paths = [Path('FFWT_removed.asw'), Path('FFWT_Fixed.asw')]
    assert audit.resolve_model('FFWT_Removed', paths) == (paths[0], True)
    assert audit.resolve_model('FFWT_Fixed', paths) == (paths[1], False)
    with pytest.raises(ValueError, match='ambiguous'):
        audit.resolve_model('FFWT_REMOVED', paths+[Path('FFWT_Removed.asw')])


def test_missing_pm2_does_not_fall_back_to_a_model_with_a_similar_name():
    with pytest.raises(ValueError, match='no substitute'):
        audit.resolve_model('FFWT_Flare20_PM2', [Path('FFWT_Flare20.asw'), Path('FFWT_Flare20_PM.asw')])
