"""Check saved-field drag accounting and derive receiver-comparison summaries."""
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path

import numpy as np

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'artifacts/isae/sa11-drag-closure-20261108'
read=lambda p:json.loads(p.read_text())
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    result=read(OUT/'analysis.json')
    for name,digest in result['source_pins'].items():assert sha(ROOT/name)==digest,name
    assert result['physical_solves']==result['accepted_loads']==result['primary_passes_added']==0
    errors=dict(raw_force=0.,partitions=0.,identity=0.)
    summary=[]
    for case in result['cases']:
        angle=math.radians(case['alpha']);e=[math.cos(angle),0.,math.sin(angle)]
        folder=(ROOT/case['source_report']).parent
        for label,replay in case['replays'].items():
            with np.load(folder/f'{label}.npz') as f:
                force=f['force_terms'][:,0,:].copy();beam=f['beam'].copy();mach=f['mach'].copy()
            scale=.5*1.2256*240**2*.9329
            # Independent scalar dot/reduction of the original saved forces.
            terms=[math.fsum(float(a)*b for a,b in zip(v,e))/scale for v in force]
            expected=math.fsum(terms)
            errors['raw_force']=max(errors['raw_force'],abs(expected-replay['total']['near']))
            for i,part in replay['by_receiver_beam'].items():
                actual=math.fsum(v for v,b in zip(terms,beam) if b==int(i))
                errors['raw_force']=max(errors['raw_force'],abs(actual-part['near']))
            rejected=math.fsum(v for v,m in zip(terms,mach) if m>=1)
            errors['raw_force']=max(errors['raw_force'],abs(rejected-replay['rejected_receivers']['near']))
            assert replay['rejected_count']==np.count_nonzero(mach>=1)==2
            for key,value in replay['total'].items():
                errors['partitions']=max(errors['partitions'],abs(value-math.fsum(p[key] for p in replay['by_receiver_beam'].values())))
            for part in [replay['total'],replay['rejected_receivers'],*replay['by_receiver_beam'].values()]:
                errors['identity']=max(errors['identity'],abs(part['difference']-math.fsum(part[k] for k in ('axis','measure','bound','finite_origin'))))
        whole=case['replays']['whole-new'];native=case['replays']['native-new']
        shift=whole['total']['difference']-native['total']['difference']
        main=whole['finite_part_by_beam_pair']['1-1']-native['finite_part_by_beam_pair']['1-1']
        summary.append(dict(alpha=case['alpha'],gap=whole['total']['difference'],
            gap_percent_of_trefftz=100*whole['total']['difference']/whole['total']['trefftz'],
            root_share_percent=100*whole['rejected_receivers']['difference']/whole['total']['difference'],
            fixed_gamma_receiver_change=shift,main_self_part_change=main,
            main_self_share_of_receiver_change_percent=100*main/shift,
            beam_bound_measure_term=whole['total']['measure']))
    assert max(errors.values())<2e-12,errors
    verification=dict(observed_utc=datetime.now(timezone.utc).isoformat(),
        analysis_sha256=sha(OUT/'analysis.json'),checker_sha256=sha(Path(__file__)),
        verified_source_pins=len(result['source_pins']),field_replays=12,errors=errors,
        summary=summary,primary_passes_added=0,
        limits='Accounting of rejected states and prescribed cross-fields, not accepted forces or quadrature convergence.')
    (OUT/'verification.json').write_text(json.dumps(verification,indent=2,allow_nan=False)+'\n')
    print(json.dumps(verification))


if __name__=='__main__':main()
