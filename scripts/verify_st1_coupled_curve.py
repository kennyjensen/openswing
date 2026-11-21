"""Recover and compare the seven-point ASWING ST-1 coupled-blade EPS curve.

Axes and polyline coordinates come from the original vector file, not fitted
solver values. One foreground solve per invocation; original mass sweep only.
"""
import argparse
from collections import Counter
from decimal import Decimal
import json
from pathlib import Path
import re
import resource
import time

import verify_sa14_defaults as common

ROOT=common.ROOT
PARENT=ROOT/'artifacts/isae/st1-static-layouts-20261109'
MASSES=[0.,.02,.05,.1,.2,.3,.4]


def prepare(out):
    parent=common.read(PARENT/'plan.json'); common.authenticate(parent['pins'])
    job=parent['jobs'][2]; original=ROOT/job['archive_job']['model_path']
    source=original.read_text(); assert source.rstrip().endswith('\nEngine')
    eps=original.parent/'images/[45_0]3s_theta_m45.eps';raw=eps.read_text()
    pattern=(r'\[([\d.]+) 0 0 ([\d.]+) ([-\d.]+) ([-\d.]+)\] CT\n0\.149 GC\n/[^\n]+ F\nGS\n'
        r'\[1 0 0 1 0 0\] CT\n[^\n]+\n1 -1 scale\n\(([-\d.]+)\) t')
    ticks=[dict(scale_x=float(m[1]),scale_y=float(m[2]),x=float(m[3]),y=float(m[4]),value=float(m[5]))
        for m in re.finditer(pattern,raw)]
    xgroup=Counter(t['y'] for t in ticks).most_common(1)[0][0]
    ygroup=Counter(t['x'] for t in ticks).most_common(1)[0][0]
    xt=sorted([t for t in ticks if t['y']==xgroup],key=lambda t:t['value'])
    yt=sorted([t for t in ticks if t['x']==ygroup],key=lambda t:t['value'])
    assert len(xt)==6 and len(yt)==7
    def axis(group,coordinate):
        first,last=group[0],group[-1]
        scale=(last[coordinate]-first[coordinate])/(last['value']-first['value'])
        offset=first[coordinate]-scale*first['value']
        assert max(abs(t[coordinate]-(offset+scale*t['value'])) for t in group)<1.1e-5
        return dict(scale=scale,offset=offset,ticks=group)
    axes=dict(x=axis(xt,'x'),y=axis(yt,'y'))
    blocks=re.findall(r'GS\n(.*?)\nGR',raw,re.S)
    selected=[]
    for i,block in enumerate(blocks):
        points=re.findall(r'^([-\d.]+) ([-\d.]+) [ML]$',block,re.M)
        if '0 0 1 RC\n[8 8] 0 setdash' in block and len(points)==7:
            selected=[blocks[i],blocks[i+1],blocks[i+2]]
    assert len(selected)==3 and '1 0 0 RC\n[8 2 4 2] 0 setdash' in selected[1]
    assert 'setdash' not in selected[2] and '2 LW' in selected[2]
    targets=[]
    for axis_name,block in zip('xyz',selected,strict=True):
        assert block.startswith('[0.75 0 0 0.75 0 0] CT\n')
        points=re.findall(r'^([-\d.]+) ([-\d.]+) [ML]$',block,re.M)
        assert len(points)==7
        for i,(x,y) in enumerate(points):
            mass=(.75*float(x)-axes['x']['offset'])/axes['x']['scale']
            assert abs(mass-MASSES[i])<1e-12
            value=(.75*float(y)-axes['y']['offset'])/axes['y']['scale']
            half=float(Decimal(5).scaleb(Decimal(y).as_tuple().exponent-1))
            # Printed ordinate half-place, plus a conservative 1.1e-5 axis
            # coordinate envelope from the independently checked tick labels.
            absolute=(.75*half+1.1e-5)/abs(axes['y']['scale'])
            targets.append(dict(axis=axis_name,index=i,mass=mass,expected=value,
                original_y_token=y,source_path=eps.relative_to(ROOT).as_posix(),
                source_line=raw[:raw.index(block)].count('\n')+block[:block.index(x+' '+y)].count('\n')+1,
                original_absolute_tolerance=absolute))
    producer=(original.parent/'Post_analysis.m').read_text().splitlines()
    assert producer[312]=='M = [0 0.02 0.05 0.1 0.2 0.3 0.4];'
    assert "change_mass('[45_0]_3s.asw',M(i),45)" in producer[314]
    pins=dict(parent['pins'])
    for path in (Path(__file__),PARENT/'plan.json',PARENT/'job-2/report.json',PARENT/'job-2/result.json',
                 eps,eps.with_suffix('.pdf')):
        pins[path.relative_to(ROOT).as_posix()]=common.sha(path)
    common.write(out/'plan.json',dict(observed_utc=common.utc(),pins=pins,axes=axes,targets=targets,
        original_model=original.relative_to(ROOT).as_posix(),masses=MASSES,
        plotted_observable='Absolute difference between each loaded and self-weight-only sensor position, as in Post_analysis.m lines329-337.',
        explicit_source_transform='Terminate empty Engine block; replace only the tip-mass field using the original producer mass list. Keep 45-degree twist and EIcs=0.102.',
        numerical_gates=dict(residual=1e-8,relative_balance=1e-7,independent_wrench=2e-10),
        relative_tolerance=.05,primary_archive_passes_added=0,
        qualification='Independent published curve reference, distinct from the mismatching same-name raw text snapshot; no aggregate addition to the 200 archive slots.'))
    print('Prepared all 21 original plotted coordinates, seven masses, without solver-based calibration.')


def run(out,index):
    plan=common.read(out/'plan.json');common.authenticate(plan['pins'])
    folder=out/f'job-{index}';folder.mkdir();mass=plan['masses'][index]
    if index==6:
        parent=common.read(PARENT/'job-2/report.json')
        for name,digest in parent['artifacts'].items():assert common.sha(PARENT/'job-2'/name)==digest
        result=common.read(PARENT/'job-2/result.json')
        common.write(folder/'result.json',result)
        checks=parent['numerical_checks'];seconds=0.;calls=0
    else:
        source=(ROOT/plan['original_model']).read_text()
        lines=source.splitlines(keepends=True)
        i=next(i for i,line in enumerate(lines) if line.strip()=='#  MASS')+1
        assert lines[i].split()==['1','-0.280','0.0','-0.280','0.0','0.4']
        fields=lines[i].split();fields[-1]=str(mass);lines[i]=' '.join(fields)+'\n'
        source=''.join(lines)+'End\n'
        (folder/'model.asw').write_text(source)
        import numpy as np
        from openswing.bridge import dispatch
        request=dict(action='solve',mode='structural',source=source,
            panels=dict(default=100,beams={'1':dict(count=100,spacing='cosine')}),
            numerics=dict(beam_interpolation='drela-segspl-v1',structural_operator='drela-steady-section-v1'),
            gravity=[0.,0.,-9.81],loads=[],tolerance=1e-8,continuation_steps=4)
        common.write(folder/'request.json',request)
        started=time.monotonic();result=dispatch(request);seconds=time.monotonic()-started;calls=1
        common.write(folder/'result.json',result)
        nodes=sorted(result['nodes'],key=lambda n:n['t'])
        t=np.array([n['t'] for n in nodes]);r=np.array([n['position'] for n in nodes])
        weights=np.zeros(len(t));half=.07*np.diff(t)/2
        weights[:-1]+=half;weights[1:]+=half;weights[0]+=mass
        force=weights[:,None]*np.array([0.,0.,-9.81])
        independent_force=force.sum(axis=0);independent_moment=np.cross(r,force).sum(axis=0)
        def relative(a,b):
            a,b=np.asarray(a),np.asarray(b)
            return float(np.max(abs(a-b))/(1+max(np.max(abs(a)),np.max(abs(b)))))
        checks=dict(residual=result['residual'],force_balance=relative(result['force_balance'],[0.,0.,0.]),
            moment_balance=relative(result['moment_balance'],[0.,0.,0.]),
            independent_force=relative(independent_force,result['applied_force']),
            independent_moment=relative(independent_moment,result['applied_moment']))
    assert result['converged'] and checks['residual']<1e-8
    assert checks['force_balance']<1e-7 and checks['moment_balance']<1e-7
    assert checks['independent_force']<2e-10 and checks['independent_moment']<2e-10
    common.write(folder/'report.json',dict(observed_utc=common.utc(),mass=mass,
        position=result['sensors'][0]['anchor_position_body'],checks=checks,seconds=seconds,cold_solves=calls,
        peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,plan_sha256=common.sha(out/'plan.json'),
        artifacts={p.name:common.sha(p) for p in folder.iterdir() if p.is_file()}))
    print(dict(index=index,mass=mass,position=result['sensors'][0]['anchor_position_body'],checks=checks,seconds=seconds))


def summarize(out):
    plan=common.read(out/'plan.json');common.authenticate(plan['pins'])
    reports=[]
    for i in range(7):
        folder=out/f'job-{i}';r=common.read(folder/'report.json')
        assert r['plan_sha256']==common.sha(out/'plan.json')
        for name,digest in r['artifacts'].items():assert common.sha(folder/name)==digest
        reports.append(r)
    zero=reports[0]['position'];rows=[]
    for target in plan['targets']:
        j='xyz'.index(target['axis']);predicted=abs(reports[target['index']]['position'][j]-zero[j])
        error=abs(predicted-target['expected']);limit=max(target['original_absolute_tolerance'],.05*abs(target['expected']))
        rows.append(dict(**target,predicted=predicted,error_m=error,passed=error<=limit,
            error_percent=None if target['mass']==0 else 100*error/abs(target['expected'])))
    common.write(out/'summary.json',dict(observed_utc=common.utc(),required=21,passed=sum(r['passed'] for r in rows),
        max_nonzero_error_percent=max(r['error_percent'] or 0 for r in rows),rows=rows,
        unloaded_position=zero,cold_solves=sum(r['cold_solves'] for r in reports),
        primary_archive_passes_added=0,plan_sha256=common.sha(out/'plan.json')))
    print('curve',sum(r['passed'] for r in rows),'/ 21; largest nonzero error',max(r['error_percent'] or 0 for r in rows),'percent')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('prepare','run','summary'))
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--index',type=int)
    args=parser.parse_args();common.bounded()
    if args.action=='prepare':prepare(args.output.resolve())
    elif args.action=='run':run(args.output.resolve(),args.index)
    else:summarize(args.output.resolve())
