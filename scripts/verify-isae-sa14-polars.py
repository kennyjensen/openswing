"""SA-14 exact-angle polars with archive flags and explicit PG/freeze variants.

The four original model/source reports stay pinned. This extends the pilot;
it does not resolve the swept force-velocity limit or validate the full family.
"""
from pathlib import Path
import fcntl
import hashlib
import json
import os
import sys
import time
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from openswing.asw import parse_asw
from openswing.aero import FlightCondition,solve_rigid,AnalysisError
from openswing.geometry import model_meshes
D=ROOT/'docs/validation'


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def key(value):return hashlib.sha256(json.dumps(value,sort_keys=True).encode()).hexdigest()
def atomic(path,value):
    temporary=path.with_suffix(f'.{os.getpid()}.tmp')
    temporary.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')
    temporary.replace(path)


def references(sources):
    result=[]
    for polar in sources['polars']:
        assert polar['columns']==['index','t','conv','stall','alpha','CL']
        for row in polar['rows']:
            assert row[2] in [0.,1.]
            result.append(dict(kind='archive',case=polar['case'],source_path=polar['path'],
                source_sha256=polar['sha256'],row_index=int(row[0]),alpha=row[4],observed=row[5],
                observable='coefficients.CL',converged=bool(row[2]),stall_flag=row[3]))
    figure=next(f for f in sources['experimental'] if f['filename']=='Figure24.csv')
    mapping={'CL_WB_S_WB':('wing_body','CL_total'),
             'CL_WB_SW':('wing_body','CL_exposed_wing'),
             'CL_W_SW':('wing_only','CL_exposed_wing')}
    for series in figure['series']:
        case,observable=mapping[series['label']]
        for p in series['points']:
            result.append(dict(kind='experiment',case=case,source_path=figure['identical_copies'][0],
                source_sha256=figure['source_sha256'],label=series['label'],source_row=p['row'],
                alpha=p['xy'][0],observed=p['xy'][1],observable='primary_normalization.'+observable))
    assert len(result)==224
    return result


def requests(refs):
    plan={}
    for ref in refs:
        for n in [25,50,100]:
            for frozen in [False,True]:
                for pg in (['zero','speed'] if ref['kind']=='archive' else ['primary_0.19','zero','speed']):
                    q=dict(case=ref['case'],panels=n,alpha=ref['alpha'],pg=pg,frozen=frozen)
                    plan[key(q)]=q
    # Primary-Mach experimental states first; ordering is not a continuation.
    result=sorted(plan.values(),key=lambda q:(q['pg']!='primary_0.19',q['frozen'],q['panels'],q['case'],q['pg'],q['alpha']))
    assert len(result)==2952
    return result


def compute(model,q,sources):
    mach={'zero':0.,'speed':70./model.constants[2],'primary_0.19':.19}[q['pg']]
    condition=FlightCondition(speed=70.,alpha=q['alpha'],mach=mach,freeze_influences=q['frozen'])
    r=solve_rigid(model,condition,q['panels'])
    assert r['converged'] and r['residual']<=1e-8
    meshes={m.beam.index:m for m in model_meshes(model,q['panels'])}
    counter={b:0 for b in meshes}
    a=np.deg2rad(q['alpha']);lift=np.array([-np.sin(a),0.,np.cos(a)])
    pressure=.5*model.constants[1]*70**2
    primary=sources['primary']['wing'];span=primary['span_m'];area=primary['area_m2'];cut=.1*span/2
    forces={name:np.zeros(3) for name in ['wing','body','exposed']};strips=[]
    for strip in r['strips']:
        mesh=meshes[strip['beam']];i=counter[strip['beam']];counter[strip['beam']]+=1
        force=np.asarray(strip['force']);fraction=0.;y0=y1=None
        if mesh.beam.lifting:
            y0,y1=sorted([float(mesh.r0[i,1]),float(mesh.r1[i,1])]);dy=y1-y0;assert dy>0
            fraction=1.-max(0.,min(y1,cut)-max(y0,-cut))/dy
            forces['wing']+=force;forces['exposed']+=fraction*force
        else:forces['body']+=force
        item={k:strip[k] for k in ['beam','t','position','force']}
        if mesh.beam.lifting:
            item.update({k:strip[k] for k in ['circulation','cl','normal_mach','normal_speed','relative_velocity']})
        item.update(lifting=mesh.beam.lifting,exposed_fraction=fraction,y0=y0,y1=y1)
        strips.append(item)
    assert np.max(abs(forces['wing']+forces['body']-r['force']))<2e-7
    assert abs(np.asarray(r['force'])@lift/pressure/model.reference[0,0]-r['CL'])<1e-10
    normalization=dict(area=area,span=span,cut_y=cut,CL_total=float(np.asarray(r['force'])@lift/pressure/area),
        CL_full_wing=float(forces['wing']@lift/pressure/area),CL_body=float(forces['body']@lift/pressure/area),
        CL_exposed_wing=float(forces['exposed']@lift/pressure/area))
    assert abs(normalization['CL_total']-normalization['CL_full_wing']-normalization['CL_body'])<1e-10
    wing=[s for s in strips if s['lifting']];worst=max(wing,key=lambda s:s['normal_mach'])
    return dict(coefficients={k:r[k] for k in ['CL','CD','Cm','CY','Cl','Cn','CDi','CDp','CDbody']},
        force=r['force'],moment=r['moment'],actual_mach=mach,dynamic_pressure=pressure,
        reference_area=float(model.reference[0,0]),primary_normalization=normalization,
        force_partitions={k:v.tolist() for k,v in forces.items()},strips=strips,
        residual=r['residual'],maximum_local_residual=float(np.max(abs(np.asarray(r['circulation_local_residual'])))),
        evaluations=r['evaluations'],circulation_solver=r['circulation_solver'],
        maximum_section_normal_mach=worst['normal_mach'],maximum_flow=worst,
        actual_lifting_intervals=len(wing),actual_body_intervals=len(strips)-len(wing),
        archived_area_multiplier_CL=r['CL']*sources['postprocessing']['total_lift_multiplier'])


def main():
    sources=json.loads((D/'isae-sa14-sources.json').read_text())
    modules={p.name:sha(p) for p in (ROOT/'openswing').glob('*.py')};assert modules==sources['modules']
    inputs={p.relative_to(ROOT).as_posix():sha(p) for p in [Path(__file__),D/'isae-sa14-sources.json',ROOT/'scripts/isae_sa14_reference.py']}
    provenance=dict(revision=sources['revision'],modules=modules,inputs=inputs)
    folder=ROOT/'.reference/isae-sa14-polars'/key(provenance);folder.mkdir(parents=True,exist_ok=True)
    # Lock the run as well as using atomic per-request files: observation
    # timeouts or a second invocation cannot create duplicate computations.
    with (folder/'run.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        if (folder/'identity.json').exists():assert json.loads((folder/'identity.json').read_text())==provenance
        else:atomic(folder/'identity.json',provenance)
        refs=references(sources);plan=requests(refs)
        atomic(folder/'plan.json',dict(references=refs,requests=plan))
        models={m['name']:parse_asw(m['source']) for m in sources['models']}
        rows=[];computed=0;rejected=0
        print('START',str(folder),'pid',os.getpid(),'requests',len(plan),flush=True)
        for q in plan:
            path=folder/(key(q)+'.json')
            if path.exists():
                row=json.loads(path.read_text());assert row['specification']==q
            else:
                start=time.monotonic()
                try:row=dict(specification=q,status='computed',result=compute(models[q['case']],q,sources))
                except (AnalysisError,ValueError) as exc:
                    row=dict(specification=q,status='rejected',error=str(exc),details=getattr(exc,'details',None))
                row['seconds']=time.monotonic()-start;atomic(path,row)
            brief={k:v for k,v in row.items() if k!='result'}
            if row['status']=='computed':
                brief['result']={k:v for k,v in row['result'].items() if k!='strips'};computed+=1
            else:rejected+=1
            brief.update(cache_path=path.relative_to(ROOT).as_posix(),cache_sha256=sha(path));rows.append(brief)
            progress=dict(completed=len(rows),total=len(plan),computed=computed,rejected=rejected,last=q,status=row['status'],pid=os.getpid())
            atomic(folder/'progress.json',progress)
            if len(rows)%10==0 or len(rows)==len(plan):print(json.dumps(progress),flush=True)
        assert modules=={p.name:sha(p) for p in (ROOT/'openswing').glob('*.py')}
        assert inputs=={name:sha(ROOT/name) for name in inputs}
        report=dict(status='FULL_POLAR_CALCULATIONS_COMPLETE_COMPARISONS_PENDING',provenance=provenance,
            references=refs,rows=rows,computed=computed,rejected=rejected,
            protocol=[
                'All180 archived polar rows at their exact angles, retaining116 converged and64 unconverged archive flags separately.',
                'All44 Figure24 digitized angles, separating total wing/body balance lift from exposed-wing pressure lift.',
                'Original input geometry, section properties, density and speed70m/s; no coefficient fit or altered Mach guard.',
                'N25/50/100 pointwise circulation, with live and frozen influences treated separately.',
                'Archive PG mode is not established by its toggle-only scripts: test fixed zero and speed-derived PG separately. Experimental states additionally use the primary Mach0.19.',
                'Every state starts independently. No unconverged or physically invalid state is promoted to computed.',
                'Exposed-wing force uses fractional strips outside2abs(y)/b=0.1; mesh sensitivity is required. All coefficients use the appropriate declared reference area.'],
            limitations=sources['limitations']+[
                'The swept bound-line force velocity has an unresolved singular refined limit; successful finite-mesh solves do not establish physical convergence.',
                'The archived ASWING mode counts, executable revision and detailed saved settings are unavailable.',
                'This does not resolve iw4 Figure15/17 provenance, missing section polars, experimental uncertainties or complete ASWING fidelity.'])
        atomic(D/'isae-sa14-polars.json',report)
        print('COMPLETE',computed,rejected,flush=True)


if __name__=='__main__':main()
