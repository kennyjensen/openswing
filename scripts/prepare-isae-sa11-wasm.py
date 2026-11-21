"""Prepare 40 native replay states, reusing the pinned SA-11 cache and locks."""
from pathlib import Path
import hashlib, importlib.util, json, sys

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
spec=importlib.util.spec_from_file_location('sa11',ROOT/'scripts/verify-isae-sa11.py')
sa11=importlib.util.module_from_spec(spec);spec.loader.exec_module(sa11)


def main():
    pilot_path=ROOT/'docs/validation/isae-sa11-pilot.json'
    pilot=json.loads(pilot_path.read_text())
    sources=json.loads((ROOT/'docs/validation/isae-sa11-sources.json').read_text())
    provenance=pilot['provenance'];modules={p.name:sa11.sha(p) for p in (ROOT/'openswing').glob('*.py')}
    assert provenance['modules']==modules
    assert provenance['script_sha256']==sa11.sha(ROOT/'scripts/verify-isae-sa11.py')
    assert provenance['reference_script_sha256']==sa11.sha(ROOT/'scripts/isae_sa11_reference.py')
    assert provenance['source_report_sha256']==sa11.sha(ROOT/'docs/validation/isae-sa11-sources.json')
    folder=ROOT/'.reference/isae-sa11-runs'/hashlib.sha256(json.dumps(provenance,sort_keys=True).encode()).hexdigest()
    assert json.loads((folder/'identity.json').read_text())==provenance
    cases=sa11.case_entries(sources)
    for case in cases:
        rows=next(c['runs'] for c in pilot['cases'] if c['case_id']==case['case_id'])
        for row in rows:assert sa11.sha(ROOT/row['cache_path'])==row['cache_sha256']
        for panels in [50,100]:
            request=sa11.specification(case,panels,240.,0.)
            rows.append(sa11.cached_request((str(folder),case['source'],request)))
        case['runs']=rows
        print(case['case_id'],len(rows),'native replay states ready',flush=True)
    assert sum(len(c['runs']) for c in cases)==40
    assert modules=={p.name:sa11.sha(p) for p in (ROOT/'openswing').glob('*.py')}
    report=dict(status='NATIVE_REPLAY_SAMPLE_READY',provenance=provenance,cases=cases,
        script_sha256=sa11.sha(Path(__file__)),pilot_sha256=sa11.sha(pilot_path),
        scope='All 30 pilot states plus N=50/100, V=240, alpha=0, current influences, speed-based PG for all five models. No claim of a completed full sweep.')
    (ROOT/'docs/validation/isae-sa11-wasm-native.json').write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':main()
