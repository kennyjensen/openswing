"""Read-only joint/rigid-arm and native-resultant checks of the ST-2 study."""
from decimal import Decimal
from pathlib import Path
import re

import verify_st2_attachment_interpretations as study

common = study.common
OUT = study.ROOT/'artifacts/isae/st2-attachment-interpretations-20261109'
RUN = OUT/'refined'


def maxdiff(a, b):
    if isinstance(a, list):
        assert isinstance(b, list) and len(a) == len(b)
        return max((maxdiff(x, y) for x, y in zip(a, b, strict=True)), default=0.)
    return abs(a-b)


def main():
    common.bounded()
    plan=common.read(RUN/'plan.json');common.authenticate(plan['pins'])
    source=(study.BASE/'temp.txt').read_text()
    token=re.search(r'^\s*Weight\s*:\s*(\S+)',source,re.M)[1]
    expected=Decimal(token);half=Decimal(5).scaleb(expected.as_tuple().exponent-1)
    assert token == '31.45'
    records=[]
    for i, job in enumerate(plan['jobs']):
        folder=RUN/f'job-{i}';report=common.read(folder/'report.json')
        assert report['job']==job and report['plan_sha256']==common.sha(RUN/'plan.json')
        for name,digest in report['artifacts'].items():assert common.sha(folder/name)==digest
        result=common.read(folder/'result.json')
        main_nodes=[n for n in result['nodes'] if n['beam']==1]
        extension=[n for n in result['nodes'] if n['beam']==2]
        tip=max(main_nodes,key=lambda n:n['t'])
        joint={};rigid={}
        if extension:
            anchor=min(extension,key=lambda n:n['t'])
            joint={key:maxdiff(anchor[key],tip[key]) for key in ('position','rotation')}
            assert max(joint.values())<1e-10
        if job['variant']=='rigid_extension':
            rigid={'position':0.,'rotation':0.,'main_resultants':0.}
            for node in extension:
                expected_position=[tip['position'][k]+tip['rotation'][k][1]*(node['t']-.55) for k in range(3)]
                rigid['position']=max(rigid['position'],maxdiff(node['position'],expected_position))
                rigid['rotation']=max(rigid['rotation'],maxdiff(node['rotation'],tip['rotation']))
            baseline=common.read(study.PRIOR/f"job-{job['baseline_index']}"/'result.json')
            actual=[e for e in result['elements'] if e['beam']==1]
            for a,b in zip(actual,baseline['elements'],strict=True):
                for x,y in zip(a['endpoint_traces'],b['endpoint_traces'],strict=True):
                    for key in ('force','moment','force_local','moment_axes'):
                        rigid['main_resultants']=max(rigid['main_resultants'],maxdiff(x[key],y[key]))
            assert max(rigid.values())<1e-10
        weight=-result['applied_force'][2]
        weight_match=abs(Decimal.from_float(weight)-expected)<=half
        assert weight_match == (job['variant']!='elastic_massive')
        tip_rows=[r for r in report['rows'] if r['row']==45 and r['field'] in ("Mc'/10","Ms'/10",'Fn/10')]
        assert len(tip_rows)==3
        mc=next(r for r in tip_rows if r['field']=="Mc'/10")
        assert mc['strict_passed'] == (job['variant']=='rigid_extension')
        records.append(dict(job=job,joint_checks=joint,rigid_extension_checks=rigid,
            total_weight=dict(predicted=weight,expected_token=token,printed_halfwidth=str(half),passed=weight_match),
            native_tip_resultants=tip_rows))
    common.write(OUT/'attachment-audit.json',dict(observed_utc=common.utc(),
        plan_sha256=common.sha(RUN/'plan.json'),audit_sha256=common.sha(Path(__file__)),
        records=records,solver_calls=0,production_imports=0,
        primary_counts_unchanged=True,native_out_of_range_policy_verified=False,
        conclusion='Rigid extension exactly reproduces pylon kinematics and main-beam resultants. '
        'Both elastic alternatives miss the original tip Mc printed interval on both meshes; '
        'extending original distributed mass also misses total weight. '
        'These tests discriminate the specified physical alternatives, not every possible native input policy.'))
    print({'audited_states':len(records),'joint_states':sum(bool(r['joint_checks']) for r in records),
        'rigid_states':sum(bool(r['rigid_extension_checks']) for r in records),
        'maximum_rigid_error':max(v for r in records for v in r['rigid_extension_checks'].values())})


if __name__=='__main__':main()
