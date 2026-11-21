"""Attribute saved SA-11 near/Trefftz differences without solving or editing fields."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import shutil

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
PRIOR = ROOT/'artifacts/isae/sa11-whole-beam-polar-20261108'
WAKE = ROOT/'artifacts/isae/sa11-whole-beam-wake-20261108'
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
read = lambda p: json.loads(p.read_text())


def write(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False)+'\n')


def bound_segment(point, start, end, beta):
    """Independent scalar finite-line integral in PG space, then P transpose.

    Rationalize same-side endpoint terms to avoid catastrophic subtraction
    when the probe is almost collinear with a distant segment.
    """
    pg = np.array([1/beta, 1., 1.])
    delta = (end-start)*pg
    length = np.linalg.norm(delta)
    direction = delta/length
    relative = (point-start)*pg
    h1 = float(relative@direction); h2 = h1-length
    transverse = relative-h1*direction
    radius2 = float(transverse@transverse)
    r1 = math.sqrt(h1*h1+radius2); r2 = math.sqrt(h2*h2+radius2)
    if h1*h2 > 0:
        factor = (h1*h1-h2*h2)/(r1*r2*(h1*r2+h2*r1))
    else:
        assert radius2 > 0
        factor = (h1/r1-h2/r2)/radius2
    return np.cross(direction, transverse)*factor/(4*math.pi)*pg


def ray_parts(point, origin, beta):
    """Semi-infinite body-x ray = half infinite ray + finite-origin term."""
    x, y, z = point-origin
    x /= beta
    transverse2 = y*y+z*z
    assert transverse2 > 0
    half = np.array([0., -z, y])/(4*math.pi*transverse2)
    tail = half*x/math.sqrt(x*x+transverse2)
    return half, tail


def matrices(geometry, points, beta):
    size = len(points)
    bound, half, tail = [np.zeros((size, size, 3)) for _ in range(3)]
    for i, point in enumerate(points):
        for j, (a, b) in enumerate(zip(geometry['a'], geometry['b'])):
            if i != j:
                bound[i,j] = bound_segment(point,a,b,beta)
            ha, ta = ray_parts(point,a,beta)
            hb, tb = ray_parts(point,b,beta)
            half[i,j], tail[i,j] = hb-ha, tb-ta
    return bound, half, tail


def main():
    assert all(os.environ.get(k)=='1' for k in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'))
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    out=parser.parse_args().output.resolve()
    assert not out.exists(),out
    prior=read(PRIOR/'analysis.json'); wake=read(WAKE/'analysis.json')
    assert sha(PRIOR/'analysis.json')==read(PRIOR/'verification.json')['analysis_sha256']
    assert sha(WAKE/'analysis.json')==read(WAKE/'verification.json')['analysis_sha256']
    pins={str(p.relative_to(ROOT)):sha(p) for p in [Path(__file__),PRIOR/'analysis.json',
        PRIOR/'verification.json',WAKE/'analysis.json',WAKE/'verification.json']}
    for item in read(ROOT/'docs/validation/aswing-authoritative-sources.json')['files']:
        p=ROOT/item['local_pdf']; assert sha(p)==item['sha256'];pins[str(p.relative_to(ROOT))]=sha(p)
    cases=[c for c in prior['cases'] if c['alpha'] in (0.,1.,5.)]
    assert len(cases)==3
    out.mkdir(parents=True)
    shutil.copyfile(__file__,out/'driver-used.py')
    write(out/'plan.json',dict(source_pins=pins,alphas=[0,1,5],
        labels=['native-old','native-new','whole-old','whole-new'],
        scope='Saved rejected report-minus4 states; 12 field replays, zero solves or accepted loads.',
        references='Drela steady Eqs64-70,149-161,207-211. Same bound-point sampling, own-bound exclusion, zero mutual core, and body-x frozen wake.',
        identity='Near_e - Trefftz_x = induced-force axis term + beam/bound measure term + bound_x + finite-origin wake_x.',
        limits='This partitions the existing finite discretization. Nonzero finite-origin plus bound contribution is not by itself proof of an erroneous equation, converged quadrature or an admissible correction.'))
    rows=[];errors=dict(velocity=0.,near_coefficient=0.,wake_coefficient=0.,closure=0.,pair_sum=0.,antisymmetric=0.)
    allpins=dict(pins)
    rho=1.2256;speed=240.;area=.9329;beta=math.sqrt(1-(speed/340.21)**2)
    scale=.5*rho*speed**2*area
    for case in cases:
        rp=ROOT/case['report'];assert sha(rp)==case['report_sha256'];r=read(rp)
        allpins[str(rp.relative_to(ROOT))]=sha(rp)
        for name,digest in r['artifact_sha256'].items():
            p=rp.parent/name;assert sha(p)==digest;allpins[str(p.relative_to(ROOT))]=digest
        assert r['production']['status']=='rejected' and r['production']['residual']<1e-8
        source=ROOT/r['source_report'];assert sha(source)==r['source_report_sha256']
        native=source.parent/'native-fields.npz';assert sha(native)==read(source)['artifact_sha256'][native.name]
        allpins[str(source.relative_to(ROOT))]=sha(source);allpins[str(native.relative_to(ROOT))]=sha(native)
        with np.load(native) as f:native_points=f['RV'].copy()
        with np.load(rp.parent/'geometry.npz') as f:g={k:f[k].copy() for k in f.files}
        theta=math.radians(case['alpha']);e=np.array([math.cos(theta),0.,math.sin(theta)])
        x=np.array([1.,0.,0.]); reference=next(c for c in wake['cases'] if c['alpha']==case['alpha'])
        operators={key:matrices(g,points,beta) for key,points in [('native',native_points),('whole',g['hv'])]}
        replays={}
        for label in ['native-old','native-new','whole-old','whole-new']:
            with np.load(rp.parent/f'{label}.npz') as f:d={k:f[k].copy() for k in f.files}
            gamma=d['gamma'];beam=d['beam'];bs=d['span']*d['ds'][:,None];segment=g['b']-g['a']
            bound,half,tail=operators[label.split('-')[0]]
            components=[np.einsum('ijk,j->ik',op,gamma) for op in (bound,half,tail)]
            induced=sum(components)
            errors['velocity']=max(errors['velocity'],float(np.max(abs(speed*e+induced-d['velocity']))))
            force=lambda v,measure:rho*gamma[:,None]*np.cross(v,measure)/scale
            beamforce=force(induced,bs);boundforce=force(induced,segment)
            near=beamforce@e
            wake_drag=force(components[1],segment)@x
            axis=beamforce@(e-x);measure=(beamforce-boundforce)@x
            bound_drag=force(components[0],segment)@x
            tail_drag=force(components[2],segment)@x
            difference=near-wake_drag
            errors['near_coefficient']=max(errors['near_coefficient'],abs(float(near.sum())-r['replays'][label]['CD_terms']['circulation']))
            errors['wake_coefficient']=max(errors['wake_coefficient'],abs(float(wake_drag.sum())-reference['replays'][label]['CDi']))
            errors['closure']=max(errors['closure'],float(np.max(abs(difference-axis-measure-bound_drag-tail_drag))))
            # Ordered receiver/source terms, summed into unordered beam pairs.
            kernel=np.cross(bound+tail,segment[:,None,:])[:,:,0]*rho/scale
            pairs=gamma[:,None]*kernel*gamma[None,:]
            symmetric=gamma[:,None]*(kernel+kernel.T)/2*gamma[None,:]
            antisymmetric=gamma[:,None]*(kernel-kernel.T)/2*gamma[None,:]
            errors['pair_sum']=max(errors['pair_sum'],abs(float(pairs.sum()-(bound_drag+tail_drag).sum())),abs(float(symmetric.sum()-pairs.sum())))
            errors['antisymmetric']=max(errors['antisymmetric'],abs(float(antisymmetric.sum())))
            by_pair={}
            for a in np.unique(beam):
                for b in np.unique(beam):
                    if b<a:continue
                    mask=(beam[:,None]==a)&(beam[None,:]==b)
                    if b!=a:mask|=(beam[:,None]==b)&(beam[None,:]==a)
                    by_pair[f'{a}-{b}']=float(pairs[mask].sum())
            def partition(mask):
                terms=dict(near=near,trefftz=wake_drag,difference=difference,axis=axis,measure=measure,bound=bound_drag,finite_origin=tail_drag)
                return {k:float(v[mask].sum()) for k,v in terms.items()}
            replays[label]=dict(total=partition(np.ones(len(gamma),dtype=bool)),
                by_receiver_beam={str(i):partition(beam==i) for i in np.unique(beam)},
                rejected_receivers=partition(d['mach']>=1),rejected_count=int(np.count_nonzero(d['mach']>=1)),
                finite_part_by_beam_pair=by_pair,
                maximum_local_mach=float(d['mach'].max()))
        rows.append(dict(alpha=case['alpha'],replays=replays,source_report=case['report']))
    assert errors['velocity']<2e-8,errors
    assert max(v for k,v in errors.items() if k!='velocity')<2e-12,errors
    for name,digest in allpins.items():assert sha(ROOT/name)==digest,name
    result=dict(observed_utc=datetime.now(timezone.utc).isoformat(),cases=rows,verification_errors=errors,
        source_pins=allpins,physical_solves=0,accepted_loads=0,primary_passes_added=0,
        diagnosis='Exact accounting at the saved sampling; not a converged continuum force or an accepted solution.')
    write(out/'analysis.json',result)
    print(json.dumps(dict(errors=errors,cases=[dict(alpha=c['alpha'],
        whole_new=c['replays']['whole-new']) for c in rows])),flush=True)


if __name__=='__main__':main()
