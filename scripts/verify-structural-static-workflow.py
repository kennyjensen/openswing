"""Replay all ST-3 static states with direct signed weights through the JSON API."""
from pathlib import Path
import hashlib,json,re,sys,time
import numpy as np

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from openswing.asw import parse_asw
from openswing.bridge import dispatch

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def pin_modules():return {p.name:sha(p) for p in sorted((ROOT/'openswing').glob('*.py'))}

def literal_loads(text,force,couple):
    rows=[]
    for i,row in enumerate(parse_asw(text).records['weight']):
        rows.append([*row[:5],force/2+(1 if i==0 else -1)*couple/.14,*row[6:]])
    block='Weight\n'+'\n'.join(' '.join(format(float(v),'.17g') for v in row) for row in rows)+'\nEnd'
    source,count=re.subn(r'(?ims)^Weight\s*\n.*?^end\s*$',block,text,count=1);assert count==1
    return source

def compare(old,new):
    differences={}
    for key in ['position','rotation']:
        a=np.array([n[key] for n in old['nodes']]);b=np.array([n[key] for n in new['nodes']])
        assert a.shape==b.shape
        differences[key]=float(np.max(abs(a-b)));assert differences[key]<2e-8,(key,differences[key])
    for key in ['applied_force','applied_moment','support_force','support_moment']:
        a=np.array(old[key]);b=np.array(new[key]);differences[key]=float(np.max(abs(a-b)))
        assert differences[key]<2e-8,(key,differences[key])
    assert new['residual']<1e-8
    return differences

def main():
    dest=ROOT/'docs/validation';cache=ROOT/'.reference/structural-static-workflow';cache.mkdir(exist_ok=True)
    baseline=json.loads((dest/'isae-st3-static.json').read_text());modules=pin_modules();script=sha(Path(__file__))
    sources={name:(ROOT/f'examples/isae-st3-static-{name}.asw').read_text() for name in ['0_3_90','p15_0','m15_0']}
    for name,text in sources.items():
        path=f'3 - Structure/CASE - ST3 Low aspect ratio/Static_Deflection_analysis/[{name}].asw'
        assert hashlib.sha256(text.encode()).hexdigest()==baseline['sources'][path]['sha256']
    requests=[]
    for row in baseline['runs']:
        spec=row['identity']['specification'];text=literal_loads(sources[spec['name']],spec['force_N'],spec['couple_Nm'])
        requests.append(dict(name=spec['name'],kind='parameterized_signed_weights',source=text,panels=spec['panels'],baseline_key=row['key'],expected=row['result']['result']))
    for item in baseline['archived_final_weights']:
        row=next(r for r in baseline['runs'] if r['key']==item['native_key'])
        requests.append(dict(name=item['name'],kind='literal_archived_file',source=sources[item['name']],panels=64,baseline_key=row['key'],expected=row['result']['result']))
    runs=[];examples=[]
    for i,item in enumerate(requests):
        request=dict(action='solve',mode='structural',source=item['source'],panels=item['panels'])
        identity=dict(request=request,modules=modules,script_sha256=script,baseline_key=item['baseline_key'])
        key=hashlib.sha256(json.dumps(identity,sort_keys=True).encode()).hexdigest();path=cache/(key+'.json')
        if path.exists():record=json.loads(path.read_text());assert record['identity']==identity
        else:
            start=time.perf_counter();result=dispatch(request)
            record=dict(identity=identity,seconds=time.perf_counter()-start,result=result)
            path.write_text(json.dumps(record,indent=2)+'\n')
        result=record['result'];differences=compare(item['expected'],result)
        negative=any(r[5]<0 for r in parse_asw(item['source']).records['weight'])
        assert (result['mass_properties'].get('physical',True) is False)==negative
        assert ('launch' not in result['equilibrium_state'])==negative
        row=dict(name=item['name'],kind=item['kind'],panels=item['panels'],baseline_key=item['baseline_key'],cache_key=key,
                 cache_sha256=sha(path),differences=differences,residual=result['residual'],seconds=record['seconds'])
        runs.append(row)
        if item['kind']=='literal_archived_file':examples.append(dict(**row,request=request,result=result))
        print(i+1,len(requests),item['name'],item['kind'],item['panels'],'PASS',flush=True)
    assert modules==pin_modules()
    report=dict(status='PASS_DIRECT_SIGNED_STATIC_WORKFLOW',modules=modules,script_sha256=script,
                baseline_sha256=sha(dest/'isae-st3-static.json'),baseline_modules=baseline['modules'],runs=runs,literal_cases=examples,
                maximum_differences={key:max(r['differences'][key] for r in runs) for key in runs[0]['differences']},
                full_suite_validated=False,goal_complete=False)
    (dest/'structural-static-workflow.json').write_text(json.dumps(report,indent=2)+'\n')
    print('PASS',len(runs),report['maximum_differences'],flush=True)

if __name__=='__main__':main()
