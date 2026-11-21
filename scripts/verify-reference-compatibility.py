"""Compare isolated old/new parsers on published inputs and shipped examples.

Baseline copies and the source manifests are explicit. Legacy normalization is
used only as an independent counterfactual reference; candidate imports and
roundtrips always use the unmodified input bytes.
"""
from pathlib import Path
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]


def sha(data):
    return hashlib.sha256(data).hexdigest()


def normalized_zero_reference(text):
    lines=text.splitlines(keepends=True)
    active=False
    matches=[]
    for i,line in enumerate(lines):
        body=re.split(r'[!#%]',line,1)[0].strip()
        if body.lower()=='reference':
            active=True
        elif body.lower()=='end':
            active=False
        elif active and body and body[0] not in '*+':
            tokens=body.replace(',',' ').split()
            if len(tokens)==6:
                assert all(float(t)==0 for t in tokens[3:])
                matches.append(i)
                # Actual pinned fixtures have no scaling records in this block.
                # An independent modern record retains exactly Sref,Cref,Bref;
                # the documented omitted moment/acceleration/velocity rows are 0.
                lines[i]=' '.join(tokens[:3])+'\n'
    assert len(matches)<=1
    return ''.join(lines),bool(matches)


def worker(kernel):
    sys.path.insert(0,str(kernel))
    from openswing.asw import parse_asw
    from openswing.asw_edit import model_data
    manifest=json.loads((ROOT/'.reference/isae-validation/manifest.json').read_text())
    cache=ROOT/'.reference/isae-validation'/manifest['revision']
    paths=[('isae/'+name,cache/name,record['sha256']) for name,record in manifest['files'].items() if name.endswith('.asw')]
    paths += [('examples/'+p.name,p,sha(p.read_bytes())) for p in sorted((ROOT/'examples').glob('*.asw'))]
    records=[]
    def parse(text):
        try:
            model=parse_asw(text)
        except ValueError as exc:
            return dict(status='rejected',error=type(exc).__name__+': '+str(exc))
        assert model.dumps()==text
        data=model_data(model)
        digest=sha(json.dumps(data,sort_keys=True).encode())
        canonical=parse_asw(model.dumps(canonical=True))
        assert model_data(canonical)==data
        return dict(status='parsed',model_sha256=digest,reference=model.reference.tolist(),diagnostics=model.diagnostics)
    for name,path,digest in paths:
        data=path.read_bytes();assert sha(data)==digest
        text=data.decode('utf-8-sig')
        modern,changed=normalized_zero_reference(text)
        records.append(dict(path=name,source_sha256=digest,literal=parse(text),
                            zero_reference_shorthand=changed,modern_equivalent=parse(modern) if changed else None))
    pins={p.name:sha(p.read_bytes()) for p in sorted((kernel/'openswing').glob('*.py'))}
    return dict(kernel_modules=pins,records=records)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--baseline-kernel',type=Path)
    parser.add_argument('--candidate-kernel',type=Path,default=ROOT)
    parser.add_argument('--worker',type=Path)
    parser.add_argument('--output',type=Path,default=ROOT/'docs/validation/reference-compatibility.json')
    args=parser.parse_args()
    if args.worker:
        print(json.dumps(worker(args.worker.resolve())));return
    assert args.baseline_kernel is not None
    snapshots=[]
    for kernel in [args.baseline_kernel,args.candidate_kernel]:
        process=subprocess.run([sys.executable,str(Path(__file__).resolve()),'--worker',str(kernel.resolve())],
                               check=True,text=True,capture_output=True,env={**os.environ,'OPENBLAS_NUM_THREADS':'1','OMP_NUM_THREADS':'1'})
        snapshots.append(json.loads(process.stdout))
    old,new=snapshots
    assert len(old['records'])==len(new['records'])
    changed={n for n in old['kernel_modules'] if old['kernel_modules'][n]!=new['kernel_modules'].get(n)}
    assert changed=={'asw.py'} and set(old['kernel_modules'])==set(new['kernel_modules'])
    preserved=newly_parsed=normalized=0
    differences=[]
    for before,after in zip(old['records'],new['records']):
        assert before['path']==after['path'] and before['source_sha256']==after['source_sha256']
        if before['zero_reference_shorthand']:
            normalized+=1
            assert after['literal']==before['modern_equivalent'],after['path']
            if after['literal']['status']=='parsed':newly_parsed+=1
            differences.append(dict(path=after['path'],before=before['literal'],after=after['literal']))
        else:
            assert before==after,after['path']
            if before['literal']['status']=='parsed':preserved+=1
    report=dict(status='PASS_PARSER_EQUIVALENCE_NOT_PHYSICAL_VALIDATION',
        baseline_modules=old['kernel_modules'],candidate_modules=new['kernel_modules'],
        script_sha256=sha(Path(__file__).read_bytes()),changed_modules=sorted(changed),
        input_count=len(new['records']),unchanged_previously_accepted=preserved,zero_reference_fixtures=normalized,newly_parsed=newly_parsed,
        verified_invariants=['Every previously accepted literal input has identical complete model-data hash and diagnostics.',
            'Every current zero-reference import equals the isolated old parser on the explicit documented three-column equivalent.',
            'All accepted inputs preserve original text and canonical serialization preserves complete model data.',
            'All other rejection outcomes are unchanged. Only asw.py differs; the other96kernelmodules are identical.'],
        differences=differences,baseline_snapshot=old,candidate_snapshot=new,
        limitations=['No nonzero six-column reference map is inferred.',
            'Positive reference dimensions remain required; no automatic reference-area choice is invented.',
            'Equivalent parsed state and unchanged physics establish source-transition continuity for those inputs; they do not validate experimental agreement.'])
    args.output.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:report[k] for k in ['status','input_count','unchanged_previously_accepted','zero_reference_fixtures','newly_parsed']},indent=2))


if __name__=='__main__':main()
