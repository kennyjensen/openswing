"""Audit the pilot's source identities, force accounting and runtime evidence."""
from pathlib import Path
import hashlib,json,sys
import numpy as np
ROOT=Path(__file__).resolve().parents[1];D=ROOT/'docs/validation'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    names=['sources','pilot','pilot-comparison','measurements','volume','wasm','browser']
    data={n:json.loads((D/f'isae-sa14-{n}.json').read_text()) for n in names}
    sources=data['sources'];native=data['pilot'];p=native['provenance'];comparison=data['pilot-comparison']
    modules={f.name:sha(f) for f in (ROOT/'openswing').glob('*.py')}
    assert p['modules']==sources['modules']==data['volume']['modules']==data['wasm']['modules']==data['browser']['modules']==modules
    assert p['source_report_sha256']==data['volume']['source_sha256']==data['measurements']['source_sha256']==sha(D/'isae-sa14-sources.json')
    for name,script in [('sources','isae_sa14_reference.py'),('pilot-comparison','summarize-isae-sa14-pilot.py'),
                        ('measurements','check-isae-sa14-measurements.py'),('volume','check-isae-sa14-volume.py'),('wasm','test-isae-sa14-wasm.mjs')]:
        assert data[name]['script_sha256']==sha(ROOT/'scripts'/script)
    assert p['script_sha256']==sha(ROOT/'scripts/verify-isae-sa14.py')
    assert p['reference_script_sha256']==sources['script_sha256']
    assert data['browser']['test_sha256']==sha(ROOT/'tests/browser/isae-sa14.spec.js')
    assert data['browser']['web_main_sha256']==sha(ROOT/'web/main.js')
    assert comparison['native_sha256']==data['wasm']['native_sha256']==data['browser']['native_sha256']==sha(D/'isae-sa14-pilot.json')
    assert comparison['measurement_audit_sha256']==sha(D/'isae-sa14-measurements.json')
    assert comparison['volume_sha256']==sha(D/'isae-sa14-volume.json')
    cache=ROOT/'.reference/isae-validation'/sources['revision']
    assert len(sources['files'])==50
    for name,pin in sources['files'].items():
        path=cache/name;assert path.stat().st_size==pin['bytes'] and sha(path)==pin['sha256']
    assert sha(ROOT/sources['primary']['path'])==sources['primary']['sha256']
    for entry in sources['experimental']:
        assert all(sha(cache/path)==entry['source_sha256'] for path in entry['identical_copies'])
    assert len(sources['polars'])==3 and all(len(r['rows'])==60 for r in sources['polars'])
    assert all(r['printed_pg_mach']==[.2058,0.,0.] for r in sources['distribution_exports'])
    assert data['measurements']['instrumented_points']==42 and data['measurements']['drawn_tip_curve_endpoints']==6
    assert len(native['rows'])==native['computed']==50 and native['rejected']==0
    seen=set();accounting=[]
    for row in native['rows']:
        assert row['status']=='computed' and sha(ROOT/row['cache_path'])==row['cache_sha256']
        q=row['specification'];key=json.dumps(q,sort_keys=True);assert key not in seen;seen.add(key)
        result=row['result'];model=next(m for m in sources['models'] if m['name']==q['case'])
        expected_mach={'zero':0.,'speed':70/model['constants'][2],'primary_0.19':.19}[q['pg']]
        assert result['actual_mach']==expected_mach and result['residual']<1e-8
        assert result['maximum_section_normal_mach']<1.
        strips=result['profiles']+result['body_strips'];reference=np.array(model['reference'][1])
        force=np.sum([r['force'] for r in strips],axis=0)
        moment=np.sum([np.array(r['moment'])+np.cross(np.array(r['position'])-reference,r['force']) for r in strips],axis=0)
        ferror=float(np.max(abs(force-result['force'])));merror=float(np.max(abs(moment-result['moment'])))
        assert ferror<2e-7 and merror<2e-7,(q,ferror,merror)
        norm=result['primary_normalization']
        assert abs(norm['CL_total']-norm['CL_full_wing']-norm['CL_body'])<1e-12
        assert abs(norm['CL_total']-result['coefficients']['CL']*result['reference_area']/norm['area'])<1e-12
        assert norm['area']==sources['primary']['wing']['area_m2']
        assert norm['mean_geometric_chord']==norm['area']/norm['span']
        accounting.append(dict(specification=q,maximum_force_error=ferror,maximum_moment_error=merror))
    for row in comparison['local_comparisons']:
        points=row['points'];instrumented=[v for v in points if v['classification']=='instrumented_station']
        good=[v for v in instrumented if v['predicted'] is not None]
        errors=np.array([v['predicted']-v['observed'] for v in good])
        assert len(instrumented)==row['requested'] and len(good)==row['available']
        assert abs(np.sqrt(np.mean(errors**2))-row['rmse'])<1e-14
        assert sum(v['classification']=='drawn_tip_curve_endpoint' for v in points)==1
    assert len(data['volume']['rows'])==12
    for r in data['volume']['rows']:
        assert len(r['positions'])==6 and r['adaptive_error_bound']<1e-8
        if r['panels']==100:assert r['maximum_component_difference']<2e-5
        if r['case']=='infinite_body':
            speed=float(np.max(abs(np.array(r['independent_body_velocity']))))
            assert (speed==0.) if r['alpha']==0 else (speed>0.)
    assert len(data['wasm']['rows'])==50 and len(data['browser']['rows'])==15
    assert data['browser']['offline'] and data['browser']['wasm_sha256']==sha(D/'isae-sa14-wasm.json')
    assert [r['case'] for r in data['browser']['display'] if r['status']=='matching_rejection']==['body_only']
    assert all(r['matches_native'] for r in data['wasm']['display'])
    out=dict(status='PASS_PILOT_EVIDENCE_AUDIT_FULL_VALIDATION_INCOMPLETE',modules=modules,
        script_sha256=sha(Path(__file__)),evidence_sha256={f'isae-sa14-{n}.json':sha(D/f'isae-sa14-{n}.json') for n in names},
        native_computations=50,wasm_replays=50,offline_browser_solves=15,source_files=50,
        instrumented_local_points=42,retained_drawn_curve_endpoints=6,force_and_moment_accounting=accounting,
        known_display_failure='body_only: tiny negative closed-tail endpoint',
        limitations=['The full family study is pending; numerical/runtime checks do not certify experimental agreement.',
            'Tip-local-flow growth, full polars and exact-angle global measurements, iw4 source mapping and physical setup, and aerodynamic model limitations remain unresolved.'])
    (D/'isae-sa14-checks.json').write_text(json.dumps(out,indent=2)+'\n');print(out['status'],flush=True)


if __name__=='__main__':main()
