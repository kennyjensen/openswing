"""Literal ST-5 distributed bench loads and unchanged ST-3 point-load controls."""
from pathlib import Path
import hashlib,importlib.util,json,sys,time
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from openswing.asw import parse_asw
from openswing.network import StaticNetwork
from openswing.bridge import dispatch
spec=importlib.util.spec_from_file_location('st5',ROOT/'scripts/verify-isae-st5.py')
st5=importlib.util.module_from_spec(spec);spec.loader.exec_module(st5)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
pins=lambda:{p.name:sha(p) for p in sorted((ROOT/'openswing').glob('*.py'))}


def main():
    dest=ROOT/'docs/validation';cache=ROOT/'.reference/distributed-static';cache.mkdir(exist_ok=True)
    baseline=json.loads((dest/'isae-st5.json').read_text());modules=pins();script=sha(Path(__file__))
    assert baseline['provenance']['script_sha256']==sha(Path(spec.origin))
    sources=baseline['provenance']['sources']
    for name,row in sources.items():assert sha(st5.CACHE/name)==row['sha256']
    literal=[]
    for path in sorted(st5.FOLDER.rglob('*.asw')):
        row=dict(path=path.relative_to(st5.CACHE).as_posix(),sha256=sha(path))
        try:
            model=parse_asw(path.read_text());row['import']='parsed'
            net=StaticNetwork(model,8,None,None,[],allow_signed_point_weights=True,allow_signed_distributed_weights=True)
            row.update(status='constructed_not_solved',signed_distributed_weights=net.inertia_model.signed_distributed_weights,
                       custom_link_validation_required='Link_Joint' in path.parts)
        except ValueError as exc:row.update(status='rejected',error=str(exc))
        literal.append(row)
    cases=[];differences=[]
    for case in baseline['cases']:
        model_path=st5.CACHE/case['input_path'];source=model_path.read_text()
        copied={k:case[k] for k in ['name','input_path','archived','experiment_file','experiment']};copied['runs']=[]
        for old in case['runs']:
            panels=old['specification']['panels']
            request=dict(action='solve',mode='structural',source=source,panels=panels)
            identity=dict(request=request,modules=modules,script_sha256=script)
            key=hashlib.sha256(json.dumps(identity,sort_keys=True).encode()).hexdigest();path=cache/(key+'.json')
            if path.exists():record=json.loads(path.read_text());assert record['identity']==identity
            else:
                start=time.monotonic()
                try:record=dict(identity=identity,status='computed',result=dispatch(request))
                except ValueError as exc:record=dict(identity=identity,status='rejected',error=str(exc))
                record['seconds']=time.monotonic()-start;path.write_text(json.dumps(record,indent=2)+'\n')
            row={k:v for k,v in record.items() if k!='identity'}
            row.update(specification=dict(case=case['name'],panels=panels,method='literal_signed_distributed'),cache_key=key,cache_sha256=sha(path))
            if row['status']=='computed':
                result=row['result'];assert result['residual']<1e-8
                assert np.max(abs(np.array(result['force_balance'])))<1e-7
                assert np.max(abs(np.array(result['moment_balance'])))<1e-7
                assert result['mass_properties']['physical'] is False and 'launch' not in result['equilibrium_state']
                assert old['status']=='computed'
                comparison={}
                for collection,keys in [(None,['applied_force','applied_moment','support_force','support_moment']),('nodes',['position','rotation']),('elements',['force','moment'])]:
                    for field in keys:
                        a=np.array(old['result'][field] if collection is None else [r[field] for r in old['result'][collection]])
                        b=np.array(result[field] if collection is None else [r[field] for r in result[collection]])
                        assert a.shape==b.shape
                        comparison[(collection+'.' if collection else '')+field]=float(np.max(abs(a-b)))
                differences.append(dict(case=case['name'],panels=panels,**comparison))
                row['reconstruction_difference']=comparison
            else:assert old['status']=='rejected' and 'Attachment station is outside' in row['error']
            copied['runs'].append(row);print(case['name'],panels,row['status'],round(row['seconds'],3),flush=True)
        cases.append(copied)
    controls=[]
    point_baseline=json.loads((dest/'structural-static-workflow.json').read_text())
    for case in point_baseline['literal_cases']:
        result=dispatch(case['request']);old=case['result'];diff={}
        for field in ['position','rotation']:
            diff[field]=float(np.max(abs(np.array([r[field] for r in result['nodes']])-np.array([r[field] for r in old['nodes']]))))
            assert diff[field]<2e-8
        controls.append(dict(name=case['name'],differences=diff,result=result,request=case['request']))
    assert modules==pins()
    report=dict(status='LITERAL_DISTRIBUTED_STATIC_COMPARISON_NOT_EXPERIMENTAL_PASS',full_suite_validated=False,
                provenance=dict(modules=modules,script_sha256=script,reference_decoder_sha256=sha(Path(spec.origin)),revision=st5.REVISION,sources=sources),
                baseline_sha256=sha(dest/'isae-st5.json'),point_baseline_sha256=sha(dest/'structural-static-workflow.json'),literal_audit=literal,cases=cases,
                reconstruction_differences=differences,point_load_controls=controls,
                settings=dict(meshes=[16,32,64,128,256],gravity='File gravity along body -z; zero motion; no airflow',loads='Unmodified mg/Dmg and independent rotating centroids; existing material-midpoint integration'),
                limitations=baseline['limitations'][1:]+['Default physical mass validation still rejects signed mass; centroidal inertias remain nonnegative.'])
    (dest/'distributed-static.json').write_text(json.dumps(report,indent=2)+'\n')
    print('COMPLETE',len(differences),'literal solves;',len(literal),'literal setups;',len(controls),'point-load controls',flush=True)

if __name__=='__main__':main()
