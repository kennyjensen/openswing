"""Audit pinned loaded-wing results and computed sign brackets without solving."""
import argparse,hashlib,json,math,runpy
from pathlib import Path


def sha(raw):return hashlib.sha256(raw).hexdigest()


def audit(root,matcher):
    match=runpy.run_path(str(matcher))['match']
    runs={};all_cases={};max_base=max_pencil=0.
    specs=[('run-01','source'),('verification-01','source'),('main73-run-01','main73')]
    specs += [(f'boundary75-n{n}-run-01','main73') for n in (8,16,32)]
    for name,source in specs:
        directory=root/name;m=json.loads((directory/'run.json').read_text())
        assert m['status']=='computed' and 'ended' in m,name
        for relative,wanted in m['source_sha256'].items():
            assert sha((root/source/relative).read_bytes())==wanted,(name,relative)
        assert sha(matcher.read_bytes())==m['source_sha256']['scripts/analyze-durrant-flutter.py']
        cases={}
        for entry in m['cases']:
            raw=(directory/entry['file']).read_bytes();assert sha(raw)==entry['sha256']
            case=json.loads(raw);assert case['status']=='computed' and case['base']['converged']
            for value in [case['base']['residual'],case['base']['modal_base']['continuous_residual']]:
                assert math.isfinite(value) and 0<=value<1e-7
                max_base=max(max_base,value)
            assert len(case['searches'])==2
            for search in case['searches']:
                for mode in search['modes']:
                    assert all(math.isfinite(v) for v in mode['eigenvalue_per_s'])
                    for key in ('right_backward_error','left_backward_error'):
                        error=mode[key];assert math.isfinite(error) and 0<=error<1e-9
                        max_pencil=max(max_pencil,error)
            if 'reused_from' in case:
                origin=case['reused_from'];recorded=Path(origin['path'])
                assert recorded.parent.name=='main73-run-01'
                raw=(root/recorded.parent.name/recorded.name).read_bytes()
                assert sha(raw)==origin['sha256']
                old=json.loads(raw)
                assert {k:v for k,v in case.items() if k!='reused_from'}=={k:v for k,v in old.items() if k!='reused_from'}
            cases[entry['file']]=case
        if 'boundaries' not in m:
            assert [c['spec'] for c in cases.values()]==m['plan']['cases']
        all_cases[name]=cases;runs[name]=m
    repeat=[]
    for old,new in [('case-04.json','case-00.json'),('case-05.json','case-01.json')]:
        a=all_cases['run-01'][old];b=all_cases['main73-run-01'][new]
        assert {k:v for k,v in a.items() if k!='elapsed_seconds'}=={k:v for k,v in b.items() if k!='elapsed_seconds'}
        repeat.append(dict(wing=b['spec']['wing'],panels=32,complete_payload_exact_except_timing=True))
    invariance=[]
    for old,checks in [('case-04.json',['case-00.json','case-01.json']),('case-05.json',['case-02.json','case-03.json'])]:
        a=all_cases['run-01'][old]
        for file in checks:
            b=all_cases['verification-01'][file];pairs=[p for p in match(a,b)['pairs'] if p['resolved']]
            assert len(pairs)>=6
            worst=max(p['scaled_root_change'] for p in pairs);assert worst<1e-7
            invariance.append(dict(wing=a['spec']['wing'],case=file,matched_modes=len(pairs),max_scaled_root_change=worst))
    boundaries=[]
    best_cases=[]
    for n in (8,16,32):
        name=f'boundary75-n{n}-run-01';m=runs[name];assert len(m['boundaries'])==1
        b=m['boundaries'][0];assert b['status']=='resolved'
        lo,hi=b['bracket_m_s'];roots=[complex(*v) for v in b['endpoint_roots_per_s']]
        assert lo<hi and hi-lo<=1e-4*max(abs(lo),abs(hi))
        assert roots[0].real<0<roots[1].real
        endpoints=[]
        for speed,target in zip((lo,hi),roots):
            choices=[c for c in all_cases[name].values() if c['spec']['speed_m_s']==speed]
            assert choices;case=choices[-1];assert case['spec']['wing']=='75' and case['spec']['panels']==n
            for search in case['searches']:
                assert min(abs(complex(*mode['eigenvalue_per_s'])-target) for mode in search['modes'])<1e-7*max(1.,abs(target))
            endpoints.append(case)
        pair=min(match(*endpoints)['pairs'],key=lambda p:abs(complex(*p['before'])-roots[0]))
        assert pair['resolved'] and abs(complex(*pair['after'])-roots[1])<1e-9*max(1.,abs(roots[1]))
        best=complex(*b['best_root_per_s']);assert abs(best.real)/max(1.,abs(best))<=1e-6
        case=all_cases[name][b['best_file']];assert case['spec']['speed_m_s']==b['best_speed_m_s']
        for search in case['searches']:
            assert min(abs(complex(*mode['eigenvalue_per_s'])-best) for mode in search['modes'])<1e-7*max(1.,abs(best))
        best_cases.append((case,best))
        boundaries.append(dict(panels=n,actual_elements=case['actual_elements'],speed_m_s=b['best_speed_m_s'],root_per_s=b['best_root_per_s'],frequency_Hz=best.imag/(2*math.pi),bracket_m_s=[lo,hi],normalized_growth=b['normalized_growth'],endpoint_mac=pair['modal_assurance']))
    mesh=[]
    for (a,ar),(b,br) in zip(best_cases[:-1],best_cases[1:]):
        pair=min(match(a,b)['pairs'],key=lambda p:abs(complex(*p['before'])-ar))
        assert abs(complex(*pair['after'])-br)<1e-8*max(1.,abs(br))
        assert pair['resolved'] and pair['modal_assurance']>.99
        mesh.append(pair)
    return dict(status='PASS_SCOPED_NUMERICAL_AUDIT',source_modules={'historical':71,'current':73},case_records=sum(len(c) for c in all_cases.values()),exact_current_repetitions=repeat,tangent_and_unit_invariance=invariance,boundaries=boundaries,cross_mesh_matches=mesh,maximum_base_residual=max_base,maximum_pencil_backward_error=max_pencil,source_pins={k:v for k,v in runs['main73-run-01']['source_sha256'].items() if k.startswith('openswing/')},limitations=['Local matched oscillatory branch only: total native finite spectrum remains unclassified.','No exact ASWING setup, experimental agreement, or continuum error bound is established.','No kernel parameter, acceptance tolerance, or physical equation was changed in this study.','Boundary results are native; WebAssembly/browser boundary replay remains outstanding.'])


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--root',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();matcher=args.root/'main73/scripts/analyze-durrant-flutter.py'
    record=audit(args.root,matcher);record['auditor_sha256']=sha(Path(__file__).read_bytes())
    args.output.write_text(json.dumps(record,indent=2)+'\n')
    print(json.dumps({k:v for k,v in record.items() if k not in ['source_pins','cross_mesh_matches']},indent=2))
