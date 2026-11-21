"""Pinned SA-14 pilot with primary force normalization and mixed archive PG."""
from pathlib import Path
import hashlib
import json
import os
import sys
import time
import numpy as np

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'scripts'))
from openswing.asw import parse_asw
from openswing.geometry import model_meshes
from openswing.aero import FlightCondition,solve_rigid,AnalysisError
from isae_sa14_reference import sha,REVISION
D=ROOT/'docs/validation'


def requests():
    rows=[]
    for case in ['wing_only','wing_body','infinite_body']:
        for n in [25,50,100]:
            for alpha in [0.,4.7,8.8,12.9]:
                rows.append(dict(case=case,panels=n,alpha=alpha,pg='speed' if alpha in [0.,4.7] else 'zero'))
        for alpha in [4.7,8.8,12.9]:rows.append(dict(case=case,panels=50,alpha=alpha,pg='primary_0.19'))
        rows.append(dict(case=case,panels=50,alpha=4.7,pg='zero'))
    for alpha in [0.,8.8]:rows.append(dict(case='body_only',panels=50,alpha=alpha,pg='zero'))
    assert len(rows)==50
    return rows


def compute(source,q,sources):
    model=parse_asw(source)
    mach={'zero':0.,'speed':70./model.constants[2],'primary_0.19':.19}[q['pg']]
    condition=FlightCondition(speed=70.,alpha=q['alpha'],mach=mach)
    result=solve_rigid(model,condition,q['panels'])
    assert result['converged'] and result['residual']<=1e-8
    meshes=model_meshes(model,q['panels']);meshmap={m.beam.index:m for m in meshes}
    local_indices={m.beam.index:0 for m in meshes}
    a=np.deg2rad(q['alpha']);lift=np.array([-np.sin(a),0.,np.cos(a)]);drag=np.array([np.cos(a),0.,np.sin(a)])
    dynamic_pressure=.5*model.constants[1]*70.**2
    primary=sources['primary']['wing'];span=primary['span_m'];area=primary['area_m2'];cbar=area/span
    cut=.1*span/2
    wing_force=np.zeros(3);body_force=np.zeros(3);exposed_force=np.zeros(3);profiles=[];bodies=[]
    for s in result['strips']:
        mesh=meshmap[s['beam']];i=local_indices[s['beam']];local_indices[s['beam']]+=1
        force=np.array(s['force'])
        if not mesh.beam.lifting:
            body_force+=force;bodies.append(s);continue
        y0,y1=sorted([float(mesh.r0[i,1]),float(mesh.r1[i,1])]);dy=y1-y0;assert dy>0
        hidden=max(0.,min(y1,cut)-max(y0,-cut))/dy
        fraction=1.-hidden
        wing_force+=force;exposed_force+=fraction*force
        y=float(s['position'][1]);chord=float(mesh.beam.value('chord',s['t']))
        profiles.append(dict(s,y0=y0,y1=y1,normalized_y=2*y/span,exposed_fraction=fraction,
            primary_local_load=float(force@lift/dynamic_pressure/dy/cbar),normal_chord=chord,
            archive_plot_ordinate=float(s['cl']*chord/sources['postprocessing']['local_denominator'])))
    assert max(np.max(abs(wing_force+body_force-result['force'])),abs(np.array(result['force'])@lift/dynamic_pressure/model.reference[0,0]-result['CL']))<2e-7
    profiles.sort(key=lambda s:s['normalized_y'])
    measured=[]
    if q['case'] in ['wing_only','wing_body']:
        figure=next(f for f in sources['experimental'] if f['filename']=='Figure7.csv')
        label=('Wing_only' if q['case']=='wing_only' else 'Wing_body')+'_alpha_'+str(q['alpha']).replace('.','_')
        series=next((s for s in figure['series'] if s['label']==label),None)
        if series:
            xs=np.array([s['normalized_y'] for s in profiles]);ys=np.array([s['primary_local_load'] for s in profiles])
            for p in series['points']:
                x,observed=p['xy'];inside=xs[0]<=x<=xs[-1]
                measured.append(dict(source_row=p['row'],normalized_y=x,observed=observed,
                    predicted=float(np.interp(x,xs,ys)) if inside else None,
                    status='computed' if inside else 'outside_native_midpoint_range'))
    coefficients={k:result[k] for k in ['CL','CD','Cm','CY','Cl','Cn','CDi','CDp','CDbody']}
    return dict(coefficients=coefficients,force=result['force'],moment=result['moment'],actual_mach=mach,
        dynamic_pressure=dynamic_pressure,reference_area=float(model.reference[0,0]),residual=result['residual'],
        maximum_local_residual=result.get('circulation_solver',{}).get('maximum_local_residual'),
        maximum_section_normal_mach=max((s['normal_mach'] for s in profiles),default=0.),
        profiles=profiles,body_strips=bodies,actual_lifting_intervals=len(profiles),actual_body_intervals=len(bodies),
        primary_normalization=dict(span=span,area=area,mean_geometric_chord=cbar,cut_y=cut,
            CL_total=float(np.array(result['force'])@lift/dynamic_pressure/area),
            CL_full_wing=float(wing_force@lift/dynamic_pressure/area),
            CL_body=float(body_force@lift/dynamic_pressure/area),
            CL_exposed_wing=float(exposed_force@lift/dynamic_pressure/area),
            method='Wind-axis strip forces. Partial strips crossing2|y|/b=0.1 use their exposed span fraction; mesh sensitivity is required.'),
        archived_area_multiplier_CL=float(result['CL']*sources['postprocessing']['total_lift_multiplier']),
        measured_local_points=measured,limitations=result['limitations'])


def main():
    source_path=D/'isae-sa14-sources.json';sources=json.loads(source_path.read_text())
    modules={p.name:sha(p) for p in (ROOT/'openswing').glob('*.py')}
    assert sources['modules']==modules and sources['script_sha256']==sha(ROOT/'scripts/isae_sa14_reference.py')
    provenance=dict(revision=REVISION,modules=modules,script_sha256=sha(Path(__file__)),
        source_report_sha256=sha(source_path),reference_script_sha256=sha(ROOT/'scripts/isae_sa14_reference.py'))
    identity=hashlib.sha256(json.dumps(provenance,sort_keys=True).encode()).hexdigest()
    folder=ROOT/'.reference/isae-sa14-runs'/identity;folder.mkdir(parents=True,exist_ok=True)
    pin=folder/'identity.json'
    if pin.exists():assert json.loads(pin.read_text())==provenance
    else:pin.write_text(json.dumps(provenance,indent=2)+'\n')
    plan=requests();rows=[]
    for q in plan:
        path=folder/(hashlib.sha256(json.dumps(q,sort_keys=True).encode()).hexdigest()+'.json')
        if path.exists():row=json.loads(path.read_text());assert row['specification']==q
        else:
            start=time.monotonic();source=next(m['source'] for m in sources['models'] if m['name']==q['case'])
            try:row=dict(specification=q,status='computed',result=compute(source,q,sources))
            except (AnalysisError,ValueError) as exc:row=dict(specification=q,status='rejected',error=str(exc),details=getattr(exc,'details',None))
            row['seconds']=time.monotonic()-start
            tmp=path.with_suffix(f'.{os.getpid()}.tmp');tmp.write_text(json.dumps(row,indent=2)+'\n');tmp.replace(path)
        row.update(cache_path=path.relative_to(ROOT).as_posix(),cache_sha256=sha(path));rows.append(row)
        progress=dict(completed=len(rows),total=len(plan),last=q,status=row['status'])
        tmp=folder/'progress.tmp';tmp.write_text(json.dumps(progress,indent=2)+'\n');tmp.replace(folder/'progress.json')
        print(len(rows),'/',len(plan),q,row['status'],flush=True)
    assert modules=={p.name:sha(p) for p in (ROOT/'openswing').glob('*.py')}
    out=dict(status='PILOT_COMPUTATIONS_COMPLETE_FULL_COMPARISONS_PENDING',provenance=provenance,rows=rows,
        computed=sum(r['status']=='computed' for r in rows),rejected=sum(r['status']=='rejected' for r in rows),
        protocol=['Three unchanged comparison models at25/50/100 intervals and alpha0/4.7/8.8/12.9.',
            'The4.7-degree exported state uses speed-derived PG;8.8/12.9 use zero PG as printed in the archives. Zero-angle setup uses speed-derived PG.',
            'AtN50, compare all three models at primary Mach0.19 and all three nonzero angles; add zero-PG4.7-degree cases.',
            'Two standalone body-only states retain their original12x size and separate reference values; they are diagnostics, not the coupled fuselage.',
            'Primary total/full-wing/body/exposed-wing observables are separate. Archive area-multiplied CL remains a separate diagnostic.',
            'Only Figure7 measured angles are sampled here. Full Figure24 exact-angle polars, iw4 geometry, independent induction and runtime checks are pending.'],
        limitations=sources['limitations'])
    (D/'isae-sa14-pilot.json').write_text(json.dumps(out,indent=2)+'\n');print('COMPLETE',out['computed'],out['rejected'],flush=True)


if __name__=='__main__':main()
