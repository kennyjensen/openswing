"""Reference selection must not confuse ASWING and experimental columns."""
from pathlib import Path
import importlib.util
import sys
import zipfile

import pytest

ROOT=Path(__file__).resolve().parents[1]
SPEC=importlib.util.spec_from_file_location('sa6_native',ROOT/'scripts/isae_sa6_native_tables.py')
NATIVE=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(NATIVE)


@pytest.fixture(scope='module')
def original():
    cache=ROOT/'.reference/isae-validation'/NATIVE.REVISION
    if not cache.exists():
        pytest.skip('Optional source-pinned ISAE archive is not installed.')
    folders=list((cache/'1 - Aerodynamics/SA - Steady Aerodynamics Cases').glob('SA - 6 - *'))
    assert len(folders)==1
    return folders[0]


def test_all_native_series_and_exact_raw_witnesses(original):
    result=NATIVE.catalog(ROOT)
    assert result['summary']==dict(series=14,native_scalar_references=308,
        exact_raw_export_witnesses=88,additional_author_tabulated_scalars=220,
        experimental_targets=0,synthetic_zero_targets=0,unregistered=True)
    assert result['new_aircraft_solves']==0 and not result['goal_complete']
    for series in result['series']:
        assert len(series['values'])==22
        assert sorted({r['delta'] for r in series['values']})==list(range(4,45,4))
        assert {r['channel'] for r in series['values']}=={'Cl','Cn'}
        assert not series['registered_acceptance'] and not series['historical_execution_authenticated']
        assert bool(series['geometry_conflict'])==(series['variant']=='10b_25c')
        assert bool(series['raw_export_witnesses'])==(series['regime']=='stall' and series['kind']=='chord')
        if not series['raw_export_witnesses']:
            assert series['operating_point']['body_alpha'] is None


def test_experimental_cells_are_never_parsed_as_native(original):
    text=(original/'Post_Treatment_Post_Stall.m').read_text()
    first=NATIVE.decode_matlab(text,'span')
    changed=text.replace('.0124\t-.0053','bad_experiment\tNaN_experiment',1)
    assert changed!=text
    assert NATIVE.decode_matlab(changed,'span')==first
    assert first[0]['token']=='0.008638' and first[1]['token']=='-0.002535'


@pytest.mark.parametrize('before,after,message',[
    ('0.008638','NaN','numeric'),
    ("Clark_Y_Steady_Span(1:end,4),'rs'","Clark_Y_Steady_Span(1:end,2),'rs'",'plot column'),
    ('= b/3,  \\  ASWING','= b/2,  \\  ASWING','variant legend'),
    ("xlabel('Aileron deflection in deg')","xlabel('Aileron deflection in rad')",'control units'),
    (',leg1,',',leg2,','legend ordering'),
])
def test_changed_native_bindings_rejected(original,before,after,message):
    text=(original/'Post_Treatment_Post_Stall.m').read_text()
    changed=text.replace(before,after,1)
    assert changed!=text
    with pytest.raises(ValueError,match=message):
        NATIVE.decode_matlab(changed,'span')


def test_original_typographical_labels_preserved(original):
    text=(original/'Post_Treatment_Level.m').read_text()
    span=NATIVE.decode_matlab(text,'span')
    chord=NATIVE.decode_matlab(text,'chord')
    assert span[0]['control_label']=='Aileron delfeciton in deg'
    assert chord[0]['coefficient_label']=='Rolling moment Coefficient'


def test_ods_addresses_preserve_leading_and_repeated_blanks(original):
    with zipfile.ZipFile(original/'ClarkY_Level_chord_varying.ods') as archive:
        sheet=NATIVE.decode_ods(archive.read('content.xml'))
    rows=sheet['rows']
    assert rows[0][0]['text']==''
    assert rows[0][1]['text']=='delta_F,c = 1.5 inch'
    assert rows[1][3]['text']=='Cl_ASW' and rows[1][4]['text']=='Cn_ASW'
    assert rows[3][0]['text']=='4' and rows[3][3]['text']=='0.016743'
    assert rows[13][0]['text']=='44'


def test_source_reader_has_no_solver_imports(original):
    import subprocess
    code="""import pathlib,sys
sys.path.insert(0,str(pathlib.Path(sys.argv[1])/'scripts'))
import isae_sa6_native_tables as m
assert len(m.catalog(sys.argv[1])['series'])==14
assert not any(n.split('.')[0] in ('numpy','scipy','openswing') for n in sys.modules)
"""
    subprocess.run([sys.executable,'-c',code,str(ROOT)],check=True,timeout=20,
                   capture_output=True,text=True)
