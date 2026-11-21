"""Audit ST-1 static bridges and update the same 200-slot archive view.

Two nominal-100 syntax-normalized inputs fill six existing slots. Refinements
and the separate published curve never add duplicate archive votes.
"""
from copy import deepcopy
from decimal import Decimal
import math
from pathlib import Path

import verify_sa14_defaults as common

ROOT=common.ROOT
OUT=ROOT/'artifacts/isae/st1-static-layouts-20261109'


def main():
    plan=common.read(OUT/'plan.json');common.authenticate(plan['pins'])
    base_path=ROOT/'artifacts/isae/st1-current-20261109/summary.json'
    base=common.read(base_path);rows=deepcopy(base['rows']);reports=[]
    source_pins=dict(plan['pins'])
    for path in (Path(__file__),base_path,OUT/'plan.json'):
        source_pins[path.relative_to(ROOT).as_posix()]=common.sha(path)
    for index,job in enumerate(plan['jobs']):
        folder=OUT/f'job-{index}';report=common.read(folder/'report.json')
        assert report['job']==job and report['plan_sha256']==common.sha(OUT/'plan.json')
        for name,digest in report['artifacts'].items():assert common.sha(folder/name)==digest
        original=(ROOT/job['archive_job']['model_path']).read_text()
        derived=(ROOT/job['source_path']).read_text()
        assert derived==original+'End\n' and common.sha(ROOT/job['source_path'])==job['derived_sha256']
        checks=report['numerical_checks']
        assert checks['residual']<=1e-8
        assert max(checks[k] for k in ('force_balance','moment_balance'))<=1e-7
        assert max(checks[k] for k in ('independent_force','independent_moment'))<=2e-10
        assert max(checks[k] for k in ('clamp_position','clamp_rotation'))<=1e-10
        source_tokens=(ROOT/job['archive_job']['table_path']).read_text().splitlines()[-1].split()
        assert source_tokens[2:]==[c['expected_token'] for c in report['comparisons']]
        result=common.read(folder/'result.json')
        for axis,(check,ref) in enumerate(zip(report['comparisons'],job['archive_job']['observations'],strict=True)):
            expected=Decimal(ref['expected_token']);absolute=Decimal(ref['exact_decimal_tolerance'])
            value=result['sensors'][0]['anchor_position_body'][axis]
            error=abs(Decimal(str(value))-expected);limit=max(absolute,abs(expected)*Decimal('.05'))
            assert value==check['predicted'] and bool(error<=limit)==check['passed'] and bool(error<=absolute)==check['strict_passed']
            if job['nominal']==100:
                target=next(r for r in rows if r['id']==job['archive_job']['id'] and r['name']==check['name'])
                assert target['predicted'] is None and target['expected_token']==check['expected_token']
                target.update(predicted=value,passed=check['passed'],strict_passed=check['strict_passed'],
                    abs_error=float(error),error_percent=check['error_percent'],
                    source_transform=job['transformation'],evidence=(folder/'report.json').relative_to(ROOT).as_posix())
        reports.append(report)
        source_pins[(folder/'report.json').relative_to(ROOT).as_posix()]=common.sha(folder/'report.json')
    assert len(rows)==200 and sum(r['predicted'] is None for r in rows)==188
    mesh=[]
    for first,second in ((reports[0],reports[1]),(reports[2],reports[3])):
        a=[r['predicted'] for r in first['comparisons']];b=[r['predicted'] for r in second['comparisons']]
        mesh.append(dict(layout=first['job']['key'],position_vector_change_m=math.dist(a,b),
            maximum_component_relative_change_percent=max(100*abs(x-y)/abs(x) for x,y in zip(a,b))))
    common.write(OUT/'summary.json',dict(observed_utc=common.utc(),required=200,
        passed=sum(r['passed'] for r in rows),strict_passed=sum(r['strict_passed'] for r in rows),
        unavailable=188,computed_mismatches=sum(not r['passed'] for r in rows if r['predicted'] is not None),
        numerically_valid=12,rows=rows,mesh_diagnostics=mesh,pins=source_pins,
        source_policy='Append only End to two empty Engine blocks; their primary N100 states replace six previously unavailable slots. '
            'N200 refinement and published baseline-subtracted curve remain separate; all other scope/settings and failed text targets retained.',
        complete_family_validation=False,production_modules_changed=0))
    print('ST-1 archive:',sum(r['passed'] for r in rows),'/ 200; 188 unavailable; 3 computed mismatches.')
    print('Mesh diagnostics:',mesh)


if __name__=='__main__':
    common.bounded();main()
