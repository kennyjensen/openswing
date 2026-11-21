"""SA-11 low-angle lower-winglet geometry alternatives from primary drawings.

Prepare six fixed cases, then run one bounded foreground solve per invocation.
Only lower-winglet geometry changes; no fitted geometry or aerodynamic laws.
"""
import argparse
from datetime import datetime, timezone
from dataclasses import replace
import hashlib
import json
import math
import os
from pathlib import Path
import re
import resource
import shutil
import signal
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
PARENT=ROOT/'artifacts/isae/sa11-two-winglet-spacing-20261108'
read=lambda p:json.loads(p.read_text())
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
utc=lambda:datetime.now(timezone.utc).isoformat()
FIELDS=('lift','drag','CL','CD','CDi','Cm_origin','efficiency')


def write(path,value):
    assert not path.exists(),path
    path.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')


def check(pins,root=ROOT):
    for name,digest in pins.items(): assert sha(root/name)==digest,name


def geometry_rows(source):
    result={}; beam=None; columns=None; scale=None
    for i,line in enumerate(source.splitlines()):
        tokens=line.split()
        if not tokens or tokens[0].startswith('#'): continue
        if tokens[0]=='Beam': beam=int(tokens[1]); columns=None
        elif tokens[0]=='End': columns=None
        elif beam in (4,5) and tokens[0]=='t':
            columns=tokens if tokens[1:4]==['x','y','z'] else None; scale=None
        elif columns and tokens[0]=='*': scale=list(map(float,tokens[1:]))
        elif columns:
            assert scale is not None and len(tokens)==len(scale)==7
            result.setdefault(beam,[]).append(dict(line=i,values={k:float(v)*s for k,v,s in zip(columns,tokens,scale)},scale=scale))
    assert sorted(result)==[4,5] and all(len(v)==2 for v in result.values())
    return result


def dimensions(rows):
    output=[]
    for beam,stations in rows.items():
        a,b=[r['values'] for r in stations]; dx=b['x']-a['x']; dy=b['y']-a['y']; dz=b['z']-a['z']
        span=math.hypot(dy,dz); length=math.hypot(dx,span); across=span/length
        output.append(dict(beam=beam,root=[a[k] for k in ('x','y','z')],tip=[b[k] for k in ('x','y','z')],
            cant_from_vertical=math.degrees(math.atan2(abs(dy),abs(dz))),
            leading_edge_sweep=math.degrees(math.atan2(dx,span)),span=span,length=length,
            normal_chords=[r['chord'] for r in (a,b)],unswept_chords=[r['chord']/across for r in (a,b)],
            untwisted_planform_area=.5*(a['chord']+b['chord'])*length))
    return output


def prepare(out):
    assert not out.exists(),out
    parent=read(PARENT/'plan.json'); check(parent['pins']); check(parent['generated_pins'],PARENT)
    assert read(PARENT/'verification.json')['analysis_sha256']==sha(PARENT/'analysis.json')
    catalog=read(ROOT/'docs/validation/aswing-authoritative-sources.json')
    pins=dict(parent['pins'])
    for entry in catalog['files']:
        if entry['id'] in ('isae-part-1','drela-steady'):
            assert sha(ROOT/entry['local_pdf'])==entry['sha256']
    nasa=ROOT/'reference/isae-sa11/NASA-TN-D-8473.pdf'
    assert sha(nasa)==read(ROOT/'docs/validation/isae-sa11-sources.json')['primary']['sha256']
    for path in (Path(__file__),nasa,PARENT/'plan.json',PARENT/'analysis.json',PARENT/'verification.json',PARENT/'model.asw',PARENT/'mesh.json'):
        pins[str(path.relative_to(ROOT))]=sha(path)
    source=(PARENT/'model.asw').read_text(); original=geometry_rows(source); variants={}
    target=dict(tip_chord=.2032,lower_span_ratio=.23,cant_from_vertical=36.,leading_edge_sweep=52.,root_chord_ratio=.4,tip_chord_ratio=.16)
    cant=math.radians(target['cant_from_vertical']); sweep=math.radians(target['leading_edge_sweep'])
    out.mkdir(parents=True)
    for variant in ('control','cant36','published_planform'):
        lines=source.splitlines(); edits=[]
        for beam,rows in original.items():
            a,b=[r['values'] for r in rows]; side=1 if a['y']>0 else -1
            span=math.hypot(b['y']-a['y'],b['z']-a['z'])
            changes={}
            if variant=='cant36':
                changes[1]=dict(y=a['y']+side*span*math.sin(cant),z=a['z']-span*math.cos(cant))
            elif variant=='published_planform':
                span=target['lower_span_ratio']*target['tip_chord']
                changes[0]=dict(chord=target['root_chord_ratio']*target['tip_chord']*math.cos(sweep))
                changes[1]=dict(x=a['x']+span*math.tan(sweep),y=a['y']+side*span*math.sin(cant),z=a['z']-span*math.cos(cant),
                                chord=target['tip_chord_ratio']*target['tip_chord']*math.cos(sweep))
            for station,updates in changes.items():
                row=rows[station]; old=lines[row['line']]; tokens=old.split(); columns=['t','x','y','z','twist','chord','Xax']
                for key,value in updates.items():
                    j=columns.index(key); tokens[j]=format(value/row['scale'][j],'.17g')
                lines[row['line']]='    '+'    '.join(tokens)
                edits.append(dict(line=row['line']+1,before=old,after=lines[row['line']],changed_fields=updates))
        text='\n'.join(lines)+'\n'; (out/f'{variant}.asw').write_text(text)
        restored=text.splitlines()
        for edit in edits: restored[edit['line']-1]=edit['before']
        assert '\n'.join(restored)+'\n'==source
        variants[variant]=dict(edits=edits,dimensions=dimensions(geometry_rows(text)),model=f'{variant}.asw')
    shutil.copyfile(PARENT/'mesh.json',out/'mesh.json'); shutil.copyfile(__file__,out/'driver-used.py')
    cases=[]
    for variant in variants:
        for label in ('0_70','0_80'):
            reference=next(c for c in parent['cases'] if c['label']==label and c['alpha']==0)
            cases.append(dict(reference,id=f'{variant}-{label}',variant=variant))
    write(out/'plan.json',dict(observed_utc=utc(),cases=cases,pins=pins,variants=variants,target=target,
        generated_pins={p.name:sha(p) for p in out.iterdir()},minimum_spacing=parent['minimum_spacing'],
        previous_goal_turn='Progress: six minimum-spacing transfers found low-angle drag error, a distinct CLmax input conflict and a lower-root own-wake rejection; independent equations checked.',
        protocol='Alpha0 only at240/272. Control; cant36 rotating only transverse axis with span/chord/sweep retained; published lower planform: h=.23*.2032, cant36, sweep52, unswept chords .4/.16*.2032 converted to normal by cos52. Preserve root position, arbitrary t, upper/main geometry, section properties, ASW beam twist -7..-11, frozen influences and minimum spacing. This is a planform diagnostic; incidence convention/fillets are not reconstructed.',
        source_basis='Jan PartI Fig40 p68 agrees on36deg lower cant and52deg sweep. NASA-TN-D-8473 printedp4/PDFp6 and Fig2b printedp17/PDFp19 supply exact span/chord ratios. No target-dependent fitting.',
        primary_passes_added=0))
    print(json.dumps(dict(prepared=True,cases=len(cases),variants=variants),indent=2))


def run(out,case_id):
    for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'): assert os.environ.get(key)=='1'
    resource.setrlimit(resource.RLIMIT_AS,(512*1024**2,512*1024**2));resource.setrlimit(resource.RLIMIT_CPU,(15,15));signal.alarm(25)
    begin=time.monotonic();plan=read(out/'plan.json');check(plan['pins']);check(plan['generated_pins'],out)
    case=next(c for c in plan['cases'] if c['id']==case_id);folder=out/case_id;assert not folder.exists()
    print(f'Bounded serial solve: {case_id}',flush=True)
    import numpy as np
    sys.path.insert(0,str(ROOT))
    from openswing.asw import parse_asw
    from openswing.aero import FlightCondition,AnalysisError,evaluate_aerodynamics
    from openswing.geometry import model_meshes
    from openswing.frozen_influence import lifting_geometry
    from openswing.factored_influence import FactoredInfluence
    from openswing.ground import GroundPlane
    from openswing.trefftz import trefftz_for_meshes
    model=parse_asw((out/plan['variants'][case['variant']]['model']).read_text())
    meshes=model_meshes(model,dict(default=32,beams=read(out/'mesh.json')))
    assert [len(m.tm) for m in meshes[:3]]==[32,16,16]
    assert all(min(m.length)>=plan['minimum_spacing']-1e-12 for m in meshes)
    g=lifting_geometry(meshes,np.array([1.,0.,0.]));n=len(g['hv']);condition=FlightCondition(**case['condition'])
    assert all(b.physical_index==1 for b in model.beams)
    span=np.concatenate([m.frames[...,1] for m in meshes]);position=np.concatenate([m.rm for m in meshes]);beam=np.concatenate([np.full(len(m.tm),m.beam.index) for m in meshes])
    sample=lambda key:np.concatenate([m.beam.value(key,m.tm) for m in meshes])
    assert np.all(sample('CLmax')==.8) and np.all(sample('CLmin')==-2) and np.all(sample('dCLda')==6.34)
    prior=PARENT/f"m{case['label']}-a00"
    with np.load(prior/'geometry.npz') as old:
        for key in g: np.testing.assert_allclose(g[key][:64],old[key][:64],atol=2e-12,rtol=0)
    folder.mkdir();np.savez(folder/'geometry.npz',**g)
    accepted=None;clock=time.monotonic()
    try: accepted=evaluate_aerodynamics(model,condition,meshes)
    except AnalysisError as exc:
        assert exc.details and exc.details['kind']=='section_normal_mach',str(exc)
        tb=exc.__traceback__
        while tb and tb.tb_frame.f_code.co_name!='evaluate_aerodynamics':tb=tb.tb_next
        assert tb is not None;local=tb.tb_frame.f_locals
        gamma,v,cl=[local[k].copy() for k in ('gamma','v','cl')];force=local['flift']+local['frate']+local['fprofile'];moments=np.full_like(force,np.nan)
        values={k:exc.details['surface_force_diagnostic']['terms']['sum'][k] for k in ('CL','CD')};values['Cm_origin']=None;residual=exc.details['circulation_residual']
        write(folder/'rejected.json',dict(message=str(exc),details=exc.details));status='REJECTED_STATE_DIAGNOSTIC';del tb,local
    else:
        write(folder/'accepted.json',accepted)
        gamma,v,cl,force,moments=[np.array([s[k] for s in accepted['strips']]) for k in ('circulation','relative_velocity','cl','force','moment')]
        values={k:accepted[k] for k in ('CL','CD','Cm_origin')};residual=accepted['residual'];status='COMPUTED_DIAGNOSTIC'
    elapsed=time.monotonic()-clock;assert residual<1e-8
    control_replay=None
    if case['variant']=='control':
        control_replay={}
        with np.load(prior/'state.npz') as old:
            for key,value in [('gamma',gamma),('velocity',v),('cl',cl),('force',force),('section_moment',moments)]:
                np.testing.assert_allclose(value,old[key],rtol=5e-13,atol=5e-13)
                control_replay[key]=dict(maximum_absolute_error=float(np.max(abs(value-old[key]))),
                    maximum_scaled_error=float(np.max(abs(value-old[key])/np.maximum(1.,abs(old[key])))))
    vp=v-np.sum(v*span,axis=1)[:,None]*span;mach=np.linalg.norm(vp,axis=1)/340.21
    assert (max(mach)<1)==(accepted is not None)
    pg=np.diag([1/math.sqrt(1-condition.mach**2),1.,1.])
    field=FactoredInfluence(g['hv'],g['a'],g['b'],np.array([1.,0.,0.]),pg,0.,GroundPlane(),exclude_bound=np.eye(n,dtype=bool))
    bound=np.einsum('ijk,j->ik',field.bound,gamma);wake=np.einsum('ijk,j->ik',field.rays,field.wake_strengths(gamma))
    replay=float(np.max(abs(condition.speed*condition.vectors()[0]+bound+wake-v)));assert replay<3e-8
    trefftz=trefftz_for_meshes(model,replace(condition,alpha=0.,beta=0.),meshes,gamma,1.2256,GroundPlane());assert trefftz['available']
    values.update(CDi=trefftz['CDi'],efficiency=trefftz['efficiency'])
    qs=.5*1.2256*condition.speed**2*.9329;values.update(lift=math.fsum(map(float,force[:,2])),drag=math.fsum(map(float,force[:,0])))
    assert abs(values['lift']/qs-values['CL'])<3e-14 and abs(values['drag']/qs-values['CD'])<3e-14
    normal=np.concatenate([np.sin(np.deg2rad(m.beam.value('alpha',m.tm)))[:,None]*m.frames[...,0]+np.cos(np.deg2rad(m.beam.value('alpha',m.tm)))[:,None]*m.frames[...,2] for m in meshes])
    cp=FactoredInfluence(g['cp'],g['a'],g['b'],np.array([1.,0.,0.]),pg,0.,GroundPlane())
    vcp=condition.speed*np.array([1.,0.,0.])+cp.apply(gamma);tangency=np.sum(vcp*normal,axis=1)
    vortex=1.2256*gamma[:,None]*np.cross(v,span)*g['ds'][:,None]
    friction=.5*1.2256*np.linalg.norm(v,axis=1)[:,None]*v*(g['chord']*sample('Cdf')*g['ds'])[:,None]
    pressure=.5*1.2256*np.linalg.norm(vp,axis=1)[:,None]*vp*(g['chord']*sample('Cdp')*g['ds'])[:,None]
    leakage=2*1.2256*vp/np.linalg.norm(vp,axis=1)[:,None]*(tangency**2*g['chord']*g['ds'])[:,None]
    assert np.max(abs(vortex+friction+pressure+leakage-force))<1e-9
    np.savez(folder/'state.npz',gamma=gamma,velocity=v,cl=cl,force=force,section_moment=moments,section_moment_available=accepted is not None,
             position=position,span=span,beam=beam,mach=mach,bound=bound,wake=wake,vortex_force=vortex,friction_force=friction,pressure_force=pressure,leakage_force=leakage)
    errors={k:None if values[k] is None else 100*(values[k]/case['reference'][k]-1) for k in FIELDS}
    passes={k:bool(accepted is not None and abs(errors[k])<=5) for k in FIELDS}
    report=dict(observed_utc=utc(),case=case,status=status,values=values,reference_error_percent=errors,passes=passes,passing_scalar_targets=sum(passes.values()),required_scalar_targets=7,
        maximum_normal_mach=float(max(mach)),rejected_sections=int(np.count_nonzero(mach>=1)),minimum_stall_margin_widths=float(min((sample('CLmax')-cl)/condition.stall_width)),
        residual=float(residual),flow_replay_error=replay,control_replay=control_replay,
        per_beam=[dict(beam=m.beam.index,intervals=len(m.tm),CL=float(np.sum(force[beam==m.beam.index,2])/qs),CD=float(np.sum(force[beam==m.beam.index,0])/qs),
            CD_parts={k:float(np.sum(f[beam==m.beam.index,0])/qs) for k,f in [('vortex',vortex),('friction',friction),('pressure',pressure),('stall_leakage',leakage)]},
            maximum_normal_mach=float(max(mach[beam==m.beam.index]))) for m in meshes],
        solve_seconds=elapsed,total_seconds=time.monotonic()-begin,maxrss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,primary_passes_added=0,
        artifacts={p.name:sha(p) for p in folder.iterdir()})
    write(folder/'report.json',report);signal.alarm(0)
    print(json.dumps({k:report[k] for k in ('status','reference_error_percent','passing_scalar_targets','maximum_normal_mach','minimum_stall_margin_widths','total_seconds','maxrss_kib')}),flush=True)


def summarize(out):
    plan=read(out/'plan.json');check(plan['pins']);check(plan['generated_pins'],out);rows=[]
    for case in plan['cases']:
        folder=out/case['id'];r=read(folder/'report.json');assert r['case']==case;check(r['artifacts'],folder)
        rows.append(dict(**r,report_sha256=sha(folder/'report.json')))
    groups={name:dict(computed=sum(r['status']=='COMPUTED_DIAGNOSTIC' for r in rows if r['case']['variant']==name),
                     passing_scalar_targets=sum(r['passing_scalar_targets'] for r in rows if r['case']['variant']==name),required_scalar_targets=14) for name in plan['variants']}
    write(out/'analysis.json',dict(observed_utc=utc(),cases=rows,groups=groups,plan_sha256=sha(out/'plan.json'),primary_passes_added=0))
    print(json.dumps(groups,indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    action=parser.add_mutually_exclusive_group(required=True);action.add_argument('--prepare',action='store_true');action.add_argument('--case');action.add_argument('--summarize',action='store_true')
    args=parser.parse_args();out=args.output.resolve()
    if args.prepare:prepare(out)
    elif args.case:run(out,args.case)
    else:summarize(out)
