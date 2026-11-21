"""Bound a root-intrinsic-moment-only explanation of saved SA-11 failures.

No solves, clipping, fitted parameters or accepted moments for invalid states.
The finite force moments and valid sections stay fixed; the two undefined
intrinsic moments are constrained only by the sign and subsonic law in Eq.73.
"""
import argparse
from datetime import datetime, timezone
from decimal import Decimal, localcontext
import importlib.util
import json
import math
from pathlib import Path
import shutil
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
SPEC = importlib.util.spec_from_file_location('receiver_study', ROOT/'scripts/verify-sa11-winglet-receivers.py')
STUDY = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(STUDY)
from openswing.asw import Distribution, parse_asw
from openswing.geometry import model_meshes

SOURCE = ROOT/'artifacts/isae/sa11-winglet-receivers-20261108'
CONTROLS = ROOT/'artifacts/isae/sa11-moment-receivers-20261108'
read, sha, write = STUDY.read, STUDY.sha, STUDY.write
utc = lambda: datetime.now(timezone.utc).isoformat()


def material(model, meshes):
    sample = lambda name: np.concatenate([m.beam.value(name, m.tm) for m in meshes])
    return dict(chord=sample('chord'), cm0=sample('Cm'), xax=sample('Xax'),
                span=np.concatenate([m.frames[...,1] for m in meshes]),
                chord_direction=np.concatenate([m.frames[...,0] for m in meshes]),
                rm=np.concatenate([m.rm for m in meshes]),
                centroid=np.concatenate([.5*(m.r0+m.r1) for m in meshes]),
                ds=np.concatenate([m.length for m in meshes]), reference=model.reference.copy())


def moments(data, forces, velocity, speed, density, sound_speed):
    chord, span, ds = data['chord'], data['span'], data['ds']
    lift = forces[:,0]; profile = forces[:,1:].sum(axis=1)
    arm = ((.25-data['xax'])*chord)[:,None]*data['chord_direction']
    scale = .5*density*speed**2*data['reference'][0,0]*data['reference'][0,1]
    lift_moment = np.cross(data['rm']+arm, lift)[:,1]/scale
    profile_moment = np.cross(data['centroid'], profile)[:,1]/scale
    vp = velocity-np.sum(velocity*span,axis=1)[:,None]*span
    normal_speed = np.linalg.norm(vp,axis=1); mach = normal_speed/sound_speed
    valid = mach < 1
    coefficient = chord**2*data['cm0']*span[:,1]*ds/(data['reference'][0,0]*data['reference'][0,1])
    # Evaluate sqrt only on the valid subset. NaNs are never used as zeros.
    intrinsic_valid = coefficient[valid]*(normal_speed[valid]/speed)**2/np.sqrt(1-mach[valid]**2)
    known = math.fsum(map(float,lift_moment))+math.fsum(map(float,profile_moment))+math.fsum(map(float,intrinsic_valid))
    return dict(force_lift_Cm=float(lift_moment.sum()), force_profile_Cm=float(profile_moment.sum()),
                intrinsic_valid_Cm=float(intrinsic_valid.sum()), known_Cm=float(known),
                invalid_count=int((~valid).sum()), coefficient=coefficient, valid=valid, mach=mach,
                lift_moment=lift_moment, profile_moment=profile_moment, intrinsic_valid=intrinsic_valid)


def decimal_replay(data, forces, velocity, speed, density, sound_speed):
    """50-digit independent scalar force moments and local-Mach correction."""
    D = lambda x: Decimal.from_float(float(x))
    with localcontext() as context:
        context.prec = 50
        qsc = D(.5)*D(density)*D(speed)**2*D(data['reference'][0,0])*D(data['reference'][0,1])
        known = Decimal(0); invalid = []
        for i in range(len(forces)):
            chord = D(data['chord'][i]); span = list(map(D,data['span'][i]))
            v = list(map(D,velocity[i])); dot = sum(x*y for x,y in zip(v,span))
            vp = [x-dot*y for x,y in zip(v,span)]; speed2 = sum(x*x for x in vp)
            ratio2 = speed2/D(sound_speed)**2
            lift = list(map(D,forces[i,0])); profile = [sum(D(forces[i,j,k]) for j in range(1,forces.shape[1])) for k in range(3)]
            point = [D(data['rm'][i,k])+(D(.25)-D(data['xax'][i]))*chord*D(data['chord_direction'][i,k]) for k in range(3)]
            centre = list(map(D,data['centroid'][i]))
            known += (point[2]*lift[0]-point[0]*lift[2]+centre[2]*profile[0]-centre[0]*profile[2])/qsc
            if ratio2 >= 1:
                invalid.append(i)
            else:
                known += (D(.5)*D(density)*speed2*chord**2*D(data['cm0'][i])*span[1]*D(data['ds'][i])/(1-ratio2).sqrt())/qsc
        return float(known), invalid


def reference_row(table, alpha):
    tokens = [line.split() for line in table.read_text().splitlines()]
    tokens = [t for t in tokens if len(t)==82 and t[0].isdigit() and float(t[71])==alpha]
    assert len(tokens)==1 and float(tokens[0][69])==240.
    value = Decimal(tokens[0][80]); half = Decimal(5).scaleb(value.as_tuple().exponent-1)
    return dict(tokens=tokens[0], Cm_token=tokens[0][80], Cm=float(value),
                printing_interval=[float(value-half),float(value+half)],
                tolerance5_interval=sorted([float(value*Decimal('.95')),float(value*Decimal('1.05'))]))


def envelope(target, known, scale):
    """Necessary moment-only feasibility; no candidate velocities are adopted.

    Negative root weights give rootCm=-B*h(M), h=M²/sqrt(1-M²).
    If all root Mach numbers <=m, |rootCm| <=B*h(m). Invert this
    inequality stably to obtain a lower bound on their maximum Mach.
    """
    lo,hi = target
    required = [lo-known,hi-known]
    if required[0] > 0:
        return dict(root_Cm_interval=required, feasible=False,
                    reason='Required root contribution is positive; both section Cm weights are negative.',
                    maximum_root_mach_lower_bound=None)
    demand = max(-required[1],0.)
    h = demand/scale
    epsilon = 4/(math.hypot(h,2)+h)**2
    minimum_maximum_mach = math.sqrt(max(0.,1-epsilon))
    distance_to_unity = epsilon/(1+minimum_maximum_mach)
    return dict(root_Cm_interval=required, feasible=True,
                reason='Necessary scalar moment condition only; it does not satisfy the velocity, force or circulation equations.',
                maximum_root_mach_lower_bound=minimum_maximum_mach,
                distance_of_lower_bound_from_unity=distance_to_unity)


def controls(pins):
    results = []
    for angle in (0,1):
        folder = CONTROLS/f'whole-beam-a{angle}'; report = read(folder/'report.json')
        for name,pin in report['artifact_sha256'].items(): assert sha(folder/name)==pin,name
        for p in [folder/'report.json',folder/'openswing.json',folder/'input-choice.json',folder/'mesh-settings.json',folder/'condition.json']:
            pins[str(p.relative_to(ROOT))]=sha(p)
        choice = read(folder/'input-choice.json'); source = ROOT/choice['source']; pins[choice['source']]=sha(source)
        model = parse_asw(source.read_text()); model.reference[:]=choice['reference_after']
        for change in choice['changes']:
            assert change['field']=='dCLda'
            beam = next(b for b in model.beams if b.index==change['beam']); d=beam.distributions['dCLda']
            beam.distributions['dCLda']=Distribution('dCLda',d.t.copy(),np.array(change['after']),d.line)
        meshes = model_meshes(model,read(folder/'mesh-settings.json')); data=material(model,meshes)
        saved = read(folder/'openswing.json'); condition=read(folder/'condition.json'); strips=saved['strips']
        v=np.array([s['relative_velocity'] for s in strips]); gamma=np.array([s['circulation'] for s in strips])
        total=np.array([s['force'] for s in strips]); rho=saved['atmosphere']['density']; speed=condition['speed']
        assert not saved['engines'] and all(s['lifting'] and not s['stalled'] for s in strips)
        assert np.max(abs(np.array([s['apparent_force'] for s in strips])))==0
        assert np.max(abs(np.array([s['circulation_rate_force'] for s in strips])))==0
        lift=rho*gamma[:,None]*np.cross(v,data['span'])*data['ds'][:,None]
        forces=np.stack([lift,total-lift],axis=1)
        r=moments(data,forces,v,speed,rho,340.21)
        scalar,invalid=decimal_replay(data,forces,v,speed,rho,340.21)
        assert not invalid and r['invalid_count']==0
        error=abs(r['known_Cm']-saved['Cm_origin']); independent=abs(scalar-saved['Cm_origin'])
        assert max(error,independent)<2e-13
        results.append(dict(alpha=angle,recorded_Cm_origin=saved['Cm_origin'],reconstructed=r['known_Cm'],
                            reconstruction_error=error,decimal_error=independent,
                            source=str((folder/'openswing.json').relative_to(ROOT))))
    return results


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    out=p.parse_args().output.resolve();assert not out.exists(),out
    prior=read(SOURCE/'analysis.json');plan=read(SOURCE/'plan.json')
    STUDY.check(plan['pins']);STUDY.check(prior['report_pins'])
    catalog=read(ROOT/'docs/validation/aswing-authoritative-sources.json')
    for item in catalog['files']:assert sha(ROOT/item['local_pdf'])==item['sha256']
    pins=dict(plan['pins'])
    for file in [Path(__file__),SOURCE/'analysis.json',SOURCE/'plan.json',ROOT/'scripts/isae_suite_polars.py']:
        pins[str(file.relative_to(ROOT))]=sha(file)
    model=STUDY.INC.model_at(-4.)
    table=STUDY.INC.FOLDER/'Aswing_Simulations/Wing_tip_up/wingtip_up_Ma_0_70.txt'
    pins[str(table.relative_to(ROOT))]=sha(table)
    out.mkdir(parents=True);shutil.copyfile(__file__,out/'driver-used.py')
    write(out/'plan.json',dict(observed_utc=utc(),cases=[dict(alpha=r['case']['alpha'],receivers=['native','whole']) for r in prior['cases']],
        initial_pins=pins, controls='Two already accepted baseline whole-beam moment states; no new solves.',
        reference='Drela steady Eqs.72-74 and221/225. Registered CM maps to origin moment, preserving literal area/chord and force conventions.',
        hypothesis='Only replace the intrinsic Cm contributions at the two invalid receivers; all finite force moments and valid intrinsic moments remain fixed. All root weights must retain their negative source signs.',
        rule='Unknown subsonic root moment can only lower the known coefficient. Compare its feasible half-line to original printed intervals and the existing5% band; inverse Mach is a necessary bound, not a fitted parameter or field repair.',
        limitation='Conditional diagnostic on report-minus4/native-endpoint setup. Does not test a consistent change of root velocity, force or circulation, and supplies no accepted moment or primary pass.'))
    control_results=controls(pins)
    rows=[]
    for report in prior['cases']:
        folder=SOURCE/report['case']['id']
        for name,pin in report['artifact_sha256'].items():assert sha(folder/name)==pin,name
        old=(ROOT/report['source_report']).parent
        original=read(ROOT/report['source_report'])
        for name,pin in original['artifact_sha256'].items():assert sha(old/name)==pin,name
        with np.load(old/'native-fields.npz') as f:native={k:f[k].copy() for k in f.files}
        _,segments=STUDY.INC.CONVERT.conversion(model,1)
        old_meshes,_,_,settings=STUDY.INC.CONVERT.mapped_meshes(model,native,segments)
        whole_meshes=model_meshes(model,dict(default=16,beams=settings))
        reference=reference_row(table,report['case']['alpha'])
        for receiver,meshes,label in [('native',old_meshes,'native-old'),('whole',whole_meshes,'whole-new')]:
            file=folder/f'{label}.npz';pins[str(file.relative_to(ROOT))]=sha(file)
            with np.load(file) as d:forces=d['force_terms'].copy();v=d['velocity'].copy();beam=d['beam'].copy();t=d['t'].copy()
            data=material(model,meshes)
            np.testing.assert_allclose(t,np.concatenate([m.tm for m in meshes]),atol=1e-14,rtol=0.)
            r=moments(data,forces,v,240.,1.2256,340.21)
            scalar,invalid=decimal_replay(data,forces,v,240.,1.2256,340.21)
            assert invalid==np.flatnonzero(~r['valid']).tolist()
            assert len(invalid)==2 and set(beam[invalid])=={2,3}
            assert np.all(r['coefficient']<0)
            error=abs(scalar-r['known_Cm']);assert error<2e-13
            root_scale=-(340.21/240)**2*float(r['coefficient'][~r['valid']].sum())
            root_required=reference['Cm']-r['known_Cm']
            record=dict(alpha=report['case']['alpha'],receivers=receiver,status='MOMENT_ONLY_FEASIBILITY_NOT_ACCEPTED_OUTPUT',
                reference=reference,force_lift_Cm=r['force_lift_Cm'],force_profile_Cm=r['force_profile_Cm'],
                valid_intrinsic_Cm=r['intrinsic_valid_Cm'],known_Cm_upper_bound=r['known_Cm'],
                full_predicted_Cm=None,root_required_for_central_token=root_required,
                negative_root_scale=root_scale,decimal_reconstruction_error=error,
                printing=envelope(reference['printing_interval'],r['known_Cm'],root_scale),
                tolerance5=envelope(reference['tolerance5_interval'],r['known_Cm'],root_scale),
                actual_invalid_roots=[dict(index=i,beam=int(beam[i]),t=float(t[i]),normal_mach=float(r['mach'][i]),coefficient=float(r['coefficient'][i])) for i in invalid])
            rows.append(record)
            np.savez(out/f'{receiver}-a{report["case"]["alpha"]:g}.npz',**data,force_terms=forces,velocity=v,
                     valid=r['valid'],mach=r['mach'],coefficient=r['coefficient'],lift_moment=r['lift_moment'],
                     profile_moment=r['profile_moment'],intrinsic_valid=r['intrinsic_valid'])
    STUDY.check(pins)
    result=dict(observed_utc=utc(),cases=rows,controls=control_results,source_pins=pins,
                new_solves=0,accepted_moments_for_winglet=0,primary_passes_added=0,
                artifact_sha256={p.name:sha(p) for p in out.iterdir() if p.is_file()})
    write(out/'analysis.json',result)
    print(json.dumps(dict(controls=control_results,cases=[{k:r[k] for k in ('alpha','receivers','reference','known_Cm_upper_bound','root_required_for_central_token','negative_root_scale','printing','tolerance5')} for r in rows])),flush=True)


if __name__=='__main__':main()
