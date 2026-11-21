"""Compare literal zero-area structural inputs with isolated positive-area controls."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()


def positive_area(source):
    lines=source.splitlines(keepends=True);active=False
    for i,line in enumerate(lines):
        body=re.split(r'[!#%]',line,1)[0].strip()
        if body.lower()=='reference':active=True
        elif active and body and body[0] not in '*+':
            if body.lower()=='end' or float(body.split()[0])!=0:return None
            lines[i]=re.sub(r'^(\s*)\S+',r'\g<1>1',line,count=1)
            return ''.join(lines)
    return None


def snapshot(kernel):
    sys.path.insert(0,str(kernel))
    from openswing.asw import parse_asw
    from openswing.asw_edit import model_data
    manifest=json.loads((ROOT/'.reference/isae-validation/manifest.json').read_text())
    cache=ROOT/'.reference/isae-validation'/manifest['revision']
    paths=[('isae/'+name,cache/name,pin['sha256']) for name,pin in manifest['files'].items() if name.endswith('.asw')]
    paths.extend(('examples/'+p.name,p,sha(p)) for p in sorted((ROOT/'examples').glob('*.asw')))
    def parsed(text,reset_area=False):
        try:m=parse_asw(text)
        except ValueError as e:return dict(status='rejected',error=type(e).__name__+': '+str(e))
        assert m.dumps()==text
        assert model_data(parse_asw(m.dumps(canonical=True)))==model_data(m)
        if reset_area:m.reference[0,0]=0
        data=model_data(m)
        return dict(status='parsed',data_sha256=hashlib.sha256(json.dumps(data,sort_keys=True).encode()).hexdigest(),diagnostics=m.diagnostics)
    rows=[]
    for name,path,pin in paths:
        assert sha(path)==pin
        text=path.read_bytes().decode('utf-8-sig');control=positive_area(text)
        rows.append(dict(path=name,sha256=pin,literal=parsed(text),
                         positive_control=None if control is None else parsed(control,True)))
    return dict(modules={p.name:sha(p) for p in sorted((kernel/'openswing').glob('*.py'))},rows=rows)


def main():
    p=argparse.ArgumentParser();p.add_argument('--worker',type=Path);p.add_argument('--work',type=Path);a=p.parse_args()
    if a.worker:print(json.dumps(snapshot(a.worker.resolve())));return
    snapshots=[]
    for side in ['baseline','candidate']:
        result=subprocess.run([sys.executable,__file__,'--worker',str(a.work/side)],capture_output=True,text=True,check=True,
                              env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1'))
        data=json.loads(result.stdout);snapshots.append(data)
        (a.work/(side+'-parse.json')).write_text(json.dumps(data,indent=2)+'\n')
    old,new=snapshots;changed=[];same=0
    assert old['modules'].keys()==new['modules'].keys() and len(old['modules'])==97
    assert {n for n in old['modules'] if old['modules'][n]!=new['modules'][n]}=={'asw.py','aero.py'}
    for before,after in zip(old['rows'],new['rows']):
        assert before['path']==after['path'] and before['sha256']==after['sha256']
        if before['literal']==after['literal']:
            assert before==after;same+=1;continue
        assert before['literal']['status']=='rejected' and 'Reference requires positive' in before['literal']['error']
        assert after['literal']['status']=='parsed' and after['literal']==before['positive_control']==after['positive_control']
        changed.append(after['path'])
    assert len(changed)==64
    out=dict(status='PASS_ZERO_AREA_LITERAL_IMPORT_AND_COMPLETE_MODEL_CONTINUITY',
             baseline_modules=old['modules'],candidate_modules=new['modules'],changed_modules=['aero.py','asw.py'],
             new_literal_imports=64,unchanged_inputs=same,inputs=len(new['rows']),changed_inputs=changed,
             snapshots={side:sha(a.work/(side+'-parse.json')) for side in ['baseline','candidate']},
             script_sha256=sha(__file__),full_physical_validation=False,
             scope='The literal zero area is preserved. All other parsed model data equal the isolated old parser with area=1, after resetting that one unused structural-normalization value. Previously accepted inputs and other rejections are unchanged. No automatic aerodynamic area is inferred.')
    (a.work/'parse-checks.json').write_text(json.dumps(out,indent=2)+'\n')
    print(json.dumps({k:out[k] for k in ['status','new_literal_imports','unchanged_inputs','inputs']},indent=2))


if __name__=='__main__':main()
