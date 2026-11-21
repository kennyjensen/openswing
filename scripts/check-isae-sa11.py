"""SA-11 provenance, load conventions, local-flow and runtime verification."""
from pathlib import Path
from collections import Counter
import argparse, importlib.util, json, sys
import numpy as np

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'scripts'))
from isae_sa11_reference import sha, CACHE, reconstruction
from openswing.asw import parse_asw
from openswing.geometry import model_meshes
spec=importlib.util.spec_from_file_location('sa11',ROOT/'scripts/verify-isae-sa11.py')
sa11=importlib.util.module_from_spec(spec);spec.loader.exec_module(sa11)
D=ROOT/'docs/validation'


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--partial',action='store_true');args=parser.parse_args()
    name='isae-sa11-progress.json' if args.partial else 'isae-sa11-comparison.json'
    snapshot=json.loads((D/name).read_text());sources=json.loads((D/'isae-sa11-sources.json').read_text())
    modules={p.name:sha(p) for p in (ROOT/'openswing').glob('*.py')}
    provenance=snapshot['provenance'];assert modules==provenance['modules']
    assert provenance['script_sha256']==sha(ROOT/'scripts/verify-isae-sa11.py')
    assert provenance['reference_script_sha256']==sha(ROOT/'scripts/isae_sa11_reference.py')
    assert provenance['source_report_sha256']==sha(D/'isae-sa11-sources.json')
    assert snapshot['script_sha256']==sha(ROOT/'scripts/summarize-isae-sa11.py')
    archive=json.loads((D/'isae-sa11-archive.json').read_text())
    assert archive['script_sha256']==sha(ROOT/'scripts/check-isae-sa11-archive.py')
    assert archive['source_report_sha256']==provenance['source_report_sha256']
    assert snapshot['archive_normalization_audit_sha256']==sha(D/'isae-sa11-archive.json')
    literal=[];derived=[]
    for model in sources['models']:
        assert (CACHE/model['path']).read_bytes()==model['source'].encode()
        assert sha(CACHE/model['path'])==model['sha256']
        for panels in [25,50,100]:
            try:mesh=model_meshes(parse_asw(model['source']),panels)
            except ValueError as exc:
                expected=model.get('error') or next(s['error'] for s in model['setups'] if s['panels']==panels)
                assert str(exc)==expected
                literal.append(dict(case=model['name'],panels=panels,status='rejected',error=str(exc)))
            else:
                assert next(s['status'] for s in model['setups'] if s['panels']==panels)=='constructed'
                literal.append(dict(case=model['name'],panels=panels,status='constructed',strips=sum(len(m.tm) for m in mesh)))
        repaired=next((r for r in sources['derived'] if r['name']==model['name']),None)
        if repaired:
            source,suffix,note=reconstruction(model['name'],model['source'])
            assert source==repaired['source'] and note==repaired['note']
            path=D/f"isae-sa11-{model['name']}-{suffix}.asw"
            assert path.read_bytes()==source.encode() and sha(path)==repaired['sha256']
            for panels in [25,50,100]:
                meshes=model_meshes(parse_asw(source),panels)
                derived.append(dict(case=repaired['case_id'],panels=panels,strips=sum(len(m.tm) for m in meshes)))
    assert Counter(r['status'] for r in literal)==dict(constructed=6,rejected=9)
    cases=sa11.case_entries(sources);models={c['case_id']:parse_asw(c['source']) for c in cases}
    plan={sa11.request_key(r):r for r in sa11.requests(cases,sources)};assert len(plan)==5304
    rows=[];maximum_flow_error=0.;maximum_origin_error=0.;profile_wrench_error=0.;normal_checked=0
    for entry in snapshot['cache_manifest']:
        path=ROOT/entry['cache_path'];assert sha(path)==entry['cache_sha256']
        row=json.loads(path.read_text());assert row['specification']==entry['specification'] and row['status']==entry['status']
        request=row['specification'];assert plan[sa11.request_key(request)]==request
        model=models[request['case']];result=row.get('result');maximum=None
        if result:
            assert result['residual']<=1e-8 and result['maximum_normal_mach']['normal_mach']<1
            assert max(result['independent_wrench_error'],result['drag_decomposition_error'])<2e-10
            assert all(np.isfinite(result[k]) for k in sa11.COEFFICIENTS)
            maximum=result['maximum_normal_mach'];qS=.5*model.constants[1]*request['speed']**2*model.reference[0,0]
            origin=np.array(result['moment'])+np.cross(model.reference[1],result['force'])
            maximum_origin_error=max(maximum_origin_error,abs(origin[1]/qS/model.reference[0,1]-result['Cm_origin']))
            if 'profiles' in result:
                forces=np.array([s['force'] for s in result['profiles']]);force=forces.sum(axis=0)
                profile_wrench_error=max(profile_wrench_error,float(np.max(abs(force-result['force']))/qS))
        elif (row.get('details') or {}).get('kind')=='section_normal_mach':
            assert row['details']['sound_speed']==model.constants[2]
            maximum=row['details']['maximum'];assert maximum['normal_mach']>=1
        if maximum:
            beam=next(b for b in model.beams if b.index==maximum['beam'])
            # Use the geometric axis derivative directly, independently of the
            # runtime's frame/projection implementation.
            tangent=beam.position(maximum['t'],derivative=1);tangent=tangent/np.linalg.norm(tangent)
            velocity=np.array(maximum['relative_velocity'])
            normal=float(np.linalg.norm(velocity-tangent*np.dot(velocity,tangent)))
            error=max(abs(normal-maximum['normal_speed'])/max(1.,normal),
                abs(normal/model.constants[2]-maximum['normal_mach'])/max(1.,maximum['normal_mach']))
            maximum_flow_error=max(maximum_flow_error,error);normal_checked+=1
        rows.append(row)
    assert max(maximum_flow_error,maximum_origin_error,profile_wrench_error)<2e-10
    assert Counter(r['status'] for r in rows)=={k:v for k,v in snapshot['outcomes'].items() if k!='not_computed'}
    assert len(rows)+snapshot['outcomes'].get('not_computed',0)==5304
    if not args.partial:assert len(rows)==5304
    evidence={}
    for filename,script in [('isae-sa11-velocity.json','check-isae-sa11-velocity.py'),
                            ('isae-sa11-source-geometry.json','check-isae-sa11-source-geometry.py')]:
        data=json.loads((D/filename).read_text())
        assert data['modules']==modules and data['source_report_sha256']==provenance['source_report_sha256']
        assert data['script_sha256']==sha(ROOT/'scripts'/script)
        evidence[filename]=sha(D/filename)
    fourier=json.loads((D/'isae-sa11-circulation.json').read_text())
    assert fourier['identity']['modules']==modules and fourier['identity']['source_report_sha256']==provenance['source_report_sha256']
    assert fourier['identity']['script_sha256']==sha(ROOT/'scripts/verify-isae-sa11-circulation.py')
    assert len(fourier['rows'])==48
    assert all(sha(ROOT/r['cache_path'])==r['cache_sha256'] for r in fourier['rows'])
    wasm=json.loads((D/'isae-sa11-wasm.json').read_text());browser=json.loads((D/'isae-sa11-browser.json').read_text())
    assert wasm['status']==browser['status']=='PASS'
    assert wasm['modules']==browser['modules']==modules
    assert wasm['sources_sha256']==browser['sources_sha256']==provenance['source_report_sha256']
    assert wasm['script_sha256']==sha(ROOT/'scripts/test-isae-sa11-wasm.mjs')
    assert browser['test_sha256']==sha(ROOT/'tests/browser/isae-sa11.spec.js')
    assert browser['web_main_sha256']==sha(ROOT/'web/main.js')
    assert wasm['native_sample_sha256']==sha(D/'isae-sa11-wasm-native.json')
    assert browser['pilot_sha256']==sha(D/'isae-sa11-pilot.json')
    assert len(wasm['rows'])==40 and len(wasm['literal_rejections'])==9
    assert len(browser['rows'])==14 and len(browser['literal_rejections'])==3
    if not args.partial:
        drag=json.loads((D/'isae-sa11-drag-checks.json').read_text())
        assert drag['status']=='PASS_MATCHED_LIFT_EVIDENCE_AUDIT_PHYSICAL_VALIDATION_INCOMPLETE'
        assert drag['script_sha256']==sha(ROOT/'scripts/check-isae-sa11-drag.py')
        assert drag['modules']==modules
        assert drag['study_sha256']==snapshot['study_sha256']==sha(D/'isae-sa11.json')
        assert drag['drag_sha256']==snapshot['drag_sha256']==sha(D/'isae-sa11-drag.json')
        assert drag['source_report_sha256']==provenance['source_report_sha256']
        assert drag['requested']==166 and drag['scans']==16
        evidence['isae-sa11-drag-checks.json']=sha(D/'isae-sa11-drag-checks.json')
    computed=[r['result'] for r in rows if r['status']=='computed']
    report=dict(status='PASS_INCOMPLETE_SNAPSHOT_NUMERICAL_CHECKS' if args.partial else 'PASS_NUMERICAL_CHECKS_NOT_EXPERIMENTAL_VALIDATION',
        script_sha256=sha(Path(__file__)),modules=modules,snapshot_sha256=sha(D/name),source_sha256=sha(D/'isae-sa11-sources.json'),
        completed_requests=len(rows),pending_requests=5304-len(rows),outcomes=dict(Counter(r['status'] for r in rows)),
        literal_input_checks=literal,derived_input_checks=derived,flow_projection_checks=normal_checked,
        maximum_flow_projection_relative_error=maximum_flow_error,maximum_origin_moment_error=maximum_origin_error,
        maximum_profile_force_coefficient_error=profile_wrench_error,
        maximum_residual=max((r['residual'] for r in computed),default=None),
        fourier_outcomes=dict(Counter(r['status'] for r in fourier['rows'])),
        wasm_outcomes=dict(Counter(r['status'] for r in wasm['rows'])),
        browser_outcomes=dict(Counter(r['status'] for r in browser['rows'])),
        evidence_sha256={**evidence,**{f:sha(D/f) for f in ['isae-sa11-circulation.json','isae-sa11-wasm.json','isae-sa11-browser.json','isae-sa11-archive.json']}},
        limitations=['Internal numerical and source consistency does not establish experimental accuracy.',
            'The transonic measurements, archived normalization/input conflicts, unresolved geometry and growing local flow remain limitations.',
            'No production module, physical input, core model, tolerance or Mach guard was changed.'])
    output='isae-sa11-progress-checks.json' if args.partial else 'isae-sa11-checks.json'
    (D/output).write_text(json.dumps(report,indent=2)+'\n')
    print(report['status'],len(rows),'completed requests;',5304-len(rows),'pending',flush=True)


if __name__=='__main__':main()
