"""Check saved moment bounds by independent 60-digit monotone bisection."""
import argparse
from datetime import datetime, timezone
from decimal import Decimal, localcontext
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--input',type=Path,required=True)
    args=p.parse_args();folder=args.input.resolve();output=folder/'verification.json'
    assert not output.exists(),output
    a=json.loads((folder/'analysis.json').read_text())
    for name,pin in a['source_pins'].items():assert sha(ROOT/name)==pin,name
    for name,pin in a['artifact_sha256'].items():assert sha(folder/name)==pin,name
    assert a['new_solves']==a['accepted_moments_for_winglet']==a['primary_passes_added']==0
    assert len(a['controls'])==2 and max(c['decimal_error'] for c in a['controls'])<2e-13
    assert [(r['alpha'],r['receivers']) for r in a['cases']]==[(0.,'native'),(0.,'whole'),(1.,'native'),(1.,'whole')]
    comparisons=[]
    with localcontext() as context:
        context.prec=60
        D=lambda x:Decimal.from_float(float(x))
        for r in a['cases']:
            assert r['full_predicted_Cm'] is None and len(r['actual_invalid_roots'])==2
            assert all(x['normal_mach']>=1 and x['coefficient']<0 for x in r['actual_invalid_roots'])
            ref=r['reference'];central=Decimal(ref['Cm_token'])
            half=Decimal(5).scaleb(central.as_tuple().exponent-1)
            assert ref['printing_interval']==[float(central-half),float(central+half)]
            assert ref['tolerance5_interval']==sorted([float(central*Decimal('.95')),float(central*Decimal('1.05'))])
            known=D(r['known_Cm_upper_bound']);scale=D(r['negative_root_scale'])
            for name,target_name in [('printing','printing_interval'),('tolerance5','tolerance5_interval')]:
                bound=r[name];lo,hi=map(D,ref[target_name])
                if lo>known:
                    assert not bound['feasible'] and bound['maximum_root_mach_lower_bound'] is None
                    comparisons.append(dict(alpha=r['alpha'],receivers=r['receivers'],interval=name,feasible=False))
                    continue
                assert bound['feasible']
                demand=max(known-hi,Decimal(0))
                left,right=Decimal(0),Decimal(1)
                if demand:
                    for _ in range(190):
                        midpoint=(left+right)/2
                        response=scale*midpoint**2/(1-midpoint**2).sqrt()
                        if response<demand:left=midpoint
                        else:right=midpoint
                    expected=(left+right)/2
                else:expected=Decimal(0)
                error=abs(float(expected)-bound['maximum_root_mach_lower_bound'])
                assert error<3e-15
                comparisons.append(dict(alpha=r['alpha'],receivers=r['receivers'],interval=name,feasible=True,
                                        independently_bisected_lower_bound=float(expected),absolute_error=error))
    record=dict(verified_utc=datetime.now(timezone.utc).isoformat(),source_pins_checked=len(a['source_pins']),
        artifact_pins_checked=len(a['artifact_sha256']),control_moment_checks=2,bound_checks=comparisons,
        analysis_sha256=sha(folder/'analysis.json'),script_sha256=sha(Path(__file__)),new_solves=0,
        rule='Independent monotone bisection of B*M^2/sqrt(1-M^2), preserving the conditional moment-only hypothesis and all rejected states.')
    output.write_text(json.dumps(record,indent=2)+'\n');print(json.dumps(record),flush=True)


if __name__=='__main__':main()
