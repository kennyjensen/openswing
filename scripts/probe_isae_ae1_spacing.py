"""Bounded, unscored AE-1 node-placement diagnostics from Drela 1989.

Retain the literal model and current equations; change only explicit base nodes.
The published full-wing distribution is mapped over the beam or its mirror half.
Neither mapping authenticates ASWING 5.x defaults or its local node adjustments.
"""
import argparse
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import resource
import signal
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import isae_suite_ae1 as adapter
from scripts.finalize_isae_ae1_saved import RAW_FILES, validate_saved


def read(path):
    return json.loads(Path(path).read_text())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, value):
    with Path(path).open('x') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')


def nodes(kind, n):
    u = [(2*j/n-1 if kind == 'whole' else j/n) for j in range(n+1)]
    # Eqs.37-38, checked using the equivalent sine expression.
    eta = [math.cos(math.pi/2*(1-v*(1+abs(v))/2)) for v in u]
    assert max(abs(a-math.sin(math.pi*v*(1+abs(v))/4)) for a,v in zip(eta,u)) < 5e-16
    s = [.55*((1+v)/2 if kind == 'whole' else v) for v in eta]
    s[0], s[-1] = 0., .55
    # Exact inverse of the literal straight beam's two linear y(t) segments.
    t = [.0001+v*(.52-.0001)/.52 if v <= .52 else v for v in s]
    t[0], t[-1] = .0001, .55
    assert all(a < b for a,b in zip(t,t[1:])) and .52 not in t
    return t, s


def checked_plan(out):
    plan = read(out/'plan.json')
    for path, digest in plan['pins'].items():
        assert sha(path) == digest, path
    return plan


def prepare(out):
    parent = ROOT/'artifacts/isae/ae1-full-current-20261110'
    original = read(parent/'plan.json')
    pins = dict(original['pins'])
    refs = ROOT/'reference/st4-node-placement-20261109'
    catalog = read(ROOT/'docs/validation/isae-st4-node-placement-sources-20261109.json')
    assert sha(refs/'drela-1989-wing-loads.pdf') == catalog['receipt']['sha256']
    assert sha(refs/'drela-1989-wing-loads.txt') == catalog['receipt']['text_sha256']
    for p in [Path(__file__), ROOT/'scripts/finalize_isae_ae1_saved.py',
              ROOT/'docs/validation/isae-st4-node-placement-sources-20261109.json',
              refs/'drela-1989-wing-loads.pdf', refs/'drela-1989-wing-loads.txt',
              ROOT/'reference/aswing_doc.txt']:
        pins[str(p)] = sha(p)
    source_dir = ROOT/'reference/aswing-authoritative-20261108'
    for catalog_name in ('drela-steady', 'isae-part-4'):
        source = read(source_dir/(catalog_name+'.json'))
        pdf = source_dir/source['filename']; text = pdf.with_suffix('.txt')
        assert sha(pdf) == source['sha256'] and sha(text) == source['text_sha256']
        for p in (pdf, text, source_dir/(catalog_name+'.json')):
            pins[str(p)] = sha(p)
    jobs = []
    for nominal in (40, 80):
        folder = parent/f'AE-1-a05-row018-m{nominal}-frozen'
        canonical = read(folder/'job.json')
        adapter.verify_reference_sources(ROOT, canonical)
        for name in ('job.json', 'strict-result.json', 'receipt.json', 'terminal.json'):
            pins[str(folder/name)] = sha(folder/name)
        for kind in ('whole', 'mirror-half'):
            t, s = nodes(kind, nominal)
            job = deepcopy(canonical)
            job['id'] = f'AE-1-spacing-{kind}-m{nominal}'
            job['panels'] = dict(default=nominal, beams={'1': dict(nodes=t)})
            job['reference_scope'] = 'Unscored node-placement diagnostic; no primary acceptance votes.'
            assert {k for k in job if job[k] != canonical[k]} == {'id','panels','reference_scope'}
            jobs.append(dict(job=job, kind=kind, material_y=s, parent_folder=str(folder)))
    for path,digest in pins.items():
        assert sha(path) == digest, path
    out.mkdir(parents=True)
    save(out/'plan.json', dict(observed_utc=datetime.now(timezone.utc).isoformat(),
        purpose=__doc__, pins=pins, jobs=jobs, primary_votes_added=0,
        limits=dict(blas_threads=1,address_space_mib=512,cpu_seconds=15,elapsed_seconds=25,supervisor_seconds=30),
        qualifications=[
            'Drela 1989 Eqs.37-38 concern ASWING 3.x; native 5.x node arrays are unknown.',
            'Whole maps the full symmetric rule across one beam; mirror-half uses its positive half for the wall-symmetric Pazy wing.',
            'The current exact .52 property-break insertion and 2015 Glauert-angle receiver rule remain unchanged.',
            'All geometry, properties, sensors, atmosphere, frozen influences and equations are unchanged.',
            'These alternative meshes do not add votes or change the completed 1200-slot primary scope.']))
    print('Prepared four unscored spacing probes; source and request pinned before execution.')


def run(out, index):
    assert all(os.environ.get(k) == '1' for k in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'))
    resource.setrlimit(resource.RLIMIT_AS,(512*1024**2,)*2)
    resource.setrlimit(resource.RLIMIT_CPU,(15,)*2)
    signal.alarm(25)
    start, cpu = time.monotonic(), time.process_time()
    plan = checked_plan(out); entry = plan['jobs'][index]; job = entry['job']
    folder = out/f'job-{index:02d}'; stage = folder/'raw'; stage.mkdir()
    save(stage/'job.json',job)
    # Independently bind material spacing to literal physical y, not arbitrary t.
    import numpy as np
    from openswing.asw import parse_asw
    from openswing.geometry import mesh_beam
    model = parse_asw(Path(job['source']).read_text(),beam_interpolation=job['settings']['beam_interpolation'])
    beam = model.beams[0]
    base = job['panels']['beams']['1']['nodes']
    actual_y = beam.position(np.array(base))[:,1].tolist()
    assert max(abs(a-b) for a,b in zip(actual_y,entry['material_y'])) < 2e-13
    mesh = mesh_beam(beam,job['panels'])
    bounds = sorted(actual_y+[.52])
    expected_receivers = [.55*(1-math.cos((math.acos(1-2*a/.55)+math.acos(1-2*b/.55))/2))/2
                          for a,b in zip(bounds,bounds[1:])]
    receiver_error = max(abs(a-b) for a,b in zip(expected_receivers,mesh.rm[:,1]))
    assert len(expected_receivers) == job['expected_elements'] and receiver_error < 2e-13
    save(stage/'spacing-preflight.json',dict(base_t=base,expected_y=entry['material_y'],actual_y=actual_y,
        element_t0=mesh.t0.tolist(),element_t1=mesh.t1.tolist(),receiver_t=mesh.tm.tolist(),
        receiver_y=mesh.rm[:,1].tolist(),expected_receiver_y=expected_receivers,receiver_max_error=receiver_error))
    values, checks = adapter._execute(ROOT,job,stage)
    assert len(checks) == 29 and all(c['passed'] for c in checks)
    checked_plan(out)
    save(folder/'receipt.json',dict(id=job['id'],physical_checks_passed=29,physical_checks_required=29,
        operations=read(stage/'operations.json'),values=values,primary_votes_added=0,
        wall_seconds=time.monotonic()-start,cpu_seconds=time.process_time()-cpu,
        peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss))
    print(job['id']+': all 29 physical checks pass',flush=True)


def launch(out,index):
    plan=checked_plan(out);assert index in range(len(plan['jobs']))
    folder=out/f'job-{index:02d}';folder.mkdir()
    started=datetime.now(timezone.utc).isoformat()
    with (folder/'stdout.log').open('x') as stdout,(folder/'stderr.log').open('x') as stderr:
        try:
            child=subprocess.run([sys.executable,str(Path(__file__)),'run','--output',str(out),'--index',str(index)],
                                 cwd=ROOT,stdout=stdout,stderr=stderr,timeout=30)
            terminal=dict(status='REAPED',returncode=child.returncode)
        except subprocess.TimeoutExpired:
            terminal=dict(status='SUPERVISOR_TIMEOUT_REAPED',returncode=None)
    terminal.update(started_utc=started,finished_utc=datetime.now(timezone.utc).isoformat())
    save(folder/'terminal.json',terminal);print(json.dumps(dict(index=index,**terminal)),flush=True)
    return 0 if terminal['returncode']==0 else 1


def assess(out):
    plan=checked_plan(out);rows=[];checks=0;pins={};receipts=[]
    for index,entry in enumerate(plan['jobs']):
        folder=out/f'job-{index:02d}';job=entry['job']
        assert read(folder/'terminal.json')['returncode']==0
        packet={name:read(folder/'raw'/name) for name in RAW_FILES}
        values,physical=validate_saved(job,packet);checks+=len(physical)
        receipt=read(folder/'receipt.json');assert receipt['values']==values
        receipts.append(receipt)
        baseline=read(Path(entry['parent_folder'])/'strict-result.json')
        baseline_values={c['name']:c['predicted'] for c in baseline['reference_checks']}
        for target in job['observations']:
            name=target['name'];expected=target['expected'];value=values[name]
            rows.append(dict(kind=entry['kind'],mesh=job['nominal'],name=name,expected=expected,predicted=value,
                absolute_error=abs(value-expected),error_percent=100*abs(value-expected)/abs(expected),
                cosine_predicted=baseline_values[name],change_from_cosine=value-baseline_values[name]))
        pins.update({str(p):sha(p) for p in folder.rglob('*') if p.is_file()})
    assert checks==116 and len(rows)==24
    assert not any(n=='openswing' or n.startswith('openswing.') for n in sys.modules)
    save(out/'assessment.json',dict(observed_utc=datetime.now(timezone.utc).isoformat(),status='PHYSICAL_AND_SAVED_DATA_AUDIT_PASS',
        plan_sha256=sha(out/'plan.json'),physical_checks_passed=checks,rows=rows,receipts=receipts,artifact_sha256=pins,
        production_imports=0,physical_calls=0,primary_votes_added=0,historical_mesh_recovered=False))
    print(json.dumps(dict(physical_checks_passed=checks,rows=[r for r in rows if 'RZ' in r['name']]),indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',choices=['prepare','run','launch','assess'])
    p.add_argument('--output',type=Path,required=True);p.add_argument('--index',type=int,default=0)
    args=p.parse_args();out=args.output.resolve()
    if args.action in ('prepare','assess'):
        resource.setrlimit(resource.RLIMIT_AS,(512*1024**2,)*2)
        resource.setrlimit(resource.RLIMIT_CPU,(15,)*2);signal.alarm(25)
    if args.action=='prepare':prepare(out)
    elif args.action=='run':run(out,args.index)
    elif args.action=='launch':raise SystemExit(launch(out,args.index))
    else:assess(out)
