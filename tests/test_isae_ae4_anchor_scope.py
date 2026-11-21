"""Original speed/index binding and preservation of incomplete modal sets."""
import importlib.util
from pathlib import Path

import pytest

ROOT=Path(__file__).resolve().parents[1]
SPEC=importlib.util.spec_from_file_location('ae4_anchor',ROOT/'scripts/verify-isae-ae4-wall-modes.py')
AE4=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AE4)


def test_artifact_pin_streams_without_reading_the_whole_file(tmp_path,monkeypatch):
    import hashlib
    payload=b'\x00retained AE-4 result\xff\n'*1000
    path=tmp_path/'result.bin';path.write_bytes(payload)
    monkeypatch.setattr(AE4,'ROOT',tmp_path)
    def whole_file_read(*args,**kwargs):
        raise AssertionError('Pinning must not allocate the whole artifact')
    monkeypatch.setattr(Path,'read_bytes',whole_file_read)
    assert AE4.pin(path)==dict(path='result.bin',bytes=len(payload),
                               sha256=hashlib.sha256(payload).hexdigest())


@pytest.fixture(scope='module')
def original():
    if not (AE4.ORIGINAL/'alpha_0.sh').is_file():
        pytest.skip('Original reference cache is optional')
    return (AE4.ORIGINAL/'alpha_0.sh').read_text(),AE4.original_rows(AE4.ORIGINAL/'alpha_0_eig.txt')


@pytest.mark.parametrize('speed',[1,40,69,70,108])
def test_literal_stack_binds_original_commands_without_selecting_by_agreement(original,speed):
    driver,rows=original
    selected=AE4.declared_targets(driver,rows,speed)
    assert selected==[r for r in rows if r['values'][0]==speed+1]


@pytest.mark.parametrize('speed',[0,109,-1,40.5,True])
def test_unknown_initial_and_missing_terminal_points_are_not_invented(original,speed):
    with pytest.raises(ValueError,match='original commanded IAS'):
        AE4.declared_targets(*original,speed)


def test_insertion_order_matters_not_just_speed_and_plus_counts(original):
    driver,rows=original
    changed=driver.replace('+\n!V 2','!V 2\n+',1)
    assert changed!=driver
    with pytest.raises(AssertionError):AE4.declared_targets(changed,rows,40)


def target(line,re,im):
    tokens=['2',re,im]
    return dict(line=line,tokens=tokens,values=list(map(float,tokens)))


def test_complete_positive_sets_use_frequency_order_and_retain_original_row_order():
    targets=[target(4,'-2.000','20.000'),target(5,'-1.000','10.000')]
    modes=[dict(eigenvalue=[-1.,-10.]),dict(eigenvalue=[-1.,10.]),dict(eigenvalue=[-2.,20.])]
    rows=AE4.compare_roots(modes,targets)
    assert [r['original'] for r in rows]==targets
    assert [r['actual'] for r in rows]==[[-2.,20.],[-1.,10.]]
    assert all(r['printed_precision']==[True,True] for r in rows)


@pytest.mark.parametrize('predicted',[[[-2.,20.]],[[-1.,10.],[-2.,20.],[-3.,30.]]])
def test_incomplete_or_different_selected_spectrum_cannot_shift_native_ordinals(predicted):
    targets=[target(4,'-1.000','10.000'),target(5,'-2.000','20.000')]
    rows=AE4.compare_roots([dict(eigenvalue=v) for v in predicted],targets)
    assert len(rows)==2 and all(r['status']=='unavailable' and 'actual' not in r for r in rows)


def test_real_native_pole_remains_required_without_an_invented_branch_match():
    targets=[target(4,'-2.000','0.000'),target(5,'-1.000','10.000')]
    rows=AE4.compare_roots([dict(eigenvalue=[-2.,0.]),dict(eigenvalue=[-1.,10.])],targets)
    assert rows[0]['original']==targets[0] and rows[0]['status']=='unavailable'
    assert rows[1]['actual']==[-1.,10.]


def test_certified_real_roundoff_does_not_shift_positive_frequency_order():
    targets=[target(4,'-1.000','10.000'),target(5,'-2.000','20.000')]
    modes=[dict(eigenvalue=v) for v in [[-23.,1e-12],[-2.,20.],[-1.,10.]]]
    classes=[dict(mode_index=i,eigenvalue=m['eigenvalue'],classification=k) for i,(m,k) in
             enumerate(zip(modes,['certified_real','positive_frequency','positive_frequency']))]
    rows=AE4.compare_roots(modes,targets,classifications=classes)
    assert [r['actual'] for r in rows]==[[-1.,10.],[-2.,20.]]
    assert modes[0]['eigenvalue']==[-23.,1e-12]
    classes[0]['classification']='unresolved_near_real'
    assert all(r['status']=='unavailable' for r in AE4.compare_roots(modes,targets,classifications=classes))


def test_classification_from_a_different_spectrum_is_rejected():
    modes=[dict(eigenvalue=[-1.,10.])]
    classes=[dict(mode_index=0,eigenvalue=[-1.,20.],classification='positive_frequency')]
    with pytest.raises(ValueError,match='classification'):
        AE4.compare_roots(modes,[target(4,'-1.000','10.000')],classifications=classes)


def test_certifying_a_real_prediction_does_not_authenticate_a_real_native_branch():
    modes=[dict(eigenvalue=[-2.,1e-12]),dict(eigenvalue=[-1.,10.])]
    classes=[dict(mode_index=i,eigenvalue=m['eigenvalue'],classification=k) for i,(m,k) in
             enumerate(zip(modes,['certified_real','positive_frequency']))]
    rows=AE4.compare_roots(modes,[target(4,'-2.000','0.000'),target(5,'-1.000','10.000')],classifications=classes)
    assert len(rows)==2 and rows[0]['status']=='unavailable'
    assert rows[1]['actual']==[-1.,10.]
