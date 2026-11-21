"""Check pinned SA-12 evidence, source rows, force conventions and runtime parity."""
from pathlib import Path
from collections import Counter
import csv, hashlib, importlib.util, json, sys
import numpy as np

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'scripts'))
from isae_sa12_reference import sha,CACHE
from openswing.asw import parse_asw
from openswing.geometry import model_meshes
spec=importlib.util.spec_from_file_location('sa12',ROOT/'scripts/verify-isae-sa12.py')
sa12=importlib.util.module_from_spec(spec);spec.loader.exec_module(sa12)
D=ROOT/'docs/validation'


def main():
    sources=json.loads((D/'isae-sa12-sources.json').read_text())
    native=json.loads((D/'isae-sa12.json').read_text())
    comparison=json.loads((D/'isae-sa12-comparison.json').read_text())
    p=native['provenance'];modules={f.name:sha(f) for f in (ROOT/'openswing').glob('*.py')}
    assert p==comparison['provenance'] and p['modules']==sources['modules']==modules
    assert p['source_report_sha256']==sha(D/'isae-sa12-sources.json')
    assert p['script_sha256']==sha(ROOT/'scripts/verify-isae-sa12.py')
    assert p['reference_script_sha256']==sources['script_sha256']==sha(ROOT/'scripts/isae_sa12_reference.py')
    assert comparison['native_sha256']==sha(D/'isae-sa12.json')
    assert comparison['script_sha256']==sha(ROOT/'scripts/summarize-isae-sa12.py')
    for name,pin in comparison['verification_evidence_sha256'].items():assert sha(D/name)==pin
    assert len(sources['sources'])==28
    for name,pin in sources['sources'].items():
        data=(CACHE/name).read_bytes();assert len(data)==pin['bytes'] and hashlib.sha256(data).hexdigest()==pin['sha256']
        assert hashlib.sha1(f'blob {len(data)}\0'.encode()+data).hexdigest()==pin['git_blob_sha1']
    for source in sources['primary']:assert sha(ROOT/source['path'])==source['sha256']
    assert sha(ROOT/'.reference/isae-sa12/primary-review.json')==sources['primary_review_sha256']
    models={};setups=[]
    for c in sources['models']:
        assert (CACHE/c['path']).read_bytes()==c['source'].encode()
        assert sha(CACHE/c['path'])==c['sha256']
        m=parse_asw(c['source']);models[c['name']]=m
        assert np.array_equal(m.reference,c['reference']) and np.array_equal(m.constants,c['constants'])
        for panels,strips in [(25,26),(50,50),(100,100)]:
            mesh,=model_meshes(m,panels);assert len(mesh.tm)==strips
            assert np.max(abs(mesh.rm[:,[0,2]]))<1e-14
            setups.append(dict(case=c['name'],requested_panels=panels,actual_strips=strips))
    plan,groups=sa12.requests(sources);rows={sa12.key(r['specification']):r for r in native['rows']}
    assert len(rows)==len(plan)==native['total']==2866
    assert set(rows)=={sa12.key(r) for r in plan} and native['groups']==groups
    counts=Counter(r['status'] for r in rows.values());assert counts==dict(computed=2866)
    assert native['computed']==comparison['computed']==2866 and native['rejected']==comparison['rejected']==0
    errors=dict(force=0.,moment=0.,drag_decomposition=0.,ground_normal=0.,ground_offset=0.,profile_force=0.,normal_mach=0.,profile_friction=0.)
    for row in rows.values():
        path=ROOT/row['cache_path'];assert sha(path)==row['cache_sha256']
        raw=json.loads(path.read_text());assert all(raw[k]==row[k] for k in raw)
        q=row['specification'];r=row['result'];m=models[q['case']]
        assert np.isfinite([r[k] for k in sa12.COEFFICIENTS if r[k] is not None]).all()
        assert 0<=r['residual']<=1e-8 and r['actual_strips']=={25:26,50:50,100:100}[q['panels']]
        qS=.5*m.constants[1]*35.76**2*m.reference[0,0]
        a=np.deg2rad(q['alpha']);wind=np.array([np.cos(a),0,np.sin(a)]);lift=np.array([-np.sin(a),0,np.cos(a)])
        force=np.array(r['force']);moment=np.array(r['moment'])
        errors['force']=max(errors['force'],abs(force@wind/qS-r['CD']),abs(force@lift/qS-r['CL']),abs(force[1]/qS-r['CY']))
        errors['moment']=max(errors['moment'],abs(moment[1]/qS/m.reference[0,1]-r['Cm']),
            abs(-moment[0]/qS/m.reference[0,2]-r['Cl']),abs(-moment[2]/qS/m.reference[0,2]-r['Cn']))
        errors['drag_decomposition']=max(errors['drag_decomposition'],abs(r['CD']-r['CDi_near']-r['CDp']))
        theta=a if q['pose']=='level_freestream' else 0.;normal=np.array([-np.sin(theta),0,np.cos(theta)])
        plane=r['ground_plane'];assert plane['flag']==q['ground']
        errors['ground_normal']=max(errors['ground_normal'],float(np.max(abs(normal-plane['normal_body']))))
        errors['ground_offset']=max(errors['ground_offset'],abs(plane['offset']-q['height']))
        assert r['trefftz']['available']==(r['CDi'] is not None)
        if q['pose']=='level_freestream':assert abs(wind@normal)<1e-14
        if q['pose']=='zero_attitude' and q['alpha']!=0:assert r['CDi'] is None
        if 'profiles' in r:
            profiles=r['profiles'];f=np.sum([v['force'] for v in profiles],axis=0)
            errors['profile_force']=max(errors['profile_force'],float(np.max(abs(f-force)))/qS)
            friction=0.
            for v in profiles:
                velocity=np.array(v['relative_velocity']);normal_speed=float(np.hypot(velocity[0],velocity[2]))
                errors['normal_mach']=max(errors['normal_mach'],abs(normal_speed/m.constants[2]-v['normal_mach']))
                cf=.01 if q['case']=='no_flap' else .04
                friction+=.5*m.constants[1]*np.linalg.norm(velocity)*(velocity@wind)*.254*cf*v['length']/qS
            errors['profile_friction']=max(errors['profile_friction'],abs(friction-r['CD_friction']))
    assert max(errors.values())<2e-10,errors
    for table in sources['archived']:
        assert np.array_equal(np.loadtxt(CACHE/table['path']),table['rows'])
        assert len(table['rows'])==85
    measured_counts=Counter();statistic_error=0.
    for entry in comparison['experimental']:
        source=sources['experimental'][entry['case']][entry['quantity']][entry['height_label']]
        raw=list(csv.reader((CACHE/source['path']).read_text().splitlines()))
        j={'05':0,'2':2,'inf':4}[entry['height_label']]
        independently_read=[(i+3,float(r[j]),float(r[j+1])) for i,r in enumerate(raw[2:]) if r[j].strip()]
        assert [(r['source_row'],r['alpha'],r['observed']) for r in entry['points']]==independently_read
        coefficient='CL' if entry['quantity']=='lift' else 'CD';case=next(c for c in sources['models'] if c['name']==entry['case'])
        pairs=[]
        for point in entry['points']:
            q=sa12.specification(case,entry['height_label'],entry['panels'],point['alpha'])
            expected=rows[sa12.key(q)]['result'][coefficient];assert point['predicted']==expected
            pairs.append(expected-point['observed'])
            if 'fixed_display_prediction' in point:
                cdi=rows[sa12.key(q)]['result']['CDi'];assert point['fixed_display_prediction']==.01+cdi
        e=np.array(pairs);metrics=entry['metrics']
        statistic_error=max(statistic_error,abs(metrics['rmse']-np.sqrt(np.mean(e*e))),
            abs(metrics['mean_error']-np.mean(e)),abs(metrics['maximum_absolute_error']-max(abs(e))))
        assert metrics['requested']==metrics['available']==len(independently_read) and metrics['missing']==0
        if entry['panels']==100:measured_counts[entry['quantity']]+=len(independently_read)
    assert measured_counts==dict(lift=75,drag=71) and statistic_error<1e-14
    assert Counter(g for gl in groups.values() for g in gl)=={
        'primary_pose_archived_angles':1530,'experimental_lift_angles':225,'experimental_drag_angles':213,
        'pg_influence_sensitivity':270,'zero_attitude_archive_diagnostic':510,'fourier_sensitivity':72,
        'primary_angle_height_error_bounds':16,'no_ground_limit':30}
    for n in [25,50,100]:
        for label in sa12.HEIGHTS:
            case=next(c for c in sources['models'] if c['name']=='no_flap')
            r=rows[sa12.key(sa12.specification(case,label,n,0.))]['result']
            assert abs(r['CL'])<1e-9 and abs(r['CD']-.01*1.524*.254/.3871)<1e-11
    velocity=json.loads((D/'isae-sa12-velocity.json').read_text());assert len(velocity['rows'])==8
    assert velocity['modules']==modules and velocity['source_report_sha256']==p['source_report_sha256']
    assert velocity['script_sha256']==sha(ROOT/'scripts/check-isae-sa12-velocity.py')
    assert velocity['compute_script_sha256']==p['script_sha256']
    assert max(velocity['maximum_velocity_difference'],velocity['maximum_induced_boundary_normal_speed'])<2e-8
    sample=json.loads((D/'isae-sa12-wasm-native.json').read_text());assert sample['provenance']==p and len(sample['rows'])==33
    assert sample['script_sha256']==sha(ROOT/'scripts/prepare-isae-sa12-wasm.py')
    for r in sample['rows']:assert r==rows[sa12.key(r['specification'])]
    wasm=json.loads((D/'isae-sa12-wasm.json').read_text());browser=json.loads((D/'isae-sa12-browser.json').read_text())
    assert wasm['status']==browser['status']=='PASS' and browser['offline']
    assert wasm['modules']==browser['modules']==modules
    assert wasm['sources_sha256']==browser['sources_sha256']==p['source_report_sha256']
    assert wasm['native_sample_sha256']==browser['native_sample_sha256']==sha(D/'isae-sa12-wasm-native.json')
    assert wasm['script_sha256']==sha(ROOT/'scripts/test-isae-sa12-wasm.mjs')
    assert browser['test_sha256']==sha(ROOT/'tests/browser/isae-sa12.spec.js')
    assert browser['web_main_sha256']==sha(ROOT/'web/main.js')
    assert len(wasm['rows'])==33 and len(browser['rows'])==17
    assert all(r['maximum_coefficient_difference']<2e-7 for r in wasm['rows']+browser['rows'])
    assert sum(r['result']['CDi'] is None for r in browser['rows'])==6
    evidence=['isae-sa12-sources.json','isae-sa12.json','isae-sa12-comparison.json','isae-sa12-velocity.json',
        'isae-sa12-wasm-native.json','isae-sa12-wasm.json','isae-sa12-browser.json']
    out=dict(status='PASS_NUMERICAL_AND_PROVENANCE_CHECKS_NOT_COMPLETE_PHYSICAL_VALIDATION',
        script_sha256=sha(Path(__file__)),modules=modules,native_requests=len(rows),source_files=28,source_setups=setups,
        measured_points=dict(measured_counts),maximum_errors=errors,maximum_statistic_error=float(statistic_error),
        independent_velocity_checks=24,independent_boundary_checks=24,wasm_states=33,offline_browser_states=17,
        maximum_wasm_coefficient_difference=max(r['maximum_coefficient_difference'] for r in wasm['rows']),
        maximum_browser_coefficient_difference=max(r['maximum_coefficient_difference'] for r in browser['rows']),
        evidence_sha256={f:sha(D/f) for f in evidence},
        limitations=sources['limitations'])
    (D/'isae-sa12-checks.json').write_text(json.dumps(out,indent=2)+'\n')
    print(out['status'],json.dumps(dict(states=len(rows),measured=dict(measured_counts),errors=errors)),flush=True)


if __name__=='__main__':main()
