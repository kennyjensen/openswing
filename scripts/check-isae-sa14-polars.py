"""Audit exact source rows, force partitions and native/WASM/browser evidence."""
from pathlib import Path
from collections import Counter
import hashlib
import json
import runpy
import numpy as np
ROOT=Path(__file__).resolve().parents[1];D=ROOT/'docs/validation'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    sources=json.loads((D/'isae-sa14-sources.json').read_text())
    native=json.loads((D/'isae-sa14-polars.json').read_text())
    comparison=json.loads((D/'isae-sa14-polars-comparison.json').read_text())
    runner=runpy.run_path(str(ROOT/'scripts/verify-isae-sa14-polars.py'))
    refs=runner['references'](sources);plan=runner['requests'](refs)
    assert refs==native['references'] and len(plan)==len(native['rows'])==2952
    assert Counter(map(runner['key'],plan))==Counter(runner['key'](r['specification']) for r in native['rows'])
    modules={p.name:sha(p) for p in (ROOT/'openswing').glob('*.py')}
    assert modules==native['provenance']['modules']==sources['modules']
    for name,pin in native['provenance']['inputs'].items():assert sha(ROOT/name)==pin,name
    assert comparison['native_sha256']==sha(D/'isae-sa14-polars.json')
    assert comparison['script_sha256']==sha(ROOT/'scripts/summarize-isae-sa14-polars.py')
    for name,pin in sources['files'].items():
        path=ROOT/'.reference/isae-validation'/sources['revision']/name
        assert sha(path)==pin['sha256'],name
    counts=Counter();failures=Counter();max_residual=0.;max_force_error=0.
    for row in native['rows']:
        path=ROOT/row['cache_path'];assert sha(path)==row['cache_sha256'];full=json.loads(path.read_text())
        assert row['specification']==full['specification'] and row['status']==full['status']
        counts[row['status']]+=1
        if row['status']=='rejected':
            assert row['error']==full['error'];failures[(row.get('details') or {}).get('kind','other')]+=1;continue
        r=full['result'];brief={k:v for k,v in r.items() if k!='strips'};assert brief==row['result']
        total=np.sum([s['force'] for s in r['strips']],axis=0)
        err=float(np.max(abs(total-r['force'])));max_force_error=max(max_force_error,err);assert err<2e-7
        for part,select,weight in [('wing',lambda s:s['lifting'],lambda s:1.),('body',lambda s:not s['lifting'],lambda s:1.),('exposed',lambda s:s['lifting'],lambda s:s['exposed_fraction'])]:
            force=sum((np.asarray(s['force'])*weight(s) for s in r['strips'] if select(s)),start=np.zeros(3))
            assert np.max(abs(force-r['force_partitions'][part]))<2e-7
        q=row['specification'];a=np.deg2rad(q['alpha']);lift=np.array([-np.sin(a),0.,np.cos(a)])
        norm=r['primary_normalization'];den=r['dynamic_pressure']*norm['area']
        assert abs(total@lift/den-norm['CL_total'])<1e-10
        for part,obs in [('wing','CL_full_wing'),('body','CL_body'),('exposed','CL_exposed_wing')]:
            assert abs(np.asarray(r['force_partitions'][part])@lift/den-norm[obs])<1e-10
        assert r['residual']<=1e-8 and r['maximum_local_residual']<=1e-8
        max_residual=max(max_residual,r['maximum_local_residual'])
    assert counts=={'computed':native['computed'],'rejected':native['rejected']}
    assert len(comparison['comparisons'])==90 and len(comparison['rejections'])==native['rejected']
    assert sum(len(g['points']) for g in comparison['comparisons'])==2952
    bykey={runner['key'](r['specification']):r for r in native['rows']}
    for group in comparison['comparisons']:
        for point in group['points']:
            ref=next(r for r in refs if r['kind']==point['kind'] and r['case']==point['case'] and r['alpha']==point['alpha'] and r.get('label')==point.get('label'))
            assert all(point[k]==v for k,v in ref.items())
            row=bykey[runner['key'](dict(case=group['case'],panels=group['panels'],alpha=point['alpha'],pg=group['pg'],frozen=group['frozen']))]
            if row['status']=='rejected':assert point['predicted'] is None
            else:
                parent,field=ref['observable'].split('.');assert point['predicted']==row['result'][parent][field]
    runtimes={}
    for name,count,status in [('wasm',78,'PASS_EXTENDED_POLAR_RUNTIME_REPLAY'),('browser',12,'PASS_EXTENDED_POLAR_OFFLINE_BROWSER')]:
        path=D/f'isae-sa14-polars-{name}.json';r=json.loads(path.read_text())
        assert r['status']==status and len(r['rows'])==count and r['modules']==modules
        assert r['native_sha256']==sha(D/'isae-sa14-polars.json')
        assert r['sources_sha256']==sha(D/'isae-sa14-sources.json')
        runtimes[name]=dict(status=r['status'],states=len(r['rows']),outcomes=dict(Counter(p['status'] for p in r['rows'])),sha256=sha(path))
    wasm=json.loads((D/'isae-sa14-polars-wasm.json').read_text());browser=json.loads((D/'isae-sa14-polars-browser.json').read_text())
    assert wasm['script_sha256']==sha(ROOT/'scripts/test-isae-sa14-polars-wasm.mjs')
    assert browser['test_sha256']==sha(ROOT/'tests/browser/isae-sa14-polars.spec.js')
    assert browser['wasm_sha256']==sha(D/'isae-sa14-polars-wasm.json') and browser['offline']
    result=dict(status='PASS_EXTENDED_POLAR_EVIDENCE_AUDIT_PHYSICAL_VALIDATION_INCOMPLETE',modules=modules,
        native_sha256=sha(D/'isae-sa14-polars.json'),comparison_sha256=sha(D/'isae-sa14-polars-comparison.json'),
        script_sha256=sha(Path(__file__)),original_files=50,source_archive_points=180,source_experimental_points=44,
        native_outcomes=dict(counts),rejection_kinds=dict(failures),maximum_local_residual=max_residual,
        maximum_strip_force_sum_error=max_force_error,runtime=runtimes,
        limitations=['This audit checks recorded provenance, equations and runtime agreement. It does not resolve the force-velocity singularity or establish physical accuracy.',
                     'No source-failed state is treated as a converged reference. No OpenSwing rejection is replaced by interpolation or zero.'])
    (D/'isae-sa14-polars-checks.json').write_text(json.dumps(result,indent=2)+'\n');print(result['status'],counts,runtimes,flush=True)


if __name__=='__main__':main()
