"""Test the archived SA-11 speed-dependent moment against saved local fields.

No circulation solve, parameter fit, field substitution or accepted-state repair.
At fixed PG and geometry, steady forces divided by U**2 are invariant. Only
the section Cm factor changes with speed in these unforced rigid cases.
"""
import argparse
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from openswing.asw import parse_asw

FIXED = ROOT/'artifacts/isae/sa11-fixed-pg-candidate-20261108'
CURVED = ROOT/'artifacts/isae/sa11-curved-extension-r2-20261108'
PRIMARY = ROOT/'artifacts/isae/sa11-complete-scope-20261108'
read = lambda p: json.loads(p.read_text())
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
utc = lambda: datetime.now(timezone.utc).isoformat()


def dump(path, value):
    with path.open('x') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')


def pin(pins, path):
    pins[str(path.relative_to(ROOT))] = sha(path)


def decimal_interval(token):
    value = Decimal(token)
    half = Decimal(5).scaleb(value.as_tuple().exponent-1)
    return value, value-half, value+half


def archived_pair(plan, variant, alpha, pins):
    rows = []
    for label in ('0_75', '0_78'):
        jobs = [j for j in plan['jobs'] if j['variant'] == variant
                and j['mach_label'] == label and j['settings']['panels'] == 64
                and float(j['reference_row']['tokens'][71]) == alpha]
        assert len(jobs) == 1
        j = jobs[0]
        for source in j['sources']:
            p = ROOT/source['path']; assert sha(p) == source['sha256']; pin(pins, p)
        lines = (ROOT/j['table_path']).read_text().splitlines()
        tokens = [s.split() for s in lines if len(s.split()) == 82 and s.split()[0].isdigit()]
        tokens = [r for r in tokens if float(r[71]) == alpha]
        assert tokens == [j['reference_row']['tokens']]
        rows.append(tokens[0])
    assert [float(r[69]) for r in rows] == [255., 266.]
    # Difference isolates speed dependence only where loading is invariant to
    # the archive's printed precision. Keep the actual intervals in evidence.
    invariants = {}
    for name, column in [('CL',77), ('CD',78), ('CDi',79), ('efficiency',81)]:
        a, b = [decimal_interval(r[column]) for r in rows]
        assert max(a[1], b[1]) <= min(a[2], b[2]), (variant, alpha, name)
        invariants[name] = [r[column] for r in rows]
    a, b = [decimal_interval(r[80]) for r in rows]
    interval = [float(b[1]-a[2]), float(b[2]-a[1])]
    assert interval[1] < 0
    return dict(speeds=[255.,266.], Cm_tokens=[r[80] for r in rows],
                delta_Cm=float(b[0]-a[0]), delta_interval=interval,
                invariant_tokens=invariants)


def section_data(folder, model, low):
    strips = low['strips']
    assert all(s['lifting'] and not s['stalled'] for s in strips)
    assert low['residual'] < 1e-8 and low['mach'] == 0
    lengths = np.array([s['length'] for s in strips])
    speeds = np.array([s['normal_speed'] for s in strips])
    frames, chords, moments = [], [], []
    for s in strips:
        beam = next(b for b in model.beams if b.index == s['beam'])
        tangent = beam.position(s['t'], derivative=1)
        frames.append(tangent/np.linalg.norm(tangent))
        chords.append(beam.value('chord', s['t']))
        moments.append(beam.value('Cm', s['t']))
    span = np.asarray(frames); chord = np.asarray(chords); cm0 = np.asarray(moments)
    velocities = np.array([s['relative_velocity'] for s in strips])
    normal = velocities-np.sum(velocities*span,axis=1)[:,None]*span
    np.testing.assert_allclose(np.linalg.norm(normal,axis=1),speeds,rtol=3e-15,atol=2e-13)
    mach = speeds/model.constants[2]
    np.testing.assert_allclose(mach,[s['normal_mach'] for s in strips],rtol=2e-15)
    np.testing.assert_allclose(cm0/np.sqrt(1-mach**2),[s['cm'] for s in strips],rtol=3e-15)
    with np.load(folder/'state.npz') as state:
        np.testing.assert_array_equal(state['velocity'],velocities)
        np.testing.assert_array_equal(state['gamma'],[s['circulation'] for s in strips])
        assert np.min(state['stall_margin']) > 0
    # Moment reference translation cannot change the paired difference when
    # normalized forces are unchanged; verify exported origin bookkeeping.
    rho=low['atmosphere']['density']; area,cref,_=model.reference[0]
    q=.5*rho*255**2
    origin=np.sum([np.cross(s['position'],s['force'])+s['moment'] for s in strips],axis=0)
    np.testing.assert_allclose(origin,low['moment_origin'],rtol=2e-14,atol=1e-9)
    assert abs(origin[1]/(q*area*cref)-low['Cm_origin']) < 2e-14
    return dict(span=span,chord=chord,cm0=cm0,length=lengths,speed=speeds,mach=mach,
                weight=(speeds/255)**2*chord**2*cm0*span[:,1]*lengths/(area*cref))


def evaluate(spec, primary, pins):
    base = ROOT/spec['folder']; saved = read(base/'report.json')
    pin(pins,base/'report.json')
    for name, digest in saved['artifact_sha256'].items():
        p=base/name; assert sha(p)==digest,(spec['id'],name); pin(pins,p)
    choice = read(base/'input-choice.json')
    source=ROOT/choice['source']; pin(pins,source)
    model=parse_asw(source.read_text())
    model.reference[:]=choice['reference_after']
    # Retained diagnostic modifications affect lift slope only. No Cm,
    # geometry or force convention is inferred from the desired difference.
    assert all(c['field']=='dCLda' for c in choice['changes'])
    folder=base/spec['low_directory']; low=read(folder/'openswing.json')
    condition=read(folder/'condition.json')
    assert condition['speed']==255 and condition['mach']==0 and condition['freeze_influences']
    assert condition['alpha']==spec['alpha'] and condition['beta']==0
    for k in ('rates','acceleration','angular_acceleration'): assert condition[k]==[0.,0.,0.]
    assert not condition['controls'] and not condition['powers'] and condition['gust'] is None
    assert condition['ground_effect']==0 and condition['altitude_m']==0
    assert not low['engines'] and all(s['lifting'] for s in low['strips'])
    data=section_data(folder,model,low)
    reference=archived_pair(primary,choice['variant'],spec['alpha'],pins)
    scaled_mach=data['mach']*(266/255)
    row=dict(**spec,variant=choice['variant'],strips=len(data['weight']),
             reference=reference,Cm_low=low['Cm_origin'],maximum_M_low=float(data['mach'].max()),
             maximum_M_high=float(scaled_mach.max()),
             minimum_stall_margin_widths=(saved['production']['minimum_stall_margin_widths']
                 if isinstance(saved['production'],dict) else read(folder/'report.json')['minimum_stall_margin_widths']))
    if np.any(scaled_mach>=1):
        row.update(status='high-speed local-Mach rejection',predicted_delta_Cm=None,
                   predicted_Cm_high=None,primary_passes_added=0)
        return row,data
    contribution=data['weight']*(1/np.sqrt(1-scaled_mach**2)-1/np.sqrt(1-data['mach']**2))
    delta=float(contribution.sum()); predicted=low['Cm_origin']+delta
    lo,hi=reference['delta_interval']; observed=reference['delta_Cm']
    row.update(status='valid moment replay',predicted_delta_Cm=delta,predicted_Cm_high=predicted,
               delta_error_percent=100*(delta/observed-1),ratio_to_archived_delta=delta/observed,
               delta_inside_printing_interval=lo<=delta<=hi,
               distance_to_printing_interval=float(max(lo-delta,delta-hi,0)),
               Cm_low_error_percent=100*(low['Cm_origin']/float(reference['Cm_tokens'][0])-1),
               Cm_high_error_percent=100*(predicted/float(reference['Cm_tokens'][1])-1),
               intrinsic_Cm_low=float(np.sum(data['weight']/np.sqrt(1-data['mach']**2))),
               primary_passes_added=0)
    data['delta_contribution']=contribution
    if spec.get('high_directory'):
        high=read(base/spec['high_directory']/'openswing.json')
        high_condition=read(base/spec['high_directory']/'condition.json')
        assert high_condition==dict(condition,speed=266.)
        row['paired_saved_Cm_difference']=high['Cm_origin']-low['Cm_origin']
        row['paired_prediction_error']=abs(predicted-high['Cm_origin'])
        assert row['paired_prediction_error']<2e-14
        for k in ('CL','CD','CDi','CY'):
            assert abs(high[k]-low[k])<1e-12
        np.testing.assert_allclose(np.array([s['relative_velocity'] for s in high['strips']])/266,
                                   np.array([s['relative_velocity'] for s in low['strips']])/255,atol=2e-13,rtol=0)
    return row,data


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--output',type=Path,required=True)
    out=ap.parse_args().output.resolve();assert not out.exists();out.mkdir(parents=True)
    specs=[]
    for choice in ('baseline_original','baseline_slope634'):
        for alpha in (0.,1.):
            name=f'{choice}-a{alpha:.1f}-pg0'
            specs.append(dict(id=name,folder=str((FIXED/name).relative_to(ROOT)),alpha=alpha,
                              low_directory='u255',high_directory='u266'))
    for alpha in (0.,1.):
        for n in (64,128):
            name=f'candidate75-a{alpha:g}-n{n}'
            specs.append(dict(id=name,folder=str((CURVED/name).relative_to(ROOT)),alpha=alpha,
                              low_directory='production'))
    prior=[];pins={}
    for base in (FIXED,CURVED):
        plan=read(base/'plan.json');pin(pins,base/'plan.json')
        differences={name:dict(prior=digest,current=sha(ROOT/name)) for name,digest in plan['pins'].items()
                     if sha(ROOT/name)!=digest}
        # UI transport and status notes changed in the intervening completed
        # goal turn. They do not enter this saved-field arithmetic replay.
        assert set(differences)<= {'openswing/bridge.py','docs/validation/ISAE_STATUS.md'}
        for name in plan['pins']: pin(pins,ROOT/name)
        prior.append(dict(plan=str((base/'plan.json').relative_to(ROOT)),differences=differences))
    primary=read(PRIMARY/'plan.json');pin(pins,PRIMARY/'plan.json')
    assert sha(PRIMARY/'plan.json')==read(PRIMARY/'analysis.json')['plan_sha256']
    for p in (Path(__file__),ROOT/'docs/validation/aswing-authoritative-sources.json',
              ROOT/'docs/validation/isae-progress/history.json',ROOT/'docs/validation/isae-progress-scopes.json'):
        pin(pins,p)
    dump(out/'plan.json',dict(observed_utc=utc(),cases=specs,pins=pins,prior_snapshot_changes=prior,
        protocol='Eight saved 255m/s fields, published section moment law, paired original255/266m/s tokens; four independent saved high-speed checks. No solves or fitted/substituted velocities.',
        limits='Fixed zeroPG/normalization alternatives remain unauthenticated. A valid moment replay is not an accepted new aerodynamic result or a primary ISAE pass. A field reaching Mach1 at266m/s yields no moment.'))
    rows=[]
    for spec in specs:
        row,data=evaluate(spec,primary,pins);rows.append(row)
        np.savez(out/(spec['id']+'.npz'),**data)
        print(json.dumps(row),flush=True)
    for name,digest in pins.items():assert sha(ROOT/name)==digest,name
    summary=dict(observed_utc=utc(),cases=rows,source_sha256=pins,new_solver_calls=0,
        valid_moment_replays=sum(r['status']=='valid moment replay' for r in rows),
        rejected_moment_replays=sum(r['status']!='valid moment replay' for r in rows),
        primary_passes_added=0,primary_scope_changed=False,production_changed=False,
        artifact_sha256={p.name:sha(p) for p in out.iterdir() if p.is_file()})
    dump(out/'analysis.json',summary)


if __name__=='__main__':main()
