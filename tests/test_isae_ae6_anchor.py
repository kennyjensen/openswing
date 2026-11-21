"""Original-source coverage and setup contracts for the AE6 modal anchor."""
import importlib.util
import json
from pathlib import Path

import pytest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('ae6_anchor',ROOT/'scripts/verify-isae-ae6-anchor.py')
anchor=importlib.util.module_from_spec(spec)
spec.loader.exec_module(anchor)


@pytest.fixture(scope='module')
def prepared(tmp_path_factory):
    if not anchor.FAMILY.exists():
        pytest.skip('Original optional ISAE source cache absent')
    folder=tmp_path_factory.mktemp('ae6-source')/'anchor'
    payload,plan=anchor.prepare(folder,32)
    return folder,payload,plan


def test_all_original_modal_rows_and_exact_st4_overlaps_are_retained(prepared):
    folder,payload,plan=prepared
    assert len(plan['tables'])==6 and plan['modal_rows']==1674 and plan['modal_scalar_slots']==3348
    assert [len(t['rows']) for t in plan['tables']]==[300,300,300,174,300,300]
    assert len(plan['targets'])==6 and {r['index'] for r in plan['targets']}=={2}
    record=next(t for t in plan['tables'] if t['group']=='Weight7a')
    assert all(p['identical'] for p in record['ST4_overlaps'])
    assert len(record['commanded_speeds'])==41 and record['commanded_speeds'][1]==120.5
    assert json.loads((folder/'plan.json').read_text())==plan
    assert json.loads((folder/'request.json').read_text())==payload


def test_declared_physical_settings_and_original_zero_area_are_explicit(prepared):
    _,payload,plan=prepared
    original=anchor.FAMILY/'Simulation_file/Weight7a/7a_b17.asw'
    assert payload['source']==original.read_text()
    assert '\n  0.0 0.2032  1.2192' in payload['source']
    assert payload['condition']['speed']==120.5
    assert payload['condition']['density']==1.0771417304
    assert payload['condition']['gravity_magnitude']==9.81
    assert payload['condition']['ground_effect']==0
    assert payload['condition']['freeze_influences'] is False and payload['condition']['aero_lag'] is True
    assert payload['modes']['count']==16 and payload['modes']['shift']==[0.,300.]
    assert payload['modes']['matrices'] is True and payload['modes']['frame']=='fixed'
    assert plan['operations']==dict(cold_bridge_calls=1,modal_solves=1,retries=0)
    assert all(t['historical_settings_authenticated'] is False for t in plan['tables'])


def test_changed_original_hash_is_rejected_before_output_creation(tmp_path,monkeypatch):
    if not anchor.FAMILY.exists():
        pytest.skip('Original optional ISAE source cache absent')
    original=anchor.pin
    def corrupted(path):
        record=original(path)
        if path==anchor.FAMILY/'Simulation_file/Weight7a/7a_b17.asw':
            record['sha256']='0'*64
        return record
    monkeypatch.setattr(anchor,'pin',corrupted)
    output=tmp_path/'bad'
    with pytest.raises(AssertionError):
        anchor.prepare(output,32)
    assert not output.exists()


def test_existing_evidence_is_never_overwritten(prepared):
    folder,_,_=prepared
    before=(folder/'plan.json').read_bytes()
    with pytest.raises(FileExistsError):
        anchor.prepare(folder,32)
    assert (folder/'plan.json').read_bytes()==before


def test_decoder_preserves_real_roots_and_printed_units():
    rows=anchor.rows('# name\n#\n# Op.Point Eigenvalue\n 2 -0.39484268D+03 0.0000000\n')
    assert rows[0]['eigenvalue']==[-394.84268,0.]
    assert rows[0]['decimal_half_units']==['0.000005','5E-8']
    assert rows[0]['tokens']==['2','-0.39484268D+03','0.0000000']


@pytest.mark.parametrize('row',['2 nan 1','0 1 2','2 1 2 3','2.0 1 2'])
def test_invalid_modal_rows_cannot_become_targets(row):
    with pytest.raises((AssertionError,ValueError)):
        anchor.rows('# name\n#\n# Op.Point Eigenvalue\n'+row+'\n')
