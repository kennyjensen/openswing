"""Audit SA-13 provenance, normalization, conservation and runtime outcomes."""
from pathlib import Path
import hashlib
import json
import numpy as np
from numpy.polynomial import Polynomial
from scipy.interpolate import CubicSpline

ROOT=Path(__file__).resolve().parents[1]
D=ROOT/'docs/validation'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    names=['sources','comparison','velocity','wasm','browser']
    data={name:json.loads((D/f'isae-sa13-{name}.json').read_text()) for name in names}
    native=json.loads((D/'isae-sa13.json').read_text())
    p=native['provenance'];sources=data['sources'];comparison=data['comparison']
    modules={f.name:sha(f) for f in (ROOT/'openswing').glob('*.py')}
    assert p['modules']==sources['modules']==modules
    assert p['source_report_sha256']==sha(D/'isae-sa13-sources.json')
    assert p['script_sha256']==sha(ROOT/'scripts/verify-isae-sa13.py')
    assert p['reference_script_sha256']==sha(ROOT/'scripts/isae_sa13_reference.py')
    assert comparison['script_sha256']==sha(ROOT/'scripts/summarize-isae-sa13.py')
    for name in ['comparison','velocity','wasm','browser']:
        assert data[name]['native_sha256']==sha(D/'isae-sa13.json')
    assert data['velocity']['script_sha256']==sha(ROOT/'scripts/check-isae-sa13-velocity.py')
    assert data['wasm']['script_sha256']==sha(ROOT/'scripts/test-isae-sa13-wasm.mjs')
    assert data['browser']['test_sha256']==sha(ROOT/'tests/browser/isae-sa13.spec.js')
    assert data['browser']['modules']==data['wasm']['modules']==modules
    assert data['browser']['wasm_sha256']==sha(D/'isae-sa13-wasm.json')
    assert data['browser']['offline'] and not data['browser']['candidate_only']
    assert len(data['browser']['rows'])==8 and len(data['wasm']['rows'])==38
    assert {r['case'] for r in data['browser']['display'] if r['status']=='matching_rejection'}=={'r33','r101'}
    assert data['wasm']['status']=='NUMERICAL_REPLAY_PASS_DISPLAY_DIVERGENCE'
    candidate={name:json.loads((D/f'isae-sa13-endpoint-candidate-{name}.json').read_text())
               for name in ['native','wasm','browser']}
    cn,cw,cb=(candidate[name] for name in ['native','wasm','browser'])
    assert cn['status']=='PASS_ISOLATED_CANDIDATE_NOT_APPLIED'
    assert (cn['literal_models'],cn['parsed'],cn['rejected'],cn['distributions_checked'])==(279,113,166,4767)
    assert cn['derivatives_orders_1_to_3_bitwise_unchanged'] and cn['maximum_scaled_change']<2e-14
    assert cn['pins']['baseline']==modules['asw.py']
    assert cn['pins']['candidate']==cw['modules']['asw.py']==cb['modules']['asw.py']
    assert cw['status']=='PASS_ISOLATED_ENDPOINT_CANDIDATE' and cw['candidate_only'] and cb['candidate_only']
    assert len(cw['rows'])==38 and len(cb['rows'])==16 and len(cb['rejections'])==2
    assert cw['native_sha256']==cb['native_sha256']==sha(D/'isae-sa13.json')
    assert all(v==cw['modules'][k]==cb['modules'][k] for k,v in modules.items() if k!='asw.py')
    assert all(r['result']['status']=='constructed' and r['endpoint_radii']==[0.,0.] for r in cw['display'])
    assert all(r['status']=='constructed' for r in cb['display'])
    assert cb['offline'] and cb['test_sha256']==sha(ROOT/'tests/browser/isae-sa13.spec.js')
    for f,pin in comparison['evidence_sha256'].items():assert sha(D/f)==pin
    assert len(sources['cases'])==4
    source_cache=ROOT/'.reference/isae-validation'/p['revision']
    for case in sources['cases']:
        assert sha(source_cache/case['path'])==case['sha256']
        assert sha(ROOT/case['derived_path'])==case['derived_sha256']
        assert (ROOT/case['derived_path']).read_text()==case['derived_source']
    measured_counts={c['name']:sum(all(v is not None for v in row) for row in c['series'][0]['xy']) for c in sources['cases']}
    assert measured_counts==dict(r33=35,r101=16,rs1=24,pressure=22)
    cases={c['name']:c for c in sources['cases']}
    seen=set();local=[]
    for row in native['rows']:
        assert row['status']=='computed' and sha(ROOT/row['cache_path'])==row['cache_sha256']
        q=row['specification'];key=json.dumps(q,sort_keys=True);assert key not in seen;seen.add(key)
        result=row['result'];case=cases[q['case']];length=q['length']
        tab=np.array(case['outline']['normalized_table']);radius=CubicSpline(tab[:,0],length*tab[:,1],bc_type='natural')
        primitives=[];cumulative=[0.]
        for i,h in enumerate(np.diff(radius.x)):
            poly=Polynomial(radius.c[:,i][::-1]);primitive=(poly*poly).integ()
            primitives.append(primitive);cumulative.append(cumulative[-1]+primitive(h)-primitive(0.))
        def integral_at(t):
            index=int(np.clip(np.searchsorted(radius.x,t,side='right')-1,0,len(primitives)-1))
            return cumulative[index]+primitives[index](t-radius.x[index])-primitives[index](0.)
        a=np.deg2rad(q['alpha']);coefficient=100.*np.sin(a)*np.cos(a)
        qs=50.*case['outline']['normalized_diameter']*length**2
        errors=[]
        for strip in result['profiles']:
            t=strip['t'];half=strip['length']/(2*length);lo,hi=t-half,t+half
            area0,area1=np.pi*radius(lo)**2,np.pi*radius(hi)**2
            volume_integral=np.pi*(integral_at(hi)-integral_at(lo))
            force=coefficient*(area1-area0)
            moment=-coefficient*length*((hi-t)*area1-(lo-t)*area0-volume_integral)
            error=dict(t=t,exact_transverse_force=float(force),native_transverse_force=strip['force'][2],
                normalized_force_error=float(abs(force-strip['force'][2])/qs),
                exact_local_pitch_moment=float(moment),native_local_pitch_moment=strip['moment'][1],
                normalized_local_moment_error=float(abs(moment-strip['moment'][1])/qs/length))
            errors.append(error)
            pointwise=np.sin(2*a)*2*np.pi*radius(t)*radius(t,1)/(length*case['outline']['normalized_diameter']*length)
            assert abs(pointwise-strip['independent_pointwise_density'])<1e-12
        assert abs(result['volume']-np.pi*length*cumulative[-1])<1e-13
        if q['panels']==256:
            assert result['normalized_net_force_error']<1e-7 and result['normalized_moment_error']<1e-7
        local.append(dict(specification=q,maximum_normalized_strip_force_error=max(v['normalized_force_error'] for v in errors),
            maximum_normalized_strip_moment_error=max(v['normalized_local_moment_error'] for v in errors),
            exact_integrated_force=float(sum(v['exact_transverse_force'] for v in errors)),
            checks=errors))
    assert len(seen)==native['computed']==38 and native['rejected']==0
    for row in comparison['comparisons']:
        assert len(row['points'])==measured_counts[row['specification']['case']]
        good=[p for p in row['points'] if p['predicted'] is not None]
        errors=np.array([p['predicted']-p['observed'] for p in good])
        assert row['metrics']['available']==len(good)
        assert abs(row['metrics']['rmse']-np.sqrt(np.mean(errors**2)))<1e-14
        if row['specification']['case']=='r33':
            missing=[p for p in row['points'] if p['predicted'] is None]
            assert len(missing)==1 and missing[0]['status']=='outside_reconstructed_hull'
    for row in comparison['physical_scale_checks']:
        for k,v in row.items():
            if k.startswith('maximum_'):assert v<1e-11
    finest=next(r for r in data['velocity']['rows'] if r['specification']['panels']==256)
    assert finest['maximum_velocity_difference']<1e-5 and finest['maximum_Cp_percent_difference']<1e-4
    out=dict(status='PASS_EVIDENCE_AUDIT_WITH_KNOWN_DISPLAY_DEFECT',modules=modules,
        script_sha256=sha(Path(__file__)),native_sha256=sha(D/'isae-sa13.json'),
        evidence_sha256={f'isae-sa13-{name}.json':sha(D/f'isae-sa13-{name}.json') for name in names},
        native_computations=38,wasm_computations=38,offline_browser_computations=8,
        offline_browser_display_rejections=['r33','r101'],finite_measurements=measured_counts,
        isolated_candidate=dict(applied_to_production=False,literal_inputs=279,distribution_checks=4767,
            wasm_computations=38,offline_browser_computations=16,negative_controls=2,
            evidence_sha256={name:sha(D/f'isae-sa13-endpoint-candidate-{name}.json') for name in candidate}),
        exact_strip_integral_checks=local,
        method='Exact transverse force from endpoint area differences, and exact local moment from piecewise polynomial radius-squared integration. Native8-point quadrature errors are recorded on every strip.',
        limitations=['Evidence consistency and numerical checks pass; experimental accuracy remains unresolved.',
                    'Display failures are retained and are not passing product behavior. The endpoint candidate is separate from these pinned production results.',
                    'The4 reconstructed bodies are diagnostics from plotted outlines, not recovered original ASWING inputs.'])
    (D/'isae-sa13-checks.json').write_text(json.dumps(out,indent=2)+'\n')
    print(out['status'],flush=True)
    for row in local:
        if row['specification']['panels']==256:print(row['specification'],row['maximum_normalized_strip_force_error'],row['maximum_normalized_strip_moment_error'],flush=True)


if __name__=='__main__':main()
