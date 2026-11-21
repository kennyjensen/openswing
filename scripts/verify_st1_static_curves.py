"""Remaining six published ST-1 static curves; capped, serial per-state execution."""
import argparse
from collections import Counter
from decimal import Decimal
import math
from pathlib import Path
import re
import resource
import time

import verify_sa14_defaults as common

ROOT = common.ROOT
BASE = ROOT/'reference/isae-validation/f62943df20e9e4d7d9f50e070477b22426b5f865/3 - Structure/CASE - ST1 High aspect ratio/Static_deflection'
PRIOR = ROOT/'artifacts/isae/st1-coupled-orientations-20261109'
CASES = {
    'cross-0': dict(model='[0_90]_3s', image='[0_90]3s_theta_0', transform='*1.0 0', mass_line=22, call_line=24),
    'cross-45': dict(model='[0_90]_3s', image='[0_90]3s_theta_45', transform='*1.0 -45', mass_line=94, call_line=96),
    'angle-0': dict(model='[20_m70_20]_2a', image='[20_m70_m70_50]3s_theta_0', transform='*1.0 0', mass_line=388, call_line=390),
    'angle-45': dict(model='[20_m70_20]_2a', image='[20_m70_m70_50]3s_theta_45', transform='+0.0 45', mass_line=461, call_line=463),
    'twisted-0': dict(model='[45_0]_3a', image='[45_0]3a_theta_0', transform='+0.0 -45', mass_line=532, call_line=534),
    'twisted-45': dict(model='[45_0]_3a', image='[45_0]3a_theta_45', transform='+0.0 0', mass_line=607, call_line=609),
}


def plan_path(out):
    corrected = out/'plan-v2.json'
    return corrected if corrected.exists() else out/'plan.json'


def affine(ticks, coordinate, precision):
    ticks = sorted(ticks, key=lambda t: t['value'])
    first, last = ticks[0], ticks[-1]
    scale = (last[coordinate]-first[coordinate])/(last['value']-first['value'])
    offset = first[coordinate]-scale*first['value']
    residual = max(abs(t[coordinate]-offset-scale*t['value']) for t in ticks)
    return dict(scale=scale, offset=offset, ticks=ticks,
                calibration_uncertainty=precision+residual, tick_fit_residual=residual)


def extract(eps, masses):
    raw = eps.read_text()
    if '%%Creator: cairo' in raw:
        # Axis calibration is read from the original labelled tick marks, never
        # from a predicted displacement. Cairo's tick non-collinearity is retained
        # as reference uncertainty, in addition to the printed coordinate precision.
        flat = eps.stem.endswith('_0')
        xs = [58.484, 138.172, 217.859, 297.547, 377.234] if flat else [53.234, 119.387, 185.535, 251.688, 317.836, 383.984]
        ys = [-268.008, -226.133, -184.258, -142.383, -100.508, -58.633, -16.758] if flat else [-261.676, -184.051, -106.43, -28.809]
        values = [-.05, 0, .05, .1, .15, .2, .25] if flat else [0, .05, .1, .15]
        for x in xs: assert re.search(rf'{re.escape(str(x))} -[\d.]+ m', raw)
        for y, value in zip(ys, values, strict=True):
            assert f'{y:g} m' in raw and f'({value:g})Tj' in raw
        axes = dict(x=affine([dict(x=x, value=i*.1) for i, x in enumerate(xs)], 'x', .0005),
                    y=affine([dict(y=y, value=v) for y, v in zip(ys, values)], 'y', .0005))
        block = raw[raw.index('0 0 1 rg\n1.5 w\n2 j\n[ 6 6] 0 d'):]
        paths = re.findall(r'q 1 0 0 -1 0 0 cm\n(.*?) S Q', block, re.S)[:3]
        assert '1 0 0 rg\n[ 6 1.5 3 1.5] 0 d' in block
        point_scale = 1.
        points = [re.findall(r'([-\d.]+) ([-\d.]+)\s+[ml]', p) for p in paths]
        assert [len(p) for p in points] == ([2, 8, 8] if flat else [6, 6, 6])
        compressed_zero = flat
    else:
        pattern = (r'\[([\d.]+) 0 0 ([\d.]+) ([-\d.]+) ([-\d.]+)\] CT\n0\.149 GC\n/[^\n]+ F\nGS\n'
                   r'\[1 0 0 1 0 0\] CT\n[^\n]+\n1 -1 scale\n\(([-\d.]+)\) t')
        ticks = [dict(x=float(m[3]), y=float(m[4]), value=float(m[5])) for m in re.finditer(pattern, raw)]
        xgroup = Counter(t['y'] for t in ticks).most_common(1)[0][0]
        ygroup = Counter(t['x'] for t in ticks).most_common(1)[0][0]
        axes = dict(x=affine([t for t in ticks if t['y']==xgroup], 'x', 1e-5),
                    y=affine([t for t in ticks if t['x']==ygroup], 'y', 1e-5))
        assert max(a['tick_fit_residual'] for a in axes.values()) < 2.1e-5
        blocks = re.findall(r'GS\n(.*?)\nGR', raw, re.S)
        selected = [i for i,b in enumerate(blocks) if '0 0 1 RC\n[' in b and 'setdash' in b
                    and len(re.findall(r'^[-\d.]+ [-\d.]+ [ML]$', b, re.M)) == len(masses)]
        assert len(selected)==1
        paths = blocks[selected[0]:selected[0]+3]
        assert '1 0 0 RC\n[' in paths[1] and 'setdash' not in paths[2]
        point_scale = .75 if paths[0].startswith('[0.75 0 0 0.75 0 0] CT\n') else 1.
        points = [re.findall(r'^([-\d.]+) ([-\d.]+) [ML]$', p, re.M) for p in paths]
        assert all(len(p)==len(masses) for p in points)
        compressed_zero = False
    targets = []
    for axis, path, series in zip('xyz', paths, points, strict=True):
        if axis=='x' and compressed_zero:
            assert series[0][1]==series[-1][1]
            selected_points = [(None, series[0][1])]*len(masses)
        else: selected_points = series
        for i, (x,y) in enumerate(selected_points):
            half = float(Decimal(5).scaleb(Decimal(y).as_tuple().exponent-1))
            value = (point_scale*float(y)-axes['y']['offset'])/axes['y']['scale']
            if x is not None:
                mass = (point_scale*float(x)-axes['x']['offset'])/axes['x']['scale']
                xhalf = float(Decimal(5).scaleb(Decimal(x).as_tuple().exponent-1))
                assert abs(mass-masses[i]) <= (point_scale*xhalf+axes['x']['calibration_uncertainty'])/abs(axes['x']['scale'])+1e-12
            targets.append(dict(axis=axis, index=i, mass=masses[i], expected=value, original_y_token=y,
                point_scale=point_scale, original_absolute_tolerance=(point_scale*half+axes['y']['calibration_uncertainty'])/abs(axes['y']['scale']),
                compressed_zero_line=axis=='x' and compressed_zero,
                source_path=eps.relative_to(ROOT).as_posix(), source_line=raw[:raw.index(path)].count('\n')+1))
    return dict(axes=axes, targets=targets)


def derive(config, mass):
    original = (BASE/(config['model']+'.asw')).read_text()
    lines = original.splitlines(keepends=True)
    im = next(i for i,l in enumerate(lines) if l.strip()=='#  MASS')+1
    it = next(i for i,l in enumerate(lines) if l.strip()=='# twist')+1
    fields = lines[im].split(); assert fields[:5]==['1','-0.280','0.0','-0.280','0.0']
    fields[-1] = str(mass); lines[im] = ' '.join(fields)+'\n'
    lines[it] = config['transform']+'\n'
    repair = dict(empty_engine_terminated=original.rstrip().endswith('\nEngine'))
    if config['model']=='[0_90]_3s':
        i = next(i for i,l in enumerate(lines) if l.split()[:6]==['t','x','y','z','chord','Xax'])
        names = lines[i].split(); values = lines[i+1].split()
        assert len(names)==15 and len(values)==17 and values[-1]=='0.0' and values[0]=='*'
        repair.update(removed_unnamed_scale=values[-1], preserved_named_scales=dict(zip(names,values[1:-1],strict=True)))
        assert repair['preserved_named_scales']['mg']=='9.8100' and repair['preserved_named_scales']['mgnn']=='0.0'
        lines[i+1] = ' '.join(values[:-1])+'\n'
    return ''.join(lines)+('End\n' if repair['empty_engine_terminated'] else ''), repair


def prepare(out):
    previous = common.read(PRIOR/'plan.json'); common.authenticate(previous['pins'])
    pins = dict(previous['pins'])
    for path in (Path(__file__), PRIOR/'plan.json', PRIOR/'summary.json', BASE/'Post_analysis.m', BASE/'change_mass.m', BASE/'change_mass2.m'):
        pins[path.relative_to(ROOT).as_posix()] = common.sha(path)
    catalog = common.read(ROOT/'docs/validation/aswing-authoritative-sources.json')
    entry = next(e for e in catalog['files'] if e['id']=='isae-part-3')
    for field, key in [('local_pdf','sha256'), ('local_text','text_sha256')]:
        assert common.sha(ROOT/entry[field])==entry[key]; pins[entry[field]]=entry[key]
    producer = (BASE/'Post_analysis.m').read_text().splitlines()
    cases = {}; jobs = []
    for name, config in CASES.items():
        masses = [float(s) for s in re.fullmatch(r'M = \[(.*)\];', producer[config['mass_line']-1])[1].split()]
        helper = 'change_mass2' if config['transform'].startswith('+') else 'change_mass'
        angle = config['transform'].split()[1]
        assert f"{helper}('{config['model']}.asw',M(i),{angle})" in producer[config['call_line']-1]
        eps = BASE/'images'/(config['image']+'.eps')
        cases[name] = dict(**config, masses=masses, **extract(eps, masses))
        for path in (BASE/(config['model']+'.asw'), BASE/(config['model']+'.sh'), eps, eps.with_suffix('.pdf')):
            pins[path.relative_to(ROOT).as_posix()] = common.sha(path)
        for i,mass in enumerate(masses): jobs.append(dict(case=name,index=i,mass=mass,nominal=100,scope='curve'))
    for name,config in cases.items():
        jobs.append(dict(case=name,index=len(config['masses'])-1,mass=config['masses'][-1],nominal=200,scope='refinement'))
    assert len(jobs)==52 and sum(len(c['targets']) for c in cases.values())==138
    common.write(out/'plan.json',dict(observed_utc=common.utc(),pins=pins,cases=cases,jobs=jobs,
        new_curve_required=138,prior_curve_required=63,relative_tolerance=.05,primary_archive_passes_added=0,
        protocol='Exact postprocessor mass and twist operations; magnitudes of loaded minus own-weight-only sensor positions. '
                 'Only explicit empty-Engine terminators and deletion of the one unnamed trailing scale for [0_90]_3s. '
                 'Original named scales, stiffnesses, geometry, gravity and sensor unchanged. No experimental values used as targets.',
        limits=dict(blas_threads=1,address_space_mib=512,cpu_seconds=15,wall_seconds=25)))
    print('Prepared 46 curve states, 138 reference coordinates and six separate loaded refinements.')


def run(out,index):
    plan = common.read(plan_path(out)); common.authenticate(plan['pins'])
    job = plan['jobs'][index]; config = plan['cases'][job['case']]
    folder = out/f'job-{index:02d}'; folder.mkdir()
    source,repair = derive(config,job['mass']); (folder/'model.asw').write_text(source)
    import numpy as np
    from openswing.asw import parse_asw
    from openswing.bridge import dispatch
    model = parse_asw(source,beam_interpolation='drela-segspl-v1'); assert not model.diagnostics
    beam = model.beams[0]; samples = np.array([-.28,0.,.28])
    layout = config['model']; rho = 0. if layout=='[45_0]_3a' else .0683
    constants = {'[0_90]_3s':dict(EIcc=.707,GJ=.183,EInn=276.,GKc=8.7e6,EA=3.7e6,GKn=2.9e5),
                 '[20_m70_20]_2a':dict(EIcc=.983,GJ=1.18,EInn=290.,GKc=1.1e6,EA=3.9e6,GKn=1.2e5),
                 '[45_0]_3a':dict(EIcc=.555,GJ=.854,EInn=279.,GKc=8.7e5,EA=3.7e6,GKn=2.2e5)}[layout]
    for field,value in dict(**constants,mg=rho*9.81).items():
        np.testing.assert_allclose(beam.value(field,samples),value,rtol=2e-15,atol=0)
    for field in ('Cea','Nea','Cta','Nta','Ccg','Ncg','Dmg','EIcs'):
        assert np.all(beam.value(field,samples)==0)
    twist = np.array([110.,77.5,45.]) if layout=='[45_0]_3a' else np.ones(3)
    angle = float(config['transform'].split()[1])
    twist = twist+angle if config['transform'][0]=='+' else twist*angle
    np.testing.assert_allclose(beam.value('twist',samples),twist,rtol=0,atol=1e-12)
    if layout=='[0_90]_3s':
        np.testing.assert_allclose(beam.value('mgcc',samples),5.13e-6,rtol=0,atol=0)
        assert np.all(beam.value('mgnn',samples)==0)
    request = dict(action='solve',mode='structural',source=source,
        panels=dict(default=job['nominal'],beams={'1':dict(count=job['nominal'],spacing='cosine')}),
        numerics=dict(beam_interpolation='drela-segspl-v1',structural_operator='drela-steady-section-v1'),
        gravity=[0.,0.,-9.81],loads=[],tolerance=1e-8,continuation_steps=4)
    common.write(folder/'request.json',request)
    started=time.monotonic(); result=dispatch(request); seconds=time.monotonic()-started
    common.write(folder/'result.json',result)
    nodes=sorted(result['nodes'],key=lambda n:n['t']); t=np.array([n['t'] for n in nodes]); r=np.array([n['position'] for n in nodes])
    assert len(nodes)==job['nominal']+2 and t[0]==-.28 and t[-1]==.28 and -.22 in t
    mass=np.zeros(len(t)); half=rho*np.diff(t)/2; mass[:-1]+=half; mass[1:]+=half; mass[0]+=job['mass']
    force=mass[:,None]*np.array([0.,0.,-9.81]); moment=np.cross(r,force).sum(axis=0)
    def relative(a,b):
        a,b=np.asarray(a),np.asarray(b)
        return float(np.max(abs(a-b))/(1+max(np.max(abs(a)),np.max(abs(b)))))
    checks=dict(residual=result['residual'],force_balance=relative(result['force_balance'],[0.,0.,0.]),
        moment_balance=relative(result['moment_balance'],[0.,0.,0.]),independent_force=relative(force.sum(axis=0),result['applied_force']),
        independent_moment=relative(moment,result['applied_moment']),clamp_position=float(np.max(abs(r[-1]-[0.,.28,0.]))),
        clamp_rotation=float(np.max(abs(np.asarray(nodes[-1]['rotation'])-np.eye(3)))))
    sensor=result['sensors'][0]; assert sensor['beam']==1 and sensor['t']==-.22
    np.testing.assert_allclose(sensor['anchor_position_body'],r[np.where(t==-.22)[0][0]],atol=1e-12,rtol=0)
    assert result['converged'] and checks['residual']<1e-8
    assert max(checks[k] for k in ('force_balance','moment_balance'))<1e-7
    assert max(checks[k] for k in ('independent_force','independent_moment'))<2e-10
    assert max(checks[k] for k in ('clamp_position','clamp_rotation'))<1e-10
    common.authenticate(plan['pins'])
    common.write(folder/'report.json',dict(observed_utc=common.utc(),job=job,checks=checks,repair=repair,
        position=sensor['anchor_position_body'],seconds=seconds,peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        plan_sha256=common.sha(plan_path(out)),artifacts={p.name:common.sha(p) for p in folder.iterdir() if p.is_file()}))
    print(dict(job_index=index,**job,position=sensor['anchor_position_body'],residual=checks['residual'],seconds=seconds))


def summarize(out):
    plan=common.read(plan_path(out)); common.authenticate(plan['pins']); reports=[]
    original=common.read(out/'plan.json')
    assert all(plan[k]==original[k] for k in ('cases','jobs','new_curve_required','relative_tolerance','protocol','limits'))
    accepted_plans={common.sha(plan_path(out)),common.sha(out/'plan.json')}
    if plan_path(out).name!='plan.json':
        assert common.sha(out/'initial-verifier/verify_st1_static_curves.py')==original['pins'][Path(__file__).relative_to(ROOT).as_posix()]
        assert {k:v for k,v in original['pins'].items() if k!=Path(__file__).relative_to(ROOT).as_posix()}=={k:v for k,v in plan['pins'].items() if k in original['pins'] and k!=Path(__file__).relative_to(ROOT).as_posix()}
    for i,job in enumerate(plan['jobs']):
        folder=out/f'job-{i:02d}'; report=common.read(folder/'report.json')
        assert report['job']==job and report['plan_sha256'] in accepted_plans
        for name,digest in report['artifacts'].items(): assert common.sha(folder/name)==digest
        reports.append(report)
    cases={}; rows=[]
    for name,config in plan['cases'].items():
        curve=[r for r in reports if r['job']['case']==name and r['job']['scope']=='curve']
        assert [r['job']['mass'] for r in curve]==config['masses']
        zero=curve[0]['position']; selected=[]
        for target in config['targets']:
            axis='xyz'.index(target['axis']); predicted=abs(curve[target['index']]['position'][axis]-zero[axis])
            error=abs(predicted-target['expected']); limit=max(target['original_absolute_tolerance'],.05*abs(target['expected']))
            selected.append(dict(**target,case=name,predicted=predicted,error_m=error,passed=error<=limit,
                error_percent=100*error/abs(target['expected']) if abs(target['expected'])>target['original_absolute_tolerance'] else None))
        fine=next(r for r in reports if r['job']['case']==name and r['job']['scope']=='refinement')
        delta=math.dist(fine['position'],curve[-1]['position'])
        cases[name]=dict(passed=sum(r['passed'] for r in selected),required=len(selected),unloaded_position=zero,
            max_nonzero_error_percent=max(r['error_percent'] or 0 for r in selected),
            loaded_refinement_change_m=delta,loaded_refinement_change_percent_of_deflection=100*delta/math.dist(curve[-1]['position'],zero))
        rows.extend(selected)
    previous=common.read(PRIOR/'summary.json')
    summary=dict(observed_utc=common.utc(),new_required=len(rows),new_passed=sum(r['passed'] for r in rows),
        combined_required=previous['combined_required']+len(rows),combined_passed=previous['combined_passed']+sum(r['passed'] for r in rows),
        cases=cases,rows=rows,prior_summary_sha256=common.sha(PRIOR/'summary.json'),plan_sha256=common.sha(plan_path(out)),
        primary_archive_passes_added=0,production_physics_changed=False,complete_family_validation=False)
    common.write(out/'summary.json',summary); print({k:v for k,v in summary.items() if k!='rows'})


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument('action',choices=('prepare','run','summary'))
    parser.add_argument('--output',type=Path,required=True); parser.add_argument('--index',type=int)
    args=parser.parse_args(); common.bounded()
    if args.action=='prepare': prepare(args.output.resolve())
    elif args.action=='run': run(args.output.resolve(),args.index)
    else: summarize(args.output.resolve())
