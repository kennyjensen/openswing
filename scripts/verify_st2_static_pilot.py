"""Recover the six published ASWING curves and check one declared tip-pylon case.

This is a diagnostic, not a change to the registered ST-2 denominator. Original
sources remain untouched. Each execution is one capped, serial two-state job.
"""
import argparse
from collections import Counter
from decimal import Decimal
from pathlib import Path
import re
import resource
import time

import verify_sa14_defaults as common

ROOT = common.ROOT
BASE = ROOT/'reference/isae-validation/f62943df20e9e4d7d9f50e070477b22426b5f865/3 - Structure/CASE - ST2 Pazy_Wing/03_Static_Structural'


def affine(ticks, coordinate):
    ordered = sorted(ticks, key=lambda t: t['value'])
    a, b = ordered[0], ordered[-1]
    scale = (b[coordinate]-a[coordinate])/(b['value']-a['value'])
    offset = a[coordinate]-scale*a['value']
    residual = max(abs(t[coordinate]-offset-scale*t['value']) for t in ticks)
    assert residual < 2e-5
    return dict(scale=scale, offset=offset, ticks=ticks, uncertainty=1e-5+residual)


def extract(path):
    raw = path.read_text()
    pattern = (r'\[([\d.]+) 0 0 ([\d.]+) ([-\d.]+) ([-\d.]+)\] CT\n'
               r'(?:[\d.]+ GC\n)?/[^\n]+ F\nGS\n\[1 0 0 1 0 0\] CT\n'
               r'[^\n]+\n1 -1 scale\n\(([-\d.]+)\) t')
    ticks = [dict(x=float(m[3]), y=float(m[4]), value=float(m[5]))
             for m in re.finditer(pattern, raw)]
    xgroup = Counter(t['y'] for t in ticks).most_common(1)[0][0]
    left = min(t['x'] for t in ticks)
    axes = dict(x=affine([t for t in ticks if t['y']==xgroup], 'x'),
                y=affine([t for t in ticks if t['x']==left], 'y'))
    selected = []
    for block in re.findall(r'GS\n(.*?)\nGR', raw, re.S):
        if '1 0 0 RC\n' not in block:
            continue
        curve = block.split('1 0 0 RC\n', 1)[1]
        points = re.findall(r'^([-\d.]+) ([-\d.]+) [ML]$', curve, re.M)
        if len(points)>2:
            selected.append((block, points))
    assert len(selected)==1
    block, points = selected[0]
    transform = re.match(r'\[([\d.]+) 0 0 ([\d.]+) ([-\d.]+) ([-\d.]+)\] CT',block)
    sx, sy, tx, ty = map(float, transform.groups())
    skin = int('_On_' in path.name)
    kind = 'bending' if 'Bending' in path.name else 'torsion'
    quantity = 'twist_deg' if '_theta' in path.name else 'displacement_m'
    loads_path = BASE/('05_Experimental_Bending' if kind=='bending' else '06_Experimental_Torsion')/f'static_{kind}_sweep_skin{skin}_disp_exp.txt'
    # Only the input load abscissae come from this file. Its measured ordinates
    # are not ASWING targets. The MATLAB producer explicitly uses this load list.
    loads = [float(line.split()[0]) for line in loads_path.read_text().splitlines() if line.strip()]
    assert len(loads)==len(points)
    rows=[]
    for load,(x,y) in zip(loads,points,strict=True):
        xhalf=float(Decimal(5).scaleb(Decimal(x).as_tuple().exponent-1))
        yhalf=float(Decimal(5).scaleb(Decimal(y).as_tuple().exponent-1))
        plotted_load=(sx*float(x)+tx-axes['x']['offset'])/axes['x']['scale']
        assert abs(plotted_load-load)<=(sx*xhalf+axes['x']['uncertainty'])/abs(axes['x']['scale'])+1e-12
        rows.append(dict(mass_kg=load,expected=(sy*float(y)+ty-axes['y']['offset'])/axes['y']['scale'],
            original_absolute_tolerance=(sy*yhalf+axes['y']['uncertainty'])/abs(axes['y']['scale']),
            original_tokens=[x,y]))
    return dict(skin=skin,kind=kind,quantity=quantity,axes=axes,targets=rows,
        source=path.relative_to(ROOT).as_posix(),source_sha256=common.sha(path),
        load_source=loads_path.relative_to(ROOT).as_posix(),load_source_sha256=common.sha(loads_path),
        source_line=raw[:raw.index(block)].count('\n')+1)


def prepare(out):
    out.mkdir(parents=True, exist_ok=True)
    curves={p.stem:extract(p) for p in sorted(BASE.glob('*.eps'))}
    assert len(curves)==6 and sum(len(c['targets']) for c in curves.values())==77
    files=[Path(__file__),ROOT/'scripts/verify_sa14_defaults.py',ROOT/'scripts/isae_st2.py',
           *sorted((ROOT/'openswing').glob('*.py')),
           *sorted(BASE.glob('*.m')),*sorted(BASE.glob('*.sh')),*sorted(BASE.glob('*.asw')),
           ROOT/'docs/validation/aswing-authoritative-references.md',ROOT/'docs/validation/aswing-authoritative-sources.json']
    pins={p.relative_to(ROOT).as_posix():common.sha(p) for p in files}
    for c in curves.values():
        pins[c['source']]=c['source_sha256'];pins[c['load_source']]=c['load_source_sha256']
    entry=next(e for e in common.read(ROOT/'docs/validation/aswing-authoritative-sources.json')['files'] if e['id']=='isae-part-3')
    for field,key in [('local_pdf','sha256'),('local_text','text_sha256')]:
        assert common.sha(ROOT/entry[field])==entry[key];pins[entry[field]]=entry[key]
    common.write(out/'plan.json',dict(observed_utc=common.utc(),pins=pins,curves=curves,
        jobs=[dict(nominal=n,kind='bending',skin=1,mass_kg=3.,layout='archive_pylon') for n in (39,79)],
        limits=dict(blas_threads=1,address_space_mib=512,cpu_seconds=15,wall_seconds=25),
        protocol='Part III p34 forty structural nodes: 39 prospective cosine intervals, then79 for refinement. '
            'Two masses totaling3kg at source coordinates(.05,.558,0), explicitly anchored at t=.55 by a rigid tip pylon. '
            'Only Weight records change; beam geometry, stiffness and distributed mass remain literal. '
            'Compare minus loaded-minus-unloaded tip z, exactly as Post_treatment.m. '
            'The attachment is a disclosed reconstruction, not recovered native handling. '
            'Six published ASWING curves are retained; only the skin-on maximum bending load is piloted.',
        relative_tolerance=.05,mesh_relative_gate=.01,primary_passes_added=0))
    print('Recovered77 ASWING ordinates; prepared two serial pilot jobs, with no registered-scope change.')


def run(out,index):
    plan=common.read(out/'plan.json');common.authenticate(plan['pins']);job=plan['jobs'][index]
    folder=out/f'job-{index}';folder.mkdir()
    from isae_st2 import static_model
    from openswing.bridge import dispatch
    import numpy as np
    rows=[];started=time.monotonic()
    for mass in (0.,job['mass_kg']):
        _,source,reconstruction=static_model(job['kind'],job['skin'],mass,job['layout'])
        request=dict(action='solve',mode='structural',source=source,
            panels=dict(default=job['nominal'],beams={'1':dict(count=job['nominal'],spacing='cosine')}),
            numerics=dict(beam_interpolation='drela-segspl-v1',structural_operator='drela-steady-section-v1'),
            gravity=[0.,0.,-9.81],loads=[],tolerance=1e-8,continuation_steps=4)
        common.write(folder/f'mass-{mass:g}-request.json',request)
        result=dispatch(request);common.write(folder/f'mass-{mass:g}-result.json',result)
        nodes=sorted(result['nodes'],key=lambda n:n['t']);assert len(nodes)==job['nominal']+1
        expected_force=np.array([0.,0.,-9.81*(mass+.3745*.55)])
        checks=dict(residual=result['residual'],force_balance=float(np.max(abs(np.asarray(result['force_balance'])))),
            moment_balance=float(np.max(abs(np.asarray(result['moment_balance'])))),
            gravity_force_error=float(np.max(abs(np.asarray(result['applied_force'])-expected_force))),
            clamp_position=float(np.max(abs(np.asarray(nodes[0]['position'])))),
            clamp_rotation=float(np.max(abs(np.asarray(nodes[0]['rotation'])-np.eye(3)))))
        assert result['converged'] and max(checks.values())<1e-7
        rows.append(dict(mass_kg=mass,tip_position=nodes[-1]['position'],checks=checks,reconstruction=reconstruction))
    predicted=-(rows[1]['tip_position'][2]-rows[0]['tip_position'][2])
    target=plan['curves']['Skin_On_Bending_bench_DZ']['targets'][-1];assert target['mass_kg']==3.
    error=abs(predicted-target['expected']);gate=max(target['original_absolute_tolerance'],.05*abs(target['expected']))
    common.authenticate(plan['pins'])
    report=dict(observed_utc=common.utc(),job=job,states=rows,target=target,predicted=predicted,
        error_percent=100*error/abs(target['expected']),within_five_percent=error<=gate,
        seconds=time.monotonic()-started,peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        plan_sha256=common.sha(out/'plan.json'),artifacts={p.name:common.sha(p) for p in folder.iterdir()})
    common.write(folder/'report.json',report)
    print({k:report[k] for k in ('job','predicted','error_percent','within_five_percent','seconds','peak_rss_kib')})


def main():
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['prepare','run'])
    parser.add_argument('--output',type=Path,required=True);parser.add_argument('--index',type=int)
    args=parser.parse_args()
    if args.action=='prepare':prepare(args.output)
    else:
        common.bounded();run(args.output,args.index)


if __name__=='__main__':main()
