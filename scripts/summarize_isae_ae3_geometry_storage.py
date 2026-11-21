"""Verify and adopt the independently tested geometry-buffer lifetime fix."""
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import sys
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.probe_isae_ae2_cold_trace import read,write,pin

OUT=ROOT/'artifacts/isae/ae3-geometry-storage-20261111'


def tests(path):
    root=ET.parse(path).getroot()
    return [dict(name=t.attrib['classname']+'::'+t.attrib['name'],
                 failed=t.find('failure') is not None,error=t.find('error') is not None,
                 skipped=t.find('skipped') is not None) for t in root.iter('testcase')]


def assess():
    assert not (OUT/'assessment.json').exists()
    plan=read(OUT/'plan.json')
    for p in plan['pins']:assert pin(p['path'])==p,p['path']
    evidence=[pin(OUT/'plan.json')];receipts=[];accepted=[];physical=[];parity=[]
    for case in plan['cases']:
        folder=OUT/'cases'/case['name']
        terminal=read(folder/'terminal.json');witness=read(folder/'sources-verified.json')
        assert terminal['process_reaped'] and not terminal['supervisor_timeout']
        assert terminal['limits']==plan['limits'] and witness['all_pins_checked']
        assert witness['plan']==pin(OUT/'plan.json')
        receipts.append(dict(case=case['name'],started_utc=read(folder/'started.json')['observed_utc'],**terminal))
        evidence.extend(pin(p) for p in folder.iterdir() if p.is_file())
        if case['kind']=='pytest':
            items=tests(folder/'tests.xml')
            assert terminal['returncode']==case['expected_exit'] and items
            assert not any(t['error'] or t['skipped'] for t in items)
            if case['candidate']:
                assert not any(t['failed'] for t in items);accepted.extend(items)
            else:
                assert len(items)==2 and all(t['failed'] and 'consumed_column_storage' in t['name'] for t in items)
            continue
        if 'parity_result' in case:
            assert terminal['returncode']==0
            report=read(folder/'report.json')
            physical=report['checks'];parity=report['candidate_parity_checks']
            assert report['numerical_pass'] and len(physical)==11 and len(parity)==9
            assert all(c['passed'] and c['metric']<=c['gate'] for c in physical+parity)
            assert max(c['metric'] for c in parity)==0
        else:
            assert terminal['returncode']==1 and not (folder/'result.json').exists()
            failure=(folder/'stderr.log').read_text()
            assert 'geometry_tangent.py' in failure and "result = hstack(columns, format='csc')" in failure
            assert 'Unable to allocate 33.5 MiB' in failure
    assert len(accepted)==40 and len({t['name'] for t in accepted})==40
    chronology=sorted(receipts,key=lambda r:r['started_utc'])
    for a,b in zip(chronology,chronology[1:]):
        assert datetime.fromisoformat(b['started_utc'])>=datetime.fromisoformat(a['observed_utc'])
    original=OUT/'original/openswing';candidate=OUT/'candidate/openswing';changed=[]
    for p in sorted(original.rglob('*')):
        if not p.is_file():continue
        relative=p.relative_to(original)
        assert p.read_bytes()==(ROOT/'openswing'/relative).read_bytes(),relative
        if p.read_bytes()!=(candidate/relative).read_bytes():changed.append(str(relative))
    assert changed==['local_geometry_matrix.py']
    from scripts.probe_isae_ae3_geometry_storage import OLD_DECODE,NEW_DECODE,HELPER
    before=(original/changed[0]).read_text()
    expected=before.replace(OLD_DECODE,NEW_DECODE).replace('def signature(g):',HELPER+'def signature(g):')
    assert expected==(candidate/changed[0]).read_text()
    write(OUT/'assessment.json',dict(observed_utc=datetime.now(timezone.utc).isoformat(),
        status='LIFETIME_FIX_VERIFIED_REFINEMENT_REACHES_LATER_ASSEMBLY_LIMIT',
        assessor=pin(Path(__file__)),plan=pin(OUT/'plan.json'),source_pins=plan['pins'],evidence=evidence,
        accepted_tests=accepted,regressions_passed=40,original_lifetime_failures=2,
        control_physical_checks=physical,control_parity_checks=parity,maximum_control_parity_error=0.,
        receipts=receipts,serial_worker_windows_verified=True,changed_modules=changed,
        primary_votes_added=0,primary_scope=dict(passed=50,required=725,computed=72,mismatches=22,uncomputed=653),
        fixed='Dense local geometry buffers release when their last returned view is dropped, without waiting for cyclic collection. Values, ownership, shapes, matrix entries and physical equations are unchanged.',
        remaining='Nominal320 completes the geometry-column loop but fails allocating33.5MiB while concatenating the complete sparse geometry matrix; no new full-load state or reference vote.',
        earlier_failure='Nominal320 previously failed allocating2.01MiB inside LocalGeometryMatrix.columns. Release-before-Newton-rebuild alone did not fix it.',
        next_step='Release completed field-derivative caches or assemble the exact sparse matrix with lower peak storage. Preserve all entries and existing factor/rank/residual gates; do not raise limits.'))
    print(json.dumps(dict(regressions_passed=40,control_checks=20,control_parity_error=0.,
        refinement_completed=False,remaining_allocation_mib=33.5,primary_votes_added=0)))


def adopt():
    assert not (OUT/'adoption.json').exists()
    assessment=read(OUT/'assessment.json')
    for p in assessment['source_pins']+assessment['evidence']+[assessment['assessor']]:
        assert pin(p['path'])==p,p['path']
    relative=assessment['changed_modules'][0]
    target=ROOT/'openswing'/relative;before=pin(target)
    candidate=OUT/'candidate/openswing'/relative
    assert target.read_bytes()==(OUT/'original/openswing'/relative).read_bytes()
    shutil.copyfile(candidate,target)
    same=[]
    for p in sorted((OUT/'candidate/openswing').rglob('*')):
        if not p.is_file() or '__pycache__' in p.parts:continue
        production=ROOT/'openswing'/p.relative_to(OUT/'candidate/openswing')
        assert p.read_bytes()==production.read_bytes(),production
        same.append(pin(production))
    write(OUT/'adoption.json',dict(observed_utc=datetime.now(timezone.utc).isoformat(),
        assessment=pin(OUT/'assessment.json'),changed_modules=[relative],before=before,after=pin(target),
        tested_candidate=pin(candidate),production_matches_tested_candidate=same,
        historical_source_witness=pin(OUT/'original/openswing'/relative),
        checkpoint_identity_changed=True,primary_votes_added=0,
        remaining_refinement_failure_preserved=True))
    print('Adopted only local_geometry_matrix.py; production package matches the tested candidate.')


def check():
    from scripts import probe_isae_ae3_derivatives_r3 as supervisor
    adoption=read(OUT/'adoption.json')
    for p in adoption['production_matches_tested_candidate']:assert pin(p['path'])==p,p['path']
    folder=OUT/'production-check';assert not folder.exists();folder.mkdir()
    paths=[Path(__file__),OUT/'adoption.json',ROOT/'tests/test_local_geometry_matrix.py',
           ROOT/'tests/test_geometry_partials.py',ROOT/'tests/test_direct_circulation.py']
    write(folder/'plan.json',dict(cases=[dict(name='production-lifetime')],
        pins=adoption['production_matches_tested_candidate']+[pin(p) for p in paths],limits=supervisor.LIMITS))
    supervisor.OUT=folder;supervisor.__file__=__file__;supervisor.launch('production-lifetime')


def worker(name):
    assert name=='production-lifetime'
    import openswing,pytest
    assert Path(openswing.__file__).resolve().parent==ROOT/'openswing'
    folder=OUT/'production-check/cases'/name
    sys.exit(pytest.main([str(ROOT/'tests/test_local_geometry_matrix.py'),'-q','-k','consumed_column_storage',
        '--junitxml='+str(folder/'tests.xml'),'-p','no:cacheprovider']))


def verify():
    folder=OUT/'production-check/cases/production-lifetime'
    terminal=read(folder/'terminal.json');items=tests(folder/'tests.xml')
    assert terminal['returncode']==0 and terminal['process_reaped'] and not terminal['supervisor_timeout']
    assert len(items)==2 and not any(t['failed'] or t['error'] or t['skipped'] for t in items)
    witness=read(folder/'sources-verified.json')
    assert witness['all_pins_checked'] and witness['plan']==pin(OUT/'production-check/plan.json')
    adoption=read(OUT/'adoption.json')
    for p in adoption['production_matches_tested_candidate']:assert pin(p['path'])==p,p['path']
    write(OUT/'production-verification.json',dict(observed_utc=datetime.now(timezone.utc).isoformat(),
        adoption=pin(OUT/'adoption.json'),plan=pin(OUT/'production-check/plan.json'),tests=items,
        evidence=[pin(p) for p in folder.iterdir() if p.is_file()],terminal=terminal,
        current_package_matches_tested_candidate=True,primary_votes_added=0))
    print('Production lifetime checks pass; current package matches the fully tested candidate.')


if __name__=='__main__':
    if sys.argv[1]=='worker':worker(sys.argv[2])
    else:{'assess':assess,'adopt':adopt,'check':check,'verify':verify}[sys.argv[1]]()
