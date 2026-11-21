"""Select ground-pose and Fourier states using the locked native SA-12 cache."""
from pathlib import Path
import hashlib, importlib.util, json, sys

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
spec=importlib.util.spec_from_file_location('sa12',ROOT/'scripts/verify-isae-sa12.py')
sa12=importlib.util.module_from_spec(spec);spec.loader.exec_module(sa12)


def main():
    sources=json.loads((ROOT/'docs/validation/isae-sa12-sources.json').read_text())
    modules={p.name:sa12.sha(p) for p in (ROOT/'openswing').glob('*.py')}
    provenance=dict(revision=sa12.REVISION,modules=modules,script_sha256=sa12.sha(ROOT/'scripts/verify-isae-sa12.py'),
        source_report_sha256=sa12.sha(ROOT/'docs/validation/isae-sa12-sources.json'),
        reference_script_sha256=sa12.sha(ROOT/'scripts/isae_sa12_reference.py'))
    assert sources['modules']==modules and sources['script_sha256']==provenance['reference_script_sha256']
    folder=ROOT/'.reference/isae-sa12-runs'/hashlib.sha256(json.dumps(provenance,sort_keys=True).encode()).hexdigest()
    assert json.loads((folder/'identity.json').read_text())==provenance
    rows=[]
    for case in sources['models']:
        for label in sa12.HEIGHTS:
            for alpha in ([0.,5.,10.] if case['name']=='no_flap' else [5.,10.]):
                for pose in (['level_freestream'] if alpha==0 else ['level_freestream','zero_attitude']):
                    request=sa12.specification(case,label,100,alpha,pose=pose)
                    rows.append(sa12.cached_request((str(folder),case['source'],request)))
            request=sa12.specification(case,label,100,10.,modes=19)
            rows.append(sa12.cached_request((str(folder),case['source'],request)))
            print(case['name'],label,len(rows),'ready',flush=True)
    assert len(rows)==33 and all(r['status']=='computed' for r in rows)
    assert modules=={p.name:sa12.sha(p) for p in (ROOT/'openswing').glob('*.py')}
    out=dict(status='NATIVE_REPLAY_SAMPLE_READY',provenance=provenance,rows=rows,
        script_sha256=sa12.sha(Path(__file__)),
        scope='27 pointwise pose/zero-incidence states plus six Fourier19 states, all at N100. Runtime verification only.')
    (ROOT/'docs/validation/isae-sa12-wasm-native.json').write_text(json.dumps(out,indent=2)+'\n')


if __name__=='__main__':main()
