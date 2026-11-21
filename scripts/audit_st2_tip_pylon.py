"""Read-only, exact-decimal audit of the archived ST-2 tip-load arm."""
from decimal import Decimal
from pathlib import Path
import json

import verify_sa14_defaults as common
from isae_st2_archive import decode_archive_profile

ROOT=common.ROOT
BASE=ROOT/'reference/isae-validation/f62943df20e9e4d7d9f50e070477b22426b5f865/3 - Structure/CASE - ST2 Pazy_Wing/03_Static_Structural'
OUT=ROOT/'artifacts/isae/st2-modal-current-20261109'


def interval(field):
    value=Decimal(field['token']);half=Decimal(5).scaleb(value.as_tuple().exponent-1)
    scale=Decimal(10)**field['power10']
    return value*scale,(value-half)*scale,(value+half)*scale


def main():
    plan=common.read(ROOT/'artifacts/isae/st2-static-curves-20261109/plan.json');common.authenticate(plan['pins'])
    source=BASE/'Pazy_wing_bending_bench.asw';archive=BASE/'temp.txt'
    text=source.read_text();lines=text.splitlines()
    header=next(i for i,s in enumerate(lines) if s.split()==['t','Cea','Nea','Cta','Nta','Ccg','Ncg'])
    scale=lines[header+1].split();assert scale[0]=='*' and len(scale)==8 and all(Decimal(x)==0 for x in scale[2:])
    # Coincident reference/elastic/tension/CG axes make prime moments identical
    # here. Static gravity has no spin/acceleration torque; pylon normal arm=0.
    profile=decode_archive_profile(archive.read_text());tip=profile['rows'][-1]['fields']
    assert len(profile['rows'])==46 and Decimal(tip['t']['token'])==Decimal('.55')
    fn,nlo,nhi=interval(tip['Fn/10']);arms={}
    for component,name,sign,expected in [("Mc'/10",'span_arm_m',1,Decimal('.008')),("Ms'/10",'chord_arm_m',-1,Decimal('.05'))]:
        moment,lo,hi=interval(tip[component]);bounds=[sign*x/y for x in (lo,hi) for y in (nlo,nhi)]
        lower,upper=min(bounds),max(bounds);assert lower<=expected<=upper
        arms[name]=dict(expected=str(expected),inferred=str(sign*moment/fn),lower=str(lower),upper=str(upper),
            contains_expected=True,contains_zero=lower<=0<=upper)
        assert not arms[name]['contains_zero']
    replay=[]
    for i in (5,11):
        folder=ROOT/f'artifacts/isae/st2-static-curves-20261109/job-{i:02d}';report=common.read(folder/'report.json')
        assert report['job']['case']=='bending' and report['job']['mass_kg']==3.
        result=common.read(folder/'result.json');trace=result['elements'][-1]['endpoint_traces'][-1];assert trace['t']==.55
        values={"Mc'/10":trace['moment_local'][0],"Ms'/10":trace['moment_local'][1],'Fn/10':trace['force_local'][2]}
        checks=[]
        for key,value in values.items():
            expected,lo,hi=interval(tip[key]);assert lo<=Decimal.from_float(value)<=hi
            checks.append(dict(field=key,actual=value,printed_expected=str(expected),lower=str(lo),upper=str(hi),inside_printed_interval=True))
        replay.append(dict(nodes=len(result['nodes']),checks=checks))
    mass=(Decimal('31.45')/Decimal('9.81'))-Decimal('.3745')*Decimal('.55')
    uncertainty=Decimal('.005')/Decimal('9.81');assert mass-uncertainty<=3<=mass+uncertainty
    paths=[Path(__file__),ROOT/'scripts/isae_st2_archive.py',archive,source,
           ROOT/'reference/aswing-authoritative-20261108/drela-aswing-steady.txt',ROOT/'reference/aswing_doc.txt']
    evidence=dict(observed_utc=common.utc(),source_pins={p.relative_to(ROOT).as_posix():common.sha(p) for p in paths},
        equations='Drela steady section3.3, equations87-90 and95-96: M = r cross F; n_arm=0 gives Mc=s_arm*Fn and Ms=-c_arm*Fn.',
        exponent_row=profile['resultant_exponents'],tip_fields=tip,arms=arms,
        point_mass_from_total_weight_kg=dict(central=str(mass),lower=str(mass-uncertainty),upper=str(mass+uncertainty)),
        current_reconstruction_replay=replay,production_imports=0,solver_calls=0,
        conclusion='Archived resultants independently support an effective8mm spanwise and50mm chordwise rigid arm at the last printed beam station. '
            'Both current reconstructed endpoints match all three original printed resultant intervals. '
            'This supports the case reconstruction, not a universal native clamp rule or the exact generating input bytes.')
    common.write(OUT/'tip-pylon-audit.json',evidence);print(json.dumps(dict(arms=arms,replay=replay),indent=2))


if __name__=='__main__':main()
