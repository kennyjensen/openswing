"""Conditional SA-13 outline-body calculations; geometry is not an original input."""
from pathlib import Path
import hashlib,json,os,sys,time
import numpy as np
from scipy.interpolate import CubicSpline
from numpy.polynomial import Polynomial

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'scripts'))
from openswing.asw import parse_asw
from openswing.aero import FlightCondition,solve_rigid,AnalysisError
from openswing.flow_survey import survey
from isae_sa13_reference import REVISION,sha,asw_source
D=ROOT/'docs/validation'


def key(q):return hashlib.sha256(json.dumps(q,sort_keys=True).encode()).hexdigest()


def requests(cases):
    rows=[]
    for c in cases:
        angles={'r33':[0.,10.],'r101':[0.,10.],'rs1':[0.,9.,10.],'pressure':[0.]}[c['name']]
        for n in [32,64,128,256]:
            for a in angles:rows.append(dict(case=c['name'],panels=n,alpha=a,length=1.,surface_offset=1e-6))
            if c['name']=='r101':rows.append(dict(case=c['name'],panels=n,alpha=10.,length=33.01*.0254,surface_offset=1e-6))
        if c['name']=='pressure':
            for offset in [1e-4,1e-8]:rows.append(dict(case=c['name'],panels=128,alpha=0.,length=1.,surface_offset=offset))
    assert len(rows)==38
    return rows


def compute(case,q):
    length=q['length'];source=asw_source(case['name'],case['outline'],length)
    model=parse_asw(source);condition=FlightCondition(speed=10.,alpha=q['alpha'],mach=0.)
    result=solve_rigid(model,condition,q['panels'])
    assert result['converged'] and result['residual']<=1e-8 and result['lifting_panels']==0
    force=np.array(result['force']);moment=np.array(result['moment']);qs=50.*model.reference[0,0]
    a=np.deg2rad(q['alpha']);wind=np.array([np.cos(a),0,np.sin(a)]);lift=np.array([-np.sin(a),0,np.cos(a)])
    assert max(abs(force@wind/qs-result['CD']),abs(force@lift/qs-result['CL']),abs(moment[1]/qs/length-result['Cm']))<2e-12
    assert abs(result['CD']-result['CDbody']-result['CDp']-result['CDam'])<2e-12
    # Independently construct the declared natural cubic interpolant, then
    # integrate its squared polynomial exactly rather than reuse body quadrature.
    tab=np.array(case['outline']['normalized_table']);radius=CubicSpline(tab[:,0],tab[:,1]*length,bc_type='natural')
    volume=0.
    for i,h in enumerate(np.diff(radius.x)):
        p=Polynomial(radius.c[:,i][::-1]);integral=(p*p).integ()
        volume+=np.pi*length*(integral(h)-integral(0.))
    exact_moment=100.*np.sin(a)*np.cos(a)*volume
    diameter=case['outline']['normalized_diameter']*length
    strips=result['strips']
    x=np.array([s['t'] for s in strips]);density=np.array([s['force'][2]/s['length']/50./diameter for s in strips])
    pointwise=np.sin(2*a)*2*np.pi*radius(x)*radius(x,1)/length/diameter
    profile=[dict(t=float(t),force=s['force'],moment=s['moment'],length=s['length'],transverse_density=float(f),
        independent_pointwise_density=float(g)) for t,s,f,g in zip(x,strips,density,pointwise)]
    points=[]
    for i,(raw_x,observed) in enumerate(case['series'][0]['xy']):
        if raw_x is None or observed is None:continue
        t=(raw_x-case['outline']['nose'])/case['outline']['raw_reconstructed_length']
        p=dict(source_index=i,raw_x=raw_x,t=t,observed=observed)
        if not 0<t<1:p['status']='outside_reconstructed_hull'
        elif case['name']=='pressure':p['status']='pressure_sample_pending'
        else:
            p['independent_pointwise_density']=float(np.sin(2*a)*2*np.pi*radius(t)*radius(t,1)/length/diameter)
            if x[0]<=t<=x[-1]:p.update(status='computed',transverse_density=float(np.interp(t,x,density)))
            else:p['status']='outside_native_strip_midpoint_range'
        points.append(p)
    out=dict(coefficients={k:result[k] for k in ['CL','CD','Cm','CY','Cl','Cn','CDi','CDbody','CDp']},
        residual=result['residual'],force=force.tolist(),moment=moment.tolist(),actual_intervals=len(strips),
        profiles=profile,measured_points=points,volume=float(volume),reference_diameter=diameter,
        independent_closed_body_moment=float(exact_moment),normalized_net_force_error=float(np.linalg.norm(force)/qs),
        normalized_moment_error=float(abs(moment[1]-exact_moment)/qs/length),
        interpolation='Natural cubic through the explicitly reconstructed outline; source geometry uncertainty remains.',
        source_sha256=hashlib.sha256(source.encode()).hexdigest())
    if case['name']=='pressure':
        # The public survey deliberately masks points on/inside a body. Sample
        # a stated positive relative offset and check its sensitivity separately.
        target=np.unique(np.r_[np.linspace(.005,.995,199),[p['t'] for p in points if p['status']=='pressure_sample_pending']])
        positions=np.c_[target*length,np.zeros(len(target)),radius(target)*(1+q['surface_offset'])]
        flow=survey(model,positions=positions,condition=condition,panels=q['panels'])
        assert all(flow['valid']) and not any(flow['inside_body'])
        velocity=np.array(flow['velocity']['relative']);cp=100.*(1.-np.sum(velocity*velocity,axis=1)/100.)
        out['pressure_profile']=[dict(t=float(t),position=pos.tolist(),velocity=v.tolist(),Cp_percent=float(c)) for t,pos,v,c in zip(target,positions,velocity,cp)]
        for p in points:
            if p['status']!='pressure_sample_pending':continue
            i=np.flatnonzero(target==p['t']);assert len(i)==1
            p.update(status='computed',predicted_Cp_percent=float(cp[i[0]]))
        out['flow_survey']=flow
    return out


def main():
    source_path=D/'isae-sa13-sources.json';sources=json.loads(source_path.read_text())
    modules={p.name:sha(p) for p in (ROOT/'openswing').glob('*.py')}
    assert sources['modules']==modules and sources['script_sha256']==sha(ROOT/'scripts/isae_sa13_reference.py')
    provenance=dict(revision=REVISION,modules=modules,script_sha256=sha(Path(__file__)),
        source_report_sha256=sha(source_path),reference_script_sha256=sha(ROOT/'scripts/isae_sa13_reference.py'))
    folder=ROOT/'.reference/isae-sa13-runs'/hashlib.sha256(json.dumps(provenance,sort_keys=True).encode()).hexdigest()
    folder.mkdir(parents=True,exist_ok=True);identity=folder/'identity.json'
    if identity.exists():assert json.loads(identity.read_text())==provenance
    else:identity.write_text(json.dumps(provenance,indent=2)+'\n')
    rows=[]
    for q in requests(sources['cases']):
        path=folder/(key(q)+'.json');case=next(c for c in sources['cases'] if c['name']==q['case'])
        if path.exists():
            row=json.loads(path.read_text());assert row['specification']==q
        else:
            start=time.monotonic()
            try:row=dict(specification=q,status='computed',result=compute(case,q))
            except (AnalysisError,ValueError) as exc:row=dict(specification=q,status='rejected',error=str(exc),details=getattr(exc,'details',None))
            row['seconds']=time.monotonic()-start
            temporary=path.with_suffix(f'.{os.getpid()}.tmp');temporary.write_text(json.dumps(row,indent=2)+'\n');temporary.replace(path)
        row.update(cache_path=path.relative_to(ROOT).as_posix(),cache_sha256=sha(path));rows.append(row)
        print(len(rows),'/',38,q,row['status'],flush=True)
    assert modules=={p.name:sha(p) for p in (ROOT/'openswing').glob('*.py')}
    out=dict(status='CONDITIONAL_GEOMETRY_COMPUTATIONS_COMPLETE_COMPARISONS_PENDING',provenance=provenance,rows=rows,
        computed=sum(r['status']=='computed' for r in rows),rejected=sum(r['status']=='rejected' for r in rows),
        protocol=['All four reconstructed bodies at32/64/128/256 requested intervals, zero PG and zero profile drag; speed10,density1 are normalization choices, not recovered tunnel settings.',
            'R33/R101 alpha0/10, RS1 alpha0/9/10, pressure alpha0. R101 physical length33.01in is a separate scale check.',
            'Body load density is native strip-average transverse force/(q*D*strip length), with piecewise linear interpolation only between strip midpoints. Independent pointwise values are labeled separately.',
            'Pressure uses the public flow-survey API at relative radius offsets1e-6, with1e-4/1e-8 sensitivities atN128. No interior mask or core law is bypassed.',
            'Pressure is100Cp. No experimental force, pressure, angle shift or global coefficient was fitted.'],limitations=sources['limitations'])
    temporary=D/'isae-sa13.json.tmp';temporary.write_text(json.dumps(out,indent=2)+'\n');temporary.replace(D/'isae-sa13.json')
    print('COMPLETE',out['computed'],out['rejected'],flush=True)


if __name__=='__main__':main()
