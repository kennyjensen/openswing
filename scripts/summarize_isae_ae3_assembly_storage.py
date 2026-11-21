"""Assess and adopt the tested release of consumed geometry workspaces."""
from datetime import datetime,timezone
from pathlib import Path
import shutil
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.probe_isae_ae2_cold_trace import read,write,pin
from scripts.summarize_isae_ae3_geometry_storage import tests

OUT=ROOT/'artifacts/isae/ae3-assembly-storage-r3-20261111'


def assess():
    assert not (OUT/'assessment.json').exists()
    plan=read(OUT/'plan.json')
    for p in plan['pins']:assert pin(p['path'])==p,p['path']
    accepted=[];receipts=[];evidence=[pin(OUT/'plan.json')];physical=[];parity=[];refinement=None;retries=[]
    for case in plan['cases']:
        folder=OUT/'cases'/case['name'];terminal=read(folder/'terminal.json')
        retry=OUT/'retries'/case['name']
        selected_plan=OUT/'plan.json'
        if retry.exists():
            prior=read(folder/'sources-verified.json')
            assert terminal['process_reaped'] and terminal['returncode']!=0
            assert prior['all_pins_checked'] and prior['plan']==pin(selected_plan)
            receipts.append(dict(case=case['name']+'-original-attempt',started_utc=read(folder/'started.json')['observed_utc'],**terminal))
            evidence.extend(pin(p) for p in folder.iterdir() if p.is_file())
            retry_plan=read(retry/'plan.json')
            assert retry_plan['cases']==[case] and retry_plan['limits']==plan['limits']
            for p in retry_plan['pins']:assert pin(p['path'])==p,p['path']
            evidence.append(pin(retry/'plan.json'));retries.append(case['name'])
            folder=retry/'cases'/case['name'];terminal=read(folder/'terminal.json');selected_plan=retry/'plan.json'
        witness=read(folder/'sources-verified.json')
        assert terminal['process_reaped'] and terminal['limits']==plan['limits']
        assert witness['all_pins_checked'] and witness['plan']==pin(selected_plan)
        receipts.append(dict(case=case['name'],started_utc=read(folder/'started.json')['observed_utc'],**terminal))
        evidence.extend(pin(p) for p in folder.iterdir() if p.is_file())
        if case['kind']=='pytest':
            items=tests(folder/'tests.xml')
            assert terminal['returncode']==case['expected_exit'] and not terminal['supervisor_timeout']
            assert items and not any(t['error'] or t['skipped'] for t in items)
            if case['candidate']:
                assert not any(t['failed'] for t in items);accepted.extend(items)
            else:
                assert len(items)==1 and items[0]['failed']
                log=(folder/'stdout.log').read_text()
                assert 'assert references and all(ref() is None for ref in references)' in log
                assert 'GroundIntersectionError' not in log
        elif 'parity_result' in case:
            report=read(folder/'report.json');physical=report['checks'];parity=report['candidate_parity_checks']
            assert terminal['returncode']==0 and report['numerical_pass']
            assert len(physical)==11 and len(parity)==9 and all(c['passed'] for c in physical+parity)
            assert max(c['metric'] for c in parity)==0.
        else:
            refinement=dict(terminal=terminal,computed=(folder/'result.json').exists(),
                stderr=(folder/'stderr.log').read_text(),case=case['name'])
            if terminal['returncode']==0:
                assert refinement['computed'] and read(folder/'report.json')['numerical_pass']
            else:assert not refinement['computed']
    assert len({t['name'] for t in accepted})==len(accepted) and len(accepted)==17
    chronology=sorted(receipts,key=lambda r:r['started_utc'])
    for a,b in zip(chronology,chronology[1:]):
        assert datetime.fromisoformat(b['started_utc'])>=datetime.fromisoformat(a['observed_utc'])
    changed=[]
    for p in sorted((OUT/'original/openswing').rglob('*')):
        if not p.is_file() or '__pycache__' in p.parts:continue
        relative=p.relative_to(OUT/'original/openswing')
        assert p.read_bytes()==(ROOT/'openswing'/relative).read_bytes()
        if p.read_bytes()!=(OUT/'candidate/openswing'/relative).read_bytes():changed.append(str(relative))
    assert changed==['geometry_tangent.py']
    from scripts.probe_isae_ae3_assembly_storage import patch
    assert patch((OUT/'original/openswing/geometry_tangent.py').read_text())==(OUT/'candidate/openswing/geometry_tangent.py').read_text()
    write(OUT/'assessment.json',dict(observed_utc=datetime.now(timezone.utc).isoformat(),
        assessor=pin(Path(__file__)),plan=pin(OUT/'plan.json'),source_pins=plan['pins'],evidence=evidence,
        accepted_tests=accepted,regressions_passed=len(accepted),original_lifetime_failures=1,
        control_physical_checks=physical,control_parity_checks=parity,maximum_control_parity_error=0.,
        receipts=receipts,serial_worker_windows_verified=True,changed_modules=changed,refinement=refinement,
        retained_original_attempts_with_unchanged_retry=retries,
        primary_votes_added=0,primary_scope=dict(passed=50,required=725,computed=72,mismatches=22,uncomputed=653)))
    print(f'{len(accepted)} regressions pass; 20 control checks pass with zero difference. Refinement computed: {refinement["computed"]}.')


def adopt():
    assert not (OUT/'adoption.json').exists()
    assessment=read(OUT/'assessment.json')
    for p in assessment['source_pins']+assessment['evidence']+[assessment['assessor']]:
        assert pin(p['path'])==p,p['path']
    relative=assessment['changed_modules'][0];target=ROOT/'openswing'/relative
    candidate=OUT/'candidate/openswing'/relative;before=pin(target)
    assert target.read_bytes()==(OUT/'original/openswing'/relative).read_bytes()
    shutil.copyfile(candidate,target)
    same=[]
    for p in sorted((OUT/'candidate/openswing').rglob('*')):
        if not p.is_file() or '__pycache__' in p.parts:continue
        production=ROOT/'openswing'/p.relative_to(OUT/'candidate/openswing')
        assert p.read_bytes()==production.read_bytes();same.append(pin(production))
    write(OUT/'adoption.json',dict(observed_utc=datetime.now(timezone.utc).isoformat(),assessment=pin(OUT/'assessment.json'),
        before=before,after=pin(target),tested_candidate=pin(candidate),production_matches_tested_candidate=same,
        historical_source_witness=pin(OUT/'original/openswing'/relative),checkpoint_identity_changed=True,primary_votes_added=0))
    print('Adopted geometry_tangent.py; production package matches the tested candidate.')


def check():
    from scripts import probe_isae_ae3_derivatives_r3 as supervisor
    adoption=read(OUT/'adoption.json')
    for p in adoption['production_matches_tested_candidate']:assert pin(p['path'])==p,p['path']
    folder=OUT/'production-check';assert not folder.exists()
    paths=[Path(__file__),OUT/'adoption.json',ROOT/'tests/test_geometry_assembly_storage.py',ROOT/'tests/test_direct_circulation.py']
    write(folder/'plan.json',dict(cases=[dict(name='production-lifetime')],
        pins=adoption['production_matches_tested_candidate']+[pin(p) for p in paths],limits=supervisor.LIMITS))
    supervisor.OUT=folder;supervisor.__file__=__file__;supervisor.launch('production-lifetime')


def worker(name):
    assert name=='production-lifetime'
    import openswing,pytest
    assert Path(openswing.__file__).resolve().parent==ROOT/'openswing'
    folder=OUT/'production-check/cases'/name
    sys.exit(pytest.main([str(ROOT/'tests/test_geometry_assembly_storage.py'),'-q',
        '--junitxml='+str(folder/'tests.xml'),'-p','no:cacheprovider']))


def verify():
    folder=OUT/'production-check/cases/production-lifetime'
    terminal=read(folder/'terminal.json');items=tests(folder/'tests.xml')
    assert terminal['returncode']==0 and terminal['process_reaped'] and not terminal['supervisor_timeout']
    assert len(items)==4 and not any(t['failed'] or t['error'] or t['skipped'] for t in items)
    witness=read(folder/'sources-verified.json')
    assert witness['all_pins_checked'] and witness['plan']==pin(OUT/'production-check/plan.json')
    adoption=read(OUT/'adoption.json')
    for p in adoption['production_matches_tested_candidate']:assert pin(p['path'])==p,p['path']
    write(OUT/'production-verification.json',dict(observed_utc=datetime.now(timezone.utc).isoformat(),
        adoption=pin(OUT/'adoption.json'),plan=pin(OUT/'production-check/plan.json'),tests=items,
        evidence=[pin(p) for p in folder.iterdir() if p.is_file()],terminal=terminal,
        current_package_matches_tested_candidate=True,primary_votes_added=0))
    print('Production lifetime/ownership checks pass; package matches the tested candidate.')


if __name__=='__main__':
    if sys.argv[1]=='worker':worker(sys.argv[2])
    else:{'assess':assess,'adopt':adopt,'check':check,'verify':verify}[sys.argv[1]]()
