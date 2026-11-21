"""Six bounded current-source SA-12 attached-flow baseline states."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import resource
import signal
import sys

import isae_suite_sa12 as adapter

ROOT = Path(__file__).resolve().parents[1]
read = lambda p: json.loads(p.read_text())
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
utc = lambda: datetime.now(timezone.utc).isoformat()


def bounded():
    for name in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):
        assert os.environ.get(name)=='1'
    resource.setrlimit(resource.RLIMIT_AS,(512*1024**2,512*1024**2))
    resource.setrlimit(resource.RLIMIT_CPU,(15,15))
    signal.alarm(25)


def write(path,value):
    text=json.dumps(value,indent=2,allow_nan=False)+'\n'
    with path.open('x') as f:f.write(text)


def authenticate(pins):
    for path,digest in pins.items():assert sha(ROOT/path)==digest,path


def prepare(out):
    bounded();assert not out.exists()
    jobs=adapter.plan(ROOT)
    selected=[j for j in jobs if j['settings']['panels']==100 and
              j['settings']['alpha']==(8. if j['flap']=='No_Flap' else 0.)]
    assert len(selected)==6
    cases=[dict(id=f"{j['flap']}-h{j['height_label']}-a{j['settings']['alpha']:g}",job=j) for j in selected]
    pins={}
    for path in [*sorted((ROOT/'openswing').glob('*.py')),Path(__file__),
                 ROOT/'scripts/isae_suite_sa12.py',ROOT/'scripts/isae_suite_polars.py',
                 ROOT/'scripts/isae_suite_extra_polars.py',ROOT/'scripts/avl_vorvelc_reference.py',
                 ROOT/'docs/validation/aswing-authoritative-references.md',
                 ROOT/'docs/validation/aswing-authoritative-sources.json',ROOT/'docs/validation/isae-sa12-sources.json']:
        pins[str(path.relative_to(ROOT))]=sha(path)
    for case in cases:
        for source in case['job']['sources']:
            path=source['path'].replace('.reference/','reference/',1)
            assert sha(ROOT/path)==source['sha256']
            pins[path]=source['sha256']
    catalog=read(ROOT/'docs/validation/aswing-authoritative-sources.json')
    for entry in catalog['files']:
        if entry['id']=='isae-part-1' or entry['filename']=='drela-aswing-steady.pdf':
            for field,key in [('local_pdf','sha256'),('local_text','text_sha256')]:
                assert sha(ROOT/entry[field])==entry[key]
                pins[entry[field]]=entry[key]
    out.mkdir(parents=True)
    (out/'driver-used.py').write_text(Path(__file__).read_text())
    write(out/'plan.json',dict(observed_utc=utc(),cases=cases,pins=pins,
        protocol='Unchanged original SA12 models and raw archived CL/CD/CDi/Cm. Three heights .127,.508,1000m,solid images,current influences,Mach0,speed35.76,density1.2256. Declared board-parallel reconstruction pitch=alpha. No-flap alpha8 and equivalent slotted flap alpha0,100 current cosine intervals. One physical call per foreground invocation.',
        source_basis='Jan PartI numerical bench and Figure23; Drela steady section4.5,Eqs165--175. Shell drivers specify heights and K/F toggle; missing historical Euler pose remains explicit. No experiment matching or MATLAB replacement of raw CD.',
        acceptance='5% for non-tiny references; absolute reference magnitude<=1e-8 keeps the printed absolute gate. Numerical gates unchanged. Pilot is a subset of original4080checks and never added to it.',
        previous_goal_turn='Progress: SA11 coverage recorded21/48; user explicitly moved focus toSA12. SA11 follow-up stopped before any saved-state audit or new physical solve.',
        physical_calls=6,primary_passes_added=0,
        limits='One BLAS thread,512MiB address-space,15CPU/25wall seconds; no background,browser,build or multi-agent jobs.'))
    signal.alarm(0);print(dict(prepared=True,physical_calls=6,scalar_targets=24))


def run(out,index):
    bounded()
    plan=read(out/'plan.json');authenticate(plan['pins'])
    case=plan['cases'][index];directory=out/case['id'];assert not directory.exists()
    sys.path.insert(0,str(ROOT))
    row=adapter.run(ROOT,case['job'])
    comparisons=[]
    for check in row['reference_checks']:
        expected=check['expected'];value=check['predicted']
        tolerance=check['tolerance'] if abs(expected)<=1e-8 else max(check['tolerance'],.05*abs(expected))
        comparisons.append(dict(name=check['name'],expected=expected,actual=value,tolerance=tolerance,
            error_percent=None if value is None or abs(expected)<=1e-8 else 100*(value-expected)/abs(expected),
            passed=bool(row['numerical_pass'] and value is not None and abs(value-expected)<=tolerance)))
    directory.mkdir()
    write(directory/'result.json',row)
    payload=row.get('verification_payload')
    margin=None
    if row['numerical_pass']:
        import numpy as np
        from openswing.asw import parse_asw
        from openswing.geometry import model_meshes
        from openswing.frozen_influence import lifting_geometry
        job=case['job'];s=job['settings']
        model=parse_asw((ROOT/job['model_path']).read_text(),beam_interpolation=s['beam_interpolation'])
        meshes=model_meshes(model,s['panels'])
        alpha=math.radians(s['alpha']);e=np.array([math.cos(alpha),0,math.sin(alpha)])
        g=lifting_geometry(meshes,e)
        span=np.concatenate([m.frames[...,1] for m in meshes])
        np.testing.assert_allclose(g['hv'],[r['velocity_position'] for r in payload['strips']],rtol=0,atol=2e-12)
        np.savez(directory/'geometry.npz',**g,span=span)
        cl=np.array([r['cl'] for r in payload['strips']])
        upper=np.concatenate([m.beam.value('CLmax',m.tm) for m in meshes])
        lower=np.concatenate([m.beam.value('CLmin',m.tm) for m in meshes])
        margin=float(np.min(np.minimum(upper-cl,cl-lower)/s['stall_width']))
    report=dict(observed_utc=utc(),case=case,plan_sha256=sha(out/'plan.json'),
        status=row['status'],numerical_pass=row['numerical_pass'],physical_calls=row['physical_calls'],
        comparisons=comparisons,passed=sum(c['passed'] for c in comparisons),required=4,
        minimum_stall_margin_widths=margin,seconds=row['seconds'],peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        artifacts={p.name:sha(p) for p in directory.iterdir()})
    write(directory/'report.json',report)
    signal.alarm(0)
    print(json.dumps(report,indent=2) if not row['numerical_pass'] else json.dumps({key:report[key] for key in
        ('status','comparisons','minimum_stall_margin_widths','seconds','peak_rss_kib')},indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('prepare','run'))
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--index',type=int)
    args=parser.parse_args()
    if args.action=='prepare':prepare(args.output.resolve())
    else:run(args.output.resolve(),args.index)
