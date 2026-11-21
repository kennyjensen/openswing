"""Compare both remaining ST-1 coupled-blade orientations, one small job at a time."""
import argparse
from collections import Counter
from decimal import Decimal
import math
from pathlib import Path
import re
import resource
import time

import verify_sa14_defaults as common

ROOT=common.ROOT
PRIOR=ROOT/'artifacts/isae/st1-coupled-curve-20261109'
MASSES=[0.,.02,.05,.1,.2,.3,.4]
CASES={'0':dict(twist=0.,producer_line=171,mass_line=169),
       '45':dict(twist=-45.,producer_line=245,mass_line=243)}


def extract(eps):
    raw=eps.read_text()
    pattern=(r'\[([\d.]+) 0 0 ([\d.]+) ([-\d.]+) ([-\d.]+)\] CT\n0\.149 GC\n/[^\n]+ F\nGS\n'
        r'\[1 0 0 1 0 0\] CT\n[^\n]+\n1 -1 scale\n\(([-\d.]+)\) t')
    ticks=[dict(x=float(m[3]),y=float(m[4]),value=float(m[5])) for m in re.finditer(pattern,raw)]
    xgroup=Counter(t['y'] for t in ticks).most_common(1)[0][0]
    ygroup=Counter(t['x'] for t in ticks).most_common(1)[0][0]
    axes={}
    for name,coordinate,group in (('x','x',[t for t in ticks if t['y']==xgroup]),('y','y',[t for t in ticks if t['x']==ygroup])):
        group=sorted(group,key=lambda t:t['value']);assert len(group)>=4
        first,last=group[0],group[-1]
        scale=(last[coordinate]-first[coordinate])/(last['value']-first['value'])
        offset=first[coordinate]-scale*first['value']
        assert max(abs(t[coordinate]-(offset+scale*t['value'])) for t in group)<1.1e-5
        axes[name]=dict(scale=scale,offset=offset,ticks=group)
    blocks=re.findall(r'GS\n(.*?)\nGR',raw,re.S);selections=[]
    for i,block in enumerate(blocks):
        points=re.findall(r'^([-\d.]+) ([-\d.]+) [ML]$',block,re.M)
        if '0 0 1 RC\n[8 8] 0 setdash' in block and len(points)==7:
            selections.append([blocks[i],blocks[i+1],blocks[i+2]])
    assert len(selections)==1;selected=selections[0]
    assert '1 0 0 RC\n[8 2 4 2] 0 setdash' in selected[1]
    assert 'setdash' not in selected[2] and '2 LW' in selected[2]
    targets=[]
    for name,block in zip('xyz',selected,strict=True):
        assert block.startswith('[0.75 0 0 0.75 0 0] CT\n')
        points=re.findall(r'^([-\d.]+) ([-\d.]+) [ML]$',block,re.M);assert len(points)==7
        for i,(x,y) in enumerate(points):
            mass=(.75*float(x)-axes['x']['offset'])/axes['x']['scale'];assert abs(mass-MASSES[i])<1e-12
            value=(.75*float(y)-axes['y']['offset'])/axes['y']['scale']
            half=float(Decimal(5).scaleb(Decimal(y).as_tuple().exponent-1))
            targets.append(dict(axis=name,index=i,mass=MASSES[i],expected=value,original_y_token=y,
                original_absolute_tolerance=(.75*half+1.1e-5)/abs(axes['y']['scale']),
                source_path=eps.relative_to(ROOT).as_posix(),
                source_line=raw[:raw.index(block)].count('\n')+block[:block.index(x+' '+y)].count('\n')+1))
    return dict(axes=axes,targets=targets)


def prepare(out):
    previous=common.read(PRIOR/'plan.json');common.authenticate(previous['pins'])
    original=ROOT/previous['original_model'];source=original.read_text()
    assert source.rstrip().endswith('\nEngine')
    producer=(original.parent/'Post_analysis.m').read_text().splitlines()
    pins=dict(previous['pins'])
    for path in (Path(__file__),PRIOR/'plan.json',PRIOR/'summary.json'):
        pins[path.relative_to(ROOT).as_posix()]=common.sha(path)
    cases={};jobs=[]
    for name,config in CASES.items():
        assert producer[config['mass_line']-1]=='M = [0 0.02 0.05 0.1 0.2 0.3 0.4];'
        assert f"change_mass('[45_0]_3s.asw',M(i),{int(config['twist'])})" in producer[config['producer_line']-1]
        eps=original.parent/f'images/[45_0]3s_theta_{name}.eps'
        cases[name]=dict(**config,**extract(eps))
        for path in (eps,eps.with_suffix('.pdf')):pins[path.relative_to(ROOT).as_posix()]=common.sha(path)
        for i,mass in enumerate(MASSES):jobs.append(dict(case=name,index=i,mass=mass,nominal=100,scope='curve'))
    for name in CASES:jobs.append(dict(case=name,index=6,mass=.4,nominal=200,scope='refinement'))
    common.write(out/'plan.json',dict(observed_utc=common.utc(),pins=pins,cases=cases,jobs=jobs,
        original_model=original.relative_to(ROOT).as_posix(),relative_tolerance=.05,
        source_transform='Append End to empty Engine; change only mass and twist multiplier exactly as the original change_mass.m calls.',
        required_new_curve_values=42,prior_curve_values=21,primary_archive_passes_added=0,
        qualification='Magnitude of loaded minus self-weight-only body sensor displacement. Original source angles differ in sign from plot titles. '
        'Two fine loaded states are separate mesh diagnostics and add no reference votes.',
        limits=dict(blas_threads=1,address_space_mib=512,cpu_seconds=15,wall_seconds=25)))
    print('Prepared 14 curve states, 42 reference coordinates, and two separate loaded refinements.')


def run(out,index):
    plan=common.read(out/'plan.json');common.authenticate(plan['pins'])
    job=plan['jobs'][index];config=plan['cases'][job['case']]
    folder=out/f'job-{index:02d}';folder.mkdir()
    original=(ROOT/plan['original_model']).read_text();lines=original.splitlines(keepends=True)
    im=next(i for i,line in enumerate(lines) if line.strip()=='#  MASS')+1
    it=next(i for i,line in enumerate(lines) if line.strip()=='# twist')+1
    assert lines[im].split()==['1','-0.280','0.0','-0.280','0.0','0.4'] and lines[it].split()==['*1.0','45']
    fields=lines[im].split();fields[-1]=str(job['mass']);lines[im]=' '.join(fields)+'\n'
    lines[it]=f"*1.0 {config['twist']}\n";source=''.join(lines)+'End\n'
    (folder/'model.asw').write_text(source)
    import numpy as np
    from openswing.asw import parse_asw
    from openswing.bridge import dispatch
    model=parse_asw(source,beam_interpolation='drela-segspl-v1');assert not model.diagnostics
    beam=model.beams[0];samples=np.array([-.28,0,.28])
    assert np.all(beam.value('twist',samples)==config['twist'])
    for field,value in dict(EIcc=.522,GJ=.368,EInn=298.,EIcs=.102,mg=.07*9.81).items():
        np.testing.assert_allclose(beam.value(field,samples),value,rtol=2e-15,atol=0)
    for field in ('Cea','Nea','Cta','Nta','Ccg','Ncg','Dmg'):assert np.all(beam.value(field,samples)==0)
    request=dict(action='solve',mode='structural',source=source,
        panels=dict(default=job['nominal'],beams={'1':dict(count=job['nominal'],spacing='cosine')}),
        numerics=dict(beam_interpolation='drela-segspl-v1',structural_operator='drela-steady-section-v1'),
        gravity=[0.,0.,-9.81],loads=[],tolerance=1e-8,continuation_steps=4)
    common.write(folder/'request.json',request)
    started=time.monotonic();result=dispatch(request);seconds=time.monotonic()-started
    common.write(folder/'result.json',result)
    nodes=sorted(result['nodes'],key=lambda n:n['t']);t=np.array([n['t'] for n in nodes]);r=np.array([n['position'] for n in nodes])
    assert len(nodes)==job['nominal']+2 and t[0]==-.28 and t[-1]==.28 and -.22 in t
    mass=np.zeros(len(t));half=.07*np.diff(t)/2;mass[:-1]+=half;mass[1:]+=half;mass[0]+=job['mass']
    force=mass[:,None]*np.array([0.,0.,-9.81]);moment=np.cross(r,force).sum(axis=0)
    def relative(a,b):
        a,b=np.asarray(a),np.asarray(b)
        return float(np.max(abs(a-b))/(1+max(np.max(abs(a)),np.max(abs(b)))))
    checks=dict(residual=result['residual'],force_balance=relative(result['force_balance'],[0.,0.,0.]),
        moment_balance=relative(result['moment_balance'],[0.,0.,0.]),
        independent_force=relative(force.sum(axis=0),result['applied_force']),independent_moment=relative(moment,result['applied_moment']),
        clamp_position=float(np.max(abs(r[-1]-[0.,.28,0.]))),
        clamp_rotation=float(np.max(abs(np.asarray(nodes[-1]['rotation'])-np.eye(3)))))
    sensor=result['sensors'][0];assert sensor['beam']==1 and sensor['t']==-.22
    np.testing.assert_allclose(sensor['anchor_position_body'],r[np.where(t==-.22)[0][0]],atol=1e-12,rtol=0)
    assert result['converged'] and checks['residual']<1e-8
    assert max(checks[k] for k in ('force_balance','moment_balance'))<1e-7
    assert max(checks[k] for k in ('independent_force','independent_moment'))<2e-10
    assert max(checks[k] for k in ('clamp_position','clamp_rotation'))<1e-10
    common.authenticate(plan['pins'])
    common.write(folder/'report.json',dict(observed_utc=common.utc(),job=job,checks=checks,
        position=sensor['anchor_position_body'],seconds=seconds,peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        plan_sha256=common.sha(out/'plan.json'),artifacts={p.name:common.sha(p) for p in folder.iterdir() if p.is_file()}))
    print(dict(job_index=index,**job,position=sensor['anchor_position_body'],residual=checks['residual'],seconds=seconds))


def summarize(out):
    plan=common.read(out/'plan.json');common.authenticate(plan['pins']);reports=[]
    for i,job in enumerate(plan['jobs']):
        folder=out/f'job-{i:02d}';r=common.read(folder/'report.json')
        assert r['job']==job and r['plan_sha256']==common.sha(out/'plan.json')
        for name,digest in r['artifacts'].items():assert common.sha(folder/name)==digest
        reports.append(r)
    cases={};rows=[]
    for name,config in plan['cases'].items():
        curve=[r for r in reports if r['job']['case']==name and r['job']['scope']=='curve']
        assert [r['job']['mass'] for r in curve]==MASSES
        zero=curve[0]['position'];selected=[]
        for target in config['targets']:
            axis='xyz'.index(target['axis']);predicted=abs(curve[target['index']]['position'][axis]-zero[axis])
            error=abs(predicted-target['expected']);limit=max(target['original_absolute_tolerance'],.05*abs(target['expected']))
            selected.append(dict(**target,case=name,predicted=predicted,error_m=error,passed=error<=limit,
                error_percent=None if target['index']==0 else 100*error/abs(target['expected'])))
        fine=next(r for r in reports if r['job']['case']==name and r['job']['scope']=='refinement')
        delta=math.dist(fine['position'],curve[-1]['position'])
        cases[name]=dict(passed=sum(r['passed'] for r in selected),required=len(selected),
            max_nonzero_error_percent=max(r['error_percent'] or 0 for r in selected),unloaded_position=zero,
            loaded_refinement_change_m=delta,loaded_refinement_change_percent_of_deflection=100*delta/math.dist(curve[-1]['position'],zero))
        rows.extend(selected)
    previous=common.read(PRIOR/'summary.json')
    result=dict(observed_utc=common.utc(),new_required=len(rows),new_passed=sum(r['passed'] for r in rows),
        combined_required=previous['required']+len(rows),combined_passed=previous['passed']+sum(r['passed'] for r in rows),
        cases=cases,rows=rows,prior_summary_sha256=common.sha(PRIOR/'summary.json'),plan_sha256=common.sha(out/'plan.json'),
        primary_archive_passes_added=0,production_physics_changed=False,complete_family_validation=False)
    common.write(out/'summary.json',result);print({k:v for k,v in result.items() if k!='rows'})


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('action',choices=('prepare','run','summary'))
    parser.add_argument('--output',type=Path,required=True);parser.add_argument('--index',type=int)
    args=parser.parse_args();common.bounded()
    if args.action=='prepare':prepare(args.output.resolve())
    elif args.action=='run':run(args.output.resolve(),args.index)
    else:summarize(args.output.resolve())
