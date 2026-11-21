"""Pinned, explicitly reconstructed SA-14 iw=4 native comparison protocol."""
from pathlib import Path
import hashlib
import importlib.util
import json
import os
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
from openswing.aero import AnalysisError
from isae_sa14_reference import sha,REVISION

D=ROOT/'docs/validation'
spec=importlib.util.spec_from_file_location('sa14_pilot',ROOT/'scripts/verify-isae-sa14.py')
pilot=importlib.util.module_from_spec(spec);spec.loader.exec_module(pilot)


def requests():
    rows=[]
    for n in [25,50,100]:
        for alpha in [4.7,8.8,12.9]:
            for pg in ['primary_0.19','speed' if alpha==4.7 else 'zero']:
                for case in ['iw0','wing_frame','body_frame']:
                    rows.append(dict(case=case,panels=n,alpha_w=alpha,
                        alpha=alpha-4. if case=='body_frame' else alpha,pg=pg))
    assert len(rows)==54
    return rows


def main():
    sources=json.loads((D/'isae-sa14-sources.json').read_text())
    incidence=json.loads((D/'isae-sa14-incidence-sources.json').read_text())
    previous=json.loads((D/'isae-sa14-pilot.json').read_text())
    modules={p.name:sha(p) for p in (ROOT/'openswing').glob('*.py')}
    assert modules==sources['modules']==incidence['modules']==previous['provenance']['modules']
    assert incidence['script_sha256']==sha(ROOT/'scripts/isae_sa14_incidence.py')
    provenance=dict(revision=REVISION,modules=modules,script_sha256=sha(Path(__file__)),
        compute_script_sha256=sha(ROOT/'scripts/verify-isae-sa14.py'),
        source_report_sha256=sha(D/'isae-sa14-sources.json'),
        incidence_source_sha256=sha(D/'isae-sa14-incidence-sources.json'),
        pilot_report_sha256=sha(D/'isae-sa14-pilot.json'))
    identity=hashlib.sha256(json.dumps(provenance,sort_keys=True).encode()).hexdigest()
    folder=ROOT/'.reference/isae-sa14-incidence'/identity;folder.mkdir(parents=True,exist_ok=True)
    pin=folder/'identity.json'
    if pin.exists():assert json.loads(pin.read_text())==provenance
    else:pin.write_text(json.dumps(provenance,indent=2)+'\n')
    models={k:v['source'] for k,v in incidence['variants'].items()}
    models['iw0']=next(m['source'] for m in sources['models'] if m['name']=='wing_body')
    rows=[]
    for q in requests():
        path=folder/(hashlib.sha256(json.dumps(q,sort_keys=True).encode()).hexdigest()+'.json')
        if path.exists():
            row=json.loads(path.read_text());assert row['specification']==q
        else:
            start=time.monotonic()
            reuse=next((r for r in previous['rows'] if q['case']=='iw0' and
                r['specification']==dict(case='wing_body',panels=q['panels'],alpha=q['alpha'],pg=q['pg'])),None)
            if reuse is not None:
                assert reuse['status']=='computed' and sha(ROOT/reuse['cache_path'])==reuse['cache_sha256']
                row=dict(specification=q,status='computed',result=reuse['result'],
                    reused_cache_path=reuse['cache_path'],reused_cache_sha256=reuse['cache_sha256'],
                    original_seconds=reuse['seconds'])
            else:
                try:row=dict(specification=q,status='computed',result=pilot.compute(models[q['case']],q,sources))
                except (AnalysisError,ValueError) as exc:
                    row=dict(specification=q,status='rejected',error=str(exc),details=getattr(exc,'details',None))
            row['seconds']=time.monotonic()-start
            tmp=path.with_suffix(f'.{os.getpid()}.tmp');tmp.write_text(json.dumps(row,indent=2)+'\n');tmp.replace(path)
        row.update(cache_path=path.relative_to(ROOT).as_posix(),cache_sha256=sha(path));rows.append(row)
        progress=dict(completed=len(rows),total=54,last=q,status=row['status'])
        tmp=folder/'progress.tmp';tmp.write_text(json.dumps(progress,indent=2)+'\n');tmp.replace(folder/'progress.json')
        print(len(rows),'/54',q,row['status'],'reused' if 'reused_cache_path' in row else round(row['seconds'],3),flush=True)
    assert modules=={p.name:sha(p) for p in (ROOT/'openswing').glob('*.py')}
    out=dict(status='NATIVE_INCIDENCE_COMPUTATIONS_COMPLETE_COMPARISONS_PENDING',provenance=provenance,
        setup=incidence['setup'],rows=rows,computed=sum(r['status']=='computed' for r in rows),
        rejected=sum(r['status']=='rejected' for r in rows),reused=sum('reused_cache_path' in r for r in rows),
        protocol=['Three meshes25/50/100, wing angles4.7/8.8/12.9, primary Mach0.19 and archive mixed PG.',
            'For each condition compare unchanged iw0 and explicit iw4 geometry in wing-fixed and body-fixed frames.',
            'The body-fixed condition angle is alpha_w-4deg. No source properties are fitted.',
            'Original pilot states may be reused only with matching modules, source, condition and immutable cache hashes.',
            'This supplements the known swept-force mesh limitation; it does not claim mesh convergence.'],
        limitations=incidence['limitations'])
    (D/'isae-sa14-incidence.json').write_text(json.dumps(out,indent=2)+'\n')
    print('COMPLETE',out['computed'],out['rejected'],'reused',out['reused'],flush=True)


if __name__=='__main__':main()
