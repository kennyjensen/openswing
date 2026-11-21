"""Independent conventions, source contradictions, symmetry and control tangents."""
from pathlib import Path
import importlib.util,json,sys,time
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from isae_sa6_reference import CACHE,sha,IDS
from openswing.bridge import dispatch
spec=importlib.util.spec_from_file_location('sa6',ROOT/'scripts/verify-isae-sa6.py');s=importlib.util.module_from_spec(spec);spec.loader.exec_module(s)
DEST=ROOT/'docs/validation';WORK=ROOT/'.reference/isae-sa6-checks'


def main():
    study=json.loads((DEST/'isae-sa6.json').read_text());refs=json.loads((DEST/'isae-sa6-sources.json').read_text())
    pins={p.name:sha(p) for p in (ROOT/'openswing').glob('*.py')};assert pins==study['provenance']['modules']
    WORK.mkdir(exist_ok=True)
    # All 44 raw fmat pairs must agree with their archived MATLAB columns.
    mat=refs['matlab']['Post_Treatment_Post_Stall.m']['Clark_Y_Steady_chord'];rawdiff=[]
    for r in refs['fmat']:
        j=IDS.index(r['id']);row=mat[r['delta']//4];a=[row[3+4*j],row[4+4*j]];b=[r['coefficients'][k] for k in ['Cl','Cn']]
        rawdiff.append(max(abs(np.array(a)-b)))
    assert max(rawdiff)==0
    conflicts=[];invalid=[];ods_mat=[];csv_conflicts=[]
    import csv,io
    raw=list(csv.reader(io.StringIO(refs['csv']['ClarkY_Steady_span_varying.csv'])))[2:]
    for j,ident in enumerate(IDS[4:]):
        primary=next(r for r in refs['primary'] if r['id']==ident and r['body_alpha']==0)
        for i,row in enumerate(raw):
            assert int(row[0])==4*i
            for offset,field in [(1,'Cl_body'),(2,'CN_tail_body')]:
                actual=float(row[2*j+offset]);expected=primary[field][i]
                if abs(actual-expected)>1e-12:csv_conflicts.append(dict(id=ident,delta=4*i,field=field,csv=actual,primary=expected))
    original=next(c for c in study['cases'] if c['id']=='10b_25c' and not c['reconstructed'])
    model=s.model_for((CACHE/original['path']).read_text());derived=s.model_for((CACHE/original['path']).read_text(),True)
    fifteen=next(c for c in study['cases'] if c['id']=='15b_25c')
    other=s.model_for((CACHE/fifteen['path']).read_text())
    physical_differences=[]
    for key,d in model.beams[0].distributions.items():
        b=other.beams[0].distributions[key]
        if not(np.array_equal(d.t,b.t) and np.array_equal(d.values,b.values)):physical_differences.append(key)
        new=derived.beams[0].distributions[key]
        if key not in ['dCLdF1','dCMdF1']:assert np.array_equal(d.t,new.t) and np.array_equal(d.values,new.values)
    assert np.allclose(model.beams[0].distributions['dCLdF1'].t,[-.762,-.381,-.381,.381,.381,.762])
    assert np.allclose(derived.beams[0].distributions['dCLdF1'].t,[-.762,-.508,-.508,.508,.508,.762])
    for name,sheets in refs['ods'].items():
        post='Stall' in name;chord='chord' in name
        m=refs['matlab']['Post_Treatment_Post_Stall.m' if post else 'Post_Treatment_Level.m']['Clark_Y_Steady_chord' if chord else 'Clark_Y_Steady_Span']
        for i,row in enumerate(sheets[0]['rows'][2:]):
            for j,c in enumerate(row[:len(m[i])]):
                if c['value'] is None:invalid.append(dict(file=name,row=i+3,column=j+1,raw=c['raw']))
                elif abs(c['value']-m[i][j])>1e-12:ods_mat.append(dict(file=name,delta=4*i,column=j+1,ods=c['value'],matlab=m[i][j]))
        alpha=0 if not post else (12 if chord else 8)
        for j,ident in enumerate(IDS[:4] if chord else IDS[4:]):
            p=next(r for r in refs['primary'] if r['id']==ident and r['body_alpha']==alpha)
            for i,row in enumerate(m):
                for offset,key in [(1,'Cl_body'),(2,'CN_tail_body')]:
                    if abs(row[4*j+offset]-p[key][i])>1e-12:
                        conflicts.append(dict(file='Post_Treatment_Post_Stall.m' if post else 'Post_Treatment_Level.m',id=ident,body_alpha=alpha,delta=4*i,field=key,archived=row[4*j+offset],primary=p[key][i]))
    symmetries=[];tangents=[]
    for case in study['cases']:
        source=(CACHE/case['path']).read_text()
        for alpha in [0,8,12]:
            for delta in [4,32]:
                row=next(r for r in case['runs'] if r['specification']==dict(case=case['case_id'],reconstructed=case['reconstructed'],panels=80,alpha=alpha,delta=delta,frozen=False))
                if row['status']!='computed':continue
                negative=s.compute(source,{**row['specification'],'delta':-delta});p=row['result']
                error=max(abs(p[k]+negative[k]) for k in ['Cl','Cn','Cl_stability','Cn_stability'])
                even=max(abs(p[k]-negative[k]) for k in ['CL','CD','Cm'])
                assert max(error,even)<2e-8
                symmetries.append(dict(case=case['case_id'],alpha=alpha,delta=delta,odd_error=error,even_error=even,negative=negative))
        if case['id'] not in IDS[:4]:continue
        for panels in [40,80]:
            for delta in [4,32]:
                request=dict(action='solve',mode='mounted',source=source,panels=panels,condition=dict(speed=20,alpha=12,mach=0,controls={1:delta}),derivatives=dict(parameters=['control.1'],axes='stability'))
                start=time.monotonic();r=dispatch(request);d=r['derivatives'];implicit=np.array(d['matrices']['coefficients'])[:,0]
                assert r['residual']<1e-8
                base=s.compute(source,dict(reconstructed=False,alpha=12,delta=delta,frozen=False,panels=panels))
                actualbase=np.array([-base['CD'],0,base['CL'],base['Cl_stability'],base['Cm'],base['Cn_stability']])
                base_error=float(max(abs(np.array(d['base_outputs']['coefficients'])-actualbase)));assert base_error<2e-8
                central=[]
                for h in [.01,.005]:
                    a,b=[s.compute(source,dict(reconstructed=False,alpha=12,delta=delta+sign*h,frozen=False,panels=panels)) for sign in [1,-1]]
                    keys=['CD','CL','Cl_stability','Cm','Cn_stability'];fd=np.array([(a[k]-b[k])/(2*h) for k in keys]);fd[0]*=-1;fd=np.insert(fd,1,0)
                    error=float(max(abs(implicit-fd)));assert error<2e-7
                    central.append(dict(h=h,coefficients=fd.tolist(),maximum_error=error))
                archived=next(a['coefficients'] for a in refs['fmat'] if a['id']==case['id'] and a['delta']==delta)
                comparison={key:float(implicit[i]-archived[key+'dF1']) for i,key in [(0,'CX'),(2,'CL'),(3,'Cl'),(4,'Cm'),(5,'Cn')]}
                tangents.append(dict(case=case['case_id'],panels=panels,delta=delta,alpha=12,seconds=time.monotonic()-start,request=request,
                    base_coefficients=d['base_outputs']['coefficients'],mounted_rigid_base_error=base_error,implicit_coefficients=implicit.tolist(),central=central,archived_derivative_difference=comparison))
                print('tangent',case['id'],panels,delta,'PASS',flush=True)
    output=dict(status='PASS_NUMERICAL_CHECKS_NOT_EXPERIMENTAL_VALIDATION',modules=pins,study_sha256=sha(DEST/'isae-sa6.json'),script_sha256=sha(Path(__file__)),
        source_report_sha256=sha(DEST/'isae-sa6-sources.json'),fmat_matlab_maximum_error=max(rawdiff),fmat_count=len(rawdiff),
        invalid_ods_cells=invalid,csv_primary_conflicts=csv_conflicts,ten_fifteen_distribution_differences=physical_differences,ods_matlab_conflicts=ods_mat,matlab_primary_conflicts=conflicts,symmetries=symmetries,tangents=tangents,
        notes=['Primary table transcriptions are explicit and separately preserved; the contradictory archive tables are not silently repaired.',
               'Implicit control derivatives are checked against two centered nonlinear step sizes. Agreement verifies the implemented tangent, not measured control effectiveness.'])
    (DEST/'isae-sa6-checks.json').write_text(json.dumps(output,indent=2)+'\n');print('COMPLETE',len(symmetries),'symmetry',len(tangents),'tangents',len(conflicts),'MATLAB-primary conflicts',flush=True)

if __name__=='__main__':main()
