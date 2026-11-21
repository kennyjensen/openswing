"""Progress preserves denominators, timestamps and distinctions between scopes."""
from copy import deepcopy
import json
from pathlib import Path

import pytest
from scripts import isae_progress as progress

ROOT=Path(__file__).resolve().parents[1]


@pytest.fixture
def source():
    # Stable contract examples: legitimate future progress must not require
    # changing test expectations to whatever happens to be in the live ledger.
    config=json.loads((ROOT/'docs/validation/isae-progress-scopes.json').read_text())
    counts={
        'SA-1':'154/154 pass at 5%',
        'SA-15':'Historical 0/182 blocked; shared conditional scope 84/182 at 5%',
        'UA-1':'148/148 harmonic; 12/12 phase',
        'UA-2':'0/222 native; 16/16 analytical',
        'ST-3':'Historical original thresholds: 930/1,080 static; 8/9 conditional modal',
        'ST-4':'Vacuum 93/3,749 at 5%; historical airflow 4/30',
        'ST-5':'Historical original thresholds: 13,833/25,920; 14,708/25,920; 10,670/18,792; 13,583/25,920',
        'ST-6':'No native target. Analytical 2/2',
        'AE-1':'Historical baseline 98/1,200; conditional 24/48 at 5%',
        'AE-2':'Historical baseline 2/2,200; conditional 24/24 at 5%',
        'AE-4':'Shared sweep 11/1,200 at 5%; sampled 67/88',
        'AE-6':'Shared sweep 116/6,696 at 5%; computed 116/118',
        'FFWT-2':'At 5%: equilibrium 10/4,005 (10/25 computed); jig 5/4,005 (5/25 computed)',
        'FFWT-3':'0/36,462 blocked',
        'P-3':'Not registered',
    }
    rows=[f"| [{key}](case.md) | Example {key} | {counts.get(key,'1/2 pass at 5%')} | — | Retained. |"
          for key in progress.EXPECTED]
    rows.append('| [SA-9](missing.md) | Absent upstream | — | — | Excluded. |')
    return '\n'.join(rows),config


def test_current_status_scope_selection_remains_unambiguous():
    cases=progress.parse_status((ROOT/'docs/validation/ISAE_STATUS.md').read_text(),
        json.loads((ROOT/'docs/validation/isae-progress-scopes.json').read_text()))
    assert len(cases)==41


def test_complete_inventory_and_selected_native_scopes(source):
    cases=progress.parse_status(*source);by={c['id']:c for c in cases}
    assert len(cases)==41 and 'SA-9' not in by
    assert (by['SA-15']['passed'],by['SA-15']['total'])==(84,182)
    assert (by['FFWT-2']['passed'],by['FFWT-2']['total'])==(5,4005)
    assert (by['ST-5']['passed'],by['ST-5']['total'])==(13833+14708+10670+13583,25920*3+18792)
    assert by['UA-2']['total']==222 and by['UA-2']['passed']==0
    assert by['UA-1']['total'] is by['ST-6']['total'] is None
    assert by['AE-1']['total']==1200 and by['AE-6']['total']==6696
    assert by['FFWT-3']['total']==36462


def add(history,cases,when,reason='test'):
    return progress.record(history,cases,timestamp=when,reason=reason,source_sha256='source',scopes_sha256='scopes')


def test_count_denominator_and_policy_changes_are_timestamped_but_prose_is_not(source):
    cases=progress.parse_status(*source);history=dict(version=1,events=[])
    first=add(history,cases,'2026-11-06T00:00:00Z');original=deepcopy(first)
    prose=deepcopy(cases);prose[0]['name']='New wording';prose[0]['status_fraction']='wording only'
    assert add(history,prose,'2026-11-06T00:01:00Z') is None
    expanded=deepcopy(cases);expanded[0].update(passed=308,total=308)
    second=add(history,expanded,'2026-11-06T00:02:00Z')
    assert second['changes'][0]['before']['total']==154 and second['changes'][0]['after']['total']==308
    assert second['previous']==first['id'] and first==original
    policy=deepcopy(expanded);policy[0]['acceptance']='3%'
    assert add(history,policy,'2026-11-06T00:03:00Z')['changes'][0]['case']=='SA-1'
    with pytest.raises(ValueError,match='follow'):
        add(history,cases,'2026-11-06T00:02:00Z')


def test_overall_includes_unscored_cases_without_inventing_scalar_denominators():
    cases=[dict(passed=5,total=10,percent=50),dict(passed=90,total=100,percent=90),
           dict(passed=None,total=None,percent=None)]
    total=progress.totals(cases)
    assert total['case_average_percent']==pytest.approx(140/3)
    assert total['pooled_percent']==pytest.approx(100*95/110)
    assert total['unscored_cases']==1 and total['total']==110


def test_history_roundtrip_and_modified_event_detection(source,tmp_path):
    history=dict(version=1,events=[]);add(history,progress.parse_status(*source),'2026-11-06T00:00:00Z')
    path=tmp_path/'history.json';progress.write_json(path,history)
    assert progress.read_history(path)==history
    history['events'][0]['cases'][0]['passed']=0;progress.write_json(path,history)
    with pytest.raises(ValueError,match='integrity'):progress.read_history(path)


@pytest.mark.parametrize('fault',['missing_case','duplicate','invalid_fraction','ambiguous_scope'])
def test_invalid_or_ambiguous_status_cannot_silently_change_coverage(source,fault):
    text,config=source;line=next(l for l in text.splitlines() if l.startswith('| [SA-1]'))
    if fault=='missing_case':text=text.replace(line,'')
    if fault=='duplicate':text+='\n'+line
    if fault=='invalid_fraction':text=text.replace('154/154 pass','155/154 pass')
    if fault=='ambiguous_scope':text=text.replace('154/154 pass','154/154 pass; 2/3 other')
    with pytest.raises(ValueError):progress.parse_status(text,config)


def test_dashboard_shows_single_baseline_without_fabricating_earlier_progress(source):
    history=dict(version=1,events=[]);event=add(history,progress.parse_status(*source),'2026-11-06T00:00:00Z')
    markup=progress.dashboard(event,history['events'],['SA','UA','P','AP','ST','AE','FFWT'])
    assert markup.count('<article ')==41 and 'No earlier progress is inferred' in markup
    assert '0/36,462' in markup and 'native' in markup


@pytest.fixture
def temporary_tracker(source,tmp_path,monkeypatch):
    text,config=source
    (tmp_path/'docs/validation').mkdir(parents=True);(tmp_path/'web').mkdir()
    (tmp_path/'docs/validation/ISAE_STATUS.md').write_text(text)
    progress.write_json(tmp_path/'docs/validation/isae-progress-scopes.json',config)
    (tmp_path/'web/plot-colors.js').write_text('palette')
    calls=[]
    def rendered(history,destination,root):
        calls.append(deepcopy(history))
        for p in progress.generated_files(destination):progress.atomic_write(p,'fixture')
        progress.write_json(destination/'rendered.json',progress.render_identity(history,root))
    monkeypatch.setattr(progress,'render',rendered)
    return tmp_path,calls,rendered


def test_every_fraction_update_regenerates_and_missing_plot_is_recovered(temporary_tracker):
    root,calls,_=temporary_tracker
    assert progress.update(root)['status']=='RECORDED' and len(calls)==1
    assert progress.update(root)['status']=='UNCHANGED' and len(calls)==1
    path=root/'docs/validation/ISAE_STATUS.md';path.write_text(path.read_text().replace('154/154 pass','153/154 pass'))
    assert progress.update(root)['changed_cases']==['SA-1'] and len(calls)==2
    assert progress.update(root,check=True)['observations']==2
    (root/'public/isae-progress/overall.svg').unlink()
    with pytest.raises(ValueError,match='missing'):progress.update(root,check=True)
    assert progress.update(root)['observations']==2 and len(calls)==3


def test_interrupted_render_retries_without_duplicate_timestamp(temporary_tracker,monkeypatch):
    root,calls,rendered=temporary_tracker
    def broken(*args):raise RuntimeError('Interrupted plotting')
    monkeypatch.setattr(progress,'render',broken)
    with pytest.raises(RuntimeError):progress.update(root)
    saved=progress.read_history(root/'docs/validation/isae-progress/history.json')
    assert len(saved['events'])==1
    monkeypatch.setattr(progress,'render',rendered)
    assert progress.update(root)['status']=='UNCHANGED' and len(calls)==1
    assert progress.read_history(root/'docs/validation/isae-progress/history.json')==saved
