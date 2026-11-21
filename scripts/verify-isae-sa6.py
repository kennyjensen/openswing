"""Source-pinned SA-6 signed aileron sweeps, primary comparisons and mesh checks."""
from pathlib import Path
import hashlib,json,sys,time
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from openswing.asw import parse_asw, Distribution
from openswing.aero import FlightCondition,solve_rigid,AnalysisError
from isae_sa6_reference import CACHE,REVISION,sha
DEST=ROOT/'docs/validation'


def model_for(source,reconstructed=False):
    m=parse_asw(source)
    if reconstructed:
        b=m.beams[0]
        for key in ['dCLdF1','dCMdF1']:
            d=b.distributions[key];t=d.t.copy();t[np.isclose(t,-.381)]=-.508;t[np.isclose(t,.381)]=.508
            b.distributions[key]=Distribution(d.name,t,d.values.copy(),d.line)
    return m


def compute(source,spec):
    model=model_for(source,spec['reconstructed']);sign=-float(np.sign(model.beams[0].value('dCLdF1',.7)))
    condition=FlightCondition(speed=20,alpha=spec['alpha'],mach=0.,controls={1:sign*spec['delta']},freeze_influences=spec['frozen'])
    r=solve_rigid(model,condition,panels=spec['panels'])
    assert r['converged'] and r['residual']<1e-8
    qS=.5*model.constants[1]*400*model.reference[0,0];b=model.reference[0,2]
    force=np.sum([s['force'] for s in r['strips']],axis=0)
    moment=np.sum([np.cross(np.array(s['position'])-model.reference[1],s['force'])+s['moment'] for s in r['strips']],axis=0)
    a=np.deg2rad(spec['alpha']);c,s=np.cos(a),np.sin(a)
    check=max(abs(-moment[0]/qS/b-r['Cl']),abs(-moment[2]/qS/b-r['Cn']),
              abs(force@[-s,0,c]/qS-r['CL']),abs(force@[c,0,s]/qS-r['CD']))
    assert check<2e-10
    return dict(**{k:float(r[k]) for k in ['Cl','Cn','CL','CD','Cm','residual']},
        Cl_stability=float(c*r['Cl']+s*r['Cn']),Cn_stability=float(-s*r['Cl']+c*r['Cn']),
        moment_body_openswing=moment.tolist(),force_body_openswing=force.tolist(),
        F1=sign*spec['delta'],independent_wrench_error=float(check),actual_strips=len(r['strips']))


def metrics(a,b):
    e=np.array(a)-np.array(b)
    return dict(count=len(e),bias=float(e.mean()),rmse=float(np.sqrt(np.mean(e**2))),maximum_absolute_error=float(max(abs(e))))


def main():
    sources=json.loads((DEST/'isae-sa6-sources.json').read_text())
    pins={p.name:sha(p) for p in sorted((ROOT/'openswing').glob('*.py'))}
    identity=dict(modules=pins,script_sha256=sha(Path(__file__)),reference_script_sha256=sha(ROOT/'scripts/isae_sa6_reference.py'),source_report_sha256=sha(DEST/'isae-sa6-sources.json'))
    runroot=ROOT/'.reference/isae-sa6-runs'/hashlib.sha256(json.dumps(identity,sort_keys=True).encode()).hexdigest();runroot.mkdir(parents=True,exist_ok=True)
    cases=[]
    for entry in sources['models']+[next(r for r in sources['models'] if r['id']=='10b_25c')]:
        reconstructed=len(cases)==7
        case=dict(**entry,reconstructed=reconstructed,case_id=entry['id']+('_reconstructed' if reconstructed else '_literal'),runs=[])
        source=(CACHE/entry['path']).read_text();assert sha(CACHE/entry['path'])==entry['sha256']
        for frozen in [False,True]:
            for panels in [40,80,160]:
                for alpha in [0,8,12]:
                    for delta in range(0,45,4):
                        spec=dict(case=case['case_id'],reconstructed=reconstructed,panels=panels,alpha=alpha,delta=delta,frozen=frozen)
                        key=hashlib.sha256(json.dumps(spec,sort_keys=True).encode()).hexdigest();path=runroot/(key+'.json')
                        if path.exists():row=json.loads(path.read_text());assert row['specification']==spec
                        else:
                            start=time.monotonic()
                            try:row=dict(specification=spec,status='computed',result=compute(source,spec))
                            except AnalysisError as exc:row=dict(specification=spec,status='rejected',error=str(exc))
                            row['seconds']=time.monotonic()-start;path.write_text(json.dumps(row,indent=2)+'\n')
                        case['runs'].append(dict(**row,cache_sha256=sha(path),cache_path=path.relative_to(ROOT).as_posix()))
                print(case['case_id'],'frozen',frozen,'panels',panels,'computed',sum(r['status']=='computed' for r in case['runs']),flush=True)
        cases.append(case)
    comparisons=[];meshes=[];archive=[]
    for case in cases:
        lookup={(r['specification']['frozen'],r['specification']['panels'],r['specification']['alpha'],r['specification']['delta']):r for r in case['runs']}
        for frozen in [False,True]:
            for alpha in [0,8,12]:
                ref=next(r for r in sources['primary'] if r['id']==case['id'] and r['body_alpha']==alpha)
                rows=[lookup[frozen,160,alpha,d] for d in ref['delta']];valid=[i for i,r in enumerate(rows) if r['status']=='computed']
                comparisons.append(dict(case=case['case_id'],frozen=frozen,body_alpha=alpha,requested=12,computed=len(valid),
                    primary_table=dict(report=ref['report'],table=ref['table'],pdf_page=ref['pdf_page']),
                    geometry_matches_label=case['id']!='10b_25c' or case['reconstructed'],
                    errors={key:metrics([rows[i]['result'][key] for i in valid],[ref[field][i] for i in valid]) for key,field in [('Cl','Cl_body'),('Cn','Cn_body')]}))
                for low,high in [(40,80),(80,160)]:
                    pairs=[(lookup[frozen,low,alpha,d],lookup[frozen,high,alpha,d]) for d in ref['delta']]
                    pairs=[(a,b) for a,b in pairs if a['status']==b['status']=='computed']
                    meshes.append(dict(case=case['case_id'],frozen=frozen,alpha=alpha,low=low,high=high,requested=12,
                        errors={key:metrics([a['result'][key] for a,b in pairs],[b['result'][key] for a,b in pairs]) for key in ['Cl','Cn']}))
            if case['id'] in ['20b_15c','20b_20c','20b_30c','20b_35c']:
                ref=[r for r in sources['fmat'] if r['id']==case['id']];pairs=[(lookup[frozen,160,12,r['delta']],r) for r in ref]
                valid=[(a,b) for a,b in pairs if a['status']=='computed']
                archive.append(dict(case=case['case_id'],frozen=frozen,body_alpha=12,requested=11,computed=len(valid),
                    errors={key:metrics([a['result'][actual] for a,b in valid],[b['coefficients'][key] for a,b in valid]) for key,actual in [('Cl','Cl_stability'),('Cn','Cn_stability'),('CL','CL'),('Cm','Cm')]}))
    assert pins=={p.name:sha(p) for p in sorted((ROOT/'openswing').glob('*.py'))}
    report=dict(status='PRIMARY_AND_ARCHIVED_COMPARISONS_WITH_RETAINED_DISCREPANCIES',full_suite_validated=False,
        provenance=dict(**identity,revision=REVISION,sources=sources['sources']),cases=cases,primary_comparisons=comparisons,mesh_comparisons=meshes,archived_fmat_comparisons=archive,
        settings=dict(speed=20,body_pitch=[0,8,12],wing_incidence=[4,12,16],delta=list(range(0,45,4)),panels=[40,80,160],mach=0,frozen=[False,True],
            solver='Unchanged default nonlinear sectional stall model, tolerance and continuation; each requested state solved independently',
            coefficients='Cl/Cn are x-forward/z-down body coefficients normalized by span; archived fmat compared after rotation to stability axes'),
        limitations=sources['findings']+['No uncertainty-based pass band or pointwise experimental uncertainty is available. Mesh differences and primary/archived errors are reported without a pass label.'])
    (DEST/'isae-sa6.json').write_text(json.dumps(report,indent=2)+'\n');print('COMPLETE',sum(len(c['runs']) for c in cases),'runs',flush=True)

if __name__=='__main__':main()
